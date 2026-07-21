import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5173,
    // Proxy API calls to the Python sidecar during development
    proxy: {
      '/graph': 'http://localhost:7077',
      '/doc': 'http://localhost:7077',
      '/events': {
        target: 'ws://localhost:7077',
        ws: true,
      },
    },
  },
})
