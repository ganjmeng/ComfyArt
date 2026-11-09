import { isOwnSizeError, lockedDeliveryError, lockedFileError, pickSizeModel, SIZE_LOCK_REFUSED } from '../../src/sizeLockPref.ts'

const QWEN = 'wavespeed-ai/qwen-image-2.0/text-to-image'
const SEEDREAM = 'bytedance/seedream-v5.0-lite/text-to-image'
const FLARE = 'openai/gpt-image-2.5-flare/text-to-image'
const listed = [FLARE, SEEDREAM]

const absent = pickSizeModel([QWEN], { auto: true, enabled: [FLARE] }, listed)
const disabled = pickSizeModel([SEEDREAM], { auto: false, enabled: [FLARE] }, listed)
const allDisabled = pickSizeModel([QWEN, SEEDREAM], { auto: false, enabled: [FLARE] }, listed)
const keepsOther = pickSizeModel([QWEN, SEEDREAM], { auto: false, enabled: [SEEDREAM] }, listed)
const permittedOffDropdown = pickSizeModel([QWEN], { auto: false, enabled: [QWEN] }, listed)
const mismatch = lockedFileError({ width: 1584, height: 396 }, { width: 2048, height: 682 })
const unread = lockedFileError({ width: 1584, height: 396 }, null)
const match = lockedFileError({ width: 1584, height: 396 }, { width: 1584, height: 396 })
const placed = lockedDeliveryError({ sizeLockModel: QWEN, pixelSize: [1584, 396] }, [{ w: 2048, h: 682 }])
const quiet = lockedDeliveryError({ pixelSize: [1024, 1024] }, [{ w: 512, h: 512 }])

const out = {
  absent, disabled, allDisabled, keepsOther, permittedOffDropdown,
  refused: SIZE_LOCK_REFUSED,
  mismatch, unread, match, placed, quiet,
  mismatchKept: !!mismatch && isOwnSizeError(mismatch),
  unreadKept: !!unread && isOwnSizeError(unread),
  refusedKept: isOwnSizeError(SIZE_LOCK_REFUSED),
}
console.log(JSON.stringify(out))
