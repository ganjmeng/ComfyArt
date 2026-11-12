import { useEffect } from 'react'
import { atom, useToasts, useValue } from 'tldraw'

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
  useEffect(() => {
    if (!error) return
    const [title, ...rest] = error.text.split('\n')
    toasts.addToast({ id: `error-${error.n}`, title, description: rest.join('\n') || undefined, severity: error.severity })
  }, [error, toasts])
  return null
}
