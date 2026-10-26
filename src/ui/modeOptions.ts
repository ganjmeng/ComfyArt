import type { AgentMode } from '../agent'
import { t } from '../i18n'
import { Icons } from './icons'

/** #306: Home + canvas composer share one mode list; pill shows these labels, never a product/agent name. */
export const MODE_OPTIONS: [AgentMode, string, keyof typeof Icons][] = [
  ['agent', t('composer.agent'), 'agent'],
  ['image', t('composer.image'), 'genImage'],
  ['video', t('common.video'), 'genVideo'],
]

export const modeOf = (mode: AgentMode) => MODE_OPTIONS.find(([m]) => m === mode)!
