# Firestore Schema Design

> **Last Updated**: 2025-12-04
> **Version**: 1.0.0
> **Issue**: #59 웹 기반 마이그레이션 UI

pokervod.db (SQLite)를 Firestore (NoSQL)로 마이그레이션하기 위한 스키마 설계입니다.

## 설계 원칙

1. **Denormalization**: JOIN 대신 데이터 중복 허용
2. **컬렉션 중첩**: 논리적 계층 구조 유지
3. **인덱스 최소화**: 단순 쿼리 우선
4. **실시간 구독**: 변경 감지가 필요한 컬렉션 분리

---

## 컬렉션 구조

```
firestore/
├── catalogs/                    # 카탈로그 (WSOP, HCL, PAD...)
│   └── {catalogId}/
│       ├── ... catalog fields
│       └── series/ (subcollection)
│           └── {seriesId}/
│               ├── ... series fields
│               └── contents/ (subcollection)
│                   └── {contentId}/
│                       └── ... content fields (with embedded players/tags)
│
├── files/                       # 파일 메타데이터
│   └── {fileId}/
│       └── ... file fields
│
├── players/                     # 플레이어 마스터
│   └── {playerId}/
│       └── ... player fields
│
├── tags/                        # 태그 마스터
│   └── {tagId}/
│       └── ... tag fields
│
├── users/                       # 사용자
│   └── {userId}/
│       └── ... user fields
│
└── migrationJobs/               # 마이그레이션 작업
    └── {jobId}/
        └── ... job fields
```

---

## 컬렉션 상세

### 1. catalogs

최상위 카탈로그 (WSOP, HCL, PAD 등)

```typescript
interface Catalog {
  id: string;                    // "wsop", "hcl", "pad"
  name: string;                  // "World Series of Poker"
  displayTitle: string;          // 시청자용 표시 제목
  description?: string;
  titleSource: "rule_based" | "ai_generated" | "manual";
  titleVerified: boolean;
  seriesCount: number;           // 집계 (denormalized)
  contentCount: number;          // 집계 (denormalized)
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

**서브컬렉션**: `catalogs/{catalogId}/series`

---

### 2. series (subcollection of catalogs)

시리즈 (WSOP 2024, HCL Season 5 등)

```typescript
interface Series {
  id: string;                    // auto-generated
  catalogId: string;             // 상위 카탈로그 참조
  slug: string;                  // URL-friendly ID
  title: string;
  subtitle?: string;
  description?: string;
  year: number;
  season?: number;
  location?: string;
  eventType?: string;            // "main_event", "high_roller" 등
  thumbnailUrl?: string;
  episodeCount: number;          // 집계
  totalDuration: number;         // 총 재생 시간 (초)
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

**서브컬렉션**: `catalogs/{catalogId}/series/{seriesId}/contents`

---

### 3. contents (subcollection of series)

개별 콘텐츠 (에피소드)

```typescript
interface Content {
  id: string;                    // auto-generated
  seriesId: string;              // 상위 시리즈 참조
  catalogId: string;             // 빠른 필터링용

  // 표시 정보
  contentType: "episode" | "highlight" | "clip";
  headline: string;              // 메인 제목
  subline?: string;              // 부제목
  thumbnailUrl?: string;
  thumbnailText?: string;        // 썸네일 오버레이 텍스트

  // 미디어 정보
  fileId: string;                // files 컬렉션 참조
  durationSec: number;
  resolution?: string;           // "1920x1080"
  codec?: string;                // "h264", "hevc"

  // Embedded 관계 데이터 (denormalized)
  players: PlayerRef[];          // [{id, name, role}]
  tags: TagRef[];                // [{id, name, category}]

  // 통계
  viewCount: number;
  lastViewedAt?: Timestamp;

  // 메타
  episodeNum?: number;
  airDate?: Timestamp;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

interface PlayerRef {
  id: string;
  name: string;
  displayName?: string;
  role: "main" | "guest" | "dealer";
}

interface TagRef {
  id: string;
  name: string;
  category?: string;
}
```

---

### 4. files

파일 메타데이터 (별도 컬렉션으로 유지)

```typescript
interface File {
  id: string;                    // MD5 hash of nas_path
  nasPath: string;               // NAS 경로 (unique)
  filename: string;
  sizeBytes: number;

  // 미디어 정보
  durationSec?: number;
  resolution?: string;
  codec?: string;
  fps?: number;
  bitrateKbps?: number;

  // 분석 상태
  analysisStatus: "pending" | "analyzing" | "completed" | "failed";
  analysisError?: string;
  analyzedAt?: Timestamp;

  // 연결된 콘텐츠 (역참조)
  contentIds: string[];          // 이 파일을 사용하는 콘텐츠들

  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

---

### 5. players

플레이어 마스터 데이터

```typescript
interface Player {
  id: string;                    // name을 slug화
  name: string;                  // Primary key (unique)
  displayName?: string;
  country?: string;

