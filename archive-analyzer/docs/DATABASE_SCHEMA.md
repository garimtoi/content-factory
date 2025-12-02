# Database Schema Documentation

> **Last Updated**: 2025-12-02
> **Version**: 1.5.0

이 문서는 archive-analyzer와 연동 레포지토리 간 DB 스키마를 정의합니다.
**스키마 변경 시 반드시 이 문서를 업데이트하고 관련 레포에 공유해야 합니다.**

---

## 연동 레포지토리

| 레포지토리 | DB 파일 | 역할 |
|-----------|---------|------|
| `archive-analyzer` | `data/output/archive.db` | 아카이브 스캔/메타데이터 |
| `qwen_hand_analysis` | `data/pokervod.db` | OTT 플랫폼 (마스터 DB) |

---

## 1. pokervod.db (OTT 마스터 DB)

**경로**: `d:/AI/claude01/qwen_hand_analysis/data/pokervod.db`
**소유자**: `qwen_hand_analysis` 레포

### 1.1 ERD

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  catalogs   │────<│  subcatalogs │     │   players   │
│─────────────│     │──────────────│     │─────────────│
│ id (PK)     │     │ id (PK)      │     │ name (PK)   │
│ name        │     │ catalog_id   │     │ display_name│
│ description │     │ name         │     │ country     │
└─────────────┘     │ display_order│     │ total_hands │
       │            └──────────────┘     └─────────────┘
       │                   │                    │
       ▼                   ▼                    │
┌─────────────────┐  ┌─────────────┐           │
│   tournaments   │  │   events    │           │
│─────────────────│  │─────────────│           │
│ id (PK)         │  │ id (PK)     │           │
│ catalog_id (FK) │──│ tournament_ │           │
│ subcatalog_id   │  │ id (FK)     │           │
│ name            │  │ name        │           │
│ year            │  │ day         │           │
│ location        │  │ session     │           │
└─────────────────┘  └──────┬──────┘           │
                            │                  │
                            ▼                  │
                     ┌─────────────┐           │
                     │    files    │           │
                     │─────────────│           │
                     │ id (PK)     │           │
                     │ event_id(FK)│           │
                     │ nas_path    │◀══════════╪═══ archive-analyzer 동기화
                     │ filename    │           │
                     │ analysis_   │           │
                     │ status      │           │
                     └──────┬──────┘           │
                            │                  │
                            ▼                  │
                     ┌─────────────┐           │
                     │    hands    │───────────┘
                     │─────────────│    (players JSON)
                     │ id (PK)     │
                     │ file_id(FK) │
                     │ start_sec   │
                     │ end_sec     │
                     │ winner      │
                     │ pot_size_bb │
                     │ is_all_in   │
                     └─────────────┘
```

### 1.2 테이블 상세

#### catalogs
카탈로그 (최상위 분류): WSOP, HCL, PAD 등

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 고유 식별자 |
| name | VARCHAR(200) | 카탈로그명 |
| description | TEXT | 설명 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식 (rule_based/ai_generated/manual)** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |

#### subcatalogs
서브 카탈로그 (다단계 계층 구조): 자기 참조를 통한 무제한 깊이 지원

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 고유 식별자 |
| catalog_id | VARCHAR(50) FK | 최상위 카탈로그 |
| **parent_id** | VARCHAR(100) FK NULL | **상위 서브카탈로그 (NULL이면 1단계)** |
| name | VARCHAR(200) | 서브카탈로그명 |
| description | TEXT | 설명 |
| **depth** | INTEGER | **계층 깊이 (1, 2, 3...)** |
| **path** | TEXT | **전체 경로 (예: wsop/wsop-br/wsop-europe)** |
| **sub1** | VARCHAR(200) | **1단계 서브카탈로그명** |
| **sub2** | VARCHAR(200) | **2단계 서브카탈로그명** |
| **sub3** | VARCHAR(200) | **3단계 서브카탈로그명** |
| **full_path_name** | VARCHAR(500) | **전체 경로명 (예: WSOP > WSOP-BR > Europe)** |
| display_order | INTEGER | 표시 순서 |
| tournament_count | INTEGER | 토너먼트 수 |
| file_count | INTEGER | 파일 수 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |
| search_vector | TEXT | 검색용 벡터 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |

##### 계층 구조 예시

```
WSOP (catalog)
├── WSOP ARCHIVE (subcatalog, depth=1, parent_id=NULL)
├── WSOP-BR (subcatalog, depth=1, parent_id=NULL)
│   ├── WSOP-EUROPE (subcatalog, depth=2, parent_id=wsop-br)
│   ├── WSOP-PARADISE (subcatalog, depth=2, parent_id=wsop-br)
│   └── WSOP-LAS VEGAS (subcatalog, depth=2, parent_id=wsop-br)
│       └── 2024 (subcatalog, depth=3, parent_id=wsop-las-vegas)
├── WSOP-C (subcatalog, depth=1, parent_id=NULL)
└── WSOP-SC (subcatalog, depth=1, parent_id=NULL)
```

##### 쿼리 예시

```sql
-- 특정 카탈로그의 모든 하위 항목 (재귀 CTE)
WITH RECURSIVE subcatalog_tree AS (
    SELECT id, parent_id, name, depth, path
    FROM subcatalogs
    WHERE catalog_id = 'WSOP' AND parent_id IS NULL

    UNION ALL

    SELECT s.id, s.parent_id, s.name, s.depth, s.path
    FROM subcatalogs s
    JOIN subcatalog_tree t ON s.parent_id = t.id
)
SELECT * FROM subcatalog_tree ORDER BY path;

