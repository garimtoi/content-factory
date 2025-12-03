"""설정 관리 모듈 - 인증 정보 및 연결 설정

#25: 통합 설정 클래스 구현
- AppConfig: 전체 애플리케이션 설정 통합
- 기존 개별 Config 클래스들은 호환성 유지
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# =============================================
# 통합 DB 경로 (환경변수 또는 기본값)
# =============================================
SHARED_DB_PATH = os.getenv("SHARED_DB_PATH", "D:/AI/claude01/qwen_hand_analysis/data/pokervod.db")


@dataclass
class SMBConfig:
    """SMB 연결 설정"""

    server: str
    share: str
    username: str
    password: str = field(repr=False, default="")  # #16 - repr에서 비밀번호 제외
    port: int = 445
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def share_path(self) -> str:
        """UNC 공유 경로 반환"""
        return f"\\\\{self.server}\\{self.share}"

    @property
    def connection_url(self) -> str:
        """smbprotocol 연결 URL (비밀번호 마스킹)"""
        return f"smb://{self.username}:***@{self.server}:{self.port}/{self.share}"

    def get_connection_url_with_password(self) -> str:
        """smbprotocol 연결 URL (비밀번호 포함 - 내부 연결용)"""
        return f"smb://{self.username}:{self.password}@{self.server}:{self.port}/{self.share}"

    def to_dict(self, mask_password: bool = True) -> dict:
        """설정을 딕셔너리로 변환 (#16 - asdict 호출 없이 직접 생성)"""
        d = {
            "server": self.server,
            "share": self.share,
            "username": self.username,
            "password": "***HIDDEN***" if mask_password else self.password,
            "port": self.port,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
        }
        return d


@dataclass
class AnalyzerConfig:
    """분석기 전체 설정"""

    smb: SMBConfig
    archive_path: str = ""
    database_path: str = SHARED_DB_PATH  # 통합 pokervod.db 사용
    log_level: str = "INFO"
    parallel_workers: int = 4
    batch_size: int = 100

    @classmethod
    def from_env(cls) -> "AnalyzerConfig":
        """환경 변수에서 설정 로드"""
        smb = SMBConfig(
            server=os.getenv("SMB_SERVER", "10.10.100.122"),
            share=os.getenv("SMB_SHARE", "docker"),
            username=os.getenv("SMB_USERNAME", ""),
            password=os.getenv("SMB_PASSWORD", ""),
            port=int(os.getenv("SMB_PORT", "445")),
            timeout=int(os.getenv("SMB_TIMEOUT", "30")),
            max_retries=int(os.getenv("SMB_MAX_RETRIES", "3")),
        )

        return cls(
            smb=smb,
            archive_path=os.getenv("ARCHIVE_PATH", "GGPNAs/ARCHIVE"),
            database_path=os.getenv("DATABASE_PATH", SHARED_DB_PATH),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            parallel_workers=int(os.getenv("PARALLEL_WORKERS", "4")),
        )

    @classmethod
    def from_file(cls, path: str) -> "AnalyzerConfig":
        """JSON 파일에서 설정 로드"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        smb_data = data.get("smb", {})
        smb = SMBConfig(**smb_data)

        return cls(
            smb=smb,
            archive_path=data.get("archive_path", "GGPNAs/ARCHIVE"),
            database_path=data.get("database_path", SHARED_DB_PATH),
            log_level=data.get("log_level", "INFO"),
            parallel_workers=data.get("parallel_workers", 4),
            batch_size=data.get("batch_size", 100),
        )

    def save_to_file(self, path: str, include_password: bool = False) -> None:
        """설정을 JSON 파일로 저장"""
        data = {
            "smb": {
                "server": self.smb.server,
                "share": self.smb.share,
                "username": self.smb.username,
                "password": self.smb.password if include_password else "",
                "port": self.smb.port,
                "timeout": self.smb.timeout,
                "max_retries": self.smb.max_retries,
                "retry_delay": self.smb.retry_delay,
            },
            "archive_path": self.archive_path,
            "database_path": self.database_path,
            "log_level": self.log_level,
            "parallel_workers": self.parallel_workers,
            "batch_size": self.batch_size,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Config saved to {path}")


def create_default_config() -> AnalyzerConfig:
    """기본 설정 생성 (GGP NAS용)"""
    smb = SMBConfig(
        server="10.10.100.122",
        share="docker",
        username="GGP",
        password="",  # 비밀번호는 환경변수 또는 직접 입력
        port=445,
        timeout=30,
        max_retries=3,
        retry_delay=1.0,
    )

    return AnalyzerConfig(
        smb=smb,
        archive_path="GGPNAs/ARCHIVE",
        database_path=SHARED_DB_PATH,
        log_level="INFO",
        parallel_workers=4,
        batch_size=100,
    )


# =============================================
# 통합 설정 클래스 (#25)
# =============================================


@dataclass
class SearchConfig:
    """MeiliSearch 검색 설정 (#25 - config.py로 통합)"""

    host: str = field(default_factory=lambda: os.getenv("MEILISEARCH_URL", "http://localhost:7700"))
    api_key: str = field(default_factory=lambda: os.getenv("MEILISEARCH_API_KEY", ""))
    files_index: str = "files"
    media_index: str = "media_info"
    clips_index: str = "clip_metadata"


@dataclass
class PokervodSyncConfig:
    """pokervod.db 동기화 설정 (#25 - config.py로 통합)"""

    archive_db: str = field(default_factory=lambda: os.getenv("ARCHIVE_DB_PATH", "data/output/archive.db"))
    pokervod_db: str = field(default_factory=lambda: os.getenv("POKERVOD_DB_PATH", SHARED_DB_PATH))
    nas_prefix: str = "//10.10.100.122/docker/GGPNAs/ARCHIVE"
    local_prefix: str = "Z:/GGPNAs/ARCHIVE"
    default_analysis_status: str = "pending"


@dataclass
class SheetsSyncConfig:
    """Google Sheets 동기화 설정 (#25 - config.py로 통합)"""

    credentials_path: Optional[str] = field(
        default_factory=lambda: os.getenv(
            "CREDENTIALS_PATH",
            "D:/AI/claude01/archive-analyzer/config/gcp-service-account.json"
        )
    )
    spreadsheet_id: Optional[str] = field(
        default_factory=lambda: os.getenv(
            "SPREADSHEET_ID",
            "1TW2ON5CQyIrL8aGQNYJ4OWkbZMaGmY9DoDG9VFXU60I"
        )
    )
    db_path: Optional[str] = field(
        default_factory=lambda: os.getenv("DB_PATH", SHARED_DB_PATH)
    )
    sync_interval_seconds: int = 300  # 5분
    tables_to_sync: List[str] = field(
        default_factory=lambda: os.getenv("TABLES_TO_SYNC", "files,hands").split(",")
    )


@dataclass
class AppConfig:
    """통합 애플리케이션 설정 (#25)

    모든 서비스 설정을 하나의 클래스로 통합합니다.

    Usage:
        # 환경변수에서 로드
        config = AppConfig.from_env()

        # JSON 파일에서 로드
        config = AppConfig.from_file("config.json")

        # 개별 설정 접근
        smb_config = config.smb
        search_config = config.search
    """

    # SMB 설정
    smb: SMBConfig = field(default_factory=lambda: SMBConfig(
        server=os.getenv("SMB_SERVER", "10.10.100.122"),
        share=os.getenv("SMB_SHARE", "docker"),
        username=os.getenv("SMB_USERNAME", ""),
        password=os.getenv("SMB_PASSWORD", ""),
    ))

    # 분석기 설정
    archive_path: str = field(default_factory=lambda: os.getenv("ARCHIVE_PATH", "GGPNAs/ARCHIVE"))
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", SHARED_DB_PATH))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    parallel_workers: int = field(default_factory=lambda: int(os.getenv("PARALLEL_WORKERS", "4")))
    batch_size: int = field(default_factory=lambda: int(os.getenv("BATCH_SIZE", "100")))

    # 검색 설정
    search: SearchConfig = field(default_factory=SearchConfig)

    # pokervod.db 동기화 설정
    pokervod_sync: PokervodSyncConfig = field(default_factory=PokervodSyncConfig)

    # Google Sheets 동기화 설정
    sheets_sync: SheetsSyncConfig = field(default_factory=SheetsSyncConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """환경변수에서 전체 설정 로드"""
        return cls()

    @classmethod
    def from_file(cls, path: str) -> "AppConfig":
        """JSON 파일에서 설정 로드"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        smb_data = data.get("smb", {})
        smb = SMBConfig(
            server=smb_data.get("server", os.getenv("SMB_SERVER", "10.10.100.122")),
            share=smb_data.get("share", os.getenv("SMB_SHARE", "docker")),
            username=smb_data.get("username", os.getenv("SMB_USERNAME", "")),
            password=smb_data.get("password", os.getenv("SMB_PASSWORD", "")),
            port=smb_data.get("port", 445),
            timeout=smb_data.get("timeout", 30),
            max_retries=smb_data.get("max_retries", 3),
            retry_delay=smb_data.get("retry_delay", 1.0),
        )

        search_data = data.get("search", {})
        search = SearchConfig(
            host=search_data.get("host", os.getenv("MEILISEARCH_URL", "http://localhost:7700")),
            api_key=search_data.get("api_key", os.getenv("MEILISEARCH_API_KEY", "")),
            files_index=search_data.get("files_index", "files"),
            media_index=search_data.get("media_index", "media_info"),
            clips_index=search_data.get("clips_index", "clip_metadata"),
        )

        pokervod_data = data.get("pokervod_sync", {})
        pokervod_sync = PokervodSyncConfig(
            archive_db=pokervod_data.get("archive_db", "data/output/archive.db"),
            pokervod_db=pokervod_data.get("pokervod_db", SHARED_DB_PATH),
            nas_prefix=pokervod_data.get("nas_prefix", "//10.10.100.122/docker/GGPNAs/ARCHIVE"),
            local_prefix=pokervod_data.get("local_prefix", "Z:/GGPNAs/ARCHIVE"),
        )

        sheets_data = data.get("sheets_sync", {})
        sheets_sync = SheetsSyncConfig(
            credentials_path=sheets_data.get("credentials_path"),
            spreadsheet_id=sheets_data.get("spreadsheet_id"),
            db_path=sheets_data.get("db_path"),
            sync_interval_seconds=sheets_data.get("sync_interval_seconds", 300),
            tables_to_sync=sheets_data.get("tables_to_sync", ["files", "hands"]),
        )

        return cls(
            smb=smb,
            archive_path=data.get("archive_path", "GGPNAs/ARCHIVE"),
            database_path=data.get("database_path", SHARED_DB_PATH),
            log_level=data.get("log_level", "INFO"),
            parallel_workers=data.get("parallel_workers", 4),
            batch_size=data.get("batch_size", 100),
            search=search,
            pokervod_sync=pokervod_sync,
            sheets_sync=sheets_sync,
        )

    def to_analyzer_config(self) -> AnalyzerConfig:
        """기존 AnalyzerConfig로 변환 (호환성 유지)"""
        return AnalyzerConfig(
            smb=self.smb,
            archive_path=self.archive_path,
            database_path=self.database_path,
            log_level=self.log_level,
            parallel_workers=self.parallel_workers,
            batch_size=self.batch_size,
        )

    def save_to_file(self, path: str, include_secrets: bool = False) -> None:
        """설정을 JSON 파일로 저장"""
        data = {
            "smb": self.smb.to_dict(mask_password=not include_secrets),
            "archive_path": self.archive_path,
            "database_path": self.database_path,
            "log_level": self.log_level,
            "parallel_workers": self.parallel_workers,
            "batch_size": self.batch_size,
            "search": {
                "host": self.search.host,
                "api_key": "" if not include_secrets else self.search.api_key,
                "files_index": self.search.files_index,
                "media_index": self.search.media_index,
                "clips_index": self.search.clips_index,
            },
            "pokervod_sync": {
                "archive_db": self.pokervod_sync.archive_db,
                "pokervod_db": self.pokervod_sync.pokervod_db,
                "nas_prefix": self.pokervod_sync.nas_prefix,
                "local_prefix": self.pokervod_sync.local_prefix,
            },
            "sheets_sync": {
                "credentials_path": self.sheets_sync.credentials_path,
                "spreadsheet_id": self.sheets_sync.spreadsheet_id,
                "db_path": self.sheets_sync.db_path,
                "sync_interval_seconds": self.sheets_sync.sync_interval_seconds,
                "tables_to_sync": self.sheets_sync.tables_to_sync,
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"AppConfig saved to {path}")
