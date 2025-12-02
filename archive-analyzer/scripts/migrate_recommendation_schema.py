#!/usr/bin/env python
"""
추천 시스템 스키마 마이그레이션 스크립트

DATABASE_SCHEMA.md Section 8에 정의된 10개 테이블을 pokervod.db에 생성합니다.

Usage:
    python scripts/migrate_recommendation_schema.py --dry-run  # 시뮬레이션
    python scripts/migrate_recommendation_schema.py            # 실행
    python scripts/migrate_recommendation_schema.py --rollback # 롤백
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 경로 설정
POKERVOD_DB = Path("D:/AI/claude01/qwen_hand_analysis/data/pokervod.db")

# 신규 테이블 DDL 정의
TABLES = {
    "recommendation_cache": """
        CREATE TABLE IF NOT EXISTS recommendation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            rec_type VARCHAR(50) NOT NULL,
            context_item_id VARCHAR(200),
            items JSON NOT NULL,
            algorithm VARCHAR(50) NOT NULL DEFAULT 'gorse',
            model_version VARCHAR(50),
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, rec_type, context_item_id)
        )
    """,
    "trending_scores": """
        CREATE TABLE IF NOT EXISTS trending_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id VARCHAR(200) NOT NULL,
            catalog_id VARCHAR(50),
            time_bucket TIMESTAMP NOT NULL,
            view_count INTEGER DEFAULT 0,
            unique_viewers INTEGER DEFAULT 0,
            avg_completion_rate FLOAT DEFAULT 0,
            avg_watch_duration FLOAT DEFAULT 0,
            trending_score FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_id, time_bucket),
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (catalog_id) REFERENCES catalogs(id)
        )
    """,
    "home_rows": """
        CREATE TABLE IF NOT EXISTS home_rows (
            id VARCHAR(50) PRIMARY KEY,
            row_type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            title_template VARCHAR(200),
            algorithm VARCHAR(50),
            query_params JSON,
            default_position INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            requires_history BOOLEAN DEFAULT FALSE,
            min_items INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "user_home_rows": """
        CREATE TABLE IF NOT EXISTS user_home_rows (
            user_id VARCHAR(50) NOT NULL,
            row_id VARCHAR(50) NOT NULL,
            position INTEGER,
            is_visible BOOLEAN DEFAULT TRUE,
            is_personalized BOOLEAN DEFAULT TRUE,
            context_item_id VARCHAR(200),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, row_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (row_id) REFERENCES home_rows(id)
        )
    """,
    "artwork_variants": """
        CREATE TABLE IF NOT EXISTS artwork_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id VARCHAR(200) NOT NULL,
            variant_type VARCHAR(50) NOT NULL DEFAULT 'default',
            image_url TEXT NOT NULL,
            thumbnail_time_sec FLOAT,
            focus_player VARCHAR(100),
            dominant_emotion VARCHAR(50),
            tags JSON,
            generated_by VARCHAR(50) DEFAULT 'ffmpeg',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """,
    "artwork_selections": """
        CREATE TABLE IF NOT EXISTS artwork_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            file_id VARCHAR(200) NOT NULL,
            artwork_id INTEGER NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            context JSON,
            selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, file_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (artwork_id) REFERENCES artwork_variants(id)
        )
    """,
    "experiments": """
        CREATE TABLE IF NOT EXISTS experiments (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            variants JSON NOT NULL,
            target_metric VARCHAR(100),
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            status VARCHAR(20) DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "experiment_assignments": """
        CREATE TABLE IF NOT EXISTS experiment_assignments (
            user_id VARCHAR(50) NOT NULL,
            experiment_id VARCHAR(50) NOT NULL,
            variant_id VARCHAR(50) NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, experiment_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """,
    "user_embeddings": """
        CREATE TABLE IF NOT EXISTS user_embeddings (
            user_id VARCHAR(50) PRIMARY KEY,
            embedding BLOB NOT NULL,
            algorithm VARCHAR(50) NOT NULL,
            model_version VARCHAR(50),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "item_embeddings": """
        CREATE TABLE IF NOT EXISTS item_embeddings (
            item_id VARCHAR(200) NOT NULL,
            item_type VARCHAR(50) NOT NULL,
            embedding BLOB NOT NULL,
            algorithm VARCHAR(50) NOT NULL,
            model_version VARCHAR(50),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (item_id, item_type)
        )
    """,
}

# 인덱스 정의
INDEXES = {
    "recommendation_cache": [
        "CREATE INDEX IF NOT EXISTS idx_rec_cache_user ON recommendation_cache(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_rec_cache_expires ON recommendation_cache(expires_at)",
    ],
    "trending_scores": [
        "CREATE INDEX IF NOT EXISTS idx_trending_bucket ON trending_scores(time_bucket)",
        "CREATE INDEX IF NOT EXISTS idx_trending_score ON trending_scores(trending_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_trending_catalog ON trending_scores(catalog_id, time_bucket)",
    ],
    "artwork_variants": [
        "CREATE INDEX IF NOT EXISTS idx_artwork_file ON artwork_variants(file_id)",
        "CREATE INDEX IF NOT EXISTS idx_artwork_player ON artwork_variants(focus_player)",
    ],
}

# 기본 home_rows 데이터
DEFAULT_HOME_ROWS = [
    ("continue_watching", "continue", "계속 시청하기", None, "watch_progress", None, 1, True, True, 1),
    ("trending_all", "trending", "지금 인기 있는 영상", None, "trending_24h", None, 2, True, False, 5),
    ("trending_wsop", "trending", "WSOP 인기 영상", None, "trending_24h", '{"catalog_id": "WSOP"}', 3, True, False, 5),
    ("trending_hcl", "trending", "HCL 인기 영상", None, "trending_24h", '{"catalog_id": "HCL"}', 4, True, False, 5),
    ("new_releases", "category", "새로 추가된 영상", None, "recent", None, 5, True, False, 5),
    ("personalized_for_you", "personalized", "당신을 위한 추천", None, "gorse_hybrid", None, 6, True, True, 5),
    ("because_watched", "personalized", "{title} 시청 후 추천", "{title} 시청 후 추천", "similar_items", None, 7, True, True, 3),
    ("top_hands", "curated", "베스트 핸드 모음", None, "highlight_score", '{"min_score": 3}', 8, True, False, 5),
    ("favorite_players", "personalized", "즐겨찾는 플레이어", None, "player_based", None, 9, True, True, 3),
]


def get_existing_tables(conn: sqlite3.Connection) -> set:
    """기존 테이블 목록 조회"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    return {row[0] for row in cursor.fetchall()}


def migrate(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """마이그레이션 실행"""
    results = {
        "tables_created": [],
        "tables_skipped": [],
        "indexes_created": [],
        "data_inserted": [],
    }

    existing_tables = get_existing_tables(conn)

    # 1. 테이블 생성
    for table_name, ddl in TABLES.items():
        if table_name in existing_tables:
            results["tables_skipped"].append(table_name)
            print(f"⏭️  {table_name}: 이미 존재 (스킵)")
        else:
            if dry_run:
                print(f"🔍 {table_name}: 생성 예정")
            else:
                conn.execute(ddl)
                print(f"✅ {table_name}: 생성 완료")
            results["tables_created"].append(table_name)

    # 2. 인덱스 생성
    for table_name, index_ddls in INDEXES.items():
        for index_ddl in index_ddls:
            index_name = index_ddl.split("IF NOT EXISTS ")[1].split(" ON")[0]
            if dry_run:
                print(f"🔍 {index_name}: 생성 예정")
            else:
                conn.execute(index_ddl)
                print(f"✅ {index_name}: 인덱스 생성 완료")
            results["indexes_created"].append(index_name)

    # 3. 기본 데이터 삽입 (home_rows)
    if "home_rows" in results["tables_created"]:
        if dry_run:
            print(f"🔍 home_rows: {len(DEFAULT_HOME_ROWS)}개 기본 데이터 삽입 예정")
        else:
            conn.executemany(
                """
                INSERT INTO home_rows
                (id, row_type, title, title_template, algorithm, query_params,
                 default_position, is_active, requires_history, min_items)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                DEFAULT_HOME_ROWS
            )
            print(f"✅ home_rows: {len(DEFAULT_HOME_ROWS)}개 기본 데이터 삽입 완료")
        results["data_inserted"].append(f"home_rows: {len(DEFAULT_HOME_ROWS)} rows")

    if not dry_run:
        conn.commit()

    return results


def rollback(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """롤백 실행 (테이블 삭제)"""
    results = {
        "tables_dropped": [],
        "tables_not_found": [],
    }

    existing_tables = get_existing_tables(conn)

    # 역순으로 삭제 (의존성 고려)
    for table_name in reversed(list(TABLES.keys())):
        if table_name in existing_tables:
            if dry_run:
                print(f"🔍 {table_name}: 삭제 예정")
            else:
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                print(f"🗑️  {table_name}: 삭제 완료")
            results["tables_dropped"].append(table_name)
        else:
            results["tables_not_found"].append(table_name)
            print(f"⏭️  {table_name}: 존재하지 않음 (스킵)")

    if not dry_run:
        conn.commit()

    return results


def verify(conn: sqlite3.Connection) -> dict:
    """마이그레이션 검증"""
    results = {
        "existing": [],
        "missing": [],
        "row_counts": {},
    }

    existing_tables = get_existing_tables(conn)

    for table_name in TABLES.keys():
        if table_name in existing_tables:
            results["existing"].append(table_name)
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            results["row_counts"][table_name] = count
        else:
            results["missing"].append(table_name)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="추천 시스템 스키마 마이그레이션"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="시뮬레이션 모드 (실제 변경 없음)"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="롤백 모드 (테이블 삭제)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="검증 모드 (상태 확인)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(POKERVOD_DB),
        help=f"DB 경로 (기본값: {POKERVOD_DB})"
    )

    args = parser.parse_args()

    # DB 연결
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)

    print(f"📁 DB: {db_path}")
    print(f"📅 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    conn = sqlite3.connect(str(db_path))

    try:
        if args.verify:
            print("🔍 마이그레이션 상태 검증\n")
            results = verify(conn)

            print(f"\n✅ 존재하는 테이블: {len(results['existing'])}/{len(TABLES)}")
            for table in results["existing"]:
                count = results["row_counts"].get(table, 0)
                print(f"   - {table}: {count} rows")

            if results["missing"]:
                print(f"\n❌ 누락된 테이블: {len(results['missing'])}")
                for table in results["missing"]:
                    print(f"   - {table}")

        elif args.rollback:
            print(f"{'🔍 롤백 시뮬레이션' if args.dry_run else '🗑️  롤백 실행'}\n")
            results = rollback(conn, dry_run=args.dry_run)

            print(f"\n📊 결과:")
            print(f"   삭제된 테이블: {len(results['tables_dropped'])}")
            print(f"   없는 테이블: {len(results['tables_not_found'])}")

        else:
            print(f"{'🔍 마이그레이션 시뮬레이션' if args.dry_run else '🚀 마이그레이션 실행'}\n")
            results = migrate(conn, dry_run=args.dry_run)

            print(f"\n📊 결과:")
            print(f"   생성된 테이블: {len(results['tables_created'])}")
            print(f"   스킵된 테이블: {len(results['tables_skipped'])}")
            print(f"   생성된 인덱스: {len(results['indexes_created'])}")

            if results["data_inserted"]:
                print(f"   삽입된 데이터:")
                for data in results["data_inserted"]:
                    print(f"      - {data}")

    finally:
        conn.close()

    print("\n✨ 완료!")


if __name__ == "__main__":
    main()
