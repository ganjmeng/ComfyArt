import { useRef, useState } from 'react'
import { atom, useValue } from 'tldraw'

import { uploadImage, viewUrl } from '../comfy'
import { errorText } from '../jobs'
import { libraryAtom } from '../library'
import { ask, parseJson } from '../llm'
import { loadMemory, MEMORY_CATEGORIES, MemoryConflict, memoryErrorAtom, memoryFocusAtom, MemoryReadError, MemoryWriteError, removeMemory, updateMemory, memoryAtom, memoryLogAtom, remember, toInputs, type MemoryInput } from '../memory'
import { isPdf, uploadPdf } from '../pdf'
import { AbilitiesPanel } from './AbilitiesPanel'
import { ChatComposer, GROUP_ICONS, GROUP_ORDER, MemoryEmpty } from '../home/ArtiMemory'
import { Icons } from './icons'
import { t } from '../i18n'
import { isEnter } from './keys'
import { Modal } from './Modal'
import { confirmAtom } from './Confirm'
import { showMemoryToast } from '../memory'

export const memoryOpenAtom = atom('memory open', false)

const MAX_TEXT = 12000
const PDF_PAGES = 30
const PDF_IMAGES = 6
const EXTRACT_SYSTEM = 'You build a long-term memory of a designer. From the material, keep only lasting facts and preferences that help future design work. Reply with ONE JSON object and nothing else: {"memories": [{"text": "<one fact or preference in Chinese>", "category": "about|taste|work|assets"}]}'

interface Step { category: string; question: string; options: string[]; multi: boolean; free: string; name?: boolean }

const LOG_LABELS = { add: t('memoryDialog.remember'), update: t('memoryDialog.correct'), forget: t('memoryDialog.forget'), skill: t('memoryDialog.learnedSkill') }

function steps(kits: string[]): Step[] {
  return [
    { category: 'about', question: t('memoryDialog.letsGetToKnow'), options: [], multi: false, free: t('memoryDialog.yourNameOrNickname'), name: true },
    { category: 'about', question: t('memoryDialog.whatKindOfCreativeWork'), options: [t('memoryDialog.eCommerce'), t('memoryDialog.brandMarketing'), t('memoryDialog.contentCreation'), t('memoryDialog.illustrationArt')], multi: true, free: t('memoryDialog.aboutPlaceholder') },
    { category: 'work', question: t('memoryDialog.howDoYouPreferTo'), options: [t('memoryDialog.checkTheDirectionWithMe'), t('memoryDialog.giveMeThreeDifferentDirections'), t('memoryDialog.useMyCopyLeaveLayout'), t('memoryDialog.tellMeDirectlyIfYou')], multi: true, free: t('memoryDialog.describeHowYoudLike') },
    { category: 'taste', question: t('memoryDialog.whatVisualStyleDoYou'), options: [t('memoryDialog.iLikeMinimalDesignsWith'), t('memoryDialog.iPreferMutedColorsAvoid'), t('memoryDialog.iPreferAHandDrawn')], multi: true, free: t('memoryDialog.whatYouDislikeMattersMore') },
    { category: 'assets', question: t('memoryDialog.whatAreYourLongTerm'), options: kits.map((k) => t('memoryDialog.useTheBrandKitBy', k)), multi: true, free: t('memoryDialog.explainHowTheseAssetsShould') },
  ]
}

function Onboarding({ onDone }: { onDone: (items: MemoryInput[] | null) => void }) {
  const kits = useValue('kit names', () => libraryAtom.get().filter((x) => x.kind === 'brand').map((x) => x.name), [])
  const list = steps(kits)
  const [index, setIndex] = useState(0)
  const [picked, setPicked] = useState<string[][]>(list.map(() => []))
  const [texts, setTexts] = useState<string[]>(list.map(() => ''))
  const step = list[index]
  const toggle = (o: string) => setPicked((all) => all.map((p, i) => (i !== index ? p : p.includes(o) ? p.filter((x) => x !== o) : [...p, o])))
  const finish = () => onDone(list.flatMap((s, i) => {
    if (s.name) return texts[i].trim() ? [{ text: t('memoryDialog.callMe', texts[i].trim()), category: s.category }] : []
    const chosen = s.category === 'about' && picked[i].length ? [t('memoryDialog.iMainlyDo', picked[i].join(t('common.listSep')))] : picked[i]
    return [...chosen, texts[i].trim()].filter(Boolean).map((text) => ({ text, category: s.category }))
  }))

  return (
    <div className="ca-rename__body">
      <div className="ca-chat__hint">{t('memoryDialog.part', index + 1, list.length, MEMORY_CATEGORIES.find(([id]) => id === step.category)![1])}</div>
      <div className="ca-memory__q">{step.question}</div>
      <div className="ca-panel__chips">
        {step.options.map((o) => <button key={o} type="button" className="ca-panel__chip" data-on={picked[index].includes(o) || undefined} onClick={() => toggle(o)}>{o}</button>)}
      </div>
      <textarea className="ca-panel__prompt ca-panel__prompt--boxed" value={texts[index]} placeholder={step.free} onChange={(e) => setTexts(texts.map((t, i) => (i === index ? e.target.value : t)))} onKeyDown={(e) => e.stopPropagation()} />
      <div className="ca-panel__foot">
        <button type="button" className="ca-panel__secondary" onClick={() => (index ? setIndex(index - 1) : onDone(null))}>{index ? t('memoryDialog.back') : t('common.cancel')}</button>
        {index < list.length - 1
          ? <button type="button" className="ca-panel__primary" onClick={() => setIndex(index + 1)}>{t('memoryDialog.next')}</button>
          : <button type="button" className="ca-panel__primary" onClick={finish}>{t('common.done')}</button>}
      </div>
    </div>
  )
}

