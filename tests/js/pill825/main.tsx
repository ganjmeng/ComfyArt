/** #825: real AssistantBlocks process-rail Auto · model label shots. $0 mocks, no network. */
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { setLang, t } from '../i18n_stub'
import { skillPinReason } from '../../../src/autoPill'
import autoTable from '../../../api/auto_models.json'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
const caseId = q.get('case') || 'auto'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
TOOL_LABELS.generate_image = t('bot.generateImage')
TOOL_LABELS.edit_image = t('bot.editImage')

const use = (id: string, name: string, input: any) => ({ type: 'tool_use' as const, id, name, input })
const res = (id: string, name: string, text: string, status = 'success') => (
  { type: 'tool_result' as const, id, name, status, text }
)

const sunburst = 'openai/gpt-image-2.6-sunburst/text-to-image'
const flare = 'openai/gpt-image-2.6-flare/text-to-image'
const seedream = 'bytedance/seedream-v5.0-pro'
const seedreamEdit = 'bytedance/seedream-v5.0-pro/edit'
const bananaEdit = 'google/nano-banana-2.1/edit'
const longId = 'openai/gpt-image-2.6-sunburst-with-an-extremely-long-marketing-name-that-must-ellipsis/text-to-image'

/** Real pose-fission pin from api/auto_models.json — not invented fixture pairs. */
const posePin = (autoTable as { skills: Record<string, { model: string; fallback: string }> }).skills['pose-fission']
if (!posePin?.model || !posePin?.fallback) throw new Error('pose-fission missing from auto_models.json')
const poseSkill = 'pose-fission'
const posePrimary = posePin.model       // what failed / pinned primary
const poseFallback = posePin.fallback   // what ran after fallback
const poseReason = skillPinReason(poseSkill)

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
          model: flare, auto: true, category: 'poster_text',
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
          model: flare, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        }), 'error'),
        { type: 'text', text: lang === 'en' ? 'Generation failed.' : '生成失败。' },
      ],
    },
  },
  // #872: poster_text Flare → Sunburst runtime fallback (table tip + models)
  poster_fb: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: '海报大字' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: sunburst, auto: true, category: 'poster_text',
          fallback: flare,
          reason: { zh: '海报/带字', en: 'poster / text' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  fallback: {
    // Real table pair: pose-fission primary failed → registered fallback ran (mirrors skill_fallback_choice)
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pose' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'pose', skill: poseSkill, auto_model: true }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: poseFallback, auto: true, category: 'skill_fallback', skill: poseSkill,
          fallback: posePrimary,
          edit_model: poseFallback,
          reason: poseReason,
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
        use('g1', 'mcp__comfyart__generate_image', { prompt: 'pose', skill: poseSkill, auto_model: true }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: posePrimary, auto: true, category: 'skill', skill: poseSkill,
          edit_model: posePrimary,
          reason: poseReason,
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
          model: flare, auto: true, category: 'poster_text',
          reason: { zh: '海报/带字', en: 'poster / text' },
        })),
        { type: 'text', text: lang === 'en' ? 'After refresh.' : '刷新后。' },
      ],
    },
  },
  // Realistic-person Auto card. reason/model follow the live table (updated with the person row).
  person: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: '一张写实人像' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: seedream, auto: true, category: 'person',
          reason: { zh: '写实人物', en: 'realistic person' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  // Product / photoreal Auto card (tip follows the live photoreal row).
  product: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__generate_image', { prompt: '电商主图，白底，香水瓶' }),
        res('g1', 'mcp__comfyart__generate_image', choice({
          model: seedream, auto: true, category: 'photoreal',
          reason: { zh: '产品摄影', en: 'product photography' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  // #825 keep-face / keep-identity Auto edit card (reason follows the live keep_identity row).
  keepface: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__edit_image', { prompt: '保留同一个人，只把衣服换成深色西装、背景换成办公室' }),
        res('g1', 'mcp__comfyart__edit_image', choice({
          model: seedreamEdit, auto: true, category: 'keep_identity',
          reason: { zh: '保留同一人物', en: 'keep the same person' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  // #825 keep_product Auto edit card (same hover wording, Banana 2.1).
  keepproduct: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__edit_image', { prompt: '保留产品，只换背景' }),
        res('g1', 'mcp__comfyart__edit_image', choice({
          model: bananaEdit, auto: true, category: 'keep_product',
          reason: { zh: '保留商品不变', en: 'keep the product unchanged' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
      ],
    },
  },
  // Same card on main: keep_identity still routed to Nano Banana 2.1 edit (L/R before).
  keepface_main: {
    thumbs: true,
    msg: {
      id: 'a', role: 'assistant', status: 'done', blocks: [
        { type: 'thinking', text: 'pick' },
        use('g1', 'mcp__comfyart__edit_image', { prompt: '保留同一个人，只把衣服换成深色西装、背景换成办公室' }),
        res('g1', 'mcp__comfyart__edit_image', choice({
          model: bananaEdit, auto: true, category: 'keep_identity',
          reason: { zh: '这是要保持人物或产品一致的局部修改', en: 'this is a local edit that must keep the person or product consistent' },
        })),
        { type: 'text', text: lang === 'en' ? 'Done.' : '好了。' },
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
          model: flare, auto: true, category: 'poster_text',
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