-- 특정 서브카탈로그의 모든 상위 항목
WITH RECURSIVE parents AS (
    SELECT id, parent_id, name, depth
    FROM subcatalogs
    WHERE id = 'wsop-europe'

    UNION ALL

    SELECT s.id, s.parent_id, s.name, s.depth
    FROM subcatalogs s
    JOIN parents p ON s.id = p.parent_id
)
SELECT * FROM parents ORDER BY depth;
```

#### tournaments
토너먼트: 연도별 대회

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 고유 식별자 |
| catalog_id | VARCHAR(50) FK | 카탈로그 |
| subcatalog_id | VARCHAR(100) | 서브카탈로그 |
| name | VARCHAR(200) | 토너먼트명 |
| year | INTEGER | 개최 연도 |
| location | VARCHAR(100) | 개최 장소 |
| start_date | TIMESTAMP | 시작일 |
| end_date | TIMESTAMP | 종료일 |
| event_count | INTEGER | 이벤트 수 |

#### events
이벤트: 토너먼트 내 개별 이벤트 (Main Event Day 1, Side Event 등)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(150) PK | 고유 식별자 |
| tournament_id | VARCHAR(100) FK | 토너먼트 |
| name | VARCHAR(200) | 이벤트명 |
| day | INTEGER | 일차 |
| session | VARCHAR(50) | 세션 |
| file_count | INTEGER | 파일 수 |

#### files
파일: 실제 미디어 파일

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(200) PK | 고유 식별자 |
| event_id | VARCHAR(150) FK | 이벤트 |
| **nas_path** | TEXT UNIQUE | **NAS 경로 (archive-analyzer 연동 키)** |
| filename | VARCHAR(500) | 파일명 |
| size_bytes | BIGINT | 파일 크기 |
| duration_sec | FLOAT | 재생 시간 (초) |
| resolution | VARCHAR(20) | 해상도 |
| codec | VARCHAR(50) | 코덱 |
| fps | FLOAT | 프레임레이트 |
| bitrate_kbps | INTEGER | 비트레이트 |
| analysis_status | VARCHAR(20) | 분석 상태 (pending/analyzing/completed/failed) |
| analysis_error | TEXT | 분석 오류 메시지 |
| analyzed_at | TIMESTAMP | 분석 일시 |
| hands_count | INTEGER | 핸드 수 |
| view_count | INTEGER | 조회수 |
| last_viewed_at | TIMESTAMP | 마지막 조회 일시 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |
| search_vector | TEXT | 검색용 벡터 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **display_subtitle** | VARCHAR(300) | **시청자용 부제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식 (rule_based/ai_generated/manual)** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |

#### hands
핸드: 포커 핸드 정보

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 고유 식별자 |
| file_id | VARCHAR(200) FK | 파일 |
| phh_hand_id | VARCHAR(200) | PHH 핸드 ID |
| hand_number | INTEGER | 핸드 번호 |
| start_sec | FLOAT | 시작 시간 (초) |
| end_sec | FLOAT | 종료 시간 (초) |
| winner | VARCHAR(100) | 승자 |
| pot_size_bb | FLOAT | 팟 크기 (BB) |
| is_all_in | BOOLEAN | 올인 여부 |
| is_showdown | BOOLEAN | 쇼다운 여부 |
| players | JSON | 참가 플레이어 |
| cards_shown | JSON | 공개된 카드 |
| board | TEXT | 보드 카드 |
| highlight_score | FLOAT | 하이라이트 점수 |
| tags | JSON | 태그 |
| created_at | TIMESTAMP | 생성일시 |
| search_vector | TEXT | 검색용 벡터 |
| **display_title** | VARCHAR(300) | **시청자용 표시 제목** |
| **title_source** | VARCHAR(20) | **제목 생성 방식 (rule_based/ai_generated/manual)** |
| **title_verified** | BOOLEAN | **수동 검수 완료 여부** |

#### players
플레이어: 포커 플레이어 정보

| 컬럼 | 타입 | 설명 |
|------|------|------|
| name | VARCHAR(100) PK | 이름 |
| display_name | VARCHAR(200) | 표시 이름 |
| country | VARCHAR(50) | 국가 |
| total_hands | INTEGER | 총 핸드 수 |
| total_wins | INTEGER | 총 승리 수 |
| total_all_ins | INTEGER | 총 올인 수 |
| avg_pot_bb | FLOAT | 평균 팟 크기 |

---

## 2. archive.db (아카이브 스캔 DB)

**경로**: `d:/AI/claude01/archive-analyzer/data/output/archive.db`
**소유자**: `archive-analyzer` 레포

### 2.1 테이블 목록

| 테이블 | 용도 | pokervod.db 연동 |
|--------|------|------------------|
| files | 파일 경로/크기/유형 | → `files.nas_path` |
| media_info | 미디어 메타데이터 | → `files.codec/resolution` |
| scan_checkpoints | 스캔 재개용 | 내부 전용 |
| scan_stats | 스캔 통계 | 내부 전용 |
| clip_metadata | iconik 클립 메타데이터 | → `hands.tags` |
| media_files | 경로 기반 매칭용 | 내부 전용 |

### 2.2 데이터 동기화 흐름

```
archive-analyzer                              qwen_hand_analysis
─────────────────                             ──────────────────
    files                                          files
    ├─ path ──────────────────────────────────→ nas_path
    ├─ size_bytes ────────────────────────────→ size_bytes
    └─ file_type

    media_info                                     files
    ├─ video_codec ───────────────────────────→ codec
    ├─ width/height ──────────────────────────→ resolution
    ├─ duration_seconds ──────────────────────→ duration_sec
    └─ framerate ─────────────────────────────→ fps

    clip_metadata                                  hands
    ├─ players_tags ──────────────────────────→ players (JSON)
    ├─ hand_grade ────────────────────────────→ tags (JSON)
    └─ is_badbeat/bluff/... ──────────────────→ tags (JSON)
