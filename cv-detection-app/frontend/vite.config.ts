import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0'
    ,
    proxy: {
      // Proxy API requests to the backend service running in docker-compose
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://backend:8080',
        changeOrigin: true,
        secure: false,
      },
    }
  }
})
