"""Google Sheets <-> SQLite Bidirectional Sync Service

Google Sheets를 프론트엔드로 사용하여 SQLite 데이터베이스를 편집합니다.
양방향 동기화를 지원하며, 변경 사항을 자동으로 감지하고 동기화합니다.

Usage:
    # 초기 동기화 (DB -> Sheet)
    python -m archive_analyzer.sheets_sync --init

    # 양방향 동기화 실행
    python -m archive_analyzer.sheets_sync --sync

    # 백그라운드 서비스 시작
    python -m archive_analyzer.sheets_sync --daemon
"""

import os
import sqlite3
import json
import hashlib
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

# Title Generator (optional - 없으면 규칙 기반 생성 스킵)
try:
    from archive_analyzer.title_generator import TitleGenerator
    TITLE_GENERATOR_AVAILABLE = True
except ImportError:
    TITLE_GENERATOR_AVAILABLE = False


# =============================================
# Configuration
# =============================================

@dataclass
class SyncConfig:
    """동기화 설정

    환경변수로 설정 가능:
        CREDENTIALS_PATH: GCP 서비스 계정 JSON 경로
        SPREADSHEET_ID: Google Sheets ID
        DB_PATH: SQLite 데이터베이스 경로
        SYNC_INTERVAL: 동기화 주기 (초)
        TABLES_TO_SYNC: 동기화할 테이블 (콤마 구분)
    """
    # Google Sheets
    credentials_path: str = None
    spreadsheet_id: str = None

    # Database
    db_path: str = None

    # Sync settings (120초 = 2분 - API 60req/min 한도 대응)
    sync_interval_seconds: int = 120
    tables_to_sync: List[str] = None

    def __post_init__(self):
        # 환경변수에서 기본값 로드
        if self.credentials_path is None:
            self.credentials_path = os.environ.get(
                "CREDENTIALS_PATH",
                "D:/AI/claude01/archive-analyzer/config/gcp-service-account.json"
            )

        if self.spreadsheet_id is None:
            self.spreadsheet_id = os.environ.get(
                "SPREADSHEET_ID",
                "1TW2ON5CQyIrL8aGQNYJ4OWkbZMaGmY9DoDG9VFXU60I"
            )

        if self.db_path is None:
            self.db_path = os.environ.get(
                "DB_PATH",
                "D:/AI/claude01/qwen_hand_analysis/data/pokervod.db"
            )

        # 환경변수에서 sync_interval 로드
        if env_interval := os.environ.get("SYNC_INTERVAL"):
            self.sync_interval_seconds = int(env_interval)

        if self.tables_to_sync is None:
            # 환경변수에서 테이블 목록 로드 (콤마 구분)
            if env_tables := os.environ.get("TABLES_TO_SYNC"):
                self.tables_to_sync = [t.strip() for t in env_tables.split(",")]
            else:
                # 동기화할 테이블 목록 (편집이 필요한 테이블)
                self.tables_to_sync = [
                    "display_names",
                    "catalogs",
                    "subcatalogs",
                    "players",
                    "events",
                    "tournaments",
                    "hands",
                    "files",
                    "wsoptv_player_aliases",
                ]


# =============================================
# Google Sheets Client
# =============================================