```

---

## 3. 스키마 변경 관리

### 3.1 변경 절차

1. **변경 제안**: 이슈 생성 (양쪽 레포에 링크)
2. **영향 분석**: 연동 테이블/컬럼 확인
3. **문서 업데이트**: 이 파일 수정
4. **마이그레이션 스크립트**: 필요시 작성
5. **PR 생성**: 양쪽 레포에 동시 반영

### 3.2 변경 이력

| 날짜 | 버전 | 변경 내용 | 영향 범위 |
|------|------|----------|----------|
| 2025-12-02 | 1.5.0 | **스키마 정리**: display_names 테이블 폐기 (display_title은 각 테이블에 직접 저장), subcatalogs에서 level1/2/3_name 컬럼 제거 (sub1/2/3와 중복) | sheets_sync.py, pokervod.db |
| 2025-12-02 | 1.4.0 | **Archive Team Google Sheet 동기화** 섹션 추가, 태그 정규화 매핑, 워크시트 자동 처리 문서화 | archive_hands_sync.py |
| 2025-12-02 | 1.3.0 | **display_title 컬럼 추가** (catalogs, subcatalogs, files, hands), title_generator.py 구현 | sheets_sync.py, Google Sheets |
| 2025-12-02 | 1.2.0 | display_names 테이블, 시청자 친화적 네이밍 설계 | Phase 3 구현 예정 |
| 2025-12-02 | 1.1.0 | subcatalogs 다단계 구조 (parent_id, depth, path, sub1/sub2/sub3, full_path_name) | sync.py, 마이그레이션 |
| 2025-12-01 | 1.0.0 | 최초 문서 작성 | - |

### 3.3 마이그레이션 예시

```python
# scripts/migrate_to_pokervod.py
"""archive.db → pokervod.db 데이터 동기화"""

