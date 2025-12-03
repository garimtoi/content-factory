# MCP Solutions Research Report

**작성일**: 2025-12-03
**버전**: 1.1.0
**목적**: Claude Code MCP 서버 솔루션 조사 및 권장 사항
**상태**: 설정 완료 (Docfork ✅, Exa ⏳, Mem0 ⏳)
**설치 가이드**: [`docs/guides/MCP_SETUP_GUIDE.md`](guides/MCP_SETUP_GUIDE.md)

---

## 1. Executive Summary

본 문서는 Claude Code 개발 환경 개선을 위한 MCP(Model Context Protocol) 서버 솔루션 조사 결과입니다.

### 조사 대상
| 카테고리 | 솔루션 |
|----------|--------|
| 문서 검색 | ref.tools, Docfork, Context7 |
| 웹 검색 | Exa AI |
| 메모리/컨텍스트 | Mem0, Antigravity, A-MEM |

### 최종 권장 구성
```json
{
  "mcpServers": {
    "docfork": { "무료, 9000+ 라이브러리" },
    "exa": { "$10 무료 크레딧, 코드 검색 특화" },
    "mem0": { "선택: 장기 메모리 필요 시" }
  }
}
```

---

## 2. 문서 검색 솔루션

### 2.1 비교표

| 솔루션 | 토큰 효율 | 라이브러리 | 비용 | MCP 지원 | 추천 |
|--------|----------|-----------|------|---------|------|
| **Docfork** | ⭐⭐⭐ | 9,000+ | 무료 | ✅ SSE | ✅ |
| **ref.tools** | ⭐⭐⭐⭐⭐ (95% 절감) | 큐레이션 | Free tier | ✅ SSE | ✅ |
| **Context7** | ⭐⭐ (10K 고정) | 20,000+ | Free tier | ✅ HTTP | △ |

### 2.2 Docfork (권장 - 기본)

**GitHub**: 오픈소스
**라이선스**: MIT
**특징**:
- 9,000+ 라이브러리 지원
- 완전 무료
- API 키 불필요

**설정**:
```json
{
  "mcpServers": {
    "docfork": {
      "type": "sse",
      "url": "https://mcp.docfork.com/sse"
    }
  }
}
```

### 2.3 ref.tools (권장 - 확장)

