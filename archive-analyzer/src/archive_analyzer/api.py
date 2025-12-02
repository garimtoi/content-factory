"""FastAPI 기반 검색 API

MeiliSearch를 통한 파일/미디어/클립 검색 REST API를 제공합니다.
인증은 NocoDB를 통해 별도로 관리됩니다.

실행:
    uvicorn archive_analyzer.api:app --reload --port 8000
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .search import (
    SearchService,
    SearchConfig,
    SearchResult,
    MEILISEARCH_AVAILABLE,
    get_search_service,
)

logger = logging.getLogger(__name__)

# 전역 서비스 인스턴스
_service: Optional[SearchService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    global _service
    if MEILISEARCH_AVAILABLE:
        try:
            _service = get_search_service()
            logger.info("MeiliSearch 서비스 초기화 완료")
        except Exception as e:
            logger.warning(f"MeiliSearch 초기화 실패: {e}")
    yield
    # 종료 시 정리


app = FastAPI(
    title="Archive Analyzer API",
    description="OTT 솔루션을 위한 미디어 아카이브 검색 API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Response Models
class SearchResponse(BaseModel):
    """검색 응답"""
    hits: list
    total_hits: int
    processing_time_ms: int
    query: str


class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str
    meilisearch: bool


class StatsResponse(BaseModel):
    """통계 응답"""
    indexes: dict


class IndexResponse(BaseModel):
    """인덱싱 응답"""
    success: bool
    indexed: dict
    message: str


# Helper functions
def get_service() -> SearchService:
    """SearchService 인스턴스 반환"""
    if _service is None:
        raise HTTPException(
            status_code=503,
            detail="MeiliSearch 서비스를 사용할 수 없습니다. 서버가 실행 중인지 확인하세요.",
        )
    return _service


def result_to_response(result: SearchResult) -> SearchResponse:
    """SearchResult를 API 응답으로 변환"""
    return SearchResponse(
        hits=result.hits,
        total_hits=result.total_hits,
        processing_time_ms=result.processing_time_ms,
        query=result.query,
    )


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 확인"""
    meilisearch_ok = False
    if _service:
        meilisearch_ok = _service.health_check()

    return HealthResponse(
        status="ok" if meilisearch_ok else "degraded",
        meilisearch=meilisearch_ok,
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """인덱스 통계 조회"""
    service = get_service()
    stats = service.get_stats()
    return StatsResponse(indexes=stats)


@app.post("/index", response_model=IndexResponse)
async def index_from_db(db_path: str = Query(..., description="archive.db 경로")):
    """DB에서 데이터 인덱싱"""
    service = get_service()

    try:
        results = service.index_from_db(db_path)
        return IndexResponse(
            success=True,
            indexed=results,
            message=f"인덱싱 완료: {sum(results.values())}건",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"DB 파일을 찾을 수 없습니다: {db_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"인덱싱 실패: {str(e)}")


@app.get("/search/files", response_model=SearchResponse)
async def search_files(
    q: str = Query(..., min_length=1, description="검색어"),
    file_type: Optional[str] = Query(None, description="파일 유형 (video, audio, subtitle 등)"),
    extension: Optional[str] = Query(None, description="확장자 (.mp4, .mkv 등)"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, description="시작 위치"),
):
    """파일 검색

    파일명, 경로, 폴더명으로 검색합니다.
    """
    service = get_service()
    result = service.search_files(
        query=q,
        file_type=file_type,
        extension=extension,
        limit=limit,
        offset=offset,
    )
    return result_to_response(result)


@app.get("/search/media", response_model=SearchResponse)
async def search_media(
    q: str = Query(..., min_length=1, description="검색어"),
    video_codec: Optional[str] = Query(None, description="비디오 코덱 (h264, hevc 등)"),
    resolution: Optional[str] = Query(None, description="해상도 (4K, 1080p, 720p 등)"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, description="시작 위치"),
):
    """미디어 정보 검색

    파일 경로, 코덱, 컨테이너 포맷으로 검색합니다.
    """
    service = get_service()
    result = service.search_media(
        query=q,
        video_codec=video_codec,
        resolution=resolution,
        limit=limit,
        offset=offset,
    )
    return result_to_response(result)


@app.get("/search/clips", response_model=SearchResponse)
async def search_clips(
    q: str = Query(..., min_length=1, description="검색어 (플레이어명, 이벤트명 등)"),
    project_name: Optional[str] = Query(None, description="프로젝트명 (WSOP, HCL 등)"),
    hand_grade: Optional[str] = Query(None, description="핸드 등급 (A, B, C 등)"),
    year: Optional[int] = Query(None, description="연도"),
    is_bluff: Optional[bool] = Query(None, description="블러프 여부"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, description="시작 위치"),
):
    """클립 메타데이터 검색

    플레이어, 토너먼트, 이벤트 등으로 검색합니다.
    """
    service = get_service()
    result = service.search_clips(
        query=q,
        project_name=project_name,
        hand_grade=hand_grade,
        year=year,
        is_bluff=is_bluff,
        limit=limit,
        offset=offset,
    )
    return result_to_response(result)


@app.delete("/clear")
async def clear_all():
    """모든 인덱스 초기화 (개발/테스트용)"""
    service = get_service()
    service.clear_all()
    return {"success": True, "message": "모든 인덱스가 초기화되었습니다."}


# =============================================
# Sync Endpoints (pokervod.db 동기화)
# =============================================

class SyncResultResponse(BaseModel):
    """동기화 결과 응답"""
    inserted: int
    updated: int
    skipped: int
    errors: list


class SyncStatsResponse(BaseModel):
    """동기화 통계 응답"""
    archive_video_count: int
    archive_media_info_count: int
    pokervod_file_count: int
    pokervod_catalog_count: int
    pokervod_subcatalog_count: int


class FullSyncResponse(BaseModel):
    """전체 동기화 응답"""
    success: bool
    catalogs: SyncResultResponse
    files: SyncResultResponse
    message: str


@app.get("/sync/stats", response_model=SyncStatsResponse)
async def get_sync_stats():
    """동기화 통계 조회

    archive.db와 pokervod.db의 현재 레코드 수를 비교합니다.
    """
    try:
        from .sync import SyncService
        sync_service = SyncService()
        stats = sync_service.get_sync_stats()
        return SyncStatsResponse(**stats)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@app.post("/sync/files", response_model=SyncResultResponse)
async def sync_files(
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """파일 동기화

    archive.db의 파일 정보를 pokervod.db로 동기화합니다.
    """
    try:
        from .sync import SyncService
        sync_service = SyncService()
        result = sync_service.sync_files(dry_run=dry_run)
        return SyncResultResponse(
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors[:20],  # 오류는 최대 20개만
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 동기화 실패: {str(e)}")


@app.post("/sync/catalogs", response_model=SyncResultResponse)
async def sync_catalogs(
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """카탈로그 동기화

    archive.db의 파일 경로에서 카탈로그를 추출하여 pokervod.db에 동기화합니다.
    """
    try:
        from .sync import SyncService
        sync_service = SyncService()
        result = sync_service.sync_catalogs(dry_run=dry_run)
        return SyncResultResponse(
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors[:20],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카탈로그 동기화 실패: {str(e)}")


@app.post("/sync/all", response_model=FullSyncResponse)
async def sync_all(
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """전체 동기화

    카탈로그와 파일을 순차적으로 동기화합니다.
    """
    try:
        from .sync import SyncService
        sync_service = SyncService()
        results = sync_service.run_full_sync(dry_run=dry_run)

        return FullSyncResponse(
            success=True,
            catalogs=SyncResultResponse(
                inserted=results["catalogs"].inserted,
                updated=results["catalogs"].updated,
                skipped=results["catalogs"].skipped,
                errors=results["catalogs"].errors[:20],
            ),
            files=SyncResultResponse(
                inserted=results["files"].inserted,
                updated=results["files"].updated,
                skipped=results["files"].skipped,
                errors=results["files"].errors[:20],
            ),
            message="동기화 완료" if not dry_run else "시뮬레이션 완료",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 동기화 실패: {str(e)}")


# 직접 실행 시
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
