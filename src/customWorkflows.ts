import { atom } from 'tldraw'

import { listUserFiles, readUserJson, setWsHook, writeUserJson, writeUserText } from './comfy'
import { asApiWorkflow, checkWorkflow, CUSTOM_ACTIONS, parseApiWorkflow, rulesText, specOf, type CustomAction, type CustomSpec } from './customMarkers'
import { t } from './i18n'

const DIR = 'comfyart/workflows'
const CONFIG = 'comfyart/workflow-config.json'

export const CUSTOM_GENERATE = 'custom:generate'
export const CUSTOM_MUSIC = 'custom:music'
export const CUSTOM_SPEECH = 'custom:speech'
export const CUSTOM_MODEL3D = 'custom:model3d'
export const workflowConfigAtom = atom<Partial<Record<CustomAction, string>>>('workflow config', {})
/** #509: WaveSpeed model id of each assigned file, so the audio dialog can read its duration range synchronously. */
export const customModelsAtom = atom<Partial<Record<CustomAction, string>>>('custom models', {})

async function refreshCustomModels(config: Partial<Record<CustomAction, string>>) {
  const entries = await Promise.all(Object.entries(config).map(async ([action, file]) => {
    const spec = await readCustomWorkflow(action as CustomAction, file!).catch(() => null)
    return spec ? [action, spec.model] : null
  }))
  customModelsAtom.set(Object.fromEntries(entries.filter((e) => !!e) as [string, string][]))
}

export async function loadWorkflowConfig() {
  setWsHook(withCustomModel)
  const config = await readUserJson<Partial<Record<CustomAction, string>>>(CONFIG, {})
  const present = await Promise.all(Object.entries(config).map(async ([action, file]) => (await listCustomWorkflows(action as CustomAction)).includes(file!) && [action, file]))
  workflowConfigAtom.set(Object.fromEntries(present.filter((e) => !!e)))
  await refreshCustomModels(workflowConfigAtom.get())
}

export async function setCustomWorkflow(action: CustomAction, file: string | null) {
  const next = { ...workflowConfigAtom.get() }
  if (file) next[action] = file
  else delete next[action]
  workflowConfigAtom.set(next)
  await writeUserJson(CONFIG, next)
  await refreshCustomModels(next)
}

export const listCustomWorkflows = async (action: CustomAction) => (await listUserFiles(`${DIR}/${action}`)).filter((f) => f.endsWith('.json')).sort()

export async function readCustomWorkflow(action: CustomAction, file: string): Promise<CustomSpec | null> {
  const data = await readUserJson<unknown>(`${DIR}/${action}/${file}`, null)
  if (data == null) return null
  return asApiWorkflow(data)
}

