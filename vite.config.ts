import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const COMFY = process.env.COMFY_URL ?? 'http://127.0.0.1:8188'

export default defineConfig({
  base: '/comfyart/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': COMFY,
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
