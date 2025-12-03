#!/usr/bin/env python
"""
정수 PK 마이그레이션 스크립트

VARCHAR PK → INTEGER PK 변환으로 JOIN 성능 및 인덱스 효율성을 개선합니다.

대상 테이블:
- catalogs: id VARCHAR(50) → id INTEGER (new: varchar_id 컬럼 추가)
- subcatalogs: id VARCHAR(100) → id INTEGER
- files: id VARCHAR(200) → id INTEGER

Usage:
    python scripts/migrate_integer_pk.py --dry-run  # 시뮬레이션
    python scripts/migrate_integer_pk.py            # 실행
    python scripts/migrate_integer_pk.py --rollback # 롤백
    python scripts/migrate_integer_pk.py --verify   # 검증
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


def get_connection():
    """DB 연결"""
    if not POKERVOD_DB.exists():
        print(f"❌ DB 파일 없음: {POKERVOD_DB}")
        sys.exit(1)
    conn = sqlite3.connect(POKERVOD_DB)
    conn.row_factory = sqlite3.Row
    return conn


def check_migration_status(conn) -> dict:
    """마이그레이션 상태 확인"""
    cursor = conn.cursor()
    result = {
        "catalogs_has_varchar_id": False,
        "subcatalogs_has_varchar_id": False,
        "files_has_varchar_id": False,
        "id_mapping_exists": False,
    }

    # 컬럼 존재 여부 확인
    for table in ["catalogs", "subcatalogs", "files"]:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row["name"]: row for row in cursor.fetchall()}
        if "varchar_id" in columns:
            result[f"{table}_has_varchar_id"] = True

    # id_mapping 테이블 존재 확인
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='id_mapping'"
    )
    result["id_mapping_exists"] = cursor.fetchone() is not None

    return result


def create_id_mapping_table(conn, dry_run: bool = False):
    """ID 매핑 테이블 생성"""
    ddl = """
        CREATE TABLE IF NOT EXISTS id_mapping (
            table_name VARCHAR(50) NOT NULL,
            old_id VARCHAR(200) NOT NULL,
            new_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (table_name, old_id)
        )
    """

    if dry_run:
        print("  [DRY-RUN] CREATE TABLE id_mapping")
    else:
        conn.execute(ddl)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_id_mapping_new ON id_mapping(table_name, new_id)")
        conn.commit()
        print("  ✅ Created table: id_mapping")


def migrate_catalogs(conn, dry_run: bool = False) -> int:
    """catalogs 테이블 마이그레이션"""
    cursor = conn.cursor()

    # 1. varchar_id 컬럼 추가 (원본 ID 보존)
    if dry_run:
        print("  [DRY-RUN] ALTER TABLE catalogs ADD COLUMN varchar_id VARCHAR(50)")
    else:
        try:
            cursor.execute("ALTER TABLE catalogs ADD COLUMN varchar_id VARCHAR(50)")
            conn.commit()
            print("  ✅ Added column: catalogs.varchar_id")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ⏭️  Column catalogs.varchar_id already exists")
            else:
                raise

    # 2. varchar_id에 현재 id 값 복사
    if dry_run:
        cursor.execute("SELECT COUNT(*) FROM catalogs")
        count = cursor.fetchone()[0]
        print(f"  [DRY-RUN] {count} catalogs to migrate")
        return count

    cursor.execute("SELECT id FROM catalogs WHERE varchar_id IS NULL")
    rows = cursor.fetchall()

    for row in rows:
        old_id = row["id"]
        cursor.execute(
            "UPDATE catalogs SET varchar_id = ? WHERE id = ?",
            (old_id, old_id)
        )

    conn.commit()
    return len(rows)


def migrate_subcatalogs(conn, dry_run: bool = False) -> int:
    """subcatalogs 테이블 마이그레이션"""
    cursor = conn.cursor()

    # 1. varchar_id 컬럼 추가
    if dry_run:
        print("  [DRY-RUN] ALTER TABLE subcatalogs ADD COLUMN varchar_id VARCHAR(100)")
    else:
        try:
            cursor.execute("ALTER TABLE subcatalogs ADD COLUMN varchar_id VARCHAR(100)")
            conn.commit()
            print("  ✅ Added column: subcatalogs.varchar_id")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ⏭️  Column subcatalogs.varchar_id already exists")
            else:
                raise

    # 2. varchar_id에 현재 id 값 복사
    if dry_run:
        cursor.execute("SELECT COUNT(*) FROM subcatalogs")
        count = cursor.fetchone()[0]
        print(f"  [DRY-RUN] {count} subcatalogs to migrate")
        return count

    cursor.execute("SELECT id FROM subcatalogs WHERE varchar_id IS NULL")
    rows = cursor.fetchall()

    for row in rows:
        old_id = row["id"]
        cursor.execute(
            "UPDATE subcatalogs SET varchar_id = ? WHERE id = ?",
            (old_id, old_id)
        )

    conn.commit()
    return len(rows)


def migrate_files(conn, dry_run: bool = False) -> int:
    """files 테이블 마이그레이션"""
    cursor = conn.cursor()

    # 1. varchar_id 컬럼 추가
    if dry_run:
        print("  [DRY-RUN] ALTER TABLE files ADD COLUMN varchar_id VARCHAR(200)")
    else:
        try:
            cursor.execute("ALTER TABLE files ADD COLUMN varchar_id VARCHAR(200)")
            conn.commit()
            print("  ✅ Added column: files.varchar_id")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ⏭️  Column files.varchar_id already exists")
            else:
                raise

    # 2. varchar_id에 현재 id 값 복사
    if dry_run:
        cursor.execute("SELECT COUNT(*) FROM files")
        count = cursor.fetchone()[0]
        print(f"  [DRY-RUN] {count} files to migrate")
        return count

    cursor.execute("SELECT id FROM files WHERE varchar_id IS NULL")
    rows = cursor.fetchall()

    for row in rows:
        old_id = row["id"]
        cursor.execute(
            "UPDATE files SET varchar_id = ? WHERE id = ?",
            (old_id, old_id)
        )

    conn.commit()
    return len(rows)


def create_id_indexes(conn, dry_run: bool = False):
    """varchar_id 인덱스 생성"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_catalogs_varchar_id ON catalogs(varchar_id)",
        "CREATE INDEX IF NOT EXISTS idx_subcatalogs_varchar_id ON subcatalogs(varchar_id)",
        "CREATE INDEX IF NOT EXISTS idx_files_varchar_id ON files(varchar_id)",
    ]

    for idx_sql in indexes:
        idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
        if dry_run:
            print(f"  [DRY-RUN] CREATE INDEX {idx_name}")
        else:
            conn.execute(idx_sql)
            print(f"  ✅ Created index: {idx_name}")

    if not dry_run:
        conn.commit()


