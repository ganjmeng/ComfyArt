import { BRAND } from './brand'

type LoaderHandle = { ready: () => void; finish: () => void }

declare global {
  interface Window {
    BRAND_CONFIG?: typeof BRAND & { logoSvg: string }
    LoomiLoader?: {
      mount: (opts?: { durationMs?: number; theme?: string; size?: number; waitForReady?: boolean }) => LoaderHandle
    }
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`)
    if (existing) {
      if (existing.dataset.loaded === '1') resolve()
      else existing.addEventListener('load', () => resolve(), { once: true })
      return
    }
    const s = document.createElement('script')
    s.src = src
    s.async = false
    s.onload = () => { s.dataset.loaded = '1'; resolve() }
    s.onerror = () => reject(new Error(`failed to load ${src}`))
    document.head.appendChild(s)
  })
}

function ensureCss(href: string) {
  if (document.querySelector(`link[href="${href}"]`)) return
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = href
  document.head.appendChild(link)
}

/** Mount canvas-entry loader v2. Plays once (~1200ms) then hard-cuts when ready(). */
export async function mountCanvasLoader(): Promise<LoaderHandle> {
  // Prefer TS brand as SSOT — ensure window config matches before loader JS runs.
  window.BRAND_CONFIG = {
    name: BRAND.name,
    pageTitle: BRAND.pageTitle,
    logoPath: BRAND.logoPath,
    logoSvg: BRAND.logoSvg,
    icons: { ...BRAND.icons },
  }
  ensureCss('/comfyart/brand/loomi-loader.css')
  await loadScript('/comfyart/brand/loomi-loader.js')
  if (!window.LoomiLoader) throw new Error('LoomiLoader missing')
  const theme = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
  return window.LoomiLoader.mount({ size: 64, waitForReady: true, theme })
}
