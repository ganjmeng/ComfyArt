import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** Hover tip above a button (shared by the image toolbar and the #287 model button).
 *  #825: `wide` = one-sentence routing reason (max ~240px, wraps, never truncates inside the tip).
 *  Default ABOVE the anchor; auto-flips BELOW when the top edge has no room. */
export function TipChip({ left, top, label, hint, wide, below }: {
  left: number; top: number; label: string; hint?: string; wide?: boolean; below?: boolean
}) {
  return createPortal(
    <div
      className={wide ? 'ca-tip ca-tip--wide' : 'ca-tip'}
      data-below={below || undefined}
      data-testid={wide ? 'auto-model-tip' : undefined}
      style={below
        ? { left, top, transform: 'translate(-50%, 0)' }
        : { left, top }}
    >
      <span className="ca-tip__name">{label}</span>
      {hint && <span className="ca-tip__key">{hint}</span>}
    </div>,
    document.body,
  )
}

export function Tip({ label, hint, children, wide }: {
  label: string; hint?: string; children: ReactNode; wide?: boolean
}) {
  const [show, setShow] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; below: boolean } | null>(null)
  const ref = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    // .ca-tip-wrap is display:contents — measure the child button, not the wrap.
    const el = ref.current?.firstElementChild as HTMLElement | null
    if (!show || !el) return
    const r = el.getBoundingClientRect()
    const left = r.left + r.width / 2
    // Prefer above (#262: bottom edge 6px above the anchor). Flip below when top has
    // little room. Wide tips wrap (up to ~3 lines @240px) — reserve ~56px so a wrapped
    // reason still fits above; otherwise flip so it never covers the reply below.
    const spaceAbove = r.top
    const need = wide ? 56 : 32
    const below = spaceAbove < need
    const top = below ? r.bottom + 6 : r.top - 6
    setPos({ left, top, below })
  }, [show, wide, label])
  return (
    <span ref={ref} className="ca-tip-wrap" onPointerEnter={() => setShow(true)} onPointerLeave={() => setShow(false)}>
      {children}
      {show && pos && <TipChip left={pos.left} top={pos.top} label={label} hint={hint} wide={wide} below={pos.below} />}
    </span>
  )
}


/* #283: every non-image selection toolbar shows <Tip> chips instead of the native title tooltip. The title text is
   moved to data-tip (+ aria-label, so a11y and e2e locators keep working) on first hover, so the copy stays identical. */
const SCOPE = '.ca-toolbar:not(.ca-toolbar--image)'
export function ToolbarTips() {
  const [tip, setTip] = useState<{ left: number; top: number; label: string } | null>(null)
  useLayoutEffect(() => {
    let cur: HTMLElement | null = null
    const over = (e: PointerEvent) => {
      const t = e.target instanceof Element ? e.target.closest<HTMLElement>('[title], [data-tip]') : null
      if (!t || !t.closest(SCOPE)) { if (cur) { cur = null; setTip(null) } return }
      if (t.hasAttribute('title')) {
        t.dataset.tip = t.getAttribute('title') ?? ''
        if (!t.hasAttribute('aria-label')) t.setAttribute('aria-label', t.dataset.tip)
        t.removeAttribute('title')
      }
      if (t === cur) return
      cur = t
      const r = t.getBoundingClientRect()
      setTip(t.dataset.tip ? { left: r.left + r.width / 2, top: r.top - 6, label: t.dataset.tip } : null)
    }
    const hide = () => { cur = null; setTip(null) }
    document.addEventListener('pointerover', over)
    document.addEventListener('pointerdown', hide, true)
    window.addEventListener('blur', hide)
    return () => { document.removeEventListener('pointerover', over); document.removeEventListener('pointerdown', hide, true); window.removeEventListener('blur', hide) }
  }, [])
  return tip ? <TipChip {...tip} /> : null
}
