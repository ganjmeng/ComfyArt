// #826 tip: real Tldraw canvas + ImageToolbar + generator card. Local fixture pixels only.
import { createRoot } from 'react-dom/client'
import { AssetRecordType, Tldraw, createShapeId, type Editor, type TLComponents } from 'tldraw'
import { ImageToolbar } from '../../../src/ui/ImageToolbar'
import { GENERATOR, GENERATOR_DEFAULTS, GeneratorShapeUtil } from '../../../src/shapes/GeneratorShape'
import { ComfyImageShapeUtil } from '../../../src/shapes/SvgImageShape'
import { resultsAtom } from '../../../src/jobs'
import 'tldraw/tldraw.css'
import '../../../src/styles/base.css'
import '../../../src/styles/canvas.css'
import '../../../src/styles/overlays.css'
import '../../../src/styles/shell.css'
import { initLocale, t } from '../../../src/i18n'

const q = new URLSearchParams(location.search)
const state = q.get('state') === 'failed' || q.get('state') === 'rejected' ? q.get('state')! : 'path'

const components: TLComponents = {
  ContextMenu: null, Toolbar: null, StylePanel: null, MainMenu: null, PageMenu: null,
  NavigationPanel: null, HelpMenu: null, ActionsMenu: null, QuickActions: null,
  ImageToolbar: null, VideoToolbar: null, MenuPanel: null, TopPanel: null, SharePanel: null,
  HelperButtons: null, DebugPanel: null, DebugMenu: null, Minimap: null,
}

function place(editor: Editor) {
  const file = new URL(state === 'failed' ? 'fail.png' : 'path.png', location.href).href
  const original = new URL(state === 'failed' ? 'text_only.svg' : 'path.svg', location.href).href
  const originalName = state === 'failed' ? 'text_only.svg' : 'path.svg'
  if (state === 'rejected') {
    const id = createShapeId()
    editor.createShape({
      id, type: GENERATOR, x: 48, y: 72,
      props: { ...GENERATOR_DEFAULTS, w: 460, h: 280, prompt: 'LOCAL FIXTURE' },
    })
    resultsAtom.set({ [id]: { srcs: [], error: t('wsErr.svgRejected') } })
    editor.select(id)
    editor.zoomToBounds({ x: 20, y: 40, w: 520, h: 360 }, { inset: 24 })
    ;(globalThis as { __svg826Ready?: boolean }).__svg826Ready = true
    return
  }
  const assetId = AssetRecordType.createId()
  const failed = state === 'failed'
  editor.createAssets([{
    id: assetId,
    typeName: 'asset',
    type: 'image',
    props: {
      name: 'logo.svg',
      src: file,
      w: 32,
      h: 32,
      mimeType: 'image/png',
      isAnimated: false,
    },
    meta: {
      localFixture: true,
      inlineSvg: false,
      svgDownload: original,
      svgName: originalName,
      svgState: failed ? 'preview_failed' : 'transparent',
      svgMessage: t('wsErr.svgPreviewFailed'),
    },
  }])
  const id = createShapeId()
  editor.createShape({ id, type: 'image', x: 120, y: 96, props: { assetId, w: 280, h: 280 } })
  editor.select(id)
  editor.zoomToBounds({ x: 80, y: 40, w: 360, h: 420 }, { inset: 32 })
  ;(globalThis as { __svg826Ready?: boolean }).__svg826Ready = true
}

export async function mount() {
  await initLocale()
  const root = document.getElementById('root')!
  root.dataset.state = state
  root.dataset.fixture = 'local'
  // Real product canvas. The banner is the harness label, not a fake card.
  const banner = document.createElement('div')
  banner.className = 'ca-fixture-banner'
  banner.textContent = `LOCAL FIXTURE · mock · 不是供应商结果 · ${state}`
  root.append(banner)
  const frame = document.createElement('div')
  frame.className = 'ca-fixture-frame'
  root.append(frame)
  createRoot(frame).render(
    <Tldraw shapeUtils={[ComfyImageShapeUtil, GeneratorShapeUtil]} components={components} onMount={place}>
      <ImageToolbar onError={() => {}} />
    </Tldraw>,
  )
}

void mount()
