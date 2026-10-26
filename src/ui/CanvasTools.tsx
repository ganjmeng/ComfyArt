import { useEffect, useState } from 'react'
import { DefaultMinimap, useEditor, useValue } from 'tldraw'

import { ColorPicker } from './ColorPicker'
import { Icons } from './icons'
import { sideAtom, type Side } from './SidePanel'
import { t } from '../i18n'

const DEFAULT_BG = '#F5F5F5'
const DEFAULT_DARK_BG = '#1A1A1A'

function Background() {
  const editor = useEditor()
  const bg = useValue('canvas bg', () => String(editor.getDocumentSettings().meta.bg ?? (editor.user.getIsDarkMode() ? DEFAULT_DARK_BG : DEFAULT_BG)), [editor])

  useEffect(() => {
    editor.getContainer().style.setProperty('--ca-canvas', bg)
  }, [editor, bg])

  const set = (value: string) => {
    const doc = editor.getDocumentSettings()
    editor.updateDocumentSettings({ meta: { ...doc.meta, bg: value } })
  }

  return <ColorPicker value={bg} title={t('canvasTools.canvasBackgroundColor')} onChange={set} />
}

function BackToContent() {
  const editor = useEditor()
  const lost = useValue('lost', () => {
    const shapes = editor.getCurrentPageShapes()
    if (!shapes.length) return false
    const view = editor.getViewportPageBounds()
    return !shapes.some((s) => {
      const b = editor.getShapePageBounds(s)
      return !!b && view.collides(b)
    })
  }, [editor])
  if (!lost) return null
  return (
    <div className="ca-back" onPointerDown={(e) => e.stopPropagation()}>
      <span>{t('canvasTools.nothingInView')}</span>
      <button type="button" className="ca-panel__primary" onClick={() => editor.zoomToFit({ animation: { duration: 200 } })}>{t('canvasTools.backToContent')}</button>
    </div>
  )
}

export function CanvasTools({ zoom }: { zoom: React.ReactNode }) {
  const side = useValue(sideAtom)
  const [map, setMap] = useState(false)
  const toggle = (s: Side) => () => sideAtom.set(side === s ? null : s)

  return (
    <>
      <BackToContent />
      {map && <div className="ca-minimap" onPointerDown={(e) => e.stopPropagation()}><DefaultMinimap /></div>}
      <div className="ca-tools" onPointerDown={(e) => e.stopPropagation()}>
        <Background />
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.layers')} data-on={side === 'layers' || undefined} onClick={toggle('layers')}>
          <span className="ca-icon">{Icons.layers}</span>
        </button>
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('canvasTools.generatedFiles')} data-on={side === 'files' || undefined} onClick={toggle('files')}>
          <span className="ca-icon">{Icons.files}</span>
        </button>
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('canvasTools.minimap')} data-on={map || undefined} onClick={() => setMap(!map)}>
          <span className="ca-icon">{Icons.map}</span>
        </button>
        <div className="ca-bar__sep" />
        {zoom}
      </div>
    </>
  )
}
