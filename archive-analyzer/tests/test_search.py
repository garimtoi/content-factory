"""검색 모듈 테스트

MeiliSearch 검색 서비스 테스트입니다.
MeiliSearch 서버가 실행 중이지 않으면 일부 테스트는 건너뜁니다.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# MeiliSearch 가용성 확인
try:
    import meilisearch
    MEILISEARCH_AVAILABLE = True
except ImportError:
    MEILISEARCH_AVAILABLE = False


class TestSearchConfig:
    """SearchConfig 테스트"""

    def test_default_values(self):
        """기본값 확인 (#28 - 환경변수 기반)"""
        from archive_analyzer.search import SearchConfig
        import os

        config = SearchConfig()
        assert config.host == os.getenv("MEILISEARCH_URL", "http://localhost:7700")
        assert config.api_key == os.getenv("MEILISEARCH_API_KEY", "")
        assert config.files_index == "files"
        assert config.media_index == "media_info"
        assert config.clips_index == "clip_metadata"

    def test_custom_values(self):
        """커스텀 값 설정"""
        from archive_analyzer.search import SearchConfig

        config = SearchConfig(
            host="http://custom:8080",
            api_key="custom-key",
        )
        assert config.host == "http://custom:8080"
        assert config.api_key == "custom-key"


class TestSearchResult:
    """SearchResult 테스트"""

    def test_creation(self):
        """생성 확인"""
        from archive_analyzer.search import SearchResult

        result = SearchResult(
            hits=[{"id": 1, "path": "/test"}],
            total_hits=1,
            processing_time_ms=5,
            query="test",
        )
        assert len(result.hits) == 1
        assert result.total_hits == 1
        assert result.processing_time_ms == 5
        assert result.query == "test"


@pytest.fixture
def mock_meilisearch_client():
    """MeiliSearch 클라이언트 모킹"""
    with patch("archive_analyzer.search.meilisearch") as mock:
        mock_client = MagicMock()
        mock.Client.return_value = mock_client

        # 인덱스 모킹
        mock_index = MagicMock()
        mock_client.index.return_value = mock_index

        # 헬스체크 모킹
        mock_client.health.return_value = {"status": "available"}

        # 검색 결과 모킹
        mock_index.search.return_value = {
            "hits": [{"id": 1, "filename": "test.mp4"}],
            "estimatedTotalHits": 1,
            "processingTimeMs": 5,
        }

        yield mock_client


@pytest.fixture
def temp_db():
    """임시 테스트 DB 생성"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # files 테이블
    cursor.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            path TEXT,
            filename TEXT,
            extension TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            file_type TEXT,
            parent_folder TEXT,
            scan_status TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO files VALUES
        (1, '/test/video.mp4', 'video.mp4', '.mp4', 1000000, '2024-01-01', 'video', 'test', 'completed')
    """)

    # media_info 테이블
    cursor.execute("""
        CREATE TABLE media_info (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            video_codec TEXT,
            audio_codec TEXT,
            container_format TEXT,
            title TEXT,
            height INTEGER,
            width INTEGER,
            duration_seconds REAL,
            bitrate INTEGER,
            file_size INTEGER,
            has_video INTEGER,
            has_audio INTEGER,
            extraction_status TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO media_info VALUES
        (1, '/test/video.mp4', 'h264', 'aac', 'mp4', 'Test Video', 1080, 1920, 3600, 5000000, 1000000, 1, 1, 'completed')
    """)

    # clip_metadata 테이블
    cursor.execute("""
        CREATE TABLE clip_metadata (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            players_tags TEXT,
            project_name TEXT,
            episode_event TEXT,
            tournament TEXT,
            hand_tag TEXT,
            year INTEGER,
            location TEXT,
            hand_grade TEXT,
            is_badbeat INTEGER,
            is_bluff INTEGER,
            is_suckout INTEGER,
            is_cooler INTEGER,
            game_type TEXT,
            time_start_ms INTEGER,
            match_confidence REAL
        )
    """)
    cursor.execute("""
        INSERT INTO clip_metadata VALUES
        (1, 'Phil Ivey Bluff', 'Amazing bluff', 'Phil Ivey', 'WSOP', 'Main Event', 'WSOP 2024', 'AK', 2024, 'Las Vegas', 'A', 0, 1, 0, 0, 'NLHE', 0, 0.95)
    """)

    conn.commit()
    conn.close()

    yield db_path

    # 정리
    Path(db_path).unlink(missing_ok=True)


class TestSearchServiceMocked:
    """SearchService 모킹 테스트"""

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_initialization(self, mock_meilisearch_client):
        """초기화 테스트"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        assert service.client is not None

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_health_check_success(self, mock_meilisearch_client):
        """헬스체크 성공"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        assert service.health_check() is True

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_health_check_failure(self, mock_meilisearch_client):
        """헬스체크 실패"""
        from archive_analyzer.search import SearchService

        mock_meilisearch_client.health.side_effect = Exception("Connection failed")

        service = SearchService()
        assert service.health_check() is False

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_search_files(self, mock_meilisearch_client):
        """파일 검색"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        result = service.search_files("test")

        assert result.query == "test"
        assert len(result.hits) == 1
        assert result.hits[0]["filename"] == "test.mp4"

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_search_files_with_filter(self, mock_meilisearch_client):
        """필터 적용 파일 검색"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        service.search_files("test", file_type="video", extension=".mp4")

        # 필터가 적용되었는지 확인
        mock_meilisearch_client.index().search.assert_called()

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_index_from_db(self, mock_meilisearch_client, temp_db):
        """DB 인덱싱"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        results = service.index_from_db(temp_db)

        assert "files" in results
        assert results["files"] == 1
        assert "media_info" in results
        assert results["media_info"] == 1
        assert "clip_metadata" in results
        assert results["clip_metadata"] == 1

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_get_stats(self, mock_meilisearch_client):
        """통계 조회"""
        from archive_analyzer.search import SearchService

        mock_meilisearch_client.index().get_stats.return_value = {
            "numberOfDocuments": 100,
            "isIndexing": False,
        }

        service = SearchService()
        stats = service.get_stats()

        assert "files" in stats
        assert "media_info" in stats
        assert "clip_metadata" in stats

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_clear_all(self, mock_meilisearch_client):
        """인덱스 초기화"""
        from archive_analyzer.search import SearchService

        service = SearchService()
        service.clear_all()

        # delete_all_documents가 호출되었는지 확인
        assert mock_meilisearch_client.index().delete_all_documents.called


class TestSearchModule:
    """검색 모듈 레벨 테스트"""

    def test_meilisearch_availability_flag(self):
        """MEILISEARCH_AVAILABLE 플래그 확인"""
        from archive_analyzer.search import MEILISEARCH_AVAILABLE as flag
        # 플래그는 boolean이어야 함
        assert isinstance(flag, bool)

    @pytest.mark.skipif(MEILISEARCH_AVAILABLE, reason="meilisearch 미설치 상태에서만 테스트")
    def test_import_error_when_unavailable(self):
        """패키지 미설치 시 ImportError"""
        from archive_analyzer.search import SearchService

        with pytest.raises(ImportError):
            SearchService()

    @pytest.mark.skipif(not MEILISEARCH_AVAILABLE, reason="meilisearch 패키지 필요")
    def test_singleton_pattern(self, mock_meilisearch_client):
        """싱글톤 패턴 확인"""
        from archive_analyzer.search import get_search_service, _search_service
        import archive_analyzer.search as search_module

        # 싱글톤 초기화
        search_module._search_service = None

        service1 = get_search_service()
        service2 = get_search_service()

        assert service1 is service2
