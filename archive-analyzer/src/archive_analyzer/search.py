"""MeiliSearch 기반 검색 모듈

archive.db 데이터를 MeiliSearch로 인덱싱하고 검색 기능을 제공합니다.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import meilisearch

    MEILISEARCH_AVAILABLE = True
except ImportError:
    MEILISEARCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """MeiliSearch 설정 (#28 - 환경변수 기반)"""

    host: str = field(default_factory=lambda: os.getenv("MEILISEARCH_URL", "http://localhost:7700"))
    api_key: str = field(default_factory=lambda: os.getenv("MEILISEARCH_API_KEY", ""))

    # 인덱스 이름
    files_index: str = "files"
    media_index: str = "media_info"
    clips_index: str = "clip_metadata"


@dataclass
class SearchResult:
    """검색 결과"""

    hits: List[Dict[str, Any]]
    total_hits: int
    processing_time_ms: int
    query: str


class SearchService:
    """MeiliSearch 검색 서비스"""

    def __init__(self, config: Optional[SearchConfig] = None):
        """
        Args:
            config: MeiliSearch 설정 (기본값 사용 시 None)
        """
        if not MEILISEARCH_AVAILABLE:
            raise ImportError("meilisearch 패키지가 설치되지 않았습니다. pip install meilisearch")

        self.config = config or SearchConfig()
        self.client = meilisearch.Client(self.config.host, self.config.api_key)
        self._setup_indexes()

    def _setup_indexes(self) -> None:
        """인덱스 초기 설정"""
        # files 인덱스
        files_index = self.client.index(self.config.files_index)
        files_index.update_settings(
            {
                "searchableAttributes": [
                    "filename",
                    "path",
                    "parent_folder",
                    "file_type",
                    "extension",
                ],
                "filterableAttributes": [
                    "file_type",
                    "extension",
                    "parent_folder",
                    "scan_status",
                ],
                "sortableAttributes": [
                    "size_bytes",
                    "modified_at",
                    "created_at",
                ],
                "displayedAttributes": [
                    "id",
                    "path",
                    "filename",
                    "extension",
                    "size_bytes",
                    "modified_at",
                    "file_type",
                    "parent_folder",
                    "scan_status",
                ],
            }
        )

        # media_info 인덱스
        media_index = self.client.index(self.config.media_index)
        media_index.update_settings(
            {
                "searchableAttributes": [
                    "file_path",
                    "video_codec",
                    "audio_codec",
                    "container_format",
                    "title",
                ],
                "filterableAttributes": [
                    "video_codec",
                    "audio_codec",
                    "has_video",
                    "has_audio",
                    "extraction_status",
                    "resolution_label",
                ],
                "sortableAttributes": [
                    "duration_seconds",
                    "width",
                    "height",
                    "bitrate",
                    "file_size",
                ],
            }
        )

        # clip_metadata 인덱스
        clips_index = self.client.index(self.config.clips_index)
        clips_index.update_settings(
            {
                "searchableAttributes": [
                    "title",
                    "description",
                    "players_tags",
                    "project_name",
                    "episode_event",
                    "tournament",
                    "hand_tag",
                ],
                "filterableAttributes": [
                    "project_name",
                    "year",
                    "location",
                    "hand_grade",
                    "is_badbeat",
                    "is_bluff",
                    "is_suckout",
                    "is_cooler",
                    "game_type",
                ],
                "sortableAttributes": [
                    "year",
                    "time_start_ms",
                    "match_confidence",
                ],
            }
        )

        logger.info("MeiliSearch 인덱스 설정 완료")

    # #41 - 청크 처리를 위한 배치 크기
    BATCH_SIZE = 1000

    def index_from_db(self, db_path: str) -> Dict[str, int]:
        """SQLite DB에서 데이터를 읽어 인덱싱 (#41 - 청크 처리로 OOM 방지)

        Args:
            db_path: archive.db 경로

        Returns:
            인덱싱된 문서 수 {index_name: count}
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = {}

        # files 테이블 인덱싱 (청크 처리)
        cursor.execute("SELECT * FROM files")
        files_count = 0
        while True:
            batch = cursor.fetchmany(self.BATCH_SIZE)
            if not batch:
                break
            docs = [dict(row) for row in batch]
            self.client.index(self.config.files_index).add_documents(docs, primary_key="id")
            files_count += len(docs)
        if files_count:
            results["files"] = files_count
            logger.info(f"files 인덱싱 완료: {files_count}건")

        # media_info 테이블 인덱싱 (청크 처리)
        cursor.execute(
            """
            SELECT
                m.*,
                CASE
                    WHEN m.height >= 2160 THEN '4K'
                    WHEN m.height >= 1440 THEN '1440p'
                    WHEN m.height >= 1080 THEN '1080p'
                    WHEN m.height >= 720 THEN '720p'
                    WHEN m.height >= 480 THEN '480p'
                    ELSE 'Other'
                END as resolution_label
            FROM media_info m
        """
        )
        media_count = 0
        while True:
            batch = cursor.fetchmany(self.BATCH_SIZE)
            if not batch:
                break
            docs = [dict(row) for row in batch]
            self.client.index(self.config.media_index).add_documents(docs, primary_key="id")
            media_count += len(docs)
        if media_count:
            results["media_info"] = media_count
            logger.info(f"media_info 인덱싱 완료: {media_count}건")

        # clip_metadata 테이블 인덱싱 (청크 처리)
        cursor.execute("SELECT * FROM clip_metadata")
        clips_count = 0
        while True:
            batch = cursor.fetchmany(self.BATCH_SIZE)
            if not batch:
                break
            docs = [dict(row) for row in batch]
            self.client.index(self.config.clips_index).add_documents(docs, primary_key="id")
            clips_count += len(docs)
        if clips_count:
            results["clip_metadata"] = clips_count
            logger.info(f"clip_metadata 인덱싱 완료: {clips_count}건")

        conn.close()
        return results

    def search_files(
        self,
        query: str,
        file_type: Optional[str] = None,
        extension: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        """파일 검색

        Args:
            query: 검색어
            file_type: 파일 유형 필터 (video, audio, subtitle 등)
            extension: 확장자 필터 (.mp4, .mkv 등)
            limit: 결과 수 제한
            offset: 시작 위치

        Returns:
            SearchResult 객체
        """
        filters = []
        if file_type:
            filters.append(f'file_type = "{file_type}"')
        if extension:
            filters.append(f'extension = "{extension}"')

        result = self.client.index(self.config.files_index).search(
            query,
            {
                "limit": limit,
                "offset": offset,
                "filter": " AND ".join(filters) if filters else None,
            },
        )

        return SearchResult(
            hits=result["hits"],
            total_hits=result.get("estimatedTotalHits", len(result["hits"])),
            processing_time_ms=result.get("processingTimeMs", 0),
            query=query,
        )

    def search_media(
        self,
        query: str,
        video_codec: Optional[str] = None,
        resolution: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        """미디어 정보 검색

        Args:
            query: 검색어
            video_codec: 비디오 코덱 필터 (h264, hevc 등)
            resolution: 해상도 라벨 필터 (4K, 1080p 등)
            limit: 결과 수 제한
            offset: 시작 위치

        Returns:
            SearchResult 객체
        """
        filters = []
        if video_codec:
            filters.append(f'video_codec = "{video_codec}"')
        if resolution:
            filters.append(f'resolution_label = "{resolution}"')

        result = self.client.index(self.config.media_index).search(
            query,
            {
                "limit": limit,
                "offset": offset,
                "filter": " AND ".join(filters) if filters else None,
            },
        )

        return SearchResult(
            hits=result["hits"],
            total_hits=result.get("estimatedTotalHits", len(result["hits"])),
            processing_time_ms=result.get("processingTimeMs", 0),
            query=query,
        )

    def search_clips(
        self,
        query: str,
        project_name: Optional[str] = None,
        hand_grade: Optional[str] = None,
        year: Optional[int] = None,
        is_bluff: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        """클립 메타데이터 검색

        Args:
            query: 검색어 (플레이어명, 이벤트명 등)
            project_name: 프로젝트명 필터 (WSOP, HCL 등)
            hand_grade: 핸드 등급 필터 (A, B, C 등)
            year: 연도 필터
            is_bluff: 블러프 여부 필터
            limit: 결과 수 제한
            offset: 시작 위치

        Returns:
            SearchResult 객체
        """
        filters = []
        if project_name:
            filters.append(f'project_name = "{project_name}"')
        if hand_grade:
            filters.append(f'hand_grade = "{hand_grade}"')
        if year:
            filters.append(f"year = {year}")
        if is_bluff is not None:
            filters.append(f"is_bluff = {1 if is_bluff else 0}")

        result = self.client.index(self.config.clips_index).search(
            query,
            {
                "limit": limit,
                "offset": offset,
                "filter": " AND ".join(filters) if filters else None,
            },
        )

        return SearchResult(
            hits=result["hits"],
            total_hits=result.get("estimatedTotalHits", len(result["hits"])),
            processing_time_ms=result.get("processingTimeMs", 0),
            query=query,
        )

    def get_stats(self) -> Dict[str, Any]:
        """인덱스 통계 조회"""
        stats = {}

        for index_name in [
            self.config.files_index,
            self.config.media_index,
            self.config.clips_index,
        ]:
            try:
                index = self.client.index(index_name)
                index_stats = index.get_stats()
                stats[index_name] = {
                    "numberOfDocuments": index_stats.get("numberOfDocuments", 0),
                    "isIndexing": index_stats.get("isIndexing", False),
                }
            except Exception as e:
                stats[index_name] = {"error": str(e)}

        return stats

    def clear_all(self) -> None:
        """모든 인덱스 삭제 (테스트용)"""
        for index_name in [
            self.config.files_index,
            self.config.media_index,
            self.config.clips_index,
        ]:
            try:
                self.client.index(index_name).delete_all_documents()
                logger.warning(f"인덱스 {index_name} 초기화됨")
            except Exception as e:
                logger.error(f"인덱스 {index_name} 초기화 실패: {e}")

    def health_check(self) -> bool:
        """MeiliSearch 서버 상태 확인"""
        try:
            health = self.client.health()
            return health.get("status") == "available"
        except Exception:
            return False


# 싱글톤 인스턴스
_search_service: Optional[SearchService] = None


def get_search_service(config: Optional[SearchConfig] = None) -> SearchService:
    """SearchService 싱글톤 반환"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService(config)
    return _search_service
