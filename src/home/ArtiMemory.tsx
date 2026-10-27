import { useEffect, useRef, useState } from 'react'
import { useValue } from 'tldraw'

import { t } from '../i18n'
import {
  MEMORY_CATEGORIES,
  loadMemory,
  memoryAtom,
  memoryErrorAtom,
  remember,
  removeMemory,
  updateMemory,
  type Memory,
} from '../memory'
import { confirmAtom } from '../ui/Confirm'
import { showMemoryToast } from '../memory'
import { Icons } from '../ui/icons'
import { isEnter } from '../ui/keys'

type CatId = 'about' | 'work' | 'taste' | 'assets'

const GROUP_ICONS: Record<CatId, typeof Icons.memory> = {
  about: Icons.memory,
  work: Icons.agent,
  taste: Icons.palette,
  assets: Icons.assets,
}

function groupLabel(id: string) {
  return MEMORY_CATEGORIES.find(([cid]) => cid === id)?.[1] ?? id
}

function MemoryRow({
  item,
  menuId,
  setMenuId,
  onEdit,
}: {
  item: Memory
  menuId: string | null
  setMenuId: (id: string | null) => void
  onEdit: (id: string) => void
}) {
  const open = menuId === item.id
  const askDelete = () => {
    setMenuId(null)
    confirmAtom.set({
      title: t('arti.memory.deleteTitle'),
      desc: t('arti.memory.deleteDesc', item.text),
      ok: t('common.delete'),
      danger: true,
      run: () => { void removeMemory(item.id, t('arti.memory.sourceManual')).then((ok) => { if (ok) showMemoryToast(t('arti.memory.deletedToast')) }, () => undefined) },
    })
  }
  return (
    <div className="ca-arti-mem__row" data-testid="arti-memory-row" data-id={item.id}>
      <div className="ca-arti-mem__rowbody">
        {item.label ? <div className="ca-arti-mem__label">{item.label}</div> : null}
        <div className="ca-arti-mem__text">{item.text}</div>
      </div>
      <div className="ca-arti-mem__actions">
        <button
          type="button"
          className="ca-arti-mem__iconbtn"
          title={t('memoryDialog.correctMemory')}
          data-testid="arti-memory-edit-btn"
          onClick={() => { setMenuId(null); onEdit(item.id) }}
        >
          <span className="ca-icon">{Icons.filePenLine}</span>
        </button>
        <div className="ca-arti-mem__menwrap">
          <button
            type="button"
            className="ca-arti-mem__iconbtn"
            title={t('arti.memory.more')}
            data-testid="arti-memory-menu-btn"
            aria-expanded={open}
            onClick={() => setMenuId(open ? null : item.id)}
          >
            <span className="ca-icon">{Icons.more}</span>
          </button>
          {open ? (
            <div className="ca-arti-mem__menu" role="menu" data-testid="arti-memory-row-menu">
              <button type="button" role="menuitem" onClick={() => { setMenuId(null); onEdit(item.id) }}>
                {t('memoryDialog.correctMemory')}
              </button>
              <button type="button" role="menuitem" data-danger onClick={askDelete}>
                {t('common.delete')}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function EditRow({
  item,
  onDone,
}: {
  item: Memory
  onDone: () => void
}) {
  const [draft, setDraft] = useState(item.text)
  const dirty = draft.trim() !== item.text
  const save = () => {
    if (!dirty || !draft.trim()) return
    void updateMemory(item.id, draft.trim(), t('arti.memory.sourceManual')).then(onDone)
  }
  const addSibling = () => {
    void remember(
      [{ text: t('arti.memory.newSibling'), category: item.category, label: item.label }],
      t('arti.memory.sourceManual'),
    ).then(onDone)
  }
  return (
    <div className="ca-arti-mem__edit" data-testid="arti-memory-edit-row">
      {item.label ? <div className="ca-arti-mem__label">{item.label}</div> : null}
      <textarea
        className="ca-arti-mem__textarea"
        value={draft}
        autoFocus
        rows={3}
        data-testid="arti-memory-edit-input"
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.stopPropagation()}
      />
      <div className="ca-arti-mem__editfoot">
        <button type="button" className="ca-arti-mem__iconbtn" title={t('arti.memory.append')} data-testid="arti-memory-edit-plus" onClick={addSibling}>
          <span className="ca-icon">{Icons.plus}</span>
        </button>
        <div className="ca-arti-mem__editactions">
          <button type="button" className="ca-panel__secondary" data-testid="arti-memory-edit-cancel" onClick={onDone}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" data-testid="arti-memory-edit-save" disabled={!dirty || !draft.trim()} onClick={save}>{t('common.save')}</button>
        </div>
      </div>
    </div>
  )
}

function AssetsAdd({ onClose }: { onClose: () => void }) {
  const [purpose, setPurpose] = useState('')
  const [name, setName] = useState('')
  const canAdd = purpose.trim().length > 0
  const add = () => {
    if (!canAdd) return
    const label = name.trim() || t('arti.memory.assetDefaultLabel')
    void remember(
      [{ text: purpose.trim(), category: 'assets', label }],
      t('arti.memory.sourceAssets'),
    ).then(onClose)
  }
  return (
    <div className="ca-arti-mem__assetadd" data-testid="arti-memory-assets-add">
      <div className="ca-arti-mem__label">{t('arti.memory.assetsPurposeTitle')}</div>
      <input
        className="ca-panel__input"
        value={name}
        placeholder={t('arti.memory.assetsNamePlaceholder')}
        data-testid="arti-memory-assets-name"
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.stopPropagation()}
      />
      <textarea
        className="ca-arti-mem__textarea"
        value={purpose}
        placeholder={t('memoryDialog.explainHowTheseAssetsShould')}
        rows={3}
        data-testid="arti-memory-assets-purpose"
        onChange={(e) => setPurpose(e.target.value)}
        onKeyDown={(e) => e.stopPropagation()}
      />
      <div className="ca-arti-mem__editfoot">
        <span />
        <div className="ca-arti-mem__editactions">
          <button type="button" className="ca-panel__secondary" data-testid="arti-memory-assets-cancel" onClick={onClose}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" data-testid="arti-memory-assets-submit" disabled={!canAdd} onClick={add}>{t('common.add')}</button>
        </div>
      </div>
    </div>
  )
}

function ChatComposer({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState('')
  const [plusOpen, setPlusOpen] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  const send = () => {
    const v = text.trim()
    if (!v) return
    // mock rewrite path — no paid model; persist via remember
    void remember([{ text: v, category: 'taste' }], t('arti.memory.sourceChat')).then(() => {
      setText('')
      onClose()
    })
  }
  const fromUpload = (files: FileList | null) => {
    const f = files?.[0]
    if (!f) return
    void remember(
      [{ text: t('arti.memory.uploadedAsset', f.name), category: 'assets', label: f.name }],
      t('arti.memory.sourceUpload'),
    ).then(() => setPlusOpen(false))
  }
  const fromLibrary = () => {
    void remember(
      [{ text: t('arti.memory.libraryAsset'), category: 'assets', label: t('arti.memory.libraryAssetLabel') }],
      t('arti.memory.sourceLibrary'),
    ).then(() => setPlusOpen(false))
  }
  return (
    <div className="ca-arti-mem__composer" data-testid="arti-memory-composer">
      <div className="ca-chat__hint">{t('arti.memory.chatHelper')}</div>
      <div className="ca-arti-mem__composerbox">
        <div className="ca-arti-mem__pluswrap">
          <button type="button" className="ca-arti-mem__iconbtn" data-testid="arti-memory-composer-plus" aria-expanded={plusOpen} onClick={() => setPlusOpen((v) => !v)}>
            <span className="ca-icon">{Icons.plus}</span>
          </button>
          {plusOpen ? (
            <div className="ca-arti-mem__menu ca-arti-mem__menu--up" role="menu" data-testid="arti-memory-composer-plus-menu">
              <button type="button" role="menuitem" data-testid="arti-memory-upload-local" onClick={() => file.current?.click()}>
                {t('arti.memory.uploadLocal')}
              </button>
              <button type="button" role="menuitem" data-testid="arti-memory-pick-library" onClick={fromLibrary}>
                {t('arti.memory.pickLibrary')}
              </button>
            </div>
          ) : null}
          <input ref={file} type="file" hidden accept="image/*,.pdf,.txt,.md" onChange={(e) => { fromUpload(e.target.files); e.target.value = '' }} />
        </div>
        <textarea
          className="ca-arti-mem__composerinput"
          value={text}
          placeholder={t('arti.memory.chatPlaceholder')}
          rows={2}
          data-testid="arti-memory-composer-input"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation()
            if (isEnter(e) && !e.shiftKey) { e.preventDefault(); send() }
          }}
        />
        <button type="button" className="ca-arti-mem__send" data-testid="arti-memory-composer-send" disabled={!text.trim()} onClick={send} title={t('arti.memory.send')}>
          <span className="ca-icon">{Icons.send}</span>
        </button>
      </div>
      <button type="button" className="ca-panel__secondary ca-arti-mem__composerclose" data-testid="arti-memory-composer-close" onClick={onClose}>{t('common.cancel')}</button>
    </div>
  )
}

function MemoryGroup({
  cat,
  items,
  editingId,
  setEditingId,
  menuId,
  setMenuId,
  addingAssets,
  setAddingAssets,
  allEmpty,
}: {
  cat: CatId
  items: Memory[]
  editingId: string | null
  setEditingId: (id: string | null) => void
  menuId: string | null
  setMenuId: (id: string | null) => void
  addingAssets: boolean
  setAddingAssets: (v: boolean) => void
  allEmpty: boolean
}) {
  return (
    <section className="ca-arti-mem__group" data-testid={`arti-memory-group-${cat}`}>
      <h3 className="ca-arti-mem__grouptitle">
        <span className="ca-icon">{GROUP_ICONS[cat]}</span>
        {groupLabel(cat)}
      </h3>
      <div className="ca-arti-mem__list">
        {items.map((m) => (
          editingId === m.id
            ? <EditRow key={m.id} item={m} onDone={() => setEditingId(null)} />
            : <MemoryRow key={m.id} item={m} menuId={menuId} setMenuId={setMenuId} onEdit={setEditingId} />
        ))}
        {cat === 'assets' && addingAssets ? (
          <AssetsAdd onClose={() => setAddingAssets(false)} />
        ) : null}
        {cat === 'assets' && !addingAssets ? (
          <button
            type="button"
            className="ca-arti-mem__addasset"
            data-testid="arti-memory-assets-empty"
            onClick={() => setAddingAssets(true)}
          >
            <span className="ca-icon">{Icons.plus}</span>
            {t('arti.memory.addAssets')}
          </button>
        ) : null}
        {cat !== 'assets' && items.length === 0 && !allEmpty ? (
          <div className="ca-arti-mem__empty" data-testid={`arti-memory-empty-${cat}`}>{t('arti.memory.groupEmpty')}</div>
        ) : null}
      </div>
    </section>
  )
}

/** #368: Arti memory center — four groups + inline edit + chat-to-edit (mock-first). */
export function ArtiMemory() {
  const memory = useValue(memoryAtom)
  const loadError = useValue(memoryErrorAtom)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [menuId, setMenuId] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [addingAssets, setAddingAssets] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // #381: an empty store stays empty — guidance copy only, nothing is seeded
    void loadMemory().finally(() => setReady(true))
  }, [])

  useEffect(() => {
    if (!menuId) return
    const onDoc = (e: MouseEvent) => {
      const el = e.target as HTMLElement | null
      if (el?.closest?.('.ca-arti-mem__menwrap')) return
      setMenuId(null)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuId])

  const byCat = (id: CatId) => memory.filter((m) => (m.category ?? 'about') === id)

  return (
    <div className="ca-arti-mem" data-testid="arti-memory-center">
      {!ready ? <div className="ca-chat__hint">{t('arti.memory.loading')}</div> : null}
      {/* #381: the server is the only truth; when it can't be read we show an error, never a stale/local list */}
      {loadError ? (
        <div className="ca-arti-mem__guide" role="alert" data-testid="arti-memory-error">
          {t('arti.memory.loadFailed')}{' '}
          <button type="button" className="ca-arti-mem__retry" data-testid="arti-memory-retry" onClick={() => void loadMemory()}>{t('arti.memory.retry')}</button>
        </div>
      ) : null}
      {!loadError ? <div className="ca-arti-mem__groups" data-testid="arti-memory-groups">
        {(['about', 'work', 'taste', 'assets'] as CatId[]).map((cat) => (
          <MemoryGroup
            key={cat}
            cat={cat}
            items={byCat(cat)}
            editingId={editingId}
            setEditingId={setEditingId}
            menuId={menuId}
            setMenuId={setMenuId}
            addingAssets={addingAssets}
            setAddingAssets={setAddingAssets}
            allEmpty={ready && memory.length === 0}
          />
        ))}
      </div> : null}

      {ready && !loadError && memory.length === 0 ? (
        <div className="ca-arti-mem__guide" data-testid="arti-memory-empty-guide">{t('arti.memory.emptyGuide')}</div>
      ) : null}

      <div className="ca-arti-mem__sticky" data-testid="arti-memory-chat-cta">
        {chatOpen ? (
          <ChatComposer onClose={() => setChatOpen(false)} />
        ) : (
          <button type="button" className="ca-arti-mem__cta" data-testid="arti-memory-chat-open" onClick={() => setChatOpen(true)}>
            {t('arti.memory.chatCta')}
          </button>
        )}
      </div>
    </div>
  )
}
