import { lockedDeliveryNotice, ratioLockOk } from '../../src/sizeLockPref.ts'

const SB = 'openai/gpt-image-2.6-sunburst/edit'
const meta = (w: number, h: number) => ({ sizeLockModel: SB, pixelSize: [w, h], sizeLockMode: 'ratio' })

const out = {
  qa1: lockedDeliveryNotice(meta(1536, 2048), [{ w: 1664, h: 2224 }]),
  qa2: lockedDeliveryNotice(meta(2048, 1536), [{ w: 2224, h: 1664 }]),
  exact1: ratioLockOk({ width: 1000, height: 1000 }, { width: 1010, height: 1000 }),
  over1: ratioLockOk({ width: 1000, height: 1000 }, { width: 10101, height: 10000 }),
  exact1_34: ratioLockOk({ width: 1536, height: 2048 }, { width: 1818, height: 2400 }),
  over1_34: ratioLockOk({ width: 1536, height: 2048 }, { width: 30303, height: 40000 }),
  short: lockedDeliveryNotice(meta(1536, 2048), [{ w: 768, h: 1024 }]),
  exactMismatch: lockedDeliveryNotice({ sizeLockModel: 'wavespeed-ai/qwen-image-2.0/text-to-image', pixelSize: [1584, 396] }, [{ w: 2048, h: 682 }]),
  unread: lockedDeliveryNotice(meta(1536, 2048), [{ w: 0, h: 0 }]),
  noLock: lockedDeliveryNotice({ pixelSize: [1536, 2048] }, [{ w: 768, h: 1024 }]),
}
console.log(JSON.stringify(out))
