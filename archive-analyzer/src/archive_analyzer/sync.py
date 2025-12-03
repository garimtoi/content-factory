"""pokervod.db 동기화 모듈

archive.db 데이터를 pokervod.db로 동기화합니다.

동기화 대상:
- files 테이블: 파일 메타데이터
- media_info → files: 코덱, 해상도, 재생시간 등

#21: 경로 정규화 유틸 통합
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils.path import generate_file_id, normalize_path

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """동기화 설정"""

    archive_db: str = "data/output/archive.db"
    pokervod_db: str = "d:/AI/claude01/qwen_hand_analysis/data/pokervod.db"

    # NAS 경로 변환
    nas_prefix: str = "//10.10.100.122/docker/GGPNAs/ARCHIVE"
    local_prefix: str = "Z:/GGPNAs/ARCHIVE"

    # 기본 분석 상태
    default_analysis_status: str = "pending"


@dataclass
class SyncResult:
    """동기화 결과"""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.skipped


# 다단계 카테고리 분류 패턴 (depth 1~3)
# 패턴: (regex, catalog_id, subcatalog_id, depth)
# depth=1: 최상위 서브카탈로그
# depth=2: 2단계 서브카탈로그
# depth=3: 3단계 서브카탈로그 (연도별)
MULTILEVEL_PATTERNS = [
    # WSOP-BR 하위 (depth=2~3)
    # 연도가 포함된 경로는 depth=3으로 분류
    (r"WSOP/WSOP-BR/WSOP-EUROPE/(\d{4})", "WSOP", "wsop-europe-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-PARADISE/(\d{4})", "WSOP", "wsop-paradise-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS/(\d{4})", "WSOP", "wsop-las-vegas-{year}", 3),
    # 연도 없으면 depth=2
    (r"WSOP/WSOP-BR/WSOP-EUROPE", "WSOP", "wsop-europe", 2),
    (r"WSOP/WSOP-BR/WSOP-PARADISE", "WSOP", "wsop-paradise", 2),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS", "WSOP", "wsop-las-vegas", 2),
    # WSOP-BR 자체 (depth=1)
    (r"WSOP/WSOP-BR", "WSOP", "wsop-br", 1),
    # WSOP Archive 하위 (depth=2~3)
    (r"WSOP/WSOP\s?ARCHIVE/(1973|19[789]\d|200[0-2])", "WSOP", "wsop-archive-1973-2002", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(200[3-9]|2010)", "WSOP", "wsop-archive-2003-2010", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(201[1-6])", "WSOP", "wsop-archive-2011-2016", 2),
    (r"WSOP/WSOP\s?ARCHIVE", "WSOP", "wsop-archive", 1),
    # WSOP Circuit/Super Circuit (depth=1)
    (r"WSOP/WSOP-C", "WSOP", "wsop-circuit", 1),
    (r"WSOP/WSOP-SC", "WSOP", "wsop-super-circuit", 1),
    # HCL (depth=1)
    (r"HCL/(\d{4})", "HCL", "hcl-{year}", 1),
    (r"HCL/.*[Cc]lip", "HCL", "hcl-clips", 1),
    (r"HCL/", "HCL", None, 0),
    # PAD (depth=1)
    (r"PAD/[Ss](?:eason\s?)?12", "PAD", "pad-s12", 1),
    (r"PAD/[Ss](?:eason\s?)?13", "PAD", "pad-s13", 1),
    (r"PAD/", "PAD", None, 0),
    # MPP (depth=1)
    (r"MPP/.*1\s?[Mm]", "MPP", "mpp-1m", 1),
    (r"MPP/.*2\s?[Mm]", "MPP", "mpp-2m", 1),
    (r"MPP/.*5\s?[Mm]", "MPP", "mpp-5m", 1),
    (r"MPP/", "MPP", None, 0),
    # GGMillions (depth=1)
    (r"GGMillions/", "GGMillions", "ggmillions-main", 1),
]

# 레거시 호환용 단순 패턴
CATEGORY_PATTERNS = [
    (r"WSOP/WSOP ARCHIVE", "WSOP", "wsop-archive"),
    (r"WSOP/WSOP-BR/WSOP-EUROPE", "WSOP", "wsop-europe"),
    (r"WSOP/WSOP-BR/WSOP-PARADISE", "WSOP", "wsop-paradise"),
    (r"WSOP/WSOP-BR/WSOP-LAS VEGAS", "WSOP", "wsop-las-vegas"),
    (r"WSOP/WSOP-C", "WSOP", "wsop-circuit"),
    (r"WSOP/WSOP-SC", "WSOP", "wsop-super-circuit"),
    (r"HCL/", "HCL", None),
    (r"PAD/", "PAD", None),
    (r"MPP/", "MPP", None),
    (r"GGMillions/", "GGMillions", None),
]


def classify_path(path: str) -> Tuple[str, Optional[str]]:
    """경로에서 카테고리/서브카테고리 추출 (레거시 호환)"""
    normalized = normalize_path(path)  # #21 - 유틸 사용
    for pattern, catalog, subcatalog in CATEGORY_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return catalog, subcatalog
    return "OTHER", None


@dataclass
class SubcatalogMatch:
    """다단계 서브카탈로그 매칭 결과"""

    catalog_id: str
    subcatalog_id: Optional[str]
    depth: int
    year: Optional[str] = None

    @property
    def full_subcatalog_id(self) -> Optional[str]:
        """연도가 포함된 전체 서브카탈로그 ID"""
        if self.subcatalog_id and self.year and "{year}" in self.subcatalog_id:
            return self.subcatalog_id.replace("{year}", self.year)
        return self.subcatalog_id


def classify_path_multilevel(path: str) -> SubcatalogMatch:
    """경로에서 다단계 서브카탈로그 정보 추출

    #37 - 가장 긴 매칭(가장 구체적인 패턴) 선택으로 패턴 순서 의존성 제거

    Args:
        path: 파일 경로

    Returns:
        SubcatalogMatch 객체 (catalog_id, subcatalog_id, depth, year)
    """
    normalized = normalize_path(path)  # #21 - 유틸 사용

    best_match = None
    best_match_length = 0
    best_result = None

    for pattern, catalog, subcatalog_template, depth in MULTILEVEL_PATTERNS:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            match_length = len(match.group(0))
            if match_length > best_match_length:
                best_match_length = match_length
                best_match = match
                best_result = (catalog, subcatalog_template, depth)

    if best_match and best_result:
        catalog, subcatalog_template, depth = best_result
        year = None
        # 연도 캡처 그룹이 있으면 추출
        if best_match.groups() and best_match.group(1).isdigit():
            year = best_match.group(1)

        return SubcatalogMatch(
            catalog_id=catalog,
            subcatalog_id=subcatalog_template,
            depth=depth,
            year=year,
        )

    return SubcatalogMatch(catalog_id="OTHER", subcatalog_id=None, depth=0)


def local_to_nas(local_path: str, config: SyncConfig) -> str:
    """로컬 경로를 NAS 경로로 변환"""
    normalized = local_path.replace("\\", "/")
    return normalized.replace(config.local_prefix, config.nas_prefix)


def format_resolution(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """해상도 문자열 생성"""
    if width and height:
        return f"{width}x{height}"
    return None


class SyncService:
    """pokervod.db 동기화 서비스"""

    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._validate_paths()
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """pokervod.db 인덱스 생성 (#40 - nas_path 인덱스 추가)"""
        try:
            conn = sqlite3.connect(self.config.pokervod_db)
            cursor = conn.cursor()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_nas_path ON files(nas_path)")
            conn.commit()
            conn.close()
            logger.debug("pokervod.db 인덱스 확인 완료")
        except Exception as e:
            logger.warning(f"인덱스 생성 실패: {e}")

    def _validate_paths(self) -> None:
        """DB 경로 유효성 검증"""
        archive_path = Path(self.config.archive_db)
        if not archive_path.exists():
            raise FileNotFoundError(f"archive.db를 찾을 수 없습니다: {archive_path}")

        pokervod_path = Path(self.config.pokervod_db)
        if not pokervod_path.exists():
            raise FileNotFoundError(f"pokervod.db를 찾을 수 없습니다: {pokervod_path}")

    def sync_files(self, dry_run: bool = False) -> SyncResult:
        """파일 정보 동기화

        archive.db의 files + media_info를 pokervod.db의 files로 동기화

        Args:
            dry_run: True면 실제 쓰기 없이 시뮬레이션

        Returns:
            SyncResult 객체
        """
        result = SyncResult()

        # 소스 DB 연결
        src_conn = sqlite3.connect(self.config.archive_db)
        src_conn.row_factory = sqlite3.Row

        # 대상 DB 연결
        dst_conn = sqlite3.connect(self.config.pokervod_db)
        dst_conn.row_factory = sqlite3.Row

        try:
            # archive.db에서 비디오 파일 조회 (media_info 조인)
            src_cursor = src_conn.cursor()
            src_cursor.execute(
                """
                SELECT
                    f.path,
                    f.filename,
                    f.size_bytes,
                    m.video_codec as codec,
                    m.width,
                    m.height,
                    m.duration_seconds,
                    m.framerate as fps,
                    m.bitrate as bitrate_kbps
                FROM files f
                LEFT JOIN media_info m ON f.id = m.file_id
                WHERE f.file_type = 'video'
            """
            )

            files = src_cursor.fetchall()
            logger.info(f"동기화 대상 파일: {len(files)}개")

            dst_cursor = dst_conn.cursor()

            for file_row in files:
                try:
                    # NAS 경로 변환
                    nas_path = local_to_nas(file_row["path"], self.config)
                    file_id = generate_file_id(nas_path)

                    # 해상도 문자열
                    resolution = format_resolution(file_row["width"], file_row["height"])

                    # 기존 레코드 확인
                    dst_cursor.execute(
                        "SELECT id, updated_at FROM files WHERE nas_path = ?", (nas_path,)
                    )
                    existing = dst_cursor.fetchone()

                    if existing:
                        # 업데이트
                        if not dry_run:
                            dst_cursor.execute(
                                """
                                UPDATE files SET
                                    size_bytes = ?,
                                    duration_sec = ?,
                                    resolution = ?,
                                    codec = ?,
                                    fps = ?,
                                    bitrate_kbps = ?,
                                    updated_at = ?
                                WHERE nas_path = ?
                            """,
                                (
                                    file_row["size_bytes"],
                                    file_row["duration_seconds"],
                                    resolution,
                                    file_row["codec"],
                                    file_row["fps"],
                                    file_row["bitrate_kbps"],
                                    datetime.now().isoformat(),
                                    nas_path,
                                ),
                            )
                        result.updated += 1
                    else:
                        # 새로 삽입
                        if not dry_run:
                            dst_cursor.execute(
                                """
                                INSERT INTO files (
                                    id, nas_path, filename, size_bytes,
                                    duration_sec, resolution, codec, fps, bitrate_kbps,
                                    analysis_status, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    file_id,
                                    nas_path,
                                    file_row["filename"],
                                    file_row["size_bytes"],
                                    file_row["duration_seconds"],
                                    resolution,
                                    file_row["codec"],
                                    file_row["fps"],
                                    file_row["bitrate_kbps"],
                                    self.config.default_analysis_status,
                                    datetime.now().isoformat(),
                                    datetime.now().isoformat(),
                                ),
                            )
                        result.inserted += 1

                except Exception as e:
                    result.errors.append(f"{file_row['path']}: {str(e)}")
                    logger.error(f"동기화 오류: {file_row['path']} - {e}")

            # 트랜잭션 커밋 (#33 - 롤백 로직 추가)
            if not dry_run:
                if (
                    len(result.errors) > 0
                    and len(result.errors) > (result.inserted + result.updated) * 0.5
                ):
                    # 에러가 50% 이상이면 롤백
                    logger.warning(f"에러율 높음 ({len(result.errors)}건), 롤백 실행")
                    dst_conn.rollback()
                    result.inserted = 0
                    result.updated = 0
                else:
                    dst_conn.commit()

            logger.info(
                f"동기화 완료: 삽입 {result.inserted}, "
                f"업데이트 {result.updated}, 오류 {len(result.errors)}"
            )

        except Exception as e:
            # 예상치 못한 오류 시 롤백
            logger.exception(f"동기화 중 치명적 오류 발생: {e}")
            try:
                dst_conn.rollback()
            except Exception:
                pass
            raise

        finally:
            src_conn.close()
            dst_conn.close()

        return result

    def sync_catalogs(self, dry_run: bool = False) -> SyncResult:
        """카탈로그 정보 자동 생성 (다단계 지원)

        파일 경로에서 카탈로그/서브카탈로그를 추출하여 동기화

        Args:
            dry_run: True면 실제 쓰기 없이 시뮬레이션

        Returns:
            SyncResult 객체
        """
        result = SyncResult()

        src_conn = sqlite3.connect(self.config.archive_db)
        src_conn.row_factory = sqlite3.Row

        dst_conn = sqlite3.connect(self.config.pokervod_db)
        dst_conn.row_factory = sqlite3.Row

        try:
            # 모든 파일 경로에서 카탈로그 추출 (다단계)
            src_cursor = src_conn.cursor()
            src_cursor.execute("SELECT DISTINCT path FROM files WHERE file_type = 'video'")

            # catalog_id -> {subcatalog_id: SubcatalogMatch}
            catalogs_found: Dict[str, Dict[str, SubcatalogMatch]] = {}

            for row in src_cursor.fetchall():
                match = classify_path_multilevel(row["path"])
                if match.catalog_id not in catalogs_found:
                    catalogs_found[match.catalog_id] = {}

                subcatalog_id = match.full_subcatalog_id
                if subcatalog_id and subcatalog_id not in catalogs_found[match.catalog_id]:
                    catalogs_found[match.catalog_id][subcatalog_id] = match

            dst_cursor = dst_conn.cursor()

            # 카탈로그 동기화
            for catalog_id, subcatalogs in catalogs_found.items():
                # 카탈로그 존재 확인
                dst_cursor.execute("SELECT id FROM catalogs WHERE id = ?", (catalog_id,))
                if not dst_cursor.fetchone():
                    if not dry_run:
                        dst_cursor.execute(
                            """
                            INSERT INTO catalogs (id, name, created_at, updated_at)
                            VALUES (?, ?, ?, ?)
                        """,
                            (
                                catalog_id,
                                catalog_id,  # name = id
                                datetime.now().isoformat(),
                                datetime.now().isoformat(),
                            ),
                        )
                    result.inserted += 1
                    logger.info(f"카탈로그 생성: {catalog_id}")

                # 다단계 서브카탈로그 동기화
                for subcatalog_id, match in subcatalogs.items():
                    dst_cursor.execute("SELECT id FROM subcatalogs WHERE id = ?", (subcatalog_id,))
                    if not dst_cursor.fetchone():
                        # 상위 서브카탈로그 ID 결정
                        parent_id = self._get_parent_subcatalog_id(match)

                        # 경로 생성
                        path = self._build_subcatalog_path(catalog_id, match)

                        if not dry_run:
                            dst_cursor.execute(
                                """
                                INSERT INTO subcatalogs (
                                    id, catalog_id, parent_id, name, depth, path,
                                    display_order, tournament_count, file_count,
                                    created_at, updated_at
                                )
                                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
                            """,
                                (
                                    subcatalog_id,
                                    catalog_id,
                                    parent_id,
                                    self._format_subcatalog_name(subcatalog_id, match),
                                    match.depth,
                                    path,
                                    datetime.now().isoformat(),
                                    datetime.now().isoformat(),
                                ),
                            )
                        result.inserted += 1
                        logger.info(
                            f"서브카탈로그 생성: {subcatalog_id} "
                            f"(depth={match.depth}, parent={parent_id})"
                        )

            # 트랜잭션 커밋 (#33 - 롤백 로직 추가)
            if not dry_run:
                dst_conn.commit()

            logger.info(f"카탈로그 동기화 완료: {result.inserted}건 생성")

        except Exception as e:
            logger.exception(f"카탈로그 동기화 중 치명적 오류: {e}")
            try:
                dst_conn.rollback()
            except Exception:
                pass
            raise

        finally:
            src_conn.close()
            dst_conn.close()

        return result

    def _get_parent_subcatalog_id(self, match: SubcatalogMatch) -> Optional[str]:
        """상위 서브카탈로그 ID 결정"""
        subcatalog_id = match.full_subcatalog_id
        if not subcatalog_id:
            return None

        # depth=1이면 상위 없음
        if match.depth <= 1:
            return None

        # depth=2: wsop-europe -> wsop-br, wsop-archive-2003-2010 -> wsop-archive
        if match.depth == 2:
            if subcatalog_id.startswith("wsop-archive-"):
                return "wsop-archive"
            if subcatalog_id in ("wsop-europe", "wsop-paradise", "wsop-las-vegas"):
                return "wsop-br"

        # depth=3: wsop-europe-2024 -> wsop-europe
        if match.depth == 3:
            # 연도 제거: wsop-europe-2024 -> wsop-europe
            if match.year:
                return subcatalog_id.replace(f"-{match.year}", "")

        return None

    def _build_subcatalog_path(self, catalog_id: str, match: SubcatalogMatch) -> Optional[str]:
        """서브카탈로그 전체 경로 생성"""
        subcatalog_id = match.full_subcatalog_id
        if not subcatalog_id:
            return None

        catalog_lower = catalog_id.lower()

        # 기본 경로
        if match.depth == 1:
            return f"{catalog_lower}/{subcatalog_id.replace(f'{catalog_lower}-', '')}"

        # depth=2
        parent_id = self._get_parent_subcatalog_id(match)
        if match.depth == 2 and parent_id:
            parent_suffix = parent_id.replace(f"{catalog_lower}-", "")
            current_suffix = subcatalog_id.replace(f"{catalog_lower}-", "")
            return f"{catalog_lower}/{parent_suffix}/{current_suffix}"

        # depth=3
        if match.depth == 3 and match.year:
            # wsop-europe-2024 -> wsop/wsop-br/wsop-europe/2024
            base_id = subcatalog_id.replace(f"-{match.year}", "")
            grandparent = self._get_parent_subcatalog_id(
                SubcatalogMatch(match.catalog_id, base_id, 2)
            )
            if grandparent:
                grandparent_suffix = grandparent.replace(f"{catalog_lower}-", "")
                base_suffix = base_id.replace(f"{catalog_lower}-", "")
                return f"{catalog_lower}/{grandparent_suffix}/{base_suffix}/{match.year}"

        return f"{catalog_lower}/{subcatalog_id}"

    def _format_subcatalog_name(self, subcatalog_id: str, match: SubcatalogMatch) -> str:
        """서브카탈로그 표시 이름 생성"""
        if match.year:
            # wsop-europe-2024 -> "2024 WSOP Europe"
            base_name = subcatalog_id.replace(f"-{match.year}", "")
            base_name = base_name.replace("-", " ").title()
            return f"{match.year} {base_name.upper()}"

        # wsop-archive -> "WSOP Archive"
        return subcatalog_id.replace("-", " ").title()

    def get_sync_stats(self) -> Dict[str, Any]:
        """동기화 통계 조회"""
        stats = {}

        # archive.db 통계
        src_conn = sqlite3.connect(self.config.archive_db)
        src_cursor = src_conn.cursor()

        src_cursor.execute("SELECT COUNT(*) FROM files WHERE file_type = 'video'")
        stats["archive_video_count"] = src_cursor.fetchone()[0]

        src_cursor.execute("SELECT COUNT(*) FROM media_info")
        stats["archive_media_info_count"] = src_cursor.fetchone()[0]

        src_conn.close()

        # pokervod.db 통계
        dst_conn = sqlite3.connect(self.config.pokervod_db)
        dst_cursor = dst_conn.cursor()

        dst_cursor.execute("SELECT COUNT(*) FROM files")
        stats["pokervod_file_count"] = dst_cursor.fetchone()[0]

        dst_cursor.execute("SELECT COUNT(*) FROM catalogs")
        stats["pokervod_catalog_count"] = dst_cursor.fetchone()[0]

        dst_cursor.execute("SELECT COUNT(*) FROM subcatalogs")
        stats["pokervod_subcatalog_count"] = dst_cursor.fetchone()[0]

        dst_conn.close()

        return stats

    def run_full_sync(self, dry_run: bool = False) -> Dict[str, SyncResult]:
        """전체 동기화 실행"""
        results = {}

        logger.info("=== 전체 동기화 시작 ===")

        # 1. 카탈로그 동기화
        logger.info("1. 카탈로그 동기화...")
        results["catalogs"] = self.sync_catalogs(dry_run)

        # 2. 파일 동기화
        logger.info("2. 파일 동기화...")
        results["files"] = self.sync_files(dry_run)

        logger.info("=== 동기화 완료 ===")

        return results


# 싱글톤 인스턴스
_sync_service: Optional[SyncService] = None


def get_sync_service(config: Optional[SyncConfig] = None) -> SyncService:
    """SyncService 싱글톤 반환"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService(config)
    return _sync_service
