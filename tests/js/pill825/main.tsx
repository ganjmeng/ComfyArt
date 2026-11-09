/** #825: real AssistantBlocks process-rail Auto · model label shots. $0 mocks, no network. */
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
const caseId = q.get('case') || 'auto'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
TOOL_LABELS.generate_image = t('bot.generateImage')

const use = (id: string, name: string, input: any) => ({ type: 'tool_use' as const, id, name, input })
const res = (id: string, name: string, text: string, status = 'success') => (
  { type: 'tool_result' as const, id, name, status, text }
)

const sunburst = 'openai/gpt-image-2.6-sunburst/text-to-image'
const flare = 'openai/gpt-image-2.6-flare/text-to-image'
const banana = 'google/nano-banana-pro/edit'
const longId = 'openai/gpt-image-2.6-sunburst-with-an-extremely-long-marketing-name-that-must-ellipsis/text-to-image'

function choice(partial: Record<string, unknown>) {
  return JSON.stringify({ ids: ['shape:g1'], model_choice: partial, note: 'wait_generation' })
}

/** 1×1 peach PNG as a mock product thumb under the model row (Lovart layout). */
const MOCK_THUMB =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAAhUlEQVR4nO3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIC3AReUAAE9sWYyAAAAAElFTkSuQmCC'

const cases: Record<string, { width?: number; msg: any; live?: boolean; thumbs?: boolean; padTop?: number }> = {
  auto: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: '海报大字' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: sunburst, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  generating: {
    live: true,
    msg: {
      id: 'a', role: 'assistant', status: 'streaming', blocks: [
        { type: 'thinking', text: '…' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'a cup' }),
      ],
    },
  },
  manual: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { model: flare, prompt: 'cat' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: flare, auto: false, category: 'user',
          reason: { zh: '你指定了这个模型', en: 'you named this model' },
        })),
        { type: 'text', text: 'ok' },
      ],
    },
  },
  failed: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'x' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: sunburst, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        }), 'error'),
        { type: 'text', text: lang === 'en' ? 'Generation failed.' : '生成失败。' },
      ],
    },
  },
  fallback: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'logo' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: flare, auto: true, category: 'logo',
          fallback: sunburst,
          reason: { zh: '图标/Logo', en: 'icon / logo' },
        })),
        { type: 'text', text: 'ok' },
      ],
    },
  },
  skill: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pose' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'pose', skill: 'pose-fission', auto_model: true }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: banana, auto: true, category: 'skill',
          reason: { zh: 'pose-fission 技能固定模型', en: 'pose-fission skill pinned model' },
        })),
        { type: 'text', text: 'ok' },
      ],
    },
  },
  legacy: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'old' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'old card' }),
        res('g1', 'mcp__comfyart__generate_image', '{"ids":["shape:g1"],"note":"wait"}'),
        { type: 'text', text: 'ok' },
      ],
    },
  },
  ellipsis: {
    width: 220,
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'long' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'x' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: longId, auto: true, category: 'default',
          reason: { zh: '默认', en: 'default' },
        })),
        { type: 'text', text: 'ok' },
      ],
    },
  },
  refresh: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: '海报' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: sunburst, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        })),
        { type: 'text', text: lang === 'en' ? 'After refresh.' : '刷新后。' },
      ],
    },
  },
  // Tip at top edge → auto-flip below the label (no reply line so tip has room)
  flip: {
    thumbs: true,
    padTop: 0,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        use('g1', 'mcp__comfyart__generate_image', { prompt: '海报大字' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: sunburst, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        })),
      ],
    },
  },
}

const cfg = cases[caseId] || cases.auto
const width = cfg.width ?? 392

createRoot(document.getElementById('root')!).render(
  <div
    className="ca-root"
    style={{
      width,
      padding: cfg.padTop === 0 ? '4px 16px 80px' : '16px 16px 80px',
      background: 'var(--ca-float)',
      minHeight: 320,
      overflow: 'visible',
    }}
    data-case={caseId}
  >
    {cfg.padTop !== 0 && (
      <div style={{ font: '11px/14px system-ui', opacity: 0.5, marginBottom: 8 }}>
        {caseId} · {lang} · {q.get('theme') || 'light'}
      </div>
    )}
    <div className="ca-chat">
      <div className="ca-chat__bot" id="gen">
        <AssistantBlocks editor={null as any} m={cfg.msg} />
        {cfg.thumbs && (
          <div className="ca-chat__thumbs" data-testid="mock-thumbs" style={{ marginTop: 8, marginLeft: 28, display: 'flex', gap: 8 }}>
            <img className="ca-chat__thumb" src={MOCK_THUMB} alt="" width={72} height={72} style={{ borderRadius: 8, objectFit: 'cover', background: '#fecaca' }} />
            <img className="ca-chat__thumb" src={MOCK_THUMB} alt="" width={72} height={72} style={{ borderRadius: 8, objectFit: 'cover', background: '#bbf7d0', filter: 'hue-rotate(90deg)' }} />
          </div>
        )}
      </div>
    </div>
  </div>,
)
;(globalThis as any).__ready = true
;(globalThis as any).__case = caseId
