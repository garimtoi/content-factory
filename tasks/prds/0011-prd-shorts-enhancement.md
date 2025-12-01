# PRD-0011: 쇼츠/릴스 품질 향상 - 무료 솔루션 기반

**작성일**: 2025-12-01
**버전**: 3.0.0
**상태**: 📋 계획됨
**우선순위**: P1 (High)
**총 비용**: **$0** (모든 Phase 무료)

---

## 1. Executive Summary

Photo Factory의 마케팅 영상을 **시청자가 끝까지 시청할 수준**으로 업그레이드합니다.
모든 기능을 **무료 솔루션**으로 구현합니다.

### 목표
- 현재: 단순 슬라이드쇼 (WebM, 무음)
- 목표: 프로 수준 쇼츠 (MP4, 자막+BGM+나레이션+효과)

### 단계별 요약

| Phase | 난이도 | 비용 | 기간 | 핵심 기능 |
|-------|--------|------|------|----------|
| **MVP** | ⭐⭐ 보통 | $0 | 3주 | 이미지 순서, 영상 생성, BGM, 자막, 로고/연락처 |
| **2** | ⭐⭐⭐ 어려움 | $0 | 3주 | AI 나레이션 (Google TTS) |

**총 개발 기간**: 6주
**총 비용**: $0

---

## 2. Phase MVP: 핵심 기능 (난이도: ⭐⭐)

### 개요

| 항목 | 내용 |
|------|------|
| **목표** | 실용적인 마케팅 영상 생성 기능 완성 |
| **비용** | $0 |
| **기간** | 3주 |
| **의존성** | 없음 |

### MVP 기능 목록

| # | 기능 | 설명 |
|---|------|------|
| 1 | 이미지 순서 설정 | 드래그앤드롭으로 사진 순서 변경 |
| 2 | 영상 생성 | 이미지당 유지시간 설정 가능 (1~5초) |
| 3 | BGM 삽입 | YouTube Audio Library BGM 내장 |
| 4 | 자막 삽입 | 카테고리별 텍스트 오버레이 |
| 5 | 고정 정보 삽입 | 로고 + 연락처 워터마크 |

---

### 2.1 이미지 순서 설정 (자동)

**방식**: 파일명 분석으로 자동 순서 결정 (타임라인 기반)

**이유**: 사진을 찍는 순서대로 영상에 배치해도 자연스러움

**파일**: `src/js/video-sequencer.js` (신규)

```javascript
/**
 * 영상용 이미지 순서 관리 - 파일명 기반 자동 정렬
 */

/**
 * 파일명에서 타임스탬프/순서 추출
 * 지원 패턴:
 * - IMG_20251201_143052.jpg (날짜_시간)
 * - 20251201_143052.jpg
 * - IMG_0001.jpg (순번)
 * - photo_001.jpg
 */
function extractOrderFromFilename(filename) {
  // 패턴 1: 날짜시간 (YYYYMMDD_HHMMSS 또는 YYYYMMDDHHMMSS)
  const dateTimeMatch = filename.match(/(\d{8})[_-]?(\d{6})/);
  if (dateTimeMatch) {
    return parseInt(dateTimeMatch[1] + dateTimeMatch[2]);
  }

  // 패턴 2: 순번 (IMG_0001, photo_001, 001 등)
  const seqMatch = filename.match(/[_-]?(\d{3,4})\./);
  if (seqMatch) {
    return parseInt(seqMatch[1]);
  }

  // 패턴 3: created_at 타임스탬프 (fallback)
  return 0;
}

/**
 * 사진을 파일명 기준으로 자동 정렬 (타임라인 순)
 * @param {Array} photos - 사진 배열
 * @returns {Array} - 정렬된 사진 배열
 */
export function sortPhotosByFilename(photos) {
  return [...photos].sort((a, b) => {
    const orderA = extractOrderFromFilename(a.file_name || '');
    const orderB = extractOrderFromFilename(b.file_name || '');

    // 파일명에서 순서를 찾지 못한 경우 created_at 사용
    if (orderA === 0 && orderB === 0) {
      return new Date(a.created_at) - new Date(b.created_at);
    }

    return orderA - orderB;
  });
}

/**
 * 카테고리 우선 + 파일명 순 정렬 (옵션)
 */
export function sortPhotosByCategoryThenFilename(photos) {
  const categoryOrder = ['before_car', 'before_wheel', 'during', 'after_wheel', 'after_car'];

  return [...photos].sort((a, b) => {
    const catA = categoryOrder.indexOf(a.category);
    const catB = categoryOrder.indexOf(b.category);

    if (catA !== catB) return catA - catB;

    // 같은 카테고리 내에서는 파일명 순
    const orderA = extractOrderFromFilename(a.file_name || '');
    const orderB = extractOrderFromFilename(b.file_name || '');
    return orderA - orderB;
  });
}
```

