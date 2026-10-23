import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue } from 'tldraw'

import { refKind, thumbUrl, uploadImage, viewUrl, type RefKind } from '../comfy'
import { planStoryboard } from '../agent'
import { baseOf, colorsOf, estimateInputsOf, featureModelsOf, generate, refOverflow, lastFrameOf, motionOf, refsOf, scenesOf, speechOf, targetSize, videoModeOf } from '../generate'
import { canvasPickAtom, fillTarget, isMediaRefs, maxRefsOf, type Target } from '../genInputs'
import { itemImages, libraryAtom } from '../library'
import { DEFAULT_STRENGTH, modeOf, modesFor, refControlsOf, refModeFor, refModesOf, refStrengthsOf, usableRefs } from '../refModes'
import { RefControls } from './RefControls'
import { errorText, jobOf } from '../jobs'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { adjustForModel, agentModels, AUTO_IMAGE, AUTO_VIDEO, isVideo, modelOf } from '../models'
import { AssetGrid } from './AssetPicker'
import { ColorPicker } from './ColorPicker'
import { AdvancedPill } from './GenAdvanced'
import { CUSTOM_GENERATE } from '../customWorkflows'
import { ModelPill, SettingsPill } from './GenSettings'
import { Icons } from './icons'
import { StoryboardEditor } from './StoryboardEditor'
import { Popover } from './Popover'
import { useElementSize, useSelectedGenerator, useSelectionRect } from './selection'
import { t } from '../i18n'
import { isEnter } from './keys'
import { estimateCost, keyStatusAtom, outOfCredit } from '../wavespeedKey'

const GAP = 12
const EDGE = 8

const TAGS: Record<RefKind, string> = { image: 'genPanel.tagImage', video: 'genPanel.tagVideo', audio: 'genPanel.tagAudio' }

function RefMedia({ src }: { src: string }) {
  const kind = refKind(src)
  if (kind === 'video') return <video src={src} muted preload="metadata" />
  if (kind === 'audio') return <span className="ca-gen__refaudio ca-icon">{Icons.music}</span>
  return <img src={src} alt="" />
}

