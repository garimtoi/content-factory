"""상세 스캔 리포트 생성 모듈

Issue #11: 상세 스캔 리포트 생성기 구현 (FR-005)
- 파일 유형별 통계
- 비디오 해상도/코덱/컨테이너 분석
- 폴더 구조 분석
- 스트리밍 적합성 평가
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


@dataclass
class FileTypeStats:
    """파일 유형별 통계"""

    file_type: str
    count: int = 0
    total_size: int = 0
    percentage: float = 0.0
    extensions: Dict[str, int] = field(default_factory=dict)

    @property
    def size_gb(self) -> float:
        return self.total_size / (1024**3)

    @property
    def size_formatted(self) -> str:
        if self.total_size >= 1024**4:
            return f"{self.total_size / (1024 ** 4):.2f} TB"
        elif self.total_size >= 1024**3:
            return f"{self.total_size / (1024 ** 3):.2f} GB"
        elif self.total_size >= 1024**2:
            return f"{self.total_size / (1024 ** 2):.2f} MB"
        else:
            return f"{self.total_size / 1024:.2f} KB"


@dataclass
class ResolutionStats:
    """해상도별 통계"""

    resolution: str
    count: int = 0
    percentage: float = 0.0
    total_size: int = 0
    avg_bitrate: float = 0.0


@dataclass
class CodecStats:
    """코덱별 통계"""

    codec: str
    count: int = 0
    percentage: float = 0.0


@dataclass
class ContainerStats:
    """컨테이너 포맷별 통계"""

    container: str
    count: int = 0
    percentage: float = 0.0
    total_size: int = 0


@dataclass
class FolderStats:
    """폴더별 통계"""

    folder: str
    file_count: int = 0
    total_size: int = 0
    video_count: int = 0
    depth: int = 0  # 폴더 깊이
    relative_path: str = ""  # 아카이브 기준 상대 경로

    @property
    def size_formatted(self) -> str:
        if self.total_size >= 1024**4:
            return f"{self.total_size / (1024 ** 4):.2f} TB"
        elif self.total_size >= 1024**3:
            return f"{self.total_size / (1024 ** 3):.2f} GB"
        elif self.total_size >= 1024**2:
            return f"{self.total_size / (1024 ** 2):.2f} MB"
        else:
            return f"{self.total_size / 1024:.2f} KB"

    @property
    def folder_name(self) -> str:
        """폴더 이름만 추출"""
        parts = self.folder.replace("\\", "/").rstrip("/").split("/")
        return parts[-1] if parts else self.folder


@dataclass
class FolderTreeNode:
    """폴더 트리 노드"""

    name: str
    full_path: str
    file_count: int = 0
    total_size: int = 0
    video_count: int = 0
    children: Dict[str, "FolderTreeNode"] = field(default_factory=dict)
    depth: int = 0

    @property
    def size_formatted(self) -> str:
        if self.total_size >= 1024**4:
            return f"{self.total_size / (1024 ** 4):.2f} TB"
        elif self.total_size >= 1024**3:
            return f"{self.total_size / (1024 ** 3):.2f} GB"
        elif self.total_size >= 1024**2:
            return f"{self.total_size / (1024 ** 2):.2f} MB"
        else:
            return f"{self.total_size / 1024:.2f} KB"


@dataclass
class DurationStats:
    """재생시간별 통계"""

    category: str  # short (<30min), medium (30-90min), long (>90min)
    count: int = 0
    percentage: float = 0.0
    total_duration_hours: float = 0.0


@dataclass
class BitrateStats:
    """비트레이트별 통계"""

    range_label: str  # "< 5 Mbps", "5-10 Mbps", "10-20 Mbps", "> 20 Mbps"
    count: int = 0
    percentage: float = 0.0


@dataclass
class StreamingCompatibility:
    """스트리밍 적합성 평가"""

    compatible_count: int = 0
    incompatible_count: int = 0
    needs_transcode: int = 0
    compatibility_rate: float = 0.0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class QualityIssues:
    """품질 이슈 목록"""

    failed_extraction: List[Dict[str, Any]] = field(default_factory=list)
    missing_video: List[Dict[str, Any]] = field(default_factory=list)
    missing_audio: List[Dict[str, Any]] = field(default_factory=list)
    unusual_format: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ArchiveReport:
    """아카이브 분석 리포트"""

    # 기본 정보
    report_date: str = ""
    archive_path: str = ""
    scan_duration_seconds: float = 0.0

    # 전체 요약
    total_files: int = 0
    total_size: int = 0
    total_videos: int = 0
    total_duration_hours: float = 0.0

    # 상세 통계
    file_type_stats: List[FileTypeStats] = field(default_factory=list)
    resolution_stats: List[ResolutionStats] = field(default_factory=list)
    codec_stats: List[CodecStats] = field(default_factory=list)
    container_stats: List[ContainerStats] = field(default_factory=list)
    folder_stats: List[FolderStats] = field(default_factory=list)
    duration_stats: List[DurationStats] = field(default_factory=list)
    bitrate_stats: List[BitrateStats] = field(default_factory=list)

    # 스트리밍 평가
    streaming_compatibility: Optional[StreamingCompatibility] = None

    # 품질 이슈
    quality_issues: Optional[QualityIssues] = None

    # 추가 정보
    extension_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    folder_tree: Optional[FolderTreeNode] = None  # 폴더 트리 구조

    @property
    def total_size_formatted(self) -> str:
        if self.total_size >= 1024**4:
            return f"{self.total_size / (1024 ** 4):.2f} TB"
        elif self.total_size >= 1024**3:
            return f"{self.total_size / (1024 ** 3):.2f} GB"
        else:
            return f"{self.total_size / (1024 ** 2):.2f} MB"

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        result = {
            "report_date": self.report_date,
            "archive_path": self.archive_path,
            "summary": {
                "total_files": self.total_files,
                "total_size": self.total_size,
                "total_size_formatted": self.total_size_formatted,
                "total_videos": self.total_videos,
                "total_duration_hours": round(self.total_duration_hours, 2),
            },
            "file_type_stats": [asdict(s) for s in self.file_type_stats],
            "resolution_stats": [asdict(s) for s in self.resolution_stats],
            "codec_stats": [asdict(s) for s in self.codec_stats],
            "container_stats": [asdict(s) for s in self.container_stats],
            "folder_stats": [asdict(s) for s in self.folder_stats],
            "duration_stats": [asdict(s) for s in self.duration_stats],
            "bitrate_stats": [asdict(s) for s in self.bitrate_stats],
            "extension_breakdown": self.extension_breakdown,
        }

        if self.streaming_compatibility:
            result["streaming_compatibility"] = asdict(self.streaming_compatibility)

        if self.quality_issues:
            result["quality_issues"] = asdict(self.quality_issues)

        return result


class ReportGenerator:
    """스캔 리포트 생성기"""

    # OTT 스트리밍 호환 코덱
    STREAMING_COMPATIBLE_VIDEO_CODECS = {"h264", "hevc", "h265", "vp9", "av1"}
    STREAMING_COMPATIBLE_AUDIO_CODECS = {"aac", "mp3", "opus", "ac3", "eac3"}
    STREAMING_COMPATIBLE_CONTAINERS = {"mp4", "webm", "mov"}

    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self._conn = db._get_connection()

    def generate(self, archive_path: str = "") -> ArchiveReport:
        """전체 리포트 생성

        Args:
            archive_path: 아카이브 경로 (표시용)

        Returns:
            ArchiveReport 객체
        """
        report = ArchiveReport(
            report_date=datetime.now().isoformat(),
            archive_path=archive_path,
        )

        # 기본 통계
        self._gather_summary(report)

        # 파일 유형별 통계
        self._gather_file_type_stats(report)

        # 확장자별 상세 분석
        self._gather_extension_breakdown(report)

        # 비디오 분석 (메타데이터 있는 경우)
        self._gather_resolution_stats(report)
        self._gather_codec_stats(report)
        self._gather_container_stats(report)
        self._gather_duration_stats(report)
        self._gather_bitrate_stats(report)

        # 폴더별 통계
        self._gather_folder_stats(report)

        # 스트리밍 적합성
        self._evaluate_streaming_compatibility(report)

        # 품질 이슈
        self._gather_quality_issues(report)

        return report

    def _gather_summary(self, report: ArchiveReport) -> None:
        """전체 요약 수집"""
        cursor = self._conn.cursor()

        # 전체 파일 수, 용량
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM files")
        row = cursor.fetchone()
        report.total_files = row[0]
        report.total_size = row[1]

        # 비디오 파일 수
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_type = 'video'")
        report.total_videos = cursor.fetchone()[0]

        # 총 재생시간
        cursor.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) / 3600.0
            FROM media_info
            WHERE extraction_status = 'success'
        """
        )
        report.total_duration_hours = cursor.fetchone()[0] or 0

    def _gather_file_type_stats(self, report: ArchiveReport) -> None:
        """파일 유형별 통계 수집 (#44 - N+1 쿼리 최적화)"""
        cursor = self._conn.cursor()

        # 파일 타입별 기본 통계
        cursor.execute(
            """
            SELECT
                file_type,
                COUNT(*) as count,
                COALESCE(SUM(size_bytes), 0) as total_size
            FROM files
            GROUP BY file_type
            ORDER BY total_size DESC
        """
        )

        type_rows = cursor.fetchall()

        # #44 - 단일 쿼리로 모든 확장자 통계 가져오기
        cursor.execute(
            """
            SELECT file_type, extension, COUNT(*) as count
            FROM files
            GROUP BY file_type, extension
            ORDER BY file_type, count DESC
        """
        )

        # 확장자별 통계를 file_type으로 그룹화
        ext_by_type = {}
        for ext_row in cursor.fetchall():
            ftype = ext_row[0] or "unknown"
            if ftype not in ext_by_type:
                ext_by_type[ftype] = {}
            ext_by_type[ftype][ext_row[1] or "none"] = ext_row[2]

        stats_list = []
        for row in type_rows:
            file_type = row[0] or "unknown"
            count = row[1]
            size = row[2]

            percentage = (count / report.total_files * 100) if report.total_files > 0 else 0

            stats = FileTypeStats(
                file_type=file_type,
                count=count,
                total_size=size,
                percentage=round(percentage, 1),
            )

            # 미리 가져온 확장자 통계 사용
            stats.extensions = ext_by_type.get(file_type, {})

            stats_list.append(stats)

        report.file_type_stats = stats_list

    def _gather_extension_breakdown(self, report: ArchiveReport) -> None:
        """확장자별 상세 분석"""
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT
                extension,
                file_type,
                COUNT(*) as count,
                COALESCE(SUM(size_bytes), 0) as total_size,
                AVG(size_bytes) as avg_size
            FROM files
            GROUP BY extension
            ORDER BY total_size DESC
        """
        )

        breakdown = {}
        for row in cursor.fetchall():
            ext = row[0] or "none"
            breakdown[ext] = {
                "file_type": row[1],
                "count": row[2],
                "total_size": row[3],
                "avg_size": row[4],
                "size_formatted": self._format_size(row[3]),
            }

        report.extension_breakdown = breakdown

    def _gather_resolution_stats(self, report: ArchiveReport) -> None:
        """해상도별 통계 수집"""
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT
                CASE
                    WHEN height >= 2160 THEN '4K (2160p+)'
                    WHEN height >= 1440 THEN '1440p (QHD)'
                    WHEN height >= 1080 THEN '1080p (FHD)'
                    WHEN height >= 720 THEN '720p (HD)'
                    WHEN height >= 480 THEN '480p (SD)'
                    WHEN height > 0 THEN 'Other (<480p)'
                    ELSE 'Unknown'
                END as resolution,
                COUNT(*) as count,
                COALESCE(SUM(f.size_bytes), 0) as total_size,
                AVG(m.bitrate) as avg_bitrate
            FROM media_info m
            LEFT JOIN files f ON m.file_id = f.id
            WHERE m.extraction_status = 'success'
            GROUP BY resolution
            ORDER BY
                CASE resolution
                    WHEN '4K (2160p+)' THEN 1
                    WHEN '1440p (QHD)' THEN 2
                    WHEN '1080p (FHD)' THEN 3
                    WHEN '720p (HD)' THEN 4
                    WHEN '480p (SD)' THEN 5
                    ELSE 6
                END
        """
        )

        total_with_resolution = 0
        stats_list = []

        for row in cursor.fetchall():
            total_with_resolution += row[1]
            stats_list.append(
                ResolutionStats(
                    resolution=row[0],
                    count=row[1],
                    total_size=row[2],
                    avg_bitrate=row[3] or 0,
                )
            )

        # 비율 계산
        for stats in stats_list:
            stats.percentage = round(
                (stats.count / total_with_resolution * 100) if total_with_resolution > 0 else 0, 1
            )

        report.resolution_stats = stats_list

    def _gather_codec_stats(self, report: ArchiveReport) -> None:
        """코덱별 통계 수집"""
        cursor = self._conn.cursor()

        # 비디오 코덱
        cursor.execute(
            """
            SELECT
                COALESCE(video_codec, 'Unknown') as codec,
                COUNT(*) as count
            FROM media_info
            WHERE extraction_status = 'success'
            GROUP BY video_codec
            ORDER BY count DESC
        """
        )

        total = 0
        stats_list = []

        for row in cursor.fetchall():
            total += row[1]
            stats_list.append(
                CodecStats(
                    codec=row[0],
                    count=row[1],
                )
            )

        for stats in stats_list:
            stats.percentage = round((stats.count / total * 100) if total > 0 else 0, 1)

        report.codec_stats = stats_list

    def _gather_container_stats(self, report: ArchiveReport) -> None:
        """컨테이너 포맷별 통계 수집"""
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(container_format, 'Unknown') as container,
                COUNT(*) as count,
                COALESCE(SUM(file_size), 0) as total_size
            FROM media_info
            WHERE extraction_status = 'success'
            GROUP BY container_format
            ORDER BY count DESC
        """
        )

        total = 0
        stats_list = []

        for row in cursor.fetchall():
            total += row[1]
            stats_list.append(
                ContainerStats(
                    container=row[0],
                    count=row[1],
                    total_size=row[2],
                )
            )

        for stats in stats_list:
            stats.percentage = round((stats.count / total * 100) if total > 0 else 0, 1)

        report.container_stats = stats_list

    def _gather_folder_stats(self, report: ArchiveReport) -> None:
        """폴더별 통계 수집"""
        cursor = self._conn.cursor()

        # 모든 폴더 통계 조회
        cursor.execute(
            """
            SELECT
                parent_folder,
                COUNT(*) as file_count,
                COALESCE(SUM(size_bytes), 0) as total_size,
                SUM(CASE WHEN file_type = 'video' THEN 1 ELSE 0 END) as video_count
            FROM files
            GROUP BY parent_folder
            ORDER BY total_size DESC
        """
        )

        all_folders = []

        for row in cursor.fetchall():
            folder_path = row[0] or "(root)"
            # 상대 경로 추출 (ARCHIVE 이후)
            relative = self._extract_relative_path(folder_path)
            depth = relative.count("/") if relative else 0

            stats = FolderStats(
                folder=folder_path,
                file_count=row[1],
                total_size=row[2],
                video_count=row[3],
                depth=depth,
                relative_path=relative,
            )
            all_folders.append(stats)

        # 상위 50개만 저장 (용량 순)
        report.folder_stats = all_folders[:50]

        # 폴더 트리 생성
        report.folder_tree = self._build_folder_tree(all_folders)

    def _extract_relative_path(self, full_path: str) -> str:
        """전체 경로에서 ARCHIVE 이후 상대 경로 추출"""
        # 경로 정규화
        path = full_path.replace("\\", "/")

        # ARCHIVE 이후 경로 추출
        markers = ["/ARCHIVE/", "/ARCHIVE"]
        for marker in markers:
            if marker in path:
                idx = path.find(marker)
                return path[idx + len(marker) :].strip("/")

        # ARCHIVE 마커가 없으면 마지막 3개 폴더만 반환
        parts = path.strip("/").split("/")
        if len(parts) > 3:
            return "/".join(parts[-3:])
        return "/".join(parts)

    def _build_folder_tree(self, folder_stats: List[FolderStats]) -> FolderTreeNode:
        """폴더 통계에서 트리 구조 생성"""
        root = FolderTreeNode(name="ARCHIVE", full_path="", depth=0)

        for stats in folder_stats:
            relative = stats.relative_path
            if not relative:
                # 루트 레벨
                root.file_count += stats.file_count
                root.total_size += stats.total_size
                root.video_count += stats.video_count
                continue

            # 경로 분리
            parts = relative.split("/")
            current = root

            for i, part in enumerate(parts):
                if not part:
                    continue

                if part not in current.children:
                    current.children[part] = FolderTreeNode(
                        name=part,
                        full_path="/".join(parts[: i + 1]),
                        depth=i + 1,
                    )

                current = current.children[part]

            # 리프 노드에 통계 추가
            current.file_count = stats.file_count
            current.total_size = stats.total_size
            current.video_count = stats.video_count

        # 부모 노드 통계 집계
        self._aggregate_tree_stats(root)

        return root

    def _aggregate_tree_stats(self, node: FolderTreeNode) -> None:
        """트리 노드의 자식 통계를 부모로 집계"""
        for child in node.children.values():
            self._aggregate_tree_stats(child)
            # 자식이 리프 노드가 아니면 합계에 포함 안함 (이중 계산 방지)
            # 리프 노드만 실제 데이터 가짐

    def _gather_duration_stats(self, report: ArchiveReport) -> None:
        """재생시간별 통계 수집"""
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT
                CASE
                    WHEN duration_seconds < 1800 THEN 'short'
                    WHEN duration_seconds < 5400 THEN 'medium'
                    ELSE 'long'
                END as category,
                COUNT(*) as count,
                SUM(duration_seconds) / 3600.0 as total_hours
            FROM media_info
            WHERE extraction_status = 'success' AND duration_seconds IS NOT NULL
            GROUP BY category
        """
        )

        total = 0
        category_map = {}

        for row in cursor.fetchall():
            total += row[1]
            category_map[row[0]] = (row[1], row[2] or 0)

        labels = {
            "short": "단편 (< 30분)",
            "medium": "중편 (30~90분)",
            "long": "장편 (> 90분)",
        }

        stats_list = []
        for key in ["short", "medium", "long"]:
            count, hours = category_map.get(key, (0, 0))
            stats_list.append(
                DurationStats(
                    category=labels[key],
                    count=count,
                    percentage=round((count / total * 100) if total > 0 else 0, 1),
                    total_duration_hours=round(hours, 2),
                )
            )

        report.duration_stats = stats_list

    def _gather_bitrate_stats(self, report: ArchiveReport) -> None:
        """비트레이트별 통계 수집"""
        cursor = self._conn.cursor()

        cursor.execute(
            """
            SELECT
                CASE
                    WHEN bitrate < 5000000 THEN '< 5 Mbps'
                    WHEN bitrate < 10000000 THEN '5-10 Mbps'
                    WHEN bitrate < 20000000 THEN '10-20 Mbps'
                    WHEN bitrate < 50000000 THEN '20-50 Mbps'
                    ELSE '> 50 Mbps'
                END as range_label,
                COUNT(*) as count
            FROM media_info
            WHERE extraction_status = 'success' AND bitrate IS NOT NULL
            GROUP BY range_label
            ORDER BY
                CASE range_label
                    WHEN '< 5 Mbps' THEN 1
                    WHEN '5-10 Mbps' THEN 2
                    WHEN '10-20 Mbps' THEN 3
                    WHEN '20-50 Mbps' THEN 4
                    ELSE 5
                END
        """
        )

        total = 0
        stats_list = []

        for row in cursor.fetchall():
            total += row[1]
            stats_list.append(
                BitrateStats(
                    range_label=row[0],
                    count=row[1],
                )
            )

        for stats in stats_list:
            stats.percentage = round((stats.count / total * 100) if total > 0 else 0, 1)

        report.bitrate_stats = stats_list

    def _evaluate_streaming_compatibility(self, report: ArchiveReport) -> None:
        """스트리밍 적합성 평가"""
        cursor = self._conn.cursor()

        compatibility = StreamingCompatibility()

        # 호환 비디오 수
        cursor.execute(
            """
            SELECT COUNT(*) FROM media_info
            WHERE extraction_status = 'success'
            AND LOWER(video_codec) IN ('h264', 'hevc', 'h265', 'vp9', 'av1')
            AND LOWER(container_format) IN ('mp4', 'webm', 'mov', 'matroska')
        """
        )
        compatibility.compatible_count = cursor.fetchone()[0]

        # 비호환 비디오 (트랜스코딩 필요)
        cursor.execute(
            """
            SELECT COUNT(*) FROM media_info
            WHERE extraction_status = 'success'
            AND (
                LOWER(video_codec) NOT IN ('h264', 'hevc', 'h265', 'vp9', 'av1')
                OR LOWER(container_format) NOT IN ('mp4', 'webm', 'mov', 'matroska')
            )
        """
        )
        compatibility.needs_transcode = cursor.fetchone()[0]

        # 추출 실패
        cursor.execute(
            """
            SELECT COUNT(*) FROM media_info
            WHERE extraction_status = 'failed'
        """
        )
        compatibility.incompatible_count = cursor.fetchone()[0]

        # 적합률
        total = compatibility.compatible_count + compatibility.needs_transcode
        if total > 0:
            compatibility.compatibility_rate = round(
                compatibility.compatible_count / total * 100, 1
            )

        # 이슈 상세
        cursor.execute(
            """
            SELECT f.path, m.video_codec, m.container_format
            FROM media_info m
            JOIN files f ON m.file_id = f.id
            WHERE m.extraction_status = 'success'
            AND (
                LOWER(m.video_codec) NOT IN ('h264', 'hevc', 'h265', 'vp9', 'av1')
                OR LOWER(m.container_format) NOT IN ('mp4', 'webm', 'mov', 'matroska')
            )
            LIMIT 10
        """
        )

        for row in cursor.fetchall():
            compatibility.issues.append(
                {
                    "path": row[0],
                    "video_codec": row[1],
                    "container": row[2],
                    "reason": "Incompatible codec or container",
                }
            )

        # 권장 사항
        if compatibility.needs_transcode > 0:
            compatibility.recommendations.append(
                f"{compatibility.needs_transcode}개 파일이 트랜스코딩이 필요합니다."
            )

        if compatibility.incompatible_count > 0:
            compatibility.recommendations.append(
                f"{compatibility.incompatible_count}개 파일의 메타데이터 추출에 실패했습니다. 파일 상태를 확인하세요."
            )

        report.streaming_compatibility = compatibility

    def _gather_quality_issues(self, report: ArchiveReport) -> None:
        """품질 이슈 수집"""
        cursor = self._conn.cursor()

        issues = QualityIssues()

        # 추출 실패 파일
        cursor.execute(
            """
            SELECT f.path, f.filename, m.extraction_error
            FROM media_info m
            JOIN files f ON m.file_id = f.id
            WHERE m.extraction_status = 'failed'
            LIMIT 20
        """
        )

        for row in cursor.fetchall():
            issues.failed_extraction.append(
                {
                    "path": row[0],
                    "filename": row[1],
                    "error": row[2],
                }
            )

        # 비디오 스트림 없는 파일
        cursor.execute(
            """
            SELECT f.path, f.filename
            FROM media_info m
            JOIN files f ON m.file_id = f.id
            WHERE m.extraction_status = 'success' AND m.has_video = 0
            LIMIT 10
        """
        )

        for row in cursor.fetchall():
            issues.missing_video.append(
                {
                    "path": row[0],
                    "filename": row[1],
                }
            )

        # 오디오 없는 비디오 파일
        cursor.execute(
            """
            SELECT f.path, f.filename
            FROM media_info m
            JOIN files f ON m.file_id = f.id
            WHERE m.extraction_status = 'success' AND m.has_video = 1 AND m.has_audio = 0
            LIMIT 10
        """
        )

        for row in cursor.fetchall():
            issues.missing_audio.append(
                {
                    "path": row[0],
                    "filename": row[1],
                }
            )

        report.quality_issues = issues

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """용량 포맷팅"""
        if size_bytes >= 1024**4:
            return f"{size_bytes / (1024 ** 4):.2f} TB"
        elif size_bytes >= 1024**3:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
        elif size_bytes >= 1024**2:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} B"


