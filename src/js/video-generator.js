/**
 * Photo Factory - Marketing Video Generator
 * Creates slideshow videos from job photos using Canvas + MediaRecorder API
 */

// Constants
const VIDEO_TIMEOUT_MS = 60 * 1000;  // 60 seconds max for video generation

/**
 * Generate marketing video from photos
 * @param {Array} photos - Array of photo objects with image_data
 * @param {Object} jobInfo - Job information {car_model, job_number}
 * @param {Object} options - Video options
 * @returns {Promise<Blob>} - Video blob
 */
export async function generateMarketingVideo(photos, jobInfo, options = {}) {
  const {
    width = 1080,
    height = 1920,  // Vertical (Shorts/Reels format)
    fps = 30,
    photoDuration = 2000,  // ms per photo
    transitionDuration = 500,  // ms for fade
    bitrate = 5000000,  // 5 Mbps
    timeout = VIDEO_TIMEOUT_MS,
    onProgress = null
  } = options;

  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  // Setup MediaRecorder
  const stream = canvas.captureStream(fps);
  const mediaRecorder = new MediaRecorder(stream, {
    mimeType: 'video/webm;codecs=vp9',
    videoBitsPerSecond: bitrate
  });

  const chunks = [];
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  // Load all images first
  const images = await Promise.all(
    photos.map(photo => loadImage(photo.image_data || photo.thumbnail_data))
  );

  // Calculate total duration
  const totalDuration = images.length * photoDuration;
  const totalFrames = (totalDuration / 1000) * fps;

  return new Promise((resolve, reject) => {
    let timeoutId = null;
    let isCompleted = false;

    // Cleanup function to release image memory
    const cleanup = () => {
      images.forEach(img => {
        img.src = '';  // Release image memory
      });
      if (timeoutId) clearTimeout(timeoutId);
    };

    // Set overall timeout
    timeoutId = setTimeout(() => {
      if (!isCompleted) {
        isCompleted = true;
        cleanup();
        mediaRecorder.stop();
        reject(new Error(`Video generation timeout exceeded (${timeout}ms)`));
      }
    }, timeout);

    mediaRecorder.onstop = () => {
      if (!isCompleted) {
        isCompleted = true;
        cleanup();
        const blob = new Blob(chunks, { type: 'video/webm' });
        resolve(blob);
      }
    };

    mediaRecorder.onerror = (e) => {
      if (!isCompleted) {
        isCompleted = true;
        cleanup();
        reject(new Error('Video recording failed: ' + (e.error?.message || e.error || 'Unknown error')));
      }
    };

    // Start recording
    mediaRecorder.start();

    // Animation loop
    let frame = 0;
    const interval = 1000 / fps;

    const renderFrame = () => {
      if (isCompleted) return;  // Stop if already completed/timed out

      if (frame >= totalFrames) {
        mediaRecorder.stop();
        return;
      }

      try {
        const currentTime = (frame / fps) * 1000;
        const photoIndex = Math.floor(currentTime / photoDuration);
        const photoProgress = (currentTime % photoDuration) / photoDuration;

        // Clear canvas with gradient background
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, '#667eea');
        gradient.addColorStop(1, '#764ba2');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        // Draw current photo
        if (photoIndex < images.length) {
          const img = images[photoIndex];
          const { x, y, w, h } = calculateFitDimensions(img, width, height * 0.7);

          // Fade effect
          let alpha = 1;
          const fadeInEnd = transitionDuration / photoDuration;
          const fadeOutStart = 1 - (transitionDuration / photoDuration);

          if (photoProgress < fadeInEnd) {
            alpha = photoProgress / fadeInEnd;
          } else if (photoProgress > fadeOutStart) {
            alpha = (1 - photoProgress) / (1 - fadeOutStart);
          }

          ctx.globalAlpha = alpha;
          ctx.drawImage(img, x, y + height * 0.1, w, h);
          ctx.globalAlpha = 1;
        }

        // Draw text overlay with actual photo category
        const currentPhoto = photos[photoIndex] || {};
        drawTextOverlay(ctx, jobInfo, photoIndex, images.length, width, height, currentPhoto.category);

        // Progress callback
        if (onProgress) {
          onProgress(Math.round((frame / totalFrames) * 100));
        }

        frame++;
        setTimeout(renderFrame, interval);
      } catch (renderError) {
        console.error('Frame render error:', renderError);
        // Continue to next frame on error
        frame++;
        setTimeout(renderFrame, interval);
      }
    };

    renderFrame();
  });
}

