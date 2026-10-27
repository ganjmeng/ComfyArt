import { useEffect, useRef, useState } from 'react'

import sheetLv1 from '../assets/arti/mascot-lv1-dna-a.png'
import sheetLv2 from '../assets/arti/mascot-lv2-dna-a.png'
import sheetLv3 from '../assets/arti/mascot-lv3-dna-a.png'
import {
  MASCOT_DURATION_MS,
  MASCOT_FRAME_MS,
  MASCOT_FRAMES,
  resolveArtiLevel,
  type ArtiLevel,
} from '../artiLevel'
import { t } from '../i18n'
import { useEscape } from './escape'

const SHEETS: Record<ArtiLevel, string> = {
  1: sheetLv1,
  2: sheetLv2,
  3: sheetLv3,
}

export type MascotTrigger = 'idle' | 'play' | 'typing' | 'hover'

/** Detect prefers-reduced-motion (and stay in sync). */
function useReducedMotion() {
  const [reduce, setReduce] = useState(() =>
    typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)').matches : false,
  )
  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const mq = matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduce(mq.matches)
    on()
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return reduce
}

/**
 * #371 P1-mascot — canvas Agent composer top-left pixel Arti badge (DNA A).
 * Idle = STATIC frame 0. --play / --typing / hover animate 17×250ms (~4.25s).
 * Hover lifts ~11px + plays; click opens in-canvas 「Arti 通知」 (not /arti).
 * Level stub Lv.1; mock via ?artiLevel= / localStorage.
 */
export function ArtiMascot({
  busy = false,
  typing = false,
  level: levelProp,
}: {
  busy?: boolean
  typing?: boolean
  /** Override for tests / harness; default = resolveArtiLevel() */
  level?: ArtiLevel
}) {
  const [level, setLevel] = useState<ArtiLevel>(() => levelProp ?? resolveArtiLevel())
  const [hover, setHover] = useState(false)
  const [notifyOpen, setNotifyOpen] = useState(false)
  const wrapRef = useRef<HTMLSpanElement>(null)
  const reduce = useReducedMotion()

  useEffect(() => {
    if (levelProp != null) { setLevel(levelProp); return }
    setLevel(resolveArtiLevel())
  }, [levelProp])

  useEscape(notifyOpen, () => setNotifyOpen(false))

  useEffect(() => {
    if (!notifyOpen) return
    const onPointer = (e: MouseEvent) => {
      const el = wrapRef.current
      if (el && !el.contains(e.target as Node)) setNotifyOpen(false)
    }
    document.addEventListener('mousedown', onPointer, true)
    return () => document.removeEventListener('mousedown', onPointer, true)
  }, [notifyOpen])

  const hovering = hover && !reduce
  const trigger: MascotTrigger = reduce
    ? 'idle'
    : busy
      ? 'play'
      : typing
        ? 'typing'
        : hovering
          ? 'hover'
          : 'idle'
  const animClass =
    trigger === 'play'
      ? 'arti-mascot--play'
      : trigger === 'typing'
        ? 'arti-mascot--typing'
        : trigger === 'hover'
          ? 'arti-mascot--hover'
          : ''

  return (
    <span className="arti-mascot-wrap" ref={wrapRef} data-testid="arti-mascot-wrap">
      <button
        type="button"
        className={`arti-mascot ${animClass}`.trim()}
        data-testid="arti-mascot"
        data-level={level}
        data-trigger={trigger}
        data-frames={MASCOT_FRAMES}
        data-frame-ms={MASCOT_FRAME_MS}
        data-duration-ms={MASCOT_DURATION_MS}
        data-notify-open={notifyOpen || undefined}
        aria-label={t('arti.notify.title')}
        aria-expanded={notifyOpen}
        aria-haspopup="dialog"
        style={{
          backgroundImage: `url(${SHEETS[level]})`,
          ['--mascot-frames' as string]: MASCOT_FRAMES,
          ['--mascot-frame-ms' as string]: `${MASCOT_FRAME_MS}ms`,
          ['--mascot-duration' as string]: `${MASCOT_DURATION_MS}ms`,
        }}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={() => setNotifyOpen((o) => !o)}
      />
      {notifyOpen && (
        <div
          className="arti-notify"
          role="dialog"
          aria-label={t('arti.notify.title')}
          data-testid="arti-notify"
        >
          <div className="arti-notify__title">{t('arti.notify.title')}</div>
          <div className="arti-notify__empty" data-testid="arti-notify-empty">
            <div className="arti-notify__empty-title">{t('arti.notify.empty')}</div>
            <div className="arti-notify__empty-hint">{t('arti.notify.emptyHint')}</div>
          </div>
        </div>
      )}
    </span>
  )
}

/** Static portrait for /arti level-card avatar — shares same sheet/level as composer badge. */
export function ArtiLevelAvatar(props: { level?: ArtiLevel } = {}) {
  const levelProp = props.level
  const [level, setLevel] = useState<ArtiLevel>(() => levelProp ?? resolveArtiLevel())
  useEffect(() => {
    if (levelProp != null) { setLevel(levelProp); return }
    setLevel(resolveArtiLevel())
  }, [levelProp])
  return (
    <span
      className="arti-mascot arti-mascot--avatar"
      data-testid="arti-avatar-mascot"
      data-level={level}
      aria-hidden="true"
      style={{
        backgroundImage: `url(${SHEETS[level]})`,
        ['--mascot-frames' as string]: MASCOT_FRAMES,
      }}
    />
  )
}