import sqlite3

ARCHIVE_DB = "d:/AI/claude01/archive-analyzer/data/output/archive.db"
POKERVOD_DB = "d:/AI/claude01/qwen_hand_analysis/data/pokervod.db"

def sync_files():
    """files 테이블 동기화"""
    src = sqlite3.connect(ARCHIVE_DB)
    dst = sqlite3.connect(POKERVOD_DB)

    # archive.db에서 미디어 파일 조회
    files = src.execute("""
        SELECT f.path, f.size_bytes, m.video_codec,
               m.width || 'x' || m.height as resolution,
               m.duration_seconds, m.framerate
        FROM files f
        LEFT JOIN media_info m ON f.id = m.file_id
        WHERE f.file_type = 'video'
    """).fetchall()

    # pokervod.db에 upsert
    for path, size, codec, res, dur, fps in files:
        dst.execute("""
            INSERT INTO files (id, nas_path, filename, size_bytes,
                               codec, resolution, duration_sec, fps, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(nas_path) DO UPDATE SET
                size_bytes = excluded.size_bytes,
                codec = excluded.codec,
                resolution = excluded.resolution,
                duration_sec = excluded.duration_sec,
                fps = excluded.fps
        """, (generate_id(path), path, os.path.basename(path),
              size, codec, res, dur, fps))

    dst.commit()
    dst.close()
    src.close()
```

---

## 4. 연동 키 규칙

### 4.1 파일 ID 생성

```python
import hashlib

def generate_file_id(nas_path: str) -> str:
    """NAS 경로로 고유 ID 생성"""
    # 경로 정규화 (Windows/Unix 호환)
    normalized = nas_path.replace("\\", "/").lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:16]
```

### 4.2 경로 변환

```python
# NAS 경로 패턴
NAS_PREFIX = "//10.10.100.122/docker/GGPNAs/ARCHIVE"
LOCAL_PREFIX = "Z:/GGPNAs/ARCHIVE"

def nas_to_local(nas_path: str) -> str:
    return nas_path.replace(NAS_PREFIX, LOCAL_PREFIX)

def local_to_nas(local_path: str) -> str:
    return local_path.replace(LOCAL_PREFIX, NAS_PREFIX)
