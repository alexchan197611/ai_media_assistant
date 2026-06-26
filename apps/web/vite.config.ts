import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'AMA_')
  const apiTarget = env.AMA_API_TARGET ?? 'http://127.0.0.1:8123'
  return { plugins: [react()], server: { host: '127.0.0.1', port: 5173, proxy: { '/api': apiTarget } }, test: { environment: 'jsdom' } }
})
