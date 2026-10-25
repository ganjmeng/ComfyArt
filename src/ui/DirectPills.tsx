import { useValue } from 'tldraw'

import { directSettingsAtom, type DirectSettings } from '../agent'
import { VIDEO_RATIOS } from '../genOptions'
import { agentModels, AUTO_IMAGE, AUTO_VIDEO, modelOf } from '../models'
import { GENERATOR_DEFAULTS, type GeneratorShape } from '../shapes/GeneratorShape'
import { ModelPill, SettingsPill } from './GenSettings'

/** Image / video mode: model + settings pills. Used by the canvas composer and (#287) the home composer;
 *  both read and write the same directSettingsAtom, and home hands its pick to the new project. */
export function DirectPills({ video, within = '.ca-composer', spacer = true }: { video: boolean; within?: string; spacer?: boolean }) {
  const key = video ? 'video' : 'image'
  const settings = useValue('direct settings', () => directSettingsAtom.get()[key], [key])
  const workflow = settings.workflow || (video ? AUTO_VIDEO : AUTO_IMAGE)
  const p: GeneratorShape['props'] = { ...GENERATOR_DEFAULTS, ratio: video ? VIDEO_RATIOS[0] : '1:1', ...settings, workflow }
  const model = modelOf(workflow)!
  const update = (patch: DirectSettings) => {
    const all = directSettingsAtom.get()
    directSettingsAtom.set({ ...all, [key]: { ...all[key], ...patch } })
  }
  return (
    <>
      {/* #268: only + and mode sit left; model and settings group right, next to voice/send */}
      {spacer && <div className="ca-composer__pillspacer" />}
      <ModelPill video={video} model={model} onPick={(_f, id) => update({ workflow: id })} onAuto={(on) => update({ workflow: on ? (video ? AUTO_VIDEO : AUTO_IMAGE) : agentModels(video)[0].id })} align="end" within={within} />
      <SettingsPill p={p} video={video} quality={!!model.steps} tiers={model.qualities} update={update} align="end" within={within} />
    </>
  )
}
