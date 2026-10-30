import { useEffect, useRef, useState } from 'react'
import { useValue } from 'tldraw'

import sheetLv1 from '../assets/arti/mascot-lv1-dna-a.png'
import sheetLv2 from '../assets/arti/mascot-lv2-dna-a.png'
import sheetLv3 from '../assets/arti/mascot-lv3-dna-a.png'
import avatarLv1 from '../assets/arti/mascot-lv1-avatar.png'
import avatarLv2 from '../assets/arti/mascot-lv2-avatar.png'
import avatarLv3 from '../assets/arti/mascot-lv3-avatar.png'
import {
  MASCOT_DURATION_MS,
  MASCOT_FRAME_MS,
  MASCOT_FRAMES,
  resolveArtiLevel,
  type ArtiLevel,
} from '../artiLevel'
import { t } from '../i18n'
import { dismissReviewCard, reviewFeedAtom, type ReviewCard } from '../reviewFeed'
import { useEscape } from './escape'

const SHEETS: Record<ArtiLevel, string> = {
  1: sheetLv1,
  2: sheetLv2,
  3: sheetLv3,
}

/** Content-centered frame-0 stills (ink center = frame center) for level-card — not peek frame0. */
const AVATARS: Record<ArtiLevel, string> = {
  1: avatarLv1,
  2: avatarLv2,
  3: avatarLv3,
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
  const panelRef = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const cards = useValue(reviewFeedAtom)

  useEffect(() => {
    if (levelProp != null) { setLevel(levelProp); return }
    setLevel(resolveArtiLevel())
  }, [levelProp])

  useEscape(notifyOpen, () => setNotifyOpen(false))

  useEffect(() => {
    if (!notifyOpen) return
    const onPointer = (e: MouseEvent) => {
      const el = wrapRef.current
      const panel = panelRef.current
      const tgt = e.target as Node
      if (el && !el.contains(tgt) && !(panel && panel.contains(tgt))) setNotifyOpen(false)
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
    <>
    <span className="arti-mascot-wrap" ref={wrapRef} data-testid="arti-mascot-wrap" data-notify-open={notifyOpen || undefined} aria-hidden={notifyOpen || undefined}>
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
        tabIndex={notifyOpen ? -1 : undefined}
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
    </span>
    {/* #376: reference CN 1:1 — panel is a composer child (same width), anchored 8px above composer top, z5 */}
    {notifyOpen && (
      <div
        ref={panelRef}
        className="arti-notify"
        role="dialog"
        aria-label={t('arti.notify.title')}
        data-testid="arti-notify"
      >
        <div className="arti-notify__head">
          <div className="arti-notify__title" data-testid="arti-notify-title">{t('arti.notify.heading')}</div>
          <button
            type="button"
            className="arti-notify__close"
            data-testid="arti-notify-close"
            aria-label={t('arti.notify.close')}
            onClick={() => setNotifyOpen(false)}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
          </button>
        </div>
        {cards.length === 0 ? (
          <div className="arti-notify__empty" data-testid="arti-notify-empty">
            <span
              className="arti-notify__icon"
              data-testid="arti-notify-icon"
              aria-hidden="true"
              style={{ backgroundImage: `url(${SHEETS[level]})`, ['--mascot-frames' as string]: MASCOT_FRAMES }}
            />
            <div className="arti-notify__empty-title">{t('arti.notify.empty')}</div>
            <div className="arti-notify__empty-hint">{t('arti.notify.emptyHint')}</div>
          </div>
        ) : (
          <ul className="arti-notify__list" data-testid="arti-notify-list">
            {cards.map((card: ReviewCard) => (
              <li key={card.id} className="arti-notify__card" data-testid="arti-review-card" data-card-id={card.id}>
                <div className="arti-notify__card-head">
                  <div className="arti-notify__card-title">{card.title}</div>
                  <button
                    type="button"
                    className="arti-notify__card-dismiss"
                    data-testid="arti-review-dismiss"
                    aria-label={t('arti.notify.dismiss')}
                    onClick={() => void dismissReviewCard(card.id)}
                  >
                    <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
                  </button>
                </div>
                <ul className="arti-notify__issues">
                  {card.issues.map((issue, i) => (
                    <li key={i} className="arti-notify__issue">{issue}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>
    )}
    </>
  )
}

/** Static portrait for /arti level-card — content-centered DNA sheet frame 0 (opaque eyes). */
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
      style={{ backgroundImage: `url(${AVATARS[level]})` }}
    />
  )
}
