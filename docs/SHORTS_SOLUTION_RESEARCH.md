# 쇼츠/릴스 제작 솔루션 종합 리서치 보고서

**작성일**: 2025-12-01
**목적**: 시청자가 관심있게 지켜볼 수준의 쇼츠 제작을 위한 솔루션 검색 및 추천

---

## Executive Summary

Photo Factory PWA의 마케팅 영상을 **시청자가 끝까지 시청할 수준**으로 업그레이드하기 위한 4가지 핵심 영역을 조사했습니다:

| 영역 | 추천 1순위 | 월 비용 | 통합 난이도 |
|------|-----------|---------|------------|
| **자막** | Whisper API | $5.40 (100개 영상) | ⭐⭐⭐ |
| **BGM** | Mubert API | $49 | ⭐⭐ |
| **음성** | CLOVA Voice | 9만원 | ⭐⭐⭐ |
| **편집** | Creatomate API | $41~99 | ⭐⭐⭐ |

**총 예상 비용**: $100~150/월 (약 13~20만원)

---

## 1. AI 자막/텍스트 오버레이

### 추천 솔루션

| 순위 | 솔루션 | 가격 (분당) | 한국어 품질 | JavaScript 통합 |
|------|--------|------------|------------|----------------|
| **1위** | **Whisper API** | $0.006 | ⭐⭐⭐⭐⭐ | ✅ openai-node |
| 2위 | AssemblyAI | $0.0025 | ⭐⭐⭐⭐ | ✅ assemblyai |
| 3위 | Deepgram | $0.0043 | ⭐⭐⭐⭐ | ✅ @deepgram/sdk |

### Whisper API 통합 예시

```javascript
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function generateSubtitles(audioBlob) {
  const transcription = await openai.audio.transcriptions.create({
    file: audioBlob,
    model: "whisper-1",
    language: "ko",
    response_format: "srt"
  });
  return transcription;
}
```

### 트렌디한 자막 스타일 (2025)

| 요소 | 트렌드 |
|------|--------|
| **폰트** | 노토산스, 배민(도현/주아), 지마켓체 |
| **색상** | 흰색+검정 테두리, 노랑 하이라이트 |
| **애니메이션** | 단어별 페이드인, 말풍선 효과 |
| **레이아웃** | 4줄 이하, Safe Zone 내 배치 |

---

## 2. BGM/배경음악 자동 매칭

### 추천 솔루션

| 순위 | 솔루션 | 월 비용 | 저작권 | API |
|------|--------|--------|--------|-----|
| **1위** | **Mubert API** | $49~ | ✅ 완전 안전 | ✅ REST |
| 2위 | Soundraw API | $500 | ✅ 완전 안전 | ✅ (파트너십) |
| 3위 | Artlist | $25/월 | ✅ 생애 라이선스 | ❌ 없음 |

### 저작권 안전성 등급

| 솔루션 | 안전성 | 이유 |
|--------|--------|------|
| Mubert/Soundraw | ✅✅✅ | 완전 오리지널 AI 생성 |
| Artlist/Epidemic | ✅✅ | 라이선스 음악 |
| **Suno/Udio** | ⚠️ **위험** | 레이블 소송 진행 중 |

### Mubert API 통합 예시

```javascript
async function generateBGM(mood, duration) {
  const response = await fetch('https://music-api.mubert.com/api/v3/public/tracks', {
    method: 'POST',
    headers: {
      'customer-id': process.env.MUBERT_ID,
      'access-token': process.env.MUBERT_TOKEN
    },
    body: JSON.stringify({
      mood: mood,        // 'upbeat', 'inspiring', 'calm'
      duration: duration, // 초 단위
      format: 'mp3'
    })
  });
  return await response.blob();
}
```

---

## 3. AI 음성/나레이션

### 추천 솔루션

