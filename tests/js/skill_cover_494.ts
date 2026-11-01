import { BUILTIN_SKILLS, matchesSkillChip, skillChips, skillCover, skillVideo } from '../../src/skills'
const r: Record<string, unknown> = {}
const old = { id: 'old-skill', name: 'o', instructions: '', custom: true }
r.noImage = skillCover(old)
r.ownImage = skillCover({ ...old, images: { 'r.png': 'input/r.png' } })
r.custom = skillCover(BUILTIN_SKILLS.find((s) => s.id === 'custom-workflow')!)
r.customNoCover = skillCover({ ...BUILTIN_SKILLS.find((s) => s.id === 'custom-workflow')!, cover: undefined }) // #581: fallback still null
r.builtinCovers = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillCover(s)?.src ?? null]))
r.chips = skillChips(BUILTIN_SKILLS)
r.byChip = Object.fromEntries((r.chips as string[]).map((c) => [c, BUILTIN_SKILLS.filter((s) => matchesSkillChip(s, c as never)).map((s) => s.id)]))
// #529 — video field data-driven (mutation: drop video → null; custom never fakes a badge)
r.builtinVideos = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillVideo(s)]))
r.noVideo = skillVideo(old)
r.customVideo = skillVideo(BUILTIN_SKILLS.find((s) => s.id === 'custom-workflow')!)
r.videoMutated = skillVideo({ ...BUILTIN_SKILLS.find((s) => s.id === 'poster')!, video: undefined })
console.log(JSON.stringify(r))
