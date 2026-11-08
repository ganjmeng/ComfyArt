import { useEffect, useState } from 'react'

import { lang } from '../i18n'
import {
  loadProviderAdmin,
  ProviderAdminError,
  restoreImageProvider,
  restoreLlmProvider,
  saveImageProvider,
  saveLlmProvider,
  setProviderAdminOpen,
  subscribeProviderAdmin,
  providerAdminOpen,
  type ImageProviderInfo,
  type LlmModel,
  type LlmProviderInfo,
  type ProviderAdminState,
} from '../providerAdmin'
import { FieldSelect } from './FieldSelect'
import { Modal } from './Modal'

const CAPS = ['text_to_image', 'image_edit', 'text_to_gif', 'reference_gif'] as const

const CAP_LABEL: Record<string, [string, string]> = {
  text_to_image: ['文生图', 'Text to image'],
  image_edit: ['图编辑', 'Image edit'],
  text_to_gif: ['文生 GIF', 'Text to GIF'],
  reference_gif: ['参考图 GIF', 'Reference GIF'],
}

const tx = (zh: string, en: string) => (lang === 'zh' ? zh : en)
const lt = (value: { zh?: string; en?: string } | undefined) => (lang === 'zh' ? value?.zh : value?.en) || value?.zh || value?.en || ''

function useDialogOpen() {
  const [value, setValue] = useState(providerAdminOpen())
  useEffect(() => subscribeProviderAdmin(() => setValue(providerAdminOpen())), [])
  return value
}

