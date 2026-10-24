/** #192: one money format for every quote (the estimate next to Send and the cost confirm dialog): the quoted amount
 * to at most 4 decimals with trailing zeros trimmed but at least 2 kept, e.g. 0.039, 0.0893, 0.04, 0.10, 0.0035. */
export function usd(n: number): string {
  const s = (Number.isFinite(n) ? n : 0).toFixed(4).replace(/0+$/, '')
  const [i, d = ''] = s.split('.')
  return `${i}.${d.padEnd(2, '0')}`
}

/** #229: the Key dialog's confirm threshold always shows two decimals (0.5 -> "0.50"). */
export const thresholdUsd = (n: number) => (Number.isFinite(n) ? n : 0).toFixed(2)