export async function saveCustomWorkflow(action: CustomAction, name: string, spec: CustomSpec): Promise<string> {
  const file = name.replace(/[\\/:*?"<>|]/g, '_').replace(/(\.api)?\.json$/i, '') + '.json'
  await writeUserText(`${DIR}/${action}/${file}`, JSON.stringify(spec, null, 2))
  return file
}

/** Inputs of a WaveSpeed job tagged with custom: <action>; swaps in the assigned model, or just drops the tag. */
export async function withCustomModel(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { custom: action, ...rest } = inputs
  if (typeof action !== 'string' || !CUSTOM_ACTIONS.some((a) => a.id === action)) return rest
  const file = workflowConfigAtom.get()[action as CustomAction]
  if (!file) {
    if (action === 'generate' && rest.model === CUSTOM_GENERATE) throw new Error(t('customWorkflows.generateGone', CUSTOM_GENERATE))
    if (action === 'music' && rest.model === CUSTOM_MUSIC) throw new Error(t('customWorkflows.musicGone'))
    if (action === 'speech' && rest.model === CUSTOM_SPEECH) throw new Error(t('customWorkflows.speechGone'))
    if (action === 'model3d' && rest.model === CUSTOM_MODEL3D) throw new Error(t('customWorkflows.model3dGone'))
    return rest
  }
  const spec = await readCustomWorkflow(action as CustomAction, file)
  if (!spec) {
    if (action === 'generate') throw new Error(t('customWorkflows.generateGone', file.replace(/\.json$/, '')))
    if (action === 'music') throw new Error(t('customWorkflows.musicGone'))
    if (action === 'speech') throw new Error(t('customWorkflows.speechGone'))
    if (action === 'model3d') throw new Error(t('customWorkflows.model3dGone'))
    return rest
  }
  const req = specOf(action as CustomAction).required
  const mapped = Object.keys(spec.fields ?? {}).map((k) => String(k).replace(/^@/, '').toLowerCase())
  const needsImage = req.includes('image') || mapped.includes('image')
  if (needsImage && !rest.image && !(rest.images as unknown[] | undefined)?.length) throw new Error(t('customWorkflows.needsImage', file))
  if (req.includes('video') && !rest.video) throw new Error(t('customWorkflows.needsVideo', file))
  if (req.includes('audio') && !rest.audio) throw new Error(t('customWorkflows.needsAudio', file))
  // Upstream: a base image with no @base mapping is an error (generate).
  if (rest.base && !mapped.includes('base')) throw new Error(t('customWorkflows.unusedInput', file, '@base'))
  return { ...rest, feature: rest.feature ?? specOf(action as CustomAction).feature, custom: true, model: spec.model, fields: spec.fields ?? {}, params: { ...(rest.params as object | undefined), ...spec.params } }
}

type Args = Record<string, unknown>

function featureOf(args: Args): CustomAction {
  const feature = CUSTOM_ACTIONS.find((a) => a.id === args.feature)?.id
  if (!feature) throw new Error(`feature must be one of ${CUSTOM_ACTIONS.map((a) => a.id).join(', ')}`)
  return feature
}

async function workflowOf(feature: CustomAction, args: Args): Promise<CustomSpec> {
  if (args.workflow != null) return typeof args.workflow === 'string' ? parseApiWorkflow(args.workflow) : asApiWorkflow(args.workflow)
  const spec = args.file ? await readCustomWorkflow(feature, String(args.file)) : null
  if (!spec) throw new Error(args.file ? `no workflow ${args.file} for ${feature}; see action list` : 'give workflow ({model, fields, params} JSON) or file')
  return spec
}

export async function customWorkflowCommand(args: Args): Promise<object> {
  if (args.action === 'rules') return { rules: rulesText() }
  if (args.action === 'list') {
    return {
      features: await Promise.all(CUSTOM_ACTIONS.map(async ({ id, required, optional }) => ({
        id, required: required.map((m) => `@${m}`), optional: optional.map((m) => `@${m}`), assigned: workflowConfigAtom.get()[id] ?? null, files: await listCustomWorkflows(id),
      }))),
    }
  }
  if (args.action === 'check') {
    const feature = featureOf(args)
    const { fields, errors, warnings, price } = await checkWorkflow(await workflowOf(feature, args), feature)
    return { ok: !errors.length, errors, warnings, fields, price }
  }
  if (args.action === 'install') {
    if (!args.name) throw new Error('give a short name for the workflow file')
    const feature = featureOf(args)
    const spec = await workflowOf(feature, args)
    const { errors, warnings } = await checkWorkflow(spec, feature)
    if (errors.length) return { installed: false, errors, warnings }
    const file = await saveCustomWorkflow(feature, String(args.name), spec)
    await setCustomWorkflow(feature, file)
    return { installed: true, file, assigned: feature, warnings }
  }
  if (args.action === 'assign') {
    const feature = featureOf(args)
    if (!args.file) {
      await setCustomWorkflow(feature, null)
      return { feature, file: null }
    }
    const { errors } = await checkWorkflow(await workflowOf(feature, { file: args.file }), feature)
    if (errors.length) return { assigned: false, errors }
    await setCustomWorkflow(feature, String(args.file))
    return { feature, file: args.file }
  }
  throw new Error('action must be rules, list, check, install or assign')
}
