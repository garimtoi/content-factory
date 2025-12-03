"""아카이브 파일 스캐너 모듈

Issue #3: 아카이브 파일 스캐너 구현
- 재귀적 디렉토리 탐색
- 파일 유형별 분류
- 진행률 표시
- 중단 후 재개 기능
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from .config import AnalyzerConfig
from .database import Database, FileRecord, ScanCheckpoint
from .file_classifier import classify_file
from .smb_connector import FileInfo, SMBConnector

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """스캔 진행 상황"""

    scan_id: str
    total_files: int
    processed_files: int
    current_path: str
    files_per_second: float
    estimated_remaining: float  # seconds

    @property
    def percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    def __str__(self) -> str:
        return (
            f"[{self.percentage:.1f}%] "
            f"{self.processed_files:,}/{self.total_files:,} files | "
            f"{self.files_per_second:.1f} files/s | "
            f"ETA: {self.estimated_remaining:.0f}s"
        )


@dataclass
class ScanResult:
    """스캔 결과"""

    scan_id: str
    total_files: int
    total_size: int
    duration_seconds: float
    by_type: dict
    errors: List[str]

    def __str__(self) -> str:
        return (
            f"Scan Complete: {self.total_files:,} files, "
            f"{self.total_size / (1024**4):.2f} TB, "
            f"{self.duration_seconds:.1f}s"
        )


class ArchiveScanner:
    """아카이브 파일 스캐너

    SMB 연결을 통해 원격 아카이브를 스캔하고
    결과를 SQLite 데이터베이스에 저장합니다.
    """

    def __init__(
        self,
        connector: SMBConnector,
        database: Database,
        archive_path: str = "",
        batch_size: int = 100,
    ):
        """
        Args:
            connector: SMB 연결 관리자
            database: 데이터베이스 관리자
            archive_path: 스캔할 아카이브 경로 (공유 내 상대 경로)
            batch_size: 배치 저장 크기
        """
        self.connector = connector
        self.database = database
        self.archive_path = archive_path
        self.batch_size = batch_size

        self._scan_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._processed_count = 0
        self._total_count = 0
        self._errors: List[str] = []
        self._progress_callback: Optional[Callable[[ScanProgress], None]] = None

    def set_progress_callback(self, callback: Callable[[ScanProgress], None]) -> None:
        """진행률 콜백 설정"""
        self._progress_callback = callback

    def _notify_progress(self, current_path: str) -> None:
        """진행률 알림"""
        if self._progress_callback and self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            fps = self._processed_count / elapsed if elapsed > 0 else 0
            remaining = (self._total_count - self._processed_count) / fps if fps > 0 else 0

            progress = ScanProgress(
                scan_id=self._scan_id or "",
                total_files=self._total_count,
                processed_files=self._processed_count,
                current_path=current_path,
                files_per_second=fps,
                estimated_remaining=remaining,
            )
            self._progress_callback(progress)

    def _count_files(self, path: str = "") -> int:
        """디렉토리 내 총 파일 수 카운트"""
        count = 0
        scan_path = os.path.join(self.archive_path, path) if path else self.archive_path

        try:
            for info in self.connector.scan_directory(scan_path, recursive=True):
                if not info.is_dir:
                    count += 1
        except Exception as e:
            logger.warning(f"Error counting files in {scan_path}: {e}")

        return count

    def _file_info_to_record(self, info: FileInfo) -> FileRecord:
        """FileInfo를 FileRecord로 변환"""
        file_type = classify_file(info.name)
        parent = os.path.dirname(info.path)

        return FileRecord(
            path=info.path,
            filename=info.name,
            extension=info.extension,
            size_bytes=info.size,
            modified_at=datetime.fromtimestamp(info.modified_time) if info.modified_time else None,
            file_type=file_type.value,
            parent_folder=parent,
            scan_status="scanned",
        )

    def scan(
        self,
        resume_scan_id: Optional[str] = None,
        count_first: bool = False,  # #39 - 기본값 False로 변경 (이중 스캔 방지)
    ) -> ScanResult:
        """아카이브 스캔 실행

        Args:
            resume_scan_id: 재개할 스캔 ID (없으면 새 스캔)
            count_first: 총 파일 수 먼저 카운트 여부
                        (False 권장 - 네트워크 I/O 절감)

        Returns:
            ScanResult 객체
        """
        # 연결 확인
        if not self.connector.is_connected:
            self.connector.connect()

        # 스캔 초기화
        self._scan_id = resume_scan_id or str(uuid.uuid4())[:8]
        self._start_time = datetime.now()
        self._processed_count = 0
        self._errors = []

        logger.info(f"Starting scan: {self._scan_id}")
        logger.info(f"Archive path: {self.archive_path}")

        # 체크포인트 확인 (재개 시)
        checkpoint = None
        resume_from_path = None

        if resume_scan_id:
            checkpoint = self.database.get_checkpoint(resume_scan_id)
            if checkpoint and checkpoint.status != "completed":
                resume_from_path = checkpoint.last_path
                self._processed_count = checkpoint.processed_files
                logger.info(f"Resuming from: {resume_from_path}")

        # 총 파일 수 카운트 (#39 - 기본적으로 스킵하여 이중 스캔 방지)
        if count_first:
            logger.info("Counting files... (네트워크 I/O 추가 발생)")
            self._total_count = self._count_files()
            logger.info(f"Total files to scan: {self._total_count:,}")
        else:
            self._total_count = checkpoint.total_files if checkpoint else 0
            if self._total_count == 0:
                logger.info("Scanning without file count (progress percentage unavailable)")

        # 체크포인트 생성/업데이트
        if not checkpoint:
            checkpoint = ScanCheckpoint(
                scan_id=self._scan_id,
                total_files=self._total_count,
                processed_files=0,
                status="in_progress",
            )
            self.database.save_checkpoint(checkpoint)

        # 스캔 실행
        batch: List[FileRecord] = []
        skip_until_resume = resume_from_path is not None
        stats_by_type = {}

        try:
            for info in self.connector.scan_directory(self.archive_path, recursive=True):
                # 디렉토리 건너뛰기
                if info.is_dir:
                    continue

                # 재개 지점까지 건너뛰기 (#32 - 재개 파일 자체는 처리)
                if skip_until_resume:
                    if info.path == resume_from_path:
                        skip_until_resume = False
                        # resume 파일은 이미 처리되었으므로 건너뛰기
                        continue
                    else:
                        continue

                try:
                    # 레코드 생성
                    record = self._file_info_to_record(info)
                    batch.append(record)

                    # 통계 업데이트
                    ft = record.file_type
                    if ft not in stats_by_type:
                        stats_by_type[ft] = {"count": 0, "size": 0}
                    stats_by_type[ft]["count"] += 1
                    stats_by_type[ft]["size"] += record.size_bytes

                    self._processed_count += 1

                    # 배치 저장
                    if len(batch) >= self.batch_size:
                        self.database.insert_files_batch(batch)
                        self.database.update_checkpoint_progress(
                            self._scan_id, info.path, self._processed_count
                        )
                        batch = []

                    # 진행률 알림
                    if self._processed_count % 100 == 0:
                        self._notify_progress(info.path)

                except Exception as e:
                    error_msg = f"Error processing {info.path}: {e}"
                    logger.warning(error_msg)
                    self._errors.append(error_msg)

            # 남은 배치 저장
            if batch:
                self.database.insert_files_batch(batch)

            # 체크포인트 완료
            self.database.complete_checkpoint(self._scan_id)

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            self._errors.append(str(e))
            raise

        # 결과 생성
        duration = (datetime.now() - self._start_time).total_seconds()
        total_size = sum(s["size"] for s in stats_by_type.values())

        result = ScanResult(
            scan_id=self._scan_id,
            total_files=self._processed_count,
            total_size=total_size,
            duration_seconds=duration,
            by_type=stats_by_type,
            errors=self._errors,
        )

        logger.info(str(result))
        return result

    def quick_scan(self) -> dict:
        """빠른 스캔 (DB 저장 없이 통계만)

        Returns:
            파일 유형별 통계 딕셔너리
        """
        if not self.connector.is_connected:
            self.connector.connect()

        stats = {
            "total_files": 0,
            "total_size": 0,
            "by_type": {},
        }

        logger.info(f"Quick scanning: {self.archive_path}")

        for info in self.connector.scan_directory(self.archive_path, recursive=True):
            if info.is_dir:
                continue

            file_type = classify_file(info.name).value
            if file_type not in stats["by_type"]:
                stats["by_type"][file_type] = {"count": 0, "size": 0}

            stats["by_type"][file_type]["count"] += 1
            stats["by_type"][file_type]["size"] += info.size
            stats["total_files"] += 1
            stats["total_size"] += info.size

            if stats["total_files"] % 100 == 0:
                logger.debug(f"Scanned {stats['total_files']} files...")

        logger.info(f"Quick scan complete: {stats['total_files']:,} files")
        return stats


def create_scanner(config: AnalyzerConfig) -> ArchiveScanner:
    """스캐너 팩토리 함수

    Args:
        config: 분석기 설정

    Returns:
        ArchiveScanner 인스턴스
    """
    from .smb_connector import SMBConnector

    connector = SMBConnector(config.smb)
    database = Database(config.database_path)

    return ArchiveScanner(
        connector=connector,
        database=database,
        archive_path=config.archive_path,
        batch_size=config.batch_size,
    )


def scan_archive(
    server: str,
    share: str,
    username: str,
    password: str,
    archive_path: str = "",
    db_path: str = "archive.db",
    progress_callback: Optional[Callable[[ScanProgress], None]] = None,
) -> ScanResult:
    """간편 스캔 함수

    Args:
        server: SMB 서버 주소
        share: 공유 이름
        username: 사용자명
        password: 비밀번호
        archive_path: 아카이브 경로
        db_path: 데이터베이스 경로
        progress_callback: 진행률 콜백

    Returns:
        ScanResult 객체
    """
    from .smb_connector import quick_connect

    connector = quick_connect(server, share, username, password)
    database = Database(db_path)

    try:
        scanner = ArchiveScanner(
            connector=connector,
            database=database,
            archive_path=archive_path,
        )

        if progress_callback:
            scanner.set_progress_callback(progress_callback)

        return scanner.scan()

    finally:
        connector.disconnect()
        database.close()
