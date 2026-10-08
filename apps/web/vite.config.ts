import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/qloo': 'http://127.0.0.1:8000',
      '/tastecare': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
      '/ablation': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/tools': 'http://127.0.0.1:8000',
      '/storage': 'http://127.0.0.1:8000',
    },
  },
})