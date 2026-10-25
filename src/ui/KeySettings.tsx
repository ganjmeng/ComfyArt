import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { t } from '../i18n'
import { thresholdUsd } from '../usd'
import { deleteKey, getConfirmUsd, setConfirmUsd, KeyError, keySettingsOpenAtom, keyStatusAtom, outOfCredit, refreshKeyStatus, saveKey, WAVESPEED_KEYS_URL } from '../wavespeedKey'
import { Modal } from './Modal'

const money = (n: number) => `$${n.toFixed(2)}`

export function keyStateText(): string {
  const s = keyStatusAtom.get()
  if (!s?.configured) return t('wsKey.notSet')
  if (s.error === 'invalid') return t('wsKey.invalid')
  if (s.error) return t('wsKey.network')
  if (s.balance === null) return t('wsKey.checking')
  return outOfCredit(s) ? t('wsKey.zero') : t('wsKey.ok', money(s.balance))
}

/** WaveSpeed API key: status, masked key, save / replace / remove. Reuses the Agent settings modal styles. */
export function KeySettings() {
  const open = useValue(keySettingsOpenAtom)
  const status = useValue(keyStatusAtom)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [usd, setUsd] = useState('')
  const [usdErr, setUsdErr] = useState('')

  useEffect(() => {
    if (!open) return
    setDraft(''); setErr(''); setUsdErr('')
    void refreshKeyStatus()
    getConfirmUsd().then((v) => setUsd(thresholdUsd(v))).catch(() => {})
  }, [open])

  if (!open) return null
  const close = () => keySettingsOpenAtom.set(false)
  const fromEnv = status?.source === 'env'
  const save = () => {
    setBusy(true); setErr('')
    saveKey(draft.trim()).then(() => { setDraft(''); close() }).catch((e) => {
      const reason = e instanceof KeyError ? e.reason : 'error'
      setErr(reason === 'invalid' ? t('wsKey.invalid') : reason === 'network' ? t('wsKey.network') : String(e.message || e))
    }).finally(() => setBusy(false))
  }
  const ok = status?.configured && !status.error
  const saveUsd = () => {
    const v = Number(usd)
    if (usd.trim() === '' || !Number.isFinite(v) || v < 0 || v > 1000) { setUsdErr(t('wsKey.confirmBad')); return }
    setUsdErr('')
    setConfirmUsd(v).then((x) => setUsd(thresholdUsd(x))).catch(() => setUsdErr(t('wsKey.confirmBad')))
  }

  return (
    <Modal title={t('wsKey.title')} onClose={close}>
      <div className="ca-rename__body">
        <div className="ca-keys__row">
          <span>{t('wsKey.status')}</span>
          <span className="ca-menu__key" data-testid="ws-key-state">{keyStateText()}</span>
        </div>
        {status?.configured && (
          <div className="ca-keys__row">
            <span>{fromEnv ? t('wsKey.fromEnv') : t('wsKey.saved')}</span>
            <span className="ca-menu__key">{`••••••••${status.last4}`}</span>
          </div>
        )}
        {ok && outOfCredit(status) && <div className="ca-chat__hint">{t('wsKey.topUp')}</div>}
        {fromEnv ? (
          <div className="ca-chat__hint">{t('wsKey.envReadOnly')}</div>
        ) : (
          <>
            <label className="ca-rename__field ca-rename__field--key">
              <span>{status?.configured ? t('wsKey.replace') : t('wsKey.enter')}</span>
              <input className="ca-panel__input" type="password" autoComplete="off" value={draft} placeholder={t('wsKey.placeholder')} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter' && draft.trim()) save() }} />
            </label>
            {err && <div className="ca-chat__hint" role="alert" style={{ color: 'var(--ca-error-text)' }}>{err}</div>}
            <div className="ca-chat__hint">
              {t('wsKey.getKey')} <a href={WAVESPEED_KEYS_URL} target="_blank" rel="noreferrer">wavespeed.ai/accesskey</a>
            </div>
          </>
        )}
        <label className="ca-rename__field ca-rename__field--key">
          <span>{t('wsKey.confirmUsd', usd.trim() && Number.isFinite(Number(usd)) ? thresholdUsd(Number(usd)) : 'X')}</span>
          <input className="ca-panel__input" data-testid="ws-confirm-usd" inputMode="decimal" value={usd} onChange={(e) => setUsd(e.target.value)} onBlur={saveUsd} onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') saveUsd() }} />
        </label>
        {usdErr && <div className="ca-chat__hint" role="alert" style={{ color: 'var(--ca-error-text)' }}>{usdErr}</div>}
        <div className="ca-panel__foot">
          {status?.source === 'settings' && <button type="button" className="ca-panel__secondary" onClick={() => void deleteKey()}>{t('common.delete')}</button>}
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.close')}</button>
          {!fromEnv && <button type="button" className="ca-panel__primary" disabled={!draft.trim() || busy} onClick={save}>{busy ? t('wsKey.checkingKey') : t('common.save')}</button>}
        </div>
      </div>
    </Modal>
  )
}
