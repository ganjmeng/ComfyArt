import { useEffect } from 'react'
import { useValue } from 'tldraw'

import { t } from '../i18n'
import { KIND_LABELS, libraryAtom, loadLibrary } from '../library'
import { showMemoryToast } from '../memory'
import { KitEditor, kitEditAtom } from '../ui/KitEditor'
import { createLibraryItem, kitTab, LibraryPanel, libraryTabAtom } from '../ui/LibraryPanel'

const fail = (msg: string) => showMemoryToast(msg, 'error')

/**
 * #539 home 「我的素材」 page: left = existing `LibraryPanel` (kitsOnly), right = existing `KitEditor`
 * (embedded) for the selected kit. Data = existing `libraryAtom` (real user data only, never auto-created).
 */
export function Assets() {
  const kind = kitTab(useValue(libraryTabAtom))
  const library = useValue(libraryAtom)
  const selected = useValue(kitEditAtom)
  const items = library.filter((x) => x.kind === kind)
  useEffect(() => { void loadLibrary().catch((e) => fail(String(e))) }, [])
  // #539 PR-B: default-select the first kit of the active tab; none → empty state.
  useEffect(() => {
    if (!items.some((x) => x.id === selected)) kitEditAtom.set(items[0]?.id ?? null)
  }, [kind, items.map((x) => x.id).join(), selected])
  const current = items.find((x) => x.id === selected)
  return (
    <div className="ca-assets-page" data-testid="assets-page">
      <aside className="ca-assets-page__left">
        <h1 className="ca-assets-page__title">{t('home.assets')}</h1>
        <LibraryPanel kitsOnly onError={fail} />
      </aside>
      {current ? (
        <section className="ca-assets-page__detail"><KitEditor embedded onError={fail} /></section>
      ) : (
        <section className="ca-assets-page__right" data-testid="assets-detail-empty">
          <div className="ca-assets-page__empty-hint">{t('assets.emptyHint', KIND_LABELS[kind])}</div>
          <button type="button" className="ca-assets-page__new" data-testid="assets-empty-new" onClick={() => createLibraryItem(kind, fail)}>{t('libraryPanel.newItem', KIND_LABELS[kind])}</button>
        </section>
      )}
    </div>
  )
}
