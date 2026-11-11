/** #725: sessionStorage glue for skill-link composer restore. Test-only hide fixture lives in this file, not src/skills.ts. */
import { draftAtom, looseRefsAtom } from '../agent'
import { refFromUrl, refKind } from '../comfy'
import { currentProject } from '../notices'
import { t } from '../i18n'
import { attachSkill, hiddenSkillNotice, loadSkills, skillAtom, skillNoticeAtom, type Skill } from '../skills'
import {
  clearSkillLinkRestore,
  dedupeLooseRefs,
  isSkillLinkRestoreActive,
  markSkillLinkRestoreActive,
  readSkillLinkRestore,
  writeSkillLinkRestore,
  type SkillLinkRestore,
} from './skillLinkRestore'

function store(): Storage | null {
  try { return sessionStorage } catch { return null }
}

/** When attachSkill refuses a hidden skill, skillAtom is null — keep the id so a refresh can re-show the notice. */
let hiddenSkillId: string | null = null
/** False until a skill-link handoff or a persisted restore has populated atoms.
 *  Stops the composer’s first empty paint from overwriting sessionStorage on refresh. */
let persistReady = false

export function rememberHiddenSkillId(id: string | null) {
  hiddenSkillId = id
}

/** #725 test-only: with localStorage comfyart.e2e=1, comfyart.e2e.hideSkills (comma ids)
 *  is treated as hidden for old-link attach/notice. Does not change HIDDEN_BUILTIN_SKILL_IDS. */
export function e2eHiddenSkillIds(): Set<string> {
  try {
    if (globalThis.localStorage?.getItem('comfyart.e2e') !== '1') return new Set()
    const raw = globalThis.localStorage.getItem('comfyart.e2e.hideSkills') ?? ''
    return new Set(raw.split(',').map((s) => s.trim()).filter(Boolean))
  } catch {
    return new Set()
  }
}

/** Attach a skill for a skill-link, honoring the e2e hide fixture. Returns false when no chip is shown. */
export function attachSkillForLink(skill: Skill): boolean {
  if (!skill.custom && e2eHiddenSkillIds().has(skill.id)) {
    skillAtom.set(null)
    skillNoticeAtom.set(hiddenSkillNotice(skill) ?? t('skills.hiddenUnavailable'))
    rememberHiddenSkillId(skill.id)
    return false
  }
  const ok = attachSkill(skill)
  if (!ok) rememberHiddenSkillId(skill.id)
  return ok
}


export function looseRefsFromHandoff(urls: string[]) {
  return dedupeLooseRefs(
    urls.filter((src) => refKind(src) !== 'audio').map((src) => ({ src, name: refFromUrl(src).filename })),
  )
}

function capture(): SkillLinkRestore {
  return {
    draft: draftAtom.get(),
    refs: dedupeLooseRefs(looseRefsAtom.get()),
    skillId: skillAtom.get()?.id ?? (skillNoticeAtom.get() ? hiddenSkillId : null),
  }
}

/** Write the current composer restore if this project has an active skill-link session. */
export function persistSkillLinkRestore() {
  if (!persistReady) return
  const s = store()
  const project = currentProject()
  if (!s || !project || !isSkillLinkRestoreActive(s, project)) return
  writeSkillLinkRestore(s, project, capture())
}

export function endSkillLinkRestore() {
  persistReady = false
  const s = store()
  const project = currentProject()
  hiddenSkillId = null
  if (!s || !project) return
  clearSkillLinkRestore(s, project)
}

export function applyLooseRefsFromHandoff(urls: string[]) {
  looseRefsAtom.set(looseRefsFromHandoff(urls))
}

/** Apply a fresh ?skill= handoff after attachSkill: composer-only refs + draft. Never places canvas shapes. */
export function applySkillLinkHandoff(text: string, refs: string[]) {
  draftAtom.set(text)
  looseRefsAtom.set(refs.length ? looseRefsFromHandoff(refs) : [])
  const s = store()
  const project = currentProject()
  persistReady = true
  if (s && project) {
    markSkillLinkRestoreActive(s, project)
    writeSkillLinkRestore(s, project, capture())
  }
}

/** After a refresh the URL params are gone — rehydrate draft, composer refs, and skill/notice. */
export async function applyPersistedSkillLinkRestore() {
  const s = store()
  const project = currentProject()
  if (!s || !project) return
  const state = readSkillLinkRestore(s, project)
  if (!state) return
  persistReady = true
  markSkillLinkRestoreActive(s, project)
  if (state.draft) draftAtom.set(state.draft)
  looseRefsAtom.set(dedupeLooseRefs(state.refs))
  if (state.skillId) {
    const found = (await loadSkills()).find((x) => x.id === state.skillId) ?? null
    if (found) attachSkillForLink(found)
  }
}
