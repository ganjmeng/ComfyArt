import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { loadSettings, saveSettings, settingsAtom } from '../bot'
import { t } from '../i18n'
import { loadMemory, memoryLogAtom, type MemoryLog } from '../memory'
import { ARTI_CAP_SETTINGS, artiCapOn } from './artiCaps'
import { ArtiMemory } from './ArtiMemory'
import { openMemoryDialog } from '../ui/MemoryDialog'
import { listProjects } from '../projects'
import { Icons } from '../ui/icons'
import { ArtiLevelAvatar } from '../ui/ArtiMascot'
import { resolveArtiLevel } from '../artiLevel'

type LearnedTab = 'memory' | 'skills' | 'evolution'

type Cap = {
  id: string
  title: string
  desc: string
  /** honest grey — not interactive (P1-2 / backend not ready) */
  disabled: boolean
  /** visual on state for shell only; disabled caps stay off */
  on: boolean
  /** no switch (feedback 改稿 on CN) */
  noSwitch?: boolean
}

/** #385: memory / skills are switchable (write settings); review / research / feedback stay grey. */
const CAPS: Cap[] = [
  { id: 'review', title: t('arti.cap.review.title'), desc: t('arti.cap.review.desc'), disabled: true, on: false },
  { id: 'research', title: t('arti.cap.research.title'), desc: t('arti.cap.research.desc'), disabled: true, on: false },
  { id: 'memory', title: t('arti.cap.memory.title'), desc: t('arti.cap.memory.desc'), disabled: false, on: false },
  { id: 'skills', title: t('arti.cap.skills.title'), desc: t('arti.cap.skills.desc'), disabled: false, on: false },
  { id: 'feedback', title: t('arti.cap.feedback.title'), desc: t('arti.cap.feedback.desc'), disabled: true, on: false, noSwitch: true },
]

const LOG_LABELS: Record<MemoryLog['action'], string> = {
  add: t('memoryDialog.remember'),
  update: t('memoryDialog.correct'),
  forget: t('memoryDialog.forget'),
  skill: t('memoryDialog.learnedSkill'),
}

function Switch({ on, disabled, onChange }: { on: boolean; disabled?: boolean; onChange?: (on: boolean) => void }) {
  return (
    <button
      type="button"
      className="ca-switch"
      role="switch"
      aria-checked={on}
      data-on={on || undefined}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : 0}
      onClick={() => { if (!disabled && onChange) onChange(!on) }}
    >
      <span />
    </button>
  )
}

function CapCard({ cap, onToggle }: { cap: Cap; onToggle?: (on: boolean) => void }) {
  // disabled switch cards say 「即将开放」; switchable caps (#385 memory/skills) never show it
  const soon = cap.disabled && !cap.noSwitch
  return (
    <div
      className="ca-arti__cap"
      data-testid={`arti-cap-${cap.id}`}
      data-disabled={cap.disabled || undefined}
    >
      <div className="ca-arti__capbody">
        <div className="ca-arti__captitle">{cap.title}</div>
        <div className="ca-arti__capdesc">{cap.desc}</div>
        {soon ? <div className="ca-arti__capsoon" data-testid={`arti-cap-${cap.id}-soon`}>{t('arti.cap.soon')}</div> : null}
      </div>
      {!cap.noSwitch ? <Switch on={cap.on} disabled={cap.disabled} onChange={onToggle} /> : null}
    </div>
  )
}

function TabBtn({ id, label, on, onClick }: { id: LearnedTab; label: string; on: boolean; onClick: () => void }) {
  return (
    <button type="button" className="ca-arti__tab" data-on={on || undefined} data-testid={`arti-tab-${id}`} onClick={onClick}>
      {label}
    </button>
  )
}

function formatLogTime(ms: number): string {
  try {
    return new Date(ms).toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })
  } catch {
    return new Date(ms).toLocaleString()
  }
}

