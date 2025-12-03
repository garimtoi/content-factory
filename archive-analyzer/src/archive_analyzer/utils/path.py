"""경로 정규화 유틸리티

#21: 경로 정규화 로직 통합
- normalize_path(): 백슬래시 → 슬래시 변환
- normalize_nas_path(): NAS 경로 정규화 (소문자 포함)
- generate_file_id(): NAS 경로 기반 고유 ID 생성
"""

import hashlib
from typing import Optional


def normalize_path(path: str) -> str:
    """경로 정규화: 백슬래시 → 슬래시 변환

    Args:
        path: 변환할 경로

    Returns:
        슬래시로 통일된 경로

    Examples:
        >>> normalize_path("GGPNAs\\ARCHIVE\\WSOP")
        'GGPNAs/ARCHIVE/WSOP'
    """
    if not path:
        return ""
    return path.replace("\\", "/")


def normalize_nas_path(path: str, remove_prefix: bool = True) -> str:
    """NAS 경로 정규화

    Args:
        path: NAS 경로
        remove_prefix: // 접두사 제거 여부 (기본 True)

    Returns:
        정규화된 경로 (소문자, 슬래시 통일)

    Examples:
        >>> normalize_nas_path("//10.10.100.122/docker/GGPNAs/ARCHIVE")
        '10.10.100.122/docker/ggpnas/archive'
        >>> normalize_nas_path("Z:\\GGPNAs\\ARCHIVE")
        'z:/ggpnas/archive'
    """
    if not path:
        return ""
    normalized = path.replace("\\", "/").lower()
    if remove_prefix and normalized.startswith("//"):
        normalized = normalized[2:]
    return normalized


def generate_file_id(nas_path: str) -> str:
    """NAS 경로로 고유 ID 생성

    동일한 파일에 대해 항상 같은 ID가 생성됩니다.
    경로는 정규화 후 해싱됩니다.

    Args:
        nas_path: NAS 파일 경로

    Returns:
        16자리 MD5 해시 ID

    Examples:
        >>> generate_file_id("//10.10.100.122/docker/GGPNAs/ARCHIVE/test.mp4")
        'a1b2c3d4e5f6g7h8'
    """
    normalized = normalize_nas_path(nas_path, remove_prefix=False)
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


def extract_relative_path(full_path: str, base_marker: str = "ARCHIVE") -> str:
    """전체 경로에서 마커 이후 상대 경로 추출

    Args:
        full_path: 전체 경로
        base_marker: 기준 마커 (기본 "ARCHIVE")

    Returns:
        마커 이후 상대 경로 (마커 포함)

    Examples:
        >>> extract_relative_path("//nas/share/GGPNAs/ARCHIVE/WSOP/2024")
        'WSOP/2024'
    """
    normalized = normalize_path(full_path)
    marker = f"/{base_marker}/"
    if marker in normalized:
        idx = normalized.find(marker)
        return normalized[idx + len(marker):].strip("/")
    return normalized.split("/")[-1] if "/" in normalized else normalized


def join_paths(*parts: str) -> str:
    """경로 조합 (빈 값 무시, 슬래시 통일)

    Args:
        *parts: 조합할 경로 부분들

    Returns:
        조합된 경로

    Examples:
        >>> join_paths("GGPNAs", "ARCHIVE", "", "WSOP")
        'GGPNAs/ARCHIVE/WSOP'
    """
    result = []
    for part in parts:
        if part:
            normalized = normalize_path(part).strip("/")
            if normalized:
                result.append(normalized)
    return "/".join(result)


def get_filename(path: str) -> str:
    """경로에서 파일명 추출

    Args:
        path: 파일 경로

    Returns:
        파일명

    Examples:
        >>> get_filename("ARCHIVE/WSOP/video.mp4")
        'video.mp4'
    """
    normalized = normalize_path(path)
    return normalized.split("/")[-1] if normalized else ""


def get_extension(path: str, with_dot: bool = True) -> Optional[str]:
    """경로에서 확장자 추출

    Args:
        path: 파일 경로
        with_dot: True면 '.'포함, False면 제외

    Returns:
        확장자 (소문자) 또는 None

    Examples:
        >>> get_extension("video.MP4")
        '.mp4'
        >>> get_extension("video.MP4", with_dot=False)
        'mp4'
    """
    filename = get_filename(path)
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return f".{ext}" if with_dot else ext
    return None
