"""SMB 네트워크 연결 모듈

Issue #2: SMB 네트워크 연결 모듈 구현
- SMB 2/3 프로토콜 지원
- 연결 풀링 및 재사용
- 연결 실패 시 재시도 로직
- 연결 상태 모니터링
"""

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

from smbclient import (
    delete_session,
    listdir,
    open_file,
    register_session,
    scandir,
    stat,
)
from smbclient.path import exists, isdir

from .config import AnalyzerConfig, SMBConfig

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """파일 정보 데이터 클래스"""

    path: str
    name: str
    size: int
    is_dir: bool
    modified_time: float
    extension: str

    @classmethod
    def from_stat(cls, path: str, name: str, stat_result: Any) -> "FileInfo":
        """stat 결과에서 FileInfo 생성"""
        is_directory = bool(stat_result.st_file_attributes & 0x10)
        ext = os.path.splitext(name)[1].lower() if not is_directory else ""

        return cls(
            path=path,
            name=name,
            size=stat_result.st_size,
            is_dir=is_directory,
            modified_time=stat_result.st_mtime,
            extension=ext,
        )


class SMBConnectionError(Exception):
    """SMB 연결 오류"""

    pass


class SMBConnector:
    """SMB 네트워크 연결 관리자

    Features:
    - 세션 관리 (연결/해제)
    - 자동 재시도
    - 디렉토리 탐색
    - 파일 정보 조회
    """

    def __init__(self, config: SMBConfig):
        """
        Args:
            config: SMB 연결 설정
        """
        self.config = config
        self._connected = False
        self._retry_count = 0

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connected

    @property
    def base_path(self) -> str:
        """기본 공유 경로"""
        return self.config.share_path

    def connect(self) -> bool:
        """SMB 세션 연결

        Returns:
            연결 성공 여부
        """
        if self._connected:
            logger.debug("Already connected")
            return True

        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Connecting to {self.config.server}... (attempt {attempt + 1})")

                register_session(
                    self.config.server,
                    username=self.config.username,
                    password=self.config.password,
                    port=self.config.port,
                    connection_timeout=self.config.timeout,
                )

                # 연결 테스트
                test_path = self.base_path
                if exists(test_path):
                    self._connected = True
                    self._retry_count = 0
                    logger.info(f"Connected to {self.config.server}")
                    return True
                else:
                    raise SMBConnectionError(f"Share path not accessible: {test_path}")

            except Exception as e:
                self._retry_count = attempt + 1
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to connect after {self.config.max_retries} attempts")
                    raise SMBConnectionError(f"Connection failed: {e}") from e

        return False

    def disconnect(self) -> None:
        """SMB 세션 해제"""
        if self._connected:
            try:
                delete_session(self.config.server)
                logger.info(f"Disconnected from {self.config.server}")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._connected = False

    def _ensure_connected(self) -> None:
        """연결 상태 확인 및 재연결"""
        if not self._connected:
            self.connect()

    def _build_path(self, *parts: str) -> str:
        """경로 조합"""
        base = self.base_path
        for part in parts:
            if part:
                base = os.path.join(base, part)
        return base

    def list_directory(self, path: str = "") -> List[str]:
        """디렉토리 내용 조회

        Args:
            path: 상대 경로 (기본: 공유 루트)

        Returns:
            파일/폴더 이름 목록
        """
        self._ensure_connected()
        full_path = self._build_path(path)

        try:
            items = listdir(full_path)
            # 숨김 파일 제외
            return [item for item in items if not item.startswith(".")]
        except Exception as e:
            logger.error(f"Failed to list directory {full_path}: {e}")
            raise

    def get_file_info(self, path: str) -> FileInfo:
        """파일/폴더 정보 조회

        Args:
            path: 상대 경로

        Returns:
            FileInfo 객체
        """
        self._ensure_connected()
        full_path = self._build_path(path)

        try:
            stat_result = stat(full_path)
            name = os.path.basename(path) or self.config.share
            return FileInfo.from_stat(full_path, name, stat_result)
        except Exception as e:
            logger.error(f"Failed to get file info {full_path}: {e}")
            raise

    def scan_directory(self, path: str = "", recursive: bool = False) -> Iterator[FileInfo]:
        """디렉토리 스캔 (제너레이터)

        Args:
            path: 상대 경로
            recursive: 하위 디렉토리 포함 여부

        Yields:
            FileInfo 객체
        """
        self._ensure_connected()
        full_path = self._build_path(path)

        try:
            for entry in scandir(full_path):
                if entry.name.startswith("."):
                    continue

                try:
                    stat_result = entry.stat()
                    file_info = FileInfo.from_stat(entry.path, entry.name, stat_result)
                    yield file_info

                    # 재귀 스캔
                    if recursive and file_info.is_dir:
                        sub_path = os.path.join(path, entry.name) if path else entry.name
                        yield from self.scan_directory(sub_path, recursive=True)

                except Exception as e:
                    logger.warning(f"Failed to process {entry.path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to scan directory {full_path}: {e}")
            raise

    def file_exists(self, path: str) -> bool:
        """파일 존재 여부 확인"""
        self._ensure_connected()
        full_path = self._build_path(path)
        return exists(full_path)

    def is_directory(self, path: str) -> bool:
        """디렉토리 여부 확인"""
        self._ensure_connected()
        full_path = self._build_path(path)
        return isdir(full_path)

    def read_file(self, path: str, mode: str = "rb") -> bytes:
        """파일 내용 읽기

        Args:
            path: 상대 경로
            mode: 읽기 모드

        Returns:
            파일 내용
        """
        self._ensure_connected()
        full_path = self._build_path(path)

        try:
            with open_file(full_path, mode=mode) as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {full_path}: {e}")
            raise

    @contextmanager
    def open_file(self, path: str, mode: str = "rb"):
        """파일 열기 컨텍스트 매니저

        Args:
            path: 상대 경로 또는 전체 경로
            mode: 파일 모드

        Yields:
            파일 객체
        """
        self._ensure_connected()

        # 전체 경로인지 확인
        if path.startswith("\\\\") or path.startswith("//"):
            full_path = path
        else:
            full_path = self._build_path(path)

        try:
            with open_file(full_path, mode=mode) as f:
                yield f
        except Exception as e:
            logger.error(f"Failed to open file {full_path}: {e}")
            raise

    def get_connection_status(self) -> dict:
        """연결 상태 정보 반환"""
        return {
            "connected": self._connected,
            "server": self.config.server,
            "share": self.config.share,
            "retry_count": self._retry_count,
        }

    @contextmanager
    def connection(self):
        """컨텍스트 매니저로 연결 관리

        Usage:
            with connector.connection():
                files = connector.list_directory()
        """
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.disconnect()
        return False


def create_connector(config: Optional[AnalyzerConfig] = None) -> SMBConnector:
    """SMBConnector 팩토리 함수

    Args:
        config: 분석기 설정 (없으면 환경변수에서 로드)

    Returns:
        SMBConnector 인스턴스
    """
    if config is None:
        config = AnalyzerConfig.from_env()

    return SMBConnector(config.smb)


def quick_connect(server: str, share: str, username: str, password: str, **kwargs) -> SMBConnector:
    """빠른 연결을 위한 헬퍼 함수

    Args:
        server: SMB 서버 주소
        share: 공유 이름
        username: 사용자명
        password: 비밀번호
        **kwargs: 추가 SMBConfig 옵션

    Returns:
        연결된 SMBConnector
    """
    config = SMBConfig(server=server, share=share, username=username, password=password, **kwargs)
    connector = SMBConnector(config)
    connector.connect()
    return connector