```

---

## 5. 카테고리/서브카테고리 매핑

### 5.1 다단계 분류 규칙

경로 패턴에서 자동으로 catalog, subcatalog, depth를 추출합니다.

| 경로 패턴 | catalog_id | subcatalog_id | depth |
|-----------|------------|---------------|-------|
| `WSOP/WSOP-BR` | WSOP | wsop-br | 1 |
| `WSOP/WSOP-BR/WSOP-EUROPE` | WSOP | wsop-europe | 2 |
| `WSOP/WSOP-BR/WSOP-EUROPE/2024` | WSOP | wsop-europe-2024 | 3 |
| `WSOP/WSOP-BR/WSOP-PARADISE` | WSOP | wsop-paradise | 2 |
| `WSOP/WSOP-BR/WSOP-PARADISE/2023` | WSOP | wsop-paradise-2023 | 3 |
| `WSOP/WSOP-BR/WSOP-LAS VEGAS` | WSOP | wsop-las-vegas | 2 |
| `WSOP/WSOP ARCHIVE` | WSOP | wsop-archive | 1 |
| `WSOP/WSOP ARCHIVE/1995` | WSOP | wsop-archive-1973-2002 | 2 |
| `WSOP/WSOP ARCHIVE/2008` | WSOP | wsop-archive-2003-2010 | 2 |
| `WSOP/WSOP ARCHIVE/2015` | WSOP | wsop-archive-2011-2016 | 2 |
| `WSOP/WSOP-C` | WSOP | wsop-circuit | 1 |
| `WSOP/WSOP-SC` | WSOP | wsop-super-circuit | 1 |
| `HCL/2025` | HCL | hcl-2025 | 1 |
| `HCL/Poker Clips` | HCL | hcl-clips | 1 |
| `PAD/Season 12` | PAD | pad-s12 | 1 |
| `PAD/Season 13` | PAD | pad-s13 | 1 |
| `MPP/5M GTD` | MPP | mpp-5m | 1 |
| `GGMillions/` | GGMillions | ggmillions-main | 1 |

### 5.2 다단계 분류 함수

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SubcatalogMatch:
    """다단계 서브카탈로그 매칭 결과"""
    catalog_id: str
    subcatalog_id: Optional[str]
    depth: int
    year: Optional[str] = None

    @property
    def full_subcatalog_id(self) -> Optional[str]:
        """연도가 포함된 전체 서브카탈로그 ID"""
        if self.subcatalog_id and self.year and "{year}" in self.subcatalog_id:
            return self.subcatalog_id.replace("{year}", self.year)
        return self.subcatalog_id

# 다단계 패턴: (regex, catalog_id, subcatalog_template, depth)
MULTILEVEL_PATTERNS = [
    # WSOP-BR 하위 (depth=2~3)
    (r"WSOP/WSOP-BR/WSOP-EUROPE/(\d{4})", "WSOP", "wsop-europe-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-PARADISE/(\d{4})", "WSOP", "wsop-paradise-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS/(\d{4})", "WSOP", "wsop-las-vegas-{year}", 3),
    (r"WSOP/WSOP-BR/WSOP-EUROPE", "WSOP", "wsop-europe", 2),
    (r"WSOP/WSOP-BR/WSOP-PARADISE", "WSOP", "wsop-paradise", 2),
    (r"WSOP/WSOP-BR/WSOP-LAS\s?VEGAS", "WSOP", "wsop-las-vegas", 2),
    (r"WSOP/WSOP-BR", "WSOP", "wsop-br", 1),
    # WSOP Archive (연대별)
    (r"WSOP/WSOP\s?ARCHIVE/(1973|19[789]\d|200[0-2])", "WSOP", "wsop-archive-1973-2002", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(200[3-9]|2010)", "WSOP", "wsop-archive-2003-2010", 2),
    (r"WSOP/WSOP\s?ARCHIVE/(201[1-6])", "WSOP", "wsop-archive-2011-2016", 2),
    (r"WSOP/WSOP\s?ARCHIVE", "WSOP", "wsop-archive", 1),
    # 기타
    (r"WSOP/WSOP-C", "WSOP", "wsop-circuit", 1),
    (r"WSOP/WSOP-SC", "WSOP", "wsop-super-circuit", 1),
    (r"HCL/(\d{4})", "HCL", "hcl-{year}", 1),
    (r"HCL/.*[Cc]lip", "HCL", "hcl-clips", 1),
    (r"PAD/[Ss](?:eason\s?)?12", "PAD", "pad-s12", 1),
    (r"PAD/[Ss](?:eason\s?)?13", "PAD", "pad-s13", 1),
    (r"MPP/.*5\s?[Mm]", "MPP", "mpp-5m", 1),
    (r"GGMillions/", "GGMillions", "ggmillions-main", 1),
]

def classify_path_multilevel(path: str) -> SubcatalogMatch:
    """경로에서 다단계 서브카탈로그 정보 추출"""
    normalized = path.replace("\\", "/")

    for pattern, catalog, subcatalog_template, depth in MULTILEVEL_PATTERNS:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            year = None
            if match.groups() and match.group(1).isdigit():
                year = match.group(1)

            return SubcatalogMatch(
                catalog_id=catalog,
                subcatalog_id=subcatalog_template,
                depth=depth,
                year=year,
            )

    return SubcatalogMatch(catalog_id="OTHER", subcatalog_id=None, depth=0)
```

### 5.3 사용 예시

```python
# WSOP Europe 2024 파일
match = classify_path_multilevel("WSOP/WSOP-BR/WSOP-EUROPE/2024/main_event.mp4")
print(match.catalog_id)           # "WSOP"
print(match.full_subcatalog_id)   # "wsop-europe-2024"
print(match.depth)                # 3
print(match.year)                 # "2024"

# WSOP Archive 2008 파일
match = classify_path_multilevel("WSOP/WSOP ARCHIVE/2008/final_table.mp4")
print(match.full_subcatalog_id)   # "wsop-archive-2003-2010"
print(match.depth)                # 2
```

---

## 6. Viewer-Friendly Naming Design

### 6.1 Problem Statement

Current archive uses **internal management folder/file naming conventions** which are unsuitable for viewers:

