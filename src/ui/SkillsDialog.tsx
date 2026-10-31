import { useEffect, useRef, useState } from 'react'
import { atom, useValue } from 'tldraw'

import { errorText } from '../jobs'
import { deleteSkill, importFolder, listVersions, loadSkills, saveSkill, skillAtom, uploadSkillImage, type Skill, type SkillVersion } from '../skills'
import { confirmAtom } from './Confirm'
import { Icons } from './icons'
import { t } from '../i18n'
import { uuid } from '../id'
import { editSkillInChat } from '../skillEdit'
import { Markdown } from './Markdown'
import { Modal } from './Modal'

export const skillsOpenAtom = atom('skills open', false)
/** #462: id of a personal skill to open straight in the Edit dialog (detail page ⋯ / edit entry, #464). */
export const skillEditIdAtom = atom<string | null>('skill edit id', null)

/** Open THE Edit Skill dialog for a personal skill by id — single shared entry for list, detail page and menus. */
export function openSkillEditor(id: string) {
  skillEditIdAtom.set(id)
  skillsOpenAtom.set(true)
}

type View = { kind: 'list' } | { kind: 'edit'; skill: Skill } | { kind: 'history'; skill: Skill; versions: SkillVersion[] | null }

/** #462 SKILL.md file card (file picker + file count + Preview/Code tabs). Shared by the Edit Skill form and, read-only
 *  (no onInstructions / onFiles), by the #494-2 / #464 skill detail page — one component, two places. */
