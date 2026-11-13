// #960: real src/skills.ts skillTool against an in-memory store (no browser, no backend).
// Prints one JSON report: paging a long built-in skill, a long bundled file, a short read, and
// the 4000-char tool-result cap. No WaveSpeed, no LLM.
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'

const YT = 'youtube-channel-banner'
const FULL = S.BUILTIN_SKILLS.find((s) => s.id === YT)!.instructions
const LONG_FILE = Array.from({ length: 220 }, (_, i) => `line ${i} reference detail card ${i} ✓`).join('\n')

async function safe<T>(fn: () => Promise<T>): Promise<T | { error: string }> {
  try { return await fn() } catch (e) { return { error: String((e as Error)?.message ?? e) } }
}

async function main() {
  setLang('zh')
  const out: Record<string, unknown> = { total: FULL.length }
  const page1 = await S.skillTool({ action: 'read', id: YT }) as any
  out.page1 = page1
  out.page1Len = JSON.stringify(page1).length
  out.page1IsWhole = page1.content === FULL
  out.page1HasCard1 = ['yt_delivery', 'yt_banner_text', 'yt_brand_assets', '3) Direction board'].every((k) => String(page1.content).includes(k))

  const pages: any[] = [page1]
  while (pages[pages.length - 1].has_more) {
    const next: number = pages[pages.length - 1].next_offset
    pages.push(await S.skillTool({ action: 'read', id: YT, offset: next }))
  }
  out.pageCount = pages.length
  out.offsets = pages.map((p) => p.offset)
  out.contentsMatch = pages.every((p) => p.content === FULL.slice(p.offset, p.offset + p.content.length))
  out.joinedIsWhole = pages.map((p) => p.content).join('') === FULL
  out.lastHasMore = pages[pages.length - 1].has_more
  out.lastNext = pages[pages.length - 1].next_offset
  out.notes = pages.every((p) => typeof p.note === 'string' && p.note.includes('next_offset'))
  out.metas = pages.map((p) => p.total_chars)
  out.hasMoreFlags = pages.map((p) => p.has_more)

  // limit + offset are honored and clamped to one cap-safe page.
  const small = await S.skillTool({ action: 'read', id: YT, offset: 10, limit: 100 }) as any
  out.small = { content: small.content, offset: small.offset, next: small.next_offset, match: small.content === FULL.slice(10, 110) }
  const clamped = await S.skillTool({ action: 'read', id: YT, offset: 0, limit: 99999 }) as any
  out.clampedLen = clamped.content.length
  out.clampedCap = S.SKILL_READ_MAX_PAGE

  // a long bundled file is paged the same way; a short read keeps the old shape.
  await S.saveSkill({ id: 'paged960', name: 'Paged 960', instructions: 'short body', files: { 'reference.md': LONG_FILE }, custom: true } as any)
  const file1 = await S.skillTool({ action: 'read', id: 'paged960', path: 'reference.md' }) as any
  const filePages: any[] = [file1]
  while (filePages[filePages.length - 1].has_more) {
    const at: number = filePages[filePages.length - 1].next_offset
    filePages.push(await S.skillTool({ action: 'read', id: 'paged960', path: 'reference.md', offset: at }))
  }
  out.file = {
    total: file1.total_chars,
    pages: filePages.length,
    hasMore: file1.has_more,
    joined: filePages.length > 1 && filePages.map((p) => p.content).join('') === LONG_FILE,
    isWhole: file1.content === LONG_FILE,
    len: JSON.stringify(file1).length,
    lastHasMore: filePages[filePages.length - 1].has_more,
  }
  const shortRead = await S.skillTool({ action: 'read', id: 'paged960' }) as any
  out.shortRead = {
    instructions: shortRead.instructions,
    hasMore: shortRead.has_more,
    hasContent: 'content' in shortRead,
    jsonLen: JSON.stringify(shortRead).length,
  }
  const past = await S.skillTool({ action: 'read', id: YT, offset: 999999 }) as any
  out.past = { content: past.content, hasMore: past.has_more, note: past.note }

  // a missing path still names the real files (no silent empty read)
  await S.saveSkill({ id: 'paged960b', name: 'Paged B', instructions: 'body', files: { 'notes.md': 'n' }, custom: true } as any)
  out.missingPath = await safe(() => S.skillTool({ action: 'read', id: 'paged960b', path: 'reference.md' }))

  console.log(JSON.stringify(out))
}
main()