| Problem | Current Example | Improvement Needed |
|---------|-----------------|-------------------|
| Abbreviations | `WSOP-BR`, `PAD S12` | Full names or familiar expressions |
| Internal codes | `WSOP-C LA`, `WSOP-SC` | Meaningful names |
| Inconsistency | `2024 WSOP-Europe` vs `WSOP-LAS VEGAS 2024` | Unified year position |
| Insufficient info | `main_event.mp4` | Add specific descriptions |
| Technical terms | `D1A`, `FT` | Viewer-understandable expressions |

### 6.2 Display Title 저장 방식

> **Note (v1.5.0)**: `display_names` 테이블은 **폐기**되었습니다.
> 대신 `display_title`, `title_source`, `title_verified` 컬럼이 각 엔티티 테이블
> (catalogs, subcatalogs, files, hands)에 직접 저장됩니다.

#### 각 테이블의 display_title 관련 컬럼

| Column | Type | Description |
|--------|------|-------------|
| display_title | VARCHAR(300) | 시청자용 표시 제목 |
| title_source | VARCHAR(20) | 제목 생성 방식: `manual`, `ai_generated`, `rule_based`, `archive_team` |
| title_verified | BOOLEAN | 수동 검수 완료 여부 |

### 6.3 Catalog Display Name Mapping

#### Catalogs

| catalog_id | internal_name | display_name | display_name_ko |
|------------|---------------|--------------|-----------------|
| WSOP | WSOP | World Series of Poker | World Series of Poker |
| HCL | HCL | Hustler Casino Live | Hustler Casino Live |
| PAD | PAD | Poker After Dark | Poker After Dark |
| MPP | MPP | MILLIONS Poker Party | MILLIONS Poker Party |
| GGMillions | GGMillions | GG MILLIONS | GG MILLIONS |

#### Subcatalogs

| subcatalog_id | internal_name | display_name | display_name_ko |
|---------------|---------------|--------------|-----------------|
| wsop-br | WSOP-BR | WSOP Bracelet Series | WSOP Bracelet Series |
| wsop-europe | WSOP-EUROPE | WSOP Europe | WSOP Europe |
| wsop-paradise | WSOP-PARADISE | WSOP Paradise | WSOP Paradise |
| wsop-las-vegas | WSOP-LAS VEGAS | WSOP Las Vegas | WSOP Las Vegas |
| wsop-archive | WSOP ARCHIVE | WSOP Classic Archive | WSOP Classic Archive |
| wsop-circuit | WSOP-C | WSOP Circuit | WSOP Circuit |
| wsop-super-circuit | WSOP-SC | WSOP Super Circuit | WSOP Super Circuit |
| hcl-2025 | 2025 | HCL Season 2025 | HCL Season 2025 |
| hcl-clips | Poker Clip | HCL Best Moments | HCL Best Moments |
| pad-s12 | PAD S12 | Poker After Dark Season 12 | Poker After Dark Season 12 |
| pad-s13 | PAD S13 | Poker After Dark Season 13 | Poker After Dark Season 13 |

### 6.4 Event/File Naming Rules

#### Event Type Display Names

| Internal Code | display_name |
|---------------|--------------|
| ME | Main Event |
| FT | Final Table |
| D1, D1A, D1B | Day 1, Day 1A, Day 1B |
| D2, D3... | Day 2, Day 3... |
| HU | Heads-Up |
| SE | Side Event |

#### File Name → Display Name Conversion Rules

```python
# Rule-based conversion examples
FILE_NAME_PATTERNS = {
    # WSOP patterns
    r"WSOP (\d{4}) Main Event.*Day (\d+)([A-Z]?)":
        "WSOP {1} Main Event Day {2}{3}",
    r"WSOP (\d{4}).*Event #(\d+).*\$(\d+[KM]?) (.+)":
        "WSOP {1} Event #{2} - ${3} {4}",

    # HCL patterns
    r"HCL.*(\d{4}-\d{2}-\d{2}).*(.+)":
        "Hustler Casino Live - {2} ({1})",

    # PAD patterns
    r"PAD S(\d+) EP(\d+)":
        "Poker After Dark S{1} Episode {2}",
}
```

### 6.5 AI-Based Naming Generation (Phase 3 Planned)

#### Process

```
1. Analyze file path/name
   ↓
2. Attempt rule-based matching
   ↓ (If matching fails or info insufficient)
3. Request AI analysis (Gemini/GPT)
   - Pass filename, folder structure, metadata
   - Request viewer-friendly title generation
   ↓
4. Save result (source_type='ai_generated', confidence=0.8)
   ↓
5. Await manual review (verified=false)
   ↓
6. Admin approval → verified=true
```