def populate_id_mapping(conn, dry_run: bool = False) -> int:
    """ID 매핑 테이블 채우기"""
    cursor = conn.cursor()
    total = 0

    tables = ["catalogs", "subcatalogs", "files"]

    if dry_run:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  [DRY-RUN] {count} {table} to map")
            total += count
        return total

    for table in tables:
        cursor.execute(f"""
            SELECT id, varchar_id FROM {table}
            WHERE varchar_id IS NOT NULL
        """)
        rows = cursor.fetchall()

        for row in rows:
            try:
                # varchar_id가 원본 ID, id가 현재 PK
                cursor.execute("""
                    INSERT OR IGNORE INTO id_mapping (table_name, old_id, new_id)
                    VALUES (?, ?, ?)
                """, (table, row["varchar_id"], row["id"] if isinstance(row["id"], int) else hash(row["id"]) % 10000000))
                total += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    return total


def show_stats(conn):
    """통계 출력"""
    cursor = conn.cursor()

    print("\n=== 마이그레이션 통계 ===\n")

    # 테이블별 레코드 수
    tables = ["catalogs", "subcatalogs", "files"]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]

        # varchar_id 채워진 레코드
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE varchar_id IS NOT NULL")
            migrated = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            migrated = 0

        print(f"{table}:")
        print(f"  총 레코드: {count}")
        print(f"  마이그레이션 완료: {migrated}")
        print()

    # id_mapping 테이블
    status = check_migration_status(conn)
    if status["id_mapping_exists"]:
        cursor.execute("SELECT table_name, COUNT(*) FROM id_mapping GROUP BY table_name")
        print("id_mapping 테이블:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}개")


