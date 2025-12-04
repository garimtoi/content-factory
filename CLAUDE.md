# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Version**: 2.6.0 | **Updated**: 2025-12-04 | **Context**: Windows 10/11, PowerShell, Root: `D:\AI\claude01`

## 1. Critical Rules

1. **Language**: 한글 출력. 기술 용어(code, GitHub)는 영어.
2. **Path**: 절대 경로만 사용. `D:\AI\claude01\...`
3. **Validation**: Phase 검증 필수. 실패 시 STOP.
4. **Inbox 체크**: ✅ Hook 동작 확인됨. 세션 시작 시 `inbox/` 미처리 파일 감지.
5. **Anti-Hallucination**: 아래 검증 규칙 필수 준수.

### 세션 시작 체크리스트

```
1. [ ] Inbox 체크 (Hook 자동 또는 /init)
2. [ ] 현재 브랜치 확인 (git branch)
3. [ ] 미완료 이슈 확인 (/issues)
```

---

## 1.5 Anti-Hallucination Rules (거짓/환각 방지)

### 절대 금지 (NEVER)

| 금지 행동 | 올바른 행동 |
|----------|------------|
| ❌ 파일 읽지 않고 내용 추측 | ✅ `Read` 도구로 먼저 확인 |
| ❌ 검증 없이 "완료/해결됨" 선언 | ✅ 실행 결과/테스트 출력 확인 후 선언 |
| ❌ 존재하지 않는 API/함수 언급 | ✅ 문서/코드에서 실제 확인 후 언급 |
| ❌ 불확실한 정보를 확신처럼 전달 | ✅ "확실하지 않음" 명시 또는 조사 |

### 의무 검증 (MUST)

```
1. 파일 존재 → Read 도구로 확인
2. 코드 작동 → 실행 결과 출력 확인
3. 테스트 통과 → pytest 출력에서 PASSED 확인
4. 기능 구현 완료 → E2E 테스트 또는 사용자 확인
```

### 불확실성 프로토콜

불확실할 때 **반드시** 다음 중 하나 선택:
- "확실하지 않습니다. 확인이 필요합니다."
- "추측입니다: [내용]. 검증하시겠습니까?"
- 조사 후 증거와 함께 응답

### 증거 기반 응답

주장할 때 **반드시** 증거 포함:
```
# 잘못된 응답
"이 함수에 버그가 있습니다"

# 올바른 응답
"D:\AI\claude01\src\utils.py:45에서
`data.strip()` 호출 시 data가 None이면
AttributeError 발생. 증거: Read 결과 참조"
```

---

## 2. Auto Workflow

Claude는 사용자 요청을 **맥락적으로 분석**하여 아래 워크플로우를 **자동 실행**합니다.

### 요청 분류 및 자동 실행

| 요청 유형 | 트리거 (맥락 분석) | 자동 실행 |
|-----------|-------------------|-----------|
| **신규 기능** | "추가", "구현", "개발", "만들어", "feature" | PRE → IMPL → FINAL |
| **버그 수정** | "수정", "고쳐", "fix", "버그", "안됨" | PRE(light) → IMPL → FINAL |
| **리팩토링** | "리팩토링", "개선", "최적화", "refactor" | PRE → IMPL → FINAL |
| **문서 수정** | "문서", "README", "docs", "주석" | ISSUE → COMMIT |
| **단순 질문** | "뭐야", "어디", "왜", "설명", "?" | 직접 응답 |

### 분류 예외 처리
다음 경우 **단순 질문**으로 처리 (자동 워크플로우 미적용):
- "설명해줘", "알려줘" 동반 시
- 코드 블록 없이 질문형 문장
- 특정 파일/기능 미언급 + 일반 질문

### PRE_WORK (사전 조사) - 자동

신규 기능/버그 수정/리팩토링 감지 시:

1. **솔루션 검색**: WebSearch + `gh search repos` (오픈소스 우선)
2. **중복 확인**: `gh issue list` + `gh pr list`
3. **Clarify (모호성 해결)**: 불명확한 요구사항 발견 시 최대 5개 질문
4. **Make vs Buy 분석**: 직접 개발 vs 라이브러리 비교표
5. **사용자 확인**: 분석 결과 제시 후 승인 대기

