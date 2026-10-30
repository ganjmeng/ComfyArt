/** #463 G4 — "Import" drop dialog: drop a Skill folder or a .zip; click opens a file picker. */
import { useState, useRef, type DragEvent } from 'react'

import { errorText } from '../jobs'
import { t } from '../i18n'
import { importEntries, importZip, isZip, type Skill, type SkillEntry } from '../skills'
import { Icons } from './icons'
import { Modal } from './Modal'

type Entry = { isFile: boolean; isDirectory: boolean; name: string; fullPath: string }
type FileEntry = Entry & { file: (ok: (f: File) => void, err: (e: unknown) => void) => void }
type DirEntry = Entry & { createReader: () => { readEntries: (ok: (list: Entry[]) => void, err: (e: unknown) => void) => void } }

/** Walks a dropped directory (webkitGetAsEntry) into path + file pairs. */
async function walk(entry: Entry, out: SkillEntry[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File>((ok, err) => (entry as FileEntry).file(ok, err))
    out.push({ path: entry.fullPath.replace(/^\//, ''), file })
    return
  }
  if (!entry.isDirectory) return
  const reader = (entry as DirEntry).createReader()
  for (;;) {
    const batch = await new Promise<Entry[]>((ok, err) => reader.readEntries(ok, err))
    if (!batch.length) break
    for (const child of batch) await walk(child, out)
  }
}

export function SkillImportDialog({ onClose, onImported }: { onClose: () => void; onImported: (skill: Skill, skipped: string[]) => void }) {
  const zip = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = (fn: () => Promise<{ skill: Skill; skipped: string[] }>) => {
    setBusy(true)
    setError('')
    void fn().then(({ skill, skipped }) => onImported(skill, skipped)).catch((e) => setError(errorText(e))).finally(() => setBusy(false))
  }
  const takeZip = (f: File | undefined) => {
    if (!f) return
    if (!isZip(f)) { setError(t('skillsImport.notZip')); return }
    run(() => importZip(f))
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    if (busy) return
    const entry = Array.from(e.dataTransfer.items ?? []).map((i) => (i as DataTransferItem & { webkitGetAsEntry?: () => Entry | null }).webkitGetAsEntry?.()).find(Boolean)
    if (entry?.isDirectory) {
      run(async () => { const out: SkillEntry[] = []; await walk(entry, out); return importEntries(out, entry.name) })
      return
    }
    takeZip(Array.from(e.dataTransfer.files)[0])
  }

  return (
    <Modal title={t('skillsImport.title')} className="ca-rename ca-skimport" onClose={onClose}>
      <div className="ca-rename__body" data-testid="skill-import-dialog">
        <button
          type="button"
          className="ca-skimport__drop"
          data-over={over || undefined}
          data-busy={busy || undefined}
          data-testid="skill-import-drop"
          disabled={busy}
          onClick={() => zip.current?.click()}
          onDragEnter={(e) => { e.preventDefault(); setOver(true) }}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setOver(true) }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false) }}
          onDrop={onDrop}
        >
          <span className="ca-skimport__icon ca-icon">{Icons.upload}</span>
          <span className="ca-skimport__title">{busy ? t('skillsImport.importing') : over ? t('skillsImport.release') : t('skillsImport.drop')}</span>
        </button>
        <input ref={zip} type="file" accept=".zip,application/zip" hidden data-testid="skill-import-zip-input" onChange={(e) => { takeZip(e.target.files?.[0]); e.target.value = '' }} />
        {error && <div className="ca-skimport__error" role="alert">{error}</div>}
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={onClose}>{t('common.cancel')}</button>
        </div>
      </div>
    </Modal>
  )
}
