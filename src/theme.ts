import { atom, type Editor } from 'tldraw'

import { readLocal, writeLocal } from './localPrefs'
import { t } from './i18n'

export type Theme = 'light' | 'dark' | 'system'
export const THEMES: [Theme, string][] = [['light', t('projectHeader.themeLight')], ['dark', t('projectHeader.themeDark')], ['system', t('projectHeader.themeSystem')]]

const KEY = 'comfyart.theme'

export const themeAtom = atom<Theme>('theme', 'dark')

const systemDark = matchMedia('(prefers-color-scheme: dark)')
/** Active document theme. `<html data-theme>` is what `--ca-*` resolves from. */
export function themeIsDark(theme: Theme = themeAtom.get()) {
  return theme === 'dark' || (theme === 'system' && systemDark.matches)
}

export async function initTheme() {
  const stored = readLocal(KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') themeAtom.set(stored)
  else {
    const res = await fetch('/api/settings/Comfy.ColorPalette').catch(() => null)
    const palette = res?.ok ? await res.json().catch(() => null) : null
    themeAtom.set(palette === 'light' ? 'light' : 'dark')
  }
  markDark(themeIsDark())
  systemDark.addEventListener('change', () => { if (themeAtom.get() === 'system') markDark(systemDark.matches) })
}

export function saveTheme(theme: Theme) {
  themeAtom.set(theme)
  writeLocal(KEY, theme)
  markDark(themeIsDark(theme))
}

export function setTheme(editor: Editor, theme: Theme) {
  saveTheme(theme)
  editor.user.updateUserPreferences({ colorScheme: theme })
}

export function markDark(dark: boolean) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}
