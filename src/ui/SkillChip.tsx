import type { KeyboardEvent } from 'react'
import { Icons } from './icons'

/** #462/#484 skill chip (max-width + ellipsis in shell.css `.ca-chip--skill`, full name on hover).
 *  #491: one component for every skill chip — home, in-project composer, chat bubbles, and the Skill Creator chip.
 *  No ×: in an input it is removed with Backspace (see chipBackspace). */
export function SkillChip({ name, testId, creator }: { name: string; testId?: string; creator?: boolean }) {
  // #491 design: the Skill Creator chip never shrinks or truncates (data-creator → shell.css); user skill chips keep the ellipsis
  return (
    <span className="ca-chip ca-chip--skill" data-creator={creator ? '' : undefined} data-testid={testId} title={name}>
      <span className="ca-icon">{Icons.scrollText}</span><span className="ca-chip__name">{name}</span>
    </span>
  )
}

/** #491 product: Backspace removes the chip when the input is empty or the caret sits at position 0 (no selection). */
export function chipBackspace(e: KeyboardEvent<HTMLTextAreaElement>): boolean {
  if (e.key !== 'Backspace' || e.nativeEvent.isComposing) return false
  const el = e.currentTarget
  return el.value === '' || (el.selectionStart === 0 && el.selectionEnd === 0)
}
