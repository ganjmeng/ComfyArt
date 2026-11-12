import { useEffect } from 'react'
import { atom, useToasts, useValue } from 'tldraw'

const errorAtom = atom<{ text: string; n: number; severity: 'error' | 'success' | 'warning' } | null>('error', null)
let count = 0

export const reportError = (text: string) => errorAtom.set({ text, n: ++count, severity: 'error' })
export const reportSuccess = (text: string) => errorAtom.set({ text, n: ++count, severity: 'success' })
/** P1 hotfix (#911): non-blocking notice, e.g. a charged image delivered off its target size. */
export const reportWarning = (text: string) => errorAtom.set({ text, n: ++count, severity: 'warning' })

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
