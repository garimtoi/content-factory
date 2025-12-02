#!/usr/bin/env python
"""
JSON 컬럼 정규화 마이그레이션 스크립트

hands.players, hands.tags JSON 컬럼을 정규화된 테이블로 분리합니다.

Usage:
    python scripts/migrate_json_normalization.py --dry-run  # 시뮬레이션
    python scripts/migrate_json_normalization.py            # 실행
    python scripts/migrate_json_normalization.py --rollback # 롤백
    python scripts/migrate_json_normalization.py --stats    # 통계
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 경로 설정
POKERVOD_DB = Path("D:/AI/claude01/qwen_hand_analysis/data/pokervod.db")

# 신규 테이블 DDL
TABLES = {
    "hand_players": """
        CREATE TABLE IF NOT EXISTS hand_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hand_id INTEGER NOT NULL,
            player_name VARCHAR(100) NOT NULL,
            position INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hand_id) REFERENCES hands(id) ON DELETE CASCADE
        )
    """,
    "hand_tags": """
        CREATE TABLE IF NOT EXISTS hand_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hand_id INTEGER NOT NULL,
            tag VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hand_id) REFERENCES hands(id) ON DELETE CASCADE,
            UNIQUE(hand_id, tag)
        )
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_hand_players_hand ON hand_players(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hand_players_player ON hand_players(player_name)",
    "CREATE INDEX IF NOT EXISTS idx_hand_tags_hand ON hand_tags(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hand_tags_tag ON hand_tags(tag)",
]


def get_connection():
    """DB 연결"""
    if not POKERVOD_DB.exists():
        print(f"❌ DB 파일 없음: {POKERVOD_DB}")
        sys.exit(1)
    conn = sqlite3.connect(POKERVOD_DB)
    conn.row_factory = sqlite3.Row
    return conn


def check_tables_exist(conn) -> dict:
    """테이블 존재 여부 확인"""
    cursor = conn.cursor()
    result = {}
    for table in TABLES.keys():
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        result[table] = cursor.fetchone() is not None
    return result


def create_tables(conn, dry_run: bool = False):
    """테이블 생성"""
    cursor = conn.cursor()

    for table_name, ddl in TABLES.items():
        if dry_run:
            print(f"  [DRY-RUN] CREATE TABLE {table_name}")
        else:
            cursor.execute(ddl)
            print(f"  ✅ Created table: {table_name}")

    for index_sql in INDEXES:
        if dry_run:
            index_name = index_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
            print(f"  [DRY-RUN] CREATE INDEX {index_name}")
        else:
            cursor.execute(index_sql)

    if not dry_run:
        conn.commit()
        print(f"  ✅ Created {len(INDEXES)} indexes")


def migrate_players(conn, dry_run: bool = False) -> int:
    """hands.players JSON → hand_players 테이블"""
    cursor = conn.cursor()

    # players가 있는 hands 조회
    cursor.execute("""
        SELECT id, players FROM hands
        WHERE players IS NOT NULL AND players != '' AND players != '[]'
    """)
    rows = cursor.fetchall()

    migrated = 0
    errors = 0

    for row in rows:
        hand_id = row["id"]
        players_json = row["players"]

        try:
            players = json.loads(players_json)
            if not isinstance(players, list):
                continue

            for position, player_name in enumerate(players, 1):
                if not player_name or not isinstance(player_name, str):
                    continue

                if dry_run:
                    print(f"    [DRY-RUN] hand_id={hand_id}, player={player_name}")
                else:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO hand_players (hand_id, player_name, position)
                            VALUES (?, ?, ?)
                        """, (hand_id, player_name.strip(), position))
                        migrated += 1
                    except sqlite3.IntegrityError:
                        pass  # 중복 무시

        except json.JSONDecodeError:
            errors += 1
            continue

    if not dry_run:
        conn.commit()

    return migrated


def migrate_tags(conn, dry_run: bool = False) -> int:
    """hands.tags JSON → hand_tags 테이블"""
    cursor = conn.cursor()

    # tags가 있는 hands 조회
    cursor.execute("""
        SELECT id, tags FROM hands
        WHERE tags IS NOT NULL AND tags != '' AND tags != '[]'
    """)
    rows = cursor.fetchall()

    migrated = 0
    errors = 0

    for row in rows:
        hand_id = row["id"]
        tags_json = row["tags"]

        try:
            tags = json.loads(tags_json)
            if not isinstance(tags, list):
                continue

            for tag in tags:
                if not tag or not isinstance(tag, str):
                    continue

                if dry_run:
                    print(f"    [DRY-RUN] hand_id={hand_id}, tag={tag}")
                else:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO hand_tags (hand_id, tag)
                            VALUES (?, ?)
                        """, (hand_id, tag.strip()))
                        migrated += 1
                    except sqlite3.IntegrityError:
                        pass  # 중복 무시

        except json.JSONDecodeError:
            errors += 1
            continue

    if not dry_run:
        conn.commit()

    return migrated


