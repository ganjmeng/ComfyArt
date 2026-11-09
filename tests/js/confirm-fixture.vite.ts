import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..')

export default defineConfig({
  root,
  base: '/',
  plugins: [react()],
  cacheDir: '/tmp/confirm-vite-cache',
  resolve: { alias: { tldraw: path.join(root, 'tests/js/tldrawAtom.ts') } },
  optimizeDeps: {
    noDiscovery: true,
    include: ['react', 'react-dom', 'react-dom/client', 'react/jsx-dev-runtime', 'lucide-react'],
  },
  server: { host: '0.0.0.0', port: 5210, strictPort: true, hmr: false },
})
