/** #460 G1 — Skills Explore / Favourites / Personal shell (mock community wall; Home grid kept). */
import { useEffect, useMemo, useRef, useState } from 'react'

import { thumbUrl } from '../comfy'
import { t } from '../i18n'
import { newProject } from '../projects'
import {
  importLanding,
  loadFavourites,
  loadSkills,
  skillChip,
  skillCreatorAtom,
  skillDescription,
  skillWallMeta,
  toggleFavourite,
  type Skill,
  type SkillChipId,
} from '../skills'
import { Icons } from '../ui/icons'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { openImportedSkill, skillsOpenAtom } from '../ui/SkillsDialog'

type Tab = 'explore' | 'favourites' | 'personal'
const CHIPS: { id: SkillChipId; labelKey: string }[] = [
  { id: 'forYou', labelKey: 'home.skillsForYou' },
  { id: 'ecommerce', labelKey: 'home.skillsChipEcommerce' },
  { id: 'branding', labelKey: 'home.skillsChipBranding' },
  { id: 'social', labelKey: 'home.skillsChipSocial' },
  { id: 'website', labelKey: 'home.skillsChipWebsite' },
  { id: 'ads', labelKey: 'home.skillsChipAds' },
]

function matchesChip(s: Skill, chip: SkillChipId): boolean {
  return chip === 'forYou' || skillChip(s.id) === chip
}

function coverOf(s: Skill): string | null {
  const imgs = Object.values(s.images ?? {})
  return imgs[0] ?? null
}

function SkillWallCard({
  skill, fav, onFav, onTry,
}: {
  skill: Skill
  fav: boolean
  onFav: () => void
  onTry: () => void
}) {
  const cover = coverOf(skill)
  const meta = skillWallMeta(skill.id)
  const desc = skillDescription(skill)
  return (
    <article className="ca-swall__card" data-testid="skills-wall-card" data-skill={skill.id}>
      <button type="button" className="ca-swall__cover" data-tone={meta.tone} onClick={onTry} aria-label={skill.name}>
        {cover
          ? <img src={thumbUrl(cover, 512)} alt="" loading="lazy" />
          : <span className="ca-swall__placeholder"><span className="ca-icon">{Icons.skill}</span></span>}
      </button>
      <div className="ca-swall__body">
        <h3 className="ca-swall__title">{skill.name}</h3>
        <p className="ca-swall__desc">{desc}</p>
        <div className="ca-swall__meta">
          <span className="ca-swall__author">
            <span className="ca-swall__avatar" aria-hidden="true">{meta.author.slice(0, 1)}</span>
            {meta.author}
          </span>
          <span className="ca-swall__stat" title={t('home.skillsViews', meta.views)}>
            <span className="ca-icon">{Icons.eye}</span>{meta.views}
          </span>
          <button
            type="button"
            className="ca-swall__stat ca-swall__heart"
            data-on={fav || undefined}
            title={fav ? t('home.skillsUnfavourite') : t('home.skillsFavourite')}
            onClick={onFav}
          >
            <span className="ca-icon">{Icons.heart}</span>{meta.likes}
          </button>
        </div>
      </div>
    </article>
  )
}

