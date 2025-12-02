#!/usr/bin/env python
"""
멀티 카탈로그 스키마 마이그레이션 스크립트

하나의 콘텐츠(file)가 여러 카탈로그에 속할 수 있도록 N:N 관계 테이블을 생성합니다.

Usage:
    python scripts/migrate_multi_catalog.py --dry-run   # 시뮬레이션
    python scripts/migrate_multi_catalog.py             # 실행
    python scripts/migrate_multi_catalog.py --rollback  # 롤백
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

POKERVOD_DB = Path("D:/AI/claude01/qwen_hand_analysis/data/pokervod.db")

# 신규 테이블 DDL
TABLES = {
    "file_catalogs": """
        CREATE TABLE IF NOT EXISTS file_catalogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id VARCHAR(200) NOT NULL,
            catalog_id VARCHAR(50) NOT NULL,
            subcatalog_id VARCHAR(100),
            is_primary BOOLEAN DEFAULT FALSE,
            display_order INTEGER DEFAULT 0,
            added_by VARCHAR(50) DEFAULT 'system',
            added_reason VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_id, catalog_id),
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (catalog_id) REFERENCES catalogs(id),
            FOREIGN KEY (subcatalog_id) REFERENCES subcatalogs(id)
        )
    """,
    "catalog_collections": """
        CREATE TABLE IF NOT EXISTS catalog_collections (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            collection_type VARCHAR(50) NOT NULL DEFAULT 'curated',
            cover_image_url TEXT,
            is_dynamic BOOLEAN DEFAULT FALSE,
            filter_query JSON,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_by VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "collection_items": """
        CREATE TABLE IF NOT EXISTS collection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id VARCHAR(100) NOT NULL,
            file_id VARCHAR(200) NOT NULL,
            display_order INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(collection_id, file_id),
            FOREIGN KEY (collection_id) REFERENCES catalog_collections(id),
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """,
}

INDEXES = {
    "file_catalogs": [
        "CREATE INDEX IF NOT EXISTS idx_file_catalogs_file ON file_catalogs(file_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_catalogs_catalog ON file_catalogs(catalog_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_catalogs_subcatalog ON file_catalogs(subcatalog_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_catalogs_primary ON file_catalogs(is_primary)",
    ],
    "collection_items": [
        "CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id)",
        "CREATE INDEX IF NOT EXISTS idx_collection_items_file ON collection_items(file_id)",
    ],
}

# 기본 컬렉션 데이터
DEFAULT_COLLECTIONS = [
    ("highlights", "베스트 핸드", "하이라이트 점수 3점 핸드 모음", "curated", None, False, None, 1, True, "system"),
    ("epic-hands", "역대급 핸드", "전설적인 핸드 컬렉션", "curated", None, False, None, 2, True, "system"),
    ("player-phil-ivey", "Phil Ivey", "Phil Ivey 등장 영상", "player", None, True, '{"player": "Phil Ivey"}', 10, True, "system"),
    ("player-tom-dwan", "Tom Dwan", "Tom Dwan 등장 영상", "player", None, True, '{"player": "Tom Dwan"}', 11, True, "system"),
    ("player-daniel-negreanu", "Daniel Negreanu", "Daniel Negreanu 등장 영상", "player", None, True, '{"player": "Daniel Negreanu"}', 12, True, "system"),
    ("tag-bluff", "블러프 명장면", "블러프 태그 핸드", "tag", None, True, '{"tag": "bluff"}', 20, True, "system"),
    ("tag-cooler", "쿨러 핸드", "쿨러/배드빗 상황", "tag", None, True, '{"tag": "cooler"}', 21, True, "system"),
    ("tag-allin", "올인 명승부", "프리플랍/멀티웨이 올인", "tag", None, True, '{"tags": ["preflop_allin", "multiway_allin"]}', 22, True, "system"),
    ("recent-week", "이번 주 업로드", "최근 7일 업로드 콘텐츠", "dynamic", None, True, '{"days": 7}', 30, True, "system"),
    ("most-viewed", "가장 많이 본 영상", "조회수 Top 100", "dynamic", None, True, '{"sort": "view_count", "limit": 100}', 31, True, "system"),
]


