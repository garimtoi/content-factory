# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Archive Analyzer는 OTT 솔루션을 위한 미디어 아카이브 분석 도구입니다. SMB 네트워크를 통해 원격 NAS에 저장된 미디어 파일(18TB+)의 메타데이터를 추출하고 카탈로그를 생성합니다.

**주요 대상**: WSOP, HCL, PAD 등 포커 방송 콘텐츠 아카이브 (1,400+ 파일)

## Build & Test Commands

```powershell
# 의존성 설치 (용도별)
pip install -e ".[dev,media]"        # 개발 + 미디어 분석
pip install -e ".[dev,media,search]" # 전체 (MeiliSearch 포함)

# 테스트 실행
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=src/archive_analyzer --cov-report=term

# 단일 테스트
pytest tests/test_scanner.py -v
pytest tests/test_media_extractor.py::test_ffprobe_extract -v

# 린터/포매터/타입
ruff check src/
black --check src/
mypy src/archive_analyzer/
```

## Architecture

```
src/archive_analyzer/
├── config.py             # SMBConfig, AnalyzerConfig (환경변수/JSON 로드)
├── smb_connector.py      # SMB 2/3 네트워크 연결 (smbprotocol 기반)
├── file_classifier.py    # 파일 유형 분류 (video, audio, subtitle, metadata)
├── scanner.py            # 재귀 디렉토리 스캔, 체크포인트 기반 재개
├── database.py           # SQLite 저장 (6개 테이블)
├── media_extractor.py    # FFprobe 기반 메타데이터 추출
├── report_generator.py   # Markdown/JSON/Console 리포트 생성
├── search.py             # MeiliSearch 인덱싱/검색 서비스
├── sync.py               # pokervod.db 동기화 모듈
├── sheets_sync.py        # Google Sheets ↔ SQLite 양방향 동기화
├── archive_hands_sync.py # 아카이브 팀 시트 → hands 테이블 동기화
├── title_generator.py    # 시청자용 제목 자동 생성 (규칙 기반)
└── api.py                # FastAPI REST API (검색/동기화)
```

### 데이터 흐름

1. `SMBConnector` → SMB 세션 관리, 파일 탐색
2. `ArchiveScanner` → 재귀 스캔, `Database`에 파일 정보 저장
3. `SMBMediaExtractor` → 파일 일부 다운로드 (512KB) → FFprobe 분석
4. `ReportGenerator` → 통계 집계, 스트리밍 적합성 평가
5. `SearchService` → MeiliSearch 인덱싱/검색
6. `SyncService` → pokervod.db 동기화
7. `SheetsSyncService` → Google Sheets 양방향 동기화
8. `ArchiveHandsSync` → 아카이브 팀 시트 → hands 테이블

### 주요 클래스

| 클래스 | 역할 | 위치 |
|--------|------|------|
| `SMBConnector` | SMB 연결/재시도/디렉토리 스캔 | `smb_connector.py` |
| `ArchiveScanner` | 체크포인트 기반 스캔 | `scanner.py` |
| `FFprobeExtractor` | 로컬 파일 메타데이터 추출 | `media_extractor.py` |
| `SMBMediaExtractor` | SMB 파일 → 임시 다운로드 → 분석 | `media_extractor.py` |
| `ReportGenerator` | DB 쿼리 → 리포트 생성 | `report_generator.py` |
| `SearchService` | MeiliSearch 검색 API | `search.py` |
| `SyncService` | archive.db → pokervod.db 동기화 | `sync.py` |
| `SheetsSyncService` | Google Sheets ↔ SQLite 양방향 동기화 | `sheets_sync.py` |
| `ArchiveHandsSync` | 아카이브 팀 시트 → hands 동기화 | `archive_hands_sync.py` |
| `TitleGenerator` | 규칙 기반 시청자용 제목 생성 | `title_generator.py` |

## Key Scripts

```powershell
# 핵심 워크플로우
python scripts/run_scan.py                    # 아카이브 스캔
python scripts/extract_metadata_netdrive.py   # 네트워크 드라이브 메타데이터 추출
python scripts/generate_report.py             # 리포트 생성
python scripts/retry_failed.py                # 실패 항목 재처리

# 검색/동기화
python scripts/index_to_meilisearch.py        # MeiliSearch 인덱싱
python scripts/sync_to_pokervod.py            # pokervod.db 동기화

# iconik 메타데이터 통합
python scripts/import_iconik_metadata.py      # iconik CSV 임포트
python scripts/clip_matcher.py                # 클립-파일 매칭
python scripts/match_by_path.py               # 경로 기반 매칭

# 유틸리티
python scripts/test_smb.py                    # SMB 연결 테스트
```

## Configuration

SMB 연결 설정은 환경변수 또는 JSON 파일로 관리:

```bash
# 환경변수
SMB_SERVER=10.10.100.122
SMB_SHARE=docker
SMB_USERNAME=GGP
SMB_PASSWORD=****
ARCHIVE_PATH=GGPNAs/ARCHIVE
```

