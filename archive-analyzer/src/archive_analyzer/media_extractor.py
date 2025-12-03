"""미디어 메타데이터 추출 모듈

비디오/오디오 파일에서 기술 메타데이터를 추출합니다.
- FFprobe를 사용한 메타데이터 추출
- SMB 파일 스트리밍 지원
- 배치 처리 지원

Issue #8: 미디어 메타데이터 추출기 구현 (FR-002)
"""

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .smb_connector import SMBConnector

logger = logging.getLogger(__name__)


@dataclass
class MediaInfo:
    """미디어 메타데이터"""

    file_id: Optional[int] = None
    file_path: str = ""

    # 비디오 정보
    video_codec: Optional[str] = None
    video_codec_long: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    framerate: Optional[float] = None
    video_bitrate: Optional[int] = None

    # 오디오 정보
    audio_codec: Optional[str] = None
    audio_codec_long: Optional[str] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    audio_bitrate: Optional[int] = None

    # 일반 정보
    duration_seconds: Optional[float] = None
    bitrate: Optional[int] = None
    container_format: Optional[str] = None
    format_long_name: Optional[str] = None
    file_size: Optional[int] = None

    # 추가 정보
    has_video: bool = False
    has_audio: bool = False
    video_stream_count: int = 0
    audio_stream_count: int = 0
    subtitle_stream_count: int = 0

    # 메타데이터
    title: Optional[str] = None
    creation_time: Optional[str] = None

    # 처리 상태
    extraction_status: str = "pending"
    extraction_error: Optional[str] = None
    extracted_at: Optional[datetime] = None

    @property
    def resolution(self) -> Optional[str]:
        """해상도 문자열 (예: 1920x1080)"""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None

    @property
    def resolution_label(self) -> Optional[str]:
        """해상도 라벨 (예: 1080p, 4K)"""
        if not self.height:
            return None
        if self.height >= 2160:
            return "4K"
        elif self.height >= 1440:
            return "1440p"
        elif self.height >= 1080:
            return "1080p"
        elif self.height >= 720:
            return "720p"
        elif self.height >= 480:
            return "480p"
        else:
            return f"{self.height}p"

    @property
    def duration_formatted(self) -> Optional[str]:
        """시간 포맷 (HH:MM:SS)"""
        if self.duration_seconds is None:
            return None
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        d = asdict(self)
        d["resolution"] = self.resolution
        d["resolution_label"] = self.resolution_label
        d["duration_formatted"] = self.duration_formatted
        if d["extracted_at"]:
            d["extracted_at"] = d["extracted_at"].isoformat()
        return d