**정렬 옵션** (UI):

```html
<div class="mb-3">
  <label class="form-label fw-bold">1. 이미지 순서</label>
  <select class="form-select form-select-sm" id="sort-mode">
    <option value="timeline">📷 촬영 순서 (타임라인)</option>
    <option value="category">📁 카테고리 우선</option>
  </select>
  <small class="text-muted">파일명에서 자동으로 순서를 분석합니다</small>
</div>
```

---

### 2.2 영상 생성 (유지시간 설정)

**파일**: `src/js/video-generator.js` (수정)

```javascript
/**
 * 영상 생성 옵션 확장
 */
export const VIDEO_OPTIONS = {
  // 이미지당 유지시간 (ms) - 자막 읽기 시간 고려
  photoDuration: {
    min: 10000,   // 10초
    max: 15000,   // 15초
    default: 12000, // 12초
    step: 1000
  },
  // 전환 효과 시간
  transitionDuration: 500,
  // 출력 해상도
  width: 1080,
  height: 1920,
  fps: 30
};

/**
 * 영상 생성 (개선)
 * @param {Array} photos - 정렬된 사진 배열
 * @param {Object} jobInfo - 작업 정보
 * @param {Object} options - 옵션
 */
export async function generateMarketingVideo(photos, jobInfo, options = {}) {
  const {
    photoDuration = VIDEO_OPTIONS.photoDuration.default,
    transitionDuration = VIDEO_OPTIONS.transitionDuration,
    bgm = null,
    bgmVolume = 0.3,
    subtitles = true,
    branding = null,  // { logo, contact }
    onProgress = null
  } = options;

  // ... 기존 로직 + 새 옵션 적용
}
```

**UI 요소**:

```html
<div class="mb-3">
  <label class="form-label">이미지당 유지시간</label>
  <input type="range" class="form-range" id="photo-duration"
         min="10" max="15" step="1" value="12">
  <div class="d-flex justify-content-between">
    <small>10초</small>
    <small id="duration-value">12초</small>
    <small>15초</small>
  </div>
  <small class="text-muted">자막을 읽을 시간이 필요합니다</small>
</div>
```

---

### 2.3 BGM 삽입

**방식**: 사용자가 `src/assets/bgm/` 폴더에 BGM 파일을 직접 추가
- 랜덤 BGM 선택
- 랜덤 시작 지점 (매번 다른 느낌)

**파일**: `src/js/bgm-manager.js` (신규)

