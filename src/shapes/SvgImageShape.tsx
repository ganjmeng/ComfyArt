import { HTMLContainer, ImageShapeUtil, type TLImageShape } from 'tldraw'

import { t } from '../i18n'

function svgMeta(asset: { meta?: Record<string, unknown> } | null | undefined) {
  const meta = asset?.meta
  return {
    state: typeof meta?.svgState === 'string' ? meta.svgState : '',
    message: typeof meta?.svgMessage === 'string' ? meta.svgMessage : '',
  }
}

/** Canvas face for an admitted SVG. The download stays the original file. */
export class ComfyImageShapeUtil extends ImageShapeUtil {
  override component(shape: TLImageShape) {
    const asset = shape.props.assetId ? this.editor.getAsset(shape.props.assetId) : null
    const { state, message } = svgMeta(asset)
    if (state === 'preview_failed') {
      return (
        <HTMLContainer
          id={shape.id}
          className="ca-svg-fail"
          data-testid="svg-preview-failed"
          style={{ width: shape.props.w, height: shape.props.h, overflow: 'hidden' }}
        >
          <div className="ca-svg-fail__body">
            <svg className="ca-svg-fail__icon" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3.5" y="5" width="17" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path d="M7 15.5l3.2-3.2 2.3 2.3 2-2L18 16" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path d="M5 5l14 14" fill="none" stroke="currentColor" strokeWidth="1.6" />
            </svg>
            <span className="ca-svg-fail__text">{message || t('wsErr.svgPreviewFailed')}</span>
          </div>
        </HTMLContainer>
      )
    }
    const image = super.component(shape)
    if (state !== 'transparent') return image
    return (
      <div className="ca-svg-checker" data-testid="svg-checker" style={{ width: shape.props.w, height: shape.props.h }}>
        {image}
      </div>
    )
  }
}