**GitHub**: [ref-tools/ref-tools-mcp](https://github.com/ref-tools/ref-tools-mcp)
**라이선스**: MIT
**Stars**: 801+

**핵심 가치**:
- **60-95% 토큰 절감** (500 vs 10,000 토큰)
- Search → Read 패턴 (정밀 타겟팅)
- Private GitHub 레포 지원

**도구**:
| 도구 | 설명 |
|------|------|
| `ref_search_documentation` | 기술 문서 검색 |
| `ref_read_url` | URL 마크다운 변환 |

**설정**:
```json
{
  "mcpServers": {
    "ref": {
      "type": "sse",
      "url": "https://api.ref.tools/mcp?apiKey=YOUR_API_KEY"
    }
  }
}
```

### 2.4 Context7 (기존)

**특징**:
- 20,000+ 라이브러리 (최대 지원)
- RAG 기반 대량 검색
- 라이브러리당 ~10K 토큰 사용

**단점**:
- 토큰 비효율 (dump and hope 방식)
- 2개 라이브러리 = 20K 토큰

---

## 3. 웹 검색 솔루션

### 3.1 Exa AI (권장)

**GitHub**: [exa-labs/exa-mcp-server](https://github.com/exa-labs/exa-mcp-server)
**웹사이트**: https://exa.ai
**라이선스**: MIT

**가격**:
| 티어 | 가격 | 내용 |
|------|------|------|
| Free | $10 크레딧 | 신규 가입 시 |
| Pay-per-use | $5/1000 검색 | 월 구독 없음 |

**핵심 도구**:
| 도구 | 설명 |
|------|------|
| `web_search_exa` | 실시간 웹 검색 |
| `get_code_context_exa` | **코드 예제/문서 검색 (핵심)** |
| `deep_search_exa` | 심층 검색 + 요약 |
| `company_research` | 회사 정보 크롤링 |

**`get_code_context_exa` 특징**:
- GitHub 1B+ 웹페이지 검색
- Stack Overflow 통합
- 코드 할루시네이션 방지
- 실제 작동 코드만 반환

**설정 (Windows)**:
```json
{
  "mcpServers": {
    "exa": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "exa-mcp-server"],
      "env": {
        "EXA_API_KEY": "${EXA_API_KEY}"
      }
    }
  }
}
```

### 3.2 기존 에이전트 연동

프로젝트에 `exa-search-specialist` 에이전트가 이미 존재:
- 경로: `.claude/agents/exa-search-specialist.md`
- **문제**: MCP 서버 미연결 → 실제 도구 호출 불가
- **해결**: Exa MCP 추가 시 에이전트 완전 활성화

---

## 4. 메모리/컨텍스트 솔루션

### 4.1 비교표

| 솔루션 | 타입 | 특징 | 비용 | 추천 |
|--------|------|------|------|------|
| **Claude Code 내장** | 체크포인트 | /rewind, Esc+Esc | 무료 | ✅ (기본) |
| **Mem0** | 장기 메모리 | +26% 정확도, 90% 토큰 절감 | Free tier | ✅ (확장) |
| **Antigravity** | 플랫폼 | Artifact 시스템, 무한 컨텍스트 | 무료 | △ (대안 IDE) |
| **A-MEM** | 연구 | Zettelkasten 방식 | 오픈소스 | - |

### 4.2 Claude Code 내장 체크포인트

**사용법**:
```
Esc + Esc  또는  /rewind
```

**복원 옵션**:
- Conversation only: 대화만 복원
- Code only: 코드만 복원
- Both: 둘 다 복원

**제한**:
- bash 명령어 (rm, mv, cp) 변경 추적 안 됨
- 세션 레벨 복구 (Git 대체 불가)

**세션 재개**:
```bash
claude --resume
```

### 4.3 Mem0 (선택적 확장)

**GitHub**: [mem0ai/mem0](https://github.com/mem0ai/mem0)
**Stars**: 26,000+
**라이선스**: Apache 2.0
**투자**: Y Combinator S24

**성능 (LOCOMO 벤치마크)**:
| 지표 | 수치 |
|------|------|
| 정확도 | +26% (OpenAI Memory 대비) |
| 응답 속도 | 91% 빠름 |
| 토큰 사용 | 90% 절감 |

**핵심 기능**:
- Multi-Level Memory: User, Session, Agent 상태 유지
- 세션 간 컨텍스트 영속성
- 시맨틱 검색

**MCP 설정**:
```json
{
  "mcpServers": {
    "mem0": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "mcp-mem0"],
      "env": {
        "MEM0_API_KEY": "${MEM0_API_KEY}"
      }
    }
  }
}
```

### 4.4 Google Antigravity

**출시**: 2025-11-18
**개발**: Google (Windsurf 팀 인수 $2.4B)
**가격**: 무료 (Rate limit 5시간마다 갱신)

**핵심 개념**:
- **Artifact 시스템**: 태스크 목록, 구현 계획, 스크린샷, 브라우저 녹화
- **Knowledge Base**: 컨텍스트/코드 스니펫 저장
- **무한 컨텍스트 패턴**: 외부 메모리 + 타겟 검색 + 토큰 예산

**지원 모델**: Gemini 3, Claude Sonnet 4.5, GPT-OSS

**평가**: 대안 IDE로 고려 가능, 현재 Claude Code 환경 유지 권장

---

## 5. 현재 프로젝트 설정

### 5.1 설정 파일

**경로**: `D:\AI\claude01\.mcp.json`

```json
{
  "mcpServers": {
    "docfork": {
      "type": "sse",
      "url": "https://mcp.docfork.com/sse"
    },
    "exa": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "exa-mcp-server"],
      "env": {
        "EXA_API_KEY": "${EXA_API_KEY}"
      }
    },
    "mem0": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "mcp-mem0"],
      "env": {
        "MEM0_API_KEY": "${MEM0_API_KEY}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### 5.2 환경 변수

**경로**: `.env.example`

```bash
# MCP Server API Keys
EXA_API_KEY=your-exa-api-key-here
MEM0_API_KEY=your-mem0-api-key-here
OPENAI_API_KEY=your-openai-api-key-here  # Mem0 임베딩용
```

### 5.3 상태

| 서버 | 상태 | 비고 |
|------|------|------|
| **docfork** | ✅ 활성 | 무료, API 키 불필요 |
| **exa** | ⏳ 대기 | API 키 설정 필요 |
| **mem0** | ⏳ 대기 | API 키 설정 필요 (장기 메모리) |

---

## 6. API 키 발급 가이드

> **상세 설치 가이드**: [`docs/guides/MCP_SETUP_GUIDE.md`](guides/MCP_SETUP_GUIDE.md)

### Exa AI
1. https://dashboard.exa.ai 접속
2. 회원가입 (Google/GitHub)
3. API Keys → Create New Key
4. $10 무료 크레딧 자동 지급

### Mem0 (선택)
1. https://app.mem0.ai 접속
2. 회원가입
3. Settings → API Keys

### ref.tools (선택)
1. https://ref.tools 접속
2. 회원가입
3. Dashboard → API Key

---

## 7. 활성화 후 사용 가능한 도구

### Docfork
| 도구 | 기능 |
|------|------|
| `mcp__docfork__search` | 라이브러리 문서 검색 |
| `mcp__docfork__fetch` | URL 콘텐츠 변환 |

### Exa (API 키 설정 후)
| 도구 | 기능 |
|------|------|
| `mcp__exa__web_search_exa` | 실시간 웹 검색 |
| `mcp__exa__get_code_context_exa` | 코드 예제/문서 검색 |
| `mcp__exa__deep_search_exa` | 심층 검색 + 요약 |

### Mem0 (설정 시)
| 도구 | 기능 |
|------|------|
| `mcp__mem0__save_memory` | 메모리 저장 |
| `mcp__mem0__search_memory` | 메모리 검색 |
| `mcp__mem0__get_memories` | 메모리 조회 |

---

## 8. 권장 사용 시나리오

| 시나리오 | 도구 조합 |
|----------|----------|
| **라이브러리 문서 확인** | Docfork |
| **최신 기술 트렌드 조사** | Exa `web_search_exa` |
| **코드 예제 검색** | Exa `get_code_context_exa` |
| **세션 내 롤백** | Claude Code `/rewind` |
| **세션 간 컨텍스트 유지** | Mem0 (선택) |

---

## 9. References

### 공식 문서
- [Claude Code Checkpointing](https://docs.claude.com/en/docs/claude-code/checkpointing)
- [Exa AI Docs](https://docs.exa.ai/reference/getting-started)
- [Mem0 Docs](https://docs.mem0.ai)
- [ref.tools Docs](https://docs.ref.tools)

### GitHub 레포지토리
- [exa-labs/exa-mcp-server](https://github.com/exa-labs/exa-mcp-server)
- [mem0ai/mem0](https://github.com/mem0ai/mem0)
- [ref-tools/ref-tools-mcp](https://github.com/ref-tools/ref-tools-mcp)
- [docfork/docfork-mcp](https://github.com/docfork/docfork-mcp)

### 비교 분석
- [Ref vs Context7](https://docs.ref.tools/comparison/context7)
- [Top Context7 Alternatives](https://fastmcp.me/blog/top-context7-mcp-alternatives)
- [Antigravity Infinite Context Guide](https://skywork.ai/blog/ai-agent/antigravity-infinite-context-window-ultimate-guide/)

### 플랫폼
- [Google Antigravity](https://developers.googleblog.com/en/build-with-google-antigravity-our-new-agentic-development-platform/)
- [Exa Pricing](https://exa.ai/pricing)
- [Mem0 OpenMemory MCP](https://mem0.ai/blog/introducing-openmemory-mcp)

---

## Changelog

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.1.0 | 2025-12-03 | Mem0 MCP 설정 추가, 맥락 이해 가능성 검토 |
| 1.0.0 | 2025-12-03 | 초기 작성 |
