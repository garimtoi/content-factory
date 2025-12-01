# PRD-0012: 분산 아키텍처 - 모바일 촬영 + 서버 비디오 생성

**작성일**: 2025-12-01
**버전**: 1.0.0
**상태**: 📋 계획됨
**우선순위**: P1 (High)
**예상 비용**: $25~66/월

---

## 1. Executive Summary

Photo Factory를 **분산 시스템**으로 확장합니다:
- **현장 작업자 (스마트폰)**: 사진 촬영 + 업로드
- **중앙 서버**: 비디오 생성 + 배포

### 현재 vs 목표

| 항목 | 현재 | 목표 |
|------|------|------|
| 아키텍처 | 단일 PWA (모든 작업 클라이언트) | **분산 시스템** |
| 이미지 저장 | IndexedDB (로컬) | **Supabase Storage (클라우드)** |
| 비디오 생성 | Canvas + MediaRecorder (브라우저) | **FFmpeg (서버)** |
| 데이터 동기화 | 없음 (세션 만료 시 삭제) | **실시간 동기화** |

### 비용 예상

| 컴포넌트 | 솔루션 | 월 비용 |
|----------|--------|---------|
| Backend + Storage | Supabase Pro | $25 |
| Frontend Hosting | Vercel Free | $0 |
| Video Worker | Render (선택) | $0~12 |
| Video API | Creatomate (선택) | $0~41 |
| **합계** | | **$25~66** |

---

## 2. 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    📱 현장 작업자 PWA                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ 카메라 촬영  │ →  │ IndexedDB   │ →  │ Upload      │     │
│  │ 카테고리선택 │    │ 오프라인 큐  │    │ Queue       │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
└────────────────────────────────────────────────┼────────────┘
                                                 │ HTTPS
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    ☁️ Supabase Backend                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Auth        │    │ PostgreSQL  │    │ Storage     │     │
│  │ (사용자)    │    │ (jobs,      │    │ (이미지)    │     │
│  │             │    │  photos)    │    │             │     │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘     │
│                            │                   │            │
│  ┌─────────────────────────┴───────────────────┘           │
│  │ Edge Functions (Trigger)                                 │
│  │ - 작업 완료 감지 → 비디오 생성 요청                       │
│  └──────────────────────────┬──────────────────────────────┘
└─────────────────────────────┼───────────────────────────────┘
                              │ Webhook
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              🎬 Video Worker (Render)                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Download    │ →  │ FFmpeg      │ →  │ Upload      │     │
│  │ Images      │    │ Process     │    │ Result      │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
└──────────────────────────────────────────────┼──────────────┘
                                               │
                              ┌────────────────┘
                              ▼
                    📲 Push 알림 → 다운로드 링크
```

---

## 3. Phase 1: Supabase 연동 (1주)

### 3.1 데이터베이스 스키마

**파일**: `supabase/migrations/001_initial_schema.sql`

```sql
-- 사용자 (Supabase Auth 연동)
CREATE TABLE technicians (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  display_name TEXT NOT NULL,
  phone TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 작업
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_number TEXT UNIQUE NOT NULL,  -- WHL250101001
  technician_id UUID REFERENCES technicians(id),
  car_model TEXT NOT NULL,
  work_date DATE DEFAULT CURRENT_DATE,
  status TEXT DEFAULT 'in_progress',  -- in_progress, completed, video_ready
  video_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 사진
CREATE TABLE photos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
  category TEXT NOT NULL,  -- before_car, before_wheel, during, after_wheel, after_car
  storage_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size INTEGER,
  sequence INTEGER DEFAULT 0,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_jobs_technician ON jobs(technician_id);
CREATE INDEX idx_jobs_work_date ON jobs(work_date);
CREATE INDEX idx_photos_job ON photos(job_id);
CREATE INDEX idx_photos_category ON photos(job_id, category);

-- RLS (Row Level Security)
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;

-- 정책: 본인 작업만 접근
CREATE POLICY "Users can view own jobs" ON jobs
  FOR SELECT USING (technician_id = auth.uid());

CREATE POLICY "Users can insert own jobs" ON jobs
  FOR INSERT WITH CHECK (technician_id = auth.uid());

CREATE POLICY "Users can view own photos" ON photos
  FOR SELECT USING (
    job_id IN (SELECT id FROM jobs WHERE technician_id = auth.uid())
  );
```

### 3.2 Storage 버킷

```javascript
// Supabase Dashboard에서 생성 또는 CLI
// supabase storage create-bucket photos --public

// Storage 정책
const STORAGE_POLICIES = {
  bucket: 'photos',
  policies: [
    {
      name: 'Users can upload to own folder',
      definition: `bucket_id = 'photos' AND (storage.foldername(name))[1] = auth.uid()::text`
    },
    {
      name: 'Public read access',
      definition: `bucket_id = 'photos'`,
      operation: 'SELECT'
    }
  ]
};
```

### 3.3 클라이언트 연동

**파일**: `src/js/supabase-client.js` (신규)

```javascript
/**
 * Supabase 클라이언트 설정
 */
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true
  }
});