```javascript
/**
 * BGM 관리자 - 폴더 기반 랜덤 선택
 * 사용자가 src/assets/bgm/ 폴더에 BGM 파일을 직접 추가
 */

const BGM_FOLDER = '/assets/bgm';

/**
 * BGM 폴더에서 파일 목록 가져오기
 * (빌드 시점에 파일 목록을 생성하거나, manifest 파일 사용)
 */
export async function getBGMList() {
  try {
    const response = await fetch(`${BGM_FOLDER}/manifest.json`);
    if (response.ok) {
      return await response.json();
    }
  } catch (e) {
    console.warn('BGM manifest not found, using fallback');
  }

  // Fallback: 기본 파일명 패턴
  return [
    { file: 'bgm1.mp3' },
    { file: 'bgm2.mp3' },
    { file: 'bgm3.mp3' }
  ];
}

/**
 * 랜덤 BGM 로드 (랜덤 시작 지점)
 * @returns {Promise<{audio: HTMLAudioElement, startTime: number}>}
 */
export async function loadRandomBGM() {
  const bgmList = await getBGMList();
  const selected = bgmList[Math.floor(Math.random() * bgmList.length)];

  const audio = new Audio(`${BGM_FOLDER}/${selected.file}`);

  return new Promise((resolve, reject) => {
    audio.onloadedmetadata = () => {
      // 랜덤 시작 지점 (0% ~ 50% 사이에서 시작)
      const maxStartRatio = 0.5;
      const randomStartTime = Math.random() * audio.duration * maxStartRatio;

      audio.currentTime = randomStartTime;
      resolve({ audio, startTime: randomStartTime, file: selected.file });
    };
    audio.onerror = reject;
    audio.load();
  });
}

/**
 * 특정 BGM 로드
 */
export async function loadBGM(filename) {
  const audio = new Audio(`${BGM_FOLDER}/${filename}`);

  return new Promise((resolve, reject) => {
    audio.onloadedmetadata = () => {
      const randomStartTime = Math.random() * audio.duration * 0.5;
      audio.currentTime = randomStartTime;
      resolve({ audio, startTime: randomStartTime });
    };
    audio.onerror = reject;
    audio.load();
  });
}
```

**파일**: `src/js/audio-mixer.js` (신규)

```javascript
/**
 * Web Audio API 기반 오디오 믹싱
 */

/**
 * BGM을 비디오 스트림에 믹싱
 */
export function mixBGMToStream(videoStream, bgmAudio, volume = 0.3) {
  const audioContext = new AudioContext();

  const bgmSource = audioContext.createMediaElementSource(bgmAudio);
  const gainNode = audioContext.createGain();
  gainNode.gain.value = volume;

  bgmSource.connect(gainNode);

  const destination = audioContext.createMediaStreamDestination();
  gainNode.connect(destination);

  // 비디오 트랙 + 오디오 트랙 합성
  const videoTrack = videoStream.getVideoTracks()[0];
  const audioTrack = destination.stream.getAudioTracks()[0];

  return new MediaStream([videoTrack, audioTrack]);
}

/**
 * 오디오 페이드 인/아웃
 */
export function fadeAudio(gainNode, startValue, endValue, duration) {
  const now = gainNode.context.currentTime;
  gainNode.gain.setValueAtTime(startValue, now);
  gainNode.gain.linearRampToValueAtTime(endValue, now + duration);
}
```

**BGM Manifest 파일** (`src/assets/bgm/manifest.json`):

```json
[
  { "file": "upbeat.mp3", "name": "Upbeat" },
  { "file": "inspiring.mp3", "name": "Inspiring" },
  { "file": "energetic.mp3", "name": "Energetic" }
]
```

> 사용자가 BGM 파일을 추가하면 `manifest.json`도 함께 업데이트

**UI 요소**:

```html
<div class="mb-3">
  <div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="bgm-toggle" checked>
    <label class="form-check-label" for="bgm-toggle">배경음악</label>
  </div>
  <div id="bgm-options" class="mt-2">
    <input type="range" class="form-range" id="bgm-volume" min="0" max="100" value="30">
    <small class="text-muted">볼륨: <span id="bgm-volume-value">30</span>%</small>
    <div class="mt-1">
      <small class="text-muted">📁 src/assets/bgm/ 폴더에서 랜덤 선택</small>
    </div>
  </div>
</div>
```

---

### 2.4 자막 삽입

**파일**: `src/js/subtitle-renderer.js` (신규)