  // 집계 통계
  totalContents: number;         // 출연 콘텐츠 수
  totalHands?: number;
  totalWins?: number;

  // 검색용
  searchVector: string;          // 검색 키워드
  aliases: string[];             // 별명들

  firstSeenAt: Timestamp;
  lastSeenAt: Timestamp;
}
```

---

### 6. tags

태그 마스터 데이터

```typescript
interface Tag {
  id: string;                    // auto-generated
  name: string;                  // unique
  category: "action" | "event" | "player" | "other";
  usageCount: number;            // 사용 횟수
  createdAt: Timestamp;
}
```

---

### 7. users

사용자 (Firebase Auth와 연동)

```typescript
interface User {
  id: string;                    // Firebase Auth UID
  username: string;
  email: string;
  displayName?: string;
  avatarUrl?: string;

  // 설정
  preferredLanguage: string;     // "ko", "en"
  autoplayEnabled: boolean;

  // 권한
  isActive: boolean;
  isAdmin: boolean;
  role: "viewer" | "editor" | "admin";

  // OAuth 정보
  authProvider: "google" | "email";
  googleId?: string;

  // 감사
  createdAt: Timestamp;
  lastLoginAt: Timestamp;
  loginCount: number;
}
```

---

### 8. migrationJobs

마이그레이션 작업 추적

```typescript
interface MigrationJob {
  id: string;                    // auto-generated
  jobType: "full_sync" | "files_sync" | "catalogs_sync" | "index" | "scan";
  jobName?: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";

  // 실행 정보
  startedBy: string;             // user ID
  startedAt: Timestamp;
  completedAt?: Timestamp;

  // 진행 상황
  progressPercent: number;       // 0-100
  currentStep?: string;

  // 결과
  recordsTotal: number;
  recordsProcessed: number;
  recordsInserted: number;
  recordsUpdated: number;
  recordsSkipped: number;
  recordsFailed: number;

  // 에러
  errorMessage?: string;
  errorDetails?: object;         // JSON

  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

---

## 인덱스 설계

### 복합 인덱스 (필수)

```
// contents 쿼리용
catalogs/{catalogId}/series/{seriesId}/contents
  - (createdAt DESC)
  - (viewCount DESC)
  - (episodeNum ASC)

// 글로벌 콘텐츠 검색용 (Collection Group)
collectionGroup: contents
  - (catalogId, createdAt DESC)
  - (players.id, createdAt DESC)
```

### 단일 필드 인덱스 (자동)

- `files.nasPath` (unique)
- `players.name` (unique)
- `tags.name` (unique)
- `users.email` (unique)

---

## 마이그레이션 매핑

### SQLite → Firestore

| SQLite 테이블 | Firestore 컬렉션 | 변환 방식 |
|--------------|-----------------|----------|
| catalogs | catalogs | 1:1 |
| series | catalogs/{id}/series | 중첩 |
| contents | .../series/{id}/contents | 중첩 + 관계 임베딩 |
| content_players | contents.players[] | 배열로 임베딩 |
| content_tags | contents.tags[] | 배열로 임베딩 |
| files | files | 1:1 |
| players | players | 1:1 |
| tags | tags | 1:1 |
| users | users | 1:1 (Firebase Auth 연동) |
| migration_jobs | migrationJobs | 1:1 |

---

## 쿼리 예시

### 카탈로그별 콘텐츠 조회

```python
# SQLite (JOIN 필요)
SELECT c.* FROM contents c
JOIN series s ON c.series_id = s.id
WHERE s.catalog_id = 'wsop'
ORDER BY c.created_at DESC

# Firestore (중첩 구조로 간단)
db.collection('catalogs').doc('wsop')
  .collection('series').get()  # 각 시리즈에서
  # 또는 Collection Group Query
db.collection_group('contents')
  .where('catalogId', '==', 'wsop')
  .order_by('createdAt', 'DESCENDING')
```

### 플레이어별 출연 콘텐츠

```python
# SQLite
SELECT c.* FROM contents c
JOIN content_players cp ON c.id = cp.content_id
WHERE cp.player_id = 'phil-hellmuth'

# Firestore (array-contains)
db.collection_group('contents')
  .where('players', 'array_contains', {'id': 'phil-hellmuth'})
```

---

## 주의사항

1. **쓰기 비용**: 중복 데이터 업데이트 시 여러 문서 수정 필요
2. **일관성**: 트랜잭션으로 관련 문서 동시 업데이트
3. **쿼리 제한**: 복합 쿼리 시 인덱스 필수
4. **문서 크기**: 1MB 제한 (players/tags 배열 크기 주의)

---

## 다음 단계

1. [ ] Firebase 프로젝트 설정
2. [ ] Security Rules 작성
3. [ ] 마이그레이션 스크립트 구현
4. [ ] 인덱스 배포
5. [ ] 테스트 데이터 마이그레이션