export function MemoryDialog({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(memoryOpenAtom)
  const memory = useValue(memoryAtom)
  const log = useValue(memoryLogAtom)
  const loadError = useValue(memoryErrorAtom)
  const [tab, setTab] = useState('memory')
  const [text, setText] = useState('')
  const [adding, setAdding] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [onboarding, setOnboarding] = useState(false)
  const [busy, setBusy] = useState('')
  const file = useRef<HTMLInputElement>(null)
  if (!open) return null
  // #433: opening from 「记忆已更新 ›」 highlights nothing and offers no undo; removal is delete + confirm only
  const close = () => { memoryOpenAtom.set(false); setEditing(null); setAdding(null); setChatOpen(false); setOnboarding(false); memoryFocusAtom.set(null) }
  // store failures already showed 保存失败，请重试 (#381); only other errors go to the panel
  const fail = (e: unknown) => { if (!(e instanceof MemoryWriteError || e instanceof MemoryConflict || e instanceof MemoryReadError)) onError(errorText(e)) }
  const add = (category: string) => {
    if (!text.trim()) return
    void remember([{ text: text.trim(), category }], t('frameToolbar.manual')).catch(fail)
    setText('')
    setAdding(null)
  }
  const importFiles = async (files: FileList | null) => {
    const found: MemoryInput[] = []
    for (const f of Array.from(files ?? [])) {
      setBusy(t('memoryDialog.reading', f.name))
      const pages = isPdf(f) ? await uploadPdf(f, PDF_PAGES) : null
      const text = pages?.map((p) => p.text).join('\n').trim()
      const raw = pages
        ? await ask(t('memoryDialog.extractFromPdf', text ? `\n\n${text.slice(0, MAX_TEXT)}` : ''), EXTRACT_SYSTEM, pages.slice(0, PDF_IMAGES).map((p) => p.src))
        : f.type.startsWith('image/')
        ? await ask(t('memoryDialog.extractMyBackgroundAndCreative'), EXTRACT_SYSTEM, [viewUrl(await uploadImage(f, f.name))])
        : await ask(t('memoryDialog.pullOutTheInformationWorth', (await f.text()).slice(0, MAX_TEXT)), EXTRACT_SYSTEM, [])
      found.push(...toInputs(parseJson(raw)?.memories))
    }
    if (!found.length) throw new Error(t('memoryDialog.couldntExtractAnyLong'))
    await remember(found, t('memoryDialog.import'))
  }
  const label = (id: string) => MEMORY_CATEGORIES.find(([c]) => c === id)?.[1] ?? id

  return (
    <Modal title={onboarding ? t('memoryDialog.tellTheAgentAboutYourself') : t('common.memory')} className="ca-rename ca-memory" onClose={close}>
      {onboarding ? (
        <Onboarding onDone={(items) => { setOnboarding(false); if (items?.length) void remember(items, t('memoryDialog.qa')).catch(fail) }} />
      ) : (
        <div className="ca-rename__body">
          <div className="ca-chat__hint">{t('memoryDialog.theAgentFollowsTheseMemories')}</div>
          {loadError ? <div className="ca-arti-mem__guide" role="alert" data-testid="memory-dialog-error">{t('arti.memory.loadFailed')}{' '}<button type="button" className="ca-arti-mem__retry" onClick={() => void loadMemory()}>{t('arti.memory.retry')}</button></div> : null}
          <div className="ca-style__row">
            <button type="button" className="ca-lib__new" onClick={() => setOnboarding(true)}><span className="ca-icon">{Icons.agent}</span>{t('memoryDialog.tellMeAboutYourself')}</button>
            <button type="button" className="ca-lib__new" disabled={!!busy} onClick={() => file.current?.click()}><span className="ca-icon">{Icons.upload}</span>{busy || t('memoryDialog.importFromFile')}</button>
            <input ref={file} type="file" multiple hidden accept="image/*,.pdf,.txt,.md,.json,.csv" onChange={(e) => { const list = e.target.files; void importFiles(list).catch(fail).finally(() => setBusy('')); e.target.value = '' }} />
          </div>
          <div className="ca-panel__chips">
            <button type="button" className="ca-panel__chip" data-on={tab === 'memory' || undefined} onClick={() => setTab('memory')}>{t('common.memory')}</button>
            <button type="button" className="ca-panel__chip" data-on={tab === 'log' || undefined} onClick={() => setTab('log')}>{t('memoryDialog.evolutionLog')}</button>
            <button type="button" className="ca-panel__chip" data-on={tab === 'abilities' || undefined} onClick={() => setTab('abilities')}>{t('abilities.title')}</button>
          </div>
          {tab === 'abilities' && <AbilitiesPanel onError={onError} />}
          {tab === 'log' && (log.length === 0
            ? <div className="ca-side__empty">{t('memoryDialog.noEvolutionLogYet')}</div>
            : log.slice(0, 200).map((l, i) => (
              <div key={i} className="ca-memory__row ca-memory__log">
                <span className="ca-model__tag">{LOG_LABELS[l.action]}</span>
                <span className="ca-menu__grow">{l.text}</span>
                <span className="ca-chat__hint">{l.source} · {new Date(l.time).toLocaleString()}</span>
              </div>
            )))}
          {tab === 'memory' && !loadError && memory.length === 0 && adding === null && <MemoryEmpty />}
          {tab === 'memory' && !loadError && (memory.length > 0 || adding !== null) && (
            <div className="ca-arti-mem__groups ca-memory__groups" data-testid="memory-dialog-groups">
              {GROUP_ORDER.map((cat) => {
                const items = memory.filter((m) => (m.category ?? 'about') === cat)
                return (
                  <section key={cat} className="ca-arti-mem__group" data-testid={`memory-dialog-group-${cat}`}>
                    <h3 className="ca-arti-mem__grouptitle"><span className="ca-icon">{GROUP_ICONS[cat]}</span>{label(cat)}</h3>
                    <div className="ca-arti-mem__list">
                      {items.map((m) => (
                        <div key={m.id} className="ca-arti-mem__row ca-memory__card" data-testid="memory-dialog-card">
                          <div className="ca-arti-mem__rowbody">
                            {m.label ? <div className="ca-memory__title">{m.label}</div> : null}
                            {editing === m.id ? (
                              <input
                                autoFocus
                                className="ca-panel__input"
                                defaultValue={m.text}
                                onBlur={(e) => { setEditing(null); const v = e.target.value.trim(); if (v && v !== m.text) void updateMemory(m.id, v, t('frameToolbar.manual')).catch(fail) }}
                                onKeyDown={(e) => { e.stopPropagation(); if (isEnter(e)) e.currentTarget.blur() }}
                              />
                            ) : (
                              <div className="ca-arti-mem__text" onDoubleClick={() => setEditing(m.id)}>{m.text}</div>
                            )}
                          </div>
                          <button type="button" className="ca-history__del" title={t('memoryDialog.correctMemory')} onClick={() => setEditing(m.id)}>{Icons.textTool}</button>
                          <button type="button" className="ca-history__del" title={t('common.delete')} data-testid="memory-dialog-delete" onClick={() => confirmAtom.set({ title: t('arti.memory.deleteTitle'), desc: t('arti.memory.deleteDesc', m.text), ok: t('common.delete'), danger: true, run: () => { void removeMemory(m.id, t('frameToolbar.manual')).then((ok) => { if (ok) showMemoryToast(t('arti.memory.deletedToast')) }).catch(fail) } })}>{Icons.trash}</button>
                        </div>
                      ))}
                      {adding === cat ? (
                        <div className="ca-style__row">
                          <input autoFocus className="ca-panel__input" value={text} placeholder={t('memoryDialog.add', label(cat))} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { e.stopPropagation(); if (isEnter(e)) add(cat) }} />
                          <button type="button" className="ca-panel__secondary" onClick={() => { setAdding(null); setText('') }}>{t('common.cancel')}</button>
                          <button type="button" className="ca-panel__primary ca-memory__add" disabled={!text.trim()} onClick={() => add(cat)}>{t('common.add')}</button>
                        </div>
                      ) : items.length === 0 ? (
                        <button type="button" className="ca-arti-mem__addasset ca-memory__addrow" data-testid={`memory-dialog-add-${cat}`} onClick={() => { setAdding(cat); setText('') }}>
                          <span className="ca-icon">{Icons.plus}</span>{t(`memoryDialog.addYour.${cat}`)}
                        </button>
                      ) : null}
                    </div>
                  </section>
                )
              })}
            </div>
          )}
          {tab === 'memory' && (
            <div className="ca-arti-mem__sticky ca-memory__sticky" data-testid="memory-dialog-chat-cta">
              {chatOpen
                ? <ChatComposer onClose={() => setChatOpen(false)} />
                : <button type="button" className="ca-arti-mem__cta" data-testid="memory-dialog-chat-open" onClick={() => setChatOpen(true)}>{t('arti.memory.chatCta')}</button>}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
