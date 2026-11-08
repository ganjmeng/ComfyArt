import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { initLocale } from '../../../src/i18n'
import { setProviderAdminOpen } from '../../../src/providerAdmin'
import { ProviderAdmin } from '../../../src/ui/ProviderAdmin'
import '../../../src/styles/base.css'
import '../../../src/styles/canvas.css'
import '../../../src/styles/shell.css'
import '../../../src/styles/overlays.css'

const empty = {
  admin: true,
  image: {
    saved: false,
    revision: 0,
    active: null,
    ignored: false,
    can_restore: false,
    providers: [
      {
        id: 'wavespeed',
        label: { zh: 'WaveSpeed', en: 'WaveSpeed' },
        mode: 'existing',
        configured: true,
        secret_env: 'WAVESPEED_API_KEY',
        note: { zh: '未保存，或保存为 WaveSpeed 时，图像仍走现有路由和现有模型。', en: 'Unsaved WaveSpeed keeps the current route.' },
        models: [],
        capabilities: {
          text_to_image: { supported: true, enabled: true, formats: [], reason: {} },
          image_edit: { supported: true, enabled: true, formats: ['png', 'jpeg', 'webp'], reason: {} },
          text_to_gif: { supported: true, enabled: true, formats: [], reason: {} },
          reference_gif: { supported: false, enabled: false, formats: [], reason: { zh: 'WaveSpeed 编辑不接受 gif（仅 png/jpeg/webp）。这里禁选，也不会把带参考图的请求改成无图文生。', en: 'Edit does not accept gif.' } },
        },
      },
      {
        id: 'replicate',
        label: { zh: 'Replicate', en: 'Replicate' },
        mode: 'replicate',
        configured: false,
        secret_env: 'REPLICATE_API_TOKEN',
        note: { zh: '可选备用。保存后只有新的四类图像任务走这里，不会自动改回 WaveSpeed。', en: 'Optional backup for new jobs only.' },
        models: ['openai/gpt-image-2.6-flare', 'openai/gpt-image-2.6-sunburst'].map((id) => ({
          id,
          label: id.endsWith('flare') ? 'GPT Image 2.6 Flare' : 'GPT Image 2.6 Sunburst',
          adapter: 'replicate_gpt_image_26',
          capabilities: ['text_to_image', 'image_edit', 'text_to_gif', 'reference_gif'],
          quote: 'unknown',
          docs: 'https://replicate.com/openai/gpt-image-2.6-flare',
          differences: { zh: '字段与 WaveSpeed 不同。费用未知。', en: 'Fields differ. Price unknown.' },
        })),
        capabilities: {},
      },
    ],
  },
  llm: {
    saved: false,
    revision: 0,
    active: null,
    ignored: false,
    can_restore: false,
    probe: 'off',
    providers: [
      {
        id: 'wavespeed',
        label: { zh: 'WaveSpeed', en: 'WaveSpeed' },
        mode: 'existing',
        base_url: '',
        configured: true,
        secret_env: '',
        docs: '',
        models: [{
          id: 'existing',
          label: { zh: '现有配置 · deepseek/deepseek-v4.1-flash-1017', en: 'Current setup' },
          adapter: 'existing',
          passthrough: true,
          request_model: 'deepseek/deepseek-v4.1-flash-1017',
          quote: 'settings',
          note: { zh: '生产默认。不保存就继续用现有地址和模型。', en: 'Production default until saved.' },
          differences: [],
        }],
      },
      {
        id: 'deepseek',
        label: { zh: 'DeepSeek 官方', en: 'DeepSeek official' },
        mode: 'openai_chat',
        base_url: 'https://api.deepseek.com',
        configured: false,
        secret_env: 'DEEPSEEK_API_KEY',
        docs: 'https://api-docs.deepseek.com/',
        models: [
          {
            id: 'deepseek-flash',
            label: { zh: 'deepseek-flash', en: 'deepseek-flash' },
            adapter: 'deepseek_official',
            passthrough: false,
            request_model: 'deepseek-flash',
            quote: 'unknown',
            note: { zh: '官方调用名，现由 DeepSeek-V4.1-Flash-1017 提供。不是 WaveSpeed 的 deepseek/deepseek-v4.1-flash-1017。', en: 'Official id. Not the WaveSpeed id.' },
            differences: [
              { zh: '地址改为 https://api.deepseek.com。密钥只读 DEEPSEEK_API_KEY，此页不接收密钥。', en: 'Endpoint and env key only.' },
              { zh: '官方默认开启思考。这条路由会关闭思考，因为现有 Agent 不回传 reasoning_content。不是无差异替换。', en: 'Thinking is disabled for this agent. Not a drop-in.' },
              { zh: 'deepseek-flash 非思考温度固定 1.0。现有链路不开启流式。工具调用未做付费实测。', en: 'Temperature and streaming differ. Tools were not live-tested.' },
            ],
          },
          {
            id: 'deepseek-v4-pro',
            label: { zh: 'deepseek-v4-pro', en: 'deepseek-v4-pro' },
            adapter: 'deepseek_official',
            passthrough: false,
            request_model: 'deepseek-v4-pro',
            quote: 'unknown',
            note: { zh: '另一个官方模型，不是 Flash 1017。费用未知。', en: 'A different official model. Price unknown.' },
            differences: [
              { zh: '不是 Flash 的别名。失败不会退回 WaveSpeed。', en: 'Not an alias of Flash. No fallback.' },
            ],
          },
        ],
      },
    ],
  },
  audit: {
    note: { zh: '审计不是路由。未实现的工具保持 WaveSpeed，设置里不能选。', en: 'Audit is not a route.' },
    summary: {
      checked_at: '2026-11-08',
      models_listed: 153,
      model_counts: { mapped_with_differences: 4, same_capability_different_model: 31, not_found_in_this_audit: 118 },
      capabilities: [
        { capability: 'text_to_image', provider: 'replicate', implemented: true, quote: 'unknown', detail: {} },
        { capability: 'image_edit', provider: 'replicate', implemented: true, quote: 'unknown', detail: {} },
        { capability: 'text_to_gif', provider: 'replicate', implemented: true, quote: 'unknown', detail: {} },
        { capability: 'reference_gif', provider: 'replicate', implemented: true, quote: 'unknown', detail: {} },
        { capability: 'reference_gif', provider: 'wavespeed', implemented: false, quote: 'unknown', detail: {} },
      ],
    },
  },
}