```javascript
/**
 * 카테고리별 자막 렌더링
 */

// 카테고리별 기본 자막
export const CATEGORY_SUBTITLES = {
  before_car: '입고',
  before_wheel: '문제 부위',
  during: '작업 중',
  after_wheel: '복원 완료',
  after_car: '출고'
};

// 자막 스타일
export const SUBTITLE_STYLE = {
  font: 'bold 42px "Noto Sans KR", -apple-system, sans-serif',
  fillColor: '#FFFFFF',
  strokeColor: '#000000',
  strokeWidth: 4,
  bgColor: 'rgba(0, 0, 0, 0.6)',
  padding: 16,
  borderRadius: 8
};

// Instagram Safe Zone
export const SAFE_ZONE = {
  top: 108,
  bottom: 320,
  left: 60,
  right: 120
};

/**
 * 자막 렌더링
 */
export function renderSubtitle(ctx, text, canvas) {
  if (!text) return;

  const { width, height } = canvas;
  const y = height - SAFE_ZONE.bottom - 80;

  ctx.font = SUBTITLE_STYLE.font;
  ctx.textAlign = 'center';

  // 배경 박스
  const metrics = ctx.measureText(text);
  const boxW = metrics.width + SUBTITLE_STYLE.padding * 2;
  const boxH = 56;
  const boxX = (width - boxW) / 2;
  const boxY = y - boxH / 2 - 10;

  ctx.fillStyle = SUBTITLE_STYLE.bgColor;
  ctx.beginPath();
  ctx.roundRect(boxX, boxY, boxW, boxH, SUBTITLE_STYLE.borderRadius);
  ctx.fill();

  // 텍스트 (테두리 + 채우기)
  ctx.strokeStyle = SUBTITLE_STYLE.strokeColor;
  ctx.lineWidth = SUBTITLE_STYLE.strokeWidth;
  ctx.strokeText(text, width / 2, y);

  ctx.fillStyle = SUBTITLE_STYLE.fillColor;
  ctx.fillText(text, width / 2, y);
}

/**
 * 카테고리에서 자막 가져오기
 */
export function getSubtitleForCategory(category, customSubtitles = {}) {
  return customSubtitles[category] || CATEGORY_SUBTITLES[category] || '';
}
```

**UI 요소**:

```html
<div class="mb-3">
  <div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="subtitle-toggle" checked>
    <label class="form-check-label" for="subtitle-toggle">자막 표시</label>
  </div>
</div>
```

---

### 2.5 고정 정보 삽입 (로고/연락처)

**파일**: `src/js/branding-renderer.js` (신규)

```javascript
/**
 * 브랜딩 정보 렌더링 (로고, 연락처)
 */

// 기본 브랜딩 설정
export const DEFAULT_BRANDING = {
  logo: null,  // base64 or URL
  contact: '',
  position: 'bottom-right',  // top-left, top-right, bottom-left, bottom-right
  opacity: 0.8
};

// 위치별 좌표
const POSITIONS = {
  'top-left': (w, h, logoW, logoH) => ({ x: 20, y: 20 }),
  'top-right': (w, h, logoW, logoH) => ({ x: w - logoW - 20, y: 20 }),
  'bottom-left': (w, h, logoW, logoH) => ({ x: 20, y: h - logoH - 340 }),
  'bottom-right': (w, h, logoW, logoH) => ({ x: w - logoW - 20, y: h - logoH - 340 })
};

/**
 * 로고 렌더링
 */
export function renderLogo(ctx, logoImg, canvas, position = 'bottom-right', opacity = 0.8) {
  if (!logoImg) return;

  const maxLogoWidth = 150;
  const maxLogoHeight = 80;

  // 비율 유지하며 크기 조정
  const scale = Math.min(maxLogoWidth / logoImg.width, maxLogoHeight / logoImg.height);
  const logoW = logoImg.width * scale;
  const logoH = logoImg.height * scale;

  const posFunc = POSITIONS[position] || POSITIONS['bottom-right'];
  const { x, y } = posFunc(canvas.width, canvas.height, logoW, logoH);

  ctx.globalAlpha = opacity;
  ctx.drawImage(logoImg, x, y, logoW, logoH);
  ctx.globalAlpha = 1;
}

/**
 * 연락처 렌더링
 */
export function renderContact(ctx, contact, canvas, position = 'bottom-right') {
  if (!contact) return;

  const { width, height } = canvas;

  ctx.font = 'bold 24px -apple-system, sans-serif';
  ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
  ctx.textAlign = position.includes('right') ? 'right' : 'left';

  const x = position.includes('right') ? width - 30 : 30;
  const y = height - 280;

  // 배경
  const metrics = ctx.measureText(contact);
  const bgX = position.includes('right') ? x - metrics.width - 16 : x - 8;

  ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
  ctx.fillRect(bgX, y - 24, metrics.width + 16, 32);

  // 텍스트
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(contact, x, y);
}

/**
 * 브랜딩 로드 (LocalStorage에서)
 */
export function loadBranding() {
  const saved = localStorage.getItem('photoFactory_branding');
  return saved ? JSON.parse(saved) : DEFAULT_BRANDING;
}

/**
 * 브랜딩 저장
 */
export function saveBranding(branding) {
  localStorage.setItem('photoFactory_branding', JSON.stringify(branding));
}
```

