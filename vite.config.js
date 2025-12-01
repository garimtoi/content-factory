import { defineConfig } from 'vite';
import { resolve } from 'path';
import os from 'os';

// Get local network IP address
function getNetworkIP() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      // Skip internal (127.0.0.1) and non-IPv4
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

// CSP Policy (Content Security Policy)
const cspPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
  "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
  "img-src 'self' data: blob:",
  "font-src 'self' https://cdn.jsdelivr.net",
  "connect-src 'self' https://cdn.jsdelivr.net",
  "media-src 'self' blob:",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'"
].join('; ');

export default defineConfig({
  root: 'src/public',
  publicDir: '../../public',
  // Inject network IP at build/dev time
  define: {
    '__NETWORK_IP__': JSON.stringify(getNetworkIP()),
    '__DEV_PORT__': JSON.stringify(6010)
  },
  server: {
    host: '0.0.0.0',
    port: 6010,  // 6000-6009 are blocked by Chrome (X11 protocol)
    strictPort: true,  // 포트 사용 중이면 에러 발생 (다른 포트로 자동 변경 안 함)
    open: true,
    headers: {
      'Content-Security-Policy': cspPolicy,
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block'
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 6011,
    strictPort: true,
    headers: {
      'Content-Security-Policy': cspPolicy,
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block'
    }
  },
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,  // Remove console.log in production
        drop_debugger: true
      }
    },
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/public/index.html'),
        upload: resolve(__dirname, 'src/public/upload.html'),
        gallery: resolve(__dirname, 'src/public/gallery.html'),
        'job-detail': resolve(__dirname, 'src/public/job-detail.html')
      }
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@js': resolve(__dirname, 'src/js'),
      '@css': resolve(__dirname, 'src/css')
    }
  }
});