export function ProviderAdmin() {
  const open = useDialogOpen()
  const [state, setState] = useState<ProviderAdminState | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [imageProvider, setImageProvider] = useState('wavespeed')
  const [imageModels, setImageModels] = useState<Record<string, string>>({})
  const [llmProvider, setLlmProvider] = useState('wavespeed')
  const [llmModel, setLlmModel] = useState('existing')
  const [imageMsg, setImageMsg] = useState('')
  const [llmMsg, setLlmMsg] = useState('')
  const [imageErr, setImageErr] = useState('')
  const [llmErr, setLlmErr] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (!open) return
    setImageMsg('')
    setLlmMsg('')
    setImageErr('')
    setLlmErr('')
    setForbidden(false)
    loadProviderAdmin().then((next) => {
      setState(next)
      applyImage(next)
      applyLlm(next)
    }).catch((e: unknown) => {
      if (e instanceof ProviderAdminError && e.status === 403) setForbidden(true)
      else setImageErr(e instanceof Error ? e.message : String(e))
    })
  }, [open])

  if (!open) return null
  const close = () => setProviderAdminOpen(false)

  function applyImage(next: ProviderAdminState) {
    const active = next.image.active
    const provider = active?.provider || 'wavespeed'
    setImageProvider(provider)
    const models: Record<string, string> = {}
    const info = next.image.providers.find((p) => p.id === 'replicate')
    for (const cap of CAPS) {
      models[cap] = active?.models?.[cap] || info?.models.find((m) => m.capabilities.includes(cap))?.id || ''
    }
    setImageModels(models)
  }

  function applyLlm(next: ProviderAdminState) {
    setLlmProvider(next.llm.active?.provider || 'wavespeed')
    setLlmModel(next.llm.active?.model || 'existing')
  }

  const imageInfo = state?.image.providers.find((p) => p.id === imageProvider)
  const llmInfo = state?.llm.providers.find((p) => p.id === llmProvider)
  const llmPicked = llmInfo?.models.find((m) => m.id === llmModel)

  const saveImage = () => {
    setBusy('image')
    setImageErr('')
    setImageMsg('')
    const body = imageProvider === 'wavespeed'
      ? { provider: 'wavespeed' }
      : { provider: imageProvider, models: imageModels }
    saveImageProvider(body).then((next) => {
      setState(next)
      applyImage(next)
      setImageMsg(tx('已保存。进行中的任务不变，只有新任务使用这份图像配置。', 'Saved. Running jobs stay as they are. Only new jobs use this image setup.'))
    }).catch((e: unknown) => {
      setImageErr(e instanceof ProviderAdminError ? [e.message, ...e.issues].filter(Boolean).join(' · ') : String(e))
    }).finally(() => setBusy(''))
  }

  const saveLlm = () => {
    setBusy('llm')
    setLlmErr('')
    setLlmMsg('')
    saveLlmProvider({ provider: llmProvider, model: llmModel }).then((next) => {
      setState(next)
      applyLlm(next)
      setLlmMsg(tx('已保存。未保存前的选择没有生效。进行中的对话仍用开始时的模型。', 'Saved. The choice did nothing until this save. A chat already running keeps the model it started with.'))
    }).catch((e: unknown) => {
      setLlmErr(e instanceof ProviderAdminError ? [e.message, ...e.issues].filter(Boolean).join(' · ') : String(e))
    }).finally(() => setBusy(''))
  }

  return (
    <Modal title={tx('供应商', 'Providers')} className="ca-rename ca-rename--key ca-provider" onClose={close}>
      <div className="ca-rename__body" data-testid="provider-admin">
        <p className="ca-provider__status" data-testid="provider-scope">
          {tx('设置页。不保存就不改变现在的生成和对话。价格未知不会被当成已确认的费用。', 'Settings only. Nothing changes until you save. An unknown price is not treated as a confirmed charge.')}
        </p>
        {forbidden && <div className="ca-provider__banner" role="alert" data-testid="provider-forbidden">{tx('只有管理员可以查看和保存。', 'Only an admin can view and save this.')}</div>}
        {state?.image.ignored && <div className="ca-provider__banner" role="status">{tx('旧的图像配置无法识别，已忽略，仍走现有路由。', 'The stored image setup could not be read and was ignored. The current route stays.')}</div>}
        {state && !forbidden && (
          <>
            <ImageSection
              state={state}
              providerId={imageProvider}
              info={imageInfo}
              models={imageModels}
              message={imageMsg}
              err={imageErr}
              busy={busy === 'image'}
              onProvider={(id) => { setImageProvider(id); setImageMsg('') }}
              onModel={(cap, id) => { setImageModels({ ...imageModels, [cap]: id }); setImageMsg('') }}
              onSave={saveImage}
              onRestore={() => {
                setBusy('image')
                restoreImageProvider().then((next) => { setState(next); applyImage(next); setImageMsg(tx('已恢复上一份图像配置。', 'Restored the previous image setup.')) }).catch((e: unknown) => setImageErr(String(e))).finally(() => setBusy(''))
              }}
            />
            <LlmSection
              state={state}
              providerId={llmProvider}
              info={llmInfo}
              model={llmPicked}
              modelId={llmModel}
              message={llmMsg}
              err={llmErr}
              busy={busy === 'llm'}
              onProvider={(id) => {
                setLlmProvider(id)
                const next = state.llm.providers.find((p) => p.id === id)
                setLlmModel(next?.models[0]?.id || 'existing')
                setLlmMsg('')
              }}
              onModel={(id) => { setLlmModel(id); setLlmMsg('') }}
              onSave={saveLlm}
              onRestore={() => {
                setBusy('llm')
                restoreLlmProvider().then((next) => { setState(next); applyLlm(next); setLlmMsg(tx('已恢复上一份语言模型配置。', 'Restored the previous language-model setup.')) }).catch((e: unknown) => setLlmErr(String(e))).finally(() => setBusy(''))
              }}
            />
            <AuditSection state={state} />
          </>
        )}
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{tx('关闭', 'Close')}</button>
        </div>
      </div>
    </Modal>
  )
}