| 순위 | 솔루션 | 한국어 품질 | 월 비용 | API |
|------|--------|------------|--------|-----|
| **1위** | **CLOVA Voice** | ⭐⭐⭐⭐⭐ | 9만원 | ✅ REST |
| 2위 | ElevenLabs | ⭐⭐⭐ | $5~99 | ✅ SDK |
| 3위 | Google TTS | ⭐⭐⭐⭐ | 무료 (WaveNet) | ✅ SDK |

### 한국어 TTS 비교

| 서비스 | 장점 | 단점 |
|--------|------|------|
| **CLOVA** | 억양/발음 완벽, 100가지 음성 | 가격 높음 (9만원/월) |
| **ElevenLabs** | 감정 표현 최고, 음성 클로닝 | 한국어 "외국인 느낌" |
| **Google** | 무료 할당량 넉넉 | 음성 수 제한 |

### CLOVA Voice 통합 예시

```javascript
async function generateNarration(text, speaker = 'nara') {
  const response = await fetch('https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts', {
    method: 'POST',
    headers: {
      'X-NCP-APIGW-API-KEY-ID': process.env.CLOVA_CLIENT_ID,
      'X-NCP-APIGW-API-KEY': process.env.CLOVA_CLIENT_SECRET,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      speaker: speaker,
      text: text,
      format: 'mp3'
    })
  });
  return await response.blob();
}
```

---

## 4. 사진 순서/스토리텔링 자동화

### 추천 솔루션

| 순위 | 솔루션 | 유형 | 월 비용 | JavaScript |
|------|--------|------|--------|-----------|
| **1위** | **Creatomate** | API | $41~99 | ✅ SDK |
| 2위 | Shotstack | API | $49~99 | ✅ SDK |
| 3위 | Canvas+MediaRecorder | 브라우저 | $0 | ✅ 네이티브 |

### Instagram Reels 기술 사양

| 항목 | 권장값 |
|------|--------|
| 해상도 | 1080 x 1920 (9:16) |
| 프레임레이트 | 30fps |
| 코덱 | H.264 (MP4) |
| 비트레이트 | 3,500~5,000 kbps |
| 길이 | 15~30초 |

### Safe Zone 가이드라인

```
┌─────────────────────┐
│ ← 60px  ↑ 108px     │ 상단: Instagram UI
│   ┌─────────────┐   │
│   │   SAFE      │   │ 텍스트/중요 요소
│   │   ZONE      │   │ 이 영역에만 배치
│   │   (4:5)     │   │
│   └─────────────┘   │
│        ↓ 320px      │ 하단: 캡션/버튼
└─────────────────────┘
```

### 스토리 템플릿: "문제→해결" (20초)

| 시간 | 카테고리 | 효과 | 텍스트 |
|------|----------|------|--------|
| 0-3초 | before_wheel | 줌인 | "이런 휠도 복원 가능할까요?" |
| 3-6초 | before_car | 정적 | "{차종} 입고" |
| 6-12초 | during (2장) | 빠른 컷 | "전문가의 손길" |
| 12-16초 | after_wheel | 줌아웃 | "완벽 복원!" |
| 16-20초 | after_car | 정적+로고 | "출고 완료" |

---

## 5. Photo Factory 통합 로드맵

### Phase 1: MVP 개선 (즉시 - 비용 $0)

현재 `video-generator.js` 개선:

```javascript
// 추가할 기능
const STORY_TEMPLATES = {
  problemSolution: {
    sequence: ['before_wheel', 'before_car', 'during', 'after_wheel', 'after_car'],
    durations: [3, 3, 6, 4, 4],
    effects: ['zoom-in', 'static', 'fast-cut', 'zoom-out', 'static']
  }
};

const SAFE_ZONE = {
  top: 108,
  bottom: 320,
  left: 60,
  right: 120
};

// Ken Burns 효과
function applyKenBurns(ctx, img, progress, type) {
  const scale = type === 'zoom-in' ? 1 + progress * 0.2 : 1.2 - progress * 0.2;
  // ...
}
```

**예상 개발 시간**: 1주

---

### Phase 2: 자막 추가 (1개월 - 비용 ~$6/월)

Whisper API 통합:

