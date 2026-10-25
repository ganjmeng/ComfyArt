import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** Hover tip above a button (shared by the image toolbar and the #287 model button). */
export function TipChip({ left, top, label, hint }: { left: number; top: number; label: string; hint?: string }) {
  return createPortal(
    <div className="ca-tip" style={{ left, top }}>
      <span className="ca-tip__name">{label}</span>
      {hint && <span className="ca-tip__key">{hint}</span>}
    </div>,
    document.body,
  )
}

export function Tip({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  const [show, setShow] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const ref = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    // .ca-tip-wrap is display:contents — measure the child button, not the wrap.
    const el = ref.current?.firstElementChild as HTMLElement | null
    if (!show || !el) return
    const r = el.getBoundingClientRect()
    setPos({ left: r.left + r.width / 2, top: r.top - 6 }) // #262: bottom edge 6px above the button (CSS shifts up by 100%)
  }, [show])
  return (
    <span ref={ref} className="ca-tip-wrap" onPointerEnter={() => setShow(true)} onPointerLeave={() => setShow(false)}>
      {children}
      {show && pos && <TipChip left={pos.left} top={pos.top} label={label} hint={hint} />}
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
