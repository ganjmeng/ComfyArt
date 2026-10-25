import { useEffect, useRef, useState } from 'react'

import type { AgentMode } from '../agent'
import { botEnabledAtom, loadProviders, providerLabel } from '../bot'
import { thumbUrl, uploadImage, viewUrl } from '../comfy'
import { t } from '../i18n'
import { errorText } from '../jobs'
import { newProject, openView, startProject, type ProjectEntry } from '../projects'
import { loadSkills, type Skill } from '../skills'
import { Icons } from '../ui/icons'
import { NoKeyNotice } from '../ui/NoKeyNotice'
import { refreshKeyStatus } from '../wavespeedKey'
import { isEnter } from '../ui/keys'
import { Popover } from '../ui/Popover'
import { shortLabel, useCurrentAgent } from '../ui/AgentPicker'
import { AgentLogo } from '../ui/agentLogos'
import { ComposerSlot, useSlot } from '../ui/ComposerSlot'
import { DirectPills } from '../ui/DirectPills'
import { ModelPrefs } from '../ui/ModelPrefs'
import { loadModels } from '../models'
import { loadEntries, ProjectCard } from './Projects'

const RECENT = 5
const ROTATE_MS = 4000
const EXAMPLES = [t('home.example1'), t('home.example2'), t('home.example3'), t('home.example4')]
const QUICK: [keyof typeof Icons, string, string][] = [
  ['grid', t('home.quickSocial'), t('home.quickSocialPrompt')],
  ['assets', t('home.quickEcommerce'), t('home.quickEcommercePrompt')],
  ['palette', t('home.quickBrand'), t('home.quickBrandPrompt')],
  ['effects', t('home.quickCreative'), t('home.quickCreativePrompt')],
  ['page', t('home.quickWebsite'), t('home.quickWebsitePrompt')],
]
const MODES: [AgentMode, string, keyof typeof Icons][] = [['agent', 'Agent', 'agent'], ['image', t('composer.image'), 'genImage'], ['video', t('common.video'), 'genVideo']]

