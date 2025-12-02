# Claude Code Workflow Configuration

**Claude Code**를 위한 전역 워크플로우 및 설정 메타 레포지토리입니다.

![Version](https://img.shields.io/badge/version-1.0.0-blue) ![Last Updated](https://img.shields.io/badge/updated-2025--12--02-green)

> **⚠️ 중요**: 이 레포지토리는 실제 제품 코드가 아닌, **개발 방법론(Workflow)**과 **자동화 도구(Scripts)**를 담고 있습니다.

---

## 🚀 Quick Start

### 1. 핵심 가이드 (AI & Human)
*   **[CLAUDE.md](CLAUDE.md)**: **(필독)** 프로젝트의 핵심 규칙 및 워크플로우 파이프라인.
*   **[docs/QUICK_START_GUIDE.md](docs/QUICK_START_GUIDE.md)**: 5분 안에 시작하는 빠른 가이드.

### 2. 주요 문서 (Documentation)
*   **[docs/WORKFLOWS/](docs/WORKFLOWS/)**: 바로 사용 가능한 워크플로우 레시피 (Bug Fix, Feature 등).
*   **[docs/GITHUB_WORKFLOW/](docs/GITHUB_WORKFLOW/)**: GitHub 연동 및 이슈 관리 가이드.
*   **[docs/AGENTS_REFERENCE.md](docs/AGENTS_REFERENCE.md)**: 사용 가능한 에이전트 목록.

### 3. 도구 (Tools)
*   **Scripts**: `scripts/` 디렉토리에 Windows Native(PowerShell) 및 Python 자동화 스크립트 포함.
*   **Plugins**: `.claude-plugin/` 및 `.claude/` 디렉토리에서 플러그인 관리.

---

## 📂 Repository Structure

```
.
├── CLAUDE.md                    # Core Workflow Definition
├── README.md                    # Entry Point (This file)
├── docs/                        # Detailed Documentation
│   ├── ARCHIVE/                 # Archived Reports
│   ├── GITHUB_WORKFLOW/         # GitHub Integration Docs
│   └── WORKFLOWS/               # Actionable Recipes
├── scripts/                     # Automation Scripts (PowerShell/Python)
├── .claude/                     # Claude Code Extensions
└── .claude-plugin/              # Plugin Registry
```

## 🤝 Contribution
개선 제안은 Issue 또는 PR로 제출해 주세요.
