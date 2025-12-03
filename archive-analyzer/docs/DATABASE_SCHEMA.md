# Database Schema Documentation

> **Last Updated**: 2025-12-03
> **Version**: 2.4.0

이 문서는 archive-analyzer와 연동 레포지토리 간 DB 스키마를 정의합니다.
**스키마 변경 시 반드시 이 문서를 업데이트하고 관련 레포에 공유해야 합니다.**

### 테이블 요약 (총 32개)

| 카테고리 | 테이블 | 설명 |
|----------|--------|------|
| **Core** | catalogs, subcatalogs, tournaments, events, files, hands, players, id_mapping | 콘텐츠 계층 구조 + ID 매핑 |
| **User** | users, user_sessions, user_preferences, watch_progress, view_events | 사용자 및 시청 기록 |
| **Recommendation** | recommendation_cache, trending_scores, home_rows, user_home_rows | 추천 시스템 |
| **Artwork** | artwork_variants, artwork_selections | 썸네일 개인화 |
| **Multi-Catalog** | file_catalogs, catalog_collections, collection_items | N:N 카탈로그 |
| **Experiment** | experiments, experiment_assignments | A/B 테스트 |
| **Embedding** | user_embeddings, item_embeddings | ML 임베딩 |
| **Search** | wsoptv_search_index, wsoptv_search_history, wsoptv_popular_searches, wsoptv_player_aliases, wsoptv_choseong_index | 검색 시스템 |

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
| **varchar_id** | VARCHAR(50) | **원본 VARCHAR PK (정수 PK 마이그레이션용)** |

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
| **varchar_id** | VARCHAR(100) | **원본 VARCHAR PK (정수 PK 마이그레이션용)** |
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
| **varchar_id** | VARCHAR(200) | **원본 VARCHAR PK (정수 PK 마이그레이션용)** |

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
| first_seen_at | TIMESTAMP | 플레이어 첫 등록 시간 |
| last_seen_at | TIMESTAMP | 마지막 활동 시간 |
| search_vector | TEXT | 검색용 벡터 |

#### id_mapping ✨ NEW
ID 매핑 테이블 (VARCHAR → INTEGER PK 마이그레이션 추적)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| table_name | VARCHAR(50) PK | 테이블명 (catalogs, subcatalogs, files) |
| old_id | VARCHAR(200) PK | 원본 VARCHAR ID |
| new_id | INTEGER | 신규 정수 ID (현재는 해시값) |
| created_at | TIMESTAMP | 생성일시 |

**인덱스**: `idx_id_mapping_new`

> **Note**: 정수 PK 마이그레이션 1단계. 현재 `varchar_id` 컬럼에 원본 ID를 보존 중.
> 향후 실제 정수 PK 전환 시 이 테이블을 활용하여 FK 업데이트 수행.

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
| 2025-12-03 | 2.0.0 | **추천 시스템 스키마 설계** (Section 8): recommendation_cache, trending_scores, home_rows, user_home_rows, artwork_variants, artwork_selections, experiments, experiment_assignments, user_embeddings, item_embeddings | Phase 3 구현 예정 |
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

---

## 8. 추천 시스템 스키마 (Phase 3)

> **Status**: ✅ 스키마 구현 완료 (마이그레이션: `scripts/migrate_recommendation_schema.py`)
> **목표**: Netflix/Disney+ 스타일 동적 카탈로그 및 개인화 추천
> **다음 단계**: Gorse 연동, API 엔드포인트 구현

### 8.1 개요

| 기능 | 테이블 | 설명 |
|------|--------|------|
| 시청 이력 추적 | `view_events`, `watch_progress` | 이미 존재 ✅ |
| 사용자 선호도 | `user_preferences` | 이미 존재 ✅ |
| 추천 결과 캐싱 | `recommendation_cache` | 신규 |
| 트렌딩/인기 집계 | `trending_scores` | 신규 |
| 홈 화면 Row 설정 | `home_rows`, `user_home_rows` | 신규 |
| 썸네일 개인화 | `artwork_variants`, `artwork_selections` | 신규 |
| A/B 테스트 | `experiments`, `experiment_assignments` | 신규 |
| 사용자 임베딩 | `user_embeddings`, `item_embeddings` | 신규 |

### 8.2 ERD (추천 시스템)

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│     users       │────<│   user_preferences  │     │    files        │
│─────────────────│     │─────────────────────│     │─────────────────│
│ id (PK)         │     │ user_id (FK)        │     │ id (PK)         │
│ username        │     │ item_type           │     │ display_title   │
└────────┬────────┘     │ item_id (FK)        │     └────────┬────────┘
         │              │ feedback_type       │              │
         │              │ score               │              │
         │              └─────────────────────┘              │
         │                                                   │
         ├──────────────────────────────┐                   │
         │                              │                   │
         ▼                              ▼                   │