def get_existing_tables(conn: sqlite3.Connection) -> set:
    """기존 테이블 목록 조회"""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def migrate_existing_data(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """기존 파일들의 카탈로그 관계를 file_catalogs로 마이그레이션"""

    # 기존 계층 구조에서 file → catalog 관계 추출
    query = """
        SELECT DISTINCT
            f.id as file_id,
            c.id as catalog_id,
            s.id as subcatalog_id
        FROM files f
        JOIN events e ON f.event_id = e.id
        JOIN tournaments t ON e.tournament_id = t.id
        JOIN subcatalogs s ON t.subcatalog_id = s.id
        JOIN catalogs c ON s.catalog_id = c.id
        WHERE f.id IS NOT NULL AND c.id IS NOT NULL
    """

    cursor = conn.execute(query)
    rows = cursor.fetchall()

    if dry_run:
        return len(rows)

    # file_catalogs에 삽입 (is_primary=TRUE로 원본 관계 표시)
    conn.executemany(
        """
        INSERT OR IGNORE INTO file_catalogs
        (file_id, catalog_id, subcatalog_id, is_primary, added_by, added_reason)
        VALUES (?, ?, ?, TRUE, 'migration', 'Original catalog from hierarchy')
        """,
        rows
    )

    return len(rows)


def migrate(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """마이그레이션 실행"""
    results = {
        "tables_created": [],
        "tables_skipped": [],
        "indexes_created": [],
        "data_migrated": 0,
        "collections_created": 0,
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

    # 3. 기존 데이터 마이그레이션
    if "file_catalogs" in results["tables_created"]:
        count = migrate_existing_data(conn, dry_run)
        results["data_migrated"] = count
        if dry_run:
            print(f"🔍 file_catalogs: {count}개 기존 관계 마이그레이션 예정")
        else:
            print(f"✅ file_catalogs: {count}개 기존 관계 마이그레이션 완료")

    # 4. 기본 컬렉션 데이터 삽입
    if "catalog_collections" in results["tables_created"]:
        if dry_run:
            print(f"🔍 catalog_collections: {len(DEFAULT_COLLECTIONS)}개 기본 컬렉션 생성 예정")
        else:
            conn.executemany(
                """
                INSERT INTO catalog_collections
                (id, name, description, collection_type, cover_image_url,
                 is_dynamic, filter_query, display_order, is_active, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                DEFAULT_COLLECTIONS
            )
            print(f"✅ catalog_collections: {len(DEFAULT_COLLECTIONS)}개 기본 컬렉션 생성 완료")
        results["collections_created"] = len(DEFAULT_COLLECTIONS)

    if not dry_run:
        conn.commit()

    return results


def rollback(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """롤백 실행"""
    results = {"tables_dropped": [], "tables_not_found": []}
    existing_tables = get_existing_tables(conn)

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
    results = {"existing": [], "missing": [], "row_counts": {}, "sample_data": []}
    existing_tables = get_existing_tables(conn)

    for table_name in TABLES.keys():
        if table_name in existing_tables:
            results["existing"].append(table_name)
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            results["row_counts"][table_name] = count
        else:
            results["missing"].append(table_name)

    # 멀티 카탈로그 샘플 확인
    if "file_catalogs" in existing_tables:
        cursor = conn.execute("""
            SELECT fc.file_id, GROUP_CONCAT(fc.catalog_id, ', ') as catalogs, COUNT(*) as cnt
            FROM file_catalogs fc
            GROUP BY fc.file_id
            HAVING cnt > 1
            LIMIT 5
        """)
        results["sample_data"] = cursor.fetchall()

    return results


def show_stats(conn: sqlite3.Connection):
    """멀티 카탈로그 통계 출력"""
    print("\n📊 멀티 카탈로그 통계\n")

    # 카탈로그별 파일 수
    cursor = conn.execute("""
        SELECT catalog_id, COUNT(*) as cnt
        FROM file_catalogs
        GROUP BY catalog_id
        ORDER BY cnt DESC
    """)
    print("카탈로그별 파일 수:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]:,}개")

    print()

    # 멀티 카탈로그 파일 수
    cursor = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT file_id FROM file_catalogs GROUP BY file_id HAVING COUNT(*) > 1
        )
    """)
    multi_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT file_id) FROM file_catalogs")
    total_count = cursor.fetchone()[0]

    print(f"멀티 카탈로그 파일: {multi_count:,}개 / {total_count:,}개")

    # 컬렉션 통계
    cursor = conn.execute("""
        SELECT collection_type, COUNT(*)
        FROM catalog_collections
        GROUP BY collection_type
    """)
    print("\n컬렉션 유형별:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}개")


def main():
    parser = argparse.ArgumentParser(description="멀티 카탈로그 스키마 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="시뮬레이션 모드")
    parser.add_argument("--rollback", action="store_true", help="롤백 모드")
    parser.add_argument("--verify", action="store_true", help="검증 모드")
    parser.add_argument("--stats", action="store_true", help="통계 출력")
    parser.add_argument("--db-path", type=str, default=str(POKERVOD_DB), help="DB 경로")

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)

    print(f"📁 DB: {db_path}")
    print(f"📅 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    conn = sqlite3.connect(str(db_path))

    try:
        if args.stats:
            show_stats(conn)
        elif args.verify:
            print("🔍 마이그레이션 상태 검증\n")
            results = verify(conn)

            print(f"\n✅ 존재하는 테이블: {len(results['existing'])}/{len(TABLES)}")
            for table in results["existing"]:
                count = results["row_counts"].get(table, 0)
                print(f"   - {table}: {count:,} rows")

            if results["missing"]:
                print(f"\n❌ 누락된 테이블: {len(results['missing'])}")
                for table in results["missing"]:
                    print(f"   - {table}")

            if results["sample_data"]:
                print(f"\n🔗 멀티 카탈로그 파일 샘플:")
                for row in results["sample_data"]:
                    print(f"   - File {row[0]}: [{row[1]}] ({row[2]}개 카탈로그)")

        elif args.rollback:
            print(f"{'🔍 롤백 시뮬레이션' if args.dry_run else '🗑️  롤백 실행'}\n")
            results = rollback(conn, dry_run=args.dry_run)
            print(f"\n📊 결과:")
            print(f"   삭제된 테이블: {len(results['tables_dropped'])}")

        else:
            print(f"{'🔍 마이그레이션 시뮬레이션' if args.dry_run else '🚀 마이그레이션 실행'}\n")
            results = migrate(conn, dry_run=args.dry_run)

            print(f"\n📊 결과:")
            print(f"   생성된 테이블: {len(results['tables_created'])}")
            print(f"   스킵된 테이블: {len(results['tables_skipped'])}")
            print(f"   생성된 인덱스: {len(results['indexes_created'])}")
            print(f"   마이그레이션된 관계: {results['data_migrated']:,}개")
            print(f"   생성된 컬렉션: {results['collections_created']}개")

    finally:
        conn.close()

    print("\n✨ 완료!")


if __name__ == "__main__":
    main()
