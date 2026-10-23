import { useEffect, useRef, useState } from 'react'
import { atom, AssetRecordType, useValue, type Editor, type TLShapeId, type TLVideoShape } from 'tldraw'

import { viewUrl } from '../comfy'
import { detectBeats, snap, type Beats } from '../beats'
import { errorText, GAP, placeMedia, rowSpots, toMedia } from '../jobs'
import { appendClip, clipLength, filmstrip, freshEdit, layout, MIN_CLIP, moveClip, removeClip, splitAt, type Edit, type Source, type Subtitle, type TransitionType } from '../videoEdit'
import { Player } from '../videoPlayer'
import { renderEdit } from '../videoRender'
import { ColorPicker } from './ColorPicker'
import { Icons } from './icons'
import { Chips } from './Chips'
import { useEscape } from './escape'
import { MediaMenu, MusicPanel, pageAudios, pageVideos } from './VideoEditorParts'
import { t } from '../i18n'
import { uuid } from '../id'

export const videoEditorAtom = atom<TLShapeId | null>('video editor', null)

const SPEEDS = [0.5, 1, 1.5, 2]
const TRANSITIONS: [TransitionType, string][] = [['none', t('common.none')], ['fade', t('videoEditor.fade')], ['black', t('videoEditor.fadeToBlack')], ['white', t('videoEditor.fadeToWhite')]]
const THUMBS = 24
const UNDO = 50
const MAX_SIDE = 1920
const SNAP_PX = 8

type Selection = { kind: 'clip' | 'transition'; index: number } | { kind: 'subtitle'; id: string } | { kind: 'music' } | null