class FFprobeExtractor:
    """FFprobe 기반 메타데이터 추출기"""

    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Args:
            ffprobe_path: FFprobe 실행 파일 경로
        """
        self.ffprobe_path = ffprobe_path
        self._verify_ffprobe()

    def _verify_ffprobe(self) -> None:
        """FFprobe 설치 확인"""
        try:
            result = subprocess.run(
                [self.ffprobe_path, "-version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError("FFprobe not working properly")
            logger.debug(f"FFprobe verified: {result.stdout.split(chr(10))[0]}")
        except FileNotFoundError:
            raise RuntimeError(f"FFprobe not found at: {self.ffprobe_path}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFprobe verification timed out")

    def extract(self, file_path: str, timeout: int = 60) -> MediaInfo:
        """로컬 파일에서 메타데이터 추출

        Args:
            file_path: 파일 경로
            timeout: 타임아웃 (초)

        Returns:
            MediaInfo 객체
        """
        info = MediaInfo(file_path=file_path)

        try:
            # FFprobe 실행
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                file_path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                info.extraction_status = "failed"
                info.extraction_error = result.stderr or "FFprobe returned non-zero exit code"
                return info

            # JSON 파싱
            data = json.loads(result.stdout)
            self._parse_ffprobe_output(info, data)

            info.extraction_status = "success"
            info.extracted_at = datetime.now()

        except subprocess.TimeoutExpired:
            info.extraction_status = "failed"
            info.extraction_error = f"Timeout after {timeout} seconds"
        except json.JSONDecodeError as e:
            info.extraction_status = "failed"
            info.extraction_error = f"JSON parse error: {e}"
        except Exception as e:
            info.extraction_status = "failed"
            info.extraction_error = str(e)
            logger.warning(f"Extraction failed for {file_path}: {e}")

        return info

    def _parse_ffprobe_output(self, info: MediaInfo, data: dict) -> None:
        """FFprobe 출력 파싱"""
        # Format 정보
        fmt = data.get("format", {})
        info.container_format = fmt.get("format_name")
        info.format_long_name = fmt.get("format_long_name")
        info.file_size = int(fmt.get("size", 0)) if fmt.get("size") else None
        info.bitrate = int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None

        if fmt.get("duration"):
            info.duration_seconds = float(fmt["duration"])

        # 태그 정보
        tags = fmt.get("tags", {})
        info.title = tags.get("title")
        info.creation_time = tags.get("creation_time")

        # 스트림 정보
        streams = data.get("streams", [])

        for stream in streams:
            codec_type = stream.get("codec_type")

            if codec_type == "video":
                info.video_stream_count += 1
                if not info.has_video:  # 첫 번째 비디오 스트림만 사용
                    info.has_video = True
                    info.video_codec = stream.get("codec_name")
                    info.video_codec_long = stream.get("codec_long_name")
                    info.width = stream.get("width")
                    info.height = stream.get("height")

                    # 프레임레이트 파싱
                    fps = stream.get("r_frame_rate") or stream.get("avg_frame_rate")
                    if fps and "/" in fps:
                        num, den = fps.split("/")
                        if int(den) > 0:
                            info.framerate = round(int(num) / int(den), 3)

                    # 비디오 비트레이트
                    if stream.get("bit_rate"):
                        info.video_bitrate = int(stream["bit_rate"])

            elif codec_type == "audio":
                info.audio_stream_count += 1
                if not info.has_audio:  # 첫 번째 오디오 스트림만 사용
                    info.has_audio = True
                    info.audio_codec = stream.get("codec_name")
                    info.audio_codec_long = stream.get("codec_long_name")
                    info.audio_channels = stream.get("channels")
                    info.audio_sample_rate = (
                        int(stream.get("sample_rate", 0)) if stream.get("sample_rate") else None
                    )

                    # 오디오 비트레이트
                    if stream.get("bit_rate"):
                        info.audio_bitrate = int(stream["bit_rate"])

            elif codec_type == "subtitle":
                info.subtitle_stream_count += 1


class SMBMediaExtractor:
    """SMB 파일에서 메타데이터를 추출하는 클래스

    FFprobe가 직접 SMB 경로를 지원하지 않으므로,
    파일의 시작 부분만 임시로 다운로드하여 분석합니다.
    """

    # 메타데이터 추출에 필요한 최소 바이트 수
    # MP4 moov atom이 파일 앞에 있는 경우 약 512KB면 충분
    # 파일 끝에 있는 경우 전체 다운로드 필요
    HEADER_SIZE = 512 * 1024  # 512KB (속도 최적화)

    def __init__(
        self,
        connector: SMBConnector,
        ffprobe_path: str = "ffprobe",
        temp_dir: Optional[str] = None,
    ):
        """
        Args:
            connector: SMB 연결 관리자
            ffprobe_path: FFprobe 실행 파일 경로
            temp_dir: 임시 파일 저장 디렉토리
        """
        self.connector = connector
        self.ffprobe = FFprobeExtractor(ffprobe_path)
        self.temp_dir = temp_dir or tempfile.gettempdir()

    def extract(
        self,
        smb_path: str,
        file_id: Optional[int] = None,
        full_download: bool = False,
        _retry_count: int = 0,  # #36 - 재시도 카운터
    ) -> MediaInfo:
        """SMB 파일에서 메타데이터 추출

        Args:
            smb_path: SMB 파일 경로 (공유 내 상대 경로)
            file_id: 데이터베이스 파일 ID (옵션)
            full_download: 전체 파일 다운로드 여부

        Returns:
            MediaInfo 객체
        """
        info = MediaInfo(file_path=smb_path, file_id=file_id)

        try:
            # 연결 확인
            if not self.connector.is_connected:
                self.connector.connect()

            # 파일 정보 확인
            file_info = self.connector.get_file_info(smb_path)
            if not file_info:
                info.extraction_status = "failed"
                info.extraction_error = "File not found"
                return info

            info.file_size = file_info.size

            # 임시 파일로 다운로드
            temp_path = self._download_for_analysis(smb_path, file_info.size, full_download)

            try:
                # FFprobe로 분석
                result = self.ffprobe.extract(temp_path)

                # 결과 복사
                for attr in [
                    "video_codec",
                    "video_codec_long",
                    "width",
                    "height",
                    "framerate",
                    "video_bitrate",
                    "audio_codec",
                    "audio_codec_long",
                    "audio_channels",
                    "audio_sample_rate",
                    "audio_bitrate",
                    "duration_seconds",
                    "bitrate",
                    "container_format",
                    "format_long_name",
                    "has_video",
                    "has_audio",
                    "video_stream_count",
                    "audio_stream_count",
                    "subtitle_stream_count",
                    "title",
                    "creation_time",
                    "extraction_status",
                    "extraction_error",
                ]:
                    setattr(info, attr, getattr(result, attr))

                # 파일 크기는 원본 유지
                info.file_size = file_info.size
                info.extracted_at = datetime.now()

                # 부분 다운로드로 실패한 경우 전체 다운로드 시도 (#36 - 재시도 1회 제한)
                if info.extraction_status == "failed" and not full_download and _retry_count == 0:
                    logger.info(f"Retrying with full download: {smb_path}")
                    return self.extract(smb_path, file_id, full_download=True, _retry_count=1)

            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            info.extraction_status = "failed"
            info.extraction_error = str(e)
            logger.warning(f"SMB extraction failed for {smb_path}: {e}")

        return info

    def _download_for_analysis(self, smb_path: str, file_size: int, full_download: bool) -> str:
        """분석을 위한 임시 다운로드

        Args:
            smb_path: SMB 파일 경로
            file_size: 파일 크기
            full_download: 전체 다운로드 여부

        Returns:
            임시 파일 경로
        """
        # 파일 확장자 추출
        ext = Path(smb_path).suffix or ".tmp"

        # 임시 파일 생성
        fd, temp_path = tempfile.mkstemp(suffix=ext, dir=self.temp_dir)
        os.close(fd)

        try:
            # 다운로드할 크기 결정
            if full_download or file_size <= self.HEADER_SIZE:
                download_size = file_size
            else:
                download_size = self.HEADER_SIZE

            logger.debug(f"Downloading {download_size:,} bytes of {smb_path}")

            # SMB에서 읽기
            with self.connector.open_file(smb_path, mode="rb") as smb_file:
                data = smb_file.read(download_size)

            # 임시 파일에 저장
            with open(temp_path, "wb") as f:
                f.write(data)

            return temp_path

        except Exception:
            # 실패 시 임시 파일 삭제
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


@dataclass
class ExtractionProgress:
    """추출 진행 상황"""

    total_files: int
    processed_files: int
    successful: int
    failed: int
    current_file: str
    files_per_second: float
    estimated_remaining: float

    @property
    def percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    def __str__(self) -> str:
        return (
            f"[{self.percentage:.1f}%] "
            f"{self.processed_files}/{self.total_files} | "
            f"OK: {self.successful}, Fail: {self.failed} | "
            f"{self.files_per_second:.1f} f/s"
        )


class MediaMetadataExtractor:
    """미디어 메타데이터 일괄 추출기

    아카이브의 모든 비디오 파일에서 메타데이터를 추출합니다.
    """

    def __init__(
        self,
        connector: SMBConnector,
        database,  # Database 타입 (순환 임포트 방지)
        ffprobe_path: str = "ffprobe",
        batch_size: int = 10,
    ):
        """
        Args:
            connector: SMB 연결 관리자
            database: 데이터베이스 관리자
            ffprobe_path: FFprobe 경로
            batch_size: 배치 저장 크기
        """
        self.connector = connector
        self.database = database
        self.smb_extractor = SMBMediaExtractor(connector, ffprobe_path)
        self.batch_size = batch_size

        self._progress_callback: Optional[Callable[[ExtractionProgress], None]] = None
        self._start_time: Optional[datetime] = None
        self._processed = 0
        self._successful = 0
        self._failed = 0

    def set_progress_callback(self, callback: Callable[[ExtractionProgress], None]) -> None:
        """진행률 콜백 설정"""
        self._progress_callback = callback

    def extract_all(
        self,
        file_type: str = "video",
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        """모든 비디오 파일에서 메타데이터 추출

        Args:
            file_type: 추출할 파일 유형 (기본: video)
            skip_existing: 이미 추출된 파일 건너뛰기

        Returns:
            추출 결과 요약
        """
        self._start_time = datetime.now()
        self._processed = 0
        self._successful = 0
        self._failed = 0

        # 비디오 파일 목록 조회
        files = self.database.get_files_by_type(file_type, limit=100000)
        total_files = len(files)

        logger.info(f"Starting metadata extraction for {total_files} {file_type} files")

        # #24 N+1 최적화: 이미 추출된 file_id들을 한 번에 조회
        existing_ids: set = set()
        if skip_existing:
            file_ids = [f.id for f in files if f.id is not None]
            existing_ids = self.database.get_existing_media_file_ids(file_ids)
            logger.info(f"Already extracted: {len(existing_ids)} files (skipping)")

        results: List[MediaInfo] = []

        for file_record in files:
            # 이미 추출된 파일 건너뛰기 (#24 - 배치 쿼리 사용)
            if skip_existing and file_record.id in existing_ids:
                self._processed += 1
                self._successful += 1
                continue

            try:
                # 메타데이터 추출
                info = self.smb_extractor.extract(file_record.path, file_id=file_record.id)

                # 데이터베이스 저장
                self.database.insert_media_info(info)

                if info.extraction_status == "success":
                    self._successful += 1
                else:
                    self._failed += 1

                results.append(info)

            except Exception as e:
                logger.error(f"Error processing {file_record.path}: {e}")
                self._failed += 1

            self._processed += 1

            # 진행률 알림
            if self._progress_callback:
                self._notify_progress(total_files, file_record.path)

        # 결과 요약
        duration = (datetime.now() - self._start_time).total_seconds()

        return {
            "total_files": total_files,
            "processed": self._processed,
            "successful": self._successful,
            "failed": self._failed,
            "duration_seconds": duration,
            "files_per_second": self._processed / duration if duration > 0 else 0,
        }

    def _notify_progress(self, total: int, current_path: str) -> None:
        """진행률 알림"""
        if not self._progress_callback or not self._start_time:
            return

        elapsed = (datetime.now() - self._start_time).total_seconds()
        fps = self._processed / elapsed if elapsed > 0 else 0
        remaining = (total - self._processed) / fps if fps > 0 else 0

        progress = ExtractionProgress(
            total_files=total,
            processed_files=self._processed,
            successful=self._successful,
            failed=self._failed,
            current_file=current_path,
            files_per_second=fps,
            estimated_remaining=remaining,
        )
        self._progress_callback(progress)


def extract_media_info(file_path: str, ffprobe_path: str = "ffprobe") -> MediaInfo:
    """단일 파일에서 메타데이터 추출 (편의 함수)

    Args:
        file_path: 로컬 파일 경로
        ffprobe_path: FFprobe 경로

    Returns:
        MediaInfo 객체
    """
    extractor = FFprobeExtractor(ffprobe_path)
    return extractor.extract(file_path)
