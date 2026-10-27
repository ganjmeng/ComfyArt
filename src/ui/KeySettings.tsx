import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { t } from '../i18n'
import { thresholdCredits } from '../usd'
import { deleteKey, getConfirmCredits, setConfirmCredits, KeyError, keySettingsOpenAtom, keyStatusAtom, outOfCredit, refreshKeyStatus, saveKey, WAVESPEED_KEYS_URL } from '../wavespeedKey'
import { Modal } from './Modal'

const money = (n: number) => `$${n.toFixed(2)}`

export function keyStateText(): string {
  const s = keyStatusAtom.get()
  if (s === null) return t('wsKey.checking')  // #305: loading ≠ Not set
  if (!s.configured) return t('wsKey.notSet')
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
  const [credits, setCredits] = useState('')
  const [creditsErr, setCreditsErr] = useState('')

  useEffect(() => {
    if (!open) return
    setDraft(''); setErr(''); setCreditsErr('')
    void refreshKeyStatus()
    getConfirmCredits().then((v) => setCredits(thresholdCredits(v))).catch(() => {})
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
  const saveCredits = () => {
    const v = Number(credits)
    // #397: integer credits 0..100000 (same ceiling as the old $0–$1000 range)
    if (credits.trim() === '' || !Number.isFinite(v) || v < 0 || v > 100000 || !Number.isInteger(v)) {
      setCreditsErr(t('wsKey.confirmBad')); return
    }
    setCreditsErr('')
    setConfirmCredits(v).then((x) => setCredits(thresholdCredits(x))).catch(() => setCreditsErr(t('wsKey.confirmBad')))
  }

  return (
    <Modal title={t('wsKey.title')} className="ca-rename ca-rename--key" onClose={close}>
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
          <span>{t('wsKey.confirmUsd', credits.trim() && Number.isFinite(Number(credits)) ? thresholdCredits(Number(credits)) : 'X')}</span>
          <input className="ca-panel__input" data-testid="ws-confirm-credits" inputMode="numeric" value={credits} onChange={(e) => setCredits(e.target.value)} onBlur={saveCredits} onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') saveCredits() }} />
        </label>
        {creditsErr && <div className="ca-chat__hint" role="alert" style={{ color: 'var(--ca-error-text)' }}>{creditsErr}</div>}
        <div className="ca-panel__foot">
          {status?.source === 'settings' && <button type="button" className="ca-panel__secondary" onClick={() => void deleteKey()}>{t('common.delete')}</button>}
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.close')}</button>
          {!fromEnv && <button type="button" className="ca-panel__primary" disabled={!draft.trim() || busy} onClick={save}>{busy ? t('wsKey.checkingKey') : t('common.save')}</button>}
        </div>
      </div>
    </Modal>
  )
}
