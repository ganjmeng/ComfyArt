import { useValue } from 'tldraw'

import { VIDEO_RATIOS } from '../genOptions'
import { agentModels, AUTO_IMAGE, AUTO_VIDEO, modelOf, modelPrefsAtom, saveDirectSettings, type DirectSettings } from '../models'
import { GENERATOR_DEFAULTS, type GeneratorShape } from '../shapes/GeneratorShape'
import { ModelPill, SettingsPill } from './GenSettings'

/** Image / video mode: model + settings pills. Used by the canvas composer and (#287) the home composer;
 *  both read and write the one saved store (modelPrefs.image / modelPrefs.video), so a pick on either side shows on both. */
export function DirectPills({ video, within = '.ca-composer', spacer = true, onError, side }: { video: boolean; within?: string; spacer?: boolean; onError?: (msg: string) => void; side?: 'top' | 'bottom' }) {
  const key = video ? 'video' : 'image'
  const settings = useValue('direct settings', () => modelPrefsAtom.get()[key] ?? {}, [key])
  const workflow = settings.workflow || (video ? AUTO_VIDEO : AUTO_IMAGE)
  const p: GeneratorShape['props'] = { ...GENERATOR_DEFAULTS, ratio: video ? VIDEO_RATIOS[0] : '1:1', ...settings, workflow }
  // a saved pick may not be in the model list yet (still loading / no longer offered): show Auto until it is
  const model = modelOf(workflow) ?? modelOf(video ? AUTO_VIDEO : AUTO_IMAGE)!
  const update = (patch: DirectSettings) => {
    void saveDirectSettings(key, patch).catch((e) => onError?.(String(e)))
  }
  return (
    <>
      {/* #268: only + and mode sit left; model and settings group right, next to voice/send */}
      {spacer && <div className="ca-composer__pillspacer" />}
      <ModelPill video={video} model={model} onPick={(_f, id) => update({ workflow: id })} onAuto={(on) => update({ workflow: on ? (video ? AUTO_VIDEO : AUTO_IMAGE) : agentModels(video)[0].id })} align="end" within={within} side={side} />
      <SettingsPill p={p} video={video} quality={!!model.steps} tiers={model.qualities} update={update} align="end" within={within} side={side} />
    </>
  )
}