export function Skills() {
  const [tab, setTab] = useState<Tab>('explore')
  const [chip, setChip] = useState<SkillChipId>('forYou')
  const [skills, setSkills] = useState<Skill[]>([])
  const [favs, setFavs] = useState<string[]>(() => loadFavourites())

  const [menu, setMenu] = useState(false)
  const [importing, setImporting] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => { void loadSkills().then(setSkills) }, [])
  useEffect(() => {
    if (!menu) return
    const off = (e: PointerEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false) }
    window.addEventListener('pointerdown', off)
    return () => window.removeEventListener('pointerdown', off)
  }, [menu])

  const personal = useMemo(() => skills.filter((s) => s.custom), [skills])
  const explore = useMemo(() => skills.filter((s) => !s.custom), [skills])
  const favouriteSkills = useMemo(() => skills.filter((s) => favs.includes(s.id)), [skills, favs])

  const wall = useMemo(() => {
    if (tab === 'favourites') return favouriteSkills
    if (tab === 'personal') return personal
    return explore.filter((s) => matchesChip(s, chip))
  }, [tab, chip, explore, personal, favouriteSkills])

  const emptyKey = tab === 'favourites'
    ? 'home.skillsEmptyFavourites'
    : tab === 'personal'
      ? 'home.skillsEmptyPersonal'
      : 'home.skillsEmptyExplore'

  const createConversational = () => {
    skillCreatorAtom.set({ on: true })
    newProject({ createSkill: '1' })
  }

  const onFav = (id: string) => setFavs(toggleFavourite(id))

  return (
    <div className="ca-skillspage" data-testid="skills-page">
      <div className="ca-skills__head">
        <h1>{t('home.skills')}</h1>
        <div className="ca-skills__headacts">
          <button
            type="button"
            className="ca-skills__iconbtn"
            title={t('composer.manageSkills')}
            onClick={() => skillsOpenAtom.set(true)}
          >
            <span className="ca-icon">{Icons.search}</span>
          </button>
          <div className="ca-skills__createwrap" ref={menuRef}>
            <button type="button" className="ca-skills__create" data-testid="skills-create" onClick={createConversational}>
              {t('home.skillsCreate')}<span className="ca-icon">{Icons.plus}</span>
            </button>
            <button
              type="button"
              className="ca-skills__create ca-skills__createmore"
              data-testid="skills-create-menu"
              aria-haspopup="menu"
              aria-expanded={menu}
              title={t('skillsImport.title')}
              onClick={() => setMenu(!menu)}
            >
              <span className="ca-icon">{Icons.chevron}</span>
            </button>
            {menu && (
              <div className="ca-menu ca-skills__createmenu" role="menu">
                <button type="button" role="menuitem" className="ca-menu__item" data-testid="skills-import" onClick={() => { setMenu(false); setImporting(true) }}>
                  <span className="ca-icon">{Icons.upload}</span>{t('skillsImport.menu')}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="ca-skills__tabs" role="tablist" data-testid="skills-tabs">
        {([
          ['explore', 'home.skillsExplore'],
          ['favourites', 'home.skillsFavourites'],
          ['personal', 'home.skillsPersonal'],
        ] as const).map(([id, key]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className="ca-skills__tab"
            aria-selected={tab === id}
            data-on={tab === id || undefined}
            data-testid={`skills-tab-${id}`}
            onClick={() => setTab(id)}
          >
            {t(key)}
          </button>
        ))}
      </div>

      {tab === 'explore' && (
        <div className="ca-skills__chips" data-testid="skills-chips">
          {CHIPS.map((c) => (
            <button
              key={c.id}
              type="button"
              className="ca-skills__chip"
              data-on={chip === c.id || undefined}
              onClick={() => setChip(c.id)}
            >
              {t(c.labelKey)}
            </button>
          ))}
        </div>
      )}

      {wall.length === 0 && <div className="ca-skills__empty" data-testid="skills-empty">{t(emptyKey)}</div>}

      <div className="ca-swall" data-testid="skills-wall">
        {wall.map((s) => (
          <SkillWallCard
            key={s.id}
            skill={s}
            fav={favs.includes(s.id)}
            onFav={() => onFav(s.id)}
            onTry={() => newProject({ skill: s.id })}
          />
        ))}
      </div>

      {tab === 'personal' && (
        <div className="ca-skills__fallback">
          <button type="button" className="ca-landing__link" onClick={() => skillsOpenAtom.set(true)}>
            {t('composer.manageSkills')} · {t('composer.skillCreatorForm')}
          </button>
        </div>
      )}
      {importing && (
        <SkillImportDialog
          onClose={() => setImporting(false)}
          onImported={(skill, skipped) => {
            // #463 product ruling: go straight to the new skill's detail (duplicates land on -2/-3) with the guide toast.
            setImporting(false)
            setTab('personal')
            openImportedSkill(importLanding(skill, skipped))
            void loadSkills().then(setSkills)
          }}
        />
      )}
    </div>
  )
}
