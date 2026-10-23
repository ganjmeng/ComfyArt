// #145: the real Popover + RefControls + Confirm inside .ca-root, the way GenPanel/App mount them.
import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Confirm } from '../../../src/ui/Confirm'
import { Popover } from '../../../src/ui/Popover'
import { RefControls } from '../../../src/ui/RefControls'
import { REF_MODES } from '../../../src/refModes'
import { setLang } from '../i18n_stub'
;(globalThis as any).__setLang = setLang

const g = globalThis as any
g.__modes = REF_MODES.filter((m) => m.node).map((m) => m.id)  // every mode with an extract button (structure + color)
g.__errors = []

function Panel() {
  const [open, setOpen] = useState(true)
  const [mode, setMode] = useState(new URLSearchParams(location.search).get('mode') ?? 'seg')
  g.__setMode = setMode
  g.__popOpen = open
  const m = REF_MODES.find((x) => x.id === mode)!
  return (
    <div className="ca-root">
      <div className="ca-gen" style={{ left: 200, top: 300 }}>
        <Popover open={open} onOpenChange={setOpen} side="top" trigger={({ toggle }) => <span className="ca-gen__refmode" onClick={toggle}>{m.label}</span>}>
          <div className="ca-menu ca-refmodes" style={{ width: 360 }}>
            <RefControls key={mode} src="ref.png" mode={m} value={undefined} onChange={() => {}} onError={(e) => g.__errors.push(e)} />
          </div>
        </Popover>
      </div>
      <Confirm />
    </div>
  )
}
createRoot(document.getElementById('root')!).render(<Panel />)
