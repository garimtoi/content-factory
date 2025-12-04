"""SQLite → Firestore 마이그레이션 스크립트

Issue #59, #61: 웹 기반 마이그레이션 UI + Firestore 스키마 적용

사용법:
    # 환경변수 설정
    export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

    # Dry-run (실제 쓰기 없이 시뮬레이션)
    python scripts/migrate_to_firestore.py --dry-run

    # 전체 마이그레이션
    python scripts/migrate_to_firestore.py

    # 특정 컬렉션만
    python scripts/migrate_to_firestore.py --collections catalogs,players

    # 통계만 확인
    python scripts/migrate_to_firestore.py --stats
"""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Warning: firebase-admin not installed. Run: pip install firebase-admin")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 기본 경로
POKERVOD_DB = Path("D:/AI/claude01/shared-data/pokervod.db")


@dataclass
class MigrationStats:
    """마이그레이션 통계"""

    collection: str
    total: int = 0
    migrated: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: List[str] = field(default_factory=list)


@dataclass
class MigrationResult:
    """전체 마이그레이션 결과"""

    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    dry_run: bool = False
    stats: Dict[str, MigrationStats] = field(default_factory=dict)

    @property
    def total_migrated(self) -> int:
        return sum(s.migrated for s in self.stats.values())

    @property
    def total_errors(self) -> int:
        return sum(s.errors for s in self.stats.values())