┌─────────────────────┐     ┌─────────────────────┐        │
│    watch_progress   │     │    view_events      │        │
│─────────────────────│     │─────────────────────│        │
│ user_id (FK)        │     │ user_id (FK)        │        │
│ file_id (FK) ───────┼─────│ file_id (FK) ───────┼────────┘
│ current_position    │     │ hand_id (FK)        │
│ progress_percent    │     │ event_type          │
│ is_completed        │     │ position_sec        │
└─────────────────────┘     │ session_id          │
                            └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ recommendation_cache│     │   trending_scores   │
│─────────────────────│     │─────────────────────│
│ user_id (FK)        │     │ file_id (FK)        │
│ rec_type            │     │ time_bucket         │
│ items (JSON)        │     │ view_count          │
│ algorithm           │     │ unique_viewers      │
│ expires_at          │     │ avg_completion      │
│ created_at          │     │ trending_score      │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│     home_rows       │     │   user_home_rows    │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ user_id (FK)        │
│ row_type            │◀────│ row_id (FK)         │
│ title               │     │ position            │
│ algorithm           │     │ is_visible          │
│ default_position    │     │ is_personalized     │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│  artwork_variants   │     │ artwork_selections  │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ user_id (FK)        │
│ file_id (FK)        │     │ file_id (FK)        │
│ variant_type        │     │ artwork_id (FK)     │
│ image_url           │     │ impressions         │
│ focus_player        │     │ clicks              │
│ emotion             │     │ selected_at         │
└─────────────────────┘     └─────────────────────┘
```

### 8.3 신규 테이블 상세

#### recommendation_cache
추천 결과 캐싱 (Gorse/Implicit 연동)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| rec_type | VARCHAR(50) | 추천 유형: `personalized`, `similar`, `because_watched`, `trending` |
| context_item_id | VARCHAR(200) NULL | 컨텍스트 아이템 (예: "Because you watched X"의 X) |
| items | JSON | 추천 아이템 리스트 `[{id, score, reason}]` |
| algorithm | VARCHAR(50) | 사용 알고리즘: `gorse`, `implicit`, `lightfm`, `rule_based` |
| model_version | VARCHAR(50) | 모델 버전 |
| expires_at | TIMESTAMP | 만료 시각 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE recommendation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    rec_type VARCHAR(50) NOT NULL,
    context_item_id VARCHAR(200),
    items JSON NOT NULL,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'gorse',
    model_version VARCHAR(50),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, rec_type, context_item_id)
);
CREATE INDEX idx_rec_cache_user ON recommendation_cache(user_id);
CREATE INDEX idx_rec_cache_expires ON recommendation_cache(expires_at);
```

#### trending_scores
실시간 트렌딩/인기도 집계 (Netflix Top 10 재현)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| catalog_id | VARCHAR(50) FK | 카탈로그 (WSOP, HCL 등) |
| time_bucket | TIMESTAMP | 집계 시간 구간 (1시간 단위) |
| view_count | INTEGER | 조회수 |
| unique_viewers | INTEGER | 고유 시청자 수 |
| avg_completion_rate | FLOAT | 평균 완료율 (0-1) |
| avg_watch_duration | FLOAT | 평균 시청 시간 (초) |
| trending_score | FLOAT | 트렌딩 점수 (가중 합산) |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE trending_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    catalog_id VARCHAR(50),
    time_bucket TIMESTAMP NOT NULL,
    view_count INTEGER DEFAULT 0,
    unique_viewers INTEGER DEFAULT 0,
    avg_completion_rate FLOAT DEFAULT 0,
    avg_watch_duration FLOAT DEFAULT 0,
    trending_score FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, time_bucket),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (catalog_id) REFERENCES catalogs(id)
);
CREATE INDEX idx_trending_bucket ON trending_scores(time_bucket);
CREATE INDEX idx_trending_score ON trending_scores(trending_score DESC);
CREATE INDEX idx_trending_catalog ON trending_scores(catalog_id, time_bucket);
```

#### home_rows
홈 화면 Row 정의 (Netflix 스타일)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | Row 식별자: `continue_watching`, `trending_wsop`, `because_watched` |
| row_type | VARCHAR(50) | 유형: `continue`, `trending`, `personalized`, `category`, `curated` |
| title | VARCHAR(200) | 표시 제목: "계속 시청하기", "WSOP 인기 영상" |
| title_template | VARCHAR(200) | 동적 제목: "Because you watched {title}" |
| algorithm | VARCHAR(50) | 사용 알고리즘 |
| query_params | JSON | 쿼리 파라미터: `{catalog_id: "WSOP", limit: 20}` |
| default_position | INTEGER | 기본 순서 |
| is_active | BOOLEAN | 활성화 여부 |
| requires_history | BOOLEAN | 시청 기록 필요 여부 |
| min_items | INTEGER | 최소 표시 아이템 수 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE home_rows (
    id VARCHAR(50) PRIMARY KEY,
    row_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    title_template VARCHAR(200),
    algorithm VARCHAR(50),
    query_params JSON,
    default_position INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    requires_history BOOLEAN DEFAULT FALSE,
    min_items INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 기본 Row 데이터
INSERT INTO home_rows (id, row_type, title, algorithm, default_position, requires_history) VALUES
    ('continue_watching', 'continue', '계속 시청하기', 'watch_progress', 1, TRUE),
    ('trending_all', 'trending', '지금 인기 있는 영상', 'trending_24h', 2, FALSE),
    ('trending_wsop', 'trending', 'WSOP 인기 영상', 'trending_24h', 3, FALSE),
    ('trending_hcl', 'trending', 'HCL 인기 영상', 'trending_24h', 4, FALSE),
    ('new_releases', 'category', '새로 추가된 영상', 'recent', 5, FALSE),
    ('personalized_for_you', 'personalized', '당신을 위한 추천', 'gorse_hybrid', 6, TRUE),
    ('because_watched', 'personalized', '{title} 시청 후 추천', 'similar_items', 7, TRUE),
    ('top_hands', 'curated', '베스트 핸드 모음', 'highlight_score', 8, FALSE),
    ('favorite_players', 'personalized', '즐겨찾는 플레이어', 'player_based', 9, TRUE);
```