**UI 요소**:

```html
<div class="mb-3">
  <div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="branding-toggle" checked>
    <label class="form-check-label" for="branding-toggle">로고/연락처</label>
  </div>
  <div id="branding-options" class="mt-2">
    <div class="mb-2">
      <label class="form-label small">로고 이미지</label>
      <input type="file" class="form-control form-control-sm" id="logo-upload" accept="image/*">
      <div id="logo-preview" class="mt-1"></div>
    </div>
    <div class="mb-2">
      <label class="form-label small">연락처</label>
      <input type="text" class="form-control form-control-sm" id="contact-input"
             placeholder="010-1234-5678">
    </div>
    <div>
      <label class="form-label small">위치</label>
      <select class="form-select form-select-sm" id="branding-position">
        <option value="bottom-right">우하단</option>
        <option value="bottom-left">좌하단</option>
        <option value="top-right">우상단</option>
        <option value="top-left">좌상단</option>
      </select>
    </div>
  </div>
</div>
```

---

### MVP 작업 목록

- [ ] `src/js/video-sequencer.js` 생성
- [ ] `src/js/bgm-manager.js` 생성
- [ ] `src/js/audio-mixer.js` 생성
- [ ] `src/js/subtitle-renderer.js` 생성
- [ ] `src/js/branding-renderer.js` 생성
- [ ] `src/assets/bgm/` 폴더 생성 및 BGM 5곡 추가
- [ ] `video-generator.js` MVP 기능 통합
- [ ] `job-detail.html` UI 추가
- [ ] 단위 테스트 작성
- [ ] E2E 테스트 작성

---

## 3. Phase 2: AI 나레이션 (난이도: ⭐⭐⭐)

### 개요

| 항목 | 내용 |
|------|------|
| **목표** | Google TTS로 자동 나레이션 생성 |
| **비용** | $0 (월 100만자 무료) |
| **기간** | 3주 |
| **의존성** | Phase MVP |

### 기술 선택: Google Cloud TTS

- **무료 할당량**: WaveNet 100만자/월 (약 666분 나레이션)
- **한국어 품질**: ⭐⭐⭐⭐ (양호)
- **API**: REST + Node.js SDK

### 구현 내용

#### 3.1 나레이션 생성기

**파일**: `src/js/narration-generator.js` (신규)

```javascript
/**
 * Google TTS 나레이션 생성기
 */

// 스크립트 템플릿
const SCRIPT_TEMPLATES = {
  standard: (jobInfo) => [
    { time: 0, text: `${jobInfo.car_model} 휠 복원을 시작합니다.` },
    { time: 4, text: '손상 부위를 확인합니다.' },
    { time: 8, text: '전문 장비로 복원 작업 중입니다.' },
    { time: 14, text: '깨끗하게 복원 완료!' },
    { time: 18, text: '출고 준비 완료되었습니다.' }
  ],
  short: (jobInfo) => [
    { time: 0, text: '복원 전.' },
    { time: 5, text: '복원 완료!' }
  ]
};

// 음성 옵션
const VOICE_OPTIONS = {
  professional: { name: 'ko-KR-Wavenet-A', pitch: 0, speakingRate: 1.0 },
  friendly: { name: 'ko-KR-Wavenet-B', pitch: 2, speakingRate: 1.1 },
  calm: { name: 'ko-KR-Wavenet-C', pitch: -2, speakingRate: 0.9 }
};

/**
 * Google TTS API 호출
 */
export async function generateNarration(text, voiceType = 'professional') {
  const voice = VOICE_OPTIONS[voiceType];

  const response = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      voice: voice.name,
      pitch: voice.pitch,
      speakingRate: voice.speakingRate
    })
  });

  if (!response.ok) throw new Error('나레이션 생성 실패');
  return await response.blob();
}

/**
 * 전체 나레이션 생성
 */
export async function generateFullNarration(template, jobInfo, voiceType) {
  const scripts = SCRIPT_TEMPLATES[template](jobInfo);
  const narrations = [];

  for (const script of scripts) {
    const audioBlob = await generateNarration(script.text, voiceType);
    narrations.push({ time: script.time, audioBlob, text: script.text });
  }

  return narrations;
}

/**
 * 음성 옵션 목록
 */
export function getVoiceOptions() {
  return Object.entries(VOICE_OPTIONS).map(([key, value]) => ({
    id: key,
    name: key === 'professional' ? '전문적' : key === 'friendly' ? '친근한' : '차분한'
  }));
}
```

