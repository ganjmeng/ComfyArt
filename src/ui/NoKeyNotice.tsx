import { useValue } from 'tldraw'

import { t } from '../i18n'
import { keySettingsOpenAtom, keyStatusAtom } from '../wavespeedKey'

/** #229: the existing "no WaveSpeed Key" notice, shown on first open (Home) before anything is sent.
 *  Same style and copy as the Agent panel notice; disappears as soon as a Key is saved. */
export function NoKeyNotice({ className }: { className?: string }) {
  const status = useValue(keyStatusAtom)
  if (!status || status.configured) return null
  return (
    <div className={`ca-chat__notice${className ? ` ${className}` : ''}`} data-level="error" data-nokey="">
      {t('agentPanel.noWavespeedKey')}{' '}
      <a href="#" onClick={(e) => { e.preventDefault(); keySettingsOpenAtom.set(true) }}>{t('agentPanel.setWavespeedKey')}</a>
    </div>
  )
}