```javascript
// src/js/subtitle-generator.js
import OpenAI from 'openai';

export async function addSubtitles(videoBlob) {
  const openai = new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_KEY });

  // 1. 오디오 추출 (나레이션이 있는 경우)
  // 2. Whisper API로 자막 생성
  // 3. Canvas에 자막 오버레이
}
```

---

### Phase 3: 나레이션 + BGM (3개월 - 비용 ~15만원/월)

```javascript
// src/js/audio-generator.js

// 1. 스크립트 기반 나레이션 (CLOVA Voice)
const narration = await generateNarration(
  "BMW 5시리즈 휠 복원 완료되었습니다.",
  "nara"
);

// 2. 무드 기반 BGM (Mubert)
const bgm = await generateBGM('inspiring', 20);

// 3. 오디오 믹싱 (Web Audio API)
const mixed = await mixAudio(narration, bgm, 0.3); // BGM 30% 볼륨
```

---

### Phase 4: 고급 편집 API (6개월 - 비용 ~$100/월)

Creatomate API로 고품질 렌더링:

```javascript
// src/js/api-video-generator.js
import Creatomate from 'creatomate';

export async function generateHighQualityVideo(photos, metadata) {
  const client = new Creatomate.Client(CREATOMATE_API_KEY);

  const source = {
    outputFormat: 'mp4',
    width: 1080,
    height: 1920,
    elements: [
      // 사진 시퀀스
      ...photos.map((photo, i) => ({
        type: 'image',
        source: photo.image_data,
        time: [i * 3, (i + 1) * 3],
        animations: [{ type: 'ken-burns' }]
      })),
      // 자막
      { type: 'text', text: metadata.car_model, ... },
      // BGM 트랙
      { type: 'audio', source: bgmUrl, volume: 0.3 }
    ]
  };

  return await client.render({ source });
}
```

---

## 6. 비용 분석

### 월 100개 영상 기준

| 항목 | 솔루션 | 월 비용 |
|------|--------|---------|
| 자막 | Whisper API | $5.40 |
| BGM | Mubert Trial | $49 |
| 나레이션 | CLOVA Voice | 9만원 |
| 편집 | Creatomate | $41~99 |
| **합계** | | **~$195 (약 26만원)** |

### 무료 대안 조합 (MVP)

| 항목 | 솔루션 | 비용 |
|------|--------|------|
| 자막 | Web Speech API | $0 |
| BGM | YouTube Audio Library | $0 |
| 나레이션 | Google TTS (무료 할당량) | $0 |
| 편집 | Canvas + MediaRecorder | $0 |
| **합계** | | **$0** |

---

## 7. 결론 및 권장사항

### 즉시 적용 (Phase 1)

1. **스토리 템플릿** 추가 (문제→해결 구조)
2. **Safe Zone** 가이드라인 적용
3. **Ken Burns 효과** 구현
4. **자막 오버레이** 기능 추가

### 단기 목표 (3개월)

1. **Whisper API** 통합 (자동 자막)
2. **CLOVA Voice** 테스트 (나레이션)
3. 사용자 피드백 수집

### 중기 목표 (6개월)

1. **Mubert API** 통합 (저작권 안전 BGM)
2. **Creatomate** 하이브리드 (고품질 옵션)
3. 멀티 플랫폼 지원 (YouTube, TikTok, Instagram)

---

## Sources

### 자막
- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [AssemblyAI](https://www.assemblyai.com/)
- [Deepgram](https://deepgram.com/)

### BGM
- [Mubert API](https://mubert.com/)
- [Soundraw](https://soundraw.io/)
- [Artlist](https://artlist.io/)

### 음성
- [CLOVA Voice](https://www.ncloud.com/product/aiService/clovaVoice)
- [ElevenLabs](https://elevenlabs.io/)
- [Google Cloud TTS](https://cloud.google.com/text-to-speech)

### 편집
- [Creatomate](https://creatomate.com/)
- [Shotstack](https://shotstack.io/)
- [Instagram Reels Safe Zone](https://www.minta.ai/blog-post/instagram-safe-zone)