export function GenPanel({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const shape = useSelectedGenerator()
  const rect = useSelectionRect()
  const panel = useRef<HTMLDivElement>(null)
  const prompt = useRef<HTMLTextAreaElement>(null)
  const size = useElementSize(panel, { w: 540, h: 160 })
  const [pick, setPick] = useState<{ to: Target; view: 'menu' | 'assets' | 'library' } | null>(null)
  const [modeOpen, setModeOpen] = useState<string | null>(null)
  const [adjusted, setAdjusted] = useState(false)
  const [smart, setSmart] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  const uploadTo = useRef<Target>('ref')
  const running = useValue('gen running', () => !!(shape && jobOf(editor.getShape(shape.id) ?? shape)), [editor, shape])
  const canvasPick = useValue(canvasPickAtom)
  const library = useValue('library images', () => libraryAtom.get().filter((x) => itemImages(x).length), [])

  useEffect(() => { prompt.current?.focus() }, [shape?.id])

  const noCredit = outOfCredit(useValue(keyStatusAtom))
  const estKey = useValue('gen estimate inputs', () => {
    const s = shape && editor.getShape<GeneratorShape>(shape.id)
    const inputs = s ? estimateInputsOf(s) : null
    return inputs ? JSON.stringify(inputs) : ''
  }, [editor, shape?.id])
  const [estimate, setEstimate] = useState<number | null>(null)
  useEffect(() => {
    setEstimate(null)
    if (!estKey) return
    let live = true
    // debounced; the backend caches each WaveSpeed quote for 5 minutes
    const timer = setTimeout(() => { estimateCost(JSON.parse(estKey)).then((e) => { if (live) setEstimate(e?.price ?? null) }).catch(() => {}) }, 300)
    return () => { live = false; clearTimeout(timer) }
  }, [estKey])
  if (!shape || !rect || running || canvasPick) return null
  const p = shape.props
  const update = (patch: Partial<GeneratorShape['props']>) => {
    const next = { ...p, ...patch }
    if (patch.ratio || patch.cw || patch.ch || patch.resolution || patch.workflow) {
      const [w, h] = targetSize(next)
      Object.assign(next, { w, h })
    }
    editor.updateShape<GeneratorShape>({ id: shape.id, type: shape.type, props: next })
  }
  const video = isVideo(p.workflow)
  const refs = refsOf(shape)
  const vmode = video ? (Array.isArray(shape.meta.scenes) ? 'story' : videoModeOf(shape)) : null
  const maxRefs = maxRefsOf(shape)
  const motion = motionOf(shape)
  const speech = speechOf(shape)
  const modes = refModesOf(shape)
  const strengths = refStrengthsOf(shape)
  const controls = refControlsOf(shape)
  const colors = colorsOf(shape)
  const setMeta = (patch: Record<string, unknown>) => editor.updateShape<GeneratorShape>({ id: shape.id, type: shape.type, meta: { ...shape.meta, ...patch } as GeneratorShape['meta'] })
  const setRefs = (next: string[]) => setMeta({ refs: next })
  const setColors = (next: string[]) => setMeta({ colors: next })
  const base = baseOf(shape)
  const last = lastFrameOf(shape)
  const media = isMediaRefs(shape)
  const firstImage = refs.filter((x) => refKind(x) === 'image').slice(0, 1)
  const fill = (to: Target, srcs: string[]) => fillTarget(editor, shape.id, to, srcs)
  const upload = async (files: FileList | null) => {
    const to = uploadTo.current
    const srcs: string[] = []
    for (const f of Array.from(files ?? []).slice(0, to === 'ref' ? undefined : 1)) srcs.push(viewUrl(await uploadImage(f, f.name)))
    await fill(to, srcs)
  }
  const accepts: Partial<Record<Target, string>> = { motion: 'video/*', speech: 'audio/*', ...(media ? { ref: 'image/*,video/*,audio/*' } : {}) }
  const assetKind = (to: Target) => (to === 'motion' ? 'video' : to === 'speech' ? null : to === 'ref' && media ? 'all' : 'image')
  const pickFailed = (e: unknown) => onError(errorText(e))
  const imagePicker = (to: Target, label: string) => {
    const kind = assetKind(to)
    const icon = to === 'motion' ? Icons.video : to === 'speech' ? Icons.music : Icons.image
    return (
      <Popover
        open={pick?.to === to}
        onOpenChange={(o) => setPick(o ? { to, view: 'menu' } : null)}
        contentKey={pick?.to === to ? pick.view : 'menu'}
        trigger={({ toggle }) => (
          <button type="button" className="ca-gen__refadd" title={label} onClick={toggle}>
            <span className="ca-icon">{icon}</span><span>{label}</span>
          </button>
        )}
      >
        {pick?.view === 'assets' && kind ? (
          <div className="ca-menu ca-assets-pop"><AssetGrid only={kind === 'all' ? undefined : kind} onPick={(item) => { setPick(null); fill(to, [item.src]).catch(pickFailed) }} /></div>
        ) : pick?.view === 'library' ? (
          <div className="ca-menu ca-assets-pop ca-libpick">
            {library.map((item) => (
              <div key={item.id}>
                <div className="ca-gen__label">{item.name}</div>
                <div className="ca-assets__grid">
                  {itemImages(item).map((src) => (
                    <button key={src} type="button" className="ca-side__cell" onClick={() => { setPick(null); fill(to, [src]).catch(pickFailed) }}><img src={thumbUrl(src)} alt="" loading="lazy" /></button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="ca-menu">
            <button type="button" className="ca-menu__item" onClick={() => { setPick(null); uploadTo.current = to; if (file.current) { file.current.multiple = to === 'ref'; file.current.accept = accepts[to] ?? 'image/*'; file.current.click() } }}>
              <span className="ca-icon">{Icons.upload}</span><span className="ca-menu__grow">{kind === 'image' ? t('genPanel.uploadImage') : t('genPanel.uploadFile')}</span>
            </button>
            {kind && (
              <button type="button" className="ca-menu__item" onClick={() => setPick({ to, view: 'assets' })}>
                <span className="ca-icon">{Icons.files}</span><span className="ca-menu__grow">{t('genPanel.chooseFromAssets')}</span><span className="ca-icon">{Icons.next}</span>
              </button>
            )}
            {(kind === 'image' || kind === 'all') && library.length > 0 && (
              <button type="button" className="ca-menu__item" onClick={() => setPick({ to, view: 'library' })}>
                <span className="ca-icon">{Icons.folder}</span><span className="ca-menu__grow">{t('genPanel.chooseFromLibrary')}</span><span className="ca-icon">{Icons.next}</span>
              </button>
            )}
            <button type="button" className="ca-menu__item" onClick={() => { setPick(null); canvasPickAtom.set({ id: shape.id, to }) }}>
              <span className="ca-icon">{Icons.select}</span><span className="ca-menu__grow">{t('genPanel.chooseFromCanvas')}</span>
            </button>
          </div>
        )}
      </Popover>
    )
  }
  const slot = (src: string, label: string, clear: () => void) => (
    <span className="ca-gen__ref"><RefMedia src={src} /><span className="ca-gen__refmode">{label}</span><button type="button" title={t('common.remove')} onClick={clear}>{Icons.close}</button></span>
  )

  const story = video && Array.isArray(shape.meta.scenes)
  const scenes = scenesOf(shape)
  const ready = story ? scenes.some((sc) => sc.prompt.trim())
    : vmode === 'motion' ? !!(refs[0] && motion)
      : vmode === 'lipsync' ? !!(refs[0] && speech)
        : !!p.prompt.trim()
  const setScenes = (next: typeof scenes | null) => setMeta({ scenes: next })
  const smartSplit = async () => {
    setSmart(true)
    try {
      const planned = await planStoryboard(scenes.map((sc) => sc.prompt).filter(Boolean).join('\n'))
      if (planned.length) setScenes(planned)
    } catch (e) {
      onError(errorText(e))
    } finally {
      setSmart(false)
    }
  }
  const submit = () => {
    if (!ready) return
    generate(editor, shape, onError).catch((e) => onError(errorText(e)))
  }

  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - size.w / 2, EDGE), host.width - size.w - EDGE)
  const floor = host.height - 72 - size.h
  const top = Math.max(EDGE, Math.min(rect.b + GAP, floor))
  const model = modelOf(p.workflow) ?? modelOf(video ? AUTO_VIDEO : AUTO_IMAGE)!
  const overflow = video ? null : refOverflow(shape)
  const available = modesFor(model)
  const modeFor = (src: string) => refModeFor(model, modes[src])?.id
  const used = usableRefs(model, refs, modes).map((r) => r.src)
  const unusedReason = (src: string) => available.length
    ? t('genPanel.refModeNotSupported', model.label, modeOf(modes[src]).label)
    : t('genPanel.refNotSupported', model.label)

  return (
    <div ref={panel} className="ca-gen" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()} onWheel={(e) => e.stopPropagation()}>
      <div className="ca-gen__refs">
        {refs.map((src) => (
          <span key={src} className="ca-gen__ref" data-off={video || used.includes(src) ? undefined : true} title={video || used.includes(src) ? undefined : unusedReason(src)}>
            <RefMedia src={src} />
            {!video && used.includes(src) && <span className="ca-gen__refnum">{used.indexOf(src) + 1}</span>}
            {media && <span className="ca-gen__refnum">{t(TAGS[refKind(src)], refs.filter((x) => refKind(x) === refKind(src)).indexOf(src) + 1)}</span>}
            <button type="button" title={t('common.remove')} onClick={() => setRefs(refs.filter((x) => x !== src))}>{Icons.close}</button>
            {!video && !available.length && <span className="ca-gen__refmode">{t('genPanel.refUnused')}</span>}
            {!video && available.length > 0 && (
              <Popover
                open={modeOpen === src}
                onOpenChange={(o) => setModeOpen(o ? src : null)}
                trigger={({ toggle }) => <span className="ca-gen__refmode" onClick={toggle}>{used.includes(src) ? modeOf(modeFor(src)).label : t('genPanel.refUnused')}</span>}
              >
                <div className="ca-menu ca-refmodes">
                  {[t('common.reference'), t('refModes.structure'), t('refModes.color')].map((group) => available.some((m) => m.group === group) && (
                    <div key={group}>
                      <div className="ca-gen__label">{group}</div>
                      {available.filter((m) => m.group === group).map((m) => (
                        <button key={m.id} type="button" className="ca-menu__item" onClick={() => setMeta({ refModes: { ...modes, [src]: m.id } })}>
                          <span className="ca-menu__grow">{m.label}{m.download && <span className="ca-model__tag">{t('genPanel.modelWillDownloadOnFirst')}</span>}</span>
                          {modeFor(src) === m.id && <span className="ca-icon">{Icons.check}</span>}
                        </button>
                      ))}
                    </div>
                  ))}
                  {model.control && modeOf(modeFor(src)).control && (
                    <>
                      <label className="ca-panel__row">
                        <span>{t('genPanel.referenceStrength')}</span>
                        <input type="range" min={10} max={150} value={strengths[src] ?? DEFAULT_STRENGTH} onChange={(e) => setMeta({ refStrengths: { ...strengths, [src]: Number(e.target.value) } })} />
                        <span className="ca-panel__val">{strengths[src] ?? DEFAULT_STRENGTH}</span>
                      </label>
                      <RefControls src={src} mode={modeOf(modeFor(src))} value={controls[src]} onChange={(c) => setMeta({ refControls: { ...controls, [src]: c } })} onError={onError} />
                    </>
                  )}
                </div>
              </Popover>
            )}
          </span>
        ))}
        {refs.length < maxRefs && (video || available.length > 0) && imagePicker('ref', media ? t('genPanel.addReference')
          : vmode === 'motion' ? t('genPanel.character')
            : vmode === 'lipsync' ? t('genPanel.portrait')
              : video ? t('genPanel.firstFrame') : t('genPanel.referenceImage'))}
        {!video && (
          <div className="ca-gen__colors">
            {colors.map((c, i) => (
              <span key={i} className="ca-gen__color">
                <ColorPicker value={c} title={t('genPanel.colorReference')} onChange={(v) => setColors(colors.map((x, j) => (j === i ? v : x)))} />
                <button type="button" title={t('common.remove')} onClick={() => setColors(colors.filter((_, j) => j !== i))}>{Icons.close}</button>
              </span>
            ))}
            <button type="button" className="ca-gen__refadd" title={t('genPanel.colorReference')} onClick={() => setColors([...colors, '#1E88E5'])}>
              <span className="ca-icon">{Icons.palette}</span><span>{t('genPanel.colorReference')}</span>
            </button>
          </div>
        )}
        {vmode === 'frames' && (last ? slot(last, t('genPanel.lastFrame'), () => setMeta({ lastFrame: null })) : imagePicker('last', t('genPanel.lastFrame')))}
        {vmode === 'motion' && (motion ? slot(motion, t('genPanel.motionVideo'), () => setMeta({ motion: null })) : imagePicker('motion', t('genPanel.motionVideo')))}
        {vmode === 'lipsync' && (speech ? slot(speech, t('genPanel.speechAudio'), () => setMeta({ speech: null })) : imagePicker('speech', t('genPanel.speechAudio')))}
        {!video && model.id !== CUSTOM_GENERATE && (base ? slot(base.src, t('genPanel.baseImage'), () => setMeta({ base: null })) : imagePicker('base', t('genPanel.baseImage')))}
        <input ref={file} type="file" accept="image/*" hidden onChange={(e) => { void upload(e.target.files).catch((err) => onError(String(err))); e.target.value = '' }} />
      </div>
      {video && (
        <div className="ca-panel__chips ca-gen__modes">
          <button type="button" className="ca-panel__chip" data-on={vmode === 'frames' || undefined} onClick={() => setMeta({ scenes: null, videoMode: null, refs: firstImage })}>{t('genPanel.firstLastFrame')}</button>
          <button type="button" className="ca-panel__chip" data-on={media || undefined} onClick={() => setMeta({ scenes: null, videoMode: 'refs', lastFrame: null })}>{t('genPanel.referenceToVideo')}</button>
          <button type="button" className="ca-panel__chip" data-on={vmode === 'motion' || undefined} onClick={() => setMeta({ scenes: null, videoMode: 'motion', lastFrame: null, refs: firstImage })}>{t('genPanel.motionControl')}</button>
          <button type="button" className="ca-panel__chip" data-on={vmode === 'lipsync' || undefined} onClick={() => setMeta({ scenes: null, videoMode: 'lipsync', lastFrame: null, refs: firstImage })}>{t('genPanel.lipSync')}</button>
          <button type="button" className="ca-panel__chip" data-on={story || undefined} onClick={() => setMeta({ videoMode: null, scenes: scenes.length ? scenes : [{ prompt: p.prompt, duration: p.duration }] })}>{t('genPanel.storyboard')}</button>
        </div>
      )}
      {base && !video && (
        <label className="ca-panel__row"><span>{t('genPanel.strength')}</span><input type="range" min={10} max={100} value={base.strength} onChange={(e) => setMeta({ strength: Number(e.target.value) })} /><span className="ca-panel__val">{base.strength}</span></label>
      )}
      {story ? <StoryboardEditor scenes={scenes} onChange={setScenes} onSmart={() => void smartSplit()} smartBusy={smart} /> : <textarea
        ref={prompt}
        className="ca-gen__prompt"
        value={p.prompt}
        placeholder={t('genPanel.whatDoYouWantTo')}
        onChange={(e) => update({ prompt: e.target.value })}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (isEnter(e) && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
      />}
      {(adjusted || overflow != null) && (
        <div className="ca-gen__notice" role="status" data-testid="gen-notice">
          {[adjusted && t('genPanel.adjusted'), overflow != null && t('genPanel.refsCapped', overflow)].filter(Boolean).join(' · ')}
        </div>
      )}
      <div className="ca-gen__foot">
        <SettingsPill p={p} video={video} quality={!!model.steps} tiers={model.qualities} caps={model} update={update} />
        <AdvancedPill shape={shape} model={model} setMeta={setMeta} />
        <div className="ca-gen__spacer" />
        <ModelPill video={video} model={model} picks={featureModelsOf(shape)}
          onPick={(f, id) => {
            if (f !== 'text_to_image' && f !== 'text_to_video') return setMeta({ featureModels: { ...featureModelsOf(shape), [f]: id } })
            const patch = adjustForModel(p, modelOf(id), video)
            setAdjusted(Object.keys(patch).length > 0)
            update({ workflow: id, ...patch })
          }}
          onAuto={(on) => {
            if (on) setMeta({ featureModels: {} })
            const id = on ? (video ? AUTO_VIDEO : AUTO_IMAGE) : agentModels(video)[0].id
            const patch = adjustForModel(p, modelOf(id), video)
            setAdjusted(Object.keys(patch).length > 0)
            update({ workflow: id, ...patch })
          }} />
        {estimate != null && <span className="ca-gen__est" data-testid="ws-estimate" title={t('wsKey.estimate', `$${estimate}`)}>{`≈$${estimate < 0.01 ? estimate.toFixed(4).replace(/0+$/, '') : estimate.toFixed(2)}`}</span>}
        <button type="button" className="ca-gen__send" disabled={!ready || noCredit} title={noCredit ? t('wsKey.needCredit') : estimate != null ? `${t('common.generate')} · ${t('wsKey.estimate', `$${estimate}`)}` : t('common.generate')} onClick={submit}>
          <span className="ca-icon">{Icons.send}</span>
        </button>
      </div>
    </div>
  )
}