let state = structuredClone(empty)

function sectionSaved(name: 'image' | 'llm', active: unknown) {
  const current = state[name]
  current.previous = current.active
  current.active = active
  current.revision += 1
  current.saved = true
  current.can_restore = true
}

const realFetch = window.fetch.bind(window)
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input)
  if (!url.includes('/comfyart/provider-admin')) return realFetch(input, init)
  if (location.hash === '#forbidden') return json({ error: 'admin only' }, 403)
  const method = (init?.method || 'GET').toUpperCase()
  if (method === 'GET') return json(state)
  const body = init?.body ? JSON.parse(String(init.body)) : {}
  if (url.endsWith('/image/restore')) {
    const current = state.image.active
    state.image.active = state.image.previous
    state.image.previous = current
    state.image.revision += 1
    state.image.saved = !!state.image.active
    return json(state)
  }
  if (url.endsWith('/llm/restore')) {
    const current = state.llm.active
    state.llm.active = state.llm.previous
    state.llm.previous = current
    state.llm.revision += 1
    state.llm.saved = !!state.llm.active
    return json(state)
  }
  if (url.endsWith('/image') && method === 'PUT') {
    sectionSaved('image', body.provider === 'wavespeed' ? { provider: 'wavespeed' } : { provider: body.provider, models: body.models })
    return json(state)
  }
  if (url.endsWith('/llm') && method === 'PUT') {
    sectionSaved('llm', { provider: body.provider, model: body.model })
    return json(state)
  }
  return json({ error: 'not found' }, 404)
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}

localStorage.setItem('comfyart.lang', 'zh')
document.documentElement.dataset.theme = 'dark'
await initLocale()
setProviderAdminOpen(true)
createRoot(document.getElementById('root')!).render(<StrictMode><ProviderAdmin /></StrictMode>)
