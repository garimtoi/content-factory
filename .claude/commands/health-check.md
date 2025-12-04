# /health-check - 시스템 상태 점검

시스템 준비 상태를 점검하는 "Doctor" 스타일 커맨드.

## 점검 항목

### 1. Environment Variables (환경 변수)

```bash
# 필수
echo "ANTHROPIC_API_KEY: $(if [ -n "$ANTHROPIC_API_KEY" ]; then echo '✓ Set'; else echo '✗ Not set'; fi)"
echo "GITHUB_TOKEN: $(if [ -n "$GITHUB_TOKEN" ]; then echo '✓ Set'; else echo '✗ Not set'; fi)"

# 선택
echo "MEILISEARCH_URL: $(if [ -n "$MEILISEARCH_URL" ]; then echo '✓ Set'; else echo '○ Not set (optional)'; fi)"
```

### 2. Required Tools (필수 도구)

```bash
git --version 2>/dev/null || echo "✗ git not found"
gh --version 2>/dev/null || echo "✗ gh not found"
python --version 2>/dev/null || echo "✗ python not found"
```

### 3. Project Files (프로젝트 파일)

```bash
# CLAUDE.md 버전 확인
head -5 CLAUDE.md | grep "Version"

# Hook 파일 확인
ls -la .claude/hooks/*.py 2>/dev/null || echo "✗ No hooks found"

# Phase validator 확인
ls scripts/validate-phase-*.ps1 2>/dev/null | wc -l
```

### 4. GitHub Connectivity (GitHub 연결)

```bash
gh auth status
gh api rate_limit --jq '.rate.remaining'
```

### 5. Inbox Status (Inbox 상태)

```bash
# 미처리 파일 확인
ls inbox/*.md 2>/dev/null | grep -v IMPROVE_PROCESS.md | wc -l
ls inbox/processed/*.md 2>/dev/null | wc -l
```

## 출력 형식

```
╭─────────────────────────────────────╮
│        System Health Check          │
╰─────────────────────────────────────╯

✓ Environment Variables
  ✓ ANTHROPIC_API_KEY: Set
  ✓ GITHUB_TOKEN: Set
  ○ MEILISEARCH_URL: Not set (optional)

✓ Required Tools
  ✓ git: 2.40.0
  ✓ gh: 2.45.0
  ✓ python: 3.11.0

✓ Project Files
  ✓ CLAUDE.md: v2.6.0
  ✓ Hooks: 2 files
  ✓ Phase validators: 9 files

✓ GitHub Connectivity
  ✓ Authenticated as: username
  ✓ Rate limit: 4998/5000

⚠ Inbox Status
  ⚠ Unprocessed: 2 files
  ✓ Processed: 1 file

─────────────────────────────────────
Summary: 1 warning, 0 errors
```

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 모든 검사 통과 |
| 1 | 경고 있음 (작업 가능) |
| 2 | 오류 있음 (작업 불가) |

## 관련 커맨드

- `/init` - 세션 초기화 (inbox 체크 포함)
- `/issues` - 이슈 목록 조회
