"""Firestore 마이그레이션 모듈 테스트

Issue #59, #61: 웹 기반 마이그레이션 UI + Firestore 스키마
"""

import pytest
import sqlite3
import tempfile
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# firebase_admin 존재 여부 확인
try:
    import firebase_admin
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# 테스트 대상 함수들을 직접 정의 (scripts 폴더는 패키지가 아니므로)
def slugify(text: str) -> str:
    """문자열을 URL-friendly slug로 변환"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    text = text.strip('-')
    return text


class TestSlugify:
    """slugify 함수 테스트"""

    def test_basic_slugify(self):
        """기본 slugify"""
        assert slugify("Hello World") == "hello-world"
        assert slugify("WSOP 2024") == "wsop-2024"
        assert slugify("Phil Hellmuth") == "phil-hellmuth"

    def test_special_characters(self):
        """특수문자 처리"""
        assert slugify("Hello@World!") == "helloworld"
        assert slugify("Test#123$456") == "test123456"
        assert slugify("A & B") == "a-b"

    def test_multiple_spaces(self):
        """여러 공백 처리"""
        assert slugify("Hello   World") == "hello-world"
        assert slugify("  Test  ") == "test"

    def test_unicode_characters(self):
        """유니코드 문자"""
        # 한글은 제거됨 (알파벳+숫자만 유지)
        result = slugify("테스트 Test")
        assert "test" in result.lower()


@pytest.fixture
def temp_sqlite_db():
    """테스트용 임시 SQLite DB 생성"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # catalogs 테이블
    cursor.execute("""
        CREATE TABLE catalogs (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # series 테이블
    cursor.execute("""
        CREATE TABLE series (
            id INTEGER PRIMARY KEY,
            catalog_id VARCHAR(50),
            name VARCHAR(200),
            year INTEGER,
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # contents 테이블
    cursor.execute("""
        CREATE TABLE contents (
            id INTEGER PRIMARY KEY,
            series_id INTEGER,
            title VARCHAR(500),
            content_type VARCHAR(50) DEFAULT 'episode',
            file_id INTEGER,
            duration_sec FLOAT,
            view_count INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # content_players 테이블
    cursor.execute("""
        CREATE TABLE content_players (
            id INTEGER PRIMARY KEY,
            content_id INTEGER,
            player_id INTEGER,
            role VARCHAR(50)
        )
    """)

    # content_tags 테이블
    cursor.execute("""
        CREATE TABLE content_tags (
            id INTEGER PRIMARY KEY,
            content_id INTEGER,
            tag_id INTEGER
        )
    """)

    # files 테이블
    cursor.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            nas_path TEXT NOT NULL,
            filename VARCHAR(500),
            size_bytes BIGINT,
            duration_sec FLOAT,
            resolution VARCHAR(20),
            codec VARCHAR(50),
            analysis_status VARCHAR(20),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # players 테이블
    cursor.execute("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            display_name VARCHAR(200),
            country VARCHAR(100),
            created_at TIMESTAMP
        )
    """)

    # tags 테이블
    cursor.execute("""
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            created_at TIMESTAMP
        )
    """)

    # users 테이블
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(200),
            hashed_password TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP,
            last_login_at TIMESTAMP
        )
    """)

    # 테스트 데이터 삽입
    now = datetime.now().isoformat()

    # 카탈로그
    cursor.execute("""
        INSERT INTO catalogs (id, name, description, created_at, updated_at)
        VALUES ('wsop', 'World Series of Poker', 'WSOP 공식 영상', ?, ?)
    """, (now, now))

    # 시리즈
    cursor.execute("""
        INSERT INTO series (id, catalog_id, name, year, description, created_at, updated_at)
        VALUES (1, 'wsop', 'WSOP 2024 Main Event', 2024, 'Main Event Coverage', ?, ?)
    """, (now, now))

    # 플레이어
    cursor.execute("""
        INSERT INTO players (id, name, display_name, country, created_at)
        VALUES (1, 'Phil Hellmuth', 'Phil Hellmuth', 'USA', ?)
    """, (now,))
    cursor.execute("""
        INSERT INTO players (id, name, display_name, country, created_at)
        VALUES (2, 'Daniel Negreanu', 'Daniel Negreanu', 'Canada', ?)
    """, (now,))

    # 태그
    cursor.execute("""
        INSERT INTO tags (id, name, category, created_at)
        VALUES (1, 'bluff', 'action', ?)
    """, (now,))
    cursor.execute("""
        INSERT INTO tags (id, name, category, created_at)
        VALUES (2, 'all-in', 'action', ?)
    """, (now,))

    # 파일
    cursor.execute("""
        INSERT INTO files (id, nas_path, filename, size_bytes, duration_sec, resolution, codec, analysis_status, created_at, updated_at)
        VALUES (1, '//10.10.100.122/docker/WSOP/2024/day1.mp4', 'day1.mp4', 1073741824, 7200.0, '1920x1080', 'h264', 'completed', ?, ?)
    """, (now, now))

    # 콘텐츠
    cursor.execute("""
        INSERT INTO contents (id, series_id, title, content_type, file_id, duration_sec, view_count, created_at, updated_at)
        VALUES (1, 1, 'WSOP 2024 Main Event Day 1', 'episode', 1, 7200.0, 1500, ?, ?)
    """, (now, now))

    # content_players
    cursor.execute("""
        INSERT INTO content_players (id, content_id, player_id, role)
        VALUES (1, 1, 1, 'main')
    """)
    cursor.execute("""
        INSERT INTO content_players (id, content_id, player_id, role)
        VALUES (2, 1, 2, 'guest')
    """)

    # content_tags
    cursor.execute("""
        INSERT INTO content_tags (id, content_id, tag_id)
        VALUES (1, 1, 1)
    """)
    cursor.execute("""
        INSERT INTO content_tags (id, content_id, tag_id)
        VALUES (2, 1, 2)
    """)

    # 사용자
    cursor.execute("""
        INSERT INTO users (id, username, email, hashed_password, is_admin, is_active, created_at, last_login_at)
        VALUES (1, 'admin', 'admin@example.com', 'hashed_pw', 1, 1, ?, ?)
    """, (now, now))

    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink(missing_ok=True)


class TestSQLiteDataIntegrity:
    """SQLite 데이터 무결성 테스트"""

    def test_catalogs_data(self, temp_sqlite_db):
        """카탈로그 데이터 확인"""
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM catalogs")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT id, name FROM catalogs")
        row = cursor.fetchone()
        assert row[0] == "wsop"
        assert row[1] == "World Series of Poker"

        conn.close()

    def test_players_data(self, temp_sqlite_db):
        """플레이어 데이터 확인"""
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM players")
        assert cursor.fetchone()[0] == 2

        cursor.execute("SELECT name FROM players ORDER BY id")
        players = cursor.fetchall()
        assert players[0][0] == "Phil Hellmuth"
        assert players[1][0] == "Daniel Negreanu"

        conn.close()

    def test_content_players_relationship(self, temp_sqlite_db):
        """콘텐츠-플레이어 관계 확인"""
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.name, cp.role
            FROM content_players cp
            JOIN players p ON cp.player_id = p.id
            WHERE cp.content_id = 1
            ORDER BY cp.id
        """)
        results = cursor.fetchall()

        assert len(results) == 2
        assert results[0] == ("Phil Hellmuth", "main")
        assert results[1] == ("Daniel Negreanu", "guest")

        conn.close()

    def test_content_tags_relationship(self, temp_sqlite_db):
        """콘텐츠-태그 관계 확인"""
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.name, t.category
            FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            WHERE ct.content_id = 1
            ORDER BY ct.id
        """)
        results = cursor.fetchall()

        assert len(results) == 2
        assert results[0] == ("bluff", "action")
        assert results[1] == ("all-in", "action")

        conn.close()


class TestSecurityRulesValidation:
    """Security Rules 유효성 검사 (정적 분석)"""

    def test_rules_file_exists(self):
        """firestore.rules 파일 존재"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        assert rules_path.exists(), "firestore.rules 파일이 없습니다"

    def test_rules_has_version(self):
        """rules_version 선언"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        assert "rules_version = '2'" in content

    def test_rules_has_helper_functions(self):
        """헬퍼 함수 존재"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        assert "function isAuthenticated()" in content
        assert "function isAdmin()" in content
        assert "function isOwner(" in content
        assert "function isActiveUser()" in content

    def test_rules_has_public_collections(self):
        """공개 컬렉션 규칙"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        # catalogs, files, players, tags는 읽기 공개
        assert "match /catalogs/{catalogId}" in content
        assert "match /files/{fileId}" in content
        assert "match /players/{playerId}" in content
        assert "match /tags/{tagId}" in content

    def test_rules_has_user_collections(self):
        """사용자 컬렉션 규칙"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        assert "match /users/{userId}" in content
        assert "match /watchProgress/{progressId}" in content
        assert "match /searchHistory/{historyId}" in content

    def test_rules_has_migration_collections(self):
        """마이그레이션 컬렉션 규칙"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        assert "match /migrationJobs/{jobId}" in content
        assert "match /migrationLocks/{lockType}" in content

    def test_rules_default_deny(self):
        """기본 거부 규칙"""
        rules_path = Path(__file__).parent.parent / "firebase" / "firestore.rules"
        content = rules_path.read_text(encoding="utf-8")

        # 정의되지 않은 경로 거부
        assert "allow read, write: if false" in content


class TestIndexesValidation:
    """인덱스 설정 유효성 검사"""

    def test_indexes_file_exists(self):
        """firestore.indexes.json 파일 존재"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        assert indexes_path.exists(), "firestore.indexes.json 파일이 없습니다"

    def test_indexes_is_valid_json(self):
        """유효한 JSON"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        content = indexes_path.read_text(encoding="utf-8")

        data = json.loads(content)
        assert "indexes" in data
        assert "fieldOverrides" in data

    def test_indexes_has_collection_group(self):
        """Collection Group 인덱스 존재"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        data = json.loads(indexes_path.read_text(encoding="utf-8"))

        collection_group_indexes = [
            idx for idx in data["indexes"]
            if idx.get("queryScope") == "COLLECTION_GROUP"
        ]
        assert len(collection_group_indexes) >= 2, "Collection Group 인덱스가 부족합니다"

    def test_indexes_has_array_contains(self):
        """Array Contains 인덱스 존재"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        data = json.loads(indexes_path.read_text(encoding="utf-8"))

        array_overrides = [
            fo for fo in data["fieldOverrides"]
            if any(idx.get("arrayConfig") == "CONTAINS" for idx in fo.get("indexes", []))
        ]
        assert len(array_overrides) >= 2, "Array Contains 인덱스가 부족합니다 (players, tags)"

    def test_indexes_has_contents_indexes(self):
        """contents 컬렉션 인덱스"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        data = json.loads(indexes_path.read_text(encoding="utf-8"))

        contents_indexes = [
            idx for idx in data["indexes"]
            if idx.get("collectionGroup") == "contents"
        ]
        assert len(contents_indexes) >= 3, "contents 인덱스가 부족합니다"

    def test_indexes_has_migration_indexes(self):
        """migrationJobs 인덱스"""
        indexes_path = Path(__file__).parent.parent / "firebase" / "firestore.indexes.json"
        data = json.loads(indexes_path.read_text(encoding="utf-8"))

        migration_indexes = [
            idx for idx in data["indexes"]
            if idx.get("collectionGroup") == "migrationJobs"
        ]
        assert len(migration_indexes) >= 1, "migrationJobs 인덱스가 없습니다"


