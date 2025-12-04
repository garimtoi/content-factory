@echo off
REM Claude CLI with bypass permissions + auto /init
REM 경고: 이 모드는 모든 권한 체크를 우회합니다. 신뢰할 수 있는 환경에서만 사용하세요.

echo ========================================
echo Claude Code CLI (Bypass Permissions)
echo ========================================
echo.

REM 세션 시작과 동시에 /init 실행 (inbox 체크 포함)
claude --dangerously-skip-permissions "/init"
