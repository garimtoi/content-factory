"""Archive Analyzer - OTT 솔루션을 위한 미디어 아카이브 분석 도구"""

__version__ = "0.2.1"

from .config import (
    AnalyzerConfig,
    AppConfig,
    PokervodSyncConfig,
    SearchConfig,
    SheetsSyncConfig,
    SMBConfig,
)
from .database import Database, FileRecord, MediaInfoRecord
from .file_classifier import FileClassifier, FileType, classify_file
from .report_generator import ArchiveReport, ReportFormatter, ReportGenerator
from .smb_connector import FileInfo, SMBConnector

__all__ = [
    # 설정 (#25 - 통합)
    "SMBConfig",
    "AnalyzerConfig",
    "AppConfig",
    "SearchConfig",
    "PokervodSyncConfig",
    "SheetsSyncConfig",
    # 분류
    "FileType",
    "FileClassifier",
    "classify_file",
    # 데이터베이스
    "Database",
    "FileRecord",
    "MediaInfoRecord",
    # SMB
    "SMBConnector",
    "FileInfo",
    # 리포트
    "ReportGenerator",
    "ReportFormatter",
    "ArchiveReport",
]
