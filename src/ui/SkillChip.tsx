import { t } from '../i18n'
import { Icons } from './icons'

/** #462/#484 skill chip (max-width + ellipsis in shell.css `.ca-chip--skill`, full name on hover);
 *  #491 reuses it on the home input with a remove button. */
export function SkillChip({ name, testId, onRemove }: { name: string; testId?: string; onRemove?: () => void }) {
  return (
    <span className="ca-chip ca-chip--skill" data-testid={testId} title={name}>
      <span className="ca-icon">{Icons.scrollText}</span><span className="ca-chip__name">{name}</span>
      {onRemove && <button type="button" title={t('common.remove')} onClick={onRemove}>{Icons.close}</button>}
    </span>
  )
}
