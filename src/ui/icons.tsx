import { useId, type ReactNode } from 'react'

function Svg({ children, fill, strokeWidth = 1.6 }: { children: ReactNode; fill?: boolean; strokeWidth?: number }) {
  return fill ? (
    <svg viewBox="0 0 24 24" fill="currentColor">{children}</svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

/** Loomi mark, mono: currentColor on a 24 canvas; mask id from useId so several copies never collide. */
export function LoomiMono() {
  const id = `loomi-${useId().replace(/:/g, '')}`
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" data-loomi="mono" aria-hidden="true">
      <mask id={id}>
        <g transform="translate(1.2 1.2) scale(.216)">
          <path fill="#fff" d="M50 4 C56 4, 64 8, 68 16 C74 10, 84 10, 90 18 C96 26, 96 36, 90 42 C98 48, 100 58, 96 66 C92 74, 84 78, 76 76 C72 84, 62 92, 50 92 C38 92, 28 84, 24 76 C16 78, 8 74, 4 66 C0 58, 2 48, 10 42 C4 36, 4 26, 10 18 C16 10, 26 10, 32 16 C36 8, 44 4, 50 4 Z" />
          <path fill="#000" d="M31 46 L35.5 34 L40 46 L51 50.5 L40 55 L35.5 67 L31 55 L20 50.5 Z" />
          <path d="M56 42 Q65 54, 74 42" fill="none" stroke="#000" strokeWidth="5" strokeLinecap="round" />
        </g>
      </mask>
      <rect width="24" height="24" mask={`url(#${id})`} />
    </svg>
  )
}

export const Icons = {
  // #437: in-house filled sparkle-image mark for the model-name (generation) row
  // #442 v6: in-house outline — rounded frame open at the top right, mountain inside, solid 4-point star in the gap
  sparkleImage: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 4H7a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-6" />
      <path d="m4.5 16.5 4-4a1.5 1.5 0 0 1 2.1 0l4.9 4.9" />
      <path d="m13.5 15.4 1.4-1.4a1.5 1.5 0 0 1 2.1 0l2.9 2.9" />
      <path data-solid="star" fill="currentColor" stroke="none" d="M18 1.6c.35 2 1.35 3.05 3.4 3.4-2.05.35-3.05 1.4-3.4 3.4-.35-2-1.35-3.05-3.4-3.4 2.05-.35 3.05-1.4 3.4-3.4Z" />
    </svg>
  ),
  // #437: in-house 56×56 search-results art: grey folder + paper pages under a white folder (.5px hairline)
  searchFolder: (
    <svg viewBox="0 0 56 56" width="56" height="56" aria-hidden="true">
      <path d="M8 16a4 4 0 0 1 4-4h10l4 4h18a4 4 0 0 1 4 4v24H8Z" fill="#d4d4d8" />
      <rect x="15" y="14" width="24" height="26" rx="2" fill="#fafafa" stroke="rgba(0,0,0,.08)" strokeWidth=".5" transform="rotate(-6 27 27)" />
      <rect x="18" y="16" width="24" height="26" rx="2" fill="#fff" stroke="rgba(0,0,0,.08)" strokeWidth=".5" />
      <path d="M22 22h14M22 26h14M22 30h9" stroke="#d4d4d8" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M6 26a3 3 0 0 1 3-3h38a3 3 0 0 1 3 3l-2 18a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3Z" fill="#fff" stroke="rgba(0,0,0,.1)" strokeWidth=".5" />
    </svg>
  ),
  sun: <Svg><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Svg>,
  moon: <Svg><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5" /></Svg>,
  image: <Svg fill><path d="M18 3a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zm-8.78 9.16a1.75 1.75 0 0 0-2.44-.04l-1.23 1.3A2 2 0 0 0 5 14.8V18a1 1 0 0 0 1 1h12.29a.71.71 0 0 0 .5-1.2l-3.55-3.62a1.75 1.75 0 0 0-2.48 0L12 14.94zM15.5 6a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5" /></Svg>,
  video: <Svg fill><path d="M18 3a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zm-7.6 5.6a.9.9 0 0 0-1.4.75v5.3a.9.9 0 0 0 1.4.75l4-2.65a.9.9 0 0 0 0-1.5z" /></Svg>,
  genVideo: <Svg><rect x="3" y="5" width="13" height="14" rx="3" /><path d="m16 10.5 4.2-2.6a.5.5 0 0 1 .8.4v7.4a.5.5 0 0 1-.8.4L16 13.5" /></Svg>,
  doodle: <Svg><path d="M4 18c2.5-4 4.5-6 6-6 2 0 .5 5 2.5 5s3-6 5.5-6c1.2 0 2 .8 2 2" /></Svg>,
  trim: <Svg><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><path d="M8 7.5 20 17M8 16.5 20 7" /></Svg>,
  extend: <Svg><rect x="3" y="6" width="10" height="12" rx="2" /><path d="M16.5 12H21M18.8 9.7 21 12l-2.2 2.3" /></Svg>,
  comment: <Svg><path d="M12 3.5a8.5 8.5 0 0 0-7.4 12.7L3.5 20.5l4.3-1.1A8.5 8.5 0 1 0 12 3.5z" /></Svg>,
  lasso: <Svg><path d="M7 17.5c-2.2-1-3.5-2.8-3.5-5C3.5 8 7.3 4.5 12 4.5s8.5 3.5 8.5 8-3.8 8-8.5 8c-1 0-2-.1-2.8-.4" /><circle cx="7" cy="18.5" r="1.5" /></Svg>,
  list: <Svg><path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" /></Svg>,
  qr: <Svg><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 18h2v2h-2zM14 18h2M18 14h2" /></Svg>,
  box: <Svg><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /></Svg>,
  close: <Svg><path d="M6 6l12 12M18 6 6 18" /></Svg>,
  trash: <Svg><path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 12.5h9l1-12.5" /></Svg>,
  /** #494 — Lucide-style bookmark (stroke 2); filled variant = saved. */
  bookmark: <Svg strokeWidth={2}><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" /></Svg>,
  bookmarkFilled: <Svg strokeWidth={2}><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" fill="currentColor" /></Svg>,
  user: <Svg strokeWidth={2}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Svg>,
  /** #494 — Lucide `workflow`: custom-workflow card fallback. */
  workflow: <Svg strokeWidth={2}><rect width="8" height="8" x="3" y="3" rx="2" /><path d="M7 11v4a2 2 0 0 0 2 2h4" /><rect width="8" height="8" x="13" y="13" rx="2" /></Svg>,
  heart: <Svg strokeWidth={2}><path d="M19.5 12.5c1.8-1.8 1.8-4.7 0-6.5s-4.7-1.8-6.5 0L12 7.5l-1-1c-1.8-1.8-4.7-1.8-6.5 0s-1.8 4.7 0 6.5L12 20.5z" /></Svg>,
  eye: <Svg><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.8" /></Svg>,
  eyeOff: <Svg><path d="M4 4l16 16M9.9 6A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.7 3.4M6.4 7.6A17 17 0 0 0 2.5 12S6 18.5 12 18.5a9 9 0 0 0 3.7-.8" /></Svg>,
  lock: <Svg><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /></Svg>,
  unlock: <Svg><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V8a4 4 0 0 1 7.7-1.5" /></Svg>,
  palette: <Svg><circle cx="12" cy="12" r="8.5" /></Svg>,
  files: <Svg><path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5z" /><path d="M14 3.5v5h5" /><circle cx="11.5" cy="14" r="2.3" /><path d="m13.2 15.7 2.3 2.3" /></Svg>,
  map: <Svg><path d="M3.5 6.5 9 4l6 2.5L20.5 4v13.5L15 20l-6-2.5-5.5 2.5z" /><path d="M9 4v13.5M15 6.5V20" /></Svg>,
  plus: <Svg><path d="M12 5v14M5 12h14" /></Svg>,
  // Lucide square-plus
  squarePlus: <Svg><rect width="18" height="18" x="3" y="3" rx="2" /><path d="M8 12h8" /><path d="M12 8v8" /></Svg>,
  home: <Svg><path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-3.5v-5.5h-6v5.5H5.5A1.5 1.5 0 0 1 4 19z" /></Svg>,
  settings: <Svg><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></Svg>,
  exit: <Svg><path d="M10 4.5H6.5A2 2 0 0 0 4.5 6.5v11A2 2 0 0 0 6.5 19.5H10" /><path d="M14 12H7.5" /><path d="M12 8.5 15.5 12 12 15.5" /></Svg>,
  folder:<Svg><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M3.5 10h17" /></Svg>,
  page: <Svg><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M12 8.5v7M8.5 12h7" /></Svg>,
  panel: <Svg><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><path d="M9.5 4.5v15" /></Svg>,
  wave: <Svg><path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" /></Svg>,
  mic: <Svg><rect x="9" y="3.5" width="6" height="11" rx="3" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v2.5" /></Svg>,
  music: <Svg><path d="M9 18V5.5l11-2V16" /><circle cx="6.5" cy="18" r="2.5" /><circle cx="17.5" cy="16" r="2.5" /></Svg>,
  cube: <Svg><path d="M12 3 4 7.5v9L12 21l8-4.5v-9z" /><path d="M4 7.5 12 12l8-4.5M12 12v9" /></Svg>,
  sound: <Svg><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" /><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" /></Svg>,
  soundOff: <Svg><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" /><path d="m16 9.5 5 5M21 9.5l-5 5" /></Svg>,
  panelRight: <Svg><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><path d="M14.5 4.5v15" /></Svg>,
  panelLeft: <Svg><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><path d="M9.5 4.5v15" /></Svg>,
  agent: <LoomiMono />,
  think: <Svg strokeWidth={2}><path d="M12 18V5" /><path d="M15 13a4.17 4.17 0 01-3-4 4.17 4.17 0 01-3 4" /><path d="M17.707 6.294A3 3 0 1012 5a3 3 0 10-5.707 1.294" /><path d="M17.996 5.125a4 4 0 012.526 5.77" /><path d="M18 18a4 4 0 002-7.465" /><path d="M19.967 17.482a4 4 0 11-7.967.517 4 4 0 11-7.967-.517" /><path d="M6 18a4 4 0 01-2-7.465" /><path d="M6.004 5.125a4 4 0 00-2.526 5.77" /></Svg>,
  /** #382: Lucide `history` for 「记忆已更新 ›」 row (process rail, stroke 2 like other #326 icons). */
  /** #435/#441: in-house solid head-in-profile with a bolt cut-out for the 记忆已读取 / 记忆已更新 rows (filled currentColor, no stroke). */
  memoryHead: <Svg strokeWidth={1.5}><path d="M7 22v-4.4a8 8 0 1 1 12.4-7.4l1.9 3.4a1 1 0 0 1-.9 1.4H19v2a2.5 2.5 0 0 1-2.5 2.5H15V22a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1Z" /><path d="M12.6 6.2 10 10.6h3.2L11 14.8" /></Svg>,
  /** #441: 16px › after 记忆已更新 (follows the text colour). */
  memoryChev: <Svg strokeWidth={1.5}><path d="m9.5 7 5 5-5 5" /></Svg>,
  keyReturn: <Svg strokeWidth={1.5}><path d="M19 7v5a4 4 0 0 1-4 4H7" /><path d="m10 12-3 4 3 4" /></Svg>,
  history: <Svg strokeWidth={2}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l4 2" /></Svg>,
  /* #326 Lucide AI Elements · stroke 2 · process timeline */
  circlePlus: <Svg strokeWidth={2}><circle cx="12" cy="12" r="10" /><path d="M8 12h8" /><path d="M12 8v8" /></Svg>,
  messageSquare: <Svg strokeWidth={2}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></Svg>,
  scrollText: <Svg strokeWidth={2}><path d="M15 12h-5" /><path d="M15 8h-5" /><path d="M19 17V5a2 2 0 0 0-2-2H4" /><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" /></Svg>,
  globe: <Svg strokeWidth={2}><circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" /><path d="M2 12h20" /></Svg>,
  imageLine: <Svg strokeWidth={2}><rect width="18" height="18" x="3" y="3" rx="2" ry="2" /><circle cx="9" cy="9" r="2" /><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" /></Svg>,
  videoLine: <Svg strokeWidth={2}><path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5" /><rect x="2" y="6" width="14" height="12" rx="2" /></Svg>,
  /* #348 Lucide · stroke 2 · process row kinds */
  fileSearch: <Svg strokeWidth={2}><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M4.268 21a2 2 0 0 0 1.727 1H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3" /><path d="m9 18-1.5-1.5" /><circle cx="5" cy="14" r="3" /></Svg>,
  squareCode: <Svg strokeWidth={2}><path d="M10 9.5 8 12l2 2.5" /><path d="m14 9.5 2 2.5-2 2.5" /><rect width="18" height="18" x="3" y="3" rx="2" /></Svg>,
  fileCode: <Svg strokeWidth={2}><path d="M10 12.5 8 15l2 2.5" /><path d="m14 12.5 2 2.5-2 2.5" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" /></Svg>,
  filePenLine: <Svg strokeWidth={2}><path d="m18 5-2.414-2.414A2 2 0 0 0 14.172 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2" /><path d="M21.378 12.626a1 1 0 0 0-3.004-3.004l-4.01 4.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z" /><path d="M8 18h1" /></Svg>,
  listChecks: <Svg strokeWidth={2}><path d="m3 17 2 2 4-4" /><path d="m3 7 2 2 4-4" /><path d="M13 6h8" /><path d="M13 12h8" /><path d="M13 18h8" /></Svg>,
  code: <Svg strokeWidth={2}><path d="m16 18 6-6-6-6" /><path d="m8 6-6 6 6 6" /></Svg>,
  eyeView: <Svg strokeWidth={2}><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></Svg>,
  sparkles: <Svg strokeWidth={2}><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" /><path d="M20 3v4" /><path d="M22 5h-4" /><path d="M4 17v2" /><path d="M5 18H3" /></Svg>,
  skill: <Svg><path d="M6 3.5h9l3 3V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 20z" /><path d="M9 10h6M9 13.5h6M9 17h3.5" /></Svg>,
  uploadArrow: <Svg><path d="M12 3v12" /><path d="m17 8-5-5-5 5" /><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /></Svg>,
  upload: <Svg><path d="M15.5 8.5 10 14a2.1 2.1 0 0 0 3 3l6-6a3.5 3.5 0 0 0-5-5l-6.2 6.2a5 5 0 0 0 7 7L20 14" /></Svg>,
  next: <Svg><path d="m10 7 5 5-5 5" /></Svg>,
  expandPanel: <Svg><path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5 13 11M4.5 19.5 11 13" /></Svg>,
  search: <Svg><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></Svg>,
  assets: <Svg><path d="M4.5 7.5 12 4l7.5 3.5L12 11z" /><path d="M4.5 12 12 15.5 19.5 12M4.5 16.5 12 20l7.5-3.5" /></Svg>,
  grid: <Svg><rect x="4" y="4" width="7" height="7" rx="1.5" /><rect x="13" y="4" width="7" height="7" rx="1.5" /><rect x="4" y="13" width="7" height="7" rx="1.5" /><rect x="13" y="13" width="7" height="7" rx="1.5" /></Svg>,
  merge: <Svg><rect x="4" y="4" width="11" height="11" rx="2" /><path d="M9 20h9a2 2 0 0 0 2-2V9" /></Svg>,
  alignLeft: <Svg><path d="M4.5 4v16M8 8h11M8 16h6" /></Svg>,
  alignCenterH: <Svg><path d="M12 4v16M6 8h12M8.5 16h7" /></Svg>,
  alignRight: <Svg><path d="M19.5 4v16M5 8h11M10 16h6" /></Svg>,
  alignTop: <Svg><path d="M4 4.5h16M8 8v11M16 8v6" /></Svg>,
  alignCenterV: <Svg><path d="M4 12h16M8 6v12M16 8.5v7" /></Svg>,
  alignBottom: <Svg><path d="M4 19.5h16M8 5v11M16 10v6" /></Svg>,
  distributeH: <Svg><path d="M4.5 4v16M19.5 4v16" /><rect x="9.5" y="8" width="5" height="8" rx="1" /></Svg>,
  distributeV: <Svg><path d="M4 4.5h16M4 19.5h16" /><rect x="8" y="9.5" width="8" height="5" rx="1" /></Svg>,
  rect: <Svg><rect x="4" y="5.5" width="16" height="13" rx="1.5" /></Svg>,
  ellipse: <Svg><ellipse cx="12" cy="12" rx="8.5" ry="7" /></Svg>,
  polygon: <Svg><path d="m12 3.5 8.5 6.2-3.2 10H6.7l-3.2-10z" /></Svg>,
  unite: <Svg><path d="M4 4h10v6h6v10H10v-6H4z" /></Svg>,
  subtract: <Svg><path d="M4 4h10v6h-4v4H4z" /><path d="M10 10h10v10H10z" strokeDasharray="2 2" /></Svg>,
  intersect: <Svg><path d="M4 4h10v10H4zM10 10h10v10H10z" strokeDasharray="2 2" /><path d="M10 10h4v4h-4z" fill="currentColor" /></Svg>,
  exclude: <Svg><path d="M4 4h10v6h-4v4H4zM20 20H10v-6h4v-4h6z" fill="currentColor" stroke="none" /><path d="M4 4h10v10H4zM10 10h10v10H10z" /></Svg>,
  pen: <Svg><path d="M12 19.5 5 13l2.5-7.5L12 4l4.5 1.5L19 13z" /><path d="M12 4v6.5" /><circle cx="12" cy="11.5" r="1.2" /></Svg>,
  star: <Svg><path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" /></Svg>,
  textTool: <Svg><path d="M5 6V4.5h14V6M12 4.5v15M9 19.5h6" /></Svg>,
  frame: <Svg><path d="M7 3.5v17M17 3.5v17M3.5 7h17M3.5 17h17" /></Svg>,
  hand: <Svg><path d="M8 12V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7-2.4 0-3.8-1-5-3l-2.3-4a1.5 1.5 0 0 1 2.6-1.5L8 13" /></Svg>,
  radius: <Svg><path d="M4.5 19.5V11a6.5 6.5 0 0 1 6.5-6.5h8.5" /></Svg>,
  link: <Svg><path d="M9.5 14.5 14.5 9.5M10.5 6.5l1.4-1.4a4 4 0 0 1 5.7 5.7l-1.4 1.4M13.5 17.5l-1.4 1.4a4 4 0 0 1-5.7-5.7l1.4-1.4" /></Svg>,
  keyboard: <Svg><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M10.5 10h.01M14 10h.01M17.5 10h.01M8 14h8" /></Svg>,
  stroke: <Svg><circle cx="12" cy="12" r="7.5" /><circle cx="12" cy="12" r="4" /></Svg>,
  spacing: <Svg><path d="M5 7h14M5 12h14M5 17h9" /></Svg>,
  replace: <Svg><path d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.7L4 15.5M4 20v-4.5h4.5" /></Svg>,
  minus: <Svg><path d="M5 12h14" /></Svg>,
  rotate: <Svg><path d="M20 12a8 8 0 1 1-2.3-5.6L20 8.5M20 4v4.5h-4.5" /></Svg>,
  adjust: <Svg><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></Svg>,
  effects: <Svg><path d="M12 3.5 14 9l5.5 2-5.5 2-2 5.5-2-5.5-5.5-2L10 9z" /></Svg>,
  restore: <Svg><path d="M4 12a8 8 0 1 0 2.3-5.6L4 8.5M4 4v4.5h4.5" /><path d="M12 8v4l3 2" /></Svg>,
  preview: <Svg><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></Svg>,
  export: <Svg><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14" /></Svg>,
  play: <Svg fill><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5" /></Svg>,
  pause: <Svg fill><rect x="6.5" y="5" width="4" height="14" rx="1" /><rect x="13.5" y="5" width="4" height="14" rx="1" /></Svg>,
  stop: <Svg fill><rect x="6.5" y="6.5" width="11" height="11" rx="2" /></Svg>,
  bell: <Svg><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0" /></Svg>,
  memory: <Svg><path d="M12 4.5a5.5 5.5 0 0 0-5.5 5.5c0 2 1 3.4 2.3 4.4.5.4.7 1 .7 1.6v1.5h5v-1.5c0-.6.2-1.2.7-1.6 1.3-1 2.3-2.4 2.3-4.4A5.5 5.5 0 0 0 12 4.5zM9.5 20h5" /></Svg>,
  pinOutline: <Svg><path d="M14.5 3.5 20.5 9.5 18 10.5 14.8 13.7 14.6 17.4 12.8 19.2 4.8 11.2 6.6 9.4 10.3 9.2 13.5 6z" /><path d="M8.6 15.4 3.8 20.2" /></Svg>,
  pinSolid: <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 3.5 20.5 9.5 18 10.5 14.8 13.7 14.6 17.4 12.8 19.2 4.8 11.2 6.6 9.4 10.3 9.2 13.5 6z" /><path d="M8.6 15.4 3.8 20.2" fill="none" /></svg>,
  resetCcw: <Svg><path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" /><path d="M6.7 2.8v3.9h3.9" /></Svg>,
  pin: <Svg><path d="M9 4h6l-1 6 3 3H7l3-3z" /><path d="M12 13v7" /></Svg>,
  select: <Svg><path d="M5 3.5 19 10l-6.2 1.8L10 18z" /></Svg>,
  genImage: <Svg><path d="M20 11.5V17a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h5.5" /><path d="m4.5 16.5 4-4a1.6 1.6 0 0 1 2.2 0L15 17" /><path d="M18 2.5v5M15.5 5h5" /></Svg>,
  chevron: <Svg><path d="m7 10 5 5 5-5" /></Svg>,
  check: <Svg><path d="m5 12.5 4.5 4.5L19 7.5" /></Svg>,
  question: <Svg><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></Svg>,
  send: <Svg><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" /></Svg>,
  download: <Svg><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14" /></Svg>,
  more: <Svg fill><circle cx="5.5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="18.5" cy="12" r="1.6" /></Svg>,
  crop: <Svg><path d="M6 2.5V16a2 2 0 0 0 2 2h13.5M2.5 6H16a2 2 0 0 1 2 2v13.5" /></Svg>,
  flipH: <Svg><path d="M12 3v18M9 6 4 18h5zM15 6l5 12h-5z" /></Svg>,
  flipV: <Svg><path d="M3 12h18M6 9 18 4v5zM6 15l12 5v-5z" /></Svg>,
  quick: <Svg fill><circle cx="12" cy="12" r="10" /><path fill="var(--ca-float)" d="M10.2 15.6h3.6v-1.3h-2.2V9.8h-1.4zM16.3 8.6a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2m0 1.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6M5.4 12.2h3.2v-1.3H5.4z" /></Svg>,
  upscale: <Svg><rect x="3" y="5.5" width="18" height="13" rx="3" /><path d="M7.5 9.5v5M7.5 12h3M10.5 9.5v5M13.5 9.5v5h1.5a2.5 2.5 0 0 0 0-5z" /></Svg>,
  cutout: <Svg><path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" /><circle cx="12" cy="10" r="2.5" /><path d="M7.5 17a4.5 4.5 0 0 1 9 0" /></Svg>,
  erase: <Svg><path d="m8 20-4.3-4.3a1.6 1.6 0 0 1 0-2.3l9-9a1.6 1.6 0 0 1 2.3 0l5.3 5.3a1.6 1.6 0 0 1 0 2.3L12.6 20z" /><path d="M8 20h12M7.2 10.8l6 6" /></Svg>,
  layers: <Svg><path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8z" /><path d="m3.5 12 8.5 4.5 8.5-4.5M3.5 16l8.5 4.5 8.5-4.5" /></Svg>,
  text: <Svg><rect x="3.5" y="3.5" width="17" height="17" rx="3" /><path d="M8 8.5h8M12 8.5v8" /></Svg>,
  angles: <Svg><path d="M12 3 4.5 7.2v9.6L12 21l7.5-4.2V7.2z" /><path d="M4.5 7.2 12 11.4l7.5-4.2M12 11.4V21" /></Svg>,
  animate: <Svg><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M8.5 14.5v-5h2.2M8.5 12h1.8M12.7 9.5v5M15.2 14.5v-5h2.2M15.2 12h1.8" /></Svg>,
  expand: <Svg><path d="M9 4H5.5A1.5 1.5 0 0 0 4 5.5V9M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15M15 20h3.5a1.5 1.5 0 0 0 1.5-1.5V15" /><rect x="9" y="9" width="6" height="6" rx="1" /></Svg>,
  undo: <Svg><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></Svg>,
  reset: <Svg><path d="M19.5 12a7.5 7.5 0 1 1-2.1-5.2" /><path d="M19.5 4.2V8H15.7" /></Svg>,
  redo: <Svg><path d="m15 14 5-5-5-5" /><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13" /></Svg>,
  refs: <Svg><rect x="3.5" y="4.5" width="17" height="15" rx="3" /><circle cx="15.5" cy="9.5" r="1.8" /><path d="m4 17 4.5-4.5a1.6 1.6 0 0 1 2.2 0L16 18" /></Svg>,
  thumbsUp: <Svg><path d="M7 11v9H4.5a1.5 1.5 0 0 1-1.5-1.5v-6A1.5 1.5 0 0 1 4.5 11H7z" /><path d="M7 11V9.2A3.2 3.2 0 0 1 10.2 6h.3l.8-2.2A1.8 1.8 0 0 1 13 2.5h.2A1.8 1.8 0 0 1 15 4.3V7h3.2a1.8 1.8 0 0 1 1.75 2.22l-1.2 5.1A2.5 2.5 0 0 1 16.3 16.5H7" /></Svg>,
  thumbsDown: <Svg><path d="M17 13V4h2.5A1.5 1.5 0 0 1 21 5.5v6A1.5 1.5 0 0 1 19.5 13H17z" /><path d="M17 13v1.8A3.2 3.2 0 0 1 13.8 18h-.3l-.8 2.2A1.8 1.8 0 0 1 11 21.5h-.2A1.8 1.8 0 0 1 9 19.7V17H5.8a1.8 1.8 0 0 1-1.75-2.22l1.2-5.1A2.5 2.5 0 0 1 7.7 7.5H17" /></Svg>,
  // #439 memory dialog group titles: in-house outline icons (stroke 1.5 @24)
  memPalette: <Svg strokeWidth={1.5}><path d="M12 3a9 9 0 1 0 0 18c1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.8-1.7 1.7-1.7H16a5 5 0 0 0 5-5C21 6.2 17 3 12 3z" /><circle cx="7.5" cy="11.5" r="1.1" /><circle cx="9.5" cy="7.5" r="1.1" /><circle cx="14.5" cy="7.5" r="1.1" /></Svg>,
  memBook: <Svg strokeWidth={1.5}><path d="M2.5 5.5C5 4.5 8.5 4.5 12 6.5v13c-3.5-2-7-2-9.5-1z" /><path d="M21.5 5.5c-2.5-1-6-1-9.5 1v13c3.5-2 7-2 9.5-1z" /></Svg>,
  memWrench: <Svg strokeWidth={1.5}><path d="M20.8 6.3a5.2 5.2 0 0 1-6.9 6.1l-7.2 7.2a2.1 2.1 0 0 1-3-3l7.2-7.2a5.2 5.2 0 0 1 6.1-6.9l-3.2 3.2.4 2.6 2.6.4 3.2-3.2c.1.3.1.5.1.8z" /></Svg>,
  memAssets: <Svg strokeWidth={1.5}><path d="M7 3.5l3.5 6h-7z" /><circle cx="16.5" cy="7" r="3" /><rect x="9" y="13.5" width="6" height="6" rx=".6" transform="rotate(15 12 16.5)" /></Svg>,
  info: <Svg><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></Svg>,
  /* #540 更多工具: original filled glyphs (fill=currentColor, no stroke) — drawn in-house, not Lovart SVGs; design may swap. */
  caretFill: <Svg fill><path d="M6.6 9.3h10.8a.6.6 0 0 1 .45 1l-5.4 5.7a.6.6 0 0 1-.9 0l-5.4-5.7a.6.6 0 0 1 .45-1z" /></Svg>,
  toolErase: <Svg fill><path d="M14.1 3.6a2 2 0 0 1 2.8 0l3.5 3.5a2 2 0 0 1 0 2.8L12.3 18H20a1 1 0 1 1 0 2H8.6a2 2 0 0 1-1.4-.6l-3.6-3.6a2 2 0 0 1 0-2.8z" /></Svg>,
  toolCrop: <Svg fill><path fillRule="evenodd" d="M6 2a1 1 0 0 1 1 1v13a1 1 0 0 0 1 1h13a1 1 0 1 1 0 2h-2v2a1 1 0 1 1-2 0v-2H8a3 3 0 0 1-3-3V8H3a1 1 0 0 1 0-2h2V3a1 1 0 0 1 1-1zm3 4h7a3 3 0 0 1 3 3v6h-2V9a1 1 0 0 0-1-1H9z" /></Svg>,
  toolExpand: <Svg fill><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H9v2H6v3H4zM15 4h3.5A1.5 1.5 0 0 1 20 5.5V9h-2V6h-3zM4 15h2v3h3v2H5.5A1.5 1.5 0 0 1 4 18.5zM18 15h2v3.5a1.5 1.5 0 0 1-1.5 1.5H15v-2h3z" /><rect x="8.5" y="8.5" width="7" height="7" rx="1.5" /></Svg>,
  toolAdjust: <Svg fill><path d="M3 6h9v2H3zM19.5 6H21v2h-1.5zM3 16h3.5v2H3zM13.5 16H21v2h-7.5z" /><circle cx="16" cy="7" r="3" /><circle cx="10" cy="17" r="3" /></Svg>,
  toolText: <Svg fill><path fillRule="evenodd" d="M6 3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zm2 5v2h3v7h2v-7h3V8z" /></Svg>,
  toolAngles: <Svg fill><path d="M12 2.6 20 7l-8 4.4L4 7zM3.4 8.6l7.6 4.2v8.6l-7.6-4.2zM20.6 8.6v8.6L13 21.4v-8.6z" /></Svg>,
  toolVector: <Svg fill><path fillRule="evenodd" d="M12 2l6 7-2.6 8H8.6L6 9zm0 8a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z" /><rect x="8" y="18.5" width="8" height="3" rx="1" /></Svg>,
  toolMove: <Svg fill><path d="M12 2l3.5 3.5H13v5.5h5.5V8.5L22 12l-3.5 3.5V13H13v5.5h2.5L12 22l-3.5-3.5H11V13H5.5v2.5L2 12l3.5-3.5V11H11V5.5H8.5z" /></Svg>,
  toolFlip: <Svg fill><path d="M10.6 4.4a.6.6 0 0 1 1.1.3v14.7a.6.6 0 0 1-.6.6H3.6a.6.6 0 0 1-.5-.9zM13.4 4.4a.6.6 0 0 0-1.1.3v14.7a.6.6 0 0 0 .6.6h7.5a.6.6 0 0 0 .5-.9z" opacity=".55" /><path d="M10.6 4.4a.6.6 0 0 1 1.1.3v14.7a.6.6 0 0 1-.6.6H3.6a.6.6 0 0 1-.5-.9z" /></Svg>,
  toolTo3d: <Svg fill><path fillRule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zM8.5 5.6a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 0 0 0-4.8z" /></Svg>,
  toolLipsync: <Svg fill><path d="M12 2a3.5 3.5 0 0 1 3.5 3.5v5a3.5 3.5 0 0 1-7 0v-5A3.5 3.5 0 0 1 12 2zM5 10a1 1 0 0 1 2 0 5 5 0 0 0 10 0 1 1 0 1 1 2 0 7 7 0 0 1-6 6.9V20h3a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h3v-3.1A7 7 0 0 1 5 10z" /></Svg>,
  toolAudio: <Svg fill><path d="M20 3v12.5a3.5 3.5 0 1 1-2-3.2V7.3l-8 1.6v8.6a3.5 3.5 0 1 1-2-3.2V5.4z" /></Svg>,
}
