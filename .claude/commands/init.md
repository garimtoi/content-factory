# 세션 초기화 (/init)

세션 시작 시 실행되는 초기화 커맨드입니다.

---

## 1. Inbox 체크 (Critical Rule #4) - 필수

**반드시 먼저 실행**:

```
1. inbox/ 폴더 스캔
2. processed/에 없는 파일 확인
3. 미처리 파일 있으면 → inbox/IMPROVE_PROCESS.md 실행
4. 없으면 → 다음 단계로
```

### 체크 방법
```bash
# inbox 파일 목록 (IMPROVE_PROCESS.md 제외)
ls inbox/*.md inbox/*.json inbox/*.csv 2>/dev/null | grep -v IMPROVE_PROCESS

# processed 파일 목록
ls inbox/processed/ 2>/dev/null
```

### 미처리 파일 발견 시
1. `inbox/IMPROVE_PROCESS.md` 읽기
2. 프로세스에 따라 피드백 분석
3. 개선안 도출 및 적용
4. 처리 완료 후 `inbox/processed/`로 이동

---

## 2. Codebase 분석

Inbox 체크 완료 후:

1. **CLAUDE.md 확인**: 프로젝트 규칙 및 워크플로우
2. **Git 상태**: 현재 브랜치, 미커밋 변경사항
3. **이슈 확인**: `gh issue list --state open --limit 5`

---

## 3. 보고 형식

```markdown
## 세션 초기화 완료

### Inbox 상태
- [ ] 미처리 파일: N개 → IMPROVE_PROCESS 실행
- [x] 미처리 파일 없음

### Git 상태
- 브랜치: `main`
- 변경사항: N개 파일

### 열린 이슈
- #XX: 제목
- #YY: 제목
```

---

## 실행 순서 (엄격히 준수)

```
/init
  │
  ├─ Step 1: Inbox 체크 ← 최우선
  │     └─ 미처리 있으면 IMPROVE_PROCESS.md 실행
  │
  ├─ Step 2: CLAUDE.md 읽기
  │
  ├─ Step 3: Git 상태 확인
  │
  └─ Step 4: 보고서 출력
```

**Critical**: Step 1을 건너뛰면 안 됨!