class TestMigrationScript:
    """마이그레이션 스크립트 존재 및 구조 테스트"""

    def test_script_exists(self):
        """migrate_to_firestore.py 파일 존재"""
        script_path = Path(__file__).parent.parent / "scripts" / "migrate_to_firestore.py"
        assert script_path.exists(), "migrate_to_firestore.py 파일이 없습니다"

    def test_script_has_required_classes(self):
        """필수 클래스 존재"""
        script_path = Path(__file__).parent.parent / "scripts" / "migrate_to_firestore.py"
        content = script_path.read_text(encoding="utf-8")

        assert "class MigrationStats" in content
        assert "class FirestoreMigrator" in content

    def test_script_has_required_methods(self):
        """필수 메서드 존재"""
        script_path = Path(__file__).parent.parent / "scripts" / "migrate_to_firestore.py"
        content = script_path.read_text(encoding="utf-8")

        # 마이그레이션 메서드
        assert "def migrate_catalogs" in content
        assert "def migrate_series" in content
        assert "def migrate_contents" in content
        assert "def migrate_files" in content
        assert "def migrate_players" in content
        assert "def migrate_tags" in content
        assert "def migrate_users" in content

    def test_script_has_dry_run_support(self):
        """dry-run 지원"""
        script_path = Path(__file__).parent.parent / "scripts" / "migrate_to_firestore.py"
        content = script_path.read_text(encoding="utf-8")

        assert "dry_run" in content
        assert "--dry-run" in content

    def test_script_has_cli_arguments(self):
        """CLI 인자 지원"""
        script_path = Path(__file__).parent.parent / "scripts" / "migrate_to_firestore.py"
        content = script_path.read_text(encoding="utf-8")

        assert "--db" in content  # SQLite DB 경로
        assert "--dry-run" in content
        assert "--collections" in content
        assert "--stats" in content
        assert "--batch-size" in content


@pytest.mark.skipif(not HAS_FIREBASE, reason="firebase_admin not installed")
class TestFirebaseIntegration:
    """Firebase 통합 테스트 (firebase_admin 설치 시에만 실행)"""

    def test_firebase_admin_import(self):
        """firebase_admin import 테스트"""
        import firebase_admin
        assert firebase_admin is not None

    def test_firestore_client_mock(self):
        """Firestore 클라이언트 모킹 테스트"""
        from unittest.mock import MagicMock, patch

        with patch("firebase_admin.initialize_app"):
            with patch("firebase_admin.firestore.client") as mock_client:
                mock_db = MagicMock()
                mock_client.return_value = mock_db

                # 컬렉션 접근 테스트
                mock_collection = MagicMock()
                mock_db.collection.return_value = mock_collection

                db = mock_client()
                collection = db.collection("test")

                mock_db.collection.assert_called_once_with("test")
