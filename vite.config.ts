import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

import { BRAND } from './src/brand.ts'

const COMFY = process.env.COMFY_URL ?? 'http://127.0.0.1:8188'

/** Inject brand title / favicon / apple-touch / og into index.html at build & dev. */
function brandHead(): Plugin {
  const icons = BRAND.icons
  const tags = [
    `<title>${BRAND.pageTitle}</title>`,
    `<meta name="application-name" content="${BRAND.name}" />`,
    `<link rel="icon" href="${icons.svg}" type="image/svg+xml" />`,
    `<link rel="icon" href="${icons.ico}" sizes="any" />`,
    `<link rel="icon" type="image/png" sizes="16x16" href="${icons.png16}" />`,
    `<link rel="icon" type="image/png" sizes="32x32" href="${icons.png32}" />`,
    `<link rel="apple-touch-icon" href="${icons.appleTouch}" />`,
    `<link rel="manifest" href="/comfyart/brand/site.webmanifest" />`,
    `<meta property="og:title" content="${BRAND.pageTitle}" />`,
    `<meta property="og:site_name" content="${BRAND.name}" />`,
    `<meta property="og:image" content="${icons.ogLight}" />`,
    `<meta name="twitter:card" content="summary" />`,
    `<meta name="twitter:title" content="${BRAND.pageTitle}" />`,
    `<meta name="twitter:image" content="${icons.ogLight}" />`,
  ].join('\n    ')
  return {
    name: 'brand-head',
    transformIndexHtml(html) {
      return html
        .replace(/<title>[^<]*<\/title>/, '')
        .replace('</head>', `    ${tags}\n  </head>`)
    },
  }
}

export default defineConfig({
  base: '/comfyart/',
  plugins: [react(), brandHead()],
  server: {
    proxy: {
      '/api': COMFY,
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
