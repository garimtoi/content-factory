#!/usr/bin/env python3
"""V3.0 Video Card 스키마 마이그레이션

5단계 계층 구조를 3단계로 단순화:
- catalogs → series → contents

통합:
- subcatalogs + tournaments + events → series
- files + hands → contents (episode/clip)

Usage:
    python scripts/migrate_v3_schema.py --db-path data/output/archive.db
    python scripts/migrate_v3_schema.py --db-path data/output/archive.db --dry-run
"""

import argparse
import json
import logging
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# DDL: 새 테이블 생성
# =============================================================================

DDL_SERIES = """
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY,
    catalog_id INTEGER NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,

    -- 표시 정보
    title VARCHAR(300) NOT NULL,
    subtitle VARCHAR(200),
    description TEXT,

    -- 분류 정보
    year INTEGER,
    season INTEGER,
    location VARCHAR(100),
    event_type VARCHAR(50),

    -- 메타 정보
    thumbnail_url TEXT,
    banner_url TEXT,
    episode_count INTEGER DEFAULT 0,
    clip_count INTEGER DEFAULT 0,
    total_duration_sec FLOAT DEFAULT 0,

    -- 정렬/표시
    sort_order INTEGER DEFAULT 0,
    is_featured BOOLEAN DEFAULT FALSE,

    -- 레거시 매핑
    legacy_subcatalog_id TEXT,
    legacy_tournament_id TEXT,
    legacy_event_id TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (catalog_id) REFERENCES catalogs(id)
);
"""

DDL_SERIES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_series_catalog ON series(catalog_id);
CREATE INDEX IF NOT EXISTS idx_series_year ON series(year);
CREATE INDEX IF NOT EXISTS idx_series_featured ON series(is_featured);
CREATE INDEX IF NOT EXISTS idx_series_slug ON series(slug);
"""

DDL_CONTENTS = """
CREATE TABLE IF NOT EXISTS contents (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('episode', 'clip')),

    -- Video Card 핵심 필드
    headline VARCHAR(300) NOT NULL,
    subline VARCHAR(300),
    thumbnail_url TEXT,
    thumbnail_text VARCHAR(50),

    -- 미디어 정보
    duration_sec FLOAT,
    resolution VARCHAR(20),
    codec VARCHAR(50),

    -- 표시 요소
    featured_text VARCHAR(200),
    badges JSON,

    -- Episode 전용 필드
    episode_number INTEGER,
    hand_count INTEGER,

    -- Clip 전용 필드
    parent_episode_id INTEGER,
    start_sec FLOAT,
    end_sec FLOAT,
    winner VARCHAR(100),
    pot_size_bb FLOAT,
    action_type VARCHAR(50),

    -- 파일 참조
    nas_path TEXT UNIQUE,
    file_size_bytes BIGINT,

    -- 통계
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,

    -- 레거시 매핑
    legacy_file_id INTEGER,
    legacy_hand_id INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (series_id) REFERENCES series(id),
    FOREIGN KEY (parent_episode_id) REFERENCES contents(id)
);
"""

DDL_CONTENTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_contents_series ON contents(series_id);
CREATE INDEX IF NOT EXISTS idx_contents_type ON contents(content_type);
CREATE INDEX IF NOT EXISTS idx_contents_action ON contents(action_type);
CREATE INDEX IF NOT EXISTS idx_contents_winner ON contents(winner);
CREATE INDEX IF NOT EXISTS idx_contents_nas_path ON contents(nas_path);
"""

DDL_CONTENT_PLAYERS = """
CREATE TABLE IF NOT EXISTS content_players (
    content_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    role VARCHAR(50) DEFAULT 'participant',
    position INTEGER,
    PRIMARY KEY (content_id, player_id),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
"""

