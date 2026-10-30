// #422: multi-turn context carries previous-turn image refs (shape id).
// main = bare [attached image: url]; ours = Attached-line with shape id. Thinking omitted.
import { createRoot } from 'react-dom/client'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const copy = lang === 'en' ? {
  title: 'Multi-turn LLM context (turn 2)',
  turn1User: 'Edit this poster — warmer tones',
  turn1Bot: 'Updated the poster.',
  turn2User: 'Brighter, keep the same ref.',
  mainLabel: 'main — text only, no shape id',
  oursLabel: 'ours — previous-turn image ref with shape id',
  mainCtx:
    'User: Edit this poster — warmer tones\n[attached image: /api/view?filename=poster.png&type=output]\n\n' +
    'Assistant: Updated the poster.\n\n' +
    'User: Brighter, keep the same ref.',
  oursCtx:
    'User: Edit this poster — warmer tones\n' +
    '[Attached image 1 "poster": shape id shape:poster1 — /api/view?filename=poster.png&type=output. ' +
    'Use the shape id with edit tools or as a generation ref.]\n\n' +
    'Assistant: Updated the poster.\n\n' +
    'User: Brighter, keep the same ref.',
  noteMain: 'No shape id → follow-up cannot pass the image as a generation ref.',
  noteOurs: 'shape id shape:poster1 kept · thinking omitted',
  chatTitle: 'Chat',
  ctxTitle: 'Context sent to model',
} : {
  title: '多轮 LLM 上下文（第 2 轮）',
  turn1User: '改这张海报——色调暖一点',
  turn1Bot: '海报已更新。',
  turn2User: '再亮一点，继续用同一张图。',
  mainLabel: 'main — 只有文字，没有 shape id',
  oursLabel: 'ours — 上一轮图片引用带 shape id',
  mainCtx:
    'User: 改这张海报——色调暖一点\n[attached image: /api/view?filename=poster.png&type=output]\n\n' +
    'Assistant: 海报已更新。\n\n' +
    'User: 再亮一点，继续用同一张图。',
  oursCtx:
    'User: 改这张海报——色调暖一点\n' +
    '[Attached image 1 "poster": shape id shape:poster1 — /api/view?filename=poster.png&type=output. ' +
    'Use the shape id with edit tools or as a generation ref.]\n\n' +
    'Assistant: 海报已更新。\n\n' +
    'User: 再亮一点，继续用同一张图。',
  noteMain: '没有 shape id → 下一轮无法把图当作生成引用。',
  noteOurs: '保留 shape id shape:poster1 · 不含思考内容',
  chatTitle: '对话',
  ctxTitle: '发给模型的上下文',
}

// Tiny placeholder thumb (no network)
const THUMB =
  'data:image/svg+xml,' + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="112" height="112">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#ef4444"/>
      </linearGradient></defs>
      <rect width="112" height="112" rx="10" fill="url(#g)"/>
      <text x="56" y="62" text-anchor="middle" fill="#fff" font-size="14" font-family="system-ui">poster</text>
    </svg>`)

function Panel({ id, label, ctx, note, highlight }: {
  id: string; label: string; ctx: string; note: string; highlight: boolean
}) {
  return (
    <div style={{ flex: 1, minWidth: 0 }} data-testid={`${id}-panel`}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>{label}</div>
      <div className="ca-chat" style={{
        border: '1px solid var(--ca-border, #3333)',
        borderRadius: 12, padding: 12, background: 'var(--ca-panel, var(--ca-bg))',
      }}>
        <div style={{ font: '11px/14px system-ui', opacity: .5, marginBottom: 8 }}>{copy.chatTitle}</div>
        <div className="ca-chat__user" style={{ alignSelf: 'flex-end', marginBottom: 8 }}>
          <div className="ca-chat__thumbs">
            <img className="ca-chat__thumb" src={THUMB} width={56} height={56}
              style={{ borderRadius: 8, objectFit: 'cover' }} alt="" />
          </div>
          <div className="ca-chat__bubble">{copy.turn1User}</div>
        </div>
        <div className="ca-chat__bot" style={{ marginBottom: 8 }}>
          <div>{copy.turn1Bot}</div>
        </div>
        <div className="ca-chat__user" style={{ alignSelf: 'flex-end' }}>
          <div className="ca-chat__bubble">{copy.turn2User}</div>
        </div>

        <div style={{ font: '11px/14px system-ui', opacity: .5, margin: '14px 0 6px' }}>{copy.ctxTitle}</div>
        <pre id={id} data-testid={`ctx-${id}`} style={{
          margin: 0, padding: 10, borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          font: '11px/15px ui-monospace, SFMono-Regular, Menlo, monospace',
          background: highlight ? 'color-mix(in srgb, #22c55e 12%, transparent)' : 'color-mix(in srgb, #ef4444 10%, transparent)',
          border: `1px solid ${highlight ? 'color-mix(in srgb, #22c55e 35%, transparent)' : 'color-mix(in srgb, #ef4444 30%, transparent)'}`,
          color: 'var(--ca-text, inherit)',
        }}>{ctx}</pre>
        <div style={{ font: '11px/14px system-ui', marginTop: 8, opacity: .7 }}>{note}</div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 920, padding: 16, background: 'var(--ca-bg)' }}>
    <div style={{ font: '13px/18px system-ui', marginBottom: 12, opacity: .75 }}>{copy.title}</div>
    <div style={{ display: 'flex', gap: 20 }}>
      <Panel id="main" label={copy.mainLabel} ctx={copy.mainCtx} note={copy.noteMain} highlight={false} />
      <Panel id="ours" label={copy.oursLabel} ctx={copy.oursCtx} note={copy.noteOurs} highlight={true} />
    </div>
  </div>)
;(globalThis as any).__ready = true
