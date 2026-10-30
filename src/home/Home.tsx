import { useEffect, useRef, useState } from 'react'

import type { AgentMode } from '../agent'
import { botEnabledAtom, loadProviders, loadSettings, providerLabel } from '../bot'
import { thumbUrl, uploadImage, viewUrl } from '../comfy'
import { t } from '../i18n'
import { errorText } from '../jobs'
import { newProject, openView, startProject, type ProjectEntry } from '../projects'
import { showMemoryToast } from '../memory'
import { HOME_CREATOR_CHIP_KEY, importLanding, loadSkills, type Skill } from '../skills'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { openSkillEditor } from '../ui/SkillsDialog'
import { Icons } from '../ui/icons'
import { NoKeyNotice } from '../ui/NoKeyNotice'
import { keyMissing, keySettingsOpenAtom, keyStatusAtom, refreshKeyStatus } from '../wavespeedKey'
import { isEnter } from '../ui/keys'
import { Popover } from '../ui/Popover'
import { AgentExtras, AgentItems, shortLabel, useCurrentAgent } from '../ui/AgentPicker'
import { AgentLogo } from '../ui/agentLogos'
import { ComposerSlot, useSlot } from '../ui/ComposerSlot'
import { MODE_OPTIONS, modeOf } from '../ui/modeOptions'
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
  // #491: home + menu (+ → 技能 → 创建技能); the creator chip stays on the home box until send
  const [plus, setPlus] = useState<null | 'plus' | 'skills' | 'skillsMore'>(null)
  const [creator, setCreator] = useState(false)
  const [picked, setPicked] = useState<Skill | null>(null)  // #491: skill chip from the + → 技能 panel; only send leaves home
  const [importing, setImporting] = useState(false)
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
    // #315: load settings with providers so AgentExtras Model matches canvas (shared bot-model-*)
    void Promise.all([loadProviders(), loadSettings()]).then(() => {
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
    if (creator && !text.trim()) { input.current?.focus(); return }
    // #305: guide once; keep the ask in the box when Key is missing
    let key = keyStatusAtom.get()
    if (!key) key = await refreshKeyStatus()
    if (keyMissing(key)) { keySettingsOpenAtom.set(true); return }
    setSending(true)
    setError('')
    try {
      // #491 entry A: only the send leaves home; the new project opens in full-screen chat with the creator prefill
      if (picked) await startProject({ skill: picked.id, ask: text.trim(), mode, ref: refs })
      else if (creator) await startProject({ createSkill: '1', ask: text.trim(), ref: refs })
      else await startProject({ ask: text.trim(), mode, ref: refs })  // #287: model / settings live in the shared saved store
      setText('')
      setRefs([])
      setCreator(false)
      setPicked(null)
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
  const modeInfo = modeOf(mode)

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
        {creator && (
          <div className="ca-landing__refs">
            <span className="ca-chip ca-chip--creator" data-testid="home-skill-creator-chip">
              <span className="ca-icon">{Icons.sparkles}</span>{t(HOME_CREATOR_CHIP_KEY)}
              <button type="button" title={t('common.remove')} onClick={() => setCreator(false)}>{Icons.close}</button>
            </span>
          </div>
        )}
        {picked && (
          <div className="ca-landing__refs">
            <span className="ca-chip ca-chip--skill" data-testid="home-skill-chip" title={picked.name}>
              <span className="ca-icon">{Icons.skill}</span><span className="ca-chip__name">{picked.name}</span>
              <button type="button" title={t('common.remove')} onClick={() => setPicked(null)}>{Icons.close}</button>
            </span>
          </div>
        )}
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
          placeholder={creator ? t('composer.skillCreatorHint') : EXAMPLES[example]}
          onChange={(e) => setText(e.target.value)}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          onKeyDown={(e) => {
            if (e.key === 'Tab' && !text) { e.preventDefault(); setText(EXAMPLES[example]) }
            if (isEnter(e) && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() }
          }}
        />
        <div className="ca-landing__foot">
          <Popover
            open={plus !== null}
            onOpenChange={(o) => setPlus(o ? 'plus' : null)}
            side="bottom"
            align="start"
            within=".ca-landing__box"
            viewportCap
            contentKey={plus ?? ''}
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-landing__add" data-testid="home-plus" title={t('home.plusMenu')} data-open={open || undefined} onClick={toggle}><span className="ca-icon">{Icons.plus}</span></button>
            )}
          >
            {plus === 'plus' && (
              <div className="ca-menu" data-testid="home-plus-menu">
                <button type="button" className="ca-menu__item" onClick={() => { setPlus(null); file.current?.click() }}>
                  <span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('home.addImage')}</span>
                </button>
                <button type="button" className="ca-menu__item" data-testid="home-plus-skills" onClick={() => setPlus('skills')}>
                  <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{t('home.skillsMenu')}</span><span className="ca-icon">{Icons.next}</span>
                </button>
              </div>
            )}
            {plus === 'skills' && (
              <div className="ca-menu ca-skills" data-testid="home-skills-menu">
                <div className="ca-menu__head">
                  <span className="ca-menu__grow">{t('home.skillsMenu')}</span>
                  <button type="button" className="ca-bar__btn ca-bar__btn--icon" data-testid="home-skills-more" title={t('home.skillsMenuMore')} onClick={() => setPlus('skillsMore')}>
                    <span className="ca-icon">{Icons.squarePlus}</span>
                  </button>
                </div>
                {skills.map((s) => (
                  <button key={s.id} type="button" className="ca-menu__item" title={s.instructions} data-testid="home-skill-row" onClick={() => { setPlus(null); setCreator(false); setPicked(s); input.current?.focus() }}>
                    <span className="ca-menu__grow">{s.name}</span>
                    {s.custom && <span className="ca-menu__key">{t('composer.personal')}</span>}
                  </button>
                ))}
              </div>
            )}
            {plus === 'skillsMore' && (
              <div className="ca-menu" data-testid="home-skills-more-menu">
                {/* #491: stays on home — only the chip is added; nothing navigates or sends here */}
                <button type="button" className="ca-menu__item" data-testid="home-create-skill" onClick={() => { setPlus(null); setPicked(null); setCreator(true); setMode('agent'); input.current?.focus() }}>
                  <span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('home.createSkill')}</span>
                </button>
                <button type="button" className="ca-menu__item" disabled>
                  <span className="ca-icon">{Icons.agent}</span><span className="ca-menu__grow">{t('home.createSkillFromChat')}</span>
                </button>
                <button type="button" className="ca-menu__item" data-testid="home-import-skill" onClick={() => { setPlus(null); setImporting(true) }}>
                  <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('home.importSkill')}</span>
                </button>
              </div>
            )}
          </Popover>
          <Popover
            open={modeMenu}
            onOpenChange={(o) => { setModeMenu(o); if (o) void Promise.all([loadProviders(), loadSettings()]).catch((e) => setError(errorText(e))) }}
            side="bottom"
            align="start"
            within=".ca-landing__box"
            viewportCap
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-landing__mode" title={mode === 'agent' && current ? providerLabel(current) : modeInfo[1]} data-agent={mode === 'agent' && current ? current.id : undefined} data-open={open || undefined} onClick={toggle}>
                {/* Ashley: same as canvas — agent pill = shortLabel (ComfyArt); image/video = mode name */}
                {mode === 'agent' && current ? <><AgentLogo id={current.id} /><span className="ca-landing__modetext">{shortLabel(current)}</span></> : <><span className="ca-icon">{Icons[modeInfo[2]]}</span><span className="ca-landing__modetext">{modeInfo[1]}</span></>}<span className="ca-icon">{Icons.chevron}</span>
              </button>
            )}
          >
            {/* #306: Home open menu = canvas AgentItems + Image/Video (no lone 「Agent」 mode row) */}
            <div className="ca-menu ca-agentpick">
              {agent && (
                <>
                  <AgentItems onError={setError} current={mode === 'agent'} close={() => setModeMenu(false)} onChosen={() => setMode('agent')} />
                  <div className="ca-menu__sep" />
                </>
              )}
              {MODE_OPTIONS.filter(([m]) => m !== 'agent').map(([m, label, icon]) => (
                <button key={m} type="button" className="ca-menu__item" onClick={() => { setMode(m); setModeMenu(false) }}>
                  <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                  {m === mode && <span className="ca-icon">{Icons.check}</span>}
                </button>
              ))}
              {mode === 'agent' && agent && <><div className="ca-menu__sep" /><AgentExtras onError={setError} close={() => setModeMenu(false)} /></>}
            </div>
          </Popover>
          <div className="ca-landing__spacer" />
          {/* #287: same right group as the canvas (#272): model → settings → voice/send; agent mode shows only prefs (no Ref: home has no canvas) */}
          {mode !== 'agent' && <DirectPills video={mode === 'video'} within=".ca-landing__box" spacer={false} onError={setError} side="bottom" />}
          {mode === 'agent' && agent && <ModelPrefs onError={setError} within=".ca-landing__box" side="bottom" />}
          <ComposerSlot showSend={showSend} setVoice={setVoice} canSend={hasContent && !uploading && !sending} onSend={() => void send()} onError={setError}
            onText={(v) => setText((cur) => `${cur}${cur ? ' ' : ''}${v}`)} />
        </div>
        <input ref={file} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(e.target.files); e.target.value = '' }} />
      </div>
      {importing && (
        <SkillImportDialog
          onClose={() => setImporting(false)}
          onImported={(skill, skipped) => {
            // #491: same landing as the Skills page import (#487)
            setImporting(false)
            const landing = importLanding(skill, skipped)
            openSkillEditor(landing.id)
            if (landing.skipped) showMemoryToast(landing.skipped, 'info')
            void loadSkills().then(setSkills)
          }}
        />
      )}
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
        <div className="ca-landing__head">
          <h2>{t('home.startFromSkill')}</h2>
          <button type="button" className="ca-landing__link" onClick={() => openView('skills')}>{t('home.viewAll')}</button>
        </div>
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
