import { useState } from 'react'
import { atom, useValue, type Editor } from 'tldraw'

import { generateAudio, musicModels, SFX_SECONDS, voices, type AudioSpec } from '../assetGen'
import { CUSTOM_SPEECH, workflowConfigAtom } from '../customWorkflows'
import { clampMusicSeconds, musicDuration, musicMissing } from '../music'
import { AUDIO, clock, type AudioShape } from '../shapes/EmbedShapes'
import { FieldSelect } from './FieldSelect'
import { Modal } from './Modal'
import { Chips } from './Chips'
import { t } from '../i18n'

type Tab = 'music' | 'speech' | 'sfx'
const TABS: [Tab, string][] = [['music', t('audio.music')], ['speech', t('audio.voiceover')], ['sfx', t('audio.soundEffect')]]
const CLONE = 'clone'

export const audioDialogAtom = atom<boolean>('audio dialog', false)

export function AudioDialog({ editor, onError }: { editor: Editor; onError: (msg: string) => void }) {
  const open = useValue(audioDialogAtom)
  const [tab, setTab] = useState<Tab>('music')
  const [prompts, setPrompts] = useState<Record<Tab, string>>({ music: '', speech: '', sfx: '' })
  const [lyrics, setLyrics] = useState('')
  const [seconds, setSeconds] = useState(30)
  const [sfxSeconds, setSfxSeconds] = useState(8)
  const models = useValue('music models', musicModels, [])
  const [pickedModel, setModel] = useState(models[0].id)
  const model = models.find((m) => m.id === pickedModel) ?? models[0]
  const speechFile = useValue('speech workflow', () => workflowConfigAtom.get().speech ?? null, [])
  const [picked, setVoice] = useState('')
  const reference = useValue('selected audio', () => {
    const s = editor.getOnlySelectedShape()
    return s?.type === AUDIO ? (s as AudioShape).props.src : null
  }, [editor])
  if (!open) return null
  const list = voices()
  // product #509: custom speech replaces the built-in voice list with the assigned workflow filename
  const speechCustom = !!speechFile
  const voice = picked === CLONE || picked === CUSTOM_SPEECH || list.includes(picked) ? picked : (speechCustom ? CUSTOM_SPEECH : list[0])
  const close = () => audioDialogAtom.set(false)
  const range = musicDuration(model.id)
  const musicSeconds = clampMusicSeconds(model.id, seconds)
  const prompt = prompts[tab]
  const spec = (): AudioSpec | null => {
    const text = prompt.trim()
    if (tab === 'music' && musicMissing({ prompt, lyrics })) return null
    if (!text) return null
    if (tab === 'music') return { kind: 'music', model: model.id, prompt: text, lyrics: lyrics.trim(), seconds: musicSeconds }
    if (tab === 'sfx') return { kind: 'sfx', prompt: text, seconds: sfxSeconds }
    if (voice === CLONE && reference) return { kind: 'clone', text, reference }
    return { kind: 'speech', text, voice: voice === CUSTOM_SPEECH || voice === CLONE ? list[0] : voice }
  }
  const run = () => {
    const s = spec()
    if (!s) return
    close()
    generateAudio(editor, s, onError)
  }

  return (
    <Modal title={t('audio.generateAudio')} onClose={close}>
      <div className="ca-rename__body">
        <Chips value={tab} options={TABS} onPick={setTab} />
        <textarea
          autoFocus
          className="ca-panel__prompt ca-panel__prompt--boxed"
          value={prompt}
          placeholder={tab === 'music' ? t('audio.musicPlaceholder') : tab === 'sfx' ? t('audio.sfxPlaceholder') : t('audio.speechPlaceholder')}
          onChange={(e) => setPrompts({ ...prompts, [tab]: e.target.value })}
          onKeyDown={(e) => e.stopPropagation()}
        />
        {tab === 'music' && (
          <>
            <textarea className="ca-panel__prompt ca-panel__prompt--boxed" value={lyrics} placeholder={t('audio.lyricsPlaceholder')} onChange={(e) => setLyrics(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
            <div className="ca-rename__field"><span>{t('audio.model')}</span>
              <FieldSelect
                value={model.id}
                options={models.map((m) => ({ id: m.id, label: m.label, title: m.desc }))}
                onChange={setModel}
              />
            </div>
          </>
        )}
        {tab === 'music' ? (
          // one fixed-height row for the slider and the note, so switching models never moves the controls below
          <div className="ca-audio__length" data-testid="music-length-row">
            {range ? (
              <label className="ca-panel__row"><span>{t('audio.duration')}</span><input type="range" min={range.min} max={range.max} step={range.step} value={musicSeconds} onChange={(e) => setSeconds(Number(e.target.value))} /><span className="ca-panel__val">{clock(musicSeconds)}</span></label>
            ) : (
              <div className="ca-panel__row" data-testid="music-duration-note"><span>{t('audio.duration')}</span><span className="ca-chat__hint">{t('audio.durationByLyrics')}</span><span /></div>
            )}
          </div>
        ) : tab === 'speech' ? (
          <div className="ca-rename__field"><span>{t('audio.voice')}</span>
            <FieldSelect
              value={voice}
              options={[
                ...(reference ? [{ id: CLONE, label: t('audio.cloneSelected') }] : []),
                ...(speechCustom
                  ? [{ id: CUSTOM_SPEECH, label: speechFile!.replace(/\.json$/, ''), title: speechFile! }]
                  : list.map((v) => ({ id: v, label: v, title: v }))),
              ]}
              onChange={setVoice}
            />
          </div>
        ) : (
          <div className="ca-rename__field"><span>{t('audio.duration')}</span>
            <Chips value={sfxSeconds} options={SFX_SECONDS.map((s) => [s, `${s}s`] as const)} onPick={setSfxSeconds} />
          </div>
        )}
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" disabled={tab === 'music' ? !!musicMissing({ prompt, lyrics }) : !prompt.trim()} onClick={run}>{t('common.generate')}</button>
        </div>
      </div>
    </Modal>
  )
}