function ImageSection({
  state, providerId, info, models, message, err, busy, onProvider, onModel, onSave, onRestore,
}: {
  state: ProviderAdminState
  providerId: string
  info: ImageProviderInfo | undefined
  models: Record<string, string>
  message: string
  err: string
  busy: boolean
  onProvider: (id: string) => void
  onModel: (cap: string, id: string) => void
  onSave: () => void
  onRestore: () => void
}) {
  const active = state.image.active
  const dirty = providerId !== (active?.provider || 'wavespeed')
    || (providerId === 'replicate' && CAPS.some((cap) => models[cap] !== active?.models?.[cap]))
  const savedLabel = !state.image.saved
    ? tx('未保存。图像仍走现有 WaveSpeed 路由。', 'Not saved. Images still use the current WaveSpeed route.')
    : active?.provider === 'wavespeed'
      ? tx('已保存 WaveSpeed。行为与现有路由相同。', 'WaveSpeed is saved. Behavior matches the current route.')
      : tx(`已保存 Replicate。新的四类图像任务使用它。版本 ${state.image.revision}。`, `Replicate is saved. New jobs in the four image types use it. Revision ${state.image.revision}.`)
  return (
    <section className="ca-provider__section" data-testid="provider-image">
      <h3 className="ca-provider__h">{tx('图像', 'Images')}</h3>
      <p className="ca-provider__status" data-testid="provider-image-status">{savedLabel}</p>
      <div className="ca-provider__cards">
        {state.image.providers.map((provider) => (
          <button key={provider.id} type="button" className="ca-provider__card" data-on={providerId === provider.id || undefined} data-testid={`provider-image-${provider.id}`} onClick={() => onProvider(provider.id)}>
            <strong>{lt(provider.label)}</strong>
            <span className="ca-provider__status">{provider.configured ? tx('密钥已配置', 'Key configured') : tx('密钥未配置', 'Key not configured')}{provider.secret_env ? ` · ${provider.secret_env}` : ''}</span>
            <span className="ca-provider__status">{lt(provider.note)}</span>
          </button>
        ))}
      </div>
      <div className="ca-provider__caps" data-testid="provider-image-caps">
        {CAPS.map((cap) => {
          const wave = state.image.providers.find((p) => p.id === 'wavespeed')?.capabilities[cap]
          const replicate = info?.id === 'replicate'
          const options = (info?.models || []).filter((m) => m.capabilities.includes(cap)).map((m) => ({ id: m.id, label: m.label }))
          const supported = replicate ? options.length > 0 : !!wave?.supported
          return (
            <div key={cap} className="ca-provider__cap" data-testid={`provider-cap-${cap}`}>
              <span>{tx(CAP_LABEL[cap][0], CAP_LABEL[cap][1])}</span>
              <span className="ca-provider__badge" data-ok={supported ? '1' : '0'}>{supported ? tx('可选', 'Available') : tx('不支持', 'Unsupported')}</span>
              {replicate && supported && (
                <FieldSelect value={models[cap] || ''} options={options} onChange={(id) => onModel(cap, id)} />
              )}
              {!supported && <span className="ca-provider__status">{lt(wave?.reason) || tx('禁选', 'Disabled')}</span>}
            </div>
          )
        })}
      </div>
      {info?.id === 'replicate' && <p className="ca-provider__status" data-testid="provider-image-quote">{tx('报价：未知。保存后新任务会在发送前停止，不能把未知价格确认成一笔费用。', 'Quote: unknown. After save, a new job stops before it is sent. An unknown price cannot be confirmed as a charge.')}</p>}
      <pre className="ca-provider__preview" data-testid="provider-image-preview">{imagePreview(state, providerId, models, dirty)}</pre>
      {message && <div className="ca-provider__banner" role="status" data-testid="provider-image-saved">{message}</div>}
      {err && <div className="ca-provider__banner" role="alert" data-testid="provider-image-error">{err}</div>}
      <div className="ca-panel__foot">
        <button type="button" className="ca-panel__secondary" data-testid="provider-image-restore" disabled={!state.image.can_restore || busy} onClick={onRestore}>{tx('恢复上一份', 'Restore previous')}</button>
        <button type="button" className="ca-panel__primary" data-testid="provider-image-save" disabled={busy || !dirty} onClick={onSave}>{busy ? tx('保存中', 'Saving') : tx('保存图像供应商', 'Save image provider')}</button>
      </div>
    </section>
  )
}