#### user_home_rows
사용자별 홈 화면 Row 설정

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) FK | 사용자 ID |
| row_id | VARCHAR(50) FK | Row ID |
| position | INTEGER | 사용자 설정 순서 |
| is_visible | BOOLEAN | 표시 여부 |
| is_personalized | BOOLEAN | 개인화 적용 여부 |
| context_item_id | VARCHAR(200) | 컨텍스트 (예: "Because you watched X"의 X) |
| updated_at | TIMESTAMP | 수정 시각 |

```sql
CREATE TABLE user_home_rows (
    user_id VARCHAR(50) NOT NULL,
    row_id VARCHAR(50) NOT NULL,
    position INTEGER,
    is_visible BOOLEAN DEFAULT TRUE,
    is_personalized BOOLEAN DEFAULT TRUE,
    context_item_id VARCHAR(200),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, row_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (row_id) REFERENCES home_rows(id)
);
```

#### artwork_variants
파일별 썸네일 변형 (Netflix Artwork Personalization)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| variant_type | VARCHAR(50) | 유형: `default`, `player_focused`, `action`, `emotion` |
| image_url | TEXT | 이미지 URL |
| thumbnail_time_sec | FLOAT | 썸네일 추출 시간 (초) |
| focus_player | VARCHAR(100) | 강조 플레이어 |
| dominant_emotion | VARCHAR(50) | 주요 감정: `excitement`, `tension`, `celebration` |
| tags | JSON | 추가 태그: `["all_in", "showdown"]` |
| generated_by | VARCHAR(50) | 생성 방식: `ffmpeg`, `ai_generated`, `manual` |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE artwork_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    variant_type VARCHAR(50) NOT NULL DEFAULT 'default',
    image_url TEXT NOT NULL,
    thumbnail_time_sec FLOAT,
    focus_player VARCHAR(100),
    dominant_emotion VARCHAR(50),
    tags JSON,
    generated_by VARCHAR(50) DEFAULT 'ffmpeg',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX idx_artwork_file ON artwork_variants(file_id);
