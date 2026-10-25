import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** Hover tip above a button (shared by the image toolbar and the #287 model button). */
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
      {show && pos && createPortal(
        <div className="ca-tip" style={{ left: pos.left, top: pos.top }}>
          <span className="ca-tip__name">{label}</span>
          {hint && <span className="ca-tip__key">{hint}</span>}
        </div>,
        document.body,
      )}
    </span>
  )
}