const fmt = (t: number) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(2).padStart(5, '0')}`

export function VideoEditor({ editor, onError }: { editor: Editor; onError: (msg: string) => void }) {
  const id = useValue(videoEditorAtom)
  const shape = id ? editor.getShape<TLVideoShape>(id) : null
  const asset = shape?.props.assetId ? editor.getAsset(shape.props.assetId) : null
  const src = asset?.type === 'video' ? asset.props.src : null
  if (!id || !shape || !src || asset?.type !== 'video') return null
  return <EditorBody key={id} editor={editor} shape={shape} src={src} name={asset.props.name} onError={onError} />
}

function EditorBody({ editor, shape, src, name, onError }: { editor: Editor; shape: TLVideoShape; src: string; name: string; onError: (msg: string) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const track = useRef<HTMLDivElement>(null)
  const player = useRef<Player | null>(null)
  const [sources, setSources] = useState<Record<string, Source>>({})
  const [edit, setEditState] = useState<Edit | null>(null)
  const editRef = useRef<Edit | null>(null)
  const history = useRef<{ past: Edit[]; future: Edit[] }>({ past: [], future: [] })
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [sel, setSel] = useState<Selection>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [menu, setMenu] = useState<'export' | 'clip' | 'music' | null>(null)
  const [beats, setBeats] = useState<Beats | null>(null)
  const [snapOn, setSnapOn] = useState(true)
  const close = () => videoEditorAtom.set(null)
  useEscape(true, close)
  const toggle = () => {
    const p = player.current
    if (!p) return
    if (p.playing) { p.pause(); setPlaying(false) } else { p.play(() => setPlaying(false)); setPlaying(true) }
  }

  const commit = (next: Edit, record = true) => {
    if (record && editRef.current) history.current = { past: [...history.current.past.slice(1 - UNDO), editRef.current], future: [] }
    editRef.current = next
    setEditState(next)
  }

  const loadSource = async (url: string, label: string) => {
    const known = sources[url]
    if (known) return known
    const s = { name: label, ...await filmstrip(url, THUMBS, 64) }
    setSources((all) => ({ ...all, [url]: s }))
    return s
  }

  useEffect(() => {
    let alive = true
    loadSource(src, name).then((s) => { if (alive) commit(freshEdit(src, s.duration), false) }).catch((e) => onError(errorText(e)))
    return () => { alive = false }
  }, [src])

  const first = sources[src]
  const ready = !!first && !!edit
  useEffect(() => {
    if (!ready || !canvas.current) return
    const k = Math.min(1, MAX_SIDE / Math.max(first.width, first.height))
    canvas.current.width = Math.round(first.width * k / 2) * 2
    canvas.current.height = Math.round(first.height * k / 2) * 2
    const p = new Player(canvas.current, () => editRef.current!)
    p.onTime = setTime
    player.current = p
    void p.seek(0)
    return () => p.dispose()
  }, [ready])

  useEffect(() => {
    if (edit && player.current && !player.current.playing) void player.current.seek(player.current.current)
  }, [edit])

  const musicSrc = edit?.music?.src
  useEffect(() => {
    setBeats(null)
    if (!musicSrc) return
    let alive = true
    detectBeats(musicSrc).then((b) => { if (alive) setBeats(b) }).catch((e) => onError(errorText(e)))
    return () => { alive = false }
  }, [musicSrc])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement | null)?.closest('input, textarea')) return
      if (e.key === ' ') toggle()
      else return
      e.preventDefault()
      e.stopPropagation()
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  })

  if (!edit || !first) {
    return <div className="ca-modal"><div className="ca-ve ca-ve--loading">{t('videoEditor.loadingVideo')}</div></div>
  }
  const { offsets, total } = layout(edit)
  const pxPerSec = (track.current?.clientWidth ?? 800) / Math.max(total, 0.1)
  const beatTimes = beats && edit.music ? beats.times.map((b) => b - edit.music!.start).filter((b) => b >= 0 && b <= total) : []
  const seekTo = (clientX: number) => {
    const b = track.current!.getBoundingClientRect()
    let at = ((clientX - b.left) / b.width) * total
    if (snapOn) at = snap(at, [...beatTimes, ...offsets], SNAP_PX / pxPerSec)
    player.current?.pause()
    setPlaying(false)
    void player.current?.seek(at)
  }
  const undo = () => {
    const prev = history.current.past.pop()
    if (!prev) return
    history.current.future.push(editRef.current!)
    editRef.current = prev
    setEditState(prev)
  }
  const redo = () => {
    const next = history.current.future.pop()
    if (!next) return
    history.current.past.push(editRef.current!)
    editRef.current = next
    setEditState(next)
  }
  const setClip = (i: number, patch: Partial<Edit['clips'][number]>) => commit({ ...edit, clips: edit.clips.map((c, j) => (j === i ? { ...c, ...patch } : c)) })
  const setSub = (sid: string, patch: Partial<Subtitle>) => commit({ ...edit, subtitles: edit.subtitles.map((s) => (s.id === sid ? { ...s, ...patch } : s)) })

  const trim = (i: number, side: 'start' | 'end') => (e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const base = edit.clips[i]
    const length = sources[base.src]?.duration ?? base.end
    const el = e.currentTarget
    const move = (ev: PointerEvent) => {
      const delta = ((ev.clientX - startX) / pxPerSec) * base.speed
      const value = side === 'start'
        ? Math.min(Math.max(0, base.start + delta), base.end - MIN_CLIP)
        : Math.max(Math.min(length, base.end + delta), base.start + MIN_CLIP)
      const next = { ...edit, clips: edit.clips.map((c, j) => (j === i ? { ...c, [side]: value } : c)) }
      editRef.current = next
      setEditState(next)
    }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerup', () => {
      el.removeEventListener('pointermove', move)
      history.current = { past: [...history.current.past.slice(1 - UNDO), edit], future: [] }
    }, { once: true })
  }

  const addSubtitle = () => {
    const sub: Subtitle = { id: uuid().slice(0, 8), start: time, end: Math.min(total, time + 2), text: t('videoEditor.enterCaptionHere'), size: 56, color: '#FFFFFF' }
    commit({ ...edit, subtitles: [...edit.subtitles, sub] })
    setSel({ kind: 'subtitle', id: sub.id })
  }

  const addClip = async (url: string, label: string) => {
    setMenu(null)
    try {
      const s = await loadSource(url, label)
      commit(appendClip(editRef.current!, url, s.duration))
    } catch (e) {
      onError(errorText(e))
    }
  }

  const exportVideo = async (replace: boolean) => {
    setMenu(null)
    player.current?.pause()
    setPlaying(false)
    setProgress(0)
    try {
      const ref = await renderEdit(edit, canvas.current!.width, canvas.current!.height, setProgress)
      const media = await toMedia(ref, 'video')
      if (replace) {
        const assetId = AssetRecordType.createId()
        editor.createAssets([{ id: assetId, typeName: 'asset', type: 'video', props: { name, src: viewUrl(ref), w: media.w, h: media.h, mimeType: 'video/mp4', isAnimated: true }, meta: {} }])
        editor.updateShape<TLVideoShape>({ id: shape.id, type: 'video', props: { assetId } })
      } else {
        const b = editor.getShapePageBounds(shape)!
        const [p] = rowSpots(editor, shape, [[b.w, b.w * media.h / media.w]], [b.maxX + GAP, b.y])
        editor.select(placeMedia(editor, media, t('videoEditor.edit', name), p.x, p.y, b.w, shape.parentId))
      }
      close()
    } catch (e) {
      onError(errorText(e))
    } finally {
      setProgress(null)
    }
  }

  const clipSel = sel?.kind === 'clip' ? sel.index : null
  const trSel = sel?.kind === 'transition' ? sel.index : null
  const subSel = sel?.kind === 'subtitle' ? edit.subtitles.find((s) => s.id === sel.id) ?? null : null

  return (
    <div className="ca-modal" onPointerDown={(e) => e.stopPropagation()}>
      <div className="ca-ve">
        <div className="ca-ve__head">
          <span className="ca-ve__title">{t('videoEditor.trimTitle', name || t('videoEditor.untitledVideo'))}</span>
          <button type="button" className="ca-bar__btn" disabled={!history.current.past.length} onClick={undo}>{t('common.undo')}</button>
          <button type="button" className="ca-bar__btn" disabled={!history.current.future.length} onClick={redo}>{t('shortcuts.redo')}</button>
          <button type="button" className="ca-bar__btn" onClick={() => { commit(freshEdit(src, first.duration)); setSel(null) }}>{t('adjustPanel.reset')}</button>
          <div className="ca-ve__export">
            <button type="button" className="ca-panel__primary" disabled={progress !== null} onClick={() => setMenu(menu === 'export' ? null : 'export')}>{progress !== null ? t('videoEditor.rendering', Math.round(progress * 100)) : t('common.export')}</button>
            {menu === 'export' && (
              <div className="ca-menu ca-ve__menu">
                <button type="button" className="ca-menu__item" onClick={() => void exportVideo(false)}>{t('videoEditor.exportAsNewVideo')}</button>
                <button type="button" className="ca-menu__item" onClick={() => void exportVideo(true)}>{t('videoEditor.replaceOriginalVideo')}</button>
              </div>
            )}
          </div>
          <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={close}>{Icons.close}</button>
        </div>
        <div className="ca-ve__body">
          <div className="ca-ve__stage"><canvas ref={canvas} /></div>
          <div className="ca-ve__side">
            {clipSel !== null && (
              <>
                <div className="ca-gen__title">{t('videoEditor.clip', clipSel + 1)}</div>
                <div className="ca-chat__hint">{sources[edit.clips[clipSel].src]?.name}</div>
                <div className="ca-gen__label">{t('videoEditor.speed')}</div>
                <Chips value={edit.clips[clipSel].speed} options={SPEEDS.map((v) => [v, `${v}x`] as const)} onPick={(v) => setClip(clipSel, { speed: v })} />
                <label className="ca-panel__row"><span>{t('videoEditor.volume')}</span><input type="range" min={0} max={200} value={Math.round(edit.clips[clipSel].volume * 100)} onChange={(e) => setClip(clipSel, { volume: Number(e.target.value) / 100 })} /><span className="ca-panel__val">{Math.round(edit.clips[clipSel].volume * 100)}</span></label>
                <div className="ca-panel__chips">
                  <button type="button" className="ca-panel__chip" onClick={() => setClip(clipSel, { volume: edit.clips[clipSel].volume ? 0 : 1 })}>{edit.clips[clipSel].volume ? t('videoEditor.mute') : t('videoEditor.unmute')}</button>
                  <button type="button" className="ca-panel__chip" disabled={clipSel === 0} onClick={() => { commit(moveClip(edit, clipSel, clipSel - 1)); setSel({ kind: 'clip', index: clipSel - 1 }) }}>{t('videoEditor.moveLeft')}</button>
                  <button type="button" className="ca-panel__chip" disabled={clipSel === edit.clips.length - 1} onClick={() => { commit(moveClip(edit, clipSel, clipSel + 1)); setSel({ kind: 'clip', index: clipSel + 1 }) }}>{t('videoEditor.moveRight')}</button>
                  <button type="button" className="ca-panel__chip" disabled={edit.clips.length < 2} onClick={() => { commit(removeClip(edit, clipSel)); setSel(null) }}>{t('videoEditor.deleteClip')}</button>
                </div>
              </>
            )}
            {trSel !== null && (
              <>
                <div className="ca-gen__title">{t('videoEditor.transition')}</div>
                <Chips value={edit.transitions[trSel].type} options={TRANSITIONS} onPick={(t) => commit({ ...edit, transitions: edit.transitions.map((x, j) => (j === trSel ? { ...x, type: t } : x)) })} />
                <label className="ca-panel__row"><span>{t('common.duration')}</span><input type="range" min={2} max={20} value={Math.round(edit.transitions[trSel].duration * 10)} onChange={(e) => commit({ ...edit, transitions: edit.transitions.map((x, j) => (j === trSel ? { ...x, duration: Number(e.target.value) / 10 } : x)) })} /><span className="ca-panel__val">{edit.transitions[trSel].duration.toFixed(1)}s</span></label>
                <button type="button" className="ca-panel__chip" onClick={() => commit({ ...edit, transitions: edit.transitions.map((x) => ({ ...x, type: edit.transitions[trSel].type, duration: edit.transitions[trSel].duration })) })}>{t('videoEditor.applyToAllTransitions')}</button>
              </>
            )}
            {subSel && (
              <>
                <div className="ca-gen__title">{t('videoEditor.captions')}</div>
                <textarea className="ca-panel__prompt ca-panel__prompt--boxed" value={subSel.text} onChange={(e) => setSub(subSel.id, { text: e.target.value })} onKeyDown={(e) => e.stopPropagation()} />
                <div className="ca-style__row">
                  <label className="ca-num"><span>{t('videoEditor.start')}</span><input type="number" step={0.1} value={subSel.start.toFixed(1)} onChange={(e) => setSub(subSel.id, { start: Math.max(0, Number(e.target.value)) })} /></label>
                  <label className="ca-num"><span>{t('videoEditor.end')}</span><input type="number" step={0.1} value={subSel.end.toFixed(1)} onChange={(e) => setSub(subSel.id, { end: Math.max(subSel.start + 0.1, Number(e.target.value)) })} /></label>
                </div>
                <div className="ca-style__row">
                  <label className="ca-num"><span>{t('videoEditor.fontSize')}</span><input type="number" value={subSel.size} onChange={(e) => setSub(subSel.id, { size: Math.max(8, Number(e.target.value)) })} /></label>
                  <ColorPicker value={subSel.color} title={t('videoEditor.fontColor')} onChange={(c) => c && setSub(subSel.id, { color: c })} />
                </div>
                <button type="button" className="ca-panel__chip" onClick={() => { commit({ ...edit, subtitles: edit.subtitles.filter((s) => s.id !== subSel.id) }); setSel(null) }}>{t('videoEditor.deleteCaption')}</button>
              </>
            )}
            {sel?.kind === 'music' && edit.music && (
              <MusicPanel music={edit.music} beats={beats} onChange={(music) => commit({ ...edit, music })} onRemove={() => { commit({ ...edit, music: null }); setSel(null) }} />
            )}
            {!sel && <div className="ca-chat__hint">{t('videoEditor.selectAClipToAdjust')}</div>}
          </div>
        </div>
        <div className="ca-ve__controls">
          <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={playing ? t('videoEditor.pause') : t('videoEditor.play')} onClick={toggle}><span className="ca-icon">{playing ? Icons.pause : Icons.play}</span></button>
          <span className="ca-ve__time">{fmt(time)} / {fmt(total)}</span>
          <div className="ca-gen__spacer" />
          <MediaMenu open={menu === 'clip'} onOpenChange={(o) => setMenu(o ? 'clip' : null)} label={t('videoEditor.addClip')} icon={Icons.video} items={pageVideos(editor)} thumbs empty={t('videoEditor.noVideos')} onPick={(it) => void addClip(it.src, it.name)} />
          <MediaMenu open={menu === 'music'} onOpenChange={(o) => setMenu(o ? 'music' : null)} label={edit.music ? t('videoEditor.music') : t('videoEditor.addMusic')} icon={Icons.music} items={pageAudios(editor)} thumbs={false} empty={t('videoEditor.noAudio')} onPick={(it) => { setMenu(null); commit({ ...edit, music: { src: it.src, name: it.name, start: 0, volume: 1 } }); setSel({ kind: 'music' }) }} />
          <button type="button" className="ca-bar__btn" data-on={snapOn || undefined} onClick={() => setSnapOn(!snapOn)}>{t('videoEditor.snapToBeats')}</button>
          <button type="button" className="ca-bar__btn" onClick={() => { const next = splitAt(edit, time); if (next) commit(next) }}><span className="ca-icon">{Icons.trim}</span><span>{t('videoEditor.split')}</span></button>
          <button type="button" className="ca-bar__btn" onClick={addSubtitle}><span className="ca-icon">{Icons.textTool}</span><span>{t('videoEditor.addCaption')}</span></button>
        </div>
        <div className="ca-ve__timeline" onPointerDown={(e) => seekTo(e.clientX)}>
          <div ref={track} className="ca-ve__lanes">
          <div className="ca-ve__track">
            {edit.clips.map((c, i) => {
              const s = sources[c.src]
              const thumbs = s?.thumbs ?? []
              const from = s ? Math.floor((c.start / s.duration) * THUMBS) : 0
              const to = s ? Math.max(from + 1, Math.ceil((c.end / s.duration) * THUMBS)) : 0
              return (
                <div
                  key={i}
                  className="ca-ve__clip"
                  data-on={clipSel === i || undefined}
                  style={{ left: offsets[i] * pxPerSec, width: clipLength(c) * pxPerSec }}
                  onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: 'clip', index: i }) }}
                >
                  <div className="ca-ve__thumbs">{thumbs.slice(from, to).map((t, k) => <img key={k} src={t} alt="" draggable={false} />)}</div>
                  {c.speed !== 1 && <span className="ca-ve__badge">{c.speed}x</span>}
                  {c.volume === 0 && <span className="ca-ve__badge ca-ve__badge--mute">{t('videoEditor.mute')}</span>}
                  <div className="ca-ve__handle" onPointerDown={trim(i, 'start')} />
                  <div className="ca-ve__handle" data-end onPointerDown={trim(i, 'end')} />
                </div>
              )
            })}
            {edit.transitions.map((tr, i) => (
              <button
                key={i}
                type="button"
                className="ca-ve__transition"
                data-on={trSel === i || undefined}
                data-type={tr.type}
                title={t('videoEditor.transition')}
                style={{ left: offsets[i + 1] * pxPerSec }}
                onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: 'transition', index: i }) }}
              />
            ))}
          </div>
          <div className="ca-ve__subs">
            {edit.subtitles.map((s) => (
              <div
                key={s.id}
                className="ca-ve__sub"
                data-on={subSel?.id === s.id || undefined}
                style={{ left: s.start * pxPerSec, width: Math.max(8, (s.end - s.start) * pxPerSec) }}
                onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: 'subtitle', id: s.id }) }}
              >
                {s.text}
              </div>
            ))}
          </div>
          {edit.music && (
            <div className="ca-ve__music" data-on={sel?.kind === 'music' || undefined} onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: 'music' }) }}>
              <span className="ca-ve__music-name">{edit.music.name}</span>
              {beatTimes.map((b) => <span key={b} className="ca-ve__beat" style={{ left: b * pxPerSec }} />)}
            </div>
          )}
          <div className="ca-ve__playhead" style={{ left: time * pxPerSec }} />
          </div>
        </div>
      </div>
    </div>
  )
}