CREATE INDEX idx_artwork_player ON artwork_variants(focus_player);
```

#### artwork_selections
사용자별 썸네일 선택 기록 (Contextual Bandit 학습용)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| artwork_id | INTEGER FK | 선택된 썸네일 ID |
| impressions | INTEGER | 노출 횟수 |
| clicks | INTEGER | 클릭 횟수 |
| context | JSON | 컨텍스트: `{row_id, position, device}` |
| selected_at | TIMESTAMP | 마지막 선택 시각 |

```sql
CREATE TABLE artwork_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    file_id VARCHAR(200) NOT NULL,
    artwork_id INTEGER NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    context JSON,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, file_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (artwork_id) REFERENCES artwork_variants(id)
);
```

#### experiments
A/B 테스트 실험 정의

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 실험 ID: `rec_algo_v2`, `artwork_personalization` |
| name | VARCHAR(200) | 실험명 |
| description | TEXT | 설명 |
| variants | JSON | 변형: `[{id: "control", weight: 50}, {id: "treatment", weight: 50}]` |
| target_metric | VARCHAR(100) | 목표 지표: `ctr`, `watch_time`, `completion_rate` |
| start_date | TIMESTAMP | 시작일 |
| end_date | TIMESTAMP | 종료일 |
| status | VARCHAR(20) | 상태: `draft`, `running`, `paused`, `completed` |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE experiments (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    variants JSON NOT NULL,
    target_metric VARCHAR(100),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### experiment_assignments
사용자별 실험 할당

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) FK | 사용자 ID |
| experiment_id | VARCHAR(50) FK | 실험 ID |
| variant_id | VARCHAR(50) | 할당된 변형 ID |
| assigned_at | TIMESTAMP | 할당 시각 |

```sql
CREATE TABLE experiment_assignments (
    user_id VARCHAR(50) NOT NULL,
    experiment_id VARCHAR(50) NOT NULL,
    variant_id VARCHAR(50) NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, experiment_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
```

#### user_embeddings
사용자 임베딩 벡터 (Gorse/Implicit 연동)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | VARCHAR(50) PK | 사용자 ID |
| embedding | BLOB | 임베딩 벡터 (numpy array serialized) |
| algorithm | VARCHAR(50) | 알고리즘: `implicit_als`, `lightfm`, `gorse` |
| model_version | VARCHAR(50) | 모델 버전 |
| updated_at | TIMESTAMP | 갱신 시각 |

```sql
CREATE TABLE user_embeddings (
    user_id VARCHAR(50) PRIMARY KEY,
    embedding BLOB NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    model_version VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### item_embeddings
아이템 임베딩 벡터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| item_id | VARCHAR(200) PK | 아이템 ID (file_id 또는 hand_id) |
| item_type | VARCHAR(50) | 아이템 유형: `file`, `hand` |
| embedding | BLOB | 임베딩 벡터 |
| algorithm | VARCHAR(50) | 알고리즘 |
| model_version | VARCHAR(50) | 모델 버전 |
| updated_at | TIMESTAMP | 갱신 시각 |

```sql
CREATE TABLE item_embeddings (
    item_id VARCHAR(200) NOT NULL,
    item_type VARCHAR(50) NOT NULL,
    embedding BLOB NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    model_version VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (item_id, item_type)
);
```

### 8.4 기존 테이블 활용

#### view_events (이미 존재)
```sql
-- 사용 예시: 추천 시스템 학습 데이터
SELECT user_id, file_id, event_type, position_sec
FROM view_events
WHERE event_type IN ('play', 'pause', 'complete', 'skip')
ORDER BY created_at;
```

#### watch_progress (이미 존재)
```sql
-- 사용 예시: "계속 시청하기" Row
SELECT file_id, current_position_sec, progress_percent
FROM watch_progress
WHERE user_id = ? AND is_completed = FALSE
ORDER BY last_watched_at DESC
LIMIT 20;
```

#### user_preferences (이미 존재)
```sql
-- 사용 예시: 좋아요/싫어요 피드백
SELECT item_type, item_id, feedback_type, score
FROM user_preferences
WHERE user_id = ?;
```

### 8.5 트렌딩 점수 계산

```python
def calculate_trending_score(
    view_count: int,
    unique_viewers: int,
    avg_completion_rate: float,
    hours_since_upload: float
) -> float:
    """Netflix 스타일 트렌딩 점수 계산

    공식: (views * completion * decay) / time_factor
    """
    # 가중치
    VIEW_WEIGHT = 1.0
    VIEWER_WEIGHT = 2.0  # 고유 시청자 더 중요
    COMPLETION_WEIGHT = 3.0  # 완료율 가장 중요

    # 시간 감쇠 (24시간 반감기)
    time_decay = 0.5 ** (hours_since_upload / 24)

    # 트렌딩 점수
    score = (
        view_count * VIEW_WEIGHT +
        unique_viewers * VIEWER_WEIGHT +
        avg_completion_rate * 100 * COMPLETION_WEIGHT
    ) * time_decay

    return round(score, 2)
```

### 8.6 홈 화면 API 예시

```python
# FastAPI 엔드포인트
@app.get("/api/home/{user_id}")
async def get_home_rows(user_id: str):
    """Netflix 스타일 홈 화면 Row 반환"""
    rows = []

    # 1. 계속 시청하기
    continue_watching = await get_continue_watching(user_id)
    if len(continue_watching) >= 1:
        rows.append({
            "id": "continue_watching",
            "title": "계속 시청하기",
            "items": continue_watching
        })

    # 2. 트렌딩 (전체)
    trending = await get_trending(catalog_id=None, hours=24)
    rows.append({
        "id": "trending_all",
        "title": "지금 인기 있는 영상",
        "items": trending
    })

    # 3. 개인화 추천 (Gorse)
    personalized = await gorse_client.get_recommend(user_id, n=20)
    if personalized:
        rows.append({
            "id": "personalized_for_you",
            "title": "당신을 위한 추천",
            "items": personalized
        })

    # 4. "Because you watched X"
    recent_watch = await get_recent_completed(user_id, limit=1)
    if recent_watch:
        similar = await get_similar_items(recent_watch[0].file_id)
        rows.append({
            "id": "because_watched",
            "title": f"'{recent_watch[0].title}' 시청 후 추천",
            "items": similar
        })

    return {"rows": rows}
```

### 8.7 마이그레이션 계획

| Phase | 작업 | 테이블 | 예상 시간 |
|-------|------|--------|----------|
| 1 | 기본 추천 인프라 | `recommendation_cache`, `trending_scores` | 1주 |
| 2 | 홈 화면 Row | `home_rows`, `user_home_rows` | 1주 |
| 3 | 썸네일 개인화 | `artwork_variants`, `artwork_selections` | 2주 |
| 4 | A/B 테스트 | `experiments`, `experiment_assignments` | 1주 |
| 5 | 임베딩 저장 | `user_embeddings`, `item_embeddings` | 1주 |

### 8.8 Gorse 연동

```yaml
# docker-compose.gorse.yml
services:
  gorse:
    image: zhenghaoz/gorse-in-one:latest
    ports:
      - "8086:8086"  # REST API
      - "8088:8088"  # Dashboard
    environment:
      GORSE_CACHE_STORE: redis://redis:6379/0
      GORSE_DATA_STORE: sqlite:///var/lib/gorse/data.db
    volumes:
      - gorse_data:/var/lib/gorse

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

```python
# Gorse 클라이언트 연동
from gorse import Gorse

gorse = Gorse("http://localhost:8086", "api_key")

# 사용자 피드백 전송
async def send_feedback(user_id: str, file_id: str, feedback_type: str):
    await gorse.insert_feedback(feedback_type, user_id, file_id)

# 추천 요청
async def get_recommendations(user_id: str, n: int = 20):
    return await gorse.get_recommend(user_id, n=n)
```

---

## 9. 멀티 카탈로그 시스템 (Phase 3)

> **Status**: 구현 완료
> **목표**: 하나의 콘텐츠가 여러 카탈로그/컬렉션에 속할 수 있도록 N:N 관계 지원

### 9.1 개요

기존에는 `files → events → tournaments → subcatalogs → catalogs` 단방향 계층 구조로,
하나의 파일은 하나의 카탈로그에만 속할 수 있었습니다.

멀티 카탈로그 시스템은 다음을 지원합니다:
- **플레이어 컬렉션**: Phil Ivey가 등장하는 모든 영상
- **태그 컬렉션**: 블러프, 쿨러, 올인 등 태그별 영상
- **큐레이션 컬렉션**: 베스트 핸드, 역대급 핸드 등
- **동적 컬렉션**: 이번 주 업로드, 가장 많이 본 영상 등

### 9.2 ERD (멀티 카탈로그)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   files     │────<│  file_catalogs   │>────│  catalogs   │
│─────────────│     │──────────────────│     │─────────────│
│ id (PK)     │     │ file_id (FK)     │     │ id (PK)     │
│ event_id    │     │ catalog_id (FK)  │     │ name        │
│ ...         │     │ subcatalog_id    │     │ ...         │
└─────────────┘     │ is_primary       │     └─────────────┘
                    │ added_by         │
                    │ added_reason     │
                    └──────────────────┘

┌───────────────────────┐     ┌──────────────────┐
│  catalog_collections  │────<│ collection_items │
│───────────────────────│     │──────────────────│
│ id (PK)               │     │ collection_id    │
│ name                  │     │ file_id (FK)     │
│ collection_type       │     │ display_order    │
│ is_dynamic            │     │ added_at         │
│ filter_query          │     └──────────────────┘
│ display_order         │
└───────────────────────┘
```

### 9.3 테이블 상세

#### file_catalogs
파일-카탈로그 N:N 연결 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| file_id | VARCHAR(200) FK | 파일 ID |
| catalog_id | VARCHAR(50) FK | 카탈로그 ID |
| subcatalog_id | VARCHAR(100) FK | 서브카탈로그 ID (선택) |
| is_primary | BOOLEAN | 원본 카탈로그 여부 (TRUE=계층 구조에서 자동 설정) |
| display_order | INTEGER | 표시 순서 |
| added_by | VARCHAR(50) | 추가자: `system`, `migration`, `admin`, `ai` |
| added_reason | VARCHAR(200) | 추가 사유 |
| created_at | TIMESTAMP | 생성 시각 |

```sql
CREATE TABLE file_catalogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(200) NOT NULL,
    catalog_id VARCHAR(50) NOT NULL,
    subcatalog_id VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    added_by VARCHAR(50) DEFAULT 'system',
    added_reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_id, catalog_id),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (catalog_id) REFERENCES catalogs(id),
    FOREIGN KEY (subcatalog_id) REFERENCES subcatalogs(id)
);
CREATE INDEX idx_file_catalogs_file ON file_catalogs(file_id);
CREATE INDEX idx_file_catalogs_catalog ON file_catalogs(catalog_id);
CREATE INDEX idx_file_catalogs_subcatalog ON file_catalogs(subcatalog_id);
CREATE INDEX idx_file_catalogs_primary ON file_catalogs(is_primary);
```

#### catalog_collections
컬렉션 정의 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 컬렉션 ID: `highlights`, `player-phil-ivey`, `tag-bluff` |
| name | VARCHAR(200) | 표시 이름 |
| description | TEXT | 설명 |
| collection_type | VARCHAR(50) | 유형: `curated`, `player`, `tag`, `dynamic` |
| cover_image_url | TEXT | 커버 이미지 URL |
| is_dynamic | BOOLEAN | 동적 컬렉션 여부 (자동 업데이트) |
| filter_query | JSON | 동적 필터 조건: `{"player": "Phil Ivey"}`, `{"tag": "bluff"}` |
| display_order | INTEGER | 표시 순서 |
| is_active | BOOLEAN | 활성화 여부 |
| created_by | VARCHAR(50) | 생성자 |
| created_at | TIMESTAMP | 생성 시각 |
| updated_at | TIMESTAMP | 수정 시각 |

```sql
CREATE TABLE catalog_collections (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    collection_type VARCHAR(50) NOT NULL DEFAULT 'curated',
    cover_image_url TEXT,
    is_dynamic BOOLEAN DEFAULT FALSE,
    filter_query JSON,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### collection_items
컬렉션-파일 연결 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| collection_id | VARCHAR(100) FK | 컬렉션 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| display_order | INTEGER | 컬렉션 내 표시 순서 |
| added_at | TIMESTAMP | 추가 시각 |

```sql
CREATE TABLE collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id VARCHAR(100) NOT NULL,
    file_id VARCHAR(200) NOT NULL,
    display_order INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, file_id),
    FOREIGN KEY (collection_id) REFERENCES catalog_collections(id),
    FOREIGN KEY (file_id) REFERENCES files(id)
);
CREATE INDEX idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX idx_collection_items_file ON collection_items(file_id);
```

### 9.4 기본 컬렉션

| ID | 이름 | 유형 | 동적 | 필터 |
|----|------|------|------|------|
| `highlights` | 베스트 핸드 | curated | ❌ | - |
| `epic-hands` | 역대급 핸드 | curated | ❌ | - |
| `player-phil-ivey` | Phil Ivey | player | ✅ | `{"player": "Phil Ivey"}` |
| `player-tom-dwan` | Tom Dwan | player | ✅ | `{"player": "Tom Dwan"}` |
| `player-daniel-negreanu` | Daniel Negreanu | player | ✅ | `{"player": "Daniel Negreanu"}` |
| `tag-bluff` | 블러프 명장면 | tag | ✅ | `{"tag": "bluff"}` |
| `tag-cooler` | 쿨러 핸드 | tag | ✅ | `{"tag": "cooler"}` |
| `tag-allin` | 올인 명승부 | tag | ✅ | `{"tags": ["preflop_allin", "multiway_allin"]}` |
| `recent-week` | 이번 주 업로드 | dynamic | ✅ | `{"days": 7}` |
| `most-viewed` | 가장 많이 본 영상 | dynamic | ✅ | `{"sort": "view_count", "limit": 100}` |

### 9.5 사용 예시

#### 파일의 모든 카탈로그 조회
```sql
SELECT fc.catalog_id, c.name, fc.is_primary, fc.added_reason
FROM file_catalogs fc
JOIN catalogs c ON fc.catalog_id = c.id
WHERE fc.file_id = '1231';
```

#### 멀티 카탈로그 파일 찾기
```sql
SELECT file_id, GROUP_CONCAT(catalog_id) as catalogs, COUNT(*) as cnt
FROM file_catalogs
GROUP BY file_id
HAVING cnt > 1;
```

#### 플레이어 컬렉션에 파일 추가
```sql
-- 수동 추가 (curated 컬렉션)
INSERT INTO collection_items (collection_id, file_id, display_order)
VALUES ('player-phil-ivey', '1231', 1);

