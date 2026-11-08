import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { initLocale } from '../../../src/i18n'
import { providerAdminOpen, setProviderAdminOpen, subscribeProviderAdmin } from '../../../src/providerAdmin'
import { ProviderAdmin } from '../../../src/ui/ProviderAdmin'
import '../../../src/styles/base.css'
import '../../../src/styles/canvas.css'
import '../../../src/styles/shell.css'
import '../../../src/styles/overlays.css'

type Route = { primary: { provider: string; model: string }; backup: { provider: string; model: string } | null; fallback: boolean }
const FLARE = 'openai/gpt-image-2.6-flare'
const SUN = 'openai/gpt-image-2.6-sunburst'
const connected = new Set(['generate_image', 'edit_image', 'to_gif'])
const tools = [
  ['generate_image', 'image', '生成图片', '用文字生成图片。带参考图时仍保留图片。'],
  ['edit_image', 'image', '改图', '按说明改一张已有的图。'],
  ['to_gif', 'image', '静图转动图', '保留这张图，做成循环 GIF。'],
  ['replace_text', 'image', '改字', '只改画面里的文字。'],
  ['style_transfer', 'image', '风格迁移', '换成另一种画风，主体还在。'],
  ['upscale_image', 'image', '放大图片', '把图片放大变清晰。'],
  ['remove_background', 'image', '去背景', '抠出主体。'],
  ['expand_image', 'image', '扩图', '把画面向外补全。'],
  ['generate_video', 'video', '生成视频', '文生或图生视频。不会自动改供应商。'],
  ['animate_image', 'video', '图生动效', '让一张图动起来，这是视频，不是 GIF。'],
  ['extend_video', 'video', '延长视频', '把视频往后接一段。'],
  ['generate_music', 'other', '音乐', '生成一段音乐。'],
  ['text_to_speech', 'other', '朗读', '把文字读出来。'],
  ['image_to_3d', 'other', '图生三维', '由图片生成三维模型。'],
] as const

const saved: Record<string, { revision: number; active: Route | null; previous: Route | null; draft: Route | null }> = {}

function choices(id: string) {
  const on = connected.has(id)
  return [
    { provider: 'wavespeed', model: 'existing', label: { zh: 'WaveSpeed · 现有模型', en: 'WaveSpeed' }, enabled: true, quote: 'provider', reason: '' },
    { provider: 'replicate', model: FLARE, label: { zh: 'Replicate · Flare', en: 'Replicate · Flare' }, enabled: on, quote: 'unknown', reason: on ? '' : '这个工具还没有接到 Replicate' },
    { provider: 'replicate', model: SUN, label: { zh: 'Replicate · Sunburst', en: 'Replicate · Sunburst' }, enabled: on, quote: 'unknown', reason: on ? '' : '这个工具还没有接到 Replicate' },
  ]
}

function row(id: string, group: string, label: string, blurb: string) {
  const rec = saved[id] || { revision: 0, active: null, previous: null, draft: null }
  const primary = rec.active?.primary || { provider: 'wavespeed', model: 'existing' }
  const replicate = primary.provider === 'replicate'
  return {
    id, group, label: { zh: label, en: label }, blurb: { zh: blurb, en: blurb }, connected: connected.has(id),
    active: rec.active, draft: rec.draft, revision: rec.revision,
    can_restore: rec.previous != null || rec.active != null,
    choices: choices(id), key_ok: location.hash !== '#nokey', usable: !replicate,
    blocked: replicate ? 'quote_unknown' : '',
    effective: { provider: primary.provider, model: primary.model, source: rec.active ? 'saved' : 'default', fallback: !!rec.active?.fallback, backup: rec.active?.backup || null },
  }
}

