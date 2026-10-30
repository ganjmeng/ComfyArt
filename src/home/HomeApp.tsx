import type { ReactNode } from 'react'

import { t } from '../i18n'
import { newProject, openView, type HomeView } from '../projects'
import { MemoryChooser, MemoryToast } from '../ui/MemoryChooser'
import { MemoryDialog } from '../ui/MemoryDialog'
import { showMemoryToast } from '../memory'
import { Confirm } from '../ui/Confirm'
import { BrandMark } from '../ui/BrandMark'
import { Icons } from '../ui/icons'
import { KeySettings } from '../ui/KeySettings'
import { SettingsMenu } from '../ui/SettingsMenu'
import { WAVESPEED_HISTORY_URL } from '../wavespeedKey'
import '../styles/home.css'
import { Arti } from './Arti'
import { Home } from './Home'
import { NotFound } from './NotFound'
import { Projects } from './Projects'
import { Schedules } from './Schedules'
import { Skills } from './Skills'

type View = HomeView | { missing: string }

function RailBtn({
  icon, label, on, onClick, testId, badge,
}: {
  icon: ReactNode
  label: string
  on?: boolean
  onClick: () => void
  testId?: string
  badge?: string
}) {
  return (
    <button
      type="button"
      className="ca-rail__btn"
      title={label}
      aria-label={label}
      data-on={on || undefined}
      data-testid={testId}
      onClick={onClick}
    >
      <span className="ca-icon">{icon}</span>
      {badge ? <span className="ca-rail__badge" data-testid="rail-arti-beta">{badge}</span> : null}
    </button>
  )
}

function main(view: View) {
  if (view === 'home') return <Home />
  if (view === 'projects') return <Projects />
  if (view === 'skills') return <Skills />
  if (view === 'schedules') return <Schedules />
  if (view === 'arti') return <Arti />
  return <NotFound id={view.missing} />
}

export function HomeApp({ view }: { view: View }) {
  return (
    <div className="ca-home" data-testid="home-shell">
      <nav className="ca-rail" data-testid="account-rail">
        <span className="ca-rail__logo"><BrandMark /></span>
        <RailBtn icon={Icons.plus} label={t('projectHeader.newProject')} onClick={() => newProject()} />
        <RailBtn icon={Icons.home} label={t('home.home')} on={view === 'home'} onClick={() => openView('home')} testId="rail-home" />
        <RailBtn icon={Icons.folder} label={t('home.projectLibrary')} on={view === 'projects'} onClick={() => openView('projects')} testId="rail-projects" />
        <RailBtn icon={Icons.skill} label={t('home.skills')} on={view === 'skills'} onClick={() => openView('skills')} testId="rail-skills" />
        {/* #367: account-level siblings — 设计委托 + Arti Beta (≠ canvas Agent chat) */}
        <RailBtn icon={Icons.bell} label={t('home.designSchedules')} on={view === 'schedules'} onClick={() => openView('schedules')} testId="rail-schedules" />
        <RailBtn
          icon={Icons.sparkles}
          label={`${t('home.arti')} ${t('home.artiBeta')}`}
          on={view === 'arti'}
          onClick={() => openView('arti')}
          testId="rail-arti"
          badge={t('home.artiBeta')}
        />
        <div className="ca-rail__spacer" />
        <RailBtn
          icon={Icons.exit}
          label={t('home.waveSpeedTaskHistory')}
          onClick={() => { window.open(WAVESPEED_HISTORY_URL, '_blank', 'noopener,noreferrer') }}
          testId="rail-ws-history"
        />
        <SettingsMenu trigger={({ open, toggle }) => <RailBtn icon={Icons.settings} label={t('settings.settings')} on={open} onClick={toggle} />} />
      </nav>
      <main className="ca-home__main">{main(view)}</main>
      <Confirm />
      <MemoryChooser />
      <MemoryToast />
      <MemoryDialog onError={(msg) => showMemoryToast(msg)} />
      <KeySettings />
    </div>
  )
}