-- 또는 file_catalogs로 가상 카탈로그 추가
INSERT INTO file_catalogs (file_id, catalog_id, added_by, added_reason)
VALUES ('1231', 'highlights', 'admin', 'Selected as best hand');
```

#### 동적 컬렉션 쿼리 예시
```python
# 플레이어 컬렉션 (is_dynamic=TRUE)
async def get_player_collection_items(player_name: str):
    return await db.execute('''
        SELECT f.* FROM files f
        JOIN hands h ON h.file_id = f.id
        WHERE JSON_EXTRACT(h.players, '$') LIKE ?
        ORDER BY f.created_at DESC
    ''', (f'%{player_name}%',))

# 태그 컬렉션
async def get_tag_collection_items(tag: str):
    return await db.execute('''
        SELECT DISTINCT f.* FROM files f
        JOIN hands h ON h.file_id = f.id
        WHERE JSON_EXTRACT(h.tags, '$') LIKE ?
        ORDER BY h.highlight_score DESC
    ''', (f'%{tag}%',))
```

### 9.6 마이그레이션

기존 계층 구조에서 `file_catalogs`로 자동 마이그레이션:

```bash
# 시뮬레이션
python scripts/migrate_multi_catalog.py --dry-run

# 실행
python scripts/migrate_multi_catalog.py

