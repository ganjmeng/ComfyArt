import { useLayoutEffect, useRef } from 'react'
import {
  BaseBoxShapeUtil,
  createShapeId,
  createShapePropsMigrationIds,
  createShapePropsMigrationSequence,
  HTMLContainer,
  resizeBox,
  StateNode,
  T,
  useEditor,
  useValue,
  type JsonObject,
  type RecordProps,
  type TLResizeInfo,
  type TLShape,
} from 'tldraw'
import { docFromText, hasMarks, plainOf, RichInput, RichView } from '../richText'
import { t } from '../i18n'

export const TEXT = 'ca-text'

declare module 'tldraw' {
  export interface TLGlobalShapePropsMap {
    [TEXT]: {
      w: number
      h: number
      text: string
      font: string
      weight: number
      size: number
      color: string
      stroke: string
      align: string
      letter: number
      line: number
      autoSize: boolean
      decoration: string
      transform: string
      rich: JsonObject | null
    }
  }
}

export type TextShape = TLShape<typeof TEXT>

const versions = createShapePropsMigrationIds(TEXT, { AddDecoration: 1, AddRich: 2 })

export function textStyle(p: TextShape['props']): React.CSSProperties {
  return {
    fontFamily: p.font,
    fontWeight: p.weight,
    fontSize: p.size,
    color: readableTextColor(p.color),
    textAlign: p.align as React.CSSProperties['textAlign'],
    letterSpacing: `${p.letter}px`,
    lineHeight: p.line,
    textDecoration: p.decoration === 'none' ? undefined : p.decoration,
    textTransform: p.transform as React.CSSProperties['textTransform'],
    WebkitTextStroke: p.stroke ? `${Math.max(1, p.size / 24)}px ${p.stroke}` : undefined,
    paintOrder: 'stroke fill',
  }
}

function Text({ shape }: { shape: TextShape }) {
  const editor = useEditor()
  const editing = useValue('editing', () => editor.getEditingShapeId() === shape.id, [editor, shape.id])
  const box = useRef<HTMLDivElement>(null)
  const p = shape.props

  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const w = p.autoSize ? Math.ceil(el.scrollWidth) : p.w
    const h = Math.ceil(el.scrollHeight)
    if (Math.abs(w - p.w) > 0.5 || Math.abs(h - p.h) > 0.5) {
      editor.run(() => editor.updateShape<TextShape>({ id: shape.id, type: TEXT, props: { w, h } }), { history: 'ignore' })
    }
  })

  const style: React.CSSProperties = {
    ...textStyle(p),
    width: p.autoSize ? 'max-content' : p.w,
    whiteSpace: p.autoSize ? 'pre' : 'pre-wrap',
    wordBreak: 'break-word',
  }

  return (
    <HTMLContainer className="ca-text" style={{ overflow: 'visible', pointerEvents: editing ? 'all' : undefined }}>
      <div ref={box} className="ca-text__box" style={{ ...style, visibility: editing ? 'hidden' : undefined }}>
        {p.rich ? <RichView doc={p.rich} /> : p.text.endsWith('\n') || !p.text ? `${p.text}​` : p.text}
      </div>
      {editing && (
        <RichInput
          doc={p.rich ?? docFromText(p.text)}
          style={style}
          onChange={(doc) => editor.updateShape<TextShape>({ id: shape.id, type: TEXT, props: { text: plainOf(doc), rich: hasMarks(doc) ? doc as JsonObject : null } })}
          onExit={() => editor.setEditingShape(null)}
        />
      )}
    </HTMLContainer>
  )
}

/** #307: theme-aware readable default — never bake near-black onto a dark canvas. */
export function defaultTextColor(): string {
  if (typeof document === 'undefined') return '#f2f2f2'
  const theme = document.documentElement.dataset.theme
  if (theme === 'light') return '#000000'
  if (theme === 'dark') return '#f2f2f2'
  // theme unset: prefer computed --ca-text, else app default (dark)
  const css = getComputedStyle(document.documentElement).getPropertyValue('--ca-text').trim()
  return css || '#f2f2f2'
}

function isNearBlack(color: string): boolean {
  const c = color.trim().toLowerCase()
  if (!c || c === 'black' || c === '#000' || c === '#000000') return true
  const m = c.match(/^rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
  if (m) return +m[1] + +m[2] + +m[3] < 40
  return false
}

/** Display/edit color: lift near-black defaults when the app theme is dark. */
export function readableTextColor(color: string): string {
  const theme = typeof document !== 'undefined' ? document.documentElement.dataset.theme : 'dark'
  if (theme === 'light') return color || '#000000'
  if (!color || isNearBlack(color)) return '#f2f2f2'
  return color
}

export class TextShapeUtil extends BaseBoxShapeUtil<TextShape> {
  static override type = TEXT
  static override props: RecordProps<TextShape> = {
    w: T.number,
    h: T.number,
    text: T.string,
    font: T.string,
    weight: T.number,
    size: T.number,
    color: T.string,
    stroke: T.string,
    align: T.string,
    letter: T.number,
    line: T.number,
    autoSize: T.boolean,
    decoration: T.string,
    transform: T.string,
    rich: T.jsonValue.nullable() as T.Validator<JsonObject | null>,
  }

  static override migrations = createShapePropsMigrationSequence({
    sequence: [
      { id: versions.AddDecoration, up: (props) => Object.assign(props, { decoration: 'none', transform: 'none' }) },
      { id: versions.AddRich, up: (props) => { props.rich = null } },
    ],
  })

  override getDefaultProps(): TextShape['props'] {
    return { w: 1, h: 1, text: '', font: 'Arial', weight: 400, size: 80, color: defaultTextColor(), stroke: '', align: 'left', letter: 0, line: 1.3, autoSize: true, decoration: 'none', transform: 'none', rich: null }
  }

  override canEdit() {
    return true
  }

  override onEditEnd(shape: TextShape) {
    if (!shape.props.text.trim()) this.editor.deleteShape(shape.id)
  }

  override onResize(shape: TextShape, info: TLResizeInfo<TextShape>) {
    const next = resizeBox(shape, info)
    return { ...next, props: { ...next.props, autoSize: false } }
  }

  override component(shape: TextShape) {
    return <Text shape={shape} />
  }

  override getIndicatorPath(shape: TextShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

export class TextTool extends StateNode {
  static override id = TEXT

  override onEnter() {
    this.editor.setCursor({ type: 'cross', rotation: 0 })
  }

  override onCancel() {
    this.editor.setCurrentTool('select')
  }

  override onPointerDown() {
    const editor = this.editor
    const p = editor.inputs.getCurrentPagePoint()
    const id = createShapeId()
    editor.createShape<TextShape>({ id, type: TEXT, x: p.x, y: p.y, props: { text: t('common.text'), color: defaultTextColor() } })
    editor.setCurrentTool('select')
    editor.select(id)
    editor.setEditingShape(id)
  }
}
