import { useEffect, useRef } from 'react'
import { atom, useToasts, useValue } from 'tldraw'

import { resultsAtom } from '../jobs'

const errorAtom = atom<{ text: string; n: number; severity: 'error' | 'success' | 'info' } | null>('error', null)
let count = 0

export const reportError = (text: string) => errorAtom.set({ text, n: ++count, severity: 'error' })
export const reportSuccess = (text: string) => errorAtom.set({ text, n: ++count, severity: 'success' })
/** P1 hotfix (#911): light, non-blocking info toast (not error red, no action button),
 *  e.g. a charged image delivered off its target size. */
export const reportInfo = (text: string) => errorAtom.set({ text, n: ++count, severity: 'info' })

export function ErrorToasts() {
  const toasts = useToasts()
  const error = useValue(errorAtom)
  const results = useValue(resultsAtom)
  const seen = useRef(new Set<string>())
  useEffect(() => {
    if (!error) return
    const [title, ...rest] = error.text.split('\n')
    toasts.addToast({ id: `error-${error.n}`, title, description: rest.join('\n') || undefined, severity: error.severity })
  }, [error, toasts])
  // #911 P1: jobs.ts puts the size notice on the job result; the UI shows the info toast.
  useEffect(() => {
    for (const [id, r] of Object.entries(results)) {
      if (!r?.notice) continue
      const key = `${id}:${r.notice}`
      if (seen.current.has(key)) continue
      seen.current.add(key)
      reportInfo(r.notice)
    }
  }, [results])
  return null
}