/**
 * 이미지 업로드
 */
export async function uploadPhoto(jobId, category, file) {
  const userId = (await supabase.auth.getUser()).data.user?.id;
  const fileName = `${Date.now()}_${file.name}`;
  const storagePath = `${userId}/${jobId}/${category}/${fileName}`;

  // 1. Storage에 업로드
  const { data: storageData, error: storageError } = await supabase.storage
    .from('photos')
    .upload(storagePath, file, {
      cacheControl: '3600',
      contentType: file.type
    });

  if (storageError) throw storageError;

  // 2. 메타데이터 저장
  const { data: photoData, error: photoError } = await supabase
    .from('photos')
    .insert({
      job_id: jobId,
      category: category,
      storage_path: storagePath,
      file_name: file.name,
      file_size: file.size
    })
    .select()
    .single();

  if (photoError) throw photoError;

  return photoData;
}

/**
 * 작업 생성
 */
export async function createJob(carModel) {
  const userId = (await supabase.auth.getUser()).data.user?.id;

  // 작업번호 생성 (WHL + YYMMDD + NNN)
  const today = new Date();
  const dateStr = today.toISOString().slice(2, 10).replace(/-/g, '');

  // 오늘 작업 수 조회
  const { count } = await supabase
    .from('jobs')
    .select('*', { count: 'exact', head: true })
    .eq('work_date', today.toISOString().slice(0, 10));

  const seq = String((count || 0) + 1).padStart(3, '0');
  const jobNumber = `WHL${dateStr}${seq}`;

  const { data, error } = await supabase
    .from('jobs')
    .insert({
      job_number: jobNumber,
      technician_id: userId,
      car_model: carModel
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

/**
 * 작업 목록 조회
 */
export async function getJobs(filters = {}) {
  let query = supabase
    .from('jobs')
    .select(`
      *,
      photos (id, category, storage_path)
    `)
    .order('created_at', { ascending: false });

  if (filters.status) {
    query = query.eq('status', filters.status);
  }

  if (filters.date) {
    query = query.eq('work_date', filters.date);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data;
}

/**
 * Public URL 가져오기
 */
export function getPublicUrl(storagePath) {
  const { data } = supabase.storage.from('photos').getPublicUrl(storagePath);
  return data.publicUrl;
}
```

### 3.4 작업 목록

- [ ] Supabase 프로젝트 생성
- [ ] 데이터베이스 스키마 마이그레이션
- [ ] Storage 버킷 생성 + RLS 정책
- [ ] `supabase-client.js` 생성
- [ ] 환경변수 설정 (`.env`)
- [ ] 기존 `db-api.js` → Supabase 마이그레이션

---

## 4. Phase 2: PWA 오프라인 동기화 (1주)

### 4.1 오프라인 큐 시스템

**파일**: `src/js/sync-queue.js` (신규)

```javascript
/**
 * 오프라인 업로드 큐 관리
 * IndexedDB에 저장 → 온라인 시 Supabase로 동기화
 */
import { db } from './db.js';
import { uploadPhoto, createJob } from './supabase-client.js';

// 큐 상태
export const QUEUE_STATUS = {
  PENDING: 'pending',
  UPLOADING: 'uploading',
  SUCCESS: 'success',
  FAILED: 'failed'
};

/**
 * 업로드 큐에 추가
 */
export async function queueUpload(jobId, category, file) {
  // 파일을 Base64로 변환 (IndexedDB 저장용)
  const base64 = await fileToBase64(file);

  const queueItem = {
    job_id: jobId,
    category: category,
    file_name: file.name,
    file_type: file.type,
    file_size: file.size,
    file_data: base64,
    status: QUEUE_STATUS.PENDING,
    retries: 0,
    created_at: new Date().toISOString()
  };

  const id = await db.upload_queue.add(queueItem);

  // 온라인이면 즉시 처리
  if (navigator.onLine) {
    processQueue();
  }

  return id;
}

/**
 * 큐 처리
 */
export async function processQueue() {
  const pending = await db.upload_queue
    .where('status')
    .anyOf([QUEUE_STATUS.PENDING, QUEUE_STATUS.FAILED])
    .and(item => item.retries < 5)
    .toArray();

  console.log(`Processing ${pending.length} queued uploads`);

  for (const item of pending) {
    try {
      // 상태 업데이트
      await db.upload_queue.update(item.id, { status: QUEUE_STATUS.UPLOADING });

      // Base64 → File 변환
      const file = base64ToFile(item.file_data, item.file_name, item.file_type);

      // Supabase 업로드
      await uploadPhoto(item.job_id, item.category, file);

      // 성공 시 큐에서 제거
      await db.upload_queue.delete(item.id);
      console.log(`Upload success: ${item.file_name}`);

    } catch (error) {
      console.error(`Upload failed: ${item.file_name}`, error);

      // 재시도 카운트 증가
      await db.upload_queue.update(item.id, {
        status: QUEUE_STATUS.FAILED,
        retries: item.retries + 1,
        last_error: error.message
      });
    }
  }
}

/**
 * 큐 상태 조회
 */
export async function getQueueStatus() {
  const all = await db.upload_queue.toArray();
  return {
    pending: all.filter(i => i.status === QUEUE_STATUS.PENDING).length,
    uploading: all.filter(i => i.status === QUEUE_STATUS.UPLOADING).length,
    failed: all.filter(i => i.status === QUEUE_STATUS.FAILED).length,
    total: all.length
  };
}

// 네트워크 상태 감지
window.addEventListener('online', () => {
  console.log('Network online - processing queue');
  processQueue();
});

// iOS PWA: 앱 열릴 때 동기화
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && navigator.onLine) {
    processQueue();
  }
});

// 주기적 동기화 (5분마다)
setInterval(() => {
  if (navigator.onLine) {
    processQueue();
  }
}, 5 * 60 * 1000);

// 유틸리티 함수
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function base64ToFile(base64, filename, type) {
  const arr = base64.split(',');
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) u8arr[n] = bstr.charCodeAt(n);
  return new File([u8arr], filename, { type });
}
```

### 4.2 IndexedDB 스키마 확장

**파일**: `src/js/db.js` (수정)

```javascript
// 기존 스키마에 upload_queue 추가
db.version(4).stores({
  // 기존 테이블
  jobs: '++id, job_number, work_date, status',
  photos: '++id, job_id, category, sequence',
  temp_photos: '++id, session_id, category, sequence',

  // 신규: 업로드 큐
  upload_queue: '++id, job_id, category, status, created_at'
});
```

### 4.3 작업 목록

- [ ] `sync-queue.js` 생성
- [ ] `db.js` 스키마 확장 (upload_queue)
- [ ] 네트워크 상태 표시 UI
- [ ] 큐 상태 표시 UI ("3개 업로드 대기 중")
- [ ] 수동 동기화 버튼

---

## 5. Phase 3: 서버 비디오 생성 (2주)

### 5.1 옵션 A: Render + FFmpeg (비용 효율)

**파일**: `video-worker/index.js`

```javascript
/**
 * Video Worker - FFmpeg 기반 서버 사이드 비디오 생성
 */
