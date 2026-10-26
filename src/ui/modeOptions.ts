import type { AgentMode } from '../agent'
import { t } from '../i18n'
import { Icons } from './icons'

/** Shared mode list for Home + canvas (image/video labels). Agent-mode pill uses shortLabel, not composer.agent. */
export const MODE_OPTIONS: [AgentMode, string, keyof typeof Icons][] = [
  ['agent', t('composer.agent'), 'agent'],
  ['image', t('composer.image'), 'genImage'],
  ['video', t('common.video'), 'genVideo'],
]

export const modeOf = (mode: AgentMode) => MODE_OPTIONS.find(([m]) => m === mode)!
