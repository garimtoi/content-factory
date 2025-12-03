"""SQLite 데이터베이스 모듈

스캔 결과 저장 및 조회를 위한 데이터베이스 관리
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MediaInfoRecord:
    """미디어 정보 레코드"""

    id: Optional[int] = None
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

    # 스트림 카운트
    has_video: bool = False
    has_audio: bool = False
    video_stream_count: int = 0
    audio_stream_count: int = 0
    subtitle_stream_count: int = 0

    # 메타데이터
    title: Optional[str] = None
    creation_time: Optional[str] = None

    # 상태
    extraction_status: str = "pending"
    extraction_error: Optional[str] = None
    created_at: Optional[datetime] = None

    @property
    def resolution(self) -> Optional[str]:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None

    @property
    def resolution_label(self) -> Optional[str]:
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


@dataclass
class FileRecord:
    """파일 레코드 데이터 클래스"""

    id: Optional[int] = None
    path: str = ""
    filename: str = ""
    extension: str = ""
    size_bytes: int = 0
    modified_at: Optional[datetime] = None
    file_type: str = ""
    parent_folder: str = ""
    scan_status: str = "pending"
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        d = asdict(self)
        if d["modified_at"]:
            d["modified_at"] = d["modified_at"].isoformat()
        if d["created_at"]:
            d["created_at"] = d["created_at"].isoformat()
        return d

    @classmethod
    def from_row(cls, row: tuple, columns: list[str]) -> "FileRecord":
        """데이터베이스 행에서 생성"""
        data = dict(zip(columns, row))

        # datetime 변환
        if data.get("modified_at"):
            data["modified_at"] = datetime.fromisoformat(data["modified_at"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])

        return cls(**data)


@dataclass
class ScanCheckpoint:
    """스캔 체크포인트"""

    id: Optional[int] = None
    scan_id: str = ""
    last_path: str = ""
    total_files: int = 0
    processed_files: int = 0
    status: str = "in_progress"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Database:
    """SQLite 데이터베이스 관리자 (#17 - 멀티스레드 안전성 개선)"""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str = "archive.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._local = threading.local()  # #17 - 스레드 로컬 저장소
        self._ensure_schema()

    @property
    def _connection(self) -> Optional[sqlite3.Connection]:
        """스레드별 연결 반환"""
        return getattr(self._local, "conn", None)

    @_connection.setter
    def _connection(self, value: Optional[sqlite3.Connection]) -> None:
        """스레드별 연결 설정"""
        self._local.conn = value

    def _get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 반환 (스레드 안전)"""
        if self._connection is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._connection

    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저 (#34 - 연결 복구 로직 추가)"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except sqlite3.DatabaseError as e:
            conn.rollback()
            logger.error(f"Database error during transaction: {e}")
            # 연결 오류 시 재연결 유도
            self.close()
            self._connection = None
            raise
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

    def _ensure_schema(self) -> None:
        """데이터베이스 스키마 생성"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 파일 테이블
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER DEFAULT 0,
                modified_at DATETIME,
                file_type TEXT,
                parent_folder TEXT,
                scan_status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(scan_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent_folder)")

        # 스캔 체크포인트 테이블
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT UNIQUE NOT NULL,
                last_path TEXT,
                total_files INTEGER DEFAULT 0,
                processed_files INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 스캔 통계 테이블
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 미디어 정보 테이블 (Issue #8)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS media_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER REFERENCES files(id),
                file_path TEXT,
                video_codec TEXT,
                video_codec_long TEXT,
                width INTEGER,
                height INTEGER,
                framerate REAL,
                video_bitrate INTEGER,
                audio_codec TEXT,
                audio_codec_long TEXT,
                audio_channels INTEGER,
                audio_sample_rate INTEGER,
                audio_bitrate INTEGER,
                duration_seconds REAL,
                bitrate INTEGER,
                container_format TEXT,
                format_long_name TEXT,
                file_size INTEGER,
                has_video INTEGER DEFAULT 0,
                has_audio INTEGER DEFAULT 0,
                video_stream_count INTEGER DEFAULT 0,
                audio_stream_count INTEGER DEFAULT 0,
                subtitle_stream_count INTEGER DEFAULT 0,
                title TEXT,
                creation_time TEXT,
                extraction_status TEXT DEFAULT 'pending',
                extraction_error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_id)
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_file_id ON media_info(file_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_status ON media_info(extraction_status)"
        )

        # 클립 메타데이터 테이블 (iconik CSV 임포트용)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clip_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iconik_id TEXT UNIQUE,
                title TEXT,
                description TEXT,
                time_start_ms INTEGER,
                time_end_ms INTEGER,
                project_name TEXT,
                year INTEGER,
                location TEXT,
                venue TEXT,
                episode_event TEXT,
                source TEXT,
                game_type TEXT,
                players_tags TEXT,
                hand_grade TEXT,
                hand_tag TEXT,
                epic_hand TEXT,
                tournament TEXT,
                poker_play_tags TEXT,
                adjective TEXT,
                emotion TEXT,
                is_badbeat INTEGER DEFAULT 0,
                is_bluff INTEGER DEFAULT 0,
                is_suckout INTEGER DEFAULT 0,
                is_cooler INTEGER DEFAULT 0,
                runout_tag TEXT,
                postflop TEXT,
                allin_tag TEXT,
                file_id INTEGER REFERENCES files(id),
                matched_file_path TEXT,
                match_confidence REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_iconik_id ON clip_metadata(iconik_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_file_id ON clip_metadata(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_project ON clip_metadata(project_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_event ON clip_metadata(episode_event)")

        # 미디어 파일 테이블 (media_metadata.csv Path 기반 매칭용)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY,
                filename TEXT,
                path TEXT UNIQUE,
                folder TEXT,
                container TEXT,
                size_bytes INTEGER,
                duration_sec REAL,
                -- Path 파싱 결과
                category TEXT,
                sub_category TEXT,
                location TEXT,
                year_folder TEXT,
                archive_path TEXT,
                normalized_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_files_category ON media_files(category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_files_sub_cat ON media_files(sub_category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_files_location ON media_files(location)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_files_normalized ON media_files(normalized_name)"
        )

        conn.commit()
        logger.info(f"Database schema ensured at {self.db_path}")

    def close(self) -> None:
        """데이터베이스 연결 종료"""
        if self._connection:
            self._connection.close()
            self._connection = None

    # === 파일 CRUD ===

    def insert_file(self, record: FileRecord) -> int:
        """파일 레코드 삽입

        Args:
            record: 파일 레코드

        Returns:
            삽입된 레코드 ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO files
            (path, filename, extension, size_bytes, modified_at, file_type, parent_folder, scan_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.path,
                record.filename,
                record.extension,
                record.size_bytes,
                record.modified_at.isoformat() if record.modified_at else None,
                record.file_type,
                record.parent_folder,
                record.scan_status,
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def insert_files_batch(self, records: List[FileRecord]) -> int:
        """파일 레코드 일괄 삽입

        Args:
            records: 파일 레코드 목록

        Returns:
            삽입된 레코드 수
        """
        if not records:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        data = [
            (
                r.path,
                r.filename,
                r.extension,
                r.size_bytes,
                r.modified_at.isoformat() if r.modified_at else None,
                r.file_type,
                r.parent_folder,
                r.scan_status,
            )
            for r in records
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO files
            (path, filename, extension, size_bytes, modified_at, file_type, parent_folder, scan_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        conn.commit()
        return len(records)

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
        """경로로 파일 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM files WHERE path = ?", (path,))
        row = cursor.fetchone()

        if row:
            columns = [col[0] for col in cursor.description]
            return FileRecord.from_row(tuple(row), columns)
        return None

    def get_files_by_type(self, file_type: str, limit: int = 1000) -> List[FileRecord]:
        """파일 유형으로 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM files WHERE file_type = ? LIMIT ?", (file_type, limit))

        columns = [col[0] for col in cursor.description]
        return [FileRecord.from_row(tuple(row), columns) for row in cursor.fetchall()]

    def get_all_files(self, limit: int = 10000) -> Iterator[FileRecord]:
        """모든 파일 조회 (제너레이터)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM files LIMIT ?", (limit,))
        columns = [col[0] for col in cursor.description]

        for row in cursor:
            yield FileRecord.from_row(tuple(row), columns)

    def update_file_status(self, path: str, status: str) -> bool:
        """파일 상태 업데이트"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE files SET scan_status = ? WHERE path = ?", (status, path))
        conn.commit()
        return cursor.rowcount > 0

    def delete_file(self, path: str) -> bool:
        """파일 레코드 삭제"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM files WHERE path = ?", (path,))
        conn.commit()
        return cursor.rowcount > 0

    def file_exists(self, path: str) -> bool:
        """파일 존재 여부 확인"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (path,))
        return cursor.fetchone() is not None

    # === 통계 ===

    def get_file_count(self, file_type: Optional[str] = None) -> int:
        """파일 수 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if file_type:
            cursor.execute("SELECT COUNT(*) FROM files WHERE file_type = ?", (file_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM files")

        return cursor.fetchone()[0]

    def get_total_size(self, file_type: Optional[str] = None) -> int:
        """총 파일 크기 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if file_type:
            cursor.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) FROM files WHERE file_type = ?", (file_type,)
            )
        else:
            cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM files")

        return cursor.fetchone()[0]

    def get_statistics(self) -> dict:
        """전체 통계 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                file_type,
                COUNT(*) as count,
                COALESCE(SUM(size_bytes), 0) as total_size
            FROM files
            GROUP BY file_type
        """
        )

        stats = {"total_files": 0, "total_size": 0, "by_type": {}}

        for row in cursor.fetchall():
            file_type = row["file_type"] or "unknown"
            count = row["count"]
            size = row["total_size"]

            stats["by_type"][file_type] = {"count": count, "size": size}
            stats["total_files"] += count
            stats["total_size"] += size

        return stats

    # === 체크포인트 ===

    def save_checkpoint(self, checkpoint: ScanCheckpoint) -> int:
        """체크포인트 저장"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO scan_checkpoints
            (scan_id, last_path, total_files, processed_files, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                checkpoint.scan_id,
                checkpoint.last_path,
                checkpoint.total_files,
                checkpoint.processed_files,
                checkpoint.status,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def get_checkpoint(self, scan_id: str) -> Optional[ScanCheckpoint]:
        """체크포인트 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM scan_checkpoints WHERE scan_id = ?", (scan_id,))
        row = cursor.fetchone()

        if row:
            return ScanCheckpoint(
                id=row["id"],
                scan_id=row["scan_id"],
                last_path=row["last_path"],
                total_files=row["total_files"],
                processed_files=row["processed_files"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            )
        return None

    def update_checkpoint_progress(
        self, scan_id: str, last_path: str, processed_files: int
    ) -> None:
        """체크포인트 진행 상황 업데이트"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE scan_checkpoints
            SET last_path = ?, processed_files = ?, updated_at = ?
            WHERE scan_id = ?
        """,
            (
                last_path,
                processed_files,
                datetime.now().isoformat(),
                scan_id,
            ),
        )

        conn.commit()

    def complete_checkpoint(self, scan_id: str) -> None:
        """체크포인트 완료 처리"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE scan_checkpoints
            SET status = 'completed', updated_at = ?
            WHERE scan_id = ?
        """,
            (datetime.now().isoformat(), scan_id),
        )

        conn.commit()

    def clear_all(self) -> None:
        """모든 데이터 삭제 (테스트용)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM files")
        cursor.execute("DELETE FROM scan_checkpoints")
        cursor.execute("DELETE FROM scan_stats")
        cursor.execute("DELETE FROM media_info")

        conn.commit()
        logger.warning("All data cleared from database")

    # === 미디어 정보 (Issue #8) ===

    def insert_media_info(self, info) -> int:
        """미디어 정보 삽입

        Args:
            info: MediaInfo 또는 MediaInfoRecord 객체

        Returns:
            삽입된 레코드 ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO media_info (
                file_id, file_path, video_codec, video_codec_long,
                width, height, framerate, video_bitrate,
                audio_codec, audio_codec_long, audio_channels,
                audio_sample_rate, audio_bitrate, duration_seconds,
                bitrate, container_format, format_long_name, file_size,
                has_video, has_audio, video_stream_count, audio_stream_count,
                subtitle_stream_count, title, creation_time,
                extraction_status, extraction_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                info.file_id,
                info.file_path,
                info.video_codec,
                getattr(info, "video_codec_long", None),
                info.width,
                info.height,
                info.framerate,
                getattr(info, "video_bitrate", None),
                info.audio_codec,
                getattr(info, "audio_codec_long", None),
                info.audio_channels,
                info.audio_sample_rate,
                getattr(info, "audio_bitrate", None),
                info.duration_seconds,
                info.bitrate,
                info.container_format,
                getattr(info, "format_long_name", None),
                getattr(info, "file_size", None),
                1 if info.has_video else 0,
                1 if info.has_audio else 0,
                info.video_stream_count,
                info.audio_stream_count,
                info.subtitle_stream_count,
                getattr(info, "title", None),
                getattr(info, "creation_time", None),
                info.extraction_status,
                getattr(info, "extraction_error", None),
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def get_media_info_by_file_id(self, file_id: int) -> Optional[MediaInfoRecord]:
        """파일 ID로 미디어 정보 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM media_info WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()

        if row:
            return MediaInfoRecord(
                id=row["id"],
                file_id=row["file_id"],
                file_path=row["file_path"],
                video_codec=row["video_codec"],
                video_codec_long=row["video_codec_long"],
                width=row["width"],
                height=row["height"],
                framerate=row["framerate"],
                video_bitrate=row["video_bitrate"],
                audio_codec=row["audio_codec"],
                audio_codec_long=row["audio_codec_long"],
                audio_channels=row["audio_channels"],
                audio_sample_rate=row["audio_sample_rate"],
                audio_bitrate=row["audio_bitrate"],
                duration_seconds=row["duration_seconds"],
                bitrate=row["bitrate"],
                container_format=row["container_format"],
                format_long_name=row["format_long_name"],
                file_size=row["file_size"],
                has_video=bool(row["has_video"]),
                has_audio=bool(row["has_audio"]),
                video_stream_count=row["video_stream_count"],
                audio_stream_count=row["audio_stream_count"],
                subtitle_stream_count=row["subtitle_stream_count"],
                title=row["title"],
                creation_time=row["creation_time"],
                extraction_status=row["extraction_status"],
                extraction_error=row["extraction_error"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            )
        return None

    def has_media_info(self, file_id: int) -> bool:
        """미디어 정보 존재 여부 확인"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM media_info WHERE file_id = ? AND extraction_status = 'success' LIMIT 1",
            (file_id,),
        )
        return cursor.fetchone() is not None

    def get_media_info_count(self, status: Optional[str] = None) -> int:
        """미디어 정보 수 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT COUNT(*) FROM media_info WHERE extraction_status = ?", (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM media_info")

        return cursor.fetchone()[0]

    def get_media_statistics(self) -> dict:
        """미디어 통계 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "by_resolution": {},
            "by_codec": {},
            "total_duration_seconds": 0,
        }

        # 추출 상태별 카운트
        cursor.execute(
            """
            SELECT extraction_status, COUNT(*) as count
            FROM media_info
            GROUP BY extraction_status
        """
        )
        for row in cursor.fetchall():
            if row["extraction_status"] == "success":
                stats["successful"] = row["count"]
            elif row["extraction_status"] == "failed":
                stats["failed"] = row["count"]
            stats["total"] += row["count"]

        # 해상도별 분포
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN height >= 2160 THEN '4K'
                    WHEN height >= 1440 THEN '1440p'
                    WHEN height >= 1080 THEN '1080p'
                    WHEN height >= 720 THEN '720p'
                    WHEN height >= 480 THEN '480p'
                    ELSE 'Other'
                END as resolution,
                COUNT(*) as count
            FROM media_info
            WHERE extraction_status = 'success' AND height IS NOT NULL
            GROUP BY resolution
        """
        )
        for row in cursor.fetchall():
            stats["by_resolution"][row["resolution"]] = row["count"]

        # 코덱별 분포
        cursor.execute(
            """
            SELECT video_codec, COUNT(*) as count
            FROM media_info
            WHERE extraction_status = 'success' AND video_codec IS NOT NULL
            GROUP BY video_codec
        """
        )
        for row in cursor.fetchall():
            stats["by_codec"][row["video_codec"]] = row["count"]

        # 총 재생 시간
        cursor.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) as total
            FROM media_info
            WHERE extraction_status = 'success'
        """
        )
        stats["total_duration_seconds"] = cursor.fetchone()["total"]

        return stats

    # === 클립 메타데이터 (iconik CSV) ===

    def insert_clip_metadata(self, clip: dict) -> int:
        """클립 메타데이터 삽입

        Args:
            clip: 클립 메타데이터 딕셔너리

        Returns:
            삽입된 레코드 ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO clip_metadata (
                iconik_id, title, description, time_start_ms, time_end_ms,
                project_name, year, location, venue, episode_event, source,
                game_type, players_tags, hand_grade, hand_tag, epic_hand,
                tournament, poker_play_tags, adjective, emotion,
                is_badbeat, is_bluff, is_suckout, is_cooler,
                runout_tag, postflop, allin_tag,
                file_id, matched_file_path, match_confidence, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                clip.get("iconik_id"),
                clip.get("title"),
                clip.get("description"),
                clip.get("time_start_ms"),
                clip.get("time_end_ms"),
                clip.get("project_name"),
                clip.get("year"),
                clip.get("location"),
                clip.get("venue"),
                clip.get("episode_event"),
                clip.get("source"),
                clip.get("game_type"),
                clip.get("players_tags"),
                clip.get("hand_grade"),
                clip.get("hand_tag"),
                clip.get("epic_hand"),
                clip.get("tournament"),
                clip.get("poker_play_tags"),
                clip.get("adjective"),
                clip.get("emotion"),
                1 if clip.get("is_badbeat") else 0,
                1 if clip.get("is_bluff") else 0,
                1 if clip.get("is_suckout") else 0,
                1 if clip.get("is_cooler") else 0,
                clip.get("runout_tag"),
                clip.get("postflop"),
                clip.get("allin_tag"),
                clip.get("file_id"),
                clip.get("matched_file_path"),
                clip.get("match_confidence"),
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def insert_clip_metadata_batch(self, clips: List[dict]) -> int:
        """클립 메타데이터 일괄 삽입

        Args:
            clips: 클립 메타데이터 딕셔너리 목록

        Returns:
            삽입된 레코드 수
        """
        if not clips:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        data = [
            (
                c.get("iconik_id"),
                c.get("title"),
                c.get("description"),
                c.get("time_start_ms"),
                c.get("time_end_ms"),
                c.get("project_name"),
                c.get("year"),
                c.get("location"),
                c.get("venue"),
                c.get("episode_event"),
                c.get("source"),
                c.get("game_type"),
                c.get("players_tags"),
                c.get("hand_grade"),
                c.get("hand_tag"),
                c.get("epic_hand"),
                c.get("tournament"),
                c.get("poker_play_tags"),
                c.get("adjective"),
                c.get("emotion"),
                1 if c.get("is_badbeat") else 0,
                1 if c.get("is_bluff") else 0,
                1 if c.get("is_suckout") else 0,
                1 if c.get("is_cooler") else 0,
                c.get("runout_tag"),
                c.get("postflop"),
                c.get("allin_tag"),
                c.get("file_id"),
                c.get("matched_file_path"),
                c.get("match_confidence"),
                datetime.now().isoformat(),
            )
            for c in clips
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO clip_metadata (
                iconik_id, title, description, time_start_ms, time_end_ms,
                project_name, year, location, venue, episode_event, source,
                game_type, players_tags, hand_grade, hand_tag, epic_hand,
                tournament, poker_play_tags, adjective, emotion,
                is_badbeat, is_bluff, is_suckout, is_cooler,
                runout_tag, postflop, allin_tag,
                file_id, matched_file_path, match_confidence, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        conn.commit()
        return len(clips)

    def get_clip_metadata_by_iconik_id(self, iconik_id: str) -> Optional[dict]:
        """iconik ID로 클립 메타데이터 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM clip_metadata WHERE iconik_id = ?", (iconik_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_clip_metadata_count(self) -> int:
        """클립 메타데이터 수 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM clip_metadata")
        return cursor.fetchone()[0]

    def get_clip_statistics(self) -> dict:
        """클립 메타데이터 통계 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {
            "total": 0,
            "matched": 0,
            "unmatched": 0,
            "by_project": {},
            "by_event": {},
            "by_hand_grade": {},
        }

        # 전체 수
        cursor.execute("SELECT COUNT(*) FROM clip_metadata")
        stats["total"] = cursor.fetchone()[0]

        # 매칭된 수
        cursor.execute("SELECT COUNT(*) FROM clip_metadata WHERE file_id IS NOT NULL")
        stats["matched"] = cursor.fetchone()[0]
        stats["unmatched"] = stats["total"] - stats["matched"]

        # 프로젝트별
        cursor.execute(
            """
            SELECT project_name, COUNT(*) as count
            FROM clip_metadata
            WHERE project_name IS NOT NULL AND project_name != ''
            GROUP BY project_name
            ORDER BY count DESC
        """
        )
        for row in cursor.fetchall():
            stats["by_project"][row["project_name"]] = row["count"]

        # 이벤트별
        cursor.execute(
            """
            SELECT episode_event, COUNT(*) as count
            FROM clip_metadata
            WHERE episode_event IS NOT NULL AND episode_event != ''
            GROUP BY episode_event
            ORDER BY count DESC
            LIMIT 20
        """
        )
        for row in cursor.fetchall():
            stats["by_event"][row["episode_event"]] = row["count"]

        # 핸드 등급별
        cursor.execute(
            """
            SELECT hand_grade, COUNT(*) as count
            FROM clip_metadata
            WHERE hand_grade IS NOT NULL AND hand_grade != ''
            GROUP BY hand_grade
            ORDER BY count DESC
        """
        )
        for row in cursor.fetchall():
            stats["by_hand_grade"][row["hand_grade"]] = row["count"]

        return stats

    def update_clip_file_match(
        self, iconik_id: str, file_id: int, file_path: str, confidence: float
    ) -> bool:
        """클립과 파일 매칭 정보 업데이트"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE clip_metadata
            SET file_id = ?, matched_file_path = ?, match_confidence = ?, updated_at = ?
            WHERE iconik_id = ?
        """,
            (file_id, file_path, confidence, datetime.now().isoformat(), iconik_id),
        )

        conn.commit()
        return cursor.rowcount > 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