import express from 'express';
import { createClient } from '@supabase/supabase-js';
import ffmpeg from 'fluent-ffmpeg';
import { promises as fs } from 'fs';
import path from 'path';
import os from 'os';

const app = express();
app.use(express.json());

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

/**
 * 비디오 생성 엔드포인트
 */
app.post('/generate-video', async (req, res) => {
  const { job_id } = req.body;

  try {
    // 1. 작업 정보 조회
    const { data: job } = await supabase
      .from('jobs')
      .select('*, photos(*)')
      .eq('id', job_id)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // 2. 이미지 다운로드
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'video-'));
    const imagePaths = [];

    for (const photo of job.photos) {
      const { data, error } = await supabase.storage
        .from('photos')
        .download(photo.storage_path);

      if (error) throw error;

      const imagePath = path.join(tempDir, photo.file_name);
      await fs.writeFile(imagePath, Buffer.from(await data.arrayBuffer()));
      imagePaths.push(imagePath);
    }

    // 3. 이미지 목록 파일 생성 (FFmpeg concat용)
    const listPath = path.join(tempDir, 'list.txt');
    const listContent = imagePaths
      .map(p => `file '${p}'\nduration 12`)  // 12초씩 유지
      .join('\n');
    await fs.writeFile(listPath, listContent);

    // 4. FFmpeg로 비디오 생성
    const outputPath = path.join(tempDir, `${job.job_number}.mp4`);

    await new Promise((resolve, reject) => {
      ffmpeg()
        .input(listPath)
        .inputOptions(['-f', 'concat', '-safe', '0'])
        .outputOptions([
          '-c:v', 'libx264',
          '-pix_fmt', 'yuv420p',
          '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
          '-r', '30'
        ])
        .output(outputPath)
        .on('end', resolve)
        .on('error', reject)
        .run();
    });

    // 5. BGM 추가 (있는 경우)
    const bgmPath = await getRandomBGM();
    if (bgmPath) {
      const finalPath = path.join(tempDir, `${job.job_number}_final.mp4`);

      await new Promise((resolve, reject) => {
        ffmpeg()
          .input(outputPath)
          .input(bgmPath)
          .outputOptions([
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            '-map', '0:v',
            '-map', '1:a'
          ])
          .output(finalPath)
          .on('end', resolve)
          .on('error', reject)
          .run();
      });

      // 최종 파일로 교체
      await fs.rename(finalPath, outputPath);
    }

    // 6. Supabase Storage에 업로드
    const videoBuffer = await fs.readFile(outputPath);
    const videoStoragePath = `videos/${job.job_number}.mp4`;

    const { error: uploadError } = await supabase.storage
      .from('photos')
      .upload(videoStoragePath, videoBuffer, {
        contentType: 'video/mp4'
      });

    if (uploadError) throw uploadError;

    // 7. 작업 상태 업데이트
    const videoUrl = supabase.storage.from('photos').getPublicUrl(videoStoragePath).data.publicUrl;

    await supabase
      .from('jobs')
      .update({
        status: 'video_ready',
        video_url: videoUrl
      })
      .eq('id', job_id);

    // 8. 정리
    await fs.rm(tempDir, { recursive: true });

    // 9. Push 알림 전송 (옵션)
    await sendPushNotification(job.technician_id, job.job_number, videoUrl);

    res.json({ success: true, video_url: videoUrl });

  } catch (error) {
    console.error('Video generation failed:', error);
    res.status(500).json({ error: error.message });
  }
});

