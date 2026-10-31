import { useEffect, useMemo, useRef, useState } from 'react'

import type { AgentMode } from '../agent'
import { botEnabledAtom, loadProviders, loadSettings, providerLabel } from '../bot'
import { thumbUrl, uploadImage, viewUrl } from '../comfy'
import { t } from '../i18n'
import { errorText } from '../jobs'
import { newProject, openView, startProject } from '../projects'
import { featuredAspect, packFeaturedColumns } from './featuredLayout'
import { toolCover } from './toolCovers'
import { showMemoryToast } from '../memory'
import { HOME_CREATOR_CHIP_KEY, hasSkillDialog, importLanding, loadSkills, skillCover, skillFeaturedCases, type Skill } from '../skills'
import { SkillChip, chipBackspace } from '../ui/SkillChip'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { SkillRunDialog } from '../ui/SkillRunDialog'
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

const ROTATE_MS = 4000
const EXAMPLES = [t('home.example1'), t('home.example2'), t('home.example3'), t('home.example4')]
const QUICK: [keyof typeof Icons, string, string][] = [
  ['grid', t('home.quickSocial'), t('home.quickSocialPrompt')],
  ['assets', t('home.quickEcommerce'), t('home.quickEcommercePrompt')],
  ['palette', t('home.quickBrand'), t('home.quickBrandPrompt')],
  ['effects', t('home.quickCreative'), t('home.quickCreativePrompt')],
  ['page', t('home.quickWebsite'), t('home.quickWebsitePrompt')],
]

/** #537 / #496 / #540: home 「实用工具」— covers = design wash on review-assets (commit-pinned). */
type ToolCard = { id: string; icon: keyof typeof Icons; label: string; accept: string; cover: string }
const HOME_TOOL_CARDS: ToolCard[] = [
  { id: 'cutout', icon: 'cutout', label: t('common.removeBackground'), accept: 'image/*', cover: toolCover('main-5', 'cutout') },
  { id: 'extend', icon: 'extend', label: t('common.extendVideo'), accept: 'video/*', cover: toolCover('main-5', 'extend') },
  { id: 'upscale', icon: 'upscale', label: t('common.upscale'), accept: 'image/*', cover: toolCover('main-5', 'upscale') },
  { id: 'inpaint', icon: 'effects', label: t('home.toolPreciseEdit'), accept: 'image/*', cover: toolCover('main-5', 'inpaint') },
  { id: 'mockup', icon: 'box', label: t('mockup.title'), accept: 'image/*', cover: toolCover('main-5', 'mockup') },
]
/** #540: Lovart「更多」10 (Loomic order) + unique 4. The menu renders icon rows only (Jingmeng ruling);
 *  `cover` is backup data, used only if a tool is pinned (置顶) into the main 16:9 row. */
const MORE_HOME_TOOLS: ToolCard[] = [
  { id: 'quick', icon: 'quick', label: t('common.quickEdit'), accept: 'image/*', cover: toolCover('more-10', 'quick') },
  { id: 'erase', icon: 'erase', label: t('common.eraser'), accept: 'image/*', cover: toolCover('more-10', 'erase') },
  { id: 'crop', icon: 'crop', label: t('imageToolbar.crop'), accept: 'image/*', cover: toolCover('more-10', 'crop') },
  { id: 'expand', icon: 'expand', label: t('common.expand'), accept: 'image/*', cover: toolCover('more-10', 'expand') },
  { id: 'adjust', icon: 'adjust', label: t('common.adjust'), accept: 'image/*', cover: toolCover('more-10', 'adjust') },
  { id: 'text', icon: 'text', label: t('common.editText'), accept: 'image/*', cover: toolCover('more-10', 'text') },
  { id: 'angles', icon: 'angles', label: t('common.multiAngle'), accept: 'image/*', cover: toolCover('more-10', 'angles') },
  { id: 'vectorize', icon: 'polygon', label: t('imageToolbar.vectorize'), accept: 'image/*', cover: toolCover('more-10', 'vectorize') },
  { id: 'move', icon: 'hand', label: t('common.moveObject'), accept: 'image/*', cover: toolCover('more-10', 'move') },
  { id: 'transform', icon: 'rotate', label: t('imageToolbar.flipAndRotate'), accept: 'image/*', cover: toolCover('more-10', 'transform') },
  { id: 'to3d', icon: 'cube', label: t('imageToolbar.imageTo3d'), accept: 'image/*', cover: toolCover('unique-4', 'to3d') },
  { id: 'lipsync', icon: 'mic', label: t('genPanel.lipSync'), accept: 'image/*', cover: toolCover('unique-4', 'lipsync') },
  { id: 'motion', icon: 'video', label: t('genPanel.motionControl'), accept: 'image/*', cover: toolCover('unique-4', 'motion') },
  { id: 'audio', icon: 'music', label: t('audio.generateAudio'), accept: 'audio/*', cover: toolCover('unique-4', 'audio') },
]

export function Home() {
  const [text, setText] = useState('')
  const [refs, setRefs] = useState<string[]>([])
  const [mode, setMode] = useState<AgentMode>('agent')
  const [agent, setAgent] = useState<boolean | null>(null)
  const [modeMenu, setModeMenu] = useState(false)
  const [example, setExample] = useState(0)
  const [skills, setSkills] = useState<Skill[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [drop, setDrop] = useState(false)
  const [composing, setComposing] = useState(false)
  const [sending, setSending] = useState(false)
  // #491: home + menu (+ → 技能 → 创建技能); the creator chip stays on the home box until send
  const [plus, setPlus] = useState<null | 'plus' | 'skills'>(null)
  const [more, setMore] = useState(false)  // #491 design: 创建技能 dropdown anchored under the panel's square-plus; panel stays open
  const [creator, setCreator] = useState(false)
  const [picked, setPicked] = useState<Skill | null>(null)  // #491: skill chip from the + → 技能 panel; only send leaves home
  const [importing, setImporting] = useState(false)
  // #494-3 / #533: home 精选 + 用 Skill 快速开始 open the same SkillRunDialog as the Skills page
  const [running, setRunning] = useState<{ id: string; preset: string | null } | null>(null)
  const [moreTools, setMoreTools] = useState(false)  // #537: 「更多工具」
  const [featuredWidth, setFeaturedWidth] = useState(1200)  // #537: masonry columns
  const featuredRoot = useRef<HTMLElement>(null)
  const toolFile = useRef<HTMLInputElement>(null)
  const pendingTool = useRef<string>('')
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
  /** #537: pick file → upload → new project with tool=; cancel leaves home (no project). Never auto-runs. */
  const pickTool = (tool: ToolCard) => {
    pendingTool.current = tool.id
    const el = toolFile.current
    if (!el) return
    el.value = ''
    el.accept = tool.accept
    el.click()
  }
  const launchTool = async (f: File | undefined) => {
    const tool = pendingTool.current
    pendingTool.current = ''
    if (!f || !tool) return
    setUploading(true)
    setMoreTools(false)
    setError('')
    try {
      newProject({ ref: viewUrl(await uploadImage(f, f.name)), tool })
    } catch (e) {
      setError(errorText(e))
      setUploading(false)
    }
  }
  const modeInfo = modeOf(mode)
  /** #494-3 — Skills-page rule: dialog when inputs[] exist; else main's direct start. Featured passes a preset id. */
  const trySkill = (s: Skill, preset: string | null = null) => (
    hasSkillDialog(s) ? setRunning({ id: s.id, preset }) : newProject({ skill: s.id })
  )
  const featured = skillFeaturedCases(skills)
  // #537: masonry waterfall via Loomic column math; cards from our skill presets only (no third-party feed data)
  const featuredItems = useMemo(
    () => featured.map(({ skill: s, preset: p, image }) => ({
      id: `${s.id}:${p.id}`,
      skill: s,
      preset: p,
      image,
      aspect: featuredAspect(`${s.id}:${p.id}`),
    })),
    [featured],
  )
  const featuredColumns = useMemo(
    () => packFeaturedColumns(featuredItems, featuredWidth),
    [featuredItems, featuredWidth],
  )
  useEffect(() => {
    const el = featuredRoot.current
    if (!el) return
    const update = () => {
      const w = el.getBoundingClientRect().width
      if (w > 0) setFeaturedWidth(w)
    }
    update()
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [featuredItems.length])
  const runSkill = running ? skills.find((s) => s.id === running.id) : undefined

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
            <SkillChip name={t(HOME_CREATOR_CHIP_KEY)} testId="home-skill-creator-chip" />
          </div>
        )}
        {picked && (
          <div className="ca-landing__refs">
            <SkillChip name={picked.name} testId="home-skill-chip" />
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
            if ((picked || creator) && chipBackspace(e)) { e.preventDefault(); setPicked(null); setCreator(false); return }
            if (e.key === 'Tab' && !text) { e.preventDefault(); setText(EXAMPLES[example]) }
            if (isEnter(e) && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() }
          }}
        />
        <div className="ca-landing__foot">
          <Popover
            open={plus !== null}
            onOpenChange={(o) => { setPlus(o ? 'plus' : null); if (!o) setMore(false) }}
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
                  <Popover
                    open={more}
                    onOpenChange={setMore}
                    side="bottom"
                    align="end"
                    within=".ca-skills"
                    contentKey="skillsMore"
                    trigger={({ open, toggle }) => (
                      <button type="button" className="ca-bar__btn ca-bar__btn--icon" data-testid="home-skills-more" title={t('home.skillsMenuMore')} data-open={open || undefined} onClick={toggle}>
                        <span className="ca-icon">{Icons.squarePlus}</span>
                      </button>
                    )}
                  >
                    <div className="ca-menu" data-testid="home-skills-more-menu">
                      {/* #491: stays on home — only the chip is added; nothing navigates or sends here */}
                      <button type="button" className="ca-menu__item" data-testid="home-create-skill" onClick={() => { setMore(false); setPlus(null); setPicked(null); setCreator(true); setMode('agent'); input.current?.focus() }}>
                        <span className="ca-icon">{Icons.circlePlus}</span><span className="ca-menu__grow">{t('home.createSkill')}</span>
                      </button>
                      <button type="button" className="ca-menu__item" disabled>
                        <span className="ca-icon">{Icons.messageSquare}</span><span className="ca-menu__grow">{t('home.createSkillFromChat')}</span>
                      </button>
                      <button type="button" className="ca-menu__item" data-testid="home-import-skill" onClick={() => { setMore(false); setPlus(null); setImporting(true) }}>
                        <span className="ca-icon">{Icons.uploadArrow}</span><span className="ca-menu__grow">{t('home.importSkill')}</span>
                      </button>
                    </div>
                  </Popover>
                </div>
                {skills.map((s) => (
                  <button key={s.id} type="button" className="ca-menu__item" title={s.name} data-testid="home-skill-row" onClick={() => { setPlus(null); setCreator(false); setPicked(s); input.current?.focus() }}>
                    <span className="ca-menu__grow ca-skills__name">{s.name}</span>
                    {s.custom && <span className="ca-menu__key">{t('composer.personal')}</span>}
                  </button>
                ))}
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

      <section className="ca-landing__section ca-landing__tools" data-testid="home-tools">
        <div className="ca-landing__head">
          <h2>{t('home.tools')}</h2>
          <Popover
            open={moreTools}
            onOpenChange={setMoreTools}
            side="bottom"
            align="end"
            trigger={({ open, toggle }) => (
              <button type="button" className="ca-landing__link ca-landing__moretools" data-testid="home-more-tools" data-open={open || undefined} onClick={toggle}>
                {t('home.moreTools')}<span className="ca-icon">{Icons.chevron}</span>
              </button>
            )}
          >
            <div className="ca-menu ca-menu--tools" data-testid="home-more-tools-menu">
              {MORE_HOME_TOOLS.map((tool) => (
                <button key={tool.id} type="button" className="ca-menu__item" data-testid={`home-more-tool-${tool.id}`} disabled={uploading} onClick={() => pickTool(tool)}>
                  <span className="ca-icon" aria-hidden>{Icons[tool.icon]}</span><span className="ca-menu__grow">{tool.label}</span>
                </button>
              ))}
            </div>
          </Popover>
        </div>
        <div className="ca-toolgrid" data-testid="home-tool-grid">
          {HOME_TOOL_CARDS.map((tool) => (
            <button
              key={tool.id}
              type="button"
              className="ca-toolcard"
              data-testid={`home-tool-card-${tool.id}`}
              data-tool={tool.id}
              disabled={uploading}
              onClick={() => pickTool(tool)}
            >
              <span className="ca-toolcard__cover" data-tool={tool.id}>
                <img src={tool.cover} alt="" draggable={false} />
              </span>
              <span className="ca-toolcard__name">{tool.label}</span>
            </button>
          ))}
        </div>
        <input ref={toolFile} type="file" hidden onChange={(e) => { void launchTool(e.target.files?.[0]); e.target.value = '' }} />
      </section>

      <section className="ca-landing__section" data-testid="home-start-skill">
        <div className="ca-landing__head">
          <h2>{t('home.startFromSkill')}</h2>
          <button type="button" className="ca-landing__link" onClick={() => openView('skills')}>{t('home.viewAll')}</button>
        </div>
        <div className="ca-skillgrid" data-testid="home-skill-grid">
          {skills.map((s) => {
            const cover = skillCover(s)
            const src = cover && (cover.own === 'bundled' ? cover.src : thumbUrl(cover.src, 128))
            return (
              <button key={s.id} type="button" className="ca-skillcard" data-testid="home-skill-card" data-skill={s.id}
                onClick={() => trySkill(s)}>
                <span className="ca-skillcard__icon">{src ? <img src={src} alt={s.name} /> : <span className="ca-icon">{Icons.skill}</span>}</span>
                <span className="ca-skillcard__name">{s.name}</span>
                <span className="ca-model__tag">{s.custom ? t('home.mySkill') : t('home.builtIn')}</span>
              </button>
            )
          })}
        </div>
      </section>

      {featuredItems.length > 0 && (
        <section ref={featuredRoot} className="ca-landing__section ca-landing__featured" data-testid="home-featured">
          <div className="ca-landing__head">
            <h2>{t('home.featured')}</h2>
          </div>
          <div className="ca-featured ca-featured--waterfall" data-testid="home-featured-grid">
            {featuredColumns.map((col, ci) => (
              <div key={`col-${ci}`} className="ca-featured__col" data-testid="home-featured-col">
                {col.map(({ id, skill: s, preset: p, image, aspect }) => (
                  <button
                    key={id}
                    type="button"
                    className="ca-featured__card"
                    data-testid="home-featured-card"
                    data-skill={s.id}
                    data-preset={p.id}
                    onClick={() => trySkill(s, p.id)}
                  >
                    <span className="ca-featured__cover" style={{ aspectRatio: aspect }}>
                      <img src={image} alt={s.name} loading="lazy" />
                      <span className="ca-featured__badge">{t('home.skillCase')}</span>
                      <span className="ca-featured__go">{t('skillRun.start')}</span>
                    </span>
                    <span className="ca-featured__name">{s.name}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {runSkill && (
        <SkillRunDialog skill={runSkill} presetId={running?.preset} onClose={() => setRunning(null)} />
      )}
    </div>
  )
}
