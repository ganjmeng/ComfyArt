// #128: requested video seconds round up to the model's next allowed duration (capped at the longest), stated in zh + en.
import { durationNote, fitDuration } from '../../src/genOptions'
import { tl } from './i18n_stub'

const zh = (k: string, ...a: (string | number)[]) => tl('zh', k, ...a)
const en = (k: string, ...a: (string | number)[]) => tl('en', k, ...a)
const asks = [undefined, 0, 3, 5, 7, 10, 12, 15, 20]
console.log(JSON.stringify({
  fit: asks.map((s) => fitDuration(s)),
  fitModel: [3, 5, 6, 9, 12].map((s) => fitDuration(s, [10, 5])),
  notes: [3, 7, 20, 10].map((s) => ({ zh: durationNote(s, fitDuration(s), undefined, zh), en: durationNote(s, fitDuration(s), undefined, en) })),
  none: durationNote(undefined, 5, undefined, en),
}))
