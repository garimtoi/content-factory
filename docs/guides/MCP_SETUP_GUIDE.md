# MCP Server Setup Guide

API 키가 필요한 MCP 서버 설치 가이드입니다.

**현재 상태**: `.mcp.json` 설정 완료, API 키만 추가하면 활성화

---

## 1. Exa AI (웹/코드 검색)

### 1.1 개요

| 항목 | 내용 |
|------|------|
| **용도** | 실시간 웹 검색, 코드 예제 검색 |
| **비용** | $10 무료 크레딧 (신규 가입) |
| **핵심 기능** | `get_code_context_exa` - GitHub 1B+ 페이지 검색 |

### 1.2 API 키 발급

1. **대시보드 접속**: https://dashboard.exa.ai

2. **회원가입**
   - Google 또는 GitHub 계정으로 가입
   - 이메일 인증 완료

3. **API 키 생성**
   - 좌측 메뉴: `API Keys`
   - `Create New Key` 클릭
   - 키 이름 입력 (예: `claude-code-dev`)
   - 생성된 키 복사 (한 번만 표시됨)

4. **무료 크레딧 확인**
   - `Billing` 메뉴에서 $10 크레딧 자동 지급 확인
   - Pay-per-use: $5/1000 검색

### 1.3 환경 변수 설정

**PowerShell (현재 세션)**:
```powershell
$env:EXA_API_KEY = "your-exa-api-key-here"
```

**영구 설정 (사용자 환경변수)**:
```powershell
[Environment]::SetEnvironmentVariable("EXA_API_KEY", "your-exa-api-key-here", "User")
```

**`.env` 파일** (프로젝트 루트):
```bash
EXA_API_KEY=your-exa-api-key-here
```

### 1.4 설치 검증

```powershell
# Claude Code 재시작 후
claude

# MCP 서버 확인
/mcp

# 도구 테스트 (Claude Code 내에서)
# "Exa로 React hooks 예제 검색해줘"
```

**활성화 시 사용 가능한 도구**:
| 도구 | 기능 |
|------|------|
| `mcp__exa__web_search_exa` | 실시간 웹 검색 |
| `mcp__exa__get_code_context_exa` | 코드 예제/문서 검색 |
| `mcp__exa__deep_search_exa` | 심층 검색 + 요약 |

---

## 2. Mem0 (장기 메모리)

### 2.1 개요

| 항목 | 내용 |
|------|------|
| **용도** | 세션 간 컨텍스트 유지, 장기 메모리 |
| **비용** | Free tier 제공 |
| **성능** | +26% 정확도, 90% 토큰 절감 |

### 2.2 API 키 발급

1. **앱 접속**: https://app.mem0.ai

2. **회원가입**
   - Google 또는 GitHub 계정으로 가입
   - 또는 이메일 가입

3. **API 키 생성**
   - 우측 상단 프로필 → `Settings`
   - `API Keys` 탭
   - `Generate New Key` 클릭
   - 키 복사

### 2.3 OpenAI API 키 (선택)

Mem0 클라우드 사용 시 OpenAI 키는 **선택 사항**입니다.
- Mem0 클라우드: 자체 임베딩 제공 → OpenAI 불필요
- Self-hosted Mem0: OpenAI 임베딩 필요

**OpenAI 키 발급** (필요 시):
1. https://platform.openai.com/api-keys 접속
2. `Create new secret key` 클릭
3. 키 복사

### 2.4 환경 변수 설정

**PowerShell (현재 세션)**:
```powershell
$env:MEM0_API_KEY = "your-mem0-api-key-here"
# OpenAI는 Mem0 클라우드 사용 시 불필요
# $env:OPENAI_API_KEY = "your-openai-api-key-here"
```

**영구 설정**:
```powershell
[Environment]::SetEnvironmentVariable("MEM0_API_KEY", "your-mem0-api-key-here", "User")
```

**`.env` 파일**:
```bash
MEM0_API_KEY=your-mem0-api-key-here
# OPENAI_API_KEY=your-openai-api-key-here  # 선택
```

### 2.5 설치 검증

```powershell
# Claude Code 재시작
claude

# MCP 서버 확인
/mcp

# 메모리 저장 테스트 (Claude Code 내에서)
# "이 프로젝트는 포커 VOD 분석 시스템이라고 기억해줘"

# 메모리 조회 테스트
# "이 프로젝트가 뭐였지?"
```

**활성화 시 사용 가능한 도구**:
| 도구 | 기능 |
|------|------|
| `mcp__mem0__save_memory` | 메모리 저장 |
| `mcp__mem0__search_memory` | 메모리 검색 |
| `mcp__mem0__get_memories` | 전체 메모리 조회 |

---

## 3. 빠른 설정 (한 번에)

### 3.1 모든 환경 변수 설정

```powershell
# PowerShell에서 한 번에 설정
$env:EXA_API_KEY = "exa-key-here"
$env:MEM0_API_KEY = "mem0-key-here"

# 영구 저장 (선택)
[Environment]::SetEnvironmentVariable("EXA_API_KEY", "exa-key-here", "User")
[Environment]::SetEnvironmentVariable("MEM0_API_KEY", "mem0-key-here", "User")
```

### 3.2 Claude Code 재시작

```powershell
# 현재 세션 종료 후
claude
```

### 3.3 전체 검증

```powershell
# MCP 서버 상태 확인
/mcp
```

예상 출력:
```
MCP Servers:
✅ docfork (SSE) - 활성
✅ exa (stdio) - 활성
✅ mem0 (stdio) - 활성
```

---

## 4. 문제 해결

### 4.1 MCP 서버 연결 실패

**증상**: `Connection closed` 또는 서버 미표시

**해결**:
1. 환경 변수 확인
   ```powershell
   echo $env:EXA_API_KEY
   echo $env:MEM0_API_KEY
   ```

2. `.mcp.json` 확인
   ```powershell
   cat D:\AI\claude01\.mcp.json
   ```

3. Node.js 설치 확인
   ```powershell
   node --version  # v18+ 필요
   npm --version
   ```

4. Claude Code 재시작

### 4.2 API 키 오류

**증상**: `401 Unauthorized` 또는 `Invalid API Key`

**해결**:
- API 키 재발급
- 환경 변수 재설정
- 키에 공백/줄바꿈 없는지 확인

### 4.3 npx 실행 오류

**증상**: `npx: command not found`

**해결**:
```powershell
# Node.js 재설치 (npm 포함)
winget install OpenJS.NodeJS.LTS

# 터미널 재시작
```

---

## 5. 참고 자료

| 리소스 | URL |
|--------|-----|
| Exa 문서 | https://docs.exa.ai |
| Exa 대시보드 | https://dashboard.exa.ai |
| Mem0 문서 | https://docs.mem0.ai |
| Mem0 앱 | https://app.mem0.ai |
| MCP 솔루션 조사 | `docs/MCP_SOLUTIONS_RESEARCH.md` |

---

## Changelog

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0.0 | 2025-12-03 | 초기 작성 |