```python
# 코드에서 로드
config = AnalyzerConfig.from_env()
config = AnalyzerConfig.from_file("config.json")
```

## Database Schema

### 내부 DB: archive.db
| 테이블 | 용도 |
|--------|------|
| `files` | 파일 경로, 크기, 유형, 스캔 상태 |
| `media_info` | 비디오/오디오 코덱, 해상도, 재생시간, 비트레이트 |
| `scan_checkpoints` | 스캔 재개를 위한 체크포인트 |
| `scan_stats` | 스캔별 통계 |
| `clip_metadata` | iconik CSV 임포트 (클립 태그, 플레이어, 핸드 정보) |
| `media_files` | media_metadata.csv 경로 기반 매칭용 |

### 외부 DB 연동: pokervod.db

**경로**: `d:/AI/claude01/qwen_hand_analysis/data/pokervod.db`
**소유자**: `qwen_hand_analysis` 레포 (OTT 플랫폼 마스터 DB)

```
archive.db                              pokervod.db
──────────                              ───────────
files.path ─────────────────────────→ files.nas_path
media_info.video_codec ─────────────→ files.codec
media_info.width/height ────────────→ files.resolution
media_info.duration_seconds ────────→ files.duration_sec
clip_metadata.players_tags ─────────→ hands.players (JSON)
clip_metadata.hand_grade ───────────→ hands.tags (JSON)
```

**스키마 변경 시 반드시 `docs/DATABASE_SCHEMA.md` 문서 업데이트 필요!**

동기화 스크립트: `scripts/sync_to_pokervod.py`

## External Dependencies

- **FFprobe**: 시스템 PATH에 설치 필요
- **Python**: 3.10+ 필수
- **smbprotocol**: SMB 2/3 네트워크 접근
- **rapidfuzz**: 파일명 퍼지 매칭 (클립 매칭용)
- **gspread**: Google Sheets API 클라이언트 (동기화 모듈)

## Streaming Compatibility

OTT 호환 판정 기준 (`ReportGenerator`에서 사용):
- **코덱**: h264, hevc, vp9, av1
- **컨테이너**: mp4, webm, mov
- MXF 등 방송용 포맷은 트랜스코딩 필요로 분류

## Search (MeiliSearch)

### 검색 서비스 실행

```powershell
# MeiliSearch 서버 시작 (Docker)
docker-compose up -d

# 데이터 인덱싱
python scripts/index_to_meilisearch.py --db-path data/output/archive.db

# 인덱스 통계 확인
python scripts/index_to_meilisearch.py --stats

# API 서버 시작
uvicorn archive_analyzer.api:app --reload --port 8000
```

### 검색 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 서버 상태 확인 |
| `/stats` | GET | 인덱스 통계 조회 |
| `/search/files` | GET | 파일 검색 (파일명, 경로, 폴더) |
| `/search/media` | GET | 미디어 정보 검색 (코덱, 해상도) |
| `/search/clips` | GET | 클립 메타데이터 검색 (플레이어, 이벤트) |
| `/index` | POST | DB 인덱싱 실행 |
| `/clear` | DELETE | 인덱스 초기화 |

### 검색 예시

```bash
# 파일 검색
curl "http://localhost:8000/search/files?q=WSOP&file_type=video"

# 미디어 검색 (1080p 영상)
curl "http://localhost:8000/search/media?q=hevc&resolution=1080p"

# 클립 검색 (플레이어)
curl "http://localhost:8000/search/clips?q=Phil%20Ivey&project_name=WSOP"
```

## Sync (pokervod.db 동기화)

### 동기화 명령어

```powershell
# 동기화 통계 확인
python scripts/sync_to_pokervod.py --stats

# 시뮬레이션 (dry-run)
python scripts/sync_to_pokervod.py --dry-run

# 전체 동기화 실행
python scripts/sync_to_pokervod.py

# 파일만 동기화
python scripts/sync_to_pokervod.py --files-only

# 카탈로그만 동기화
python scripts/sync_to_pokervod.py --catalogs-only
```

### 동기화 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/sync/stats` | GET | 동기화 통계 조회 |
| `/sync/files` | POST | 파일 동기화 |
| `/sync/catalogs` | POST | 카탈로그 동기화 |
| `/sync/all` | POST | 전체 동기화 |

### 다단계 서브카탈로그 분류

파일 경로에서 자동으로 catalog/subcatalog/depth를 추출합니다 (최대 3단계):

| 경로 패턴 | subcatalog_id | depth |
|-----------|---------------|-------|
| `WSOP/WSOP-BR` | wsop-br | 1 |
| `WSOP/WSOP-BR/WSOP-EUROPE` | wsop-europe | 2 |
| `WSOP/WSOP-BR/WSOP-EUROPE/2024` | wsop-europe-2024 | 3 |
| `WSOP/WSOP ARCHIVE` | wsop-archive | 1 |
| `WSOP/WSOP ARCHIVE/2008` | wsop-archive-2003-2010 | 2 |
| `HCL/2025` | hcl-2025 | 1 |
| `PAD/Season 12` | pad-s12 | 1 |

