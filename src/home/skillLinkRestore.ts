/** #725: persist a skill-link composer restore (draft + composer-only refs + skill id)
 *  per project in sessionStorage so a refresh does not lose or duplicate it. $0, no network. */
import type { LooseRef } from '../agent'

export const SKILL_LINK_STORE_PREFIX = 'comfyart.skillLinkRestore.'
export const SKILL_LINK_ACTIVE_PREFIX = 'comfyart.skillLinkRestore.active.'

export interface SkillLinkRestore {
  draft: string
  refs: LooseRef[]
  skillId: string | null
}

export function skillLinkStoreKey(project: string): string {
  return SKILL_LINK_STORE_PREFIX + project
}

export function skillLinkActiveKey(project: string): string {
  return SKILL_LINK_ACTIVE_PREFIX + project
}

export function dedupeLooseRefs(refs: LooseRef[]): LooseRef[] {
  const seen = new Set<string>()
  const out: LooseRef[] = []
  for (const r of refs) {
    const src = typeof r?.src === 'string' ? r.src.trim() : ''
    if (!src || seen.has(src)) continue
    seen.add(src)
    out.push({ src, name: typeof r.name === 'string' && r.name ? r.name : src })
  }
  return out
}

export function parseSkillLinkRestore(raw: string | null): SkillLinkRestore | null {
  if (!raw) return null
  try {
    const v = JSON.parse(raw) as Partial<SkillLinkRestore>
    const draft = typeof v.draft === 'string' ? v.draft : ''
    const refs = dedupeLooseRefs(Array.isArray(v.refs) ? v.refs as LooseRef[] : [])
    const skillId = typeof v.skillId === 'string' && v.skillId ? v.skillId : null
    if (!draft && !refs.length && !skillId) return null
    return { draft, refs, skillId }
  } catch {
    return null
  }
}

/** Returns the JSON to store, or null when the state should be deleted. */
export function encodeSkillLinkRestore(state: SkillLinkRestore): string | null {
  const next: SkillLinkRestore = {
    draft: state.draft ?? '',
    refs: dedupeLooseRefs(state.refs ?? []),
    skillId: state.skillId || null,
  }
  if (!next.draft && !next.refs.length && !next.skillId) return null
  return JSON.stringify(next)
}

export function readSkillLinkRestore(storage: Storage, project: string): SkillLinkRestore | null {
  if (!project) return null
  try {
    return parseSkillLinkRestore(storage.getItem(skillLinkStoreKey(project)))
  } catch {
    return null
  }
}

export function writeSkillLinkRestore(storage: Storage, project: string, state: SkillLinkRestore): void {
  if (!project) return
  try {
    const key = skillLinkStoreKey(project)
    const encoded = encodeSkillLinkRestore(state)
    if (!encoded) storage.removeItem(key)
    else storage.setItem(key, encoded)
  } catch { /* private mode */ }
}

export function isSkillLinkRestoreActive(storage: Storage, project: string): boolean {
  if (!project) return false
  try {
    return storage.getItem(skillLinkActiveKey(project)) === '1'
  } catch {
    return false
  }
}

export function markSkillLinkRestoreActive(storage: Storage, project: string): void {
  if (!project) return
  try { storage.setItem(skillLinkActiveKey(project), '1') } catch { /* private mode */ }
}

export function clearSkillLinkRestore(storage: Storage, project: string): void {
  if (!project) return
  try {
    storage.removeItem(skillLinkStoreKey(project))
    storage.removeItem(skillLinkActiveKey(project))
  } catch { /* private mode */ }
}

/** Replace (never append) so a second apply / refresh cannot grow the list. */
export function replaceSkillLinkRestore(
  _prev: SkillLinkRestore | null,
  incoming: SkillLinkRestore,
): SkillLinkRestore {
  return {
    draft: incoming.draft ?? '',
    refs: dedupeLooseRefs(incoming.refs ?? []),
    skillId: incoming.skillId || null,
  }
}