#### Clarify 트리거 조건
| 감지 패턴 | 동작 |
|----------|------|
| "적절한", "좋은", "빠른" 등 주관적 표현 | 구체적 기준 질문 |
| 수치/범위 미명시 | 범위 확인 질문 |
| 여러 구현 방식 가능 | 옵션 제시 후 선택 요청 |
| 기존 코드와 충돌 가능 | 호환성 확인 질문 |

> 요구사항이 명확하면 Clarify 스킵

> Light 모드 (버그 수정): 중복 확인만, 분석표 생략

#### 오픈소스 우선순위
1. **MIT/Apache/BSD 라이선스** 우선 검색
2. Stars > 500, 최근 커밋 < 6개월
3. 직접 개발은 마지막 수단

#### 병렬 검색 에스컬레이션
검색 결과 **불충분** 시 `/parallel-research` 자동 제안:
- 결과 < 3개, 품질 미달, 상충 정보, 복합 기술, 비교 요청 ("vs")

> 상세 기준: `/pre-work` 커맨드 참조

### IMPLEMENTATION (구현) - 자동

PRE_WORK 승인 후:

1. **GitHub 연동**
   - 코드 수정: `gh issue create/comment` → 브랜치 생성 → PR 필수
   - 문서 수정: 이슈 업데이트 → 직접 커밋 허용
2. **TDD 순서**: Red → Green → Refactor
3. **브랜치**: `<type>/issue-<num>-<desc>`
4. **커밋 타이밍**
   - 테스트 통과 후 즉시 커밋
   - 이슈 해결: `fix(scope): Resolve #123 🐛`
   - 기능 완료: `feat(scope): Add feature ✨`
   - `/commit` 커맨드 또는 수동 커밋
   - README.md 수정 시: `version`, `updated` 배지 갱신
5. **병렬 에이전트 (조건부 자동)**

   | 복잡도 | 기준 | 동작 |
   |--------|------|------|
   | 단순 | 파일 ≤2, 변경 <50줄 | 단일 에이전트 |
   | 중간 | 파일 3-5, 변경 50-200줄 | `/parallel-test` 제안 |
   | 복잡 | 파일 ≥6, 아키텍처 변경 | `/parallel-dev` + Dual-agent |

#### Dual-agent 패턴 (복잡도 "복잡" 시)

```
Initializer (계획)          Executor (실행)
     │                           │
     ├─ 요구사항 분석              ├─ 작업 순차 실행
     ├─ 작업 분해                  ├─ 각 작업 후 검증
     ├─ 의존성 분석                └─ 실패 시 재계획 요청
     └─ 실행 순서 결정
          │
          └──────────────────────→
```

   > 복잡도는 PRE_WORK 분석 시 자동 판단. validator는 `haiku` 모델 사용 (비용 최적화)

### FINAL_CHECK (최종 검증) - 자동

구현 완료 후 **자동 실행 및 자동 진행**:

1. **E2E 테스트**: Playwright/Cypress 또는 `webapp-testing` 스킬
2. **100% 통과 필수**: 실패 시 자동 수정 (최대 3회)
3. **자동 Phase 진행**: 통과 시 Phase 3→4→5 자동 진행
4. **최종 보고서**: 모든 Phase 완료 후 보고

```
✅ E2E 통과 → Phase 3 (버전) → Phase 4 (PR) → Phase 5 (Security)
           → Phase 6 (배포) - 사용자 확인 대기
```

**대기 조건 (다음 경우에만 멈춤)**:
| 조건 | 동작 |
|------|------|
| 사용자 검증 필수 | 배포, 프로덕션 변경 시 확인 요청 |
| 해결 불가능 판단 | 3회 실패, 환경 문제 시 수동 개입 요청 |

---

## 3. Phase Pipeline (요약)

| Phase | 핵심 | Validator |
|-------|------|-----------|
| 0 | PRD 생성 | `validate-phase-0.ps1` |
| 0.5 | Task 분해 | `validate-phase-0.5.ps1` |
| 1 | 구현 + 테스트 | `validate-phase-1.ps1` |
| 2 | 테스트 통과 | `validate-phase-2.ps1` |
| 2.5 | 코드 리뷰 + Security | `/parallel-review` + Security Audit |
| 3 | 버전 자동 결정 | Conventional Commits 분석 |
| 4 | PR 생성 | `validate-phase-4.ps1` |
| 5 | 보안 감사 | `validate-phase-5.ps1` + Security Audit |
| 6 | 배포 | `validate-phase-6.ps1` (사용자 확인 필수) |

