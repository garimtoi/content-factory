# Database Schema V2 (Simplified)

> **Version**: 2.0.0
> **Status**: 설계 완료, 마이그레이션 예정

## 핵심 변경 사항

| 항목 | V1 (현재) | V2 (신규) |
|------|-----------|-----------|
| **PK 타입** | VARCHAR (문자열) | INTEGER (자동 증가) |
| **조회용 코드** | PK와 동일 | `code` 컬럼 분리 |
| **계층 구조** | `parent_id`, `depth`, `path` 혼재 | `sub1`, `sub2`, `sub3` 명시적 분리 |
| **중복 컬럼** | 많음 | 제거 |

---

## 1. ERD (V2)

```
┌─────────────┐
│  catalogs   │
│─────────────│
│ id (PK) INT │──────┐
│ code        │      │
│ name        │      │
└─────────────┘      │
                     │
┌────────────────────┴───────────────────────────────┐
│                    subcatalogs                      │
│─────────────────────────────────────────────────────│
│ id (PK) INTEGER                                     │
│ catalog_id (FK) → catalogs.id                       │
│ code VARCHAR(100) UNIQUE  ← 조회/연동용             │
│ name VARCHAR(200)         ← 표시명                  │
│ sub1 VARCHAR(200)         ← 1단계 (예: WSOP-BR)     │
│ sub2 VARCHAR(200)         ← 2단계 (예: Europe)      │
│ sub3 VARCHAR(200)         ← 3단계 (예: 2024)        │
│ full_path VARCHAR(500)    ← 전체 경로               │
│ display_order INTEGER                               │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                      files                           │
│─────────────────────────────────────────────────────│
│ id (PK) INTEGER                                      │
│ subcatalog_id (FK) → subcatalogs.id                  │
│ code VARCHAR(200) UNIQUE   ← 조회/연동용             │
│ nas_path TEXT UNIQUE       ← 실제 경로               │
│ filename VARCHAR(500)                                │
│ ...                                                  │
└─────────────────────────────────────────────────────┘
```

---

## 2. 테이블 상세

### 2.1 catalogs

```sql
CREATE TABLE catalogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,    -- 조회용: 'wsop', 'hcl'
    name VARCHAR(200) NOT NULL,           -- 표시명: 'World Series of Poker'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**예시 데이터:**

| id | code | name |
|----|------|------|
| 1 | wsop | World Series of Poker |
| 2 | hcl | Hustler Casino Live |
| 3 | pad | Poker After Dark |

### 2.2 subcatalogs (단순화)

```sql
CREATE TABLE subcatalogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER NOT NULL REFERENCES catalogs(id),
    code VARCHAR(100) UNIQUE NOT NULL,    -- 조회용: 'wsop-europe-2024'
    name VARCHAR(200) NOT NULL,            -- 현재 단계 이름: '2024'

    -- 명시적 계층 (Google Sheets에서 직관적으로 수정 가능)
    sub1 VARCHAR(200),                     -- 1단계: 'WSOP-BR'
    sub2 VARCHAR(200),                     -- 2단계: 'Europe'
    sub3 VARCHAR(200),                     -- 3단계: '2024'
    full_path VARCHAR(500),                -- 전체: 'WSOP > WSOP-BR > Europe > 2024'

    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**예시 데이터:**

| id | catalog_id | code | name | sub1 | sub2 | sub3 | full_path |
|----|------------|------|------|------|------|------|-----------|
| 1 | 1 | wsop-br | WSOP-BR | WSOP-BR | - | - | WSOP > WSOP-BR |
| 2 | 1 | wsop-europe | Europe | WSOP-BR | Europe | - | WSOP > WSOP-BR > Europe |
| 3 | 1 | wsop-europe-2024 | 2024 | WSOP-BR | Europe | 2024 | WSOP > WSOP-BR > Europe > 2024 |

### 2.3 files (단순화)

```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subcatalog_id INTEGER REFERENCES subcatalogs(id),
    code VARCHAR(200) UNIQUE,              -- 조회용 (옵션)
    nas_path TEXT UNIQUE NOT NULL,         -- 실제 NAS 경로
    filename VARCHAR(500) NOT NULL,

    -- 미디어 정보
    size_bytes BIGINT,
    duration_sec FLOAT,
    resolution VARCHAR(20),
    codec VARCHAR(50),

    -- 상태
    analysis_status VARCHAR(20) DEFAULT 'pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.4 hands (변경 없음)

```sql
CREATE TABLE hands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id),
    -- ... 기존과 동일
);
```

### 2.5 players (PK 변경)

```sql
CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(100) UNIQUE NOT NULL,     -- 조회용: 'phil-ivey'
    name VARCHAR(100) NOT NULL,            -- 표시명: 'Phil Ivey'
    display_name VARCHAR(200),
    country VARCHAR(50),
    -- ...
);
```

---

## 3. 장점

### 3.1 수정 용이성

**V1 (문제):**
```
subcatalog PK 'wsop-europe' 수정 시:
→ files.subcatalog_id 모두 변경 필요
→ tournaments.subcatalog_id 모두 변경 필요
→ hands 연쇄 영향
```

**V2 (해결):**
```
subcatalog.code 'wsop-europe' 수정:
→ id (INTEGER)는 그대로
→ FK 영향 없음
→ 안전하게 이름만 변경
```

### 3.2 Google Sheets 편집

**V1 (불편):**
```
| id (PK) | parent_id | depth | path | level1_name | sub1 | ...
복잡하고 중복된 컬럼, PK 수정 불가
```

**V2 (직관적):**
```
| id | code | name | sub1 | sub2 | sub3 | full_path |
| 3  | wsop-europe-2024 | 2024 | WSOP-BR | Europe | 2024 | WSOP > ... |

→ code, sub1, sub2, sub3 자유롭게 수정 가능
→ id는 시스템이 관리 (수정 불필요)
```

---

## 4. 마이그레이션

### 4.1 마이그레이션 순서

1. 새 테이블 생성 (`_v2` 접미사)
2. 데이터 복사 (id 자동 생성)
3. FK 매핑 테이블 생성
4. 기존 테이블 백업 후 삭제
5. 새 테이블 이름 변경

### 4.2 삭제 대상 컬럼

```
subcatalogs:
  - parent_id (계층은 sub1/sub2/sub3로 대체)
  - depth (sub1/sub2/sub3의 NULL 여부로 판단)
  - path (full_path로 대체)
  - level1_name, level2_name, level3_name (sub1/sub2/sub3로 통일)
  - search_vector (필요시 재생성)
```

---

## 5. 호환성

### 5.1 기존 코드 영향

| 모듈 | 변경 필요 |
|------|----------|
| `sheets_sync.py` | 컬럼명 변경 반영 |
| `sync.py` | FK 타입 변경 (VARCHAR → INTEGER) |
| `api.py` | 응답 필드명 확인 |

### 5.2 외부 연동

```python
# 기존 코드와 호환을 위한 code 필드 유지
subcatalog = db.query("SELECT * FROM subcatalogs WHERE code = 'wsop-europe-2024'")
# → id: 3, code: 'wsop-europe-2024', ...
```