#### 3.2 API 프록시

**파일**: `vite.config.js` (수정)

```javascript
// Google TTS API 프록시
server: {
  proxy: {
    '/api/tts': {
      target: 'https://texttospeech.googleapis.com/v1',
      changeOrigin: true,
      rewrite: (path) => '/text:synthesize',
      configure: (proxy) => {
        proxy.on('proxyReq', (proxyReq) => {
          proxyReq.setHeader('X-Goog-Api-Key', process.env.VITE_GOOGLE_TTS_API_KEY);
        });
      }
    }
  }
}
```

#### 3.3 나레이션 + BGM 믹싱

**파일**: `src/js/audio-mixer.js` (확장)

```javascript
/**
 * 나레이션 + BGM 믹싱
 */
export function mixNarrationAndBGM(narrationAudio, bgmAudio, bgmVolume = 0.2) {
  const audioContext = new AudioContext();

  // 나레이션 소스
  const narrationSource = audioContext.createMediaElementSource(narrationAudio);

  // BGM 소스 (나레이션 중 볼륨 낮춤)
  const bgmSource = audioContext.createMediaElementSource(bgmAudio);
  const bgmGain = audioContext.createGain();
  bgmGain.gain.value = bgmVolume;
  bgmSource.connect(bgmGain);

  // 믹싱
  const merger = audioContext.createChannelMerger(2);
  narrationSource.connect(merger, 0, 0);
  bgmGain.connect(merger, 0, 1);

  const destination = audioContext.createMediaStreamDestination();
  merger.connect(destination);

  return destination.stream;
}
```

### Phase 2 작업 목록

- [ ] Google Cloud Console TTS API 활성화
- [ ] API 키 발급 및 환경변수 설정
- [ ] `src/js/narration-generator.js` 생성
- [ ] `vite.config.js` 프록시 설정
- [ ] `audio-mixer.js` 나레이션 믹싱 추가
- [ ] `job-detail.html` 나레이션 UI 추가
- [ ] 스크립트 편집 기능 (선택)
- [ ] 단위 테스트 작성
- [ ] E2E 테스트 작성

---

## 4. UI 전체 구조

### `job-detail.html` 영상 옵션 패널

