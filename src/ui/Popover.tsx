import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useEscape } from './escape'

const GAP = 8
const EDGE = 8

export function Popover({ trigger, children, side = 'bottom', align = 'start', open, onOpenChange, contentKey }: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode
  children: ReactNode
  side?: 'top' | 'bottom'
  align?: 'start' | 'center' | 'end'
  open: boolean
  onOpenChange: (open: boolean) => void
  contentKey?: string
}) {
  const anchor = useRef<HTMLSpanElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  useLayoutEffect(() => {
    if (!open || !anchor.current || !panel.current) return
    const a = anchor.current.getBoundingClientRect()
    const p = panel.current.getBoundingClientRect()
    let left = align === 'start' ? a.left : align === 'end' ? a.right - p.width : a.left + a.width / 2 - p.width / 2
    left = Math.min(Math.max(left, EDGE), innerWidth - p.width - EDGE)
    let top = side === 'top' ? a.top - p.height - GAP : a.bottom + GAP
    if (top < EDGE) top = a.bottom + GAP
    if (top + p.height > innerHeight - EDGE) top = Math.max(EDGE, a.top - p.height - GAP)
    setPos({ left, top })
  }, [open, side, align, contentKey])

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node
      if (panel.current?.contains(t) || anchor.current?.contains(t) || (t as Element).closest?.('.ca-pop, .ca-modal')) return  // #145: answering a dialog opened from the popover keeps it open
      onOpenChange(false)
    }
    document.addEventListener('pointerdown', onDown, true)
    return () => document.removeEventListener('pointerdown', onDown, true)
  }, [open, onOpenChange])
  useEscape(open, () => onOpenChange(false))

  useEffect(() => { if (!open) setPos(null) }, [open])

  return (
    <>
      <span ref={anchor} className="ca-pop-anchor">{trigger({ open, toggle: () => onOpenChange(!open) })}</span>
      {open && createPortal(
        <div
          ref={panel}
          className="ca-pop"
          style={pos ?? { left: -9999, top: -9999 }}
          onPointerDown={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        >
          {children}
        </div>,
        document.body,
      )}
    </>
  )
}
