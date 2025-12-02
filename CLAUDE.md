# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Critical Rules

1. **Language**: 한글 출력. 기술 용어(code, GitHub)는 영어.
2. **Path**: 절대 경로만 사용. `D:\AI\claude01\...`
3. **Validation**: Phase 검증 필수. 실패 시 STOP.
4. **Inbox 체크**: 세션 시작 시 `inbox/`에 `processed/`에 없는 파일 있으면 `inbox/IMPROVE_PROCESS.md` 실행.

**Context**: Windows 10/11, PowerShell, Root: `D:\AI\claude01`

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
3. **Make vs Buy 분석**: 직접 개발 vs 라이브러리 비교표
4. **사용자 확인**: 분석 결과 제시 후 승인 대기

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
   | 복잡 | 파일 ≥6, 아키텍처 변경 | `/parallel-dev` 제안 |

   > 복잡도는 PRE_WORK 분석 시 자동 판단. validator는 `haiku` 모델 사용 (비용 최적화)

### FINAL_CHECK (최종 검증) - 자동

구현 완료 후 **최종 보고 전 필수**:

1. **E2E 테스트**: Playwright/Cypress 또는 `webapp-testing` 스킬
2. **100% 통과 필수**: 실패 시 수정 후 재실행 (최대 3회)
3. **커밋 & 푸시**: `/commit` → `Closes #<issue>` 포함
4. **최종 보고서**: 변경사항 + 테스트 결과 + PR 링크

```
## 작업 완료 보고
- 유형: [신규 기능/버그 수정/리팩토링]
- 이슈: #123 | PR: #456
- 테스트: Unit 15/15, E2E 8/8 (100%)
- 다음: PR 리뷰 대기
```

---

## 3. Phase Pipeline (요약)

| Phase | 핵심 | Validator |
|-------|------|-----------|
| 0 | PRD 생성 | `validate-phase-0.ps1` |
| 0.5 | Task 분해 | `validate-phase-0.5.ps1` |
| 1 | 구현 + 테스트 | `validate-phase-1.ps1` |
| 2 | 테스트 통과 | `validate-phase-2.ps1` |
| 2.5 | 코드 리뷰 | `/parallel-review` |
| 3 | 버전 + CHANGELOG | `validate-phase-3.ps1` |
| 4 | PR 생성 | `validate-phase-4.ps1` |
| 5 | E2E + Security | `validate-phase-5.ps1` |
| 6 | 배포 | `validate-phase-6.ps1` |

### 워크플로우 선택 기준

| 상황 | 워크플로우 | 설명 |
|------|-----------|------|
| 단순 작업 | **Auto Workflow** | 버그 수정, 소규모 기능 (PRE→IMPL→FINAL) |
| 복잡한 프로젝트 | **Phase Pipeline** | PRD 필요, 다수 파일 변경 (Phase 0→6) |
| 명시적 요청 | **Phase Pipeline** | "PRD 만들어줘", "Phase 0 시작" |

> 상세: `docs/WORKFLOW_REFERENCE.md`

---

## 4. Commands (카테고리)

| 카테고리 | 주요 커맨드 |
|----------|-------------|
| Planning | `/create-prd`, `/todo`, `/issues`, `/issue` |
| Coding | `/tdd`, `/fix-issue`, `/parallel-dev` |
| Testing | `/parallel-test`, `/parallel-review`, `/check`, `/api-test` |
| Ops | `/commit`, `/changelog`, `/create-pr` |
| Auto | `/pre-work`, `/final-check` |
| Research | `/parallel-research`, `/issue-update` |
| Analysis | `/optimize`, `/analyze-logs`, `/analyze-code` |

> 전체 목록 (26개): `.claude/commands/`

---

## 5. Architecture (요약)

```
D:\AI\claude01\
├── .claude/           # Commands, Agents, Skills, Hooks
├── src/agents/        # Multi-Agent (LangGraph)
├── scripts/           # Phase Validators (PowerShell)
├── tasks/prds/        # PRD 문서
└── docs/              # 상세 가이드
```

**Agents**: 33개 (`.claude/agents/`)
**Skills**: `skill-creator`, `webapp-testing`

> 상세: `docs/WORKFLOW_REFERENCE.md`, `docs/guides/MULTI_AGENT_GUIDE.md`

---

## 6. Quick Reference

```powershell
# 환경 설정
$env:ANTHROPIC_API_KEY = "your-key"

# 테스트
pytest tests/ -v -m unit

# Phase 상태
.\scripts\phase-status.ps1

# Bypass 모드
.\start-claude.bat
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

### 환경 변수 (필수)

| 변수 | 용도 | 예시 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Claude API | `sk-ant-...` |
| `GITHUB_TOKEN` | GitHub CLI | `ghp_...` |
| `SMB_SERVER` | NAS 접속 | `10.10.100.122` |
| `SMB_USERNAME` / `SMB_PASSWORD` | NAS 인증 | - |
| `MEILISEARCH_URL` | 검색 서버 | `http://localhost:7700` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth (선택) | - |

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
