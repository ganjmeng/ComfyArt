import { useEffect, useState, type ReactNode } from 'react'

import { copyText } from '../clipboard'
import { Icons } from './icons'
import { t } from '../i18n'

const DONE_MS = 1500

export function CopyButton({ text, className = 'ca-history__del', testId, icon }: { text: string; className?: string; testId?: string; icon?: ReactNode }) {
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (!done) return
    const timer = setTimeout(() => setDone(false), DONE_MS)
    return () => clearTimeout(timer)
  }, [done])
  return (
    <button type="button" className={className} data-testid={testId} title={done ? t('common.copied') : t('common.copy')} onClick={() => void copyText(text).then(() => setDone(true))}>
      {done ? Icons.check : (icon ?? Icons.page)}
    </button>
  )
}
