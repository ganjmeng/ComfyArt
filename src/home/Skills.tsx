import { showMemoryToast } from '../memory'
/** #460 G1 — Skills Explore / Favourites / Personal shell (#494: cards driven by the built-in skill data). */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useValue } from 'tldraw'

import { thumbUrl } from '../comfy'
import { t } from '../i18n'
import { newProject } from '../projects'
import {
  deleteSkill,
  hasSkillDialog,
  importLanding,
  loc,
  openSkillDetail,
  presetImage,
  skillDetailAtom,
  skillGuideAtom,
  skillPreset,
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
import { openSkillEditor, SkillFileBox, skillsOpenAtom } from '../ui/SkillsDialog'
import { SkillRunDialog } from '../ui/SkillRunDialog'
import { confirmAtom } from '../ui/Confirm'
import { editSkillInChat } from '../skillEdit'

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
  // #494 — a cover that fails to load falls back to the same placeholder; keyed by src so a new src retries.
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const showImg = !!src && failedSrc !== src
  return (
    <article className="ca-swall__card" data-testid="skills-wall-card" data-skill={skill.id} data-custom={skill.custom || undefined}>
      <div className="ca-swall__cover" role="button" tabIndex={0} aria-label={skill.name} onClick={onTry}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onTry() } }}>
        {showImg
          ? <img src={src} alt={skill.name} loading="lazy" data-testid="skills-card-cover" onError={() => setFailedSrc(src)} />
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

/** #494-2 / #464 — a skill's detail page (inside the Skills page, not a new route): back, cover, title, description,
 *  presets (click = select; its prompt rides along when run), 「试用该技能」 → the skill's own dialog, personal skills
 *  also get 「在对话中编辑」 + ⋯ (表单编辑（备用） / delete), and the read-only SKILL.md file card shared with SkillForm.
 *  After an import the 「Skill 创建成功」 guide bubble points at 试用. No author / view / like counts. */
function SkillDetail({ skill, onBack, onTry, onDeleted }: {
  skill: Skill; onBack: () => void; onTry: (presetId: string | null) => void; onDeleted: () => void
}) {
  const [preset, setPreset] = useState(() => skillPreset(skill)?.id ?? null)
  const [open, setOpen] = useState('SKILL.md')
  const [more, setMore] = useState(false)
  const guide = useValue(skillGuideAtom) === skill.id
  const author = skillAuthor(skill)
  const cover = skillCover(skill)
  const chosen = skillPreset(skill, preset)
  const hero = chosen ? presetImage(skill, chosen) : cover?.src ?? null
  const heroSrc = hero && (cover?.own === 'userdata' && hero === cover.src ? thumbUrl(hero, 1024) : hero)
  const files = skill.files ?? {}
  const closeGuide = () => skillGuideAtom.set(null)
  return (
    <div className="ca-skilldetail" data-testid="skill-detail" data-skill={skill.id}>
      <button type="button" className="ca-skilldetail__back" data-testid="skill-detail-back" onClick={onBack}>
        <span className="ca-icon ca-skilldetail__backicon">{Icons.chevron}</span>{t('skillsDialog.back')}
      </button>
      <div className="ca-skilldetail__hero">
        {heroSrc
          ? <img src={heroSrc} alt={skill.name} data-testid="skill-detail-cover" />
          : <span className="ca-swall__placeholder" data-testid="skill-detail-placeholder"><span className="ca-icon">{Icons.skill}</span></span>}
      </div>
      <div className="ca-skilldetail__head">
        <div>
          <h2 data-testid="skill-detail-title">{skill.name}</h2>
          <div className="ca-swall__author" data-testid="skill-detail-author" data-kind={author.kind}>
            {author.kind === 'builtin'
              ? <img className="ca-swall__avatar" src={BRAND.logoPath} alt="" aria-hidden="true" />
              : <span className="ca-swall__avatar" aria-hidden="true"><span className="ca-icon">{Icons.user}</span></span>}
            {author.label}
          </div>
        </div>
        <div className="ca-skilldetail__acts">
          <span className="ca-skilldetail__trywrap">
            <button type="button" className="ca-panel__primary" data-testid="skill-detail-try" onClick={() => { closeGuide(); onTry(preset) }}>{t('skillDetail.try')}</button>
            {guide && (
              <div className="ca-skillguide" role="dialog" data-testid="skill-guide">
                <p>{t('skillDetail.guide')}</p>
                <div className="ca-skillguide__acts">
                  <button type="button" data-testid="skill-guide-skip" onClick={closeGuide}>{t('skillDetail.guideSkip')}</button>
                  <button type="button" data-testid="skill-guide-next" data-primary onClick={() => { closeGuide(); onTry(preset) }}>{t('skillDetail.guideNext')}</button>
                </div>
              </div>
            )}
          </span>
          {skill.custom && (
            <>
              <button type="button" className="ca-panel__secondary" data-testid="skill-detail-edit-chat" onClick={() => editSkillInChat(skill)}>{t('skillsDialog.editInChat')}</button>
              <span className="ca-skills__createwrap">
                <button type="button" className="ca-skills__iconbtn" data-testid="skill-detail-more" aria-haspopup="menu" aria-expanded={more} title={t('skillDetail.more')} onClick={() => setMore(!more)}>
                  <span className="ca-icon">{Icons.more}</span>
                </button>
                {more && (
                  <div className="ca-menu ca-skills__createmenu" role="menu">
                    <button type="button" role="menuitem" className="ca-menu__item" data-testid="skill-detail-form-edit" onClick={() => { setMore(false); openSkillEditor(skill.id) }}>{t('composer.skillCreatorForm')}</button>
                    <button type="button" role="menuitem" className="ca-menu__item" data-testid="skill-detail-delete" onClick={() => {
                      setMore(false)
                      confirmAtom.set({ danger: true, title: t('skillsDialog.deleteSkill', skill.name), desc: t('skillsDialog.theSkillFolderAndAll'), ok: t('common.delete'), run: () => void deleteSkill(skill.id).then(onDeleted) })
                    }}>{t('common.delete')}</button>
                  </div>
                )}
              </span>
            </>
          )}
        </div>
      </div>
      {skillDescription(skill) && <p className="ca-skilldetail__desc" data-testid="skill-detail-desc">{skillDescription(skill)}</p>}
      {!!skill.presets?.length && (
        <div className="ca-skillrun__presets" role="radiogroup" data-testid="skill-detail-presets">
          {skill.presets.map((p) => {
            const img = presetImage(skill, p)
            return (
              <button key={p.id} type="button" role="radio" aria-checked={preset === p.id} data-on={preset === p.id || undefined}
                className="ca-skillrun__preset" data-testid="skill-detail-preset" data-preset={p.id} onClick={() => setPreset(p.id)}>
                {img ? <img src={img} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}
                <span>{loc(p.name)}</span>
              </button>
            )
          })}
        </div>
      )}
      <div className="ca-skilldetail__file" data-testid="skill-detail-file">
        <SkillFileBox instructions={skill.instructions} files={files} open={open} setOpen={setOpen} />
      </div>
    </div>
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
  const detailId = useValue(skillDetailAtom)
  const [running, setRunning] = useState<{ id: string; preset: string | null } | null>(null)
  /** #494-2 — a card opens the skill's OWN dialog when its data has inputs[]; legacy skills keep main's direct start. */
  const tryCard = (s: Skill) => (hasSkillDialog(s) ? setRunning({ id: s.id, preset: null }) : newProject({ skill: s.id }))

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

  const detail = detailId ? skills.find((s) => s.id === detailId) : undefined
  const runSkill = running ? skills.find((s) => s.id === running.id) : undefined
  const runDialog = runSkill && (
    <SkillRunDialog skill={runSkill} presetId={running?.preset} onClose={() => setRunning(null)}
      onDetail={detail ? undefined : () => { setRunning(null); openSkillDetail(runSkill.id) }} />
  )
  if (detail) return (
    <div className="ca-skillspage" data-testid="skills-page">
      <SkillDetail key={detail.id} skill={detail} onBack={() => { skillGuideAtom.set(null); skillDetailAtom.set(null) }}
        onTry={(preset) => (hasSkillDialog(detail) ? setRunning({ id: detail.id, preset }) : newProject({ skill: detail.id }))}
        onDeleted={() => { skillDetailAtom.set(null); void loadSkills().then(setSkills) }} />
      {runDialog}
    </div>
  )

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
            onTry={() => (hasSkillDialog(s) ? tryCard(s) : newProject({ skill: s.id }))}
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
      {runDialog}
      {importing && (
        <SkillImportDialog
          onClose={() => setImporting(false)}
          onImported={(skill, skipped) => {
            // #463 product ruling (#494-2 / #464: the detail PAGE + guide bubble, not the edit form): go straight to the new skill's detail (duplicates land on -2/-3); skipped files get one toast.
            setImporting(false)
            setTab('personal')
            const landing = importLanding(skill, skipped)
            openSkillDetail(landing.id, true)
            if (landing.skipped) showMemoryToast(landing.skipped, 'info')
            void loadSkills().then(setSkills)
          }}
        />
      )}
    </div>
  )
}
