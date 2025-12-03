"""FastAPI 기반 검색 API

MeiliSearch를 통한 파일/미디어/클립 검색 REST API를 제공합니다.

실행:
    uvicorn archive_analyzer.api:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False

from .search import (
    MEILISEARCH_AVAILABLE,
    SearchResult,
    SearchService,
    get_search_service,
)

# 환경 변수 기반 설정
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://10.10.100.74:8000"
).split(",")

API_KEY = os.getenv("ARCHIVE_API_KEY", "")

# 허용된 DB 경로 (Path Traversal 방지)
ALLOWED_DB_DIR = Path(os.getenv("ALLOWED_DB_DIR", "D:/AI/claude01/archive-analyzer/data/output"))

MAX_OFFSET = 10000  # offset 상한

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

# Rate Limiting 설정 (#29)
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    limiter = None
    logger.warning("slowapi not installed - rate limiting disabled")

# CORS 설정 (#26 - 특정 Origin만 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


# API Key 인증 (#19 - 위험한 엔드포인트 보호)
async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """API Key 검증 (환경변수 ARCHIVE_API_KEY 설정 필요)"""
    if not API_KEY:
        # API Key 미설정 시 개발 모드로 간주 (경고만 출력)
        logger.warning("ARCHIVE_API_KEY not set - running in development mode")
        return None
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def sanitize_string(value: str) -> str:
    """XSS 방지를 위한 문자열 이스케이프"""
    return escape(value) if value else value


def sanitize_result(data: dict) -> dict:
    """검색 결과 XSS 방지 (#30)"""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_result(value)
        elif isinstance(value, list):
            sanitized[key] = [
                (
                    sanitize_result(item)
                    if isinstance(item, dict)
                    else sanitize_string(item) if isinstance(item, str) else item
                )
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def validate_db_path(db_path: str) -> Path:
    """DB 경로 검증 (#27 - Path Traversal 방지)"""
    try:
        resolved = Path(db_path).resolve()
        # 허용된 디렉토리 내인지 확인
        if not str(resolved).startswith(str(ALLOWED_DB_DIR.resolve())):
            raise HTTPException(403, "허용되지 않은 경로입니다")
        # .db 확장자 확인
        if resolved.suffix.lower() != ".db":
            raise HTTPException(400, "DB 파일(.db)만 허용됩니다")
        # 파일 존재 확인
        if not resolved.exists():
            raise HTTPException(404, "요청한 파일을 찾을 수 없습니다")
        return resolved
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "유효하지 않은 경로입니다")


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
    """SearchResult를 API 응답으로 변환 (XSS 방지 포함)"""
    sanitized_hits = [sanitize_result(hit) for hit in result.hits]
    return SearchResponse(
        hits=sanitized_hits,
        total_hits=result.total_hits,
        processing_time_ms=result.processing_time_ms,
        query=sanitize_string(result.query),
    )


# Rate limit decorator helper
def rate_limit(limit_string: str):
    """Rate limit 데코레이터 (slowapi 미설치 시 무시)"""
    if SLOWAPI_AVAILABLE and limiter:
        return limiter.limit(limit_string)
    return lambda f: f  # no-op decorator


# Endpoints
@app.get("/health", response_model=HealthResponse)
@rate_limit("120/minute")
async def health_check(request: Request):
    """서버 상태 확인"""
    meilisearch_ok = False
    if _service:
        meilisearch_ok = _service.health_check()

    return HealthResponse(
        status="ok" if meilisearch_ok else "degraded",
        meilisearch=meilisearch_ok,
    )


@app.get("/stats", response_model=StatsResponse)
@rate_limit("120/minute")
async def get_stats(request: Request):
    """인덱스 통계 조회"""
    service = get_service()
    stats = service.get_stats()
    return StatsResponse(indexes=stats)


@app.post("/index", response_model=IndexResponse, dependencies=[Depends(verify_api_key)])
@rate_limit("10/minute")
async def index_from_db(request: Request, db_path: str = Query(..., description="archive.db 경로")):
    """DB에서 데이터 인덱싱 (API Key 필요)"""
    service = get_service()

    # 경로 검증 (#27)
    validated_path = validate_db_path(db_path)

    try:
        results = service.index_from_db(str(validated_path))
        return IndexResponse(
            success=True,
            indexed=results,
            message=f"인덱싱 완료: {sum(results.values())}건",
        )
    except Exception:
        logger.exception("Indexing failed")  # 상세 로그는 서버에만
        raise HTTPException(status_code=500, detail="인덱싱 중 오류가 발생했습니다")


@app.get("/search/files", response_model=SearchResponse)
@rate_limit("60/minute")
async def search_files(
    request: Request,
    q: str = Query(..., min_length=1, description="검색어"),
    file_type: Optional[str] = Query(None, description="파일 유형 (video, audio, subtitle 등)"),
    extension: Optional[str] = Query(None, description="확장자 (.mp4, .mkv 등)"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="시작 위치"),
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
@rate_limit("60/minute")
async def search_media(
    request: Request,
    q: str = Query(..., min_length=1, description="검색어"),
    video_codec: Optional[str] = Query(None, description="비디오 코덱 (h264, hevc 등)"),
    resolution: Optional[str] = Query(None, description="해상도 (4K, 1080p, 720p 등)"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="시작 위치"),
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
@rate_limit("60/minute")
async def search_clips(
    request: Request,
    q: str = Query(..., min_length=1, description="검색어 (플레이어명, 이벤트명 등)"),
    project_name: Optional[str] = Query(None, description="프로젝트명 (WSOP, HCL 등)"),
    hand_grade: Optional[str] = Query(None, description="핸드 등급 (A, B, C 등)"),
    year: Optional[int] = Query(None, description="연도"),
    is_bluff: Optional[bool] = Query(None, description="블러프 여부"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="시작 위치"),
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


@app.delete("/clear", dependencies=[Depends(verify_api_key)])
@rate_limit("5/minute")
async def clear_all(request: Request):
    """모든 인덱스 초기화 (API Key 필요, 개발/테스트용)"""
    service = get_service()
    service.clear_all()
    logger.warning("All indexes cleared by API request")
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
@rate_limit("60/minute")
async def get_sync_stats(request: Request):
    """동기화 통계 조회

    archive.db와 pokervod.db의 현재 레코드 수를 비교합니다.
    """
    try:
        from .sync import SyncService

        sync_service = SyncService()
        stats = sync_service.get_sync_stats()
        return SyncStatsResponse(**stats)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="필요한 파일을 찾을 수 없습니다")
    except Exception:
        logger.exception("Stats query failed")
        raise HTTPException(status_code=500, detail="통계 조회 중 오류가 발생했습니다")


@app.post("/sync/files", response_model=SyncResultResponse, dependencies=[Depends(verify_api_key)])
@rate_limit("10/minute")
async def sync_files(
    request: Request,
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """파일 동기화 (API Key 필요)

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
            errors=result.errors[:20],
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="필요한 파일을 찾을 수 없습니다")
    except Exception:
        logger.exception("File sync failed")
        raise HTTPException(status_code=500, detail="파일 동기화 중 오류가 발생했습니다")


@app.post(
    "/sync/catalogs", response_model=SyncResultResponse, dependencies=[Depends(verify_api_key)]
)
@rate_limit("10/minute")
async def sync_catalogs(
    request: Request,
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """카탈로그 동기화 (API Key 필요)

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
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="필요한 파일을 찾을 수 없습니다")
    except Exception:
        logger.exception("Catalog sync failed")
        raise HTTPException(status_code=500, detail="카탈로그 동기화 중 오류가 발생했습니다")


@app.post("/sync/all", response_model=FullSyncResponse, dependencies=[Depends(verify_api_key)])
@rate_limit("5/minute")
async def sync_all(
    request: Request,
    dry_run: bool = Query(False, description="실제 쓰기 없이 시뮬레이션"),
):
    """전체 동기화 (API Key 필요)

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
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="필요한 파일을 찾을 수 없습니다")
    except Exception:
        logger.exception("Full sync failed")
        raise HTTPException(status_code=500, detail="전체 동기화 중 오류가 발생했습니다")


# 직접 실행 시
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