function state() {
  return {
    admin: true,
    tools: tools.map((item) => row(...item)),
    llm: {
      saved: false, revision: 0, active: null, can_restore: false, probe: 'off',
      providers: [
        { id: 'wavespeed', label: { zh: 'WaveSpeed', en: 'WaveSpeed' }, mode: 'existing', base_url: '', configured: true, secret_env: '', docs: '', models: [{ id: 'existing', label: { zh: '现有配置 · deepseek/deepseek-v4.1-flash-1017', en: 'Current' }, adapter: 'existing', passthrough: true, request_model: 'deepseek/deepseek-v4.1-flash-1017', quote: 'settings', note: { zh: '生产默认。', en: 'Default.' }, differences: [] }] },
        { id: 'deepseek', label: { zh: 'DeepSeek 官方', en: 'DeepSeek' }, mode: 'openai_chat', base_url: 'https://api.deepseek.com', configured: false, secret_env: 'DEEPSEEK_API_KEY', docs: 'https://api-docs.deepseek.com/', models: [{ id: 'deepseek-flash', label: { zh: 'deepseek-flash', en: 'deepseek-flash' }, adapter: 'deepseek_official', passthrough: false, request_model: 'deepseek-flash', quote: 'unknown', note: { zh: '官方调用名。不是 WaveSpeed 的那条 id，也不是无差异替换。', en: 'Not a drop-in.' }, differences: [] }, { id: 'deepseek-v4-pro', label: { zh: 'deepseek-v4-pro', en: 'deepseek-v4-pro' }, adapter: 'deepseek_official', passthrough: false, request_model: 'deepseek-v4-pro', quote: 'unknown', note: { zh: '另一个官方模型。', en: 'Another model.' }, differences: [] }] },
      ],
    },
    policy: { fallback_default: false, max_attempts: 'primary once, then one backup', eligible: ['not_accepted'], human: ['unknown', 'safety', 'price'] },
  }
}

const realFetch = window.fetch.bind(window)
const mock = new URLSearchParams(location.search).has('mock')
if (mock) {
document.getElementById('mock-banner')!.textContent = 'Mock 预览 · 未调用真实供应商 · 费用未知 · 无密钥'
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input)
  if (!url.includes('/comfyart/provider-admin')) return realFetch(input, init)
  if (location.hash === '#forbidden') return json({ error: 'admin only' }, 403)
  const method = (init?.method || 'GET').toUpperCase()
  const body = init?.body ? JSON.parse(String(init.body)) : {}
  if (url.endsWith('/llm/check')) {
    return json({ saved: false, calls: 0, quote: 'unknown', base_url: 'https://api.deepseek.com', model: body.model, key_ok: false, message: '只检查草稿。当前对话线路没变，没有付费请求。价格未知。官方模型不是无差异替换。' })
  }
  if (method === 'GET') return json(state())
  const tool = url.split('/tool/')[1]?.replace('/restore', '')
  if (url.endsWith('/restore') && tool) {
    const rec = saved[tool] || { revision: 0, active: null, previous: null, draft: null }
    const current = rec.active
    rec.active = rec.previous
    rec.previous = current
    rec.revision += 1
    saved[tool] = rec
    return json({ ...state(), restored_tool: tool })
  }
  if (url.endsWith('/tools/batch')) {
    const applied: string[] = []
    const skipped: string[] = []
    for (const id of body.ids || []) {
      if (!connected.has(id)) { skipped.push(id); continue }
      saved[id] = { revision: (saved[id]?.revision || 0) + 1, previous: saved[id]?.active || null, draft: null, active: { primary: body.primary, backup: null, fallback: false } }
      applied.push(id)
    }
    return json({ ...state(), applied, skipped, activated: true, usable: false, blocked: 'quote_unknown' })
  }
  if (tool && method === 'PUT') {
    if (location.hash === '#nokey' && body.activate !== false && body.primary?.provider === 'replicate') {
      return json({ error: 'needs_key', saved: false, activated: false }, 409)
    }
    const rec = saved[tool] || { revision: 0, active: null, previous: null, draft: null }
    const route = { primary: body.primary, backup: body.backup || null, fallback: !!body.fallback }
    if (body.activate === false) rec.draft = route
    else { rec.previous = rec.active; rec.active = route; rec.revision += 1 }
    saved[tool] = rec
    return json({ ...state(), saved_tool: tool, activated: body.activate !== false, usable: body.primary?.provider !== 'replicate', blocked: body.primary?.provider === 'replicate' ? 'quote_unknown' : '' })
  }
  return json(state())
}
} else {
  document.getElementById('mock-banner')!.textContent = '本地设置接口 · 临时目录 · 不调用生成供应商'
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}

localStorage.setItem('comfyart.lang', 'zh')
document.documentElement.dataset.theme = 'dark'
await initLocale()

function Gate() {
  const [open, setOpen] = useState(providerAdminOpen())
  useEffect(() => subscribeProviderAdmin(() => setOpen(providerAdminOpen())), [])
  return (
    <>
      {!open && (
      <main className="ca-prov-gate">
        <h1>设置</h1>
        <p>从设置进入供应商。这一页只连本地设置接口。</p>
        <button type="button" data-testid="settings-providers" onClick={() => setProviderAdminOpen(true)}>供应商</button>
      </main>
      )}
      <ProviderAdmin />
    </>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><Gate /></StrictMode>)
