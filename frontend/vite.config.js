import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port 8000 is a popular default -- if something else on your machine already owns it,
// run the API elsewhere and set API_PROXY_TARGET rather than editing this file.
const API = process.env.API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy /api to the backend so there is no CORS setup in local dev.
    proxy: {
      '/api': API,
      '/health': API,
    },
  },
})
