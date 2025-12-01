# TODO - Photo Factory PWA

코드 리뷰 결과 (2025-12-01) 기반 개선 작업 목록

---

## 완료된 항목

### Phase 1 (2025-12-01)

- [x] **XSS 취약점 수정** [Critical]
  - `src/js/utils/sanitizer.js` 생성
  - `gallery.html`, `upload.html`, `job-detail.html` escapeHtml 적용

- [x] **입력 검증 추가** [High]
  - `db-api.js` - `validateJobData()`, `validateFile()` 함수 추가

- [x] **N+1 Query 수정** [Critical]
  - `db-api.js:131-150` - `anyOf()` 사용하여 단일 쿼리로 변경

- [x] **Photo Count 최적화** [Critical]
  - `db.js:246-272` - `filter()` + `count()` 사용 (이미지 데이터 로드 안 함)

### Phase 2 (2025-12-01)

- [x] **작업번호 Race Condition 수정** [Critical]
  - `db-api.js:394-450` - Optimistic Locking + Retry 패턴 적용
  - job_number 존재 여부 확인 후 생성 (최대 5회 재시도)

- [x] **Timezone 불일치 수정** [Critical]
  - `db-api.js:396-402` - Local 시간 기준으로 날짜 계산 통일
  - `toISOString()` 대신 Local 날짜 포맷 사용

- [x] **State 동기화 수정** [Critical]
  - `state.js:210-267` - Try-Catch + Rollback 패턴 적용
  - IndexedDB 저장 성공 후에만 LocalStorage 업데이트

- [x] **Transaction 적용** [High]
  - `db-api.js:214-236` - `db.transaction('rw', ...)` 사용
  - Job 삭제 시 Photos 함께 삭제 (atomic)

- [x] **파일 업로드 검증** [High]
  - `upload.html:545-602` - validateFile() 적용
  - 파일 크기 제한: 10MB
  - 파일 타입 제한: `['image/jpeg', 'image/png', 'image/webp']`
  - 전체 파일 수 제한: 50장

- [x] **Bulk Insert 적용** [High]
  - `upload.html:731-751` - 개별 insert → 단일 bulkAdd

- [x] **Base64 이중 변환 제거** [High]
  - `db-api.js:476-522` - `URL.createObjectURL()` 사용
  - File → Blob URL → Canvas → Base64 (한번만 변환)

### Phase 3 (2025-12-01)

- [x] **CSP 헤더 적용** [Medium]
  - `vite.config.js` - 서버 헤더에 CSP 추가
  - X-Content-Type-Options, X-Frame-Options, X-XSS-Protection 추가

- [x] **민감 정보 로깅 제거** [Medium]
  - `src/js/utils/logger.js` 생성
  - 프로덕션에서 console.log 비활성화
  - sanitizeForLog() 함수로 민감 데이터 제거

- [x] **세션 타임아웃 조정** [Medium]
  - `state.js:327-361` - 8시간 + 비활성 30분
  - getRemainingTime() 함수 추가

- [x] **Retry 타임아웃 추가** [High]
  - `retry.js:6-81` - 최대 지연 30초, 전체 타임아웃 2분
  - maxDelay, totalTimeout 옵션 추가

- [x] **에러 타입 판별 개선** [High]
  - `errors.js:134-222` - NON_RETRYABLE_ERRORS 목록
  - QuotaExceededError, SecurityError 등 추가
  - getErrorCategory() 함수 추가

- [x] **비디오 생성 타임아웃** [Medium]
  - `video-generator.js:7, 55-161` - 최대 60초 제한
  - 프레임 렌더링 에러 처리
  - cleanup() 함수로 이미지 메모리 해제

- [x] **Image 메모리 해제** [High]
  - `video-generator.js:60-65` - 비디오 생성 완료 후 `img.src = ''`
  - `db-api.js:509-510` - 썸네일 생성 후 이미지 참조 해제

- [x] **IndexedDB 인덱스 추가** [Medium]
  - `db.js:32-49` - version 3 마이그레이션
  - 복합 인덱스: `[session_id+category]`, `[job_id+sequence]`, `[work_date+status]`

- [x] **번들 최적화** [Medium]
  - `vite.config.js:48-54` - terser 옵션 추가
  - `drop_console: true` (프로덕션)

### Phase 4 (2025-12-01)

- [x] **Deprecated 메서드 교체** [High]
  - `db.js:210` - `substr()` → `slice()`

- [x] **crypto.getRandomValues 적용** [Low]
  - `db.js:201-212` - generateSessionId()에서 crypto API 사용
  - Math.random() 대체

- [x] **CDN SRI 해시 추가** [Low]
  - `index.html` - Bootstrap integrity 속성 추가
  - crossorigin="anonymous" 추가

---

## 남은 작업 (Optional)

### Style
- [ ] **Magic Numbers 상수화** [Medium]
  - 24시간, 30분 등 → 상수 정의 (일부 적용됨)
  - `MS_PER_HOUR`, `MS_PER_DAY` 등

- [ ] **JSDoc 보완** [Low]
  - `@private` 태그 추가
  - 반환 타입 상세화
  - 모듈 레벨 문서 추가

- [ ] **사용하지 않는 Import 정리** [Low]
  - `tests/unit/upload.test.js:3` - `addPhotoToCategory`

### Performance
- [x] **DOM 렌더링 최적화** [High] ✅ 완료
  - `upload.html` - DocumentFragment + 증분 업데이트 (addPhotoToGrid, removePhotoFromGrid)
  - `gallery.html` - DocumentFragment + createJobCardElement