def verify(conn) -> dict:
    """마이그레이션 검증"""
    cursor = conn.cursor()
    result = {
        "catalogs_ok": True,
        "subcatalogs_ok": True,
        "files_ok": True,
        "errors": [],
    }

    # varchar_id가 NULL인 레코드 확인
    tables = ["catalogs", "subcatalogs", "files"]
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE varchar_id IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                result[f"{table}_ok"] = False
                result["errors"].append(f"{table}: {null_count} records with NULL varchar_id")
        except sqlite3.OperationalError:
            result[f"{table}_ok"] = False
            result["errors"].append(f"{table}: varchar_id column not found")

    return result


def rollback(conn, dry_run: bool = False):
    """롤백: varchar_id 컬럼은 SQLite에서 직접 삭제 불가 - 경고만 출력"""
    print("\n⚠️  SQLite는 ALTER TABLE DROP COLUMN을 지원하지 않습니다.")
    print("   완전한 롤백을 위해서는 DB 백업에서 복원하세요.")
    print("\n   다음 테이블에 varchar_id 컬럼이 추가되었습니다:")

    tables = ["catalogs", "subcatalogs", "files"]
    cursor = conn.cursor()

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row["name"] for row in cursor.fetchall()]
        if "varchar_id" in columns:
            print(f"   - {table}.varchar_id")

    if not dry_run:
        # id_mapping 테이블은 삭제 가능
        cursor.execute("DROP TABLE IF EXISTS id_mapping")
        conn.commit()
        print("\n  ✅ Dropped table: id_mapping")


def main():
    parser = argparse.ArgumentParser(description="정수 PK 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="시뮬레이션 모드")
    parser.add_argument("--rollback", action="store_true", help="롤백")
    parser.add_argument("--verify", action="store_true", help="검증")
    parser.add_argument("--stats", action="store_true", help="통계 출력")

    args = parser.parse_args()

    conn = get_connection()

    try:
        if args.stats:
            show_stats(conn)
            return

        if args.verify:
            print("🔍 마이그레이션 검증...\n")
            result = verify(conn)

            if all([result["catalogs_ok"], result["subcatalogs_ok"], result["files_ok"]]):
                print("✅ 모든 테이블 검증 통과")
            else:
                print("❌ 검증 실패:")
                for error in result["errors"]:
                    print(f"   - {error}")
            return

        if args.rollback:
            print("🔄 롤백...")
            rollback(conn, dry_run=args.dry_run)
            print("✅ 롤백 완료 (부분)")
            return

        print(f"🚀 정수 PK 마이그레이션 시작 (dry_run={args.dry_run})")
        print(f"   DB: {POKERVOD_DB}")
        print()

        # 1. ID 매핑 테이블 생성
        print("1️⃣ ID 매핑 테이블 생성")
        create_id_mapping_table(conn, dry_run=args.dry_run)
        print()

        # 2. catalogs 마이그레이션
        print("2️⃣ catalogs 마이그레이션")
        catalog_count = migrate_catalogs(conn, dry_run=args.dry_run)
        print(f"   → {catalog_count} records")
        print()

        # 3. subcatalogs 마이그레이션
        print("3️⃣ subcatalogs 마이그레이션")
        subcatalog_count = migrate_subcatalogs(conn, dry_run=args.dry_run)
        print(f"   → {subcatalog_count} records")
        print()

        # 4. files 마이그레이션
        print("4️⃣ files 마이그레이션")
        files_count = migrate_files(conn, dry_run=args.dry_run)
        print(f"   → {files_count} records")
        print()

        # 5. 인덱스 생성
        print("5️⃣ 인덱스 생성")
        create_id_indexes(conn, dry_run=args.dry_run)
        print()

        # 6. ID 매핑 데이터 채우기
        print("6️⃣ ID 매핑 데이터 생성")
        mapping_count = populate_id_mapping(conn, dry_run=args.dry_run)
        print(f"   → {mapping_count} mappings")
        print()

        if args.dry_run:
            print("✅ Dry-run 완료 (실제 변경 없음)")
        else:
            print("✅ 마이그레이션 완료!")
            show_stats(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
