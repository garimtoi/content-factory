# 최종 검증 (Final Check)

구현 완료 후 자동 실행되는 최종 검증 워크플로우입니다.
수동 호출도 가능합니다.

## 자동 트리거

다음 조건 시 자동 실행:
- 코드 수정 완료 후
- PR 생성 전
- 사용자에게 최종 보고 전

## 실행 단계

### Step 1: E2E 테스트 실행

#### Playwright 감지 시
```bash
npx playwright test
```

#### Cypress 감지 시
```bash
npx cypress run
```

#### 테스트 프레임워크 없을 시
`webapp-testing` 스킬을 사용하여 스모크 테스트:
- 주요 페이지 로딩 확인
- 핵심 기능 동작 확인
- 콘솔 에러 없음 확인

### Step 2: 통과 조건

| 상태 | 조건 | 다음 단계 |
|------|------|-----------|
| ✅ PASS | 100% 통과 | 최종 보고 진행 |
| ❌ FAIL (1차) | 실패 테스트 존재 | 자동 수정 시도 |
| ❌ FAIL (2차) | 수정 후 재실행 | 자동 수정 시도 |
| ❌ FAIL (3차) | 3회 실패 | 사용자에게 보고 |

### Step 3: 자동 수정 (실패 시)

실패 감지 시 **서브에이전트 자동 투입**:

```
1. 실패 테스트 분석 → debugger 에이전트
2. 원인 파악 및 수정 → code-reviewer + 적절한 개발 에이전트
3. 테스트 재실행 → playwright-engineer
4. 최대 3회 반복 (모든 테스트 통과까지)
```

> 이전 `/aiden-endtoend` 기능 통합: 서브에이전트를 활용한 자동 수정

### Step 4: 자동 Phase 진행

테스트 100% 통과 시 **사용자 대기 없이 자동 진행**:

```
✅ E2E 통과 → Phase 2.5 (Security Audit) ─┬─ 취약점 없음 → 자동 진행
                                          └─ Critical/High → ⏸️ 대기
             → Phase 3 (버전 자동 결정) ───┬─ PATCH/MINOR → 자동 진행
                                          └─ MAJOR (Breaking) → ⏸️ 대기
             → Phase 4 (PR 생성) 자동 진행
             → Phase 5 (배포) - 사용자 확인 대기
```

**버전 자동 결정 (Conventional Commits 분석)**:
```bash
# 커밋 히스토리 분석
git log --oneline $BASE_BRANCH..HEAD

# 버전 결정 로직
feat:            → MINOR (0.X.0)
fix:             → PATCH (0.0.X)
BREAKING CHANGE: → MAJOR (X.0.0) + ⏸️ 사용자 확인
```

**대기 조건 (다음 경우에만 멈춤)**:
| 조건 | 이유 | 동작 |
|------|------|------|
| MAJOR 버전 변경 | Breaking changes 영향도 검토 | ⏸️ 사용자 확인 |
| Critical/High 취약점 | 보안 위험 감수 여부 결정 | ⏸️ 사용자 확인 |
| 배포 (Phase 5) | 프로덕션 변경 | ⏸️ 사용자 확인 |
| 3회 실패 | 자동 해결 불가 | 수동 개입 요청 |

### Step 5: 최종 보고서 (자동 진행 후)

```markdown
## 작업 완료 보고

### 요약
- **작업 유형**: [신규 기능/버그 수정/리팩토링]
- **관련 이슈**: #123
- **PR**: #456

### 변경 사항
| 파일 | 변경 내용 |
|------|-----------|
| `src/feature.ts` | 새 기능 추가 |
| `tests/feature.test.ts` | 테스트 추가 |

### 테스트 결과
- **Unit**: 15/15 통과 ✅
- **Integration**: 5/5 통과 ✅
- **E2E**: 8/8 통과 ✅
- **Coverage**: 87%

### 완료된 Phase
- [x] Phase 2: 테스트 검증 ✅
- [x] Phase 3: 버전 + CHANGELOG ✅
- [x] Phase 4: PR 생성 ✅
- [x] Phase 5: Security Audit ✅

### 다음 단계
- [ ] Phase 6: 배포 (사용자 확인 대기)
```

## 실패 시 보고서

3회 실패 후 사용자에게 보고:

```markdown
## 테스트 실패 보고

### 실패 테스트
| 테스트 | 실패 사유 |
|--------|-----------|
| `login.spec.ts` | Timeout exceeded |
| `api.spec.ts` | 404 Not Found |

### 시도한 수정
1. [수정 내용 1] - 실패
2. [수정 내용 2] - 실패
3. [수정 내용 3] - 실패

### 필요한 조치
- [ ] [수동 확인 필요 항목]
- [ ] [환경 설정 확인]

**수동 개입이 필요합니다.**
```

## Override

테스트를 건너뛰려면:
- "테스트 스킵하고 보고해줘" (⚠️ 경고 발생)
- "E2E 없이 진행" (⚠️ 경고 발생)

> ⚠️ 테스트 스킵은 Hook에서 경고가 발생합니다.

## 관련 커맨드

- `/pre-work` - 사전 조사
- `/check` - 코드 품질 검사
- `/parallel-test` - 병렬 테스트 실행
- `/create-pr` - PR 생성