#### AI Prompt Template

```
Generate a viewer-friendly content title based on the following information:

File path: {file_path}
Filename: {filename}
Folder: {parent_folder}
Content type: {content_type}
Metadata: {metadata}

Requirements:
1. Provide both English and Korean titles
2. Use full names instead of abbreviations
3. Include event day and table information
4. Highlight player information if available
5. Concise title within 100 characters

Output format:
{
  "display_name": "...",
  "display_name_ko": "...",
  "short_name": "...",
  "description": "...",
  "confidence": 0.85
}
```

### 6.6 Consistency Management

#### Patterns Requiring Unification

| Inconsistent Pattern | Unified Rule | Example |
|---------------------|--------------|---------|
| Year position | `{Series} {Year} {Event}` | WSOP 2024 Main Event |
| Day notation | `Day {number}` | Day 1, Day 2 |
| Season notation | `Season {number}` | Season 12 |
| Episode | `Episode {number}` or `EP{number}` | Episode 5 / EP5 |

#### Synonym Dictionary

```python
SYNONYMS = {
    # Abbreviation → Standard English
    "ME": "Main Event",
    "FT": "Final Table",
    "HU": "Heads-Up",
    "EP": "Episode",
    "S": "Season",
    "D1": "Day 1",
    "D2": "Day 2",
}
```

### 6.7 Updated ERD (v1.5.0)

> display_names 테이블 폐기 후, display_title은 각 테이블에 직접 저장됩니다.

```
┌─────────────────────────┐
│       catalogs          │
│─────────────────────────│
│ id (PK)                 │
│ name                    │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      subcatalogs        │
│─────────────────────────│
│ id (PK)                 │
│ catalog_id (FK)         │
│ sub1, sub2, sub3        │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│         files           │
│─────────────────────────│
│ id (PK)                 │
│ filename                │
│ nas_path                │
│ display_title           │  ← 시청자용 제목
│ display_subtitle        │
│ title_source            │
│ title_verified          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│         hands           │
│─────────────────────────│
│ id (PK)                 │
│ file_id (FK)            │
│ display_title           │  ← 시청자용 제목
│ title_source            │
│ title_verified          │
└─────────────────────────┘
```

---

## 7. Archive Team Google Sheet 동기화

### 7.1 개요

아카이브 팀이 핸드 태깅 작업을 수행하는 Google Sheet를 pokervod.db hands 테이블과 동기화합니다.

