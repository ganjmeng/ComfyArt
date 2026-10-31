import { useEffect, useRef, useState } from 'react'
import { atom, useValue } from 'tldraw'

import { checkProblem, checkWorkflow, CUSTOM_ACTIONS, parseApiWorkflow, rulesText, type CustomAction, type CustomGroup } from '../customMarkers'
import { listCustomWorkflows, readCustomWorkflow, saveCustomWorkflow, setCustomWorkflow, workflowConfigAtom } from '../customWorkflows'
import { errorText } from '../jobs'
import { CopyButton } from './CopyButton'
import { FieldSelect } from './FieldSelect'
import { Icons } from './icons'
import { Modal } from './Modal'
import { t } from '../i18n'

export const workflowsOpenAtom = atom('workflows open', false)

const DOCS = 'https://comfyart.org/guides/custom-workflows'
const GROUPS: CustomGroup[] = ['image', 'edit', 'tools', 'video', 'audio']

async function problemsOf(action: CustomAction, file: string): Promise<string[]> {
  const spec = await readCustomWorkflow(action, file)
  if (!spec) return []
  const check = await checkWorkflow(spec, action)
  return check.errors.length ? [checkProblem(file, check)] : []
}

export function WorkflowsDialog({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(workflowsOpenAtom)
  const config = useValue(workflowConfigAtom)
  const [files, setFiles] = useState<Partial<Record<CustomAction, string[]>>>({})
  const [problems, setProblems] = useState<Partial<Record<CustomAction, string[]>>>({})
  const upload = useRef<HTMLInputElement>(null)
  const target = useRef<CustomAction>('generate')
  const run = (p: Promise<unknown>) => void p.catch((e) => onError(errorText(e)))

  useEffect(() => {
    if (!open) return
    let alive = true
    run(Promise.all(CUSTOM_ACTIONS.map(async ({ id }) => [id, await listCustomWorkflows(id), config[id] ? await problemsOf(id, config[id]) : []] as const))
      .then((rows) => {
        if (!alive) return
        setFiles(Object.fromEntries(rows.map(([id, list]) => [id, list])))
        setProblems(Object.fromEntries(rows.map(([id, , errors]) => [id, errors])))
      }))
    return () => { alive = false }
  }, [open, config])

  if (!open) return null

  const pick = async (action: CustomAction, file: string) => {
    if (file) {
      const errors = await problemsOf(action, file)
      if (errors.length) throw new Error(errors[0])
    }
    await setCustomWorkflow(action, file || null)
  }

  const add = async (action: CustomAction, file: File | undefined) => {
    if (!file) return
    const spec = parseApiWorkflow(await file.text())
    const check = await checkWorkflow(spec, action)
    if (check.errors.length) throw new Error(checkProblem(file.name, check))
    await setCustomWorkflow(action, await saveCustomWorkflow(action, file.name, spec))
  }

  return (
    <Modal title={t('customWorkflows.title')} onClose={() => workflowsOpenAtom.set(false)}>
      <div className="ca-rename__body">
        <div className="ca-chat__hint">
          {t('customWorkflows.intro')} <a href={DOCS} target="_blank" rel="noreferrer">{t('customWorkflows.docs')}</a>
        </div>
        <div className="ca-memory__row">
          <span className="ca-menu__grow ca-chat__hint">{t('customWorkflows.agentHint')}</span>
          <CopyButton text={rulesText()} />
        </div>
        {GROUPS.map((group) => (
          <div key={group} className="ca-workflows__group">
            <div className="ca-gen__label">{t(`customWorkflows.group.${group}`)}</div>
            {CUSTOM_ACTIONS.filter((a) => a.group === group).map(({ id }) => (
              <div key={id} className="ca-workflows__row">
                <span>{t(`customWorkflows.action.${id}`)}</span>
                <FieldSelect
                  value={files[id]?.includes(config[id] ?? '') ? (config[id] ?? '') : ''}
                  options={[
                    { id: '', label: t('customWorkflows.builtIn') },
                    ...(files[id] ?? []).map((f) => ({ id: f, label: f.replace(/\.json$/, ''), title: f })),
                  ]}
                  onChange={(v) => run(pick(id, v))}
                />
                <button type="button" className="ca-panel__icon" title={`${t('customWorkflows.upload')} (comfyart/workflows/${id}/)`} onClick={() => { target.current = id; upload.current?.click() }}>{Icons.upload}</button>
                {(problems[id]?.length ?? 0) > 0 && <span className="ca-workflows__warn">{problems[id]!.join(' ')}</span>}
              </div>
            ))}
          </div>
        ))}
        <div className="ca-chat__hint">{t('customWorkflows.where')}</div>
        <input ref={upload} type="file" accept=".json,application/json" hidden onChange={(e) => { run(add(target.current, e.target.files?.[0])); e.target.value = '' }} />
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__primary" onClick={() => workflowsOpenAtom.set(false)}>{t('common.done')}</button>
        </div>
      </div>
    </Modal>
  )
}