export function SkillFileBox({ instructions, files, open, setOpen, onInstructions, onFiles }: {
  instructions: string; files: Record<string, string>; open: string; setOpen: (path: string) => void
  onInstructions?: (v: string) => void; onFiles?: (next: Record<string, string>) => void
}) {
  const [tab, setTab] = useState<'preview' | 'code'>(instructions.trim() ? 'preview' : 'code')
  const isMain = open === 'SKILL.md' || !(open in files)
  const body = isMain ? instructions : files[open]
  const setBody = (v: string) => (isMain ? onInstructions?.(v) : onFiles?.({ ...files, [open]: v }))
  return (
    <div className="ca-skillform__box" data-testid="skill-instructions">
      <div className="ca-skillform__bar">
        <select className="ca-skillform__file" value={isMain ? 'SKILL.md' : open} onChange={(e) => setOpen(e.target.value)} onKeyDown={(e) => e.stopPropagation()}>
          <option value="SKILL.md">SKILL.md</option>
          {Object.keys(files).map((path) => <option key={path} value={path}>{path}</option>)}
        </select>
        <span className="ca-skillform__count">{t('skillsDialog.nFiles', Object.keys(files).length + 1)}</span>
        {!isMain && onFiles && <button type="button" className="ca-history__del" title={t('common.remove')} onClick={() => { const { [open]: _gone, ...rest } = files; onFiles?.(rest); setOpen('SKILL.md') }}>{Icons.trash}</button>}
        <span className="ca-menu__grow" />
        <div className="ca-skillform__tabs" role="tablist" data-testid="skill-tabs">
          <button type="button" role="tab" aria-selected={tab === 'preview'} title={t('skillsDialog.preview')} className={tab === 'preview' ? 'is-on' : ''} onClick={() => setTab('preview')}><span className="ca-icon">{Icons.eyeView}</span></button>
          <button type="button" role="tab" aria-selected={tab === 'code'} title={t('skillsDialog.code')} className={tab === 'code' ? 'is-on' : ''} onClick={() => setTab('code')}><span className="ca-icon">{Icons.code}</span></button>
        </div>
      </div>
      {tab === 'preview'
        ? <div className="ca-skillform__preview ca-md" onDoubleClick={() => setTab('code')}>{body.trim() ? <Markdown text={body} /> : <span className="ca-side__empty">{t('composer.instructionsForTheAgentDeliverables')}</span>}</div>
        : <textarea className="ca-skillform__code ca-skills__md" value={body} placeholder={isMain ? t('composer.instructionsForTheAgentDeliverables') : ''} readOnly={!onInstructions} onChange={(e) => setBody(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />}
    </div>
  )
}

/** #462 — reference Edit Skill layout: Name → Description → Instructions box (file picker + Preview/Code tabs) → Edit in Chat · Cancel · Save. */
export function SkillForm({ initial, onDone, onEditInChat }: { initial: Skill; onDone: (s: Skill | null) => void; onEditInChat?: (s: Skill) => void }) {
  const [draft, setDraft] = useState(initial)
  const [open, setOpen] = useState<string>('SKILL.md')
  const file = useRef<HTMLInputElement>(null)
  const imageFile = useRef<HTMLInputElement>(null)
  const files = draft.files ?? {}
  const images = draft.images ?? {}
  const setFiles = (next: Record<string, string>) => setDraft({ ...draft, files: next })
  const add = async (list: FileList | null) => {
    const next = { ...files }
    for (const f of Array.from(list ?? [])) next[f.name] = await f.text()
    setFiles(next)
  }
  const valid = !!draft.name.trim() && !!draft.instructions.trim()
  return (
    <div className="ca-skillform" data-testid="skill-form">
      <div className="ca-rename__body ca-skillform__scroll" data-testid="skill-form-scroll">
      <label className="ca-skillform__label" htmlFor="skill-name">{t('skillsDialog.name')}</label>
      <input id="skill-name" className="ca-panel__input" value={draft.name} placeholder={t('composer.skillName')} onChange={(e) => setDraft({ ...draft, name: e.target.value })} onKeyDown={(e) => e.stopPropagation()} />
      <label className="ca-skillform__label" htmlFor="skill-desc">{t('skillsDialog.description')}</label>
      <textarea id="skill-desc" data-testid="skill-description" className="ca-panel__prompt ca-panel__prompt--boxed ca-skillform__desc" rows={2} value={draft.description ?? ''} placeholder={t('skillsDialog.descriptionPlaceholder')} onChange={(e) => setDraft({ ...draft, description: e.target.value })} onKeyDown={(e) => e.stopPropagation()} />
      <div className="ca-skillform__label">{t('skillsDialog.instructions')}</div>
      <SkillFileBox instructions={draft.instructions} files={files} open={open} setOpen={setOpen} onInstructions={(v) => setDraft({ ...draft, instructions: v })} onFiles={setFiles} />
      <div className="ca-gen__label">{t('skillsDialog.attachedFiles')}</div>
      {Object.keys(files).map((path) => (
        <div key={path} className="ca-skills__file">
          <div className="ca-memory__row">
            <span className="ca-icon">{Icons.files}</span>
            <span className="ca-menu__grow" onClick={() => setOpen(path)}>{path}</span>
            <button type="button" className="ca-history__del" title={t('common.remove')} onClick={() => { const { [path]: _gone, ...rest } = files; setFiles(rest); if (open === path) setOpen('SKILL.md') }}>{Icons.trash}</button>
          </div>
        </div>
      ))}
      <button type="button" className="ca-lib__new" onClick={() => file.current?.click()}><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.addFile')}</button>
      <div className="ca-gen__label">{t('common.image')}</div>
      <div className="ca-gen__refs ca-lib__images">
        {Object.entries(images).map(([path, src]) => (
          <span key={path} className="ca-gen__ref" title={path}><img src={src} alt="" /><button type="button" title={t('common.remove')} onClick={() => { const { [path]: _gone, ...rest } = images; setDraft({ ...draft, images: rest }) }}>{Icons.close}</button></span>
        ))}
        <button type="button" className="ca-gen__refadd" onClick={() => imageFile.current?.click()}><span className="ca-icon">{Icons.plus}</span><span>{t('skillsDialog.addImage')}</span></button>
        <input ref={imageFile} type="file" accept="image/*" multiple hidden onChange={(e) => {
          const list = Array.from(e.target.files ?? [])
          e.target.value = ''
          void Promise.all(list.map(async (f) => [f.name, await uploadSkillImage(f, draft.id)] as const)).then((added) => setDraft((d) => ({ ...d, images: { ...(d.images ?? {}), ...Object.fromEntries(added) } })))
        }} />
      </div>
      <input ref={file} type="file" multiple hidden accept=".md,.txt,.json,.csv,.yaml,.yml,.html,.css,.js,.ts,.svg" onChange={(e) => { void add(e.target.files); e.target.value = '' }} />
      </div>
      <div className="ca-panel__foot ca-skillform__foot">
        {onEditInChat && <button type="button" className="ca-panel__secondary" data-testid="skill-edit-in-chat" disabled={!draft.name.trim()} onClick={() => onEditInChat({ ...draft, name: draft.name.trim(), description: draft.description?.trim() || undefined })}>{t('skillsDialog.editInChat')}</button>}
        <span className="ca-menu__grow" />
        <button type="button" className="ca-panel__secondary" onClick={() => onDone(null)}>{t('common.cancel')}</button>
        <button type="button" className="ca-panel__primary" disabled={!valid} onClick={() => onDone({ ...draft, name: draft.name.trim(), description: draft.description?.trim() || undefined })}>{t('common.save')}</button>
      </div>
    </div>
  )
}

/** `home`: mounted on the Home/Skills shell (no canvas Composer) — Edit in Chat hands off to a new project. */
export function SkillsDialog({ onError }: { onError: (msg: string) => void; home?: boolean }) {
  const open = useValue(skillsOpenAtom)
  const editId = useValue(skillEditIdAtom)
  const [skills, setSkills] = useState<Skill[]>([])
  const [view, setView] = useState<View>({ kind: 'list' })
  const [note, setNote] = useState('')
  const folder = useRef<HTMLInputElement>(null)
  const refresh = () => loadSkills().then((all) => setSkills(all.filter((s) => s.custom))).catch((e) => onError(String(e)))

  useEffect(() => {
    if (!open) return
    setView({ kind: 'list' })
    void refresh()
    if (!editId) return
    skillEditIdAtom.set(null)
    void loadSkills().then((all) => {
      const s = all.find((x) => x.id === editId)
      if (s) setView({ kind: 'edit', skill: s })
      else onError(t('skillsDialog.notFound', editId))
    }).catch((e) => onError(String(e)))
  }, [open, editId])

  useEffect(() => {
    if (view.kind === 'history' && !view.versions) void listVersions(view.skill.id).then((versions) => setView({ ...view, versions })).catch((e) => onError(String(e)))
  }, [view])

  useEffect(() => {
    folder.current?.setAttribute('webkitdirectory', '')
  })

  if (!open) return null
  const close = () => skillsOpenAtom.set(false)
  const act = (fn: () => Promise<unknown>) => void fn().then(refresh).catch((e) => onError(errorText(e)))

  return (
    <Modal title={view.kind === 'list' ? t('skillsDialog.mySkills') : view.kind === 'edit' ? t('skillsDialog.editSkill') : t('skillsDialog.versionHistoryOf', view.skill.name)} className="ca-rename ca-memory ca-skills-dialog" onClose={close}>
      {view.kind === 'edit' && (
        <SkillForm
          initial={view.skill}
          onDone={(s) => {
            setView({ kind: 'list' })
            if (s) act(() => saveSkill(s))
          }}
          onEditInChat={view.skill.custom && view.skill.instructions.trim() ? () => { close(); editSkillInChat(view.skill) } : undefined}
        />
      )}
      {view.kind === 'history' && (
        <div className="ca-rename__body">
          {!view.versions && <div className="ca-side__empty">{t('skillsDialog.loading')}</div>}
          {view.versions?.length === 0 && <div className="ca-side__empty">{t('skillsDialog.noVersionsYetVersionsAre')}</div>}
          {view.versions?.map((v) => (
            <div key={v.time} className="ca-memory__row">
              <span className="ca-menu__grow" title={v.skill.instructions}>
                {new Date(v.time).toLocaleString()} · {v.skill.name} · {t('skillsDialog.versionFiles', Object.keys(v.skill.files ?? {}).length)}
              </span>
              <button type="button" className="ca-panel__chip" onClick={() => { setView({ kind: 'list' }); act(() => saveSkill({ ...v.skill, id: view.skill.id })) }}>{t('skillsDialog.rollBack')}</button>
            </div>
          ))}
          <div className="ca-panel__foot"><button type="button" className="ca-panel__secondary" onClick={() => setView({ kind: 'list' })}>{t('skillsDialog.back')}</button></div>
        </div>
      )}
      {view.kind === 'list' && (
        <div className="ca-rename__body">
          <div className="ca-chat__hint">{t('skillsDialog.eachSkillIsAFolder')}</div>
          <div className="ca-style__row">
            <button type="button" className="ca-lib__new" onClick={() => setView({ kind: 'edit', skill: { id: uuid().slice(0, 8), name: '', instructions: '', files: {}, custom: true } })}>
              <span className="ca-icon">{Icons.plus}</span>{t('skillsDialog.newSkill')}
            </button>
            <button type="button" className="ca-lib__new" onClick={() => folder.current?.click()}><span className="ca-icon">{Icons.upload}</span>{t('skillsDialog.importFolder')}</button>
            <input ref={folder} type="file" multiple hidden onChange={(e) => { const list = e.target.files; if (list) act(async () => { const { skipped } = await importFolder(list); setNote(skipped.length ? t('skillsDialog.importedSkipped', skipped.join(t('common.listSep'))) : t('skillsDialog.imported')) }); e.target.value = '' }} />
          </div>
          {note && <div className="ca-chat__hint">{note}</div>}
          {skills.length === 0 && <div className="ca-side__empty">{t('skillsDialog.noPersonalSkillsYet')}</div>}
          {skills.map((s) => (
            <div key={s.id} className="ca-memory__row">
              <span className="ca-icon">{Icons.skill}</span>
              <span className="ca-menu__grow" title={s.learned ? t('proactive.learnedFrom', s.learned.length, s.learned.join(' / ')) : s.instructions}>{s.name}{s.learned && <span className="ca-model__tag">{t('skillsDialog.learned')}</span>}{Object.keys(s.files ?? {}).length + Object.keys(s.images ?? {}).length > 0 && <span className="ca-menu__key"> · {t('skillsDialog.filesImages', Object.keys(s.files ?? {}).length, Object.keys(s.images ?? {}).length)}</span>}</span>
              <button type="button" className="ca-history__del" title={t('skillsDialog.use')} onClick={() => { skillAtom.set(s); close() }}>{Icons.comment}</button>
              <button type="button" className="ca-history__del" title={t('common.edit')} onClick={() => setView({ kind: 'edit', skill: s })}>{Icons.textTool}</button>
              <button type="button" className="ca-history__del" title={t('skillsDialog.versionHistory')} onClick={() => setView({ kind: 'history', skill: s, versions: null })}>{Icons.undo}</button>
              <button type="button" className="ca-history__del" title={t('common.delete')} onClick={() => confirmAtom.set({ danger: true, title: t('skillsDialog.deleteSkill', s.name), desc: t('skillsDialog.theSkillFolderAndAll'), ok: t('common.delete'), run: () => act(() => deleteSkill(s.id)) })}>{Icons.trash}</button>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
