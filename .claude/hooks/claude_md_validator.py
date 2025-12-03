#!/usr/bin/env python3
# .claude/hooks/claude_md_validator.py
"""
CLAUDE.md 규칙 실시간 검증 Hook

UserPromptSubmit 이벤트를 인터셉트하여 CLAUDE.md 규칙 위반을 감지합니다.
severity1/claude-code-prompt-improver 패턴 참조.

사용법:
    이 파일을 .claude/hooks/ 에 배치하고 settings.json에 등록합니다.
"""

import json
import sys
import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Severity(Enum):
    """위반 심각도"""
    CRITICAL = "critical"  # 차단
    HIGH = "high"          # 강한 경고
    MEDIUM = "medium"      # 경고
    LOW = "low"            # 제안


@dataclass
class Violation:
    """규칙 위반"""
    rule_id: str
    message: str
    severity: Severity
    suggestion: Optional[str] = None


# ============================================================================
# CLAUDE.md 핵심 규칙 정의
# ============================================================================

RULES = {
    # Section 1: Critical Instructions
    "relative_path": {
        "pattern": r'(?:^|\s)\.\/[^\s]+|(?:^|\s)cd\s+(?!\/|[A-Z]:)[^\s]+',
        "message": "상대 경로 대신 절대 경로를 사용하세요 (CLAUDE.md Section 1.2)",
        "severity": Severity.HIGH,
        "suggestion": "예: D:\\AI\\claude01\\src 또는 /home/user/project"
    },

    "skip_validation": {
        "pattern": r'skip\s+(?:phase\s+)?validation|validation\s*(?:을|를)?\s*(?:건너뛰|스킵)|검증\s*(?:을|를)?\s*(?:건너뛰|스킵|skip)',
        "message": "Phase 검증을 건너뛸 수 없습니다 (CLAUDE.md Section 1.3)",
        "severity": Severity.CRITICAL,
        "suggestion": "검증 실패 시 현재 Phase에서 수정하세요"
    },

    # Section 3: Workflow Pipeline
    "phase_jump": {
        "pattern": r'phase\s*[2-6]\s*(?:부터|from|으로|로)\s*(?:시작|start)|skip\s+(?:to\s+)?phase|phase\s*[3-6]\s*(?:로|으로)\s*(?:바로|직접)',
        "message": "Phase를 건너뛸 수 없습니다. Phase 0부터 순차 진행 (CLAUDE.md Section 3)",
        "severity": Severity.HIGH,
        "suggestion": "Phase 0 → 0.5 → 1 → 2 → ... 순서로 진행하세요"
    },

    # Section 9: TDD Strict Order
    "implement_before_test": {
        "pattern": r'(?:구현|implement|code).*(?:먼저|first|before).*(?:테스트|test)|(?:without|없이).*(?:테스트|test)|테스트\s*없이.*(?:코드|구현|작성)',
        "message": "TDD: 테스트를 먼저 작성하세요 (CLAUDE.md Section 9)",
        "severity": Severity.HIGH,
        "suggestion": "Red → Green → Refactor 순서를 따르세요"
    },

    # Section 1.1: Language
    "english_output": {
        "pattern": r'(?:respond|answer|reply|output)\s+(?:in\s+)?(?:english|영어로)|영어로\s*(?:respond|answer|reply|output|대답|답변)',
        "message": "사용자 출력은 한글로 작성합니다 (CLAUDE.md Section 1.1)",
        "severity": Severity.MEDIUM,
        "suggestion": "기술 용어(code, GitHub 등)만 영어로 유지"
    },

    # Section 7: E2E Skip Warning
    "skip_e2e": {
        "pattern": r'(?:테스트|test|e2e|E2E|검증)\s*(?:스킵|skip|없이|생략|건너뛰)|(?:스킵|skip|없이|생략|건너뛰).*(?:테스트|test|e2e|E2E|검증)',
        "message": "E2E 테스트를 스킵하면 품질 보장이 어렵습니다 (CLAUDE.md Section 7)",
        "severity": Severity.HIGH,
        "suggestion": "불가피한 경우 '⚠️ E2E 미실행' 경고와 수동 테스트 계획 포함 필수"
    },
}


# ============================================================================
# 검증 함수
# ============================================================================

def validate_prompt(prompt: str) -> list[Violation]:
    """
    프롬프트에서 CLAUDE.md 규칙 위반 검사

    Args:
        prompt: 사용자 입력 프롬프트

    Returns:
        위반 목록
    """
    violations = []

    for rule_id, rule in RULES.items():
        if re.search(rule["pattern"], prompt, re.IGNORECASE | re.MULTILINE):
            violations.append(Violation(
                rule_id=rule_id,
                message=rule["message"],
                severity=rule["severity"],
                suggestion=rule.get("suggestion")
            ))

    return violations


def format_feedback(violations: list[Violation]) -> str:
    """
    위반 사항을 사용자 친화적 메시지로 변환

    Args:
        violations: 위반 목록

    Returns:
        포맷된 메시지
    """
    if not violations:
        return ""

    severity_icons = {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢"
    }

    lines = ["**CLAUDE.md 규칙 위반 감지:**\n"]

    for v in violations:
        icon = severity_icons.get(v.severity, "⚪")
        lines.append(f"{icon} **[{v.rule_id}]** {v.message}")
        if v.suggestion:
            lines.append(f"   💡 {v.suggestion}")
        lines.append("")

    return "\n".join(lines)


def get_action(violations: list[Violation]) -> str:
    """
    위반 심각도에 따른 액션 결정

    Args:
        violations: 위반 목록

    Returns:
        "block", "warn", 또는 "proceed"
    """
    if not violations:
        return "proceed"

    # Critical 위반이 있으면 차단
    if any(v.severity == Severity.CRITICAL for v in violations):
        return "block"

    # High 위반이 있으면 경고
    if any(v.severity == Severity.HIGH for v in violations):
        return "warn"

    # Medium/Low는 proceed (로그만)
    return "proceed"


# ============================================================================
# Hook 진입점
# ============================================================================

def main():
    """Hook 메인 함수"""
    try:
        # stdin에서 입력 읽기
        input_data = sys.stdin.read()

        if not input_data.strip():
            # 입력이 없으면 통과
            print(json.dumps({"action": "proceed"}))
            return

        # JSON 파싱
        try:
            data = json.loads(input_data)
            prompt = data.get("prompt", data.get("text", ""))
        except json.JSONDecodeError:
            # JSON이 아니면 전체를 프롬프트로 처리
            prompt = input_data

        # 검증 실행
        violations = validate_prompt(prompt)

        # 액션 결정
        action = get_action(violations)

        # 결과 출력
        if violations:
            output = {
                "action": action,
                "message": format_feedback(violations),
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "message": v.message,
                        "severity": v.severity.value,
                        "suggestion": v.suggestion
                    }
                    for v in violations
                ]
            }
        else:
            output = {"action": "proceed"}

        print(json.dumps(output, ensure_ascii=False))

    except Exception as e:
        # 에러 발생 시에도 진행 허용 (Hook 실패로 작업 차단 방지)
        print(json.dumps({
            "action": "proceed",
            "error": str(e)
        }))


if __name__ == "__main__":
    main()
