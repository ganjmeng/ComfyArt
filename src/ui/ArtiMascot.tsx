import { useEffect, useState } from 'react'

import sheetLv1 from '../assets/arti/mascot-lv1-developing.png'
import sheetLv2 from '../assets/arti/mascot-lv2-beret.png'
import sheetLv3 from '../assets/arti/mascot-lv3-brush.png'
import {
  MASCOT_DURATION_MS,
  MASCOT_FRAME_MS,
  MASCOT_FRAMES,
  resolveArtiLevel,
  type ArtiLevel,
} from '../artiLevel'

const SHEETS: Record<ArtiLevel, string> = {
  1: sheetLv1,
  2: sheetLv2,
  3: sheetLv3,
}

export type MascotTrigger = 'idle' | 'play' | 'typing'

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
 * #371 P1-mascot — canvas Agent composer top-left pixel Arti badge.
 * Idle = STATIC frame 0. --play and --typing animate 17×250ms (~4.25s).
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
  const reduce = useReducedMotion()

  useEffect(() => {
    if (levelProp != null) { setLevel(levelProp); return }
    setLevel(resolveArtiLevel())
  }, [levelProp])

  const trigger: MascotTrigger = reduce ? 'idle' : busy ? 'play' : typing ? 'typing' : 'idle'
  const animClass =
    trigger === 'play' ? 'arti-mascot--play' : trigger === 'typing' ? 'arti-mascot--typing' : ''

  return (
    <span
      className={`arti-mascot ${animClass}`.trim()}
      data-testid="arti-mascot"
      data-level={level}
      data-trigger={trigger}
      data-frames={MASCOT_FRAMES}
      data-frame-ms={MASCOT_FRAME_MS}
      data-duration-ms={MASCOT_DURATION_MS}
      aria-hidden="true"
      style={{
        backgroundImage: `url(${SHEETS[level]})`,
        // CSS vars consumed by shell.css keyframes
        ['--mascot-frames' as string]: MASCOT_FRAMES,
        ['--mascot-frame-ms' as string]: `${MASCOT_FRAME_MS}ms`,
        ['--mascot-duration' as string]: `${MASCOT_DURATION_MS}ms`,
      }}
    />
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
