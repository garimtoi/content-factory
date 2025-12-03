"""Integration Test Fixtures

#22: 통합 테스트용 공통 픽스처
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from archive_analyzer.database import Database


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """임시 디렉토리 생성 (ignore_cleanup_errors로 Windows 호환)"""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    yield Path(tmpdir.name)
    # cleanup은 자동으로 수행됨 (ignore_cleanup_errors=True)


@pytest.fixture
def archive_db(temp_dir: Path) -> Generator[Path, None, None]:
    """테스트용 archive.db 생성 (Database 클래스 사용)"""
    db_path = temp_dir / "archive.db"
    # Database 클래스가 스키마를 자동 생성
    db = Database(str(db_path))
    db.close()
    yield db_path


@pytest.fixture
def pokervod_db(temp_dir: Path) -> Generator[Path, None, None]:
    """테스트용 pokervod.db 생성 (실제 스키마와 동일)"""
    db_path = temp_dir / "pokervod.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # files 테이블 (pokervod 스키마 - sync.py와 일치)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            nas_path TEXT,
            filename TEXT,
            size_bytes INTEGER,
            duration_sec REAL,
            resolution TEXT,
            codec TEXT,
            fps REAL,
            bitrate_kbps INTEGER,
            analysis_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # catalogs 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalog_id TEXT UNIQUE,
            name TEXT,
            description TEXT
        )
    """)

    conn.commit()
    conn.close()

    yield db_path


@pytest.fixture
def mock_smb_connector():
    """Mock SMB Connector"""
    with patch("archive_analyzer.smb_connector.SMBConnector") as mock:
        connector = MagicMock()
        connector.connect.return_value = True
        connector.is_connected = True
        mock.return_value = connector
        yield connector


@pytest.fixture
def sample_files_data():
    """샘플 파일 데이터"""
    return [
        {
            "path": "//10.10.100.122/docker/GGPNAs/ARCHIVE/WSOP/WSOP-BR/WSOP-EUROPE/2024/final_table.mp4",
            "filename": "final_table.mp4",
            "extension": ".mp4",
            "size": 5_000_000_000,
            "file_type": "video",
        },
        {
            "path": "//10.10.100.122/docker/GGPNAs/ARCHIVE/HCL/2024/episode_001.mp4",
            "filename": "episode_001.mp4",
            "extension": ".mp4",
            "size": 3_000_000_000,
            "file_type": "video",
        },
        {
            "path": "//10.10.100.122/docker/GGPNAs/ARCHIVE/PAD/Season12/cash_game.mxf",
            "filename": "cash_game.mxf",
            "extension": ".mxf",
            "size": 8_000_000_000,
            "file_type": "video",
        },
    ]


@pytest.fixture
def sample_media_info():
    """샘플 미디어 정보"""
    return [
        {
            "video_codec": "h264",
            "audio_codec": "aac",
            "width": 1920,
            "height": 1080,
            "duration_seconds": 7200.0,
            "bitrate": 8_000_000,
            "container": "mp4",
            "extraction_status": "success",
        },
        {
            "video_codec": "h264",
            "audio_codec": "aac",
            "width": 1920,
            "height": 1080,
            "duration_seconds": 3600.0,
            "bitrate": 6_000_000,
            "container": "mp4",
            "extraction_status": "success",
        },
        {
            "video_codec": "mpeg2video",
            "audio_codec": "pcm_s24le",
            "width": 1920,
            "height": 1080,
            "duration_seconds": 5400.0,
            "bitrate": 50_000_000,
            "container": "mxf",
            "extraction_status": "success",
        },
    ]