/**
 * Load image from data URL
 * @param {string} src - Image source (data URL or URL)
 * @returns {Promise<HTMLImageElement>}
 */
function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/**
 * Calculate dimensions to fit image in container while maintaining aspect ratio
 * @param {HTMLImageElement} img - Image element
 * @param {number} containerWidth - Container width
 * @param {number} containerHeight - Container height
 * @returns {Object} - {x, y, w, h}
 */
function calculateFitDimensions(img, containerWidth, containerHeight) {
  const imgRatio = img.width / img.height;
  const containerRatio = containerWidth / containerHeight;

  let w, h;
  if (imgRatio > containerRatio) {
    w = containerWidth;
    h = containerWidth / imgRatio;
  } else {
    h = containerHeight;
    w = containerHeight * imgRatio;
  }

  const x = (containerWidth - w) / 2;
  const y = (containerHeight - h) / 2;

  return { x, y, w, h };
}

/**
 * Draw text overlay on canvas
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {Object} jobInfo - Job information
 * @param {number} photoIndex - Current photo index
 * @param {number} totalPhotos - Total number of photos
 * @param {number} width - Canvas width
 * @param {number} height - Canvas height
 * @param {string} category - Photo category key
 */
function drawTextOverlay(ctx, jobInfo, photoIndex, totalPhotos, width, height, category) {
  // Category labels mapping
  const categoryLabels = {
    before_car: '입고',
    before_wheel: '문제',
    during: '과정',
    after_wheel: '해결',
    after_car: '출고'
  };
  const currentCategory = categoryLabels[category] || `${photoIndex + 1}/${totalPhotos}`;

  // Top bar with category
  ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
  ctx.fillRect(0, 0, width, 80);

  ctx.fillStyle = 'white';
  ctx.font = 'bold 36px -apple-system, BlinkMacSystemFont, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(currentCategory, width / 2, 55);

  // Progress indicator
  const progressWidth = (photoIndex + 1) / totalPhotos * width;
  ctx.fillStyle = '#28a745';
  ctx.fillRect(0, 76, progressWidth, 4);

  // Bottom overlay
  ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
  ctx.fillRect(0, height - 200, width, 200);

  // Car model
  ctx.fillStyle = 'white';
  ctx.font = 'bold 48px -apple-system, BlinkMacSystemFont, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(jobInfo.car_model || '휠 복원', width / 2, height - 130);

  // Job number
  ctx.font = '28px -apple-system, BlinkMacSystemFont, sans-serif';
  ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
  ctx.fillText(jobInfo.job_number || '', width / 2, height - 80);

  // Branding
  ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, sans-serif';
  ctx.fillStyle = '#667eea';
  ctx.fillText('Photo Factory', width / 2, height - 35);
}

/**
 * Download video blob as file
 * @param {Blob} blob - Video blob
 * @param {string} filename - Download filename
 */
export function downloadVideo(blob, filename = 'marketing-video.webm') {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Generate and download video for a job
 * @param {Array} photos - Array of photos
 * @param {Object} jobInfo - Job information
 * @param {Function} onProgress - Progress callback (0-100)
 * @returns {Promise<void>}
 */
export async function generateAndDownloadVideo(photos, jobInfo, onProgress) {
  try {
    // Sort photos by category order, then by sequence within each category
    const categoryOrder = ['before_car', 'before_wheel', 'during', 'after_wheel', 'after_car'];
    const sortedPhotos = [...photos].sort((a, b) => {
      const categoryDiff = categoryOrder.indexOf(a.category) - categoryOrder.indexOf(b.category);
      if (categoryDiff !== 0) return categoryDiff;
      return (a.sequence || 0) - (b.sequence || 0);
    });

    // Include ALL photos, not just first from each category
    const selectedPhotos = sortedPhotos.filter(p => p.image_data || p.thumbnail_data);

    if (selectedPhotos.length === 0) {
      throw new Error('No photos available for video generation');
    }

    const blob = await generateMarketingVideo(selectedPhotos, jobInfo, {
      onProgress
    });

    const filename = `${jobInfo.job_number || 'video'}_marketing.webm`;
    downloadVideo(blob, filename);

    return blob;
  } catch (error) {
    console.error('Video generation failed:', error);
    throw error;
  }
}

console.log('🎬 Video generator module loaded');
