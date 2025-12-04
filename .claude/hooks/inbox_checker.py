#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inbox 체크 Hook - 세션 시작 시 미처리 파일 감지

UserPromptSubmit 이벤트에서 실행되어 inbox/ 폴더의 미처리 파일을 감지합니다.
미처리 파일이 있으면 Claude에게 IMPROVE_PROCESS.md 실행을 강제합니다.
"""

import json
import sys
import os
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# 프로젝트 루트
PROJECT_ROOT = Path(r"D:\AI\claude01")
INBOX_DIR = PROJECT_ROOT / "inbox"
PROCESSED_DIR = INBOX_DIR / "processed"

# 세션별 체크 여부를 추적하는 플래그 파일
SESSION_FLAG = PROJECT_ROOT / ".claude" / ".inbox_checked"


def get_unprocessed_files() -> list[str]:
    """
    inbox/에서 processed/에 없는 파일 목록 반환
    IMPROVE_PROCESS.md는 제외
    """
    if not INBOX_DIR.exists():
        return []

    # inbox 파일 목록
    inbox_files = set()
    for ext in ["*.md", "*.json", "*.csv"]:
        for f in INBOX_DIR.glob(ext):
            if f.name != "IMPROVE_PROCESS.md":
                inbox_files.add(f.name)

    # processed 파일 목록
    processed_files = set()
    if PROCESSED_DIR.exists():
        for f in PROCESSED_DIR.iterdir():
            processed_files.add(f.name)

    # 미처리 파일
    unprocessed = inbox_files - processed_files
    return sorted(list(unprocessed))


def is_already_checked() -> bool:
    """이번 세션에서 이미 체크했는지 확인 (1시간 이내)"""
    if not SESSION_FLAG.exists():
        return False

    import time
    # 1시간(3600초) 이내에 체크했으면 True
    mtime = SESSION_FLAG.stat().st_mtime
    return (time.time() - mtime) < 3600


def mark_as_checked():
    """체크 완료 표시"""
    SESSION_FLAG.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FLAG.touch()


def main():
    """Hook 메인 함수"""
    try:
        # stdin 읽기 (Hook 프로토콜)
        input_data = sys.stdin.read()

        # 이미 체크했으면 통과
        if is_already_checked():
            print(json.dumps({"action": "proceed"}))
            return

        # 미처리 파일 확인
        unprocessed = get_unprocessed_files()

        if unprocessed:
            # 미처리 파일 있음 → Claude 컨텍스트에 주입
            file_list = "\n".join(f"  - {f}" for f in unprocessed)
            context_message = f"""[CRITICAL] Inbox 미처리 파일 감지!

미처리 파일 ({len(unprocessed)}개):
{file_list}

CLAUDE.md Critical Rule #4 위반 방지:
지금 즉시 inbox/IMPROVE_PROCESS.md를 읽고 실행하세요.

처리 순서:
1. inbox/IMPROVE_PROCESS.md 읽기
2. 미처리 파일 분석
3. 개선안 도출 및 적용
4. 처리 완료 후 inbox/processed/로 이동

이 작업이 완료될 때까지 다른 작업을 진행하지 마세요."""

            # 체크 완료 표시 (중복 방지)
            mark_as_checked()

            # 공식 형식: Plain text stdout → Claude 컨텍스트에 추가
            print(context_message)
        else:
            # 미처리 파일 없음 - 아무것도 출력 안 함
            mark_as_checked()

    except Exception as e:
        # 에러 시에도 진행 허용 (stderr에 에러 출력)
        print(f"inbox_checker error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
