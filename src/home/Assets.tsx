import { useEffect } from 'react'

import { t } from '../i18n'
import { loadLibrary } from '../library'
import { showMemoryToast } from '../memory'
import { Icons } from '../ui/icons'
import { LibraryPanel } from '../ui/LibraryPanel'

/**
 * #539 PR-A: home 「我的素材」 page shell. Thin two-pane layout only — the left pane is the
 * existing canvas `LibraryPanel` (kitsOnly), data is the existing `libraryAtom`. Right pane
 * (existing `KitEditor`) is wired in PR-B; until then it shows the empty state. Real user data only.
 */
export function Assets() {
  useEffect(() => { void loadLibrary().catch((e) => showMemoryToast(String(e), 'error')) }, [])
  return (
    <div className="ca-assets-page" data-testid="assets-page">
      <aside className="ca-assets-page__left">
        <h1 className="ca-assets-page__title">{t('home.assets')}</h1>
        <LibraryPanel kitsOnly onError={(msg) => showMemoryToast(msg, 'error')} />
      </aside>
      <section className="ca-assets-page__right" data-testid="assets-detail-empty">
        <span className="ca-icon ca-assets-page__icon">{Icons.assets}</span>
        <div className="ca-assets-page__empty-title">{t('assets.emptyTitle')}</div>
        <div className="ca-assets-page__empty-hint">{t('assets.emptyHint')}</div>
      </section>
    </div>
  )
}