마이그레이션 스크립트: `scripts/migrate_subcatalogs_v2.py`

## Google Sheets 동기화

### 양방향 동기화 (sheets_sync.py)

```powershell
# 초기 동기화 (DB → Sheet)
python -m archive_analyzer.sheets_sync --init

# 양방향 동기화 실행
python -m archive_analyzer.sheets_sync --sync

# 백그라운드 데몬 모드
python -m archive_analyzer.sheets_sync --daemon
```

### 아카이브 팀 Hands 동기화 (archive_hands_sync.py)

```powershell
# 동기화 실행
python -m archive_analyzer.archive_hands_sync --sync

# Dry-run (미리보기)
python -m archive_analyzer.archive_hands_sync --dry-run

# 데몬 모드 (기본 1시간 간격)
python -m archive_analyzer.archive_hands_sync --daemon

# 30분 간격 데몬
python -m archive_analyzer.archive_hands_sync --daemon --interval 1800
```

### Docker 동기화 서비스

```powershell
# 동기화 서비스 시작 (Watchtower 자동 업데이트 포함)
docker-compose -f docker-compose.sync.yml up -d

# 로그 확인
docker logs -f sheets-sync
```

### 환경변수 (Google Sheets 동기화)

| 변수 | 용도 | 예시 |
|------|------|------|
| `CREDENTIALS_PATH` | GCP 서비스 계정 JSON | `config/gcp-service-account.json` |
| `SPREADSHEET_ID` | Google Sheets ID | `1TW2ON5CQyIrL8...` |
| `SYNC_INTERVAL` | 동기화 간격 (초) | `120` |
| `DB_PATH` | SQLite 경로 | `data/pokervod.db` |

## Admin (Web UI + Authentication)

### Network Accessible Server

동일 네트워크의 모든 사용자가 접속할 수 있는 관리 서버입니다.

```powershell
# 환경변수 설정 후 실행
$env:GOOGLE_CLIENT_ID = "your-client-id"
$env:GOOGLE_CLIENT_SECRET = "your-secret"
$env:ADMIN_EMAILS = "admin@example.com"

# 관리 서버 시작 (API + DB Manager)
python scripts/start_admin.py
```

### URLs (Network Access)

서버 IP: `10.10.100.74` (자동 감지)

| URL | Description |
|-----|-------------|
| `http://10.10.100.74:8000/admin/` | Admin Dashboard |
| `http://10.10.100.74:8000/auth/login` | Google OAuth Login |
| `http://10.10.100.74:8000/admin/db` | Database Manager |
| `http://10.10.100.74:8000/docs` | API Documentation |
| `http://10.10.100.74:8088` | pokervod.db (Direct) |
| `http://10.10.100.74:8089` | archive.db (Direct) |

### User Roles

| Role | Permissions |
|------|-------------|
| `pending` | Awaiting approval |
| `viewer` | Read-only access |
| `editor` | Read/Write access |
| `admin` | Full access + user management |

### Google Cloud Console Setup

1. https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add redirect URI: `http://10.10.100.74:8000/auth/callback`

### Direct DB Access (without auth)

```powershell
# pokervod.db
python -m sqlite_web d:/AI/claude01/qwen_hand_analysis/data/pokervod.db --host 0.0.0.0 --port 8088

# archive.db
python -m sqlite_web d:/AI/claude01/archive-analyzer/data/output/archive.db --host 0.0.0.0 --port 8089
```

## Roadmap

- **Phase 1: 검색 기능** ✅ (MeiliSearch, FastAPI)
- **Phase 2: pokervod.db 동기화** ✅ (sync.py, REST API)
- **Phase 2.5: Admin UI** ✅ (Google OAuth, User Management, sqlite-web)
- **Phase 2.6: Google Sheets 동기화** ✅ (sheets_sync.py, archive_hands_sync.py, Docker)
- **Phase 3: AI 기능** (예정) - Whisper 전사, YOLOv8 카드 감지

## Documentation

| 문서 | 설명 |
|------|------|
| `docs/DATABASE_SCHEMA.md` | DB 스키마 및 연동 관계 (스키마 변경 시 필수 업데이트) |
| `docs/DATABASE_SCHEMA_V2.md` | V2 스키마 설계 (단순화된 계층 구조) |
| `docs/archive_structure.md` | 아카이브 폴더 구조 및 태그 스키마 |
| `docs/MAM_SOLUTIONS_RESEARCH.md` | 오픈소스 MAM 솔루션 비교 |
| `docs/MAM_ARCHITECTURE_PATTERNS.md` | Self-hosted 아키텍처 패턴 |