```html
<div class="card mb-3">
  <div class="card-header">
    <h5><i class="bi bi-camera-video"></i> 마케팅 영상</h5>
  </div>
  <div class="card-body">

    <!-- 1. 이미지 순서 -->
    <div class="mb-3">
      <label class="form-label fw-bold">1. 이미지 순서</label>
      <div id="photo-sequence" class="d-flex flex-wrap gap-2 border rounded p-2">
        <!-- 드래그 가능한 썸네일 -->
      </div>
      <button class="btn btn-sm btn-outline-secondary mt-2" id="reset-sequence">
        기본 순서로
      </button>
    </div>

    <!-- 2. 영상 설정 -->
    <div class="mb-3">
      <label class="form-label fw-bold">2. 영상 설정</label>
      <div class="d-flex align-items-center gap-2">
        <span class="small">이미지당</span>
        <input type="range" class="form-range flex-grow-1" id="photo-duration"
               min="1" max="5" step="0.5" value="2">
        <span class="badge bg-primary" id="duration-value">2초</span>
      </div>
    </div>

    <!-- 3. BGM -->
    <div class="mb-3">
      <div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" id="bgm-toggle" checked>
        <label class="form-check-label fw-bold" for="bgm-toggle">3. BGM</label>
      </div>
      <div id="bgm-options" class="ms-4 mt-2">
        <select class="form-select form-select-sm mb-2" id="bgm-select">
          <option value="random">🎲 랜덤</option>
          <option value="upbeat1">Upbeat</option>
          <option value="inspiring1">Inspiring</option>
          <option value="energetic1">Energetic</option>
          <option value="calm1">Calm</option>
          <option value="dramatic1">Dramatic</option>
        </select>
        <div class="d-flex align-items-center gap-2">
          <i class="bi bi-volume-down"></i>
          <input type="range" class="form-range" id="bgm-volume" min="0" max="100" value="30">
          <span class="small" id="bgm-volume-value">30%</span>
        </div>
      </div>
    </div>

    <!-- 4. 자막 -->
    <div class="mb-3">
      <div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" id="subtitle-toggle" checked>
        <label class="form-check-label fw-bold" for="subtitle-toggle">4. 자막</label>
      </div>
    </div>

    <!-- 5. 로고/연락처 -->
    <div class="mb-3">
      <div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" id="branding-toggle" checked>
        <label class="form-check-label fw-bold" for="branding-toggle">5. 로고/연락처</label>
      </div>
      <div id="branding-options" class="ms-4 mt-2">
        <div class="row g-2">
          <div class="col-6">
            <input type="file" class="form-control form-control-sm" id="logo-upload" accept="image/*">
          </div>
          <div class="col-6">
            <input type="text" class="form-control form-control-sm" id="contact-input"
                   placeholder="연락처">
          </div>
        </div>
      </div>
    </div>

    <!-- Phase 2: AI 나레이션 (추후 활성화) -->
    <div class="mb-3 opacity-50" id="narration-section" style="display:none">
      <div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" id="narration-toggle" disabled>
        <label class="form-check-label fw-bold" for="narration-toggle">
          AI 나레이션 <span class="badge bg-secondary">Coming Soon</span>
        </label>
      </div>
    </div>

  </div>
  <div class="card-footer">
    <button class="btn btn-primary w-100" id="generate-video-btn">
      <i class="bi bi-play-fill"></i> 영상 생성
    </button>
    <div class="progress mt-2 d-none" id="video-progress">
      <div class="progress-bar progress-bar-striped progress-bar-animated"
           role="progressbar" style="width: 0%"></div>
    </div>
  </div>
</div>
```

---

## 5. 파일 구조

```
src/
├── assets/
│   └── bgm/                      # [MVP] YouTube Audio Library BGM
│       ├── upbeat.mp3
│       ├── inspiring.mp3
│       ├── energetic.mp3
│       ├── calm.mp3
│       └── dramatic.mp3
├── js/
│   ├── video-generator.js        # [기존] 영상 생성 (수정)
│   ├── video-sequencer.js        # [MVP] 이미지 순서 관리
│   ├── bgm-manager.js            # [MVP] BGM 관리
│   ├── audio-mixer.js            # [MVP] 오디오 믹싱
│   ├── subtitle-renderer.js      # [MVP] 자막 렌더링
│   ├── branding-renderer.js      # [MVP] 로고/연락처 렌더링
│   └── narration-generator.js    # [Phase 2] AI 나레이션
└── public/
    └── job-detail.html           # UI 수정
```

---

## 6. 비용 요약

| Phase | 기능 | 솔루션 | 비용 |
|-------|------|--------|------|
| **MVP** | 이미지 순서 | 코드 구현 | $0 |
| **MVP** | 영상 생성 | Canvas + MediaRecorder | $0 |
| **MVP** | BGM | YouTube Audio Library | $0 |
| **MVP** | 자막 | 코드 구현 (하드코딩) | $0 |
| **MVP** | 로고/연락처 | 코드 구현 | $0 |
| **Phase 2** | AI 나레이션 | Google TTS (100만자 무료) | $0 |
| **합계** | | | **$0** |

---

## 7. 환경변수

```env
# .env (Phase 2에서 필요)
VITE_GOOGLE_TTS_API_KEY=your-google-tts-api-key
```

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-12-01 | 1.0.0 | 초안 (유료 솔루션) |
| 2025-12-01 | 2.0.0 | 무료 솔루션으로 전환 |
| 2025-12-01 | 3.0.0 | MVP + Phase 2 재구성 |