DDL_CONTENT_PLAYERS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_content_players_player ON content_players(player_id);
"""

DDL_CONTENT_TAGS = """
CREATE TABLE IF NOT EXISTS content_tags (
    content_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (content_id, tag_id),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""

DDL_CONTENT_TAGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_content_tags_tag ON content_tags(tag_id);
"""

DDL_TAGS = """
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_CATALOGS = """
CREATE TABLE IF NOT EXISTS catalogs (
    id INTEGER PRIMARY KEY,
    slug VARCHAR(50) UNIQUE,
    name VARCHAR(100) NOT NULL,
    display_title VARCHAR(200),
    logo_url TEXT,
    banner_url TEXT,
    series_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    country VARCHAR(50),
    total_hands INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# =============================================================================
# 호환성 뷰
# =============================================================================

VIEW_V_FILES = """
CREATE VIEW IF NOT EXISTS v_files AS
SELECT
    c.id,
    c.nas_path,
    c.headline AS display_title,
    c.duration_sec AS duration_seconds,
    c.file_size_bytes AS file_size,
    c.series_id,
    c.legacy_file_id AS original_file_id
FROM contents c
WHERE c.content_type = 'episode';
"""

VIEW_V_HANDS = """
CREATE VIEW IF NOT EXISTS v_hands AS
SELECT
    c.id,
    c.parent_episode_id AS file_id,
    c.headline AS display_title,
    c.winner,
    c.pot_size_bb AS pot_bb,
    c.action_type,
    c.start_sec AS timecode_start_seconds,
    c.end_sec AS timecode_end_seconds,
    c.legacy_hand_id AS original_hand_id,
    (
        SELECT GROUP_CONCAT(p.name, ', ')
        FROM content_players cp
        JOIN players p ON cp.player_id = p.id
        WHERE cp.content_id = c.id
    ) AS players
FROM contents c
WHERE c.content_type = 'clip';
"""


# =============================================================================
# Headline 생성 로직
# =============================================================================

HEADLINE_TEMPLATES = {
    "bluff": [
        "{winner}의 역대급 블러프",
        "{winner}, 에어로 {pot}BB 스틸",
    ],
    "hero_call": [
        "{winner}의 소름돋는 히어로콜",
        "{winner}, 블러프 간파하다",
    ],
    "bad_beat": [
        "{loser}의 악몽 같은 순간",
        "리버에서 무너진 {loser}",
    ],
    "cooler": [
        "쿨러 대결! {winner} vs {loser}",
        "피할 수 없는 운명의 대결",
    ],
    "all_in": [
        "{winner} vs {loser}, {pot}BB 올인 대결",
        "올인 쇼다운! 누가 승자인가",
    ],
    "final_hand": [
        "파이널 핸드! {winner} 우승 확정",
        "{winner}, 마지막 핸드에서 승리",
    ],
}


def generate_headline(
    winner: Optional[str] = None,
    loser: Optional[str] = None,
    pot_bb: Optional[float] = None,
    action_type: Optional[str] = None,
    hand_number: Optional[int] = None,
) -> str:
    """클립용 헤드라인 생성"""
    if action_type and action_type in HEADLINE_TEMPLATES:
        templates = HEADLINE_TEMPLATES[action_type]
        template = templates[0]  # 첫 번째 템플릿 사용
        return template.format(
            winner=winner or "Unknown",
            loser=loser or "Opponent",
            pot=int(pot_bb) if pot_bb else 0,
        )

    # 기본 헤드라인
    if winner:
        if pot_bb and pot_bb >= 100:
            return f"{winner}, {int(pot_bb)}BB 팟 승리"
        return f"{winner}의 승리"

    if hand_number:
        return f"Hand #{hand_number}"

    return "Poker Hand"


def generate_episode_headline(
    title: Optional[str] = None,
    year: Optional[int] = None,
    day: Optional[int] = None,
    event_type: Optional[str] = None,
) -> str:
    """에피소드용 헤드라인 생성"""
    if title:
        return title

    parts = []
    if event_type:
        parts.append(event_type.replace("_", " ").title())
    if year:
        parts.append(str(year))
    if day:
        parts.append(f"Day {day}")

    return " - ".join(parts) if parts else "Episode"


def generate_slug(text: str) -> str:
    """URL 친화적인 slug 생성"""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9가-힣\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:100]


# =============================================================================
# 마이그레이션 클래스
# =============================================================================


class V3SchemaMigration:
    """V3.0 스키마 마이그레이션 실행기"""

    def __init__(self, db_path: str, dry_run: bool = False):
        self.db_path = Path(db_path)
        self.dry_run = dry_run
        self.conn: Optional[sqlite3.Connection] = None
        self.stats = {
            "series_created": 0,
            "episodes_migrated": 0,
            "clips_migrated": 0,
            "content_players_created": 0,
            "content_tags_created": 0,
        }

    def connect(self):
        """데이터베이스 연결"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()

    def backup_database(self):
        """마이그레이션 전 백업 생성"""
        backup_path = self.db_path.with_suffix(
            f".v2-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        shutil.copy(self.db_path, backup_path)
        logger.info(f"백업 생성: {backup_path}")
        return backup_path

    def check_existing_tables(self) -> dict:
        """기존 테이블 존재 여부 확인"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        return {
            "catalogs": "catalogs" in tables,
            "subcatalogs": "subcatalogs" in tables,
            "tournaments": "tournaments" in tables,
            "events": "events" in tables,
            "files": "files" in tables,
            "hands": "hands" in tables,
            "players": "players" in tables,
            "series": "series" in tables,
            "contents": "contents" in tables,
        }

    def create_tables(self):
        """새 테이블 생성"""
        cursor = self.conn.cursor()

        logger.info("V3.0 테이블 생성 중...")

        # 기반 테이블 (의존성)
        cursor.executescript(DDL_CATALOGS)
        cursor.executescript(DDL_PLAYERS)
        cursor.executescript(DDL_TAGS)

        # series 테이블
        cursor.executescript(DDL_SERIES)
        cursor.executescript(DDL_SERIES_INDEXES)

        # contents 테이블
        cursor.executescript(DDL_CONTENTS)
        cursor.executescript(DDL_CONTENTS_INDEXES)

        # N:N 링크 테이블
        cursor.executescript(DDL_CONTENT_PLAYERS)
        cursor.executescript(DDL_CONTENT_PLAYERS_INDEX)
        cursor.executescript(DDL_CONTENT_TAGS)
        cursor.executescript(DDL_CONTENT_TAGS_INDEX)

        if not self.dry_run:
            self.conn.commit()

        logger.info("V3.0 테이블 생성 완료")

    def create_views(self):
        """호환성 뷰 생성"""
        cursor = self.conn.cursor()

        logger.info("호환성 뷰 생성 중...")

        # 기존 뷰 삭제
        cursor.execute("DROP VIEW IF EXISTS v_files")
        cursor.execute("DROP VIEW IF EXISTS v_hands")

        # 새 뷰 생성
        cursor.execute(VIEW_V_FILES)
        cursor.execute(VIEW_V_HANDS)

        if not self.dry_run:
            self.conn.commit()

        logger.info("호환성 뷰 생성 완료")

    def migrate_series(self):
        """subcatalogs + tournaments + events → series 마이그레이션"""
        cursor = self.conn.cursor()
        existing = self.check_existing_tables()

        logger.info("Series 마이그레이션 시작...")

        # 기존 tournaments 테이블에서 마이그레이션
        if existing.get("tournaments"):
            cursor.execute("""
                SELECT
                    t.id, t.catalog_id, t.name, t.year, t.location,
                    t.subcatalog_id, t.description, t.display_title
                FROM tournaments t
            """)
            tournaments = cursor.fetchall()

            for t in tournaments:
                slug = generate_slug(f"{t['name']}-{t['year'] or ''}")

                # 중복 체크
                cursor.execute("SELECT id FROM series WHERE slug = ?", (slug,))
                if cursor.fetchone():
                    slug = f"{slug}-{t['id']}"

                cursor.execute(
                    """
                    INSERT INTO series (
                        catalog_id, slug, title, subtitle, description,
                        year, location, event_type,
                        legacy_subcatalog_id, legacy_tournament_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        t["catalog_id"],
                        slug,
                        t["display_title"] or t["name"],
                        None,
                        t["description"],
                        t["year"],
                        t["location"],
                        "tournament",
                        t["subcatalog_id"],
                        t["id"],
                    ),
                )
                self.stats["series_created"] += 1

        # subcatalogs에서 tournament가 없는 경우 직접 마이그레이션
        elif existing.get("subcatalogs"):
            cursor.execute("""
                SELECT
                    s.id, s.catalog_id, s.name, s.display_title, s.description
                FROM subcatalogs s
            """)
            subcatalogs = cursor.fetchall()

            for s in subcatalogs:
                slug = generate_slug(s["name"])

                cursor.execute("SELECT id FROM series WHERE slug = ?", (slug,))
                if cursor.fetchone():
                    slug = f"{slug}-{s['id']}"

                # 연도 추출 시도
                year_match = re.search(r"(19|20)\d{2}", s["name"])
                year = int(year_match.group()) if year_match else None

                cursor.execute(
                    """
                    INSERT INTO series (
                        catalog_id, slug, title, description, year,
                        legacy_subcatalog_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s["catalog_id"],
                        slug,
                        s["display_title"] or s["name"],
                        s["description"],
                        year,
                        s["id"],
                    ),
                )
                self.stats["series_created"] += 1

        # 기본 series가 없으면 생성 (episode 마이그레이션용)
        cursor.execute("SELECT COUNT(*) FROM series")
        if cursor.fetchone()[0] == 0:
            # 기본 catalog 확인/생성
            cursor.execute("SELECT id FROM catalogs LIMIT 1")
            cat_row = cursor.fetchone()
            if cat_row:
                default_catalog_id = cat_row[0]
            else:
                cursor.execute(
                    "INSERT INTO catalogs (id, name) VALUES (1, 'Default')"
                )
                default_catalog_id = 1

            # 기본 series 생성
            cursor.execute(
                """
                INSERT INTO series (id, catalog_id, slug, title)
                VALUES (1, ?, 'default', 'Default Series')
                """,
                (default_catalog_id,),
            )
            self.stats["series_created"] += 1
            logger.info("기본 Series 생성됨 (id=1)")

        if not self.dry_run:
            self.conn.commit()

        logger.info(f"Series 마이그레이션 완료: {self.stats['series_created']}개 생성")

    def migrate_episodes(self):
        """files → contents (episode) 마이그레이션"""
        cursor = self.conn.cursor()
        existing = self.check_existing_tables()

        if not existing.get("files"):
            logger.warning("files 테이블이 없습니다. Episode 마이그레이션 건너뜀.")
            return

        logger.info("Episode 마이그레이션 시작...")

        # files 테이블 스키마 확인
        cursor.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in cursor.fetchall()}
        has_event_id = "event_id" in columns
        has_display_title = "display_title" in columns

        # 동적 쿼리 생성
        select_cols = ["f.id", "f.path", "f.filename", "f.size_bytes"]
        if has_event_id:
            select_cols.append("f.event_id")
        if has_display_title:
            select_cols.append("f.display_title")

        # media_info 조인
        query = f"""
            SELECT
                {', '.join(select_cols)},
                m.duration_seconds, m.width, m.height, m.video_codec
            FROM files f
            LEFT JOIN media_info m ON f.id = m.file_id
        """
        cursor.execute(query)
        files = cursor.fetchall()

        # 결과를 dict로 변환 (컬럼 이름으로 접근)
        col_names = [desc[0] for desc in cursor.description]

        for row in files:
            f = dict(zip(col_names, row))

            # series_id 찾기 (event_id 또는 기본값)
            series_id = 1  # 기본값

            if has_event_id and f.get("event_id"):
                # events → tournaments → series 매핑
                cursor.execute(
                    """
                    SELECT s.id FROM series s
                    WHERE s.legacy_tournament_id = (
                        SELECT tournament_id FROM events WHERE id = ?
                    )
                    """,
                    (f["event_id"],),
                )
                result = cursor.fetchone()
                if result:
                    series_id = result[0]

            # 해상도 라벨
            resolution = None
            height = f.get("height")
            if height:
                if height >= 2160:
                    resolution = "4K"
                elif height >= 1080:
                    resolution = "1080p"
                elif height >= 720:
                    resolution = "720p"
                else:
                    resolution = f"{height}p"

            display_title = f.get("display_title") if has_display_title else None
            headline = display_title or generate_episode_headline(
                title=f.get("filename", "Episode")
            )

            cursor.execute(
                """
                INSERT INTO contents (
                    series_id, content_type, headline, subline,
                    duration_sec, resolution, codec,
                    nas_path, file_size_bytes, legacy_file_id
                ) VALUES (?, 'episode', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    series_id,
                    headline,
                    None,  # subline
                    f.get("duration_seconds"),
                    resolution,
                    f.get("video_codec"),
                    f.get("path"),
                    f.get("size_bytes"),
                    f.get("id"),
                ),
            )
            self.stats["episodes_migrated"] += 1

        if not self.dry_run:
            self.conn.commit()

        logger.info(
            f"Episode 마이그레이션 완료: {self.stats['episodes_migrated']}개 생성"
        )

    def migrate_clips(self):
        """hands → contents (clip) 마이그레이션"""
        cursor = self.conn.cursor()
        existing = self.check_existing_tables()

        if not existing.get("hands"):
            logger.warning("hands 테이블이 없습니다. Clip 마이그레이션 건너뜀.")
            return

        logger.info("Clip 마이그레이션 시작...")

        cursor.execute("""
            SELECT
                h.id, h.file_id, h.winner, h.pot_bb, h.is_all_in,
                h.timecode_start_seconds, h.timecode_end_seconds,
                h.display_title, h.players, h.tags, h.hand_number
            FROM hands h
        """)
        hands = cursor.fetchall()

        for h in hands:
            # parent_episode_id 찾기
            parent_episode_id = None
            series_id = 1  # 기본값

            if h["file_id"]:
                cursor.execute(
                    """
                    SELECT id, series_id FROM contents
                    WHERE legacy_file_id = ? AND content_type = 'episode'
                    """,
                    (h["file_id"],),
                )
                row = cursor.fetchone()
                if row:
                    parent_episode_id = row[0]
                    series_id = row[1]

            # action_type 결정
            action_type = None
            if h["is_all_in"]:
                action_type = "all_in"

            headline = h["display_title"] or generate_headline(
                winner=h["winner"],
                pot_bb=h["pot_bb"],
                action_type=action_type,
                hand_number=h["hand_number"],
            )

            cursor.execute(
                """
                INSERT INTO contents (
                    series_id, content_type, headline, subline,
                    parent_episode_id, start_sec, end_sec,
                    winner, pot_size_bb, action_type,
                    legacy_hand_id
                ) VALUES (?, 'clip', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    series_id,
                    headline,
                    None,  # subline
                    parent_episode_id,
                    h["timecode_start_seconds"],
                    h["timecode_end_seconds"],
                    h["winner"],
                    h["pot_bb"],
                    action_type,
                    h["id"],
                ),
            )

            clip_id = cursor.lastrowid
            self.stats["clips_migrated"] += 1

            # players JSON → content_players 마이그레이션
            if h["players"]:
                self._migrate_players_for_content(cursor, clip_id, h["players"])

            # tags JSON → content_tags 마이그레이션
            if h["tags"]:
                self._migrate_tags_for_content(cursor, clip_id, h["tags"])

        if not self.dry_run:
            self.conn.commit()

        logger.info(f"Clip 마이그레이션 완료: {self.stats['clips_migrated']}개 생성")

    def _migrate_players_for_content(
        self, cursor: sqlite3.Cursor, content_id: int, players_json: str
    ):
        """플레이어 JSON을 content_players로 마이그레이션"""
        try:
            players = json.loads(players_json) if players_json else []
        except json.JSONDecodeError:
            players = [p.strip() for p in players_json.split(",") if p.strip()]

        for i, player_name in enumerate(players):
            if not player_name:
                continue

            # 플레이어 ID 찾기 또는 생성
            cursor.execute(
                "SELECT id FROM players WHERE name = ?", (player_name,)
            )
            row = cursor.fetchone()

            if row:
                player_id = row[0]
            else:
                cursor.execute(
                    "INSERT INTO players (name) VALUES (?)", (player_name,)
                )
                player_id = cursor.lastrowid

            # content_players에 삽입
            cursor.execute(
                """
                INSERT OR IGNORE INTO content_players (content_id, player_id, position)
                VALUES (?, ?, ?)
                """,
                (content_id, player_id, i),
            )
            self.stats["content_players_created"] += 1

    def _migrate_tags_for_content(
        self, cursor: sqlite3.Cursor, content_id: int, tags_json: str
    ):
        """태그 JSON을 content_tags로 마이그레이션"""
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = [t.strip() for t in tags_json.split(",") if t.strip()]

        for tag_name in tags:
            if not tag_name:
                continue

            # 태그 ID 찾기 또는 생성
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            row = cursor.fetchone()

            if row:
                tag_id = row[0]
            else:
                cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                tag_id = cursor.lastrowid

            # content_tags에 삽입
            cursor.execute(
                """
                INSERT OR IGNORE INTO content_tags (content_id, tag_id)
                VALUES (?, ?)
                """,
                (content_id, tag_id),
            )
            self.stats["content_tags_created"] += 1

    def update_series_counts(self):
        """series 테이블의 episode_count, clip_count 업데이트"""
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE series SET
                episode_count = (
                    SELECT COUNT(*) FROM contents
                    WHERE series_id = series.id AND content_type = 'episode'
                ),
                clip_count = (
                    SELECT COUNT(*) FROM contents
                    WHERE series_id = series.id AND content_type = 'clip'
                ),
                total_duration_sec = (
                    SELECT COALESCE(SUM(duration_sec), 0) FROM contents
                    WHERE series_id = series.id AND content_type = 'episode'
                )
        """)

        if not self.dry_run:
            self.conn.commit()

        logger.info("Series 카운트 업데이트 완료")

    def run(self):
        """전체 마이그레이션 실행"""
        logger.info(f"V3.0 스키마 마이그레이션 시작: {self.db_path}")
        logger.info(f"Dry run: {self.dry_run}")

        try:
            self.connect()

            # 1. 백업
            if not self.dry_run:
                self.backup_database()

            # 2. 테이블 생성
            self.create_tables()

            # 3. 데이터 마이그레이션
            self.migrate_series()
            self.migrate_episodes()
            self.migrate_clips()

            # 4. 카운트 업데이트
            self.update_series_counts()

            # 5. 호환성 뷰 생성
            self.create_views()

            # 결과 출력
            logger.info("=" * 50)
            logger.info("마이그레이션 완료!")
            logger.info(f"  - Series 생성: {self.stats['series_created']}")
            logger.info(f"  - Episodes 마이그레이션: {self.stats['episodes_migrated']}")
            logger.info(f"  - Clips 마이그레이션: {self.stats['clips_migrated']}")
            logger.info(
                f"  - Content-Players 링크: {self.stats['content_players_created']}"
            )
            logger.info(f"  - Content-Tags 링크: {self.stats['content_tags_created']}")
            logger.info("=" * 50)

            return self.stats

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="V3.0 스키마 마이그레이션")
    parser.add_argument(
        "--db-path",
        default="data/output/archive.db",
        help="데이터베이스 파일 경로",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 변경 없이 시뮬레이션만 실행",
    )
    args = parser.parse_args()

    migration = V3SchemaMigration(args.db_path, dry_run=args.dry_run)
    migration.run()


if __name__ == "__main__":
    main()