def rollback(conn, dry_run: bool = False):
    """롤백: 신규 테이블 삭제"""
    cursor = conn.cursor()

    for table_name in TABLES.keys():
        if dry_run:
            print(f"  [DRY-RUN] DROP TABLE {table_name}")
        else:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            print(f"  ✅ Dropped table: {table_name}")

    if not dry_run:
        conn.commit()


def show_stats(conn):
    """통계 출력"""
    cursor = conn.cursor()

    print("\n=== 마이그레이션 통계 ===\n")

    # hands 테이블 통계
    cursor.execute("SELECT COUNT(*) FROM hands")
    total_hands = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hands WHERE players IS NOT NULL AND players != '[]'")
    hands_with_players = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hands WHERE tags IS NOT NULL AND tags != '[]'")
    hands_with_tags = cursor.fetchone()[0]

    print(f"hands 테이블:")
    print(f"  총 핸드 수: {total_hands}")
    print(f"  players 있는 핸드: {hands_with_players}")
    print(f"  tags 있는 핸드: {hands_with_tags}")

    # 정규화 테이블 통계
    tables_exist = check_tables_exist(conn)

    if tables_exist.get("hand_players"):
        cursor.execute("SELECT COUNT(*) FROM hand_players")
        player_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT player_name) FROM hand_players")
        unique_players = cursor.fetchone()[0]

        print(f"\nhand_players 테이블:")
        print(f"  총 레코드 수: {player_count}")
        print(f"  고유 플레이어 수: {unique_players}")

        # 상위 플레이어
        cursor.execute("""
            SELECT player_name, COUNT(*) as cnt
            FROM hand_players
            GROUP BY player_name
            ORDER BY cnt DESC
            LIMIT 5
        """)
        print("  상위 5 플레이어:")
        for row in cursor.fetchall():
            print(f"    - {row[0]}: {row[1]}회")
    else:
        print("\nhand_players 테이블: 미생성")

    if tables_exist.get("hand_tags"):
        cursor.execute("SELECT COUNT(*) FROM hand_tags")
        tag_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT tag) FROM hand_tags")
        unique_tags = cursor.fetchone()[0]

        print(f"\nhand_tags 테이블:")
        print(f"  총 레코드 수: {tag_count}")
        print(f"  고유 태그 수: {unique_tags}")

        # 상위 태그
        cursor.execute("""
            SELECT tag, COUNT(*) as cnt
            FROM hand_tags
            GROUP BY tag
            ORDER BY cnt DESC
            LIMIT 5
        """)
        print("  상위 5 태그:")
        for row in cursor.fetchall():
            print(f"    - {row[0]}: {row[1]}회")
    else:
        print("\nhand_tags 테이블: 미생성")


def main():
    parser = argparse.ArgumentParser(description="JSON 컬럼 정규화 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="시뮬레이션 모드")
    parser.add_argument("--rollback", action="store_true", help="롤백 (테이블 삭제)")
    parser.add_argument("--stats", action="store_true", help="통계 출력")

    args = parser.parse_args()

    conn = get_connection()

    try:
        if args.stats:
            show_stats(conn)
            return

        if args.rollback:
            print("🔄 롤백 시작...")
            rollback(conn, dry_run=args.dry_run)
            print("✅ 롤백 완료")
            return

        print(f"🚀 JSON 정규화 마이그레이션 시작 (dry_run={args.dry_run})")
        print(f"   DB: {POKERVOD_DB}")
        print()

        # 1. 테이블 생성
        print("1️⃣ 테이블 생성")
        create_tables(conn, dry_run=args.dry_run)
        print()

        # 2. players 마이그레이션
        print("2️⃣ players 마이그레이션")
        player_count = migrate_players(conn, dry_run=args.dry_run)
        print(f"   → {player_count} records")
        print()

        # 3. tags 마이그레이션
        print("3️⃣ tags 마이그레이션")
        tag_count = migrate_tags(conn, dry_run=args.dry_run)
        print(f"   → {tag_count} records")
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