function imagePreview(state: ProviderAdminState, providerId: string, models: Record<string, string>, dirty: boolean) {
  if (!dirty) {
    return [
      tx('没有未保存的图像变更。', 'No unsaved image change.'),
      state.image.saved
        ? tx('上面的状态是已经生效的配置。进行中的任务不变。', 'The status above is the active setup. Running jobs stay as they are.')
        : tx('未保存。图像仍走现有 WaveSpeed 路由。', 'Not saved. Images still use the current WaveSpeed route.'),
    ].join('\n')
  }
  const lines = [
    tx('保存前的变更范围', 'What save will change'),
    providerId === (state.image.active?.provider || 'wavespeed') && providerId === 'wavespeed'
      ? tx('图像路由：不变。', 'Image route: unchanged.')
      : tx(`图像路由：新任务改为 ${providerId}。进行中的任务不变。`, `Image route: new jobs change to ${providerId}. Running jobs stay.`),
  ]
  if (providerId === 'replicate') {
    for (const cap of CAPS) lines.push(`${tx(CAP_LABEL[cap][0], CAP_LABEL[cap][1])}: ${models[cap] || tx('未选', 'not chosen')} · ${tx('价格未知', 'price unknown')}`)
    lines.push(tx('视频、放大、音乐等不在这份设置里，仍走 WaveSpeed。', 'Video, upscale, music and the rest are not in this setting and stay on WaveSpeed.'))
    lines.push(tx('不会在失败后自动改走另一个供应商。', 'A failure does not automatically try the other provider.'))
  }
  return lines.join('\n')
}

function LlmSection({
  state, providerId, info, model, modelId, message, err, busy, onProvider, onModel, onSave, onRestore,
}: {
  state: ProviderAdminState
  providerId: string
  info: LlmProviderInfo | undefined
  model: LlmModel | undefined
  modelId: string
  message: string
  err: string
  busy: boolean
  onProvider: (id: string) => void
  onModel: (id: string) => void
  onSave: () => void
  onRestore: () => void
}) {
  const active = state.llm.active
  const dirty = providerId !== (active?.provider || 'wavespeed') || modelId !== (active?.model || 'existing')
  const savedLabel = !state.llm.saved
    ? tx('未保存。对话仍用 WaveSpeed 上的 deepseek/deepseek-v4.1-flash-1017。', 'Not saved. Chat still uses deepseek/deepseek-v4.1-flash-1017 on WaveSpeed.')
    : active?.provider === 'wavespeed'
      ? tx('已保存现有 WaveSpeed 配置。活动路由没有改。', 'The current WaveSpeed setup is saved. The live route did not change.')
      : tx(`已保存 ${active?.provider} / ${active?.model}。只有新对话使用它。`, `Saved ${active?.provider} / ${active?.model}. Only new chats use it.`)
  return (
    <section className="ca-provider__section" data-testid="provider-llm">
      <h3 className="ca-provider__h">{tx('语言模型', 'Language model')}</h3>
      <p className="ca-provider__status" data-testid="provider-llm-status">{savedLabel}</p>
      <div className="ca-provider__cards">
        {state.llm.providers.map((provider) => (
          <button key={provider.id} type="button" className="ca-provider__card" data-on={providerId === provider.id || undefined} data-testid={`provider-llm-${provider.id}`} onClick={() => onProvider(provider.id)}>
            <strong>{lt(provider.label)}</strong>
            <span className="ca-provider__status">{provider.mode === 'existing' ? tx('使用现有密钥和地址', 'Uses the current key and endpoint') : provider.configured ? tx('密钥已配置', 'Key configured') : tx('密钥未配置，保存后新对话会安全失败', 'Key not configured. After save, a new chat fails closed.')}{provider.secret_env ? ` · ${provider.secret_env}` : ''}</span>
            {provider.base_url && <span className="ca-provider__status">{provider.base_url}</span>}
          </button>
        ))}
      </div>
      <FieldSelect
        value={modelId}
        options={(info?.models || []).map((item) => ({ id: item.id, label: lt(item.label) }))}
        onChange={onModel}
      />
      {model && <p className="ca-provider__status" data-testid="provider-llm-note">{lt(model.note)}</p>}
      {model && !model.passthrough && (
        <ul className="ca-provider__diff" data-testid="provider-llm-diff">
          {model.differences.map((item) => <li key={lt(item)}>{lt(item)}</li>)}
          <li data-testid="provider-llm-price">{tx('价格：未知', 'Price: unknown')}</li>
          <li data-testid="provider-llm-probe">{tx('连通测试默认关闭。自费探测需要另作确认，这个页面不会发起。', 'A connectivity test stays off. A paid probe needs its own confirmation. This page does not start one.')}</li>
        </ul>
      )}
      <pre className="ca-provider__preview" data-testid="provider-llm-preview">{llmPreview(state, providerId, modelId, dirty)}</pre>
      {message && <div className="ca-provider__banner" role="status" data-testid="provider-llm-saved">{message}</div>}
      {err && <div className="ca-provider__banner" role="alert" data-testid="provider-llm-error">{err}</div>}
      <div className="ca-panel__foot">
        <button type="button" className="ca-panel__secondary" data-testid="provider-llm-restore" disabled={!state.llm.can_restore || busy} onClick={onRestore}>{tx('恢复上一份', 'Restore previous')}</button>
        <button type="button" className="ca-panel__primary" data-testid="provider-llm-save" disabled={busy || !dirty} onClick={onSave}>{busy ? tx('保存中', 'Saving') : tx('保存语言模型', 'Save language model')}</button>
      </div>
    </section>
  )
}

