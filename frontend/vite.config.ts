import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    /**
     * `/api` -> the FastAPI backend.
     *
     * Without this, `getApiBaseUrl()` returns '' and every request resolves
     * against the dev server on :5173, which serves index.html for unknown
     * paths — so a fetch does not 404 cleanly, it succeeds and hands back HTML
     * that fails to parse as JSON. The Contract 2b screens hide that behind
     * their mock fallback; the passport has none by design, so it is the first
     * screen to break and the reason this proxy exists.
     *
     * VITE_FOODS_API_BASE_URL still wins when it is set, for pointing the dev
     * frontend at a deployed backend.
     */
    proxy: {
      '/api': {
        target: process.env.VITE_FOODS_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})