**스프레드시트**: [Metadata Archive](https://docs.google.com/spreadsheets/d/1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4)

### 7.2 워크시트 구조

각 워크시트는 하나의 이벤트/파일에 대한 핸드 정보를 포함합니다.

| 행 | 내용 |
|----|------|
| 1-2행 | 메타데이터 (무시) |
| 3행 | 헤더 |
| 4행~ | 데이터 |

#### 헤더 컬럼 (3행)

| 컬럼 | 타입 | DB 매핑 | 설명 |
|------|------|---------|------|
| File No. | INTEGER | `hand_number` | 핸드 번호 |
| File Name | TEXT | - | 파일명 (매칭용) |
| Nas Folder Link | TEXT | → `file_id` | NAS 경로 (파일 매칭 키) |
| In | TIME (H:MM:SS) | `start_sec` | 시작 타임코드 |
| Out | TIME (H:MM:SS) | `end_sec` | 종료 타임코드 |
| Hand Grade | TEXT (★~★★★) | `highlight_score` | 하이라이트 등급 (1-3) |
| Hands | TEXT | `cards_shown` | 공개 카드 (예: "AA vs KK") |
| Tag (Player) | TEXT (다중) | `players` | 플레이어 태그 (JSON 배열) |
| Tag (Poker Play) | TEXT (다중) | `tags` | 포커 플레이 태그 (정규화) |
| Tag (Emotion) | TEXT (다중) | `tags` | 감정 태그 (정규화) |

### 7.3 워크시트 자동 처리

워크시트 수가 **동적으로 증가**합니다. 동기화 스크립트는 모든 워크시트를 자동으로 순회합니다.

```python
# 모든 워크시트 동기화
for ws in spreadsheet.worksheets():
    sync_worksheet(ws.title)
```

#### 워크시트 명명 규칙

| 패턴 | 예시 |
|------|------|
| `{Year} {Event}` | "2024 WSOPC LA" |
| `{Year} {Series} {Event} {Day}` | "2025 WSOP Main Event Day 1A" |

### 7.4 태그 정규화 매핑

Google Sheet의 태그를 DB 저장용 정규화된 형태로 변환합니다.

#### Poker Play 태그

| 원본 (시트) | 정규화 (DB) |
|------------|-------------|
| Preflop All-in | `preflop_allin` |
| 4-way All-in | `multiway_allin` |
| Hero Fold | `hero_fold` |
| Nice Fold | `nice_fold` |
| Hero Call | `hero_call` |
| Cooler | `cooler` |
| Badbeat | `badbeat` |
| Suckout | `suckout` |
| Bluff | `bluff` |
| Epic Hand | `epic_hand` |
| Crazy Runout | `crazy_runout` |
| Reversal over Reversal | `reversal` |
| Quads | `quads` |
| Straight Flush | `straight_flush` |
| Royal Flush | `royal_flush` |
| Flush vs Flush | `flush_vs_flush` |
| Set over Set | `set_over_set` |
| KK vs QQ, AA vs KK | `premium_vs_premium` |

#### Emotion 태그

| 원본 (시트) | 정규화 (DB) |
|------------|-------------|
| Absurd | `absurd` |
| Luckbox | `luckbox` |
| Insane | `insane` |
| Brutal | `brutal` |

### 7.5 동기화 흐름

```
┌────────────────────────────────┐
│  Archive Team Google Sheet     │
│  (Metadata Archive)            │
│  ├── 2024 WSOPC LA            │
│  ├── 2025 WSOP Main Event     │
│  ├── 2023 WSOP Paradise       │
│  └── ... (동적 증가)           │
└────────────────┬───────────────┘
                 │ archive_hands_sync.py --sync
                 ▼
┌────────────────────────────────┐
│       pokervod.db hands        │
│  ├── title_source='archive_team'
│  ├── tags (정규화 JSON)        │
│  ├── players (JSON 배열)       │
│  └── highlight_score (1-3)     │
└────────────────┬───────────────┘
                 │ sheets_sync.py --daemon
                 ▼
┌────────────────────────────────┐
│   NAS 관리 Google Sheet        │
│   (pokervod DB Sync)           │
│   └── hands 워크시트           │
└────────────────────────────────┘
```

### 7.6 CLI 사용법

```bash
# 정방향 동기화 (Archive Sheet → DB)
python src/archive_analyzer/archive_hands_sync.py --sync

# 역방향 동기화 (DB → Archive Sheet)
python src/archive_analyzer/archive_hands_sync.py --reverse

# 미리보기 (dry-run)
python src/archive_analyzer/archive_hands_sync.py --dry-run

# 특정 워크시트만
python src/archive_analyzer/archive_hands_sync.py --sheet "2024 WSOPC LA" --sync
```

### 7.7 NAS 경로 → file_id 매칭

워크시트의 `Nas Folder Link` 컬럼으로 DB의 `files.nas_path`와 매칭하여 `file_id`를 찾습니다.

```python
def find_file_id(nas_path: str, filename: str) -> Optional[str]:
    # 1. NAS 경로 정규화 후 정확 매칭
    normalized = normalize_nas_path(nas_path)
    if normalized in file_mapping:
        return file_mapping[normalized]

    # 2. 부분 매칭 (폴더 경로)
    for path, file_id in file_mapping.items():
        if normalized in path or path in normalized:
            return file_id

    # 3. 파일명 검색 (fallback)
    cursor.execute(
        "SELECT id FROM files WHERE LOWER(filename) LIKE ?",
        (f"%{filename.lower()}%",)
    )
```

### 7.8 타임코드 변환

| 형식 | 변환 |
|------|------|
| `H:MM:SS` → `float` | "6:58:55" → 25135.0 |
| `float` → `H:MM:SS` | 25135.0 → "6:58:55" |

```python
def parse_timecode(timecode: str) -> float:
    h, m, s = timecode.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def seconds_to_timecode(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"
```

### 7.9 Hand Grade 변환

| 시트 | DB |
|------|-----|
| ★ | 1 |
| ★★ | 2 |
| ★★★ | 3 |

```python
def parse_hand_grade(grade: str) -> int:
    return grade.count("★")

def grade_to_stars(score: int) -> str:
    return "★" * score
```
