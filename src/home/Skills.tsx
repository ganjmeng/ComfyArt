import { showMemoryToast } from '../memory'
/** #460 G1 — Skills Explore / Favourites / Personal shell (#494: cards driven by the built-in skill data). */
import { useEffect, useMemo, useRef, useState } from 'react'

import { thumbUrl } from '../comfy'
import { t } from '../i18n'
import { newProject } from '../projects'
import {
  importLanding,
  loadFavourites,
  loadSkills,
  skillCreatorAtom,
  skillDescription,
  skillAuthor,
  skillChips,
  skillCover,
  matchesSkillChip,
  toggleFavourite,
  type Skill,
  type SkillChipId,
} from '../skills'
import { BRAND } from '../brand'
import { Icons } from '../ui/icons'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { openSkillEditor, skillsOpenAtom } from '../ui/SkillsDialog'

type Tab = 'explore' | 'favourites' | 'personal'
const CHIP_LABEL: Record<SkillChipId, string> = {
  forYou: 'home.skillsForYou',
  ecommerce: 'home.skillsChipEcommerce',
  branding: 'home.skillsChipBranding',
  social: 'home.skillsChipSocial',
  website: 'home.skillsChipWebsite',
  ads: 'home.skillsChipAds',
}

/** #494 — Explore card: 231:173 cover (skillCover, else neutral grey + Lucide icon), image badge, one-line title and
 *  description, real author (ComfyArt / 个人), no counts. Hover: bookmark only (试用 arrives with the step-2 dialog). */
function SkillWallCard({
  skill, fav, onFav, onTry,
}: {
  skill: Skill
  fav: boolean
  onFav: () => void
  onTry: () => void
}) {
  const cover = skillCover(skill)
  const author = skillAuthor(skill)
  const src = cover && (cover.own === 'bundled' ? cover.src : thumbUrl(cover.src, 512))
  const desc = skillDescription(skill)
  return (
    <article className="ca-swall__card" data-testid="skills-wall-card" data-skill={skill.id} data-custom={skill.custom || undefined}>
      <div className="ca-swall__cover" role="button" tabIndex={0} aria-label={skill.name} onClick={onTry}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onTry() } }}>
        {src
          ? <img src={src} alt={skill.name} loading="lazy" data-testid="skills-card-cover" />
          : <span className="ca-swall__placeholder" data-testid="skills-card-placeholder"><span className="ca-icon">{skill.id === 'custom-workflow' ? Icons.workflow : Icons.skill}</span></span>}
        <span className="ca-swall__badge" data-testid="skills-card-kind" data-kind="image" aria-hidden="true"><span className="ca-icon">{Icons.imageLine}</span></span>
        <button
            type="button"
            className="ca-swall__bookmark"
            data-testid="skills-card-bookmark"
            data-on={fav || undefined}
            aria-pressed={fav}
            title={fav ? t('home.skillsUnfavourite') : t('home.skillsFavourite')}
            onClick={(e) => { e.stopPropagation(); onFav() }}
          >
            <span className="ca-icon">{fav ? Icons.bookmarkFilled : Icons.bookmark}</span>
          </button>
      </div>
      <h3 className="ca-swall__title">{skill.name}</h3>
      <p className="ca-swall__desc">{desc}</p>
      <div className="ca-swall__author" data-testid="skills-card-author" data-kind={author.kind}>
        {author.kind === 'builtin'
          ? <img className="ca-swall__avatar" src={BRAND.logoPath} alt="" aria-hidden="true" />
          : <span className="ca-swall__avatar" aria-hidden="true"><span className="ca-icon">{Icons.user}</span></span>}
        {author.label}
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
  /** #494 — chips come from data; a category with no skill (today: 网站) is not shown. */
  const chips = useMemo(() => skillChips(explore), [explore])
  const favouriteSkills = useMemo(() => skills.filter((s) => favs.includes(s.id)), [skills, favs])

  const wall = useMemo(() => {
    if (tab === 'favourites') return favouriteSkills
    if (tab === 'personal') return personal
    return explore.filter((s) => matchesSkillChip(s, chip))
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
          {chips.map((c) => (
            <button
              key={c}
              type="button"
              className="ca-skills__chip"
              data-on={chip === c || undefined}
              data-testid={`skills-chip-${c}`}
              onClick={() => setChip(c)}
            >
              {t(CHIP_LABEL[c])}
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
            // #463 product ruling: go straight to the new skill's detail (duplicates land on -2/-3); skipped files get one toast.
            setImporting(false)
            setTab('personal')
            const landing = importLanding(skill, skipped)
            openSkillEditor(landing.id)
            if (landing.skipped) showMemoryToast(landing.skipped, 'info')
            void loadSkills().then(setSkills)
          }}
        />
      )}
    </div>
  )
}
