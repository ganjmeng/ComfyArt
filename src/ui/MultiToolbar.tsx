import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useActions, useEditor, useValue, type Editor, type TLImageShape, type TLShape } from 'tldraw'

import { MAX_VIEWS, viewsTo3d } from '../assetGen'

import { booleanOp, type BoolOp } from '../booleans'
import { openCanvasChat } from '../canvasChat'
import { errorText, mediaAsset } from '../jobs'
import { download, downloadUrl, exportPsd } from '../psd'
import { VECTOR } from '../shapes/VectorShape'
import { exportAtom } from './ExportDialog'
import { Icons } from './icons'
import { modeAtom } from './mode'
import { Popover } from './Popover'
import { useSelectionRect } from './selection'
import { t } from '../i18n'

const GAP = 22
const EDGE = 8
const ARRANGE_GAP = 40

type Menu = 'align' | 'distribute' | 'download' | 'boolean' | null
const BOOL_OPS: [BoolOp, keyof typeof Icons, string][] = [['unite', 'unite', t('multiToolbar.union')], ['subtract', 'subtract', t('multiToolbar.subtract')], ['intersect', 'intersect', t('multiToolbar.intersect')], ['exclude', 'exclude', t('multiToolbar.exclude')]]

export function arrange(editor: Editor, shapes: TLShape[]) {
  const boxes = shapes.map((s) => ({ s, b: editor.getShapePageBounds(s)! })).sort((a, b) => a.b.y - b.b.y || a.b.x - b.b.x)
  const cols = Math.ceil(Math.sqrt(boxes.length))
  const origin = editor.getSelectionPageBounds()!
  let y = origin.y
  editor.run(() => {
    for (let i = 0; i < boxes.length; i += cols) {
      const row = boxes.slice(i, i + cols).sort((a, b) => a.b.x - b.b.x)
      let x = origin.x
      for (const { s, b } of row) {
        editor.updateShape({ id: s.id, type: s.type, x: s.x + x - b.x, y: s.y + y - b.y })
        x += b.w + ARRANGE_GAP
      }
      y += Math.max(...row.map(({ b }) => b.h)) + ARRANGE_GAP
    }
  })
}

function Btn({ icon, label, title, open, onClick }: { icon: ReactNode; label?: string; title?: string; open?: boolean; onClick: () => void }) {
  return (
    <button type="button" className="ca-bar__btn" title={title} data-open={open || undefined} onClick={onClick}>
      <span className="ca-icon">{icon}</span>{label && <span>{label}</span>}
    </button>
  )
}

