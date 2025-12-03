"""sheets_sync.py 테스트

#18: Google Sheets <-> SQLite 동기화 테스트
"""

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


class TestSyncConfig:
    """SyncConfig 테스트"""

    def test_default_values(self):
        """기본값 테스트"""
        from archive_analyzer.sheets_sync import SyncConfig

        config = SyncConfig(
            credentials_path="test/creds.json",
            spreadsheet_id="test_sheet_id",
            db_path="test.db",
        )
        assert config.credentials_path == "test/creds.json"
        assert config.spreadsheet_id == "test_sheet_id"
        assert config.db_path == "test.db"
        assert config.sync_interval_seconds == 300
        assert len(config.tables_to_sync) > 0

    def test_env_override(self):
        """환경변수 오버라이드 테스트"""
        with patch.dict(
            "os.environ",
            {
                "SYNC_INTERVAL": "600",
                "TABLES_TO_SYNC": "table1,table2,table3",
            },
        ):
            from archive_analyzer.sheets_sync import SyncConfig

            config = SyncConfig(
                credentials_path="test/creds.json",
                spreadsheet_id="test_sheet_id",
                db_path="test.db",
            )
            assert config.sync_interval_seconds == 600
            assert config.tables_to_sync == ["table1", "table2", "table3"]

    def test_tables_to_sync_default(self):
        """기본 동기화 테이블 목록 테스트"""
        with patch.dict("os.environ", {}, clear=True):
            from archive_analyzer.sheets_sync import SyncConfig

            config = SyncConfig(
                credentials_path="test/creds.json",
                spreadsheet_id="test_sheet_id",
                db_path="test.db",
            )
            expected_tables = [
                "catalogs",
                "subcatalogs",
                "players",
                "events",
                "tournaments",
                "hands",
                "files",
                "wsoptv_player_aliases",
            ]
            assert config.tables_to_sync == expected_tables


class TestDatabaseClient:
    """DatabaseClient 테스트"""

    @pytest.fixture
    def temp_db(self) -> Generator[Path, None, None]:
        """임시 SQLite DB 생성 (Windows 호환)"""
        # Windows에서 파일 잠금 문제 방지를 위해 tempfile.TemporaryDirectory 사용
        tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = Path(tmpdir.name) / "test.db"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 테스트 테이블 생성
        cursor.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 샘플 데이터 삽입
        cursor.executemany(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [(1, "item1", 100), (2, "item2", 200), (3, "item3", 300)],
        )

        conn.commit()
        conn.close()

        yield db_path
        # cleanup은 TemporaryDirectory가 자동 처리 (ignore_cleanup_errors=True)

    def test_get_connection(self, temp_db):
        """데이터베이스 연결 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        conn = client.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

    def test_get_table_schema(self, temp_db):
        """테이블 스키마 조회 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        schema = client.get_table_schema("test_table")

        assert len(schema) == 4
        column_names = [col["name"] for col in schema]
        assert "id" in column_names
        assert "name" in column_names
        assert "value" in column_names
        assert "created_at" in column_names

    def test_get_primary_key(self, temp_db):
        """Primary Key 조회 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        pk = client.get_primary_key("test_table")
        assert pk == "id"

    def test_get_all_records(self, temp_db):
        """전체 레코드 조회 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        headers, records = client.get_all_records("test_table")

        assert "id" in headers
        assert "name" in headers
        assert len(records) == 3
        assert records[0]["name"] == "item1"

    def test_get_table_hash(self, temp_db):
        """테이블 해시 계산 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        hash1 = client.get_table_hash("test_table")
        hash2 = client.get_table_hash("test_table")

        assert hash1 == hash2  # 동일 데이터는 동일 해시
        assert len(hash1) == 32  # MD5 해시 길이

    def test_upsert_record_insert(self, temp_db):
        """레코드 삽입 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        new_record = {"id": 4, "name": "item4", "value": 400}
        client.upsert_record("test_table", new_record, "id")

        _, records = client.get_all_records("test_table")
        assert len(records) == 4

    def test_upsert_record_update(self, temp_db):
        """레코드 업데이트 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        updated_record = {"id": 1, "name": "item1_updated", "value": 150}
        client.upsert_record("test_table", updated_record, "id")

        _, records = client.get_all_records("test_table")
        item1 = [r for r in records if r["id"] == 1][0]
        assert item1["name"] == "item1_updated"
        assert item1["value"] == 150

    def test_delete_record(self, temp_db):
        """레코드 삭제 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        client.delete_record("test_table", "id", 2)

        _, records = client.get_all_records("test_table")
        assert len(records) == 2
        ids = [r["id"] for r in records]
        assert 2 not in ids

    def test_bulk_upsert(self, temp_db):
        """벌크 Upsert 테스트"""
        from archive_analyzer.sheets_sync import DatabaseClient

        client = DatabaseClient(str(temp_db))
        new_records = [
            {"id": 4, "name": "item4", "value": 400},
            {"id": 5, "name": "item5", "value": 500},
            {"id": 1, "name": "item1_bulk", "value": 111},  # 기존 레코드 업데이트
        ]
        client.bulk_upsert("test_table", new_records, "id")

        _, records = client.get_all_records("test_table")
        assert len(records) == 5  # 3 기존 + 2 신규

        item1 = [r for r in records if r["id"] == 1][0]
        assert item1["name"] == "item1_bulk"