class ReportFormatter:
    """리포트 출력 포맷터"""

    @staticmethod
    def to_json(report: ArchiveReport, indent: int = 2) -> str:
        """JSON 포맷으로 변환"""
        return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def to_markdown(report: ArchiveReport) -> str:
        """Markdown 포맷으로 변환"""
        lines = []

        # 헤더
        lines.append("# 아카이브 분석 리포트")
        lines.append("")
        lines.append(f"**생성일시**: {report.report_date}")
        if report.archive_path:
            lines.append(f"**아카이브 경로**: `{report.archive_path}`")
        lines.append("")

        # 요약
        lines.append("## 1. 전체 요약")
        lines.append("")
        lines.append("| 항목 | 값 |")
        lines.append("|------|-----|")
        lines.append(f"| 총 파일 수 | {report.total_files:,}개 |")
        lines.append(f"| 총 용량 | {report.total_size_formatted} |")
        lines.append(f"| 비디오 파일 수 | {report.total_videos:,}개 |")
        lines.append(f"| 총 재생시간 | {report.total_duration_hours:,.1f}시간 |")
        lines.append("")

        # 파일 유형별 통계
        lines.append("## 2. 파일 유형별 통계")
        lines.append("")
        lines.append("| 유형 | 파일 수 | 용량 | 비율 |")
        lines.append("|------|---------|------|------|")
        for stats in report.file_type_stats:
            lines.append(
                f"| {stats.file_type} | {stats.count:,}개 | {stats.size_formatted} | {stats.percentage}% |"
            )
        lines.append("")

        # 확장자별 상세
        if report.extension_breakdown:
            lines.append("### 확장자별 상세")
            lines.append("")
            lines.append("| 확장자 | 유형 | 파일 수 | 용량 |")
            lines.append("|--------|------|---------|------|")
            for ext, data in sorted(
                report.extension_breakdown.items(), key=lambda x: x[1]["total_size"], reverse=True
            )[:15]:
                lines.append(
                    f"| {ext} | {data['file_type']} | {data['count']:,}개 | {data['size_formatted']} |"
                )
            lines.append("")

        # 비디오 분석 (메타데이터가 있는 경우만)
        if report.resolution_stats:
            lines.append("## 3. 비디오 상세 분석")
            lines.append("")

            # 해상도별
            lines.append("### 3.1 해상도별 분포")
            lines.append("")
            lines.append("| 해상도 | 파일 수 | 비율 |")
            lines.append("|--------|---------|------|")
            for stats in report.resolution_stats:
                lines.append(f"| {stats.resolution} | {stats.count:,}개 | {stats.percentage}% |")
            lines.append("")

            # 코덱별
            if report.codec_stats:
                lines.append("### 3.2 비디오 코덱별 분포")
                lines.append("")
                lines.append("| 코덱 | 파일 수 | 비율 |")
                lines.append("|------|---------|------|")
                for stats in report.codec_stats[:10]:
                    lines.append(f"| {stats.codec} | {stats.count:,}개 | {stats.percentage}% |")
                lines.append("")

            # 컨테이너별
            if report.container_stats:
                lines.append("### 3.3 컨테이너 포맷별 분포")
                lines.append("")
                lines.append("| 포맷 | 파일 수 | 비율 |")
                lines.append("|------|---------|------|")
                for stats in report.container_stats[:10]:
                    lines.append(f"| {stats.container} | {stats.count:,}개 | {stats.percentage}% |")
                lines.append("")

            # 재생시간별
            if report.duration_stats:
                lines.append("### 3.4 재생시간별 분포")
                lines.append("")
                lines.append("| 구분 | 파일 수 | 비율 | 총 시간 |")
                lines.append("|------|---------|------|---------|")
                for stats in report.duration_stats:
                    lines.append(
                        f"| {stats.category} | {stats.count:,}개 | {stats.percentage}% | {stats.total_duration_hours:.1f}시간 |"
                    )
                lines.append("")

            # 비트레이트별
            if report.bitrate_stats:
                lines.append("### 3.5 비트레이트별 분포")
                lines.append("")
                lines.append("| 비트레이트 | 파일 수 | 비율 |")
                lines.append("|------------|---------|------|")
                for stats in report.bitrate_stats:
                    lines.append(
                        f"| {stats.range_label} | {stats.count:,}개 | {stats.percentage}% |"
                    )
                lines.append("")

        # 폴더 구조 다이어그램
        if report.folder_tree:
            lines.append("## 4. 폴더 구조")
            lines.append("")
            lines.append("```")
            lines.extend(ReportFormatter._render_folder_tree(report.folder_tree))
            lines.append("```")
            lines.append("")

        # 폴더별 상세 통계
        if report.folder_stats:
            lines.append("## 5. 폴더별 상세 통계 (용량순 상위 50개)")
            lines.append("")

            # 상대 경로 기준으로 표시
            for i, stats in enumerate(report.folder_stats[:50], 1):
                lines.append(f"### {i}. {stats.relative_path or '(root)'}")
                lines.append("")
                lines.append(f"- **파일 수**: {stats.file_count:,}개")
                lines.append(f"- **비디오 수**: {stats.video_count:,}개")
                lines.append(f"- **용량**: {stats.size_formatted}")
                lines.append(f"- **전체 경로**: `{stats.folder}`")
                lines.append("")

        # 스트리밍 적합성
        if report.streaming_compatibility:
            compat = report.streaming_compatibility
            lines.append("## 6. 스트리밍 적합성 평가")
            lines.append("")
            lines.append("| 항목 | 값 |")
            lines.append("|------|-----|")
            lines.append(f"| 호환 파일 수 | {compat.compatible_count:,}개 |")
            lines.append(f"| 트랜스코딩 필요 | {compat.needs_transcode:,}개 |")
            lines.append(f"| 분석 실패 | {compat.incompatible_count:,}개 |")
            lines.append(f"| 적합률 | {compat.compatibility_rate}% |")
            lines.append("")

            if compat.recommendations:
                lines.append("### 권장 사항")
                lines.append("")
                for rec in compat.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        # 품질 이슈
        if report.quality_issues:
            issues = report.quality_issues
            if issues.failed_extraction or issues.missing_video or issues.missing_audio:
                lines.append("## 7. 품질 이슈")
                lines.append("")

                if issues.failed_extraction:
                    lines.append(f"### 분석 실패 파일 ({len(issues.failed_extraction)}개)")
                    lines.append("")
                    for item in issues.failed_extraction[:5]:
                        lines.append(
                            f"- `{item['filename']}`: {item.get('error', 'Unknown error')}"
                        )
                    if len(issues.failed_extraction) > 5:
                        lines.append(f"- ... 외 {len(issues.failed_extraction) - 5}개")
                    lines.append("")

                if issues.missing_audio:
                    lines.append(f"### 오디오 없는 비디오 ({len(issues.missing_audio)}개)")
                    lines.append("")
                    for item in issues.missing_audio[:5]:
                        lines.append(f"- `{item['filename']}`")
                    if len(issues.missing_audio) > 5:
                        lines.append(f"- ... 외 {len(issues.missing_audio) - 5}개")
                    lines.append("")

        # 푸터
        lines.append("---")
        lines.append(f"*Generated by Archive Analyzer on {report.report_date}*")

        return "\n".join(lines)

    @staticmethod
    def _render_folder_tree(
        node: FolderTreeNode, prefix: str = "", is_last: bool = True, max_depth: int = 4
    ) -> List[str]:
        """폴더 트리를 텍스트로 렌더링

        Args:
            node: 폴더 트리 노드
            prefix: 현재 줄 접두사
            is_last: 마지막 자식 여부
            max_depth: 최대 표시 깊이

        Returns:
            렌더링된 라인 목록
        """
        lines = []

        # 현재 노드 표시
        if node.depth == 0:
            # 루트 노드
            lines.append(f"ARCHIVE/ ({node.file_count:,}개 파일, {node.size_formatted})")
        else:
            connector = "└── " if is_last else "├── "
            size_info = (
                f" ({node.file_count:,}개, {node.size_formatted})" if node.file_count > 0 else ""
            )
            lines.append(f"{prefix}{connector}{node.name}/{size_info}")

        # 자식 노드들 (용량순 정렬)
        if node.depth < max_depth:
            children = sorted(node.children.values(), key=lambda x: x.total_size, reverse=True)

            # 자식이 많으면 상위 10개만 표시
            display_children = children[:10]
            hidden_count = len(children) - 10 if len(children) > 10 else 0

            for i, child in enumerate(display_children):
                is_child_last = (i == len(display_children) - 1) and hidden_count == 0

                if node.depth == 0:
                    child_prefix = ""
                else:
                    child_prefix = prefix + ("    " if is_last else "│   ")

                lines.extend(
                    ReportFormatter._render_folder_tree(
                        child, prefix=child_prefix, is_last=is_child_last, max_depth=max_depth
                    )
                )

            # 숨겨진 항목 표시
            if hidden_count > 0:
                if node.depth == 0:
                    hidden_prefix = ""
                else:
                    hidden_prefix = prefix + ("    " if is_last else "│   ")
                lines.append(f"{hidden_prefix}└── ... 외 {hidden_count}개 폴더")

        return lines

    @staticmethod
    def to_console(report: ArchiveReport) -> str:
        """콘솔 출력용 포맷"""
        lines = []

        # 헤더
        lines.append("=" * 60)
        lines.append("           아카이브 분석 리포트")
        lines.append("=" * 60)
        lines.append(f"  생성일시: {report.report_date}")
        if report.archive_path:
            lines.append(f"  경로: {report.archive_path}")
        lines.append("")

        # 요약
        lines.append("-" * 60)
        lines.append("  [전체 요약]")
        lines.append("-" * 60)
        lines.append(f"  총 파일 수: {report.total_files:,}개")
        lines.append(f"  총 용량: {report.total_size_formatted}")
        lines.append(f"  비디오 파일: {report.total_videos:,}개")
        lines.append(f"  총 재생시간: {report.total_duration_hours:,.1f}시간")
        lines.append("")

        # 파일 유형별
        lines.append("-" * 60)
        lines.append("  [파일 유형별 통계]")
        lines.append("-" * 60)
        for stats in report.file_type_stats:
            lines.append(
                f"  {stats.file_type:12} : {stats.count:>6,}개 | {stats.size_formatted:>10} | {stats.percentage:>5.1f}%"
            )
        lines.append("")

        # 해상도별
        if report.resolution_stats:
            lines.append("-" * 60)
            lines.append("  [해상도별 분포]")
            lines.append("-" * 60)
            for stats in report.resolution_stats:
                bar = "█" * int(stats.percentage / 5) + "░" * (20 - int(stats.percentage / 5))
                lines.append(
                    f"  {stats.resolution:15} |{bar}| {stats.count:>5,}개 ({stats.percentage}%)"
                )
            lines.append("")

        # 코덱별
        if report.codec_stats:
            lines.append("-" * 60)
            lines.append("  [비디오 코덱별 분포]")
            lines.append("-" * 60)
            for stats in report.codec_stats[:8]:
                bar = "█" * int(stats.percentage / 5) + "░" * (20 - int(stats.percentage / 5))
                lines.append(
                    f"  {stats.codec:15} |{bar}| {stats.count:>5,}개 ({stats.percentage}%)"
                )
            lines.append("")

        # 스트리밍 적합성
        if report.streaming_compatibility:
            compat = report.streaming_compatibility
            lines.append("-" * 60)
            lines.append("  [스트리밍 적합성]")
            lines.append("-" * 60)
            lines.append(f"  호환 파일: {compat.compatible_count:,}개")
            lines.append(f"  트랜스코딩 필요: {compat.needs_transcode:,}개")
            lines.append(f"  적합률: {compat.compatibility_rate}%")

            if compat.recommendations:
                lines.append("")
                lines.append("  [권장 사항]")
                for rec in compat.recommendations:
                    lines.append(f"  • {rec}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)