/** #385: evolution log — two columns 时间 | 操作, data from memoryLog (newest first). */
function ArtiEvolution() {
  const log = useValue(memoryLogAtom)
  const [ready, setReady] = useState(false)
  useEffect(() => { void loadMemory().finally(() => setReady(true)) }, [])
  if (!ready) return <div className="ca-chat__hint">{t('arti.memory.loading')}</div>
  if (!log.length) {
    return (
      <div className="ca-arti__placeholder" data-testid="arti-evolution-empty">
        {t('arti.evolutionEmpty')}
      </div>
    )
  }
  return (
    <div className="ca-arti-evo" data-testid="arti-evolution-log">
      <div className="ca-arti-evo__head" data-testid="arti-evolution-head">
        <span className="ca-arti-evo__col-time">{t('arti.evolutionTime')}</span>
        <span className="ca-arti-evo__col-action">{t('arti.evolutionAction')}</span>
      </div>
      <div className="ca-arti-evo__body">
        {log.map((l, i) => (
          <div key={`${l.time}-${i}`} className="ca-arti-evo__row" data-testid="arti-evolution-row" data-action={l.action}>
            <span className="ca-arti-evo__col-time" data-testid="arti-evolution-time">{formatLogTime(l.time)}</span>
            <span className="ca-arti-evo__col-action" data-testid="arti-evolution-action">
              <span className="ca-model__tag">{LOG_LABELS[l.action]}</span>
              <span className="ca-arti-evo__text">{l.text}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function LearnedBody({ tab }: { tab: LearnedTab }) {
  if (tab === 'memory') {
    // #368: full memory center (replaces P0-1 placeholder)
    return <ArtiMemory />
  }
  if (tab === 'skills') {
    return (
      <div className="ca-arti__skeletons" data-testid="arti-skills-skeleton" aria-busy="true">
        <div className="ca-arti__skel" />
        <div className="ca-arti__skel" />
        <div className="ca-arti__skel" />
        <p className="ca-chat__hint">{t('arti.skillsEmpty')}</p>
      </div>
    )
  }
  // #385: real evolution log (was placeholder)
  return <ArtiEvolution />
}

function ArtiIntroActions() {
  const [projectCount, setProjectCount] = useState<number | null>(null)
  useEffect(() => {
    void listProjects().then((list) => setProjectCount(list.length)).catch(() => setProjectCount(0))
  }, [])
  return (
    <section className="ca-arti__actions" data-testid="arti-intro-actions">
      <button
        type="button"
        className="ca-arti__action"
        data-testid="arti-tell-yourself"
        onClick={() => openMemoryDialog({ onboard: true })}
      >
        <span className="ca-arti__actionicon ca-icon">{Icons.agent}</span>
        <span className="ca-arti__actionbody">
          <span className="ca-arti__actiontitle">{t('arti.tellYourself')}</span>
          <span className="ca-arti__actiondesc">{t('arti.tellYourselfDesc')}</span>
        </span>
        <span className="ca-arti__actionchev ca-icon">{Icons.memoryChev}</span>
      </button>
      <button
        type="button"
        className="ca-arti__action"
        data-testid="arti-learn-past"
        title={t('arti.learnPastSoon')}
        disabled
        aria-disabled="true"
      >
        <span className="ca-arti__actionicon ca-icon">{Icons.folder}</span>
        <span className="ca-arti__actionbody">
          <span className="ca-arti__actiontitle">{t('arti.learnPast')}</span>
          <span className="ca-arti__actiondesc">{t('arti.learnPastDesc', projectCount ?? 0)}</span>
        </span>
        <span className="ca-arti__actionsoon">{t('arti.cap.soon')}</span>
      </button>
    </section>
  )
}

/** #367: account-level /arti home shell — level card + capabilities + learned tabs. */
export function Arti() {
  const [tab, setTab] = useState<LearnedTab>('memory')
  const settings = useValue(settingsAtom)
  useEffect(() => { void loadSettings() }, [])
  const toggleCap = (id: string, on: boolean) => {
    const key = ARTI_CAP_SETTINGS[id as keyof typeof ARTI_CAP_SETTINGS]
    if (!key) return
    void saveSettings({ [key]: on })
  }
  return (
    <div className="ca-arti" data-testid="arti-page">
      <section className="ca-arti__level" data-testid="arti-level-card">
        <div className="ca-arti__avatar" aria-hidden="true" data-testid="arti-avatar">
          {/* #371 SHOULD: share same level sheet as composer badge */}
          <ArtiLevelAvatar />
        </div>
        <div className="ca-arti__levelbody">
          <div className="ca-arti__levelrow">
            <span className="ca-arti__status">{t('arti.levelStatus')}</span>
            <span className="ca-arti__lv">{t('arti.level', resolveArtiLevel())}</span>
          </div>
          <p className="ca-arti__levelhint">{t('arti.levelHint')}</p>
        </div>
      </section>

      <ArtiIntroActions />

      <section className="ca-arti__section" data-testid="arti-capabilities">
        <h2 className="ca-arti__sectiontitle">{t('arti.canDoTitle')}</h2>
        <div className="ca-arti__caps">
          {CAPS.map((c) => (
            <CapCard
              key={c.id}
              cap={c.id in ARTI_CAP_SETTINGS ? { ...c, on: artiCapOn(c.id, settings) } : c}
              onToggle={c.id in ARTI_CAP_SETTINGS ? (on) => toggleCap(c.id, on) : undefined}
            />
          ))}
        </div>
      </section>

      <section className="ca-arti__section" data-testid="arti-learned">
        <h2 className="ca-arti__sectiontitle">{t('arti.learnedTitle')}</h2>
        <div className="ca-arti__tabs" role="tablist">
          <TabBtn id="memory" label={t('arti.tabMemory')} on={tab === 'memory'} onClick={() => setTab('memory')} />
          <TabBtn id="skills" label={t('arti.tabSkills')} on={tab === 'skills'} onClick={() => setTab('skills')} />
          <TabBtn id="evolution" label={t('arti.tabEvolution')} on={tab === 'evolution'} onClick={() => setTab('evolution')} />
        </div>
        <div className="ca-arti__tabbody" role="tabpanel" data-testid="arti-learned-body">
          <LearnedBody tab={tab} />
        </div>
      </section>
    </div>
  )
}
