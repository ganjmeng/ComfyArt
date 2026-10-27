import { BRAND } from '../brand'

/** Canvas / home brand mark — SVG paths from brand config (theme via currentColor + --ca-float cutouts). */
export function BrandMark() {
  return (
    <span
      className="ca-brand-mark"
      role="img"
      aria-label={BRAND.name}
      dangerouslySetInnerHTML={{ __html: BRAND.logoSvg }}
    />
  )
}