class TestSheetsClient:
    """SheetsClient 테스트 (Mocked)"""

    @pytest.fixture
    def mock_gspread(self):
        """gspread 모듈 모킹"""
        with patch("archive_analyzer.sheets_sync.gspread") as mock_gspread:
            with patch("archive_analyzer.sheets_sync.Credentials") as mock_creds:
                mock_creds.from_service_account_file.return_value = MagicMock()

                mock_client = MagicMock()
                mock_gspread.authorize.return_value = mock_client

                mock_spreadsheet = MagicMock()
                mock_client.open_by_key.return_value = mock_spreadsheet

                yield {
                    "gspread": mock_gspread,
                    "creds": mock_creds,
                    "client": mock_client,
                    "spreadsheet": mock_spreadsheet,
                }

    def test_client_initialization(self, mock_gspread):
        """클라이언트 초기화 테스트"""
        from archive_analyzer.sheets_sync import SheetsClient, SyncConfig

        config = SyncConfig(
            credentials_path="test/creds.json",
            spreadsheet_id="test_sheet_id",
            db_path="test.db",
        )
        client = SheetsClient(config)

        assert client.client is not None
        assert client.spreadsheet is not None
        mock_gspread["creds"].from_service_account_file.assert_called_once()
        mock_gspread["gspread"].authorize.assert_called_once()

    def test_get_or_create_worksheet_existing(self, mock_gspread):
        """기존 워크시트 조회 테스트"""
        from archive_analyzer.sheets_sync import SheetsClient, SyncConfig

        mock_worksheet = MagicMock()
        mock_gspread["spreadsheet"].worksheet.return_value = mock_worksheet

        config = SyncConfig(
            credentials_path="test/creds.json",
            spreadsheet_id="test_sheet_id",
            db_path="test.db",
        )
        client = SheetsClient(config)
        result = client.get_or_create_worksheet("test_sheet", ["col1", "col2"])

        assert result == mock_worksheet

    def test_get_all_records(self, mock_gspread):
        """전체 레코드 조회 테스트 (Mocked)"""
        from archive_analyzer.sheets_sync import SheetsClient, SyncConfig

        mock_worksheet = MagicMock()
        mock_worksheet.get_all_records.return_value = [
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"},
        ]
        mock_gspread["spreadsheet"].worksheet.return_value = mock_worksheet

        config = SyncConfig(
            credentials_path="test/creds.json",
            spreadsheet_id="test_sheet_id",
            db_path="test.db",
        )
        client = SheetsClient(config)
        records = client.get_all_records("test_sheet")

        assert len(records) == 2
        assert records[0]["id"] == 1


class TestSheetsSyncServiceInit:
    """SheetsSyncService 초기화 테스트"""

    @pytest.fixture
    def mock_clients(self):
        """클라이언트 모킹"""
        with patch("archive_analyzer.sheets_sync.SheetsClient") as mock_sheets:
            with patch("archive_analyzer.sheets_sync.DatabaseClient") as mock_db:
                mock_sheets_instance = MagicMock()
                mock_sheets.return_value = mock_sheets_instance

                mock_db_instance = MagicMock()
                mock_db.return_value = mock_db_instance

                yield {
                    "sheets_class": mock_sheets,
                    "db_class": mock_db,
                    "sheets": mock_sheets_instance,
                    "db": mock_db_instance,
                }

    def test_service_initialization(self, mock_clients):
        """서비스 초기화 테스트"""
        from archive_analyzer.sheets_sync import SheetsSyncService, SyncConfig

        config = SyncConfig(
            credentials_path="test/creds.json",
            spreadsheet_id="test_sheet_id",
            db_path="test.db",
        )
        service = SheetsSyncService(config)

        assert service.config == config
        mock_clients["sheets_class"].assert_called_once_with(config)
        mock_clients["db_class"].assert_called_once_with(config.db_path)


class TestHashComparison:
    """해시 비교 로직 테스트"""

    def test_hash_consistency(self):
        """해시 일관성 테스트"""
        data1 = [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}]
        data2 = [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}]

        hash1 = hashlib.md5(str(data1).encode()).hexdigest()
        hash2 = hashlib.md5(str(data2).encode()).hexdigest()

        assert hash1 == hash2

    def test_hash_different_data(self):
        """다른 데이터는 다른 해시"""
        data1 = [{"id": 1, "name": "test"}]
        data2 = [{"id": 1, "name": "test_modified"}]

        hash1 = hashlib.md5(str(data1).encode()).hexdigest()
        hash2 = hashlib.md5(str(data2).encode()).hexdigest()

        assert hash1 != hash2
