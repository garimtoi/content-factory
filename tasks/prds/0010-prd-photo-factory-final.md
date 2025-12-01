# PRD-0010: Photo Factory - 최종 제품 명세서

**작성일**: 2025-12-01
**버전**: 1.0.0
**상태**: ✅ 완료 (Production Ready)
**작성자**: Claude Code

---

## 1. Executive Summary

**Photo Factory**는 휠 복원 전문 기술자를 위한 모바일 우선 사진 관리 PWA입니다. 작업 전/중/후 사진을 5개 카테고리로 자동 분류하여 마케팅 콘텐츠(동영상) 생성을 자동화합니다.

### 핵심 가치
- **Offline-First**: IndexedDB 기반으로 인터넷 없이도 완전 동작
- **모바일 최적화**: 세로 영상 포맷(1080x1920) 지원, 터치 친화적 UI
- **자동화**: 사진 촬영 → 분류 → 마케팅 영상 생성 원클릭 워크플로우

---

## 2. 제품 아키텍처

### 2.1 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| Frontend | Vanilla JavaScript (ES6+) | - |
| Storage | IndexedDB (Dexie.js) + LocalStorage | Dexie 4.x |
| Build | Vite | 6.x |
| Unit Test | Vitest + happy-dom | - |
| E2E Test | Playwright | - |
| Styling | Bootstrap 5 + Custom CSS | 5.3.0 |

### 2.2 디렉토리 구조

```
contents-factory/
├── src/
│   ├── public/                    # HTML 페이지
│   │   ├── index.html             # 메인 대시보드
│   │   ├── upload.html            # 사진 촬영/업로드 (핵심)
│   │   ├── gallery.html           # 작업 목록
│   │   └── job-detail.html        # 작업 상세/영상 생성
│   └── js/
│       ├── db.js                  # IndexedDB 스키마 (Dexie.js)
│       ├── db-api.js              # 데이터 액세스 레이어
│       ├── video-generator.js     # Canvas + MediaRecorder 영상 생성
│       └── utils/
│           ├── errors.js          # 에러 계층 구조
│           ├── retry.js           # 재시도 유틸리티
│           ├── state.js           # 하이브리드 상태 관리
│           ├── sanitizer.js       # XSS 방지
│           └── logger.js          # 안전한 로깅
├── tests/
│   ├── setup.js                   # Vitest 전역 설정
│   ├── unit/                      # 유닛 테스트
│   └── *.spec.cjs                 # E2E 테스트 (Playwright)
├── vite.config.js                 # Vite 빌드 설정
├── vitest.config.js               # Vitest 설정
└── playwright.config.cjs          # Playwright 설정
```

### 2.3 데이터베이스 스키마

```javascript
// db.js - IndexedDB (Dexie.js)
db.version(3).stores({
  jobs: '++id, job_number, work_date, car_model, technician_id, status, created_at, updated_at, [work_date+status]',
  photos: '++id, job_id, category, sequence, uploaded_at, [job_id+sequence]',
  temp_photos: '++id, session_id, category, sequence, created_at, [session_id+category]',
  users: '++id, &email, display_name, created_at',
  settings: '++id, key'
});
```

**테이블 설명**:
| 테이블 | 용도 |
|--------|------|
| `jobs` | 완료된 작업 (차량 모델, 작업번호, 상태) |
| `photos` | 완료된 작업의 사진 (job_id 연결) |
| `temp_photos` | 진행 중 작업 세션의 임시 사진 |
| `users` | 사용자 정보 |
| `settings` | 앱 설정 |

---

## 3. 핵심 기능

### 3.1 사진 촬영 및 업로드 (`upload.html`)

**기능 목록**:
1. 카메라 직접 촬영 또는 갤러리 선택
2. 5개 카테고리 분류 (입고/문제/과정/해결/출고)
3. 실시간 썸네일 프리뷰
4. 사진 삭제 기능
5. 전체화면 미리보기

**사진 카테고리**:
| 카테고리 | 한글명 | 설명 |
|----------|--------|------|
| `before_car` | 입고 | 작업 전 차량 전체 |
| `before_wheel` | 문제 | 손상된 휠 클로즈업 |
| `during` | 과정 | 작업 중 사진 |
| `after_wheel` | 해결 | 복원된 휠 클로즈업 |
| `after_car` | 출고 | 작업 완료 차량 전체 |

**입력 검증**:
- 파일 크기: 최대 10MB
- 파일 타입: `image/jpeg`, `image/png`, `image/webp`
- 총 파일 수: 최대 50장

### 3.2 하이브리드 상태 관리 (`state.js`)

LocalStorage + IndexedDB 하이브리드 패턴:

```javascript
// LocalStorage: 메타데이터만 (빠른 접근)
{
  sessionId: "abc123",
  carModel: "BMW 5시리즈",
  jobNumber: "WHL251201001",
  photoMeta: {
    before_car: { count: 2 },
    before_wheel: { count: 3 },
    // ...
  }
}

// IndexedDB (temp_photos): 실제 이미지 데이터
{
  id: 1,
  session_id: "abc123",
  category: "before_car",
  image_data: "data:image/jpeg;base64,...",
  thumbnail_data: "data:image/jpeg;base64,...",
  file_name: "photo.jpg",
  file_size: 1024000
}
```

**세션 관리**:
- 세션 유효 시간: 8시간
- 비활성 타임아웃: 30분
- 자동 정리: 만료 세션 자동 삭제

### 3.3 작업번호 생성 (`db-api.js`)

**형식**: `WHL{YYMMDD}{NNN}`
- 예: `WHL251201001` (2025년 12월 1일 첫 번째 작업)

**Race Condition 방지**:
```javascript
// Optimistic Locking + Retry 패턴
async function generateJobNumber(workDate) {
  const maxRetries = 5;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const jobNumber = buildJobNumber(workDate, sequence);
    const exists = await db.jobs.where('job_number').equals(jobNumber).count();
    if (!exists) return jobNumber;
    sequence++;
  }
  throw new Error('작업번호 생성 실패');
}
```

### 3.4 영상 생성 (`video-generator.js`)

**출력 사양**:
- 해상도: 1080 x 1920 (세로, Shorts/Reels 최적화)
- 프레임율: 30 FPS
- 비트레이트: 5 Mbps
- 포맷: WebM (VP9)
- 사진당 표시 시간: 2초
- 전환 효과: 페이드 (500ms)

**오버레이 요소**:
1. 상단: 카테고리 표시 (입고/문제/과정/해결/출고)
2. 진행률 바
3. 하단: 차량 모델, 작업번호, Photo Factory 브랜딩

**타임아웃**: 최대 60초 (무한 루프 방지)

### 3.5 작업 목록 (`gallery.html`)

**기능**:
- 전체 작업 목록 표시
- 검색 (차량 모델, 작업번호)
- 통계 (총 작업 수, 총 사진 수, 저장 용량)
- 작업 카드 클릭 → 상세 페이지

**최적화**:
- DocumentFragment 사용 (DOM 배치 최적화)
- 썸네일 먼저 표시 (빠른 로딩)

### 3.6 QR 코드 접속 (`index.html`)

동일 WiFi 네트워크에서 스마트폰으로 접속:
- QR 코드 자동 생성
- 네트워크 IP + 포트 표시

---

## 4. 보안

### 4.1 적용된 보안 조치

