import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useValue, type Editor, type TLShapeId } from 'tldraw'

import { agentModeAtom, DOC_ACCEPT, docsAtom, draftAtom, eachLine, eachRuns, extraRefsAtom, generateDirect, isRefShape, kitsAtom, refKindOf, sendToAgent, srcOf, uploadRefs, type AgentMode, type RefShape } from '../agent'
import { EachButton, EachRole, useEach } from './EachToggle'
import { RefFrameButton } from './RefFrameButton'
import { placeAsset } from '../assets'
import { botEnabledAtom, loadProviders, messagesAtom, providerLabel, providersStateAtom } from '../bot'
import { errorText } from '../jobs'
import { KIND_LABELS, libraryAtom } from '../library'
import type { AudioShape } from '../shapes/EmbedShapes'
import { loadSkills, saveSkill, skillAtom, type Skill } from '../skills'
import { AssetGrid } from './AssetPicker'
import { schedulesOpenAtom } from '../schedules'
import { AgentExtras, AgentItems, shortLabel, useCurrentAgent } from './AgentPicker'
import { AgentLogo } from './agentLogos'
import { Icons } from './icons'
import { ModelPrefs } from './ModelPrefs'
import { DirectPills } from './DirectPills'
import { ComposerSlot, useSlot } from './ComposerSlot'
import { SkillForm, skillsOpenAtom } from './SkillsDialog'
import { Popover } from './Popover'
import { t } from '../i18n'
import { uuid } from '../id'
import { isEnter } from './keys'

const MODES: [AgentMode, string, keyof typeof Icons][] = [['agent', 'Agent', 'agent'], ['image', t('composer.image'), 'genImage'], ['video', t('common.video'), 'genVideo']]
const REVIEW_PROMPT = t('composer.canvasReviewUseGetCanvas')
const SKILL_PROMPT = t('composer.turnTheApproachCompletedIn')

export const FILE_ACCEPT = `image/*,video/*,audio/*,${DOC_ACCEPT}`

function imageName(editor: Editor, s: RefShape) {
  if (refKindOf(s) === 'audio') return (s as AudioShape).props.name || t('composer.audio')
  const v = s as Exclude<RefShape, AudioShape>
  const asset = v.props.assetId ? editor.getAsset(v.props.assetId) : null
  return (asset?.type === v.type && asset.props.name) || (v.type === 'video' ? t('common.video') : t('common.image'))
}

function RefThumb({ editor, s }: { editor: Editor; s: RefShape }) {
  const kind = refKindOf(s)
  if (kind === 'audio') return <span className="ca-icon">{Icons.music}</span>
  return kind === 'video' ? <video src={srcOf(editor, s) ?? ''} muted preload="metadata" /> : <img src={srcOf(editor, s) ?? ''} alt="" />
}

/** #250: how far the composer bar has to fold so +, voice and send stay inside it.
 *  0 full · 1 settings drops its tail ("1K · 1:1") · 2 settings icon only · 3 model icon only (the mode button always keeps its text).
 *  The group never squeezes its buttons (no cut-off text); it folds one step at a time until nothing overflows. */