### 버전 자동 결정 (Phase 3)

| 커밋 타입 | 버전 변경 | 대기 여부 |
|----------|----------|----------|
| `fix:` | PATCH (0.0.X) | 자동 진행 |
| `feat:` | MINOR (0.X.0) | 자동 진행 |
| `BREAKING CHANGE:` | MAJOR (X.0.0) | ⏸️ 사용자 확인 |

### 조건부 대기 (자동 진행 중지)

| 조건 | 동작 |
|------|------|
| MAJOR 버전 변경 (Breaking) | ⏸️ 사용자 확인 대기 |
| Critical/High 보안 취약점 | ⏸️ 사용자 확인 대기 |
| 배포 (Phase 6) | ⏸️ 사용자 확인 대기 |
| 3회 실패 | 수동 개입 요청 |

### 워크플로우 선택 기준

| 상황 | 워크플로우 | 정량 기준 |
|------|-----------|----------|
| 단순 작업 | **Auto Workflow** | 파일 ≤3, 변경 <100줄 |
| 복잡한 프로젝트 | **Phase Pipeline** | 파일 ≥4 또는 변경 ≥100줄 또는 PRD 요청 |
| 자율 운영 | **Autopilot** | `/autopilot` - 이슈 자동 처리 |
| 명시적 요청 | **Phase Pipeline** | "PRD 만들어줘", "Phase 0 시작" |

> 상세: `docs/WORKFLOW_REFERENCE.md`

### Autopilot 모드 (`/autopilot`)

이슈 분석 및 **토큰 한도까지 연속 실행**:

```
/autopilot
    ↓
/init → /issues ─┬─ 이슈 있음 → 작업 실행 ─┐
                 │                         │
                 └─ 이슈 없음 ──────────────┤
                         ↓                 │
               /parallel-research          │
                         ↓                 │
               개선안 → 이슈 등록 ──────────┘
                         ↓
               반복 (토큰 한도까지)
                         ↓
               토큰 한도 → 세션 종료
                         ↓
               사용자가 /autopilot 입력 → 재개
```

| 원칙 | 설명 |
|------|------|
| 무한 반복 | 이슈 처리 → 없으면 생성 → 처리 → 반복 |
| 토큰 한도 의존 | 토큰 소진 시 자동 종료 |
| **수동 재개** | 세션 초기화 후 사용자가 `/autopilot` 입력 필요 |

> 상세: `.claude/commands/autopilot.md`

---

## 4. Commands (카테고리)

| 카테고리 | 커맨드 |
|----------|--------|
| **Autopilot** | `/autopilot` |
| **Init** | `/init` (세션 시작, inbox 체크 포함) |
| Planning | `/create-prd`, `/todo`, `/issues`, `/issue`, `/aiden-plan`, `/aiden-first` |
| Coding | `/tdd`, `/fix-issue`, `/parallel-dev`, `/check` |
| Testing | `/parallel-test`, `/parallel-review`, `/api-test` |
| Ops | `/commit`, `/changelog`, `/create-pr`, `/create-docs` |
| Auto | `/pre-work`, `/final-check` |
| Research | `/parallel-research`, `/issue-update` |
| Analysis | `/optimize`, `/analyze-logs`, `/analyze-code` |
| Docs | `/aiden-update`, `/aiden-summary` |
| System | `/health-check` (시스템 상태 점검) |

> 전체 목록 (29개): `.claude/commands/` | 상세: `docs/WORKFLOW_REFERENCE.md`

---

## 5. Architecture (요약)

```
D:\AI\claude01\
├── .claude/           # Commands (28), Agents (33), Skills, Hooks
├── src/agents/        # Multi-Agent (LangGraph + Claude Agent SDK)
├── scripts/           # Phase Validators (PowerShell)
├── tasks/prds/        # PRD 문서
├── tests/             # 테스트 코드 (pytest)
├── inbox/             # 처리 대기 문서 (Critical Rule #4)
├── shared-data/       # 공유 DB (pokervod.db)
├── archive-analyzer/  # 서브프로젝트 (자체 CLAUDE.md)
└── docs/              # 상세 가이드
```

### Skills 활용