| 항목 | 구현 내용 |
|------|-----------|
| XSS 방지 | `escapeHtml()` 함수로 모든 사용자 입력 이스케이프 |
| 입력 검증 | `validateJobData()`, `validateFile()` |
| CSP 헤더 | `vite.config.js`에서 서버 헤더 설정 |
| 민감 정보 로깅 | 프로덕션에서 console.log 비활성화 |
| 파일 검증 | 크기(10MB), 타입(image/*) 제한 |
| CDN 무결성 | Bootstrap에 SRI 해시 적용 |

### 4.2 에러 처리 계층

```
AppError (base)
├── UploadError     - 재시도 가능
├── NetworkError    - 재시도 가능
├── DatabaseError   - 재시도 가능
├── AuthError       - 재시도 불가 (로그인 필요)
└── ValidationError - 재시도 불가 (입력 수정 필요)
```

### 4.3 재시도 정책 (`retry.js`)

```javascript
{
  maxRetries: 3,
  delayMs: 1000,
  maxDelay: 30000,      // 최대 30초
  totalTimeout: 120000, // 전체 2분
  backoff: 'exponential'
}
```

---

## 5. 성능 최적화

### 5.1 적용된 최적화

| 영역 | 최적화 내용 |
|------|-------------|
| N+1 Query | `anyOf()` 사용하여 단일 쿼리 |
| Photo Count | `count()` 직접 사용 (이미지 로드 안 함) |
| Bulk Insert | `bulkAdd()` 사용 |
| DOM 업데이트 | DocumentFragment + 증분 업데이트 |
| Base64 변환 | `URL.createObjectURL()` 사용 |
| 이미지 메모리 | 사용 후 `img.src = ''` 해제 |
| 번들 최적화 | terser + `drop_console` |

### 5.2 IndexedDB 인덱스

```javascript
// 복합 인덱스 (빠른 조회)
[session_id+category]  // 세션별 카테고리 조회
[job_id+sequence]      // 작업별 사진 순서
[work_date+status]     // 날짜+상태별 필터링
```

---

## 6. 테스트

### 6.1 테스트 설정

**Vitest (Unit)**:
- 환경: `happy-dom`
- 커버리지 임계값: 70%
- 별칭: `@` → `/src`, `@js` → `/src/js`

**Playwright (E2E)**:
- 기본 URL: `http://localhost:6010`
- 브라우저: Desktop Chrome/Firefox/Safari + Mobile Chrome/Safari
- 테스트 파일: `tests/*.spec.cjs`

### 6.2 테스트 결과

| 유형 | 테스트 수 | 통과 | 실패 |
|------|----------|------|------|
| E2E | 22 | 22 | 0 |

---

## 7. 개발 환경

### 7.1 명령어

```bash
# 설치
npm install

# 개발 서버 (http://localhost:6010)
npm run dev

# 빌드
npm run build

# 프리뷰 (http://localhost:6011)
npm run preview

# 유닛 테스트
npm run test:unit
npx vitest run

# E2E 테스트 (dev 서버 실행 필요)
npm test
npx playwright test --project=chromium
```

### 7.2 포트 설정

| 용도 | 포트 |
|------|------|
| Dev Server | 6010 |
| Preview | 6011 |

> **주의**: 포트 6000-6009는 Chrome에서 차단됨 (X11 프로토콜)

---

## 8. 사용자 워크플로우

### 8.1 기본 워크플로우

```
1. 메인 페이지 접속 (index.html)
   ↓
2. "새 작업 시작" 클릭 (upload.html)
   ↓
3. 차량 모델 입력 (예: "BMW 5시리즈")
   ↓
4. 카테고리별 사진 촬영
   - 입고: 차량 전체
   - 문제: 손상된 휠
   - 과정: 작업 중
   - 해결: 복원된 휠
   - 출고: 완성 차량
   ↓
5. "저장 완료" 버튼 클릭
   ↓
6. 작업 상세 페이지 (job-detail.html)
   ↓
7. "마케팅 영상 생성" 클릭
   ↓
8. WebM 파일 다운로드
```

### 8.2 모바일 접속 (QR 코드)

```
1. PC에서 Photo Factory 실행
   ↓
2. 메인 페이지에서 "스마트폰으로 접속" 클릭
   ↓
3. QR 코드 표시됨
   ↓
4. 스마트폰으로 QR 스캔 (같은 WiFi)
   ↓
5. 모바일 브라우저에서 작업 시작
```

---

## 9. 향후 개선 사항 (Optional)

### 9.1 남은 작업

| 우선순위 | 항목 | 설명 |
|----------|------|------|
| Medium | Magic Numbers 상수화 | 시간 값 등을 상수로 정의 |
| Low | JSDoc 보완 | `@private` 태그, 반환 타입 상세화 |
| Low | 미사용 Import 정리 | 테스트 파일 정리 |
| Medium | Sequence 정렬 통일 | IndexedDB/LocalStorage 동기화 |

### 9.2 확장 가능 기능

1. **클라우드 동기화**: Supabase 연동 (RLS 정책 준비됨)
2. **사용자 인증**: Google OAuth
3. **이미지 압축**: browser-image-compression
4. **푸시 알림**: Service Worker
5. **다국어 지원**: i18n

---

## 10. 코드 품질 지표

### 10.1 개선 이력

| 단계 | 점수 | 주요 개선 |
|------|------|-----------|
| 초기 | 62/100 | - |
| Phase 1 | 70/100 | XSS 수정, N+1 Query 수정 |
| Phase 2 | 78/100 | Race Condition, State 동기화 |
| Phase 3 | 83/100 | CSP, 로깅, 타임아웃 |
| Phase 4 | 85/100 | Deprecated 교체, 인덱스 추가 |

### 10.2 발견/해결된 이슈

- **총 발견**: 56개 (Critical 9, High 16, Medium 19, Low 12)
- **해결됨**: 52개 (93%)
- **미해결 (Optional)**: 4개

---

## 11. 릴리스 체크리스트

### 11.1 배포 전 확인

- [x] 모든 E2E 테스트 통과 (22/22)
- [x] XSS 취약점 수정됨
- [x] 입력 검증 구현됨
- [x] 에러 처리 구현됨
- [x] CSP 헤더 설정됨
- [x] 프로덕션 console.log 제거됨
- [x] 인덱스 최적화됨

### 11.2 버전 정보

```
Photo Factory v1.0.0
Build: 2025-12-01
Node: 18+
```

---

## 12. 문서 참조

| 문서 | 위치 | 내용 |
|------|------|------|
| 프로젝트 가이드 | `CLAUDE.md` | 개발 컨벤션, 아키텍처 |
| 작업 목록 | `TODO.md` | 완료/남은 작업 |
| 보안 가이드 | `docs/SECURITY.md` | 보안 설정 상세 |
| RLS 정책 | `docs/supabase_rls_policies.sql` | Supabase 정책 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-12-01 | 1.0.0 | 최종 PRD 작성 |

---

**작성자**: Claude Code
**검토자**: -
**승인자**: -
