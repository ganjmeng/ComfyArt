import { t } from '../i18n'
import { Icons } from '../ui/icons'

/** #367: /schedules entry shell — CRUD = P1-1 (out of scope). */
export function Schedules() {
  return (
    <div className="ca-arti" data-testid="schedules-page">
      <header className="ca-arti__pagehead">
        <span className="ca-arti__pageicon ca-icon">{Icons.bell}</span>
        <div>
          <h1 className="ca-arti__pagetitle">{t('schedules.pageTitle')}</h1>
          <p className="ca-arti__pagelead">{t('schedules.pageLead')}</p>
        </div>
      </header>
      <div className="ca-arti__placeholder" data-testid="schedules-placeholder">
        {t('schedules.pagePlaceholder')}
      </div>
    </div>
  )
}
