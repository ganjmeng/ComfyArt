/** #381: the /arti 自动更新记忆 / 自进化技能 switches mirror the real settings (api/settings.py, off by default). */
export const ARTI_CAP_SETTINGS = { memory: 'proactive-memory', skills: 'proactive-skills' } as const

export function artiCapOn(id: string, settings: Record<string, unknown>): boolean {
  const key = ARTI_CAP_SETTINGS[id as keyof typeof ARTI_CAP_SETTINGS]
  return key ? settings[key] === true : false
}