class SheetsClient:
    """Google Sheets API 클라이언트 (Rate Limit 대응)

    Google Sheets API 한도 (공식 문서 기준):
    - 읽기: 60회/분/유저, 300회/분/프로젝트
    - 쓰기: 60회/분/유저, 300회/분/프로젝트

    참고: https://developers.google.com/workspace/sheets/api/limits
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # API Rate Limit 설정 (60 req/min = 1 req/sec)
    API_DELAY = 1.2  # 요청 간 딜레이 (초) - 안전 마진 포함
    MAX_RETRIES = 5  # 최대 재시도 횟수
    MAX_BACKOFF = 64  # 최대 백오프 시간 (초)

    def __init__(self, config: SyncConfig):
        self.config = config
        self.client = None
        self.spreadsheet = None
        self._request_count = 0
        self._minute_start = time.time()
        self._connect()

    def _connect(self):
        """Google Sheets에 연결"""
        creds = Credentials.from_service_account_file(
            self.config.credentials_path,
            scopes=self.SCOPES,
        )
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)

    def _check_rate_limit(self):
        """분당 요청 수 체크 및 대기"""
        current_time = time.time()
        elapsed = current_time - self._minute_start

        # 1분 경과 시 카운터 리셋
        if elapsed >= 60:
            self._request_count = 0
            self._minute_start = current_time
            return

        # 60회 한도 근접 시 남은 시간 대기
        if self._request_count >= 55:  # 안전 마진
            wait_time = 60 - elapsed + 1
            print(f"    Approaching rate limit ({self._request_count}/60), waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
            self._request_count = 0
            self._minute_start = time.time()

    def _with_retry(self, func, *args, **kwargs):
        """API 호출 래퍼: Exponential Backoff 적용

        Google 권장 알고리즘: min((2^n + random_ms), max_backoff)
        """
        import random

        self._check_rate_limit()

        for attempt in range(self.MAX_RETRIES):
            try:
                time.sleep(self.API_DELAY)
                self._request_count += 1
                return func(*args, **kwargs)
            except APIError as e:
                if e.response.status_code == 429:
                    # Truncated Exponential Backoff
                    wait_time = min(
                        (2 ** attempt) + random.uniform(0, 1),
                        self.MAX_BACKOFF
                    )
                    print(f"    Rate limit (429), backoff {wait_time:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(wait_time)
                    # 분 카운터 리셋
                    self._request_count = 0
                    self._minute_start = time.time()
                else:
                    raise
        raise Exception(f"Max retries ({self.MAX_RETRIES}) exceeded")

    def get_or_create_worksheet(self, name: str, headers: List[str]) -> gspread.Worksheet:
        """워크시트 가져오기 또는 생성"""
        try:
            worksheet = self._with_retry(self.spreadsheet.worksheet, name)
        except gspread.WorksheetNotFound:
            worksheet = self._with_retry(
                self.spreadsheet.add_worksheet,
                title=name, rows=1000, cols=len(headers)
            )
            self._with_retry(worksheet.update, values=[headers], range_name='A1')
            self._with_retry(worksheet.freeze, rows=1)
        return worksheet

    def get_all_records(self, worksheet_name: str) -> List[Dict[str, Any]]:
        """워크시트의 모든 레코드 가져오기"""
        try:
            worksheet = self._with_retry(self.spreadsheet.worksheet, worksheet_name)
            return self._with_retry(worksheet.get_all_records)
        except gspread.WorksheetNotFound:
            return []

    def update_worksheet(self, worksheet_name: str, headers: List[str], rows: List[List[Any]]):
        """워크시트 전체 업데이트"""
        worksheet = self.get_or_create_worksheet(worksheet_name, headers)

        # 기존 데이터 클리어 (헤더 제외)
        self._with_retry(worksheet.batch_clear, ["A2:ZZ"])

        if rows:
            # 새 데이터 입력
            self._with_retry(worksheet.update, values=rows, range_name='A2')

    def get_worksheet_hash(self, worksheet_name: str) -> str:
        """워크시트 데이터의 해시값 계산"""
        records = self.get_all_records(worksheet_name)
        data_str = json.dumps(records, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()


# =============================================
# Database Client
# =============================================

class DatabaseClient:
    """SQLite 데이터베이스 클라이언트"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블 스키마 가져오기"""
        conn = self.get_connection()
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "name": row["name"],
                "type": row["type"],
                "pk": row["pk"] == 1,
            })
        conn.close()
        return columns

    def get_primary_key(self, table_name: str) -> str:
        """Primary Key 컬럼명 반환"""
        schema = self.get_table_schema(table_name)
        for col in schema:
            if col["pk"]:
                return col["name"]
        return None

    def get_all_records(self, table_name: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """테이블의 모든 레코드 가져오기"""
        conn = self.get_connection()
        cursor = conn.execute(f"SELECT * FROM {table_name}")
        columns = [description[0] for description in cursor.description]
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return columns, rows

    def get_table_hash(self, table_name: str) -> str:
        """테이블 데이터의 해시값 계산"""
        _, rows = self.get_all_records(table_name)
        data_str = json.dumps(rows, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()

    def upsert_record(self, table_name: str, record: Dict[str, Any], pk_column: str):
        """레코드 삽입 또는 업데이트"""
        conn = self.get_connection()

        columns = list(record.keys())
        placeholders = ", ".join(["?" for _ in columns])
        update_clause = ", ".join([f"{col} = excluded.{col}" for col in columns if col != pk_column])

        sql = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT({pk_column}) DO UPDATE SET {update_clause}
        """

        conn.execute(sql, list(record.values()))
        conn.commit()
        conn.close()

    def delete_record(self, table_name: str, pk_column: str, pk_value: Any):
        """레코드 삭제"""
        conn = self.get_connection()
        conn.execute(f"DELETE FROM {table_name} WHERE {pk_column} = ?", (pk_value,))
        conn.commit()
        conn.close()

    def bulk_upsert(self, table_name: str, records: List[Dict[str, Any]], pk_column: str):
        """여러 레코드 일괄 삽입/업데이트"""
        if not records:
            return

        conn = self.get_connection()
        columns = list(records[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        update_clause = ", ".join([f"{col} = excluded.{col}" for col in columns if col != pk_column])

        sql = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT({pk_column}) DO UPDATE SET {update_clause}
        """

        for record in records:
            conn.execute(sql, list(record.values()))

        conn.commit()
        conn.close()


# =============================================
# Sync Service
# =============================================

class SheetsSyncService:
    """Google Sheets <-> SQLite 양방향 동기화 서비스"""

    def __init__(self, config: SyncConfig = None):
        self.config = config or SyncConfig()
        self.sheets = SheetsClient(self.config)
        self.db = DatabaseClient(self.config.db_path)
        self._last_hashes: Dict[str, Dict[str, str]] = {}  # {table: {source: hash}}

        # Title Generator 초기화
        self.title_generator = TitleGenerator() if TITLE_GENERATOR_AVAILABLE else None

    def init_sheets(self):
        """DB 데이터를 Google Sheets로 초기화"""
        print("Initializing Google Sheets from database...")

        for table_name in self.config.tables_to_sync:
            print(f"  - {table_name}...")
            columns, rows = self.db.get_all_records(table_name)

            # 데이터를 시트 형식으로 변환
            sheet_rows = []
            for row in rows:
                sheet_rows.append([self._serialize_value(row.get(col)) for col in columns])

            self.sheets.update_worksheet(table_name, columns, sheet_rows)
            print(f"    -> {len(rows)} rows synced")

        print("Initialization complete!")

    def sync_table(self, table_name: str) -> Dict[str, int]:
        """단일 테이블 동기화"""
        pk_column = self.db.get_primary_key(table_name)
        if not pk_column:
            print(f"  Warning: {table_name} has no primary key, skipping...")
            return {"inserted": 0, "updated": 0, "deleted": 0}

        # DB와 Sheet 데이터 가져오기
        db_columns, db_rows = self.db.get_all_records(table_name)
        sheet_records = self.sheets.get_all_records(table_name)

        # 해시 비교로 변경 감지
        db_hash = self.db.get_table_hash(table_name)
        sheet_hash = self.sheets.get_worksheet_hash(table_name)

        last_db_hash = self._last_hashes.get(table_name, {}).get("db")
        last_sheet_hash = self._last_hashes.get(table_name, {}).get("sheet")

        stats = {"inserted": 0, "updated": 0, "deleted": 0}

        # 최초 실행 시 해시만 저장하고 스킵 (거짓 변경 방지)
        if last_db_hash is None or last_sheet_hash is None:
            self._last_hashes[table_name] = {"db": db_hash, "sheet": sheet_hash}
            print(f"    (초기화 - 해시 저장)")
            return stats

        db_changed = db_hash != last_db_hash
        sheet_changed = sheet_hash != last_sheet_hash

        if not db_changed and not sheet_changed:
            # 변경 없음
            return stats

        if sheet_changed and not db_changed:
            # Sheet에서 변경됨 -> DB로 동기화
            stats = self._sync_sheet_to_db(table_name, sheet_records, db_rows, pk_column, db_columns)
        elif db_changed and not sheet_changed:
            # DB에서 변경됨 -> Sheet로 동기화
            stats = self._sync_db_to_sheet(table_name, db_columns, db_rows)
        else:
            # 양쪽 다 변경됨 -> Sheet 우선 (사용자 편집 우선)
            print(f"    Both changed, prioritizing Sheet changes...")
            stats = self._sync_sheet_to_db(table_name, sheet_records, db_rows, pk_column, db_columns)

        # 해시 저장
        self._last_hashes[table_name] = {
            "db": self.db.get_table_hash(table_name),
            "sheet": self.sheets.get_worksheet_hash(table_name),
        }

        return stats

    def _sync_sheet_to_db(
        self,
        table_name: str,
        sheet_records: List[Dict],
        db_rows: List[Dict],
        pk_column: str,
        db_columns: List[str],
    ) -> Dict[str, int]:
        """Sheet -> DB 동기화"""
        stats = {"inserted": 0, "updated": 0, "deleted": 0}

        # DB의 현재 PK 목록
        db_pks = {self._serialize_value(row[pk_column]) for row in db_rows}
        sheet_pks = set()

        for record in sheet_records:
            # 빈 행 스킵
            if not any(record.values()):
                continue

            # 타입 변환
            typed_record = self._convert_types(record, table_name)
            pk_value = typed_record.get(pk_column)

            if pk_value is None or pk_value == "":
                continue

            # subcatalogs: full_path_name 자동 계산
            if table_name == "subcatalogs":
                typed_record = self._auto_calculate_subcatalog_fields(typed_record)

            # display_title 자동 생성 (비어있으면)
            if table_name in ["catalogs", "subcatalogs", "files", "hands"]:
                typed_record = self._auto_generate_display_title(table_name, typed_record)

            sheet_pks.add(str(pk_value))

            # DB에 upsert
            self.db.upsert_record(table_name, typed_record, pk_column)

            if str(pk_value) in db_pks:
                stats["updated"] += 1
            else:
                stats["inserted"] += 1

        # Sheet에서 삭제된 레코드 처리
        deleted_pks = db_pks - sheet_pks
        for pk in deleted_pks:
            self.db.delete_record(table_name, pk_column, pk)
            stats["deleted"] += 1

        return stats

    def _sync_db_to_sheet(
        self,
        table_name: str,
        columns: List[str],
        rows: List[Dict],
    ) -> Dict[str, int]:
        """DB -> Sheet 동기화"""
        sheet_rows = []
        for row in rows:
            sheet_rows.append([self._serialize_value(row.get(col)) for col in columns])

        self.sheets.update_worksheet(table_name, columns, sheet_rows)
        return {"inserted": 0, "updated": len(rows), "deleted": 0}

    def _serialize_value(self, value: Any) -> Any:
        """값을 시트 호환 형식으로 변환"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        return str(value)

    def _convert_types(self, record: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """시트 데이터를 DB 타입으로 변환"""
        schema = self.db.get_table_schema(table_name)
        type_map = {col["name"]: col["type"] for col in schema}

        converted = {}
        for key, value in record.items():
            if key not in type_map:
                continue

            col_type = type_map[key].upper()

            if value == "" or value is None:
                converted[key] = None
            elif "INT" in col_type:
                try:
                    converted[key] = int(float(value)) if value else None
                except (ValueError, TypeError):
                    converted[key] = None
            elif "FLOAT" in col_type or "REAL" in col_type:
                try:
                    converted[key] = float(value) if value else None
                except (ValueError, TypeError):
                    converted[key] = None
            elif "BOOL" in col_type:
                converted[key] = bool(value) if value else False
            else:
                converted[key] = str(value) if value else None

        return converted

    def _auto_calculate_subcatalog_fields(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """subcatalogs: sub1/sub2/sub3 기반으로 파생 필드 자동 계산

        Google Sheets에서 sub1, sub2, sub3만 수정하면:
        - full_path_name: 자동 생성
        - level1_name, level2_name, level3_name: sub1/sub2/sub3에서 복사
        - depth: 자동 계산
        """
        # catalog 이름 가져오기
        catalog_id = record.get("catalog_id", "")
        catalog_name = catalog_id.upper() if catalog_id else ""

        # sub1, sub2, sub3 가져오기
        sub1 = record.get("sub1") or ""
        sub2 = record.get("sub2") or ""
        sub3 = record.get("sub3") or ""

        # full_path_name 자동 계산
        parts = [p for p in [catalog_name, sub1, sub2, sub3] if p]
        record["full_path_name"] = " > ".join(parts) if parts else ""

        # level 필드 동기화 (하위 호환)
        record["level1_name"] = sub1 if sub1 else None
        record["level2_name"] = sub2 if sub2 else None
        record["level3_name"] = sub3 if sub3 else None

        # depth 자동 계산
        if sub3:
            record["depth"] = 3
        elif sub2:
            record["depth"] = 2
        elif sub1:
            record["depth"] = 1
        else:
            record["depth"] = 0

        return record

    def _auto_generate_display_title(
        self,
        table_name: str,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """display_title이 비어있으면 자동 생성

        title_source: 'rule_based' (자동생성), 'manual' (수동입력), 'ai_generated' (AI)
        title_verified: 수동 검수 완료 여부
        """
        if not self.title_generator:
            return record

        # display_title이 이미 있고 verified면 스킵
        if record.get("display_title") and record.get("title_verified"):
            return record

        # 테이블별 제목 생성
        if table_name == "catalogs":
            # catalog: catalog_id -> 풀네임
            result = self.title_generator.generate_catalog_title(
                catalog_id=record.get("id", ""),
                name=record.get("name", ""),
            )
            if not record.get("display_title"):
                record["display_title"] = result.title
                record["title_source"] = result.source

        elif table_name == "subcatalogs":
            # subcatalog: catalog + sub1/sub2/sub3 조합
            result = self.title_generator.generate_subcatalog_title(
                catalog_id=record.get("catalog_id", ""),
                sub1=record.get("sub1"),
                sub2=record.get("sub2"),
                sub3=record.get("sub3"),
            )
            if not record.get("display_title"):
                record["display_title"] = result.title
                record["title_source"] = result.source

        elif table_name == "files":
            # file: 파일명 기반 제목 생성
            result = self.title_generator.generate_file_title(
                filename=record.get("filename", ""),
                nas_path=record.get("nas_path"),
            )
            if not record.get("display_title"):
                record["display_title"] = result.title
                record["display_subtitle"] = result.subtitle
                record["title_source"] = result.source

        elif table_name == "hands":
            # hands: 플레이어, 상황 기반 제목 생성
            # JSON 필드 파싱
            players = []
            if record.get("players"):
                try:
                    players = json.loads(record["players"]) if isinstance(record["players"], str) else record["players"]
                except (json.JSONDecodeError, TypeError):
                    pass

            tags = []
            if record.get("tags"):
                try:
                    tags = json.loads(record["tags"]) if isinstance(record["tags"], str) else record["tags"]
                except (json.JSONDecodeError, TypeError):
                    pass

            result = self.title_generator.generate_hand_title(
                players=players,
                winner=record.get("winner"),
                pot_size_bb=record.get("pot_size_bb"),
                is_all_in=bool(record.get("is_all_in")),
                is_showdown=bool(record.get("is_showdown")),
                tags=tags,
            )
            if not record.get("display_title"):
                record["display_title"] = result.title
                record["title_source"] = result.source

        return record

    def sync_all(self) -> Dict[str, Dict[str, int]]:
        """모든 테이블 동기화"""
        print(f"Syncing {len(self.config.tables_to_sync)} tables...")
        results = {}

        for table_name in self.config.tables_to_sync:
            print(f"  - {table_name}...")
            stats = self.sync_table(table_name)
            results[table_name] = stats

            if any(stats.values()):
                print(f"    -> inserted: {stats['inserted']}, updated: {stats['updated']}, deleted: {stats['deleted']}")

        return results

    def run_daemon(self):
        """백그라운드 동기화 서비스 실행"""
        import time

        print(f"Starting sync daemon (interval: {self.config.sync_interval_seconds}s)")
        print("Press Ctrl+C to stop")
        print()

        # 초기 해시 설정
        for table_name in self.config.tables_to_sync:
            self._last_hashes[table_name] = {
                "db": self.db.get_table_hash(table_name),
                "sheet": self.sheets.get_worksheet_hash(table_name),
            }

        try:
            while True:
                self.sync_all()
                time.sleep(self.config.sync_interval_seconds)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")


# =============================================
# CLI
# =============================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Google Sheets <-> SQLite Sync Service")
    parser.add_argument("--init", action="store_true", help="Initialize sheets from database")
    parser.add_argument("--sync", action="store_true", help="Run one-time sync")
    parser.add_argument("--daemon", action="store_true", help="Run as background service")
    parser.add_argument("--interval", type=int, default=30, help="Sync interval in seconds")

    args = parser.parse_args()

    config = SyncConfig(sync_interval_seconds=args.interval)
    service = SheetsSyncService(config)

    if args.init:
        service.init_sheets()
    elif args.sync:
        service.sync_all()
    elif args.daemon:
        service.run_daemon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