| 스킬 | 자동 트리거 | 용도 |
|------|------------|------|
| `webapp-testing` | "E2E 테스트", "브라우저 테스트", "UI 검증" | Playwright 기반 웹앱 테스트 |
| `skill-creator` | "스킬 만들어", "커스텀 스킬" | 새 스킬 생성 가이드 |

> Claude가 프롬프트와 스킬 description 매칭하여 자동 로드

> 상세: `docs/WORKFLOW_REFERENCE.md`, `docs/guides/MULTI_AGENT_GUIDE.md`

---

## 6. Quick Reference

```powershell
# 환경 설정
$env:ANTHROPIC_API_KEY = "your-key"

# 테스트
pytest tests/ -v -m unit              # 단위 테스트만
pytest tests/ -v -m integration       # 통합 테스트만
pytest tests/ -v -m "not slow"        # 느린 테스트 제외
pytest tests/test_parallel_workflow.py -v  # 단일 파일
pytest tests/test_parallel_workflow.py::test_function_name -v  # 특정 함수

# 커버리지
pytest tests/ -v --cov=src --cov-report=term

# Phase 상태
.\scripts\phase-status.ps1

# Bypass 모드
.\start-claude.bat
```

### Lint & Format (archive-analyzer)

```powershell
ruff check D:\AI\claude01\archive-analyzer\src
black --check D:\AI\claude01\archive-analyzer\src
mypy D:\AI\claude01\archive-analyzer\src\archive_analyzer
```

### 서브프로젝트 실행

```powershell
# archive-analyzer (API 서버)
cd D:\AI\claude01\archive-analyzer
pip install -e ".[dev,media,search]"
uvicorn src.archive_analyzer.api:app --reload --port 8000

# archive-analyzer (Docker 동기화)
docker-compose -f D:\AI\claude01\archive-analyzer\docker-compose.sync.yml up -d

# MeiliSearch 인덱싱
python D:\AI\claude01\archive-analyzer\scripts\index_to_meilisearch.py

# pokervod.db 동기화
python D:\AI\claude01\archive-analyzer\scripts\sync_to_pokervod.py --dry-run
```

### 환경 변수

| 변수 | 용도 | 필수 |
|------|------|:----:|
| `ANTHROPIC_API_KEY` | Claude API | ✅ |
| `GITHUB_TOKEN` | GitHub CLI (`gh`) | ✅ |
| `SMB_SERVER`, `SMB_USERNAME`, `SMB_PASSWORD` | NAS 접속 | - |
| `MEILISEARCH_URL` | 검색 서버 | - |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Agent Evolution | - |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth | - |

> 상세: `archive-analyzer/.env.example`, `.env.example`

**Hooks**: 프롬프트 제출 시 규칙 위반 자동 검사 (`.claude/hooks/`)

---

## 7. Workflow Override

자동 워크플로우를 건너뛰려면 명시적으로 요청:

| Override 대상 | 트리거 표현 | 경고 |
|---------------|-------------|------|
| PRE_WORK 전체 | "바로", "그냥", "빨리", "분석 없이", "검색 없이" | - |
| 솔루션 검색만 | "검색 생략", "라이브러리 검색 없이" | - |
| FINAL_CHECK | "테스트 스킵", "E2E 없이", "검증 생략" | ⚠️ |

### E2E 테스트 불가 시
테스트 환경 없음 감지 시:
1. `webapp-testing` 스킬로 기본 스모크 테스트
2. 불가 시 "⚠️ E2E 미실행" 경고와 함께 보고
3. 수동 테스트 계획 포함 필수

---

## 8. Do Not (금지 사항)

| 금지 | 이유 |
|------|------|
| ❌ Phase validator 없이 다음 Phase 진행 | 품질 보장 실패 |
| ❌ 상대 경로 사용 (`./`, `../`) | `D:\AI\claude01\...` 절대 경로 필수 |
| ❌ E2E 테스트 없이 최종 보고 | 불가 시 "⚠️ E2E 미실행" 경고 필수 |
| ❌ 영어로 일반 응답 | 기술 용어(code, GitHub)만 영어 |
| ❌ PR 없이 main 직접 커밋 | 코드 수정은 브랜치 → PR 필수 |
| ❌ 테스트 없이 구현 완료 처리 | TDD: Red → Green → Refactor |
| ❌ pokervod.db 스키마 무단 변경 | `qwen_hand_analysis` 소유, 협의 필수 |
