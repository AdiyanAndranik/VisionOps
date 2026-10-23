import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API = 'http://localhost:8000'

// The browser only talks to /api/*. Vite strips the prefix and forwards
// to the FastAPI app, so the api needs no CORS. nginx will do the same later.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})