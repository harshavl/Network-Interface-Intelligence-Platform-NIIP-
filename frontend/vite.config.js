import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API calls to the Flask backend so the dashboard can be developed
// against a live backend without CORS configuration. In production, serve
// the built frontend behind the same reverse proxy as the API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
