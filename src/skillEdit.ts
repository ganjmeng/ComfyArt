// #462 Edit in chat: the skill dialog hands off to a NEW project named after the skill, which auto-sends one turn
// (skill chip + 「我想修改这个 Skill」). The agent loads the skill, lists what it holds and asks what to change; it reads
// and saves through the skill tool by id (#463 skillEditToolHint), so same-name skills (x, x-2) are never confused.
import { t } from './i18n'
import { newProject } from './projects'
import { skillEditToolHint, type Skill } from './skills'

export const EDIT_SKILL_PARAM = 'editSkill'

export function editSkillInChat(skill: Skill) {
  newProject({ [EDIT_SKILL_PARAM]: skill.id })
}

export function skillEditTurn(skill: Skill) {
  return {
    title: t('skillEdit.projectTitle', skill.name),
    text: t('skillEdit.ask'),
    context: `[The user opened "Edit in chat" for their custom Skill "${skill.name}". ${skillEditToolHint(skill)} `
      + 'First list what it currently contains (purpose, fixed outputs, rules, constraints) in short bullets, then ask what they want to change and offer a few concrete options. '
      + 'Do not save until they say what to change.]',
  }
}

type Send = (text: string, skill: Skill, context: string) => Promise<unknown>

/** Names the fresh project and sends the single opening turn. */
export async function startSkillEdit(editor: { updateDocumentSettings: (s: { name: string }) => void }, skill: Skill, send: Send) {
  const turn = skillEditTurn(skill)
  editor.updateDocumentSettings({ name: turn.title })
  await send(turn.text, skill, turn.context)
}
