import { customWorkflowCommand, listCustomWorkflows, workflowConfigAtom } from '../../src/customWorkflows'
import { checkProblem } from '../../src/customMarkers'
import { setLang } from "./i18n_stub"
import { files } from './comfy_stub'

const BAD = { ok: false, errors: ['acme/my-edit has no field for @image'], warnings: [], fields: {},
  codes: [{ code: 'missingFields', model: 'acme/my-edit', markers: ['@image', '@prompt'] }, { code: 'requiredParams', model: 'acme/my-edit', params: ['input_image', 'instruction', 'strength'] }] }
;(globalThis as any).__check = async (body: any) => ({ ok: true, json: async () => (body.spec.fields ? { ok: true, errors: [], warnings: [], fields: {} } : BAD) })

const out: any = {}
out.bad = await customWorkflowCommand({ action: 'install', name: 'broken', feature: 'edit', workflow: { model: 'acme/my-edit' } })
out.listAfterBad = await listCustomWorkflows('edit')
out.configAfterBad = workflowConfigAtom.get()
out.files = Object.keys(files)
out.good = await customWorkflowCommand({ action: 'install', name: 'my-edit', feature: 'edit', workflow: { model: 'acme/my-edit', fields: { '@image': 'input_image' } } })
out.listAfterGood = await listCustomWorkflows('edit')
setLang('zh'); out.zh = checkProblem('broken.json', BAD)
setLang('en'); out.en = checkProblem('broken.json', BAD)
console.log(JSON.stringify(out))