async function getRandomBGM() {
  const bgmDir = './assets/bgm';
  try {
    const files = await fs.readdir(bgmDir);
    const mp3Files = files.filter(f => f.endsWith('.mp3'));
    if (mp3Files.length === 0) return null;
    const randomFile = mp3Files[Math.floor(Math.random() * mp3Files.length)];
    return path.join(bgmDir, randomFile);
  } catch {
    return null;
  }
}

async function sendPushNotification(userId, jobNumber, videoUrl) {
  // Web Push API 구현 (Phase 4)
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Video Worker running on port ${PORT}`);
});
```

### 5.2 옵션 B: Creatomate API (빠른 구현)

**파일**: `src/js/video-api.js`

```javascript
/**
 * Creatomate API를 통한 비디오 생성
 */

const CREATOMATE_API_KEY = import.meta.env.VITE_CREATOMATE_API_KEY;
const CREATOMATE_TEMPLATE_ID = import.meta.env.VITE_CREATOMATE_TEMPLATE_ID;

/**
 * Creatomate로 비디오 생성 요청
 */
export async function generateVideoWithCreatomate(job, photos) {
  const imageUrls = photos.map(p => getPublicUrl(p.storage_path));

  const response = await fetch('https://api.creatomate.com/v1/renders', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${CREATOMATE_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      template_id: CREATOMATE_TEMPLATE_ID,
      modifications: {
        // 템플릿 변수에 이미지 URL 바인딩
        'Image-1': imageUrls[0] || '',
        'Image-2': imageUrls[1] || '',
        'Image-3': imageUrls[2] || '',
        'Image-4': imageUrls[3] || '',
        'Image-5': imageUrls[4] || '',
        'Title': job.car_model,
        'Subtitle': job.job_number
      }
    })
  });

  if (!response.ok) {
    throw new Error('Creatomate API error');
  }

  const result = await response.json();
  return result[0].url;  // 렌더링된 비디오 URL
}
```

### 5.3 작업 목록

- [ ] 옵션 선택 (Render + FFmpeg vs Creatomate)
- [ ] Video Worker 서버 구현
- [ ] Supabase Edge Function (트리거)
- [ ] BGM 믹싱 기능
- [ ] 자막 오버레이 (drawtext filter)
- [ ] 로고 워터마크 (overlay filter)

---

## 6. Phase 4: Push 알림 (1주)

### 6.1 Web Push 설정

**파일**: `src/js/push-manager.js`

```javascript
/**
 * Web Push 알림 관리
 */

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;

/**
 * Push 알림 구독
 */
export async function subscribeToPush() {
  if (!('PushManager' in window)) {
    console.warn('Push not supported');
    return null;
  }

  const registration = await navigator.serviceWorker.ready;

  // 기존 구독 확인
  let subscription = await registration.pushManager.getSubscription();

  if (!subscription) {
    // 새 구독 생성
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
    });

    // 서버에 구독 정보 저장
    await saveSubscription(subscription);
  }

  return subscription;
}

async function saveSubscription(subscription) {
  const { data: { user } } = await supabase.auth.getUser();

  await supabase.from('push_subscriptions').upsert({
    user_id: user.id,
    endpoint: subscription.endpoint,
    keys: JSON.stringify(subscription.toJSON().keys)
  });
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
```

### 6.2 Service Worker Push 핸들러

**파일**: `src/sw.js` (추가)

```javascript
// Push 알림 수신
self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};

  const options = {
    body: data.body || '비디오가 준비되었습니다.',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    data: {
      url: data.url || '/'
    },
    actions: [
      { action: 'open', title: '열기' },
      { action: 'dismiss', title: '닫기' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Photo Factory', options)
  );
});

// 알림 클릭
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.openWindow(event.notification.data.url)
    );
  }
});
```

### 6.3 작업 목록

- [ ] VAPID 키 생성
- [ ] `push-manager.js` 생성
- [ ] Service Worker Push 핸들러
- [ ] Supabase에 구독 테이블 추가
- [ ] 서버에서 Push 전송 (web-push 라이브러리)

---

## 7. 환경변수

```env
# .env.local (프론트엔드)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_VAPID_PUBLIC_KEY=your-vapid-public-key

# .env (Video Worker)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
VAPID_PRIVATE_KEY=your-vapid-private-key

# 선택: Creatomate
VITE_CREATOMATE_API_KEY=your-api-key
VITE_CREATOMATE_TEMPLATE_ID=your-template-id
```

---

## 8. 파일 구조

```
src/
├── js/
│   ├── supabase-client.js    # [Phase 1] Supabase 연동
│   ├── sync-queue.js         # [Phase 2] 오프라인 큐
│   ├── push-manager.js       # [Phase 4] Push 알림
│   ├── db.js                 # (수정) upload_queue 추가
│   └── ...
├── sw.js                     # Service Worker (Push)
└── ...

video-worker/                 # [Phase 3] 별도 서버
├── index.js
├── package.json
├── Dockerfile
└── assets/
    └── bgm/                  # BGM 파일들

supabase/
├── migrations/
│   └── 001_initial_schema.sql
└── config.toml
```

---

## 9. 비용 상세

### 월 100개 비디오 기준

| 항목 | 계산 | 비용 |
|------|------|------|
| **Supabase Pro** | 고정 | $25 |
| **Storage (10GB)** | 포함 (100GB) | $0 |
| **Egress (50GB)** | 포함 (250GB) | $0 |
| **Render Worker** | $7 + 사용량 | $7~12 |
| **또는 Creatomate** | 50분 × $0.28 | $14~41 |
| **합계** | | **$32~66** |

### 무료 시작 가능

1. **Supabase Free** (1GB storage) + **Vercel Free** = $0
2. 비디오 생성: 클라이언트 유지 (현재 방식)
3. 성장 후 Pro 업그레이드

---

## 10. 마일스톤

| 주차 | Phase | 작업 | 산출물 |
|------|-------|------|--------|
| 1 | Phase 1 | Supabase 연동 | 클라우드 이미지 저장 |
| 2 | Phase 2 | 오프라인 동기화 | PWA 오프라인 큐 |
| 3-4 | Phase 3 | 서버 비디오 생성 | Video Worker |
| 5 | Phase 4 | Push 알림 | 완료 알림 |

**총 개발 기간**: 5주

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-12-01 | 1.0.0 | 초안 작성 |