- [ ] **Sequence 정렬 통일** [Medium]
  - `state.js` - IndexedDB와 LocalStorage sequence 값 통일

---

## 테스트 결과

### E2E Tests (Playwright)
- **총 테스트**: 22개
- **통과**: 22개
- **실패**: 0개
- **브라우저**: Chrome, Firefox, Safari

---

## 쇼츠 품질 향상 (PRD-0011 v3.0)

**총 비용: $0** | **기간: 6주** | **PRD**: `tasks/prds/0011-prd-shorts-enhancement.md`

### Phase MVP: 핵심 기능 (3주) ⭐⭐

#### 1. 이미지 순서 설정 (자동)
- [ ] `src/js/video-sequencer.js` 생성
  - extractOrderFromFilename() - 파일명에서 타임스탬프/순번 추출
  - sortPhotosByFilename() - 촬영 순서 정렬
  - sortPhotosByCategoryThenFilename() - 카테고리 우선 정렬

#### 2. 영상 생성 (유지시간 설정)
- [ ] `video-generator.js` 옵션 확장
  - photoDuration 설정 (10~15초) - 자막 읽기 시간 고려
  - VIDEO_OPTIONS 상수

#### 3. BGM 삽입
- [ ] `src/assets/bgm/` 폴더 생성 + manifest.json
- [ ] 사용자가 BGM 파일 직접 추가
- [ ] `src/js/bgm-manager.js` 생성
  - getBGMList() - manifest.json 기반
  - loadRandomBGM() - 랜덤 BGM + 랜덤 시작 지점
- [ ] `src/js/audio-mixer.js` 생성
  - mixBGMToStream(), fadeAudio()

#### 4. 자막 삽입
- [ ] `src/js/subtitle-renderer.js` 생성
  - CATEGORY_SUBTITLES (입고/문제/과정/해결/출고)
  - SUBTITLE_STYLE, SAFE_ZONE 상수
  - renderSubtitle()

#### 5. 고정 정보 삽입 (로고/연락처)
- [ ] `src/js/branding-renderer.js` 생성
  - renderLogo(), renderContact()
  - loadBranding(), saveBranding() (LocalStorage)

#### UI & 통합
- [ ] `job-detail.html` 마케팅 영상 옵션 UI 추가
- [ ] `video-generator.js` MVP 기능 통합
- [ ] 단위 테스트 작성
- [ ] E2E 테스트 작성

---

### Phase 2: AI 나레이션 (3주) ⭐⭐⭐

- [ ] Google Cloud Console TTS API 활성화
- [ ] API 키 발급 및 환경변수 설정
- [ ] `src/js/narration-generator.js` 생성
  - generateNarration() (Google TTS)
  - SCRIPT_TEMPLATES, VOICE_OPTIONS
- [ ] `vite.config.js` TTS API 프록시 설정
- [ ] `audio-mixer.js` 나레이션+BGM 믹싱 추가
- [ ] `job-detail.html` 나레이션 UI 추가
- [ ] 단위 테스트 작성

### 환경변수 (.env)

```
# Phase 2에서 필요
VITE_GOOGLE_TTS_API_KEY=
```

---

## 분산 아키텍처 (PRD-0012)

**예상 비용: $25~66/월** | **기간: 5주** | **PRD**: `tasks/prds/0012-prd-distributed-architecture.md`

### Phase 1: Supabase 연동 (1주)

- [ ] Supabase 프로젝트 생성
- [ ] 데이터베이스 스키마 마이그레이션 (jobs, photos, technicians)
- [ ] Storage 버킷 생성 + RLS 정책
- [ ] `src/js/supabase-client.js` 생성
- [ ] 환경변수 설정 (`.env`)
- [ ] 기존 `db-api.js` → Supabase 마이그레이션

### Phase 2: PWA 오프라인 동기화 (1주)

- [ ] `src/js/sync-queue.js` 생성
- [ ] `db.js` 스키마 확장 (upload_queue)
- [ ] 네트워크 상태 표시 UI
- [ ] 큐 상태 표시 UI ("3개 업로드 대기 중")
- [ ] 수동 동기화 버튼

### Phase 3: 서버 비디오 생성 (2주)

- [ ] 옵션 선택 (Render + FFmpeg vs Creatomate)
- [ ] Video Worker 서버 구현
- [ ] Supabase Edge Function (트리거)
- [ ] BGM 믹싱 기능 (FFmpeg)
- [ ] 자막 오버레이 (drawtext filter)
- [ ] 로고 워터마크 (overlay filter)

### Phase 4: Push 알림 (1주)

- [ ] VAPID 키 생성
- [ ] `src/js/push-manager.js` 생성
- [ ] Service Worker Push 핸들러
- [ ] Supabase에 구독 테이블 추가
- [ ] 서버에서 Push 전송

### 환경변수 (.env)

```
# 프론트엔드
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_VAPID_PUBLIC_KEY=

# Video Worker
SUPABASE_SERVICE_KEY=
VAPID_PRIVATE_KEY=
```

---

## 참고

- 코드 리뷰 보고서: 2025-12-01
- 총 발견 이슈: 56개 (Critical 9, High 16, Medium 19, Low 12)
- 초기 점수: 62/100
- **개선 후 점수**: ~85/100 (추정)

### 커밋 내역
1. `fix: Phase 1 보안 및 성능 개선`
2. `test: fix E2E tests to match actual HTML structure`
3. `feat: Phase 2-4 개선사항 구현`