export function MultiToolbar({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const actions = useActions()
  const rect = useSelectionRect()
  const mode = useValue(modeAtom)
  const shapes = useValue('multi', () => {
    const s = editor.getSelectedShapes()
    return s.length > 1 ? s : null
  }, [editor])
  const bar = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [menu, setMenu] = useState<Menu>(null)

  useLayoutEffect(() => {
    if (bar.current) setWidth(bar.current.offsetWidth)
  })

  if (!shapes || !rect || mode) return null
  const ids = shapes.map((s) => s.id)
  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - width / 2, EDGE), host.width - width - EDGE)
  let top = rect.t - GAP - 44
  if (top < EDGE) top = rect.b + GAP
  const pick = (m: Exclude<Menu, null>) => (o: boolean) => setMenu(o ? m : null)
  const act = (fn: () => unknown) => () => { setMenu(null); Promise.resolve(fn()).catch((e) => onError(errorText(e))) }
  const name = (editor.getDocumentSettings().name || 'comfyart').replace(/[\\/:*?"<>|]/g, '_')

  const views = shapes.length <= MAX_VIEWS && shapes.every((s) => s.type === 'image')
    ? [...shapes as TLImageShape[]].sort((a, b) => editor.getShapePageBounds(a)!.x - editor.getShapePageBounds(b)!.x)
    : null

  const downloadAll = async () => {
    for (const s of shapes) {
      const asset = mediaAsset(editor, s)
      if (asset) {
        await downloadUrl(asset.props.src, asset.props.name || 'download')
      }
    }
    const rest = shapes.filter((s) => !(s.props as { assetId?: string }).assetId).map((s) => s.id)
    if (rest.length) download((await editor.toImage(rest, { format: 'png', background: false })).blob, `${name}.png`)
  }

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      <Btn icon={Icons.comment} label={t('canvasChat.chat')} onClick={() => openCanvasChat(editor)} />
      <Btn icon={Icons.grid} label={t('multiToolbar.tidyUp')} onClick={() => arrange(editor, shapes)} />
      <Btn icon={Icons.box} label={t('canvasMenu.group')} onClick={() => editor.groupShapes(ids)} />
      <Btn icon={Icons.merge} label={t('canvasMenu.mergeLayers')} onClick={() => actions['flatten-to-image']?.onSelect('toolbar')} />
      {views && <Btn icon={Icons.cube} label={t('imageToolbar.multiViewTo3d')} title={t('imageToolbar.multiViewTo3dHint')} onClick={() => viewsTo3d(editor, views, onError)} />}
      {shapes.every((s) => s.type === VECTOR) && (
        <Popover open={menu === 'boolean'} onOpenChange={pick('boolean')} trigger={({ open, toggle }) => <Btn icon={Icons.unite} title={t('multiToolbar.boolean')} open={open} onClick={toggle} />}>
          <div className="ca-menu ca-iconmenu">
            {BOOL_OPS.map(([op, icon, label]) => <Btn key={op} icon={Icons[icon]} title={label} onClick={act(() => booleanOp(editor, ids, op))} />)}
          </div>
        </Popover>
      )}
      <div className="ca-bar__sep" />
      <Popover open={menu === 'align'} onOpenChange={pick('align')} trigger={({ open, toggle }) => <Btn icon={Icons.alignLeft} title={t('multiToolbar.align')} open={open} onClick={toggle} />}>
        <div className="ca-menu ca-iconmenu">
          <Btn icon={Icons.alignLeft} title={t('multiToolbar.alignLeft')} onClick={act(() => editor.alignShapes(ids, 'left'))} />
          <Btn icon={Icons.alignCenterH} title={t('multiToolbar.alignHorizontalCenters')} onClick={act(() => editor.alignShapes(ids, 'center-horizontal'))} />
          <Btn icon={Icons.alignRight} title={t('multiToolbar.alignRight')} onClick={act(() => editor.alignShapes(ids, 'right'))} />
          <Btn icon={Icons.alignTop} title={t('multiToolbar.alignTop')} onClick={act(() => editor.alignShapes(ids, 'top'))} />
          <Btn icon={Icons.alignCenterV} title={t('multiToolbar.alignVerticalCenters')} onClick={act(() => editor.alignShapes(ids, 'center-vertical'))} />
          <Btn icon={Icons.alignBottom} title={t('multiToolbar.alignBottom')} onClick={act(() => editor.alignShapes(ids, 'bottom'))} />
        </div>
      </Popover>
      <Popover open={menu === 'distribute'} onOpenChange={pick('distribute')} trigger={({ open, toggle }) => <Btn icon={Icons.distributeH} title={t('multiToolbar.distribute')} open={open} onClick={toggle} />}>
        <div className="ca-menu ca-iconmenu">
          <Btn icon={Icons.distributeH} title={t('multiToolbar.distributeHorizontally')} onClick={act(() => editor.distributeShapes(ids, 'horizontal'))} />
          <Btn icon={Icons.distributeV} title={t('multiToolbar.distributeVertically')} onClick={act(() => editor.distributeShapes(ids, 'vertical'))} />
          <Btn icon={Icons.grid} title={t('multiToolbar.arrangeInGrid')} onClick={act(() => arrange(editor, shapes))} />
        </div>
      </Popover>
      <div className="ca-bar__sep" />
      <Popover open={menu === 'download'} onOpenChange={pick('download')} align="end" trigger={({ open, toggle }) => <Btn icon={Icons.download} title={t('common.download')} open={open} onClick={toggle} />}>
        <div className="ca-menu ca-menu--bar">
          <button type="button" className="ca-menu__item" onClick={act(downloadAll)}><span className="ca-menu__grow">{t('common.download')}</span></button>
          <button type="button" className="ca-menu__item" onClick={act(() => exportPsd(editor, shapes, name))}><span className="ca-menu__grow">{t('multiToolbar.exportPsd')}</span></button>
          <button type="button" className="ca-menu__item" onClick={act(() => exportAtom.set(ids))}><span className="ca-menu__grow">{t('multiToolbar.exportAs')}</span></button>
        </div>
      </Popover>
    </div>
  )
}