# 검증
python scripts/migrate_multi_catalog.py --verify

# 통계
python scripts/migrate_multi_catalog.py --stats

# 롤백
python scripts/migrate_multi_catalog.py --rollback
```

### 9.7 API 연동

```python
# FastAPI 엔드포인트 예시
@app.get("/api/files/{file_id}/catalogs")
async def get_file_catalogs(file_id: str):
    """파일이 속한 모든 카탈로그 조회"""
    catalogs = await db.execute('''
        SELECT c.id, c.name, fc.is_primary
        FROM file_catalogs fc
        JOIN catalogs c ON fc.catalog_id = c.id
        WHERE fc.file_id = ?
    ''', (file_id,))
    return {"catalogs": catalogs}

@app.post("/api/files/{file_id}/catalogs")
async def add_file_to_catalog(file_id: str, catalog_id: str, reason: str = None):
    """파일을 카탈로그에 추가"""
    await db.execute('''
        INSERT OR IGNORE INTO file_catalogs
        (file_id, catalog_id, added_by, added_reason)
        VALUES (?, ?, 'admin', ?)
    ''', (file_id, catalog_id, reason))
    return {"status": "success"}

@app.get("/api/collections/{collection_id}/items")
async def get_collection_items(collection_id: str, limit: int = 50):
    """컬렉션 아이템 조회"""
    collection = await db.execute(
        "SELECT * FROM catalog_collections WHERE id = ?",
        (collection_id,)
    )

    if collection['is_dynamic']:
        # 동적 컬렉션: filter_query로 실시간 조회
        return await execute_dynamic_filter(collection['filter_query'], limit)
    else:
        # 정적 컬렉션: collection_items에서 조회
        items = await db.execute('''
            SELECT f.* FROM collection_items ci
            JOIN files f ON ci.file_id = f.id
            WHERE ci.collection_id = ?
            ORDER BY ci.display_order
            LIMIT ?
        ''', (collection_id, limit))
        return {"items": items}