export function Home() {
  const [text, setText] = useState('')
  const [refs, setRefs] = useState<string[]>([])
  const [mode, setMode] = useState<AgentMode>('agent')
  const [agent, setAgent] = useState<boolean | null>(null)
  const [modeMenu, setModeMenu] = useState(false)
  const [example, setExample] = useState(0)
  const [recent, setRecent] = useState<ProjectEntry[] | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [drop, setDrop] = useState(false)
  const [composing, setComposing] = useState(false)
  const [sending, setSending] = useState(false)
  const current = useCurrentAgent()  // #278: same agent the canvas mode button shows
  const hasContent = !!text.trim() || refs.length > 0  // #276: an image with no text counts as content
  const { showSend, setVoice } = useSlot(hasContent, composing)
  const input = useRef<HTMLTextAreaElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const breakdown = useRef<HTMLInputElement>(null)

  useEffect(() => {
    input.current?.focus()
    void refreshKeyStatus()
    void loadModels().catch((e) => setError(errorText(e)))  // #287: same model list / saved picks as the canvas
    void loadProviders().then(() => {
      const on = !!botEnabledAtom.get()
      setAgent(on)
      if (!on) setMode('image')
    }, () => { setAgent(false); setMode('image') })
    void loadEntries(RECENT).then(setRecent)
    void loadSkills().then(setSkills)
    const timer = window.setInterval(() => setExample((i) => (i + 1) % EXAMPLES.length), ROTATE_MS)
    return () => clearInterval(timer)
  }, [])

  // #278: keep the draft until the new project is created; on failure it stays and an error shows
  const send = async () => {
    if (!hasContent || uploading || sending) return
    setSending(true)
    setError('')
    try {
      await startProject({ ask: text.trim(), mode, ref: refs })  // #287: model / settings live in the shared saved store
      setText('')
      setRefs([])
    } catch (e) {
      setError(errorText(e))
    } finally {
      setSending(false)
    }
  }
  const upload = async (files: FileList | null) => {
    setUploading(true)
    try {
      for (const f of Array.from(files ?? []).filter((x) => x.type.startsWith('image/'))) {
        const src = viewUrl(await uploadImage(f, f.name))
        setRefs((r) => (r.includes(src) ? r : [...r, src]))
      }
    } catch (e) {
      setError(errorText(e))
    } finally {
      setUploading(false)
    }
  }
  const breakDown = async (f: File | undefined) => {
    if (!f) return
    setUploading(true)
    try {
      newProject({ ref: viewUrl(await uploadImage(f, f.name)), tool: 'elements' })
    } catch (e) {
      setError(errorText(e))
      setUploading(false)
    }
  }
  const modes = MODES.filter(([m]) => agent || m !== 'agent')
  const modeInfo = MODES.find(([m]) => m === mode)!

  return (
    <div className="ca-landing">
      <h1 className="ca-landing__title">{t('home.whatToDesign')}</h1>
      {agent && <NoKeyNotice className="ca-landing__notice" />}
      <div
        className="ca-landing__box"
        data-drop={drop || undefined}
        onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrop(true) } }}
        onDragLeave={() => setDrop(false)}
        onDrop={(e) => { e.preventDefault(); setDrop(false); void upload(e.dataTransfer.files) }}
      >
        {refs.length > 0 && (
          <div className="ca-landing__refs">
            {refs.map((src) => (
              <span key={src} className="ca-landing__ref">
                <img src={thumbUrl(src, 128)} alt="" />
                <button type="button" title={t('common.remove')} onClick={() => setRefs(refs.filter((x) => x !== src))}>{Icons.close}</button>
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={input}
          className="ca-landing__input"
          value={text}
          placeholder={EXAMPLES[example]}
          onChange={(e) => setText(e.target.value)}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          onKeyDown={(e) => {
            if (e.key === 'Tab' && !text) { e.preventDefault(); setText(EXAMPLES[example]) }
            if (isEnter(e) && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() }
          }}
        />
        <div className="ca-landing__foot">
          <button type="button" className="ca-rail__btn" title={t('home.addImage')} onClick={() => file.current?.click()}><span className="ca-icon">{Icons.plus}</span></button>
          <Popover open={modeMenu} onOpenChange={setModeMenu} trigger={({ open, toggle }) => (
            <button type="button" className="ca-landing__mode" title={mode === 'agent' && current ? providerLabel(current) : modeInfo[1]} data-agent={mode === 'agent' && current ? current.id : undefined} data-open={open || undefined} onClick={toggle}>
              {mode === 'agent' && current ? <><AgentLogo id={current.id} /><span className="ca-landing__modetext">{shortLabel(current)}</span></> : <><span className="ca-icon">{Icons[modeInfo[2]]}</span><span className="ca-landing__modetext">{modeInfo[1]}</span></>}<span className="ca-icon">{Icons.chevron}</span>
            </button>
          )}>
            <div className="ca-menu">
              {modes.map(([m, label, icon]) => (
                <button key={m} type="button" className="ca-menu__item" onClick={() => { setMode(m); setModeMenu(false) }}>
                  <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                  {m === mode && <span className="ca-icon">{Icons.check}</span>}
                </button>
              ))}
            </div>
          </Popover>
          <div className="ca-landing__spacer" />
          {/* #287: same right group as the canvas (#272): model → settings → voice/send; agent mode shows only prefs (no Ref: home has no canvas) */}
          {mode !== 'agent' && <DirectPills video={mode === 'video'} within=".ca-landing__box" spacer={false} onError={setError} />}
          {mode === 'agent' && agent && <ModelPrefs onError={setError} within=".ca-landing__box" />}
          <ComposerSlot showSend={showSend} setVoice={setVoice} canSend={hasContent && !uploading && !sending} onSend={() => void send()} onError={setError}
            onText={(v) => setText((cur) => `${cur}${cur ? ' ' : ''}${v}`)} />
        </div>
        <input ref={file} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(e.target.files); e.target.value = '' }} />
      </div>
      {error && <div className="ca-landing__error" onClick={() => setError('')}>{error}</div>}
      <div className="ca-landing__quick">
        <span className="ca-landing__hint">{t('home.letAgentHelp')}</span>
        {QUICK.map(([icon, label, prompt]) => (
          <button key={label} type="button" className="ca-landing__chip" onClick={() => { setText(prompt); input.current?.focus() }}>
            <span className="ca-icon">{Icons[icon]}</span>{label}
          </button>
        ))}
        <button type="button" className="ca-landing__chip" disabled={uploading} title={t('home.breakdownHint')} onClick={() => breakdown.current?.click()}>
          <span className="ca-icon">{Icons.layers}</span>{t('home.breakdown')}
        </button>
        <input ref={breakdown} type="file" accept="image/*" hidden onChange={(e) => { void breakDown(e.target.files?.[0]); e.target.value = '' }} />
      </div>

      <section className="ca-landing__section">
        <div className="ca-landing__head">
          <h2>{t('home.recentProjects')}</h2>
          <button type="button" className="ca-landing__link" onClick={() => openView('projects')}>{t('home.viewAll')}</button>
        </div>
        {recent?.length === 0 && <div className="ca-projects__empty">{t('home.noProjectsYet')}</div>}
        <div className="ca-projects__grid">
          {recent?.map((e) => <ProjectCard key={e.id} entry={e} onChanged={() => void loadEntries(RECENT).then(setRecent)} />)}
        </div>
      </section>

      <section className="ca-landing__section">
        <div className="ca-landing__head"><h2>{t('home.startFromSkill')}</h2></div>
        <div className="ca-skillgrid">
          {skills.map((s) => {
            const cover = Object.values(s.images ?? {})[0]
            return (
              <button key={s.id} type="button" className="ca-skillcard" onClick={() => newProject({ skill: s.id })}>
                <span className="ca-skillcard__icon">{cover ? <img src={thumbUrl(cover, 128)} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}</span>
                <span className="ca-skillcard__name">{s.name}</span>
                <span className="ca-model__tag">{s.custom ? t('home.mySkill') : t('home.builtIn')}</span>
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
