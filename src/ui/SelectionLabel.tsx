import { useEditor, useValue } from 'tldraw'

import { genInfoOf, targetSize } from '../generate'
import { autoPillLabel, autoPillTooltip } from '../autoPill'
import { GENERATOR } from '../shapes/GeneratorShape'
import { isVideo } from '../models'
import { Icons } from './icons'
import { useSelectionRect } from './selection'
import { lang, t } from '../i18n'

export function SelectionLabel() {
  const editor = useEditor()
  const rect = useSelectionRect()
  const info = useValue('selection label', () => {
    const shape = editor.getOnlySelectedShape()
    if (!shape) return null
    if (shape.type === 'image' || shape.type === 'video') {
      const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
      if (asset?.type !== shape.type) return null
      const choice = genInfoOf(shape)?.modelChoice
      const model = autoPillLabel(choice)
      return {
        name: asset.props.name || (shape.type === 'video' ? t('common.video') : t('common.image')),
        size: `${asset.props.w} × ${asset.props.h}`,
        video: shape.type === 'video',
        model,
        modelTitle: autoPillTooltip(choice, lang) ?? undefined,
      }
    }
    if (shape.type === GENERATOR) {
      const [w, h] = targetSize(shape.props)
      const video = isVideo(shape.props.workflow)
      const choice = genInfoOf(shape)?.modelChoice || (shape.meta.modelChoice as import('../autoPill').ModelChoice | undefined)
      const model = autoPillLabel(choice)
      return { name: video ? t('selectionLabel.videoGenerator') : t('selectionLabel.imageGenerator'), size: `${w} × ${h}`, video, model: model ?? undefined, modelTitle: autoPillTooltip(choice, lang) ?? undefined }
    }
    return null
  }, [editor])
  if (!rect || !info) return null
  return (
    <div className="ca-label" style={{ left: rect.l, top: rect.t - 22, width: rect.r - rect.l }}>
      <span className="ca-label__icon">{info.video ? Icons.video : Icons.image}</span>
      <span className="ca-label__name">{info.name}</span>
      {info.model && <span className="ca-label__model" data-testid="auto-model-label" title={info.modelTitle}>{info.model}</span>}
      <span className="ca-label__size">{info.size}</span>
    </div>
  )
}
