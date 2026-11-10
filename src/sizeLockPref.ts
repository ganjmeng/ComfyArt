/** #707: a LinkedIn size lock may use a model that is not on the reference product dropdown.
 *  That absence is not a disable. Auto off is an allowlist (`enabled`): an id the
 *  user did not check is an active disable, and the lock must not turn it back on.
 *  Nothing here calls a provider. */

export interface SizePrefs { auto: boolean; enabled: readonly string[] }

export type SizeLockPick =
  | { ok: true; model: string; reason: 'not_in_dropdown' | 'auto' | 'checked' }
  | { ok: false; reason: 'disabled' }

export const SIZE_LOCK_REFUSED =
  '没有提交：没有可用的尺寸兼容模型。兼容模型已被关闭，不会改用默认模型，也没有生成。 / Not submitted: no size-compatible model is available. A disabled compatible model was not turned back on, the default model was not substituted, and nothing was submitted.'

/** First schema-compatible candidate the user still allows, or a refusal.
 *  Never returns an id that was not in `candidates` (the feature default is not a substitute). */
export function pickSizeModel(candidates: readonly string[], prefs: SizePrefs, listed: readonly string[]): SizeLockPick {
  const dropdown = new Set(listed)
  const ids = [...new Set(candidates.map((id) => id.trim()).filter(Boolean))]
  for (const id of ids) {
    if (prefs.auto) return { ok: true, model: id, reason: dropdown.has(id) ? 'auto' : 'not_in_dropdown' }
    if (prefs.enabled.includes(id)) return { ok: true, model: id, reason: 'checked' }
  }
  return { ok: false, reason: 'disabled' }
}

export function isOwnSizeError(msg: string): boolean {
  const text = msg.trim()
  // Completion mismatches and the pre-submit size-lock refusal must stay readable.
  // The command bus maps unknown errors to generic copy; these prefixes are ours.
  return text.startsWith('没有通过：') || text.startsWith('Not accepted:')
    || text.startsWith('没有提交：') || text.startsWith('Not submitted:')
}

/** Delivery gate. Null means the file pixels match the lock and may be placed.
 *  A mismatch or an unreadable file is an explicit fail: no stretch, crop, or retry. */
export function lockedFileError(want: { width: number; height: number }, got: { width: number; height: number } | null): string | null {
  if (!(want.width > 0) || !(want.height > 0)) {
    return '没有通过：尺寸已锁定，但没有可核对的宽高。没有拉伸，没有重试，没有换模型。 / Not accepted: size was locked but there was no pixel size to check. It was not stretched, retried, or sent to another model.'
  }
  if (!got || !(got.width > 0) || !(got.height > 0)) {
    return `没有通过：供应商原文件读不出像素，不能当成 ${want.width}×${want.height} 交付。没有拉伸，没有裁切，没有重试，没有换模型。 / Not accepted: the provider file has no readable pixels, so it was not delivered as ${want.width}×${want.height}. It was not stretched, cropped, retried, or sent to another model.`
  }
  if (got.width === want.width && got.height === want.height) return null
  return `没有通过：供应商原文件是 ${got.width}×${got.height}，锁定尺寸是 ${want.width}×${want.height}。没有拉伸，没有裁切，没有重试，没有换模型。 / Not accepted: the provider file is ${got.width}×${got.height} and the locked size is ${want.width}×${want.height}. It was not stretched, cropped, retried, or sent to another model.`
}

/** Canvas delivery. No size lock on the holder means this gate stays quiet. */
export function lockedDeliveryError(meta: { sizeLockModel?: unknown; pixelSize?: unknown } | null | undefined, media: { w: number; h: number }[]): string | null {
  if (!meta || typeof meta.sizeLockModel !== 'string' || !meta.sizeLockModel) return null
  const raw = meta.pixelSize
  const width = Array.isArray(raw) ? Math.round(Number(raw[0])) : 0
  const height = Array.isArray(raw) ? Math.round(Number(raw[1])) : 0
  const want = { width, height }
  if (!media.length) return lockedFileError(want, null)
  for (const item of media) {
    const got = item.w > 0 && item.h > 0 ? { width: item.w, height: item.h } : null
    const err = lockedFileError(want.width > 0 ? want : { width: 0, height: 0 }, got)
    if (err) return err
  }
  return null
}
