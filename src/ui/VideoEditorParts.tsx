import type { ReactNode } from 'react'
import type { Editor, TLVideoShape } from 'tldraw'

import type { Beats } from '../beats'
import { thumbUrl } from '../comfy'
import { AUDIO, type AudioShape } from '../shapes/EmbedShapes'
import type { Music } from '../videoEdit'
import { Popover } from './Popover'
import { t } from '../i18n'

export interface MediaItem { id: string; src: string; name: string }

export function pageVideos(editor: Editor): MediaItem[] {
  return editor.getCurrentPageShapes().flatMap((s) => {
    if (s.type !== 'video') return []
    const asset = (s as TLVideoShape).props.assetId ? editor.getAsset((s as TLVideoShape).props.assetId!) : null
    return asset?.type === 'video' && asset.props.src ? [{ id: s.id, src: asset.props.src, name: asset.props.name }] : []
  })
}

export function pageAudios(editor: Editor): MediaItem[] {
  return editor.getCurrentPageShapes().flatMap((s) => (s.type === AUDIO && (s as AudioShape).props.src ? [{ id: s.id, src: (s as AudioShape).props.src, name: (s as AudioShape).props.name }] : []))
}

export function MediaMenu({ open, onOpenChange, label, icon, items, thumbs, empty, onPick }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  label: string
  icon: ReactNode
  items: MediaItem[]
  thumbs: boolean
  empty: string
  onPick: (item: MediaItem) => void
}) {
  return (
    <Popover
      open={open}
      onOpenChange={onOpenChange}
      side="top"
      align="end"
      trigger={({ toggle }) => (
        <button type="button" className="ca-bar__btn" data-open={open || undefined} onClick={toggle}><span className="ca-icon">{icon}</span><span>{label}</span></button>
      )}
    >
      <div className="ca-menu ca-ve__pick">
        {items.map((it) => (
          <button key={it.id} type="button" className="ca-menu__item" onClick={() => onPick(it)}>
            {thumbs && <img className="ca-ve__pick-thumb" src={thumbUrl(it.src)} alt="" />}
            <span className="ca-menu__grow">{it.name}</span>
          </button>
        ))}
        {!items.length && <div className="ca-chat__hint">{empty}</div>}
      </div>
    </Popover>
  )
}

export function MusicPanel({ music, beats, onChange, onRemove }: { music: Music; beats: Beats | null; onChange: (music: Music) => void; onRemove: () => void }) {
  return (
    <>
      <div className="ca-gen__title">{t('videoEditor.music')}</div>
      <div className="ca-chat__hint">{music.name}{beats ? ` · ${t('videoEditor.bpm', Math.round(beats.bpm))}` : ''}</div>
      <label className="ca-panel__row"><span>{t('videoEditor.volume')}</span><input type="range" min={0} max={200} value={Math.round(music.volume * 100)} onChange={(e) => onChange({ ...music, volume: Number(e.target.value) / 100 })} /><span className="ca-panel__val">{Math.round(music.volume * 100)}</span></label>
      <label className="ca-num"><span>{t('videoEditor.musicStart')}</span><input type="number" min={0} step={0.01} value={music.start} onChange={(e) => onChange({ ...music, start: Math.max(0, Number(e.target.value)) })} /></label>
      <button type="button" className="ca-panel__chip" onClick={onRemove}>{t('videoEditor.removeMusic')}</button>
    </>
  )
}
