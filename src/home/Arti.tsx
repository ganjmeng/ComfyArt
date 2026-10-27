import { useState } from 'react'

import { t } from '../i18n'
import { ArtiMemory } from './ArtiMemory'
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

const CAPS: Cap[] = [
  { id: 'review', title: t('arti.cap.review.title'), desc: t('arti.cap.review.desc'), disabled: true, on: false },
  { id: 'research', title: t('arti.cap.research.title'), desc: t('arti.cap.research.desc'), disabled: true, on: false },
  { id: 'memory', title: t('arti.cap.memory.title'), desc: t('arti.cap.memory.desc'), disabled: true, on: true },
  { id: 'skills', title: t('arti.cap.skills.title'), desc: t('arti.cap.skills.desc'), disabled: true, on: true },
  { id: 'feedback', title: t('arti.cap.feedback.title'), desc: t('arti.cap.feedback.desc'), disabled: true, on: false, noSwitch: true },
]

function Switch({ on, disabled }: { on: boolean; disabled?: boolean }) {
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
    >
      <span />
    </button>
  )
}

function CapCard({ cap }: { cap: Cap }) {
  const grey = cap.disabled && (cap.id === 'review' || cap.id === 'research')
  return (
    <div
      className="ca-arti__cap"
      data-testid={`arti-cap-${cap.id}`}
      data-disabled={cap.disabled || undefined}
      data-grey={grey || undefined}
    >
      <div className="ca-arti__capbody">
        <div className="ca-arti__captitle">{cap.title}</div>
        <div className="ca-arti__capdesc">{cap.desc}</div>
        {grey ? <div className="ca-arti__capnote" data-testid={`arti-cap-${cap.id}-note`}>{t('arti.cap.comingSoon')}</div> : null}
      </div>
      {!cap.noSwitch ? <Switch on={cap.on} disabled={cap.disabled} /> : null}
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
  return (
    <div className="ca-arti__placeholder" data-testid="arti-evolution-placeholder">
      {t('arti.evolutionPlaceholder')}
    </div>
  )
}

/** #367: account-level /arti home shell — level card + capabilities + learned tabs. */
export function Arti() {
  const [tab, setTab] = useState<LearnedTab>('memory')
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

      <section className="ca-arti__section" data-testid="arti-capabilities">
        <h2 className="ca-arti__sectiontitle">{t('arti.canDoTitle')}</h2>
        <div className="ca-arti__caps">
          {CAPS.map((c) => <CapCard key={c.id} cap={c} />)}
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
