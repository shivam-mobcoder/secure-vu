import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = process.env.VITE_BACKEND_PROXY_TARGET || 'https://localhost:8000';

export default defineConfig(({ command }) => ({
  base: command === 'serve' ? '/' : '/super-admin/dashboard/',
  plugins: [react()],
  define: {
    // During dev (`serve`) leave empty so fetch('/api/…') goes through Vite proxy.
    // During production build use the env var or hardcoded backend origin.
    'import.meta.env.VITE_BACKEND_ORIGIN': JSON.stringify(
      command === 'serve' ? '' : (process.env.VITE_BACKEND_ORIGIN || 'https://localhost:8000')
    ),
  },
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // Proxy the entire backend client.html through a /backend-client path
      // so the live-feed iframe can load same-origin (avoids mixed-content)
      '/backend-client': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/backend-client/, ''),
      },
      '/static': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      '/event-clips': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // WebRTC signaling
      '/offer': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // Camera rules endpoints
      '/rules': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // ROI save endpoint
      '/save-roi': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // Face management endpoints (non-api prefix)
      '/face': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/enroll': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/login': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/signup': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/me': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/logout': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
}));
