"""설정 관리 모듈 - 인증 정보 및 연결 설정"""

import json
import logging
import os
from dataclasses import dataclass, field

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
