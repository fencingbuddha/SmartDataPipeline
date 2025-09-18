import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // anything starting with /api goes to FastAPI
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