function useFootFit(dep: unknown) {
  const ref = useRef<HTMLDivElement>(null)
  const [fit, setFit] = useState(0)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(Math.round(el.clientWidth)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useLayoutEffect(() => { setFit(0) }, [width, dep])
  useLayoutEffect(() => {
    const mid = ref.current?.querySelector('.ca-composer__mid')
    if (mid && fit < 3 && mid.scrollWidth > mid.clientWidth) setFit(fit + 1)
  })
  return { ref, fit }
}

export function Composer({ editor, busy, onError }: { editor: Editor; busy: boolean; onError: (msg: string) => void }) {
  const started = useValue('chat started', () => messagesAtom.get().length > 0, [])
  const draft = useValue(draftAtom)
  const mode = useValue(agentModeAtom)
  const enabled = useValue(botEnabledAtom)
  const agentOff = mode === 'agent' && enabled === false
  const listLoading = useValue('agent list loading', () => providersStateAtom.get().state === 'loading', [])
  const agentLoading = mode === 'agent' && listLoading  // #294: no sending to an Agent until the list has arrived
  const skill = useValue(skillAtom)
  const extra = useValue(extraRefsAtom)
  const kits = useValue(kitsAtom)
  const library = useValue(libraryAtom)
  const docs = useValue(docsAtom)
  const selected = useValue('selected media', () => editor.getSelectedShapes().filter(isRefShape), [editor])
  const images = useValue('canvas media', () => editor.getCurrentPageShapes().filter(isRefShape), [editor])
  const [menu, setMenu] = useState<'plus' | 'skills' | 'assets' | 'mode' | 'create' | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const file = useRef<HTMLInputElement>(null)
  const [hidden, setHidden] = useState<TLShapeId[]>([])
  const [drop, setDrop] = useState(false)
  const each = useEach()
  // #250 v2: one action slot on the right. Empty input → voice (waveform); text or an attached image → send (↑).
  // Whitespace-only counts as empty. The slot does not flip while an IME is composing, and stays on voice while recording.
  const [composing, setComposing] = useState(false)
  const content = !!draft.trim()
  const foot = useFootFit(`${mode}|${draft.length > 0}`)

  const shown = selected.filter((s) => !hidden.includes(s.id))
  const refs = [...shown, ...extra.map((id) => editor.getShape(id)).filter((s): s is RefShape => !!s && isRefShape(s) && !shown.some((x) => x.id === s.id))]
  const slash = /^\/(\S*)$/.exec(draft)
  const at = /(?:^|\s)@(\S*)$/.exec(draft)

  useEffect(() => {
    if (menu === 'skills' || slash) void loadSkills().then(setSkills)
  }, [menu, !!slash])

  useEffect(() => {
    setHidden((h) => h.filter((id) => selected.some((s) => s.id === id)))
  }, [selected])

  const addRef = (id: TLShapeId) => {
    setHidden((h) => h.filter((x) => x !== id))
    extraRefsAtom.set([...extraRefsAtom.get().filter((x) => x !== id), id])
  }
  const removeRef = (id: TLShapeId) => {
    extraRefsAtom.set(extraRefsAtom.get().filter((x) => x !== id))
    if (selected.some((s) => s.id === id)) setHidden((h) => [...h, id])
  }
  const useSkill = (s: Skill) => { skillAtom.set(s); setMenu(null); if (slash) draftAtom.set('') }

  const fail = (e: unknown) => onError(errorText(e))
  const upload = (files: FileList | null) => uploadRefs(editor, Array.from(files ?? [])).catch(fail)
  const imageFiles = (list: DataTransfer) => Array.from(list.files)
  const { showSend, setVoice } = useSlot(content || refs.length > 0, composing)
  const send = () => {
    const text = draft.trim()
    if ((!text && !refs.length) || agentOff || agentLoading) return  // #268: an image with no text counts as content
    draftAtom.set('')
    extraRefsAtom.set([])
    kitsAtom.set([])
    if (mode === 'agent') {
      skillAtom.set(null)
      docsAtom.set([])
    }
    const targets = refs.length > 1 ? each.targets(refs) : []
    each.reset()
    void (mode === 'agent'
      ? sendToAgent(editor, text, refs, skill, kits, docs, targets.length ? eachLine(refs, targets) : '')
      : generateDirect(editor, text, eachRuns(refs, targets, () => text), mode === 'video', onError)).catch(fail)
  }

  const filtered = slash ? skills.filter((s) => s.name.includes(slash[1])) : skills
  const mentions = at ? images.filter((s) => imageName(editor, s).toLowerCase().includes(at[1].toLowerCase())).slice(0, 8) : []
  const kitMentions = at ? library.filter((k) => k.name.toLowerCase().includes(at[1].toLowerCase()) && !kits.some((x) => x.id === k.id)).slice(0, 8) : []
  const clearAt = () => draftAtom.set(draft.slice(0, at!.index) + (at!.index ? ' ' : ''))
  const modeInfo = MODES.find(([m]) => m === mode)!
  const agent = useCurrentAgent()

  return (
    <div
      className="ca-composer"
      data-drop={drop || undefined}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrop(true) } }}
      onDragLeave={() => setDrop(false)}
      onDrop={(e) => { setDrop(false); const files = imageFiles(e.dataTransfer); if (files.length) { e.preventDefault(); void uploadRefs(editor, files).catch(fail) } }}
    >
      {(slash && filtered.length > 0) && (
        <div className="ca-menu ca-composer__suggest">
          {filtered.slice(0, 8).map((s) => (
            <button key={s.id} type="button" className="ca-menu__item" onClick={() => useSkill(s)}>
              <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">{s.name}</span>
            </button>
          ))}
        </div>
      )}
      {(mentions.length > 0 || kitMentions.length > 0) && (
        <div className="ca-menu ca-composer__suggest">
          {kitMentions.map((k) => (
            <button key={k.id} type="button" className="ca-menu__item" onClick={() => { kitsAtom.set([...kits, k]); clearAt() }}>
              {k.images[0] ? <img className="ca-composer__mini" src={k.images[0]} alt="" /> : <span className="ca-icon">{Icons.assets}</span>}
              <span className="ca-menu__grow">{k.name}</span><span className="ca-menu__key">{KIND_LABELS[k.kind]}</span>
            </button>
          ))}
          {mentions.map((s) => (
            <button key={s.id} type="button" className="ca-menu__item" onClick={() => { addRef(s.id); clearAt() }}>
              {s.type === 'image' ? <img className="ca-composer__mini" src={srcOf(editor, s) ?? ''} alt="" /> : <span className="ca-icon">{s.type === 'video' ? Icons.video : Icons.music}</span>}<span className="ca-menu__grow">{imageName(editor, s)}</span>
            </button>
          ))}
        </div>
      )}
      {(refs.length > 0 || skill || kits.length > 0 || (mode === 'agent' && docs.length > 0)) && (
        <div className="ca-composer__chips">
          {kits.map((k) => (
            <span key={k.id} className="ca-chip">
              <span className="ca-icon">{Icons.assets}</span>{k.name}
              <button type="button" title={t('common.remove')} onClick={() => kitsAtom.set(kits.filter((x) => x.id !== k.id))}>{Icons.close}</button>
            </span>
          ))}
          {skill && (
            <span className="ca-chip">
              <span className="ca-icon">{Icons.skill}</span>{skill.name}
              <button type="button" title={t('common.remove')} onClick={() => skillAtom.set(null)}>{Icons.close}</button>
            </span>
          )}
          {mode === 'agent' && docs.map((d) => (
            <span key={d.src} className="ca-chip" title={d.name}>
              <span className="ca-icon">{Icons.page}</span><span className="ca-chip__name">{d.name}</span>
              <button type="button" title={t('common.remove')} onClick={() => docsAtom.set(docs.filter((x) => x.src !== d.src))}>{Icons.close}</button>
            </span>
          ))}
          {refs.map((r) => (
            <span key={r.id} className="ca-chip ca-chip--image" data-audio={refKindOf(r) === 'audio' || undefined} title={imageName(editor, r)}>
              <RefThumb editor={editor} s={r} />
              <button type="button" title={t('common.remove')} onClick={() => removeRef(r.id)}>{Icons.close}</button>
              {each.on && refs.length > 1 && <EachRole shared={each.isShared(r.id)} onToggle={() => each.toggleShared(r.id)} />}
            </span>
          ))}
        </div>
      )}
      <textarea
        className="ca-composer__input"
        value={draft}
        placeholder={t('composer.describeYourDesignNeedsFor')}
        onChange={(e) => draftAtom.set(e.target.value)}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={() => setComposing(false)}
        onPaste={(e) => { const files = imageFiles(e.clipboardData); if (!files.length) return; e.preventDefault(); e.stopPropagation(); void uploadRefs(editor, files).catch(fail) }}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (isEnter(e) && !e.shiftKey && !slash && !mentions.length && !kitMentions.length) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div ref={foot.ref} className="ca-composer__foot" data-fit={foot.fit || undefined}>
        <input ref={file} type="file" accept={FILE_ACCEPT} multiple hidden onChange={(e) => { void upload(e.target.files); e.target.value = '' }} />
        <Popover
          open={menu === 'plus' || menu === 'skills' || menu === 'assets' || menu === 'create'}
          onOpenChange={(o) => setMenu(o ? 'plus' : null)}
          side="top"
          contentKey={menu ?? ''}
          trigger={({ open, toggle }) => (
            <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.add')} data-open={open || undefined} onClick={toggle}>
              <span className="ca-icon">{Icons.plus}</span>
            </button>
          )}
        >
          {menu === 'plus' && (
            <div className="ca-menu">
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); file.current?.click() }}>
                <span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{t('common.uploadFile')}</span>
              </button>
              <div className="ca-menu__sep" />
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); void sendToAgent(editor, REVIEW_PROMPT, [], null).catch(fail) }}>
                <span className="ca-icon">{Icons.search}</span><span className="ca-menu__grow">{t('composer.canvasReview')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); schedulesOpenAtom.set(draft.trim() ? { prompt: draft.trim() } : {}) }}>
                <span className="ca-icon">{Icons.bell}</span><span className="ca-menu__grow">{t('composer.scheduledTask')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => setMenu('skills')}>
                <span className="ca-icon">{Icons.skill}</span><span className="ca-menu__grow">Skill</span><span className="ca-icon">{Icons.next}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => setMenu('assets')}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.addAssets')}</span><span className="ca-icon">{Icons.next}</span>
              </button>
            </div>
          )}
          {menu === 'skills' && (
            <div className="ca-menu ca-skills">
              <button type="button" className="ca-menu__item" onClick={() => setMenu('create')}>
                <span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('composer.skillCreator')}</span>
              </button>
              <button type="button" className="ca-menu__item" disabled={!started} onClick={() => { setMenu(null); void sendToAgent(editor, SKILL_PROMPT, [], null).catch(fail) }}>
                <span className="ca-icon">{Icons.agent}</span><span className="ca-menu__grow">{t('composer.createSkillFromThisChat')}</span>
              </button>
              <button type="button" className="ca-menu__item" onClick={() => { setMenu(null); skillsOpenAtom.set(true) }}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('composer.manageSkills')}</span>
              </button>
              <div className="ca-menu__sep" />
              {skills.map((s) => (
                <button key={s.id} type="button" className="ca-menu__item" title={s.instructions} onClick={() => useSkill(s)}>
                  <span className="ca-menu__grow">{s.name}</span>
                  {s.custom && <span className="ca-menu__key">{t('composer.personal')}</span>}
                </button>
              ))}
            </div>
          )}
          {menu === 'assets' && (
            <div className="ca-menu ca-assets-pop">
              <AssetGrid only="image" onPick={(item) => { setMenu(null); void placeAsset(editor, item).then((id) => id && addRef(id)) }} />
            </div>
          )}
          {menu === 'create' && (
            <div className="ca-menu ca-skilled">
              <div className="ca-gen__title">{t('composer.skillCreator')}</div>
              <SkillForm
                initial={{ id: uuid().slice(0, 8), name: '', instructions: '', custom: true }}
                onDone={(s) => {
                  setMenu(null)
                  if (!s) return
                  void saveSkill(s).then(() => skillAtom.set(s)).catch((e) => onError(String(e)))
                }}
              />
            </div>
          )}
        </Popover>
        {/* #250: mode / settings / model share one shrinkable group, so +, voice and send always stay inside the bar */}
        <div className="ca-composer__mid">
        <Popover
          open={menu === 'mode'}
          onOpenChange={(o) => { setMenu(o ? 'mode' : null); if (o) void loadProviders().catch(fail) }}
          side="top"
          within=".ca-composer"
          trigger={({ open, toggle }) => (
            <button type="button" className="ca-bar__btn ca-composer__mode" title={mode === 'agent' && agent ? providerLabel(agent) : modeInfo[1]} data-agent={mode === 'agent' && agent ? agent.id : undefined} data-open={open || undefined} onClick={toggle}>
              {mode === 'agent' && agent ? <><AgentLogo id={agent.id} /><span className="ca-menu__grow">{shortLabel(agent)}</span></> : <><span className="ca-icon">{Icons[modeInfo[2]]}</span><span className="ca-composer__modetext">{modeInfo[1]}</span></>}<span className="ca-icon">{Icons.chevron}</span>
            </button>
          )}
        >
          <div className="ca-menu ca-agentpick">
            <AgentItems onError={onError} current={mode === 'agent'} close={() => setMenu(null)} onChosen={() => agentModeAtom.set('agent')} />
            <div className="ca-menu__sep" />
            {MODES.filter(([m]) => m !== 'agent').map(([m, label, icon]) => (
              <button key={m} type="button" className="ca-menu__item" onClick={() => { agentModeAtom.set(m); setMenu(null) }}>
                <span className="ca-icon">{Icons[icon]}</span><span className="ca-menu__grow">{label}</span>
                {m === mode && <span className="ca-icon">{Icons.check}</span>}
              </button>
            ))}
            {mode === 'agent' && <><div className="ca-menu__sep" /><AgentExtras onError={onError} close={() => setMenu(null)} /></>}
          </div>
        </Popover>
        {mode !== 'agent' && <DirectPills video={mode === 'video'} />}
        </div>
        {/* #268: right group = reference / preferences (agent) or settings, next to voice/send */}
        <div className="ca-gen__spacer" />
        {refs.length > 1 && <EachButton compact on={each.on} onChange={each.setOn} />}
        {mode === 'agent' && !agentOff && <RefFrameButton editor={editor} />}
        {mode === 'agent' && <ModelPrefs onError={onError} />}
        <ComposerSlot showSend={showSend} setVoice={setVoice} canSend={(content || refs.length > 0) && !agentOff && !agentLoading} onSend={send}
          title={agentLoading ? t('bot.agentListLoading') : busy && mode === 'agent' ? t('composer.sendQueuedAfterTheCurrent') : t('composer.send')} onError={onError}
          onText={(t) => draftAtom.set(`${draftAtom.get()}${draftAtom.get() ? ' ' : ''}${t}`)} />
      </div>
    </div>
  )
}