```

---

## 10. 사용자 및 인증 시스템

### 10.1 users
사용자 계정 정보 (Google OAuth 지원)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(50) PK | 사용자 ID |
| username | VARCHAR(100) NOT NULL | 사용자명 |
| email | VARCHAR(200) | 이메일 |
| hashed_password | VARCHAR(255) | 비밀번호 해시 (로컬 인증) |
| display_name | VARCHAR(100) | 표시 이름 |
| avatar_url | TEXT | 프로필 이미지 URL |
| preferred_language | VARCHAR(10) | 선호 언어 |
| autoplay_enabled | BOOLEAN | 자동재생 설정 |
| is_active | BOOLEAN | 활성 상태 |
| is_admin | BOOLEAN | 관리자 여부 |
| created_at | TIMESTAMP | 생성일시 |
| last_login_at | TIMESTAMP | 마지막 로그인 |
| is_approved | BOOLEAN | 승인 상태 (기본: 0) |
| approved_by | VARCHAR(50) | 승인자 |
| approved_at | TIMESTAMP | 승인일시 |
| rejection_reason | TEXT | 거절 사유 |
| google_id | VARCHAR(100) | Google OAuth ID |
| google_email | VARCHAR(200) | Google 이메일 |
| google_picture | TEXT | Google 프로필 이미지 |
| auth_provider | VARCHAR(20) | 인증 방식 (local/google) |

### 10.2 user_sessions
사용자 세션 관리

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR(100) PK | 세션 ID |
| user_id | VARCHAR(50) FK | 사용자 ID |
| device_type | VARCHAR(50) | 디바이스 유형 |
| browser | VARCHAR(100) | 브라우저 |
| os | VARCHAR(100) | OS |
| ip_address | VARCHAR(45) | IP 주소 |
| refresh_token_hash | VARCHAR(255) | 리프레시 토큰 해시 |
| expires_at | TIMESTAMP NOT NULL | 만료일시 |
| is_active | BOOLEAN | 활성 상태 |
| revoked_at | TIMESTAMP | 폐기일시 |
| created_at | TIMESTAMP | 생성일시 |
| last_activity_at | TIMESTAMP | 마지막 활동일시 |

### 10.3 user_preferences
사용자 선호도/피드백 (좋아요/싫어요)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| item_type | VARCHAR(50) | 아이템 유형 (file/hand/player) |
| item_id | VARCHAR(200) | 아이템 ID |
| feedback_type | VARCHAR(20) | 피드백 유형 (like/dislike/bookmark) |
| score | FLOAT | 점수 |
| created_at | TIMESTAMP | 생성일시 |

### 10.4 view_events
시청 이벤트 로그

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) | 사용자 ID |
| file_id | VARCHAR(200) | 파일 ID |
| hand_id | INTEGER | 핸드 ID |
| event_type | VARCHAR(50) NOT NULL | 이벤트 유형 (play/pause/seek/complete) |
| position_sec | FLOAT | 재생 위치 (초) |
| session_id | VARCHAR(100) | 세션 ID |
| device_type | VARCHAR(50) | 디바이스 유형 |
| referrer | TEXT | 유입 경로 |
| created_at | TIMESTAMP | 생성일시 |

### 10.5 watch_progress
시청 진행 상태 (계속 시청하기)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(50) FK | 사용자 ID |
| file_id | VARCHAR(200) FK | 파일 ID |
| current_position_sec | FLOAT | 현재 위치 (초) |
| duration_sec | FLOAT | 전체 길이 (초) |
| progress_percent | FLOAT | 진행률 (0-100) |
| is_completed | BOOLEAN | 완료 여부 |
| started_at | TIMESTAMP | 시작일시 |
| last_watched_at | TIMESTAMP | 마지막 시청일시 |
| completed_at | TIMESTAMP | 완료일시 |

---

## 11. 검색 시스템 (wsoptv_*)

### 11.1 wsoptv_search_index
통합 검색 인덱스

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| entity_type | VARCHAR(20) NOT NULL | 엔티티 유형 (player/hand/file) |
| entity_id | INTEGER NOT NULL | 엔티티 ID |
| search_vector | TEXT | 검색용 텍스트 |
| normalized_text | TEXT | 정규화된 텍스트 |
| player_ids | JSON | 관련 플레이어 ID 배열 |
| tournament_id | VARCHAR(100) | 토너먼트 ID |
| pot_size | FLOAT | 팟 크기 |
| action_types | JSON | 액션 유형 배열 |
| title | VARCHAR(500) | 제목 |
| description | TEXT | 설명 |
| thumbnail_url | VARCHAR(500) | 썸네일 URL |
| source_updated_at | TIMESTAMP | 원본 수정일시 |
| indexed_at | TIMESTAMP | 인덱싱일시 |

### 11.2 wsoptv_search_history
검색 기록

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| user_id | VARCHAR(100) | 사용자 ID |
| session_id | VARCHAR(100) | 세션 ID |
| query | TEXT NOT NULL | 검색어 |
| parsed_query | JSON | 파싱된 쿼리 |
| results_count | INTEGER | 결과 수 |
| clicked_entity_type | VARCHAR(20) | 클릭된 엔티티 유형 |
| clicked_entity_id | INTEGER | 클릭된 엔티티 ID |
| search_latency_ms | INTEGER | 검색 소요시간 (ms) |
| created_at | TIMESTAMP | 생성일시 |

### 11.3 wsoptv_popular_searches
인기 검색어

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| query | TEXT NOT NULL | 검색어 |
| normalized_query | TEXT | 정규화된 검색어 |
| search_count | INTEGER | 검색 횟수 |
| click_count | INTEGER | 클릭 횟수 |
| first_searched_at | TIMESTAMP | 최초 검색일시 |
| last_searched_at | TIMESTAMP | 마지막 검색일시 |

### 11.4 wsoptv_player_aliases
플레이어 별칭/별명

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| player_id | INTEGER NOT NULL | 플레이어 ID |
| canonical_name | VARCHAR(200) NOT NULL | 정식 이름 |
| alias | VARCHAR(100) NOT NULL | 별칭 |
| alias_type | VARCHAR(20) | 별칭 유형 (nickname/typo/variant) |
| confidence | FLOAT | 신뢰도 |
| created_at | TIMESTAMP | 생성일시 |
| is_verified | BOOLEAN | 검증 여부 |

### 11.5 wsoptv_choseong_index
한글 초성 검색 인덱스

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| player_id | INTEGER NOT NULL | 플레이어 ID |
| korean_name | VARCHAR(100) | 한글 이름 |
| choseong | VARCHAR(50) | 초성 (ㄴㄱㄹㄴ) |
| romanization | VARCHAR(100) | 로마자 표기 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-03 | 2.4.0 | **정수 PK 마이그레이션 1단계**: `varchar_id` 컬럼 추가 (catalogs, subcatalogs, files), `id_mapping` 테이블 |
| 2025-12-03 | 2.2.0 | 사용자/인증/검색 시스템 테이블 문서화 (Section 10, 11), players 테이블 컬럼 추가 |
| 2025-12-03 | 2.1.0 | 멀티 카탈로그 시스템 추가 (Section 9) |
| 2025-12-03 | 2.0.0 | 추천 시스템 스키마 추가 (Section 8) |
| 2025-11-29 | 1.5.0 | display_names 테이블 폐기, display_title 직접 저장 |
| 2025-11-28 | 1.4.0 | Archive Team Google Sheet 동기화 추가 |
| 2025-11-27 | 1.3.0 | 다단계 서브카탈로그 분류 추가 |
| 2025-11-26 | 1.2.0 | 검색 인덱스 테이블 추가 |
| 2025-11-25 | 1.1.0 | 사용자/시청 기록 테이블 추가 |
| 2025-11-24 | 1.0.0 | 초기 스키마 정의 |
