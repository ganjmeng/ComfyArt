// #494-2 behavior harness: the input dialog / preset / handoff helpers through the real src/skills.ts, two different
// skills (poster, custom-workflow) + an old personal skill without inputs. No network, $0.
import { BUILTIN_SKILLS, hasSkillDialog, missingInputs, presetImage, skillDefaults, skillPreset, skillRunParams, withPreset } from '../../src/skills'
const by = (id: string) => BUILTIN_SKILLS.find((s) => s.id === id)!
const poster = by('poster'), cw = by('custom-workflow')
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
const r: Record<string, unknown> = {}
r.fields = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, (s.inputs ?? []).map((f) => [f.key, f.type, !!f.required, f.label.zh, f.label.en ?? null, f.placeholder?.en ?? null])]))
r.presets = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, (s.presets ?? []).map((p) => [p.id, p.name.en ?? null, !!p.prompt])]))
r.posterDefaults = skillDefaults(poster)
r.cwDefaults = skillDefaults(cw)
r.posterMissing = missingInputs(poster, skillDefaults(poster))
r.posterFilled = missingInputs(poster, { ...skillDefaults(poster), topic: 'Autumn launch' })
r.cwMissing = missingInputs(cw, { brief: '  ' })
r.dialog = [hasSkillDialog(poster), hasSkillDialog(cw), hasSkillDialog(old)]
const second = poster.presets![1]
r.withPreset = withPreset(poster, second.id).instructions
r.posterInstr = poster.instructions
r.secondPrompt = second.prompt
r.withUnknown = withPreset(poster, 'nope').instructions === poster.instructions
r.withNull = withPreset(old, null) === old
r.presetDefault = skillPreset(poster)?.id
r.presetPick = skillPreset(poster, second.id)?.id
r.presetImg = presetImage(poster, second)
r.posterPresetImgs = poster.presets!.map((p) => presetImage(poster, p))
r.builtinPresetImgs = BUILTIN_SKILLS.flatMap((s) => (s.presets ?? []).map((p) => presetImage(s, p)))
r.posterRun = skillRunParams(poster, { ...skillDefaults(poster), topic: 'Autumn launch', reference: '/view?f=a.png' }, second.id)
r.cwRun = skillRunParams(cw, { brief: 'Upscale my photo' }, null)
r.emptyRun = skillRunParams(old, {}, null)
console.log(JSON.stringify(r))