function llmPreview(state: ProviderAdminState, providerId: string, modelId: string, dirty: boolean) {
  if (!dirty) return tx('这份选择和已生效的配置相同。不点保存不会写入。', 'This matches the active setup. It is not written until you save.')
  const active = state.llm.active
  return [
    tx('尚未保存，活动配置不变。', 'Not saved yet. The active setup is unchanged.'),
    tx(`当前生效：${active?.provider || 'wavespeed'} / ${active?.model || 'existing'}`, `Active now: ${active?.provider || 'wavespeed'} / ${active?.model || 'existing'}`),
    tx(`保存后新对话：${providerId} / ${modelId}`, `After save, new chats: ${providerId} / ${modelId}`),
    tx('进行中的对话保持开始时锁定的地址和模型。失败不会改走另一个供应商。', 'A chat already running keeps the endpoint and model it locked at the start. Failure does not switch provider.'),
  ].join('\n')
}

function AuditSection({ state }: { state: ProviderAdminState }) {
  const counts = state.audit.summary.model_counts
  return (
    <section className="ca-provider__section" data-testid="provider-audit">
      <h3 className="ca-provider__h">{tx('覆盖审计', 'Coverage audit')}</h3>
      <p className="ca-provider__status" data-testid="provider-audit-note">{lt(state.audit.note)} {state.audit.summary.checked_at}</p>
      <p className="ca-provider__status" data-testid="provider-audit-counts">
        {tx(
          `精选模型 ${state.audit.summary.models_listed}。可映射 ${counts.mapped_with_differences || 0}。同能力不同模型 ${counts.same_capability_different_model || 0}。未定位 ${counts.not_found_in_this_audit || 0}。`,
          `${state.audit.summary.models_listed} curated models. Mapped ${counts.mapped_with_differences || 0}. Same capability, different model ${counts.same_capability_different_model || 0}. Not located ${counts.not_found_in_this_audit || 0}.`,
        )}
      </p>
      <ul className="ca-provider__diff">
        {state.audit.summary.capabilities.map((row) => (
          <li key={`${row.provider}-${row.capability}`} data-implemented={row.implemented ? '1' : '0'}>
            {row.implemented ? tx('已实现', 'Implemented') : tx('仅审计', 'Audit only')} · {row.provider} · {row.capability} · {row.quote === 'unknown' ? tx('价格未知', 'price unknown') : row.quote}
          </li>
        ))}
      </ul>
    </section>
  )
}
