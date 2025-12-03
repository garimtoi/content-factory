"""파일 유형 분류 모듈

파일 확장자를 기반으로 미디어 파일 유형을 분류합니다.
"""

import os
from enum import Enum
from typing import Set


class FileType(Enum):
    """파일 유형 열거형"""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    METADATA = "metadata"
    IMAGE = "image"
    OTHER = "other"


# 파일 유형별 확장자 매핑
FILE_TYPE_EXTENSIONS: dict[FileType, Set[str]] = {
    FileType.VIDEO: {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".ts",
        ".mts",
        ".m2ts",
        ".vob",
        ".mpg",
        ".mpeg",
        ".3gp",
        ".ogv",
        ".rm",
        ".rmvb",
        ".divx",
        ".f4v",
        ".mxf",  # Professional broadcast format (Material eXchange Format)
    },
    FileType.AUDIO: {
        ".mp3",
        ".aac",
        ".flac",
        ".wav",
        ".m4a",
        ".ogg",
        ".wma",
        ".opus",
        ".ape",
        ".alac",
        ".aiff",
        ".ac3",
        ".dts",
        ".pcm",
    },
    FileType.SUBTITLE: {
        ".srt",
        ".ass",
        ".ssa",
        ".vtt",
        ".sub",
        ".idx",
        ".sup",
        ".smi",
        ".sami",
        ".txt",
        ".lrc",
    },
    FileType.METADATA: {".nfo", ".xml", ".json", ".yaml", ".yml"},
    FileType.IMAGE: {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".ico",
        ".svg",
        ".heic",
        ".heif",
        ".raw",
        ".cr2",
    },
}

# 역방향 매핑 (확장자 -> 파일 유형)
_EXTENSION_TO_TYPE: dict[str, FileType] = {}
for file_type, extensions in FILE_TYPE_EXTENSIONS.items():
    for ext in extensions:
        _EXTENSION_TO_TYPE[ext] = file_type


def classify_file(filename: str) -> FileType:
    """파일명으로 파일 유형 분류

    Args:
        filename: 파일명 또는 전체 경로

    Returns:
        FileType 열거형 값
    """
    ext = os.path.splitext(filename)[1].lower()
    return _EXTENSION_TO_TYPE.get(ext, FileType.OTHER)


def get_extension(filename: str) -> str:
    """파일 확장자 추출 (소문자)

    Args:
        filename: 파일명 또는 전체 경로

    Returns:
        확장자 (점 포함, 소문자)
    """
    return os.path.splitext(filename)[1].lower()


def is_media_file(filename: str) -> bool:
    """미디어 파일 여부 확인 (비디오 또는 오디오)

    Args:
        filename: 파일명

    Returns:
        미디어 파일 여부
    """
    file_type = classify_file(filename)
    return file_type in (FileType.VIDEO, FileType.AUDIO)


def is_video_file(filename: str) -> bool:
    """비디오 파일 여부 확인"""
    return classify_file(filename) == FileType.VIDEO


def is_audio_file(filename: str) -> bool:
    """오디오 파일 여부 확인"""
    return classify_file(filename) == FileType.AUDIO


def is_subtitle_file(filename: str) -> bool:
    """자막 파일 여부 확인"""
    return classify_file(filename) == FileType.SUBTITLE


def is_metadata_file(filename: str) -> bool:
    """메타데이터 파일 여부 확인"""
    return classify_file(filename) == FileType.METADATA


def is_image_file(filename: str) -> bool:
    """이미지 파일 여부 확인"""
    return classify_file(filename) == FileType.IMAGE


def get_supported_extensions(file_type: FileType) -> Set[str]:
    """특정 파일 유형의 지원 확장자 목록

    Args:
        file_type: 파일 유형

    Returns:
        확장자 집합
    """
    return FILE_TYPE_EXTENSIONS.get(file_type, set())


def get_all_media_extensions() -> Set[str]:
    """모든 미디어 확장자 (비디오 + 오디오)"""
    return FILE_TYPE_EXTENSIONS[FileType.VIDEO] | FILE_TYPE_EXTENSIONS[FileType.AUDIO]


def get_all_supported_extensions() -> Set[str]:
    """모든 지원 확장자"""
    all_extensions = set()
    for extensions in FILE_TYPE_EXTENSIONS.values():
        all_extensions |= extensions
    return all_extensions


class FileClassifier:
    """파일 분류기 클래스

    확장 가능한 파일 분류 기능 제공
    """

    def __init__(self):
        self._custom_extensions: dict[str, FileType] = {}

    def add_extension(self, extension: str, file_type: FileType) -> None:
        """커스텀 확장자 추가

        Args:
            extension: 확장자 (점 포함)
            file_type: 파일 유형
        """
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        self._custom_extensions[ext] = file_type

    def classify(self, filename: str) -> FileType:
        """파일 분류

        커스텀 확장자를 우선 확인한 후 기본 분류 적용

        Args:
            filename: 파일명

        Returns:
            FileType 열거형 값
        """
        ext = get_extension(filename)

        # 커스텀 확장자 우선
        if ext in self._custom_extensions:
            return self._custom_extensions[ext]

        return classify_file(filename)

    def get_statistics(self, filenames: list[str]) -> dict[FileType, int]:
        """파일 목록의 유형별 통계

        Args:
            filenames: 파일명 목록

        Returns:
            유형별 개수 딕셔너리
        """
        stats = {ft: 0 for ft in FileType}
        for filename in filenames:
            file_type = self.classify(filename)
            stats[file_type] += 1
        return stats
