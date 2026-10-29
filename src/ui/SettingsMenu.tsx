import { useState, type ReactNode } from 'react'
import { useValue, type Editor } from 'tldraw'

import { clearCache, unloadModels } from '../comfy'
import { DOCS_SITE } from '../docsConfig'
import { errorText } from '../jobs'
import { loadCloudModels } from '../wavespeed'
import { lang, setLang, t, type Lang } from '../i18n'
import { pushEnabled, setPush } from '../notices'
import { saveTheme, setTheme, themeAtom, THEMES } from '../theme'
import { dockAtom, setDock } from './chatDock'
import { reportError, reportSuccess } from './ErrorToasts'
import { showMemoryToast } from '../memory'

// #408: canvas -> tldraw success toast; home has no tldraw toast host, so use the existing home toast (ca-mem-toast).
const done = (text: string, onCanvas: boolean) => (onCanvas ? reportSuccess(text) : showMemoryToast(text))
import { Icons } from './icons'
import { Popover } from './Popover'
import { shortcutsAtom } from './Shortcuts'
import { keySettingsOpenAtom } from '../wavespeedKey'

/** #35: the docs site (Mintlify, URL in docsConfig.ts); English at the root, Chinese under /zh. */
export function docsUrl(l: Lang = lang): string {
  return l === 'zh' ? `${DOCS_SITE}/zh` : DOCS_SITE
}

const LANGS: [Lang, string][] = [['zh', t('settings.langZh')], ['en', t('settings.langEn')]]
const SIDES: ['left' | 'right', string][] = [['left', t('settings.chatLeft')], ['right', t('settings.chatRight')]]

function Choice({ label, hint, on, onPick }: { label: string; hint?: string; on: boolean; onPick: () => void }) {
  return (
    <button type="button" className="ca-menu__item" onClick={onPick}>
      <span className="ca-menu__grow">{label}</span>{hint && <span className="ca-menu__key">{hint}</span>}{on && <span className="ca-icon">{Icons.check}</span>}
    </button>
  )
}

export function SettingsMenu({ editor, trigger }: { editor?: Editor; trigger: (props: { open: boolean; toggle: () => void }) => ReactNode }) {
  const [open, setOpen] = useState(false)
  const [push, setPushOn] = useState(pushEnabled)
  const theme = useValue(themeAtom)
  const dock = useValue(dockAtom)
  const toggle = (next: boolean) => setOpen(next)
  return (
    <>
      <Popover open={open} onOpenChange={toggle} side={editor ? 'bottom' : 'top'} align={editor ? 'end' : 'start'} trigger={trigger}>
        <div className="ca-menu ca-settings">
          <div className="ca-gen__label">{t('settings.language')}</div>
          {LANGS.map(([value, label]) => <Choice key={value} label={label} on={lang === value} onPick={() => value !== lang && setLang(value)} />)}
          <div className="ca-menu__sep" />
          <div className="ca-gen__label">{t('projectHeader.theme')}</div>
          {THEMES.map(([value, label]) => <Choice key={value} label={label} on={theme === value} onPick={() => (editor ? setTheme(editor, value) : saveTheme(value))} />)}
          <div className="ca-menu__sep" />
          <button type="button" className="ca-menu__item" onClick={() => { setOpen(false); keySettingsOpenAtom.set(true) }}>
            <span className="ca-icon">{Icons.settings}</span><span className="ca-menu__grow">{t('wsKey.menu')}</span>
          </button>
          {/* #408 (upstream 515d36e): both entries kept; no local models, so they act on the WaveSpeed lists and local caches */}
          <button type="button" className="ca-menu__item" data-testid="settings-unload" onClick={() => { setOpen(false); void unloadModels().then((r) => { done(t('settings.unloadModelsDone', r.models, r.prices), !!editor); void loadCloudModels() }, (e) => reportError(errorText(e))) }}>
            <span className="ca-icon">{Icons.erase}</span><span className="ca-menu__grow">{t('settings.unloadModels')}</span>
          </button>
          <button type="button" className="ca-menu__item" data-testid="settings-clear-cache" onClick={() => { setOpen(false); void clearCache().then((r) => done(t('settings.clearCacheDone', r.entries, r.thumbs), !!editor), (e) => reportError(errorText(e))) }}>
            <span className="ca-icon">{Icons.trash}</span><span className="ca-menu__grow">{t('settings.clearCache')}</span>
          </button>
          {editor && (
            <>
              <div className="ca-menu__sep" />
              <div className="ca-gen__label">{t('settings.chatPosition')}</div>
              {SIDES.map(([value, label]) => <Choice key={value} label={label} on={dock === value} onPick={() => setDock(value)} />)}
              <div className="ca-menu__sep" />
              <button type="button" className="ca-menu__item" onClick={() => { setOpen(false); shortcutsAtom.set(true) }}>
                <span className="ca-icon">{Icons.keyboard}</span><span className="ca-menu__grow">{t('shortcuts.keyboardShortcuts')}</span><span className="ca-menu__key">?</span>
              </button>
              <label className="ca-menu__item">
                <span className="ca-icon">{Icons.bell}</span><span className="ca-menu__grow">{t('settings.systemNotifications')}</span>
                <input type="checkbox" checked={push} onChange={(e) => void setPush(e.target.checked).then(setPushOn)} />
              </label>
            </>
          )}
          <div className="ca-menu__sep" />
          <button type="button" className="ca-menu__item" data-testid="settings-guide" onClick={() => { setOpen(false); window.open(docsUrl(), '_blank', 'noopener,noreferrer') }}>
            <span className="ca-icon">{Icons.link}</span><span className="ca-menu__grow">{t('settings.userGuide')}</span>
          </button>
        </div>
      </Popover>
    </>
  )
}