class FirestoreMigrator:
    """SQLite → Firestore 마이그레이터"""

    def __init__(
        self,
        sqlite_path: Path = POKERVOD_DB,
        dry_run: bool = False,
        batch_size: int = 500,
    ):
        self.sqlite_path = sqlite_path
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.db: Optional[Any] = None
        self.conn: Optional[sqlite3.Connection] = None

        if not self.dry_run and FIREBASE_AVAILABLE:
            self._init_firebase()

    def _init_firebase(self):
        """Firebase 초기화"""
        try:
            # 이미 초기화된 경우 기존 앱 사용
            firebase_admin.get_app()
        except ValueError:
            # 초기화되지 않은 경우
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_path and Path(cred_path).exists():
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                # Application Default Credentials 사용
                firebase_admin.initialize_app()

        self.db = firestore.client()
        logger.info("Firebase 초기화 완료")

    def _connect_sqlite(self):
        """SQLite 연결"""
        if not self.sqlite_path.exists():
            raise FileNotFoundError(f"SQLite DB not found: {self.sqlite_path}")
        self.conn = sqlite3.connect(self.sqlite_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"SQLite 연결: {self.sqlite_path}")

    def _close_sqlite(self):
        """SQLite 연결 종료"""
        if self.conn:
            self.conn.close()

    def _generate_id(self, value: str) -> str:
        """문자열을 Firestore 문서 ID로 변환"""
        # 슬래시, 공백 등을 하이픈으로 변환
        slug = value.lower().replace("/", "-").replace(" ", "-").replace("_", "-")
        # 연속 하이픈 제거
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")[:100]  # 최대 100자

    def _timestamp_to_iso(self, ts: Optional[str]) -> Optional[str]:
        """SQLite timestamp를 ISO 형식으로 변환"""
        if not ts:
            return None
        try:
            # 다양한 형식 시도
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(ts, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
            return ts
        except Exception:
            return ts

    # ==================== 컬렉션별 마이그레이션 ====================

    def migrate_catalogs(self) -> MigrationStats:
        """catalogs 마이그레이션"""
        stats = MigrationStats(collection="catalogs")

        cursor = self.conn.execute("""
            SELECT id, name, description, display_title, title_source,
                   title_verified, created_at, updated_at
            FROM catalogs
        """)
        rows = cursor.fetchall()
        stats.total = len(rows)

        # 시리즈/콘텐츠 집계
        series_counts = dict(
            self.conn.execute("""
                SELECT catalog_id, COUNT(*) FROM series GROUP BY catalog_id
            """).fetchall()
        )
        content_counts = dict(
            self.conn.execute("""
                SELECT s.catalog_id, COUNT(c.id)
                FROM contents c
                JOIN series s ON c.series_id = s.id
                GROUP BY s.catalog_id
            """).fetchall()
        )

        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                catalog_id = self._generate_id(row["id"])
                doc_data = {
                    "id": catalog_id,
                    "name": row["name"],
                    "displayTitle": row["display_title"] or row["name"],
                    "description": row["description"],
                    "titleSource": row["title_source"] or "rule_based",
                    "titleVerified": bool(row["title_verified"]),
                    "seriesCount": series_counts.get(row["id"], 0),
                    "contentCount": content_counts.get(row["id"], 0),
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                    "updatedAt": self._timestamp_to_iso(row["updated_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] catalog: {catalog_id}")
                else:
                    doc_ref = self.db.collection("catalogs").document(catalog_id)
                    batch.set(doc_ref, doc_data)

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"catalog {row['id']}: {e}")
                logger.error(f"Error migrating catalog {row['id']}: {e}")

        if not self.dry_run and batch:
            batch.commit()
            logger.info(f"catalogs 커밋 완료: {stats.migrated}건")

        return stats

    def migrate_series(self) -> MigrationStats:
        """series 마이그레이션 (catalogs 서브컬렉션)"""
        stats = MigrationStats(collection="series")

        cursor = self.conn.execute("""
            SELECT s.*, c.id as catalog_varchar_id
            FROM series s
            JOIN catalogs c ON s.catalog_id = c.id OR s.catalog_id = c.rowid
        """)
        rows = cursor.fetchall()
        stats.total = len(rows)

        # 에피소드 집계
        episode_counts = dict(
            self.conn.execute("""
                SELECT series_id, COUNT(*) FROM contents GROUP BY series_id
            """).fetchall()
        )
        duration_sums = dict(
            self.conn.execute("""
                SELECT series_id, SUM(duration_sec) FROM contents GROUP BY series_id
            """).fetchall()
        )

        for row in rows:
            try:
                catalog_id = self._generate_id(row["catalog_varchar_id"])
                series_id = str(row["id"])

                doc_data = {
                    "id": series_id,
                    "catalogId": catalog_id,
                    "slug": row["slug"] or series_id,
                    "title": row["title"],
                    "subtitle": row["subtitle"],
                    "description": row["description"],
                    "year": row["year"],
                    "season": row["season"],
                    "location": row["location"],
                    "eventType": row["event_type"],
                    "thumbnailUrl": row["thumbnail_url"],
                    "episodeCount": episode_counts.get(row["id"], 0),
                    "totalDuration": duration_sums.get(row["id"], 0) or 0,
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                    "updatedAt": self._timestamp_to_iso(row["updated_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] series: {catalog_id}/{series_id}")
                else:
                    doc_ref = (
                        self.db.collection("catalogs")
                        .document(catalog_id)
                        .collection("series")
                        .document(series_id)
                    )
                    doc_ref.set(doc_data)

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"series {row['id']}: {e}")
                logger.error(f"Error migrating series {row['id']}: {e}")

        logger.info(f"series 마이그레이션 완료: {stats.migrated}건")
        return stats

    def migrate_contents(self) -> MigrationStats:
        """contents 마이그레이션 (series 서브컬렉션, players/tags 임베딩)"""
        stats = MigrationStats(collection="contents")

        # 콘텐츠 조회
        cursor = self.conn.execute("""
            SELECT c.*, s.catalog_id, cat.id as catalog_varchar_id
            FROM contents c
            JOIN series s ON c.series_id = s.id
            JOIN catalogs cat ON s.catalog_id = cat.id OR s.catalog_id = cat.rowid
        """)
        rows = cursor.fetchall()
        stats.total = len(rows)

        # content_players 조회
        player_map = {}
        for row in self.conn.execute("""
            SELECT cp.content_id, p.name, p.display_name, cp.role
            FROM content_players cp
            JOIN players p ON cp.player_id = p.name OR cp.player_id = p.rowid
        """):
            content_id = row[0]
            if content_id not in player_map:
                player_map[content_id] = []
            player_map[content_id].append({
                "id": self._generate_id(row[1]),
                "name": row[1],
                "displayName": row[2],
                "role": row[3] or "main",
            })

        # content_tags 조회
        tag_map = {}
        for row in self.conn.execute("""
            SELECT ct.content_id, t.id, t.name, t.category
            FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
        """):
            content_id = row[0]
            if content_id not in tag_map:
                tag_map[content_id] = []
            tag_map[content_id].append({
                "id": str(row[1]),
                "name": row[2],
                "category": row[3],
            })

        batch_count = 0
        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                catalog_id = self._generate_id(row["catalog_varchar_id"])
                series_id = str(row["series_id"])
                content_id = str(row["id"])

                doc_data = {
                    "id": content_id,
                    "seriesId": series_id,
                    "catalogId": catalog_id,
                    "contentType": row["content_type"] or "episode",
                    "headline": row["headline"],
                    "subline": row["subline"],
                    "thumbnailUrl": row["thumbnail_url"],
                    "thumbnailText": row["thumbnail_text"],
                    "fileId": row["file_id"],
                    "durationSec": row["duration_sec"] or 0,
                    "resolution": row["resolution"],
                    "codec": row["codec"],
                    "players": player_map.get(row["id"], []),
                    "tags": tag_map.get(row["id"], []),
                    "viewCount": row["view_count"] or 0,
                    "lastViewedAt": self._timestamp_to_iso(row["last_viewed_at"]),
                    "episodeNum": row["episode_num"],
                    "airDate": self._timestamp_to_iso(row["air_date"]),
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                    "updatedAt": self._timestamp_to_iso(row["updated_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] content: {catalog_id}/{series_id}/{content_id}")
                else:
                    doc_ref = (
                        self.db.collection("catalogs")
                        .document(catalog_id)
                        .collection("series")
                        .document(series_id)
                        .collection("contents")
                        .document(content_id)
                    )
                    batch.set(doc_ref, doc_data)
                    batch_count += 1

                    # 배치 커밋 (500건마다)
                    if batch_count >= self.batch_size:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                        logger.info(f"contents 배치 커밋: {stats.migrated + 1}건")

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"content {row['id']}: {e}")
                logger.error(f"Error migrating content {row['id']}: {e}")

        # 남은 배치 커밋
        if not self.dry_run and batch and batch_count > 0:
            batch.commit()

        logger.info(f"contents 마이그레이션 완료: {stats.migrated}건")
        return stats

    def migrate_files(self) -> MigrationStats:
        """files 마이그레이션"""
        stats = MigrationStats(collection="files")

        cursor = self.conn.execute("""
            SELECT * FROM files
        """)
        rows = cursor.fetchall()
        stats.total = len(rows)

        # 연결된 콘텐츠 조회
        content_map = {}
        for row in self.conn.execute("""
            SELECT file_id, id FROM contents WHERE file_id IS NOT NULL
        """):
            file_id = row[0]
            if file_id not in content_map:
                content_map[file_id] = []
            content_map[file_id].append(str(row[1]))

        batch_count = 0
        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                file_id = row["id"]
                # NAS 경로로 ID 생성
                nas_path = row["nas_path"] or ""
                doc_id = hashlib.md5(nas_path.lower().encode()).hexdigest()[:16] if nas_path else file_id

                doc_data = {
                    "id": doc_id,
                    "originalId": file_id,
                    "nasPath": nas_path,
                    "filename": row["filename"],
                    "sizeBytes": row["size_bytes"] or 0,
                    "durationSec": row["duration_sec"],
                    "resolution": row["resolution"],
                    "codec": row["codec"],
                    "fps": row["fps"],
                    "bitrateKbps": row["bitrate_kbps"],
                    "analysisStatus": row["analysis_status"] or "pending",
                    "analysisError": row["analysis_error"],
                    "analyzedAt": self._timestamp_to_iso(row["analyzed_at"]),
                    "contentIds": content_map.get(file_id, []),
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                    "updatedAt": self._timestamp_to_iso(row["updated_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] file: {doc_id}")
                else:
                    doc_ref = self.db.collection("files").document(doc_id)
                    batch.set(doc_ref, doc_data)
                    batch_count += 1

                    if batch_count >= self.batch_size:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"file {row['id']}: {e}")
                logger.error(f"Error migrating file {row['id']}: {e}")

        if not self.dry_run and batch and batch_count > 0:
            batch.commit()

        logger.info(f"files 마이그레이션 완료: {stats.migrated}건")
        return stats

    def migrate_players(self) -> MigrationStats:
        """players 마이그레이션"""
        stats = MigrationStats(collection="players")

        cursor = self.conn.execute("SELECT * FROM players")
        rows = cursor.fetchall()
        stats.total = len(rows)

        # 출연 콘텐츠 수 집계
        content_counts = dict(
            self.conn.execute("""
                SELECT player_id, COUNT(*) FROM content_players GROUP BY player_id
            """).fetchall()
        )

        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                player_id = self._generate_id(row["name"])

                doc_data = {
                    "id": player_id,
                    "name": row["name"],
                    "displayName": row["display_name"],
                    "country": row["country"],
                    "totalContents": content_counts.get(row["name"], 0),
                    "totalHands": row["total_hands"],
                    "totalWins": row["total_wins"],
                    "searchVector": row["search_vector"],
                    "aliases": [],
                    "firstSeenAt": self._timestamp_to_iso(row["first_seen_at"]),
                    "lastSeenAt": self._timestamp_to_iso(row["last_seen_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] player: {player_id}")
                else:
                    doc_ref = self.db.collection("players").document(player_id)
                    batch.set(doc_ref, doc_data)

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"player {row['name']}: {e}")

        if not self.dry_run and batch:
            batch.commit()

        logger.info(f"players 마이그레이션 완료: {stats.migrated}건")
        return stats

    def migrate_tags(self) -> MigrationStats:
        """tags 마이그레이션"""
        stats = MigrationStats(collection="tags")

        cursor = self.conn.execute("SELECT * FROM tags")
        rows = cursor.fetchall()
        stats.total = len(rows)

        # 사용 횟수 집계
        usage_counts = dict(
            self.conn.execute("""
                SELECT tag_id, COUNT(*) FROM content_tags GROUP BY tag_id
            """).fetchall()
        )

        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                tag_id = str(row["id"])

                doc_data = {
                    "id": tag_id,
                    "name": row["name"],
                    "category": row["category"] or "other",
                    "usageCount": usage_counts.get(row["id"], 0),
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] tag: {tag_id}")
                else:
                    doc_ref = self.db.collection("tags").document(tag_id)
                    batch.set(doc_ref, doc_data)

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"tag {row['id']}: {e}")

        if not self.dry_run and batch:
            batch.commit()

        logger.info(f"tags 마이그레이션 완료: {stats.migrated}건")
        return stats

    def migrate_users(self) -> MigrationStats:
        """users 마이그레이션"""
        stats = MigrationStats(collection="users")

        cursor = self.conn.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        stats.total = len(rows)

        batch = self.db.batch() if self.db else None

        for row in rows:
            try:
                user_id = row["id"]

                doc_data = {
                    "id": user_id,
                    "username": row["username"],
                    "email": row["email"],
                    "displayName": row["display_name"],
                    "avatarUrl": row["avatar_url"],
                    "preferredLanguage": row["preferred_language"] or "ko",
                    "autoplayEnabled": bool(row["autoplay_enabled"]),
                    "isActive": bool(row["is_active"]),
                    "isAdmin": bool(row["is_admin"]),
                    "role": row["role"] or "viewer",
                    "authProvider": row["auth_provider"] or "email",
                    "googleId": row["google_id"],
                    "createdAt": self._timestamp_to_iso(row["created_at"]),
                    "lastLoginAt": self._timestamp_to_iso(row["last_login_at"]),
                    "loginCount": row["login_count"] or 0,
                }

                if self.dry_run:
                    logger.debug(f"[DRY-RUN] user: {user_id}")
                else:
                    doc_ref = self.db.collection("users").document(user_id)
                    batch.set(doc_ref, doc_data)

                stats.migrated += 1

            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"user {row['id']}: {e}")

        if not self.dry_run and batch:
            batch.commit()

        logger.info(f"users 마이그레이션 완료: {stats.migrated}건")
        return stats

    # ==================== 메인 실행 ====================

    def run(self, collections: Optional[List[str]] = None) -> MigrationResult:
        """전체 마이그레이션 실행"""
        result = MigrationResult(dry_run=self.dry_run)

        # 마이그레이션 함수 매핑
        migrate_funcs = {
            "catalogs": self.migrate_catalogs,
            "series": self.migrate_series,
            "contents": self.migrate_contents,
            "files": self.migrate_files,
            "players": self.migrate_players,
            "tags": self.migrate_tags,
            "users": self.migrate_users,
        }

        # 실행할 컬렉션 결정
        if collections:
            selected = [c for c in collections if c in migrate_funcs]
        else:
            selected = list(migrate_funcs.keys())

        try:
            self._connect_sqlite()

            for collection in selected:
                logger.info(f"=== {collection} 마이그레이션 시작 ===")
                stats = migrate_funcs[collection]()
                result.stats[collection] = stats

        finally:
            self._close_sqlite()

        result.completed_at = datetime.now()
        return result

    def get_stats(self) -> Dict[str, int]:
        """현재 SQLite 통계"""
        self._connect_sqlite()

        stats = {}
        tables = ["catalogs", "series", "contents", "files", "players", "tags", "users"]

        for table in tables:
            try:
                cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except Exception:
                stats[table] = 0

        self._close_sqlite()
        return stats


def main():
    parser = argparse.ArgumentParser(description="SQLite → Firestore 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="실제 쓰기 없이 시뮬레이션")
    parser.add_argument("--collections", type=str, help="마이그레이션할 컬렉션 (쉼표 구분)")
    parser.add_argument("--stats", action="store_true", help="통계만 출력")
    parser.add_argument("--batch-size", type=int, default=500, help="배치 크기 (기본: 500)")
    parser.add_argument("--db", type=str, default=str(POKERVOD_DB), help="SQLite DB 경로")

    args = parser.parse_args()

    migrator = FirestoreMigrator(
        sqlite_path=Path(args.db),
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )

    if args.stats:
        stats = migrator.get_stats()
        print("\n=== SQLite 통계 ===")
        for table, count in stats.items():
            print(f"  {table}: {count:,}건")
        return

    if not FIREBASE_AVAILABLE and not args.dry_run:
        print("Error: firebase-admin not installed")
        print("Run: pip install firebase-admin")
        sys.exit(1)

    collections = args.collections.split(",") if args.collections else None

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}마이그레이션 시작...")
    result = migrator.run(collections=collections)

    print("\n=== 마이그레이션 결과 ===")
    for collection, stats in result.stats.items():
        status = "OK" if stats.errors == 0 else "WARN"
        print(f"  [{status}] {collection}: {stats.migrated}/{stats.total}건 (에러: {stats.errors})")
        for err in stats.error_messages[:3]:
            print(f"       - {err}")

    duration = (result.completed_at - result.started_at).total_seconds()
    print(f"\n총 마이그레이션: {result.total_migrated}건")
    print(f"총 에러: {result.total_errors}건")
    print(f"소요 시간: {duration:.1f}초")


if __name__ == "__main__":
    main()
