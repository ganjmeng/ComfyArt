import { useValue, type Editor } from 'tldraw'

import { createRefFrame, refFrameContents, refFrameOf, refLinkedOf, setRefLinked } from '../chatFrame'
import { Icons } from './icons'
import { t } from '../i18n'

export function RefFrameButton({ editor }: { editor: Editor }) {
  const state = useValue('ref frame', () => {
    const frame = refFrameOf(editor)
    if (!frame) return null
    const { media, notes } = refFrameContents(editor, frame)
    return { count: media.length + notes.length, linked: refLinkedOf(editor) }
  }, [editor])
  const click = () => {
    if (!state) {
      createRefFrame(editor)
      setRefLinked(editor, true)
    } else setRefLinked(editor, !state.linked)
  }
  const title = !state ? t('chatFrame.createRefTip') : state.linked ? t('chatFrame.linkedTip') : state.count ? t('chatFrame.linkTip') : t('chatFrame.emptyTip')
  return (
    <button type="button" className="ca-bar__btn ca-refbtn" data-on={state?.linked || undefined} title={title} onClick={click}>
      <span className="ca-icon">{Icons.frame}</span><span>{t('chatFrame.ref')}</span>
      {/* #282: the count is its own span so the agent-bar collapse (which hides the word) never hides the number */}
      {state?.count ? <span className="ca-refbtn__count">{state.count}</span> : null}
    </button>
  )
}
