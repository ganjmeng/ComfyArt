import { TOP_UP_URL } from '../wsErrors'
import {
  BaseBoxShapeUtil,
  createShapePropsMigrationIds,
  createShapePropsMigrationSequence,
  HTMLContainer,
  T,
  type RecordProps,
  type TLShape,
  useValue,
} from 'tldraw'

import { isVideo } from '../models'
import { progressAtom } from '../progress'
import { resultsAtom } from '../jobs'
import { Icons } from '../ui/icons'
import { t } from '../i18n'

export const GENERATOR = 'generator'
/** #287: shared with the home composer, which has no editor to ask for defaults. */
export const GENERATOR_DEFAULTS: GeneratorShape['props'] = { w: 512, h: 512, prompt: '', ratio: '1:1', resolution: '1K', count: 1, workflow: '', duration: 5, transparent: false, quality: 'standard', style: '', cw: 1024, ch: 1024 }

declare module 'tldraw' {
  export interface TLGlobalShapePropsMap {
    [GENERATOR]: {
      w: number
      h: number
      prompt: string
      ratio: string
      resolution: string
      count: number
      workflow: string
      duration: number
      transparent: boolean
      quality: string
      style: string
      cw: number
      ch: number
    }
  }
}

export type GeneratorShape = TLShape<typeof GENERATOR>

const versions = createShapePropsMigrationIds(GENERATOR, { AddDuration: 1, AddOptions: 2 })

/** #163: the top-up URL in the insufficient-balance copy is clickable; same text, no new wording. */
export function withTopUpLink(text: string) {
  const i = text.indexOf(TOP_UP_URL)
  if (i < 0) return text
  return <>{text.slice(0, i)}<a href={TOP_UP_URL} target="_blank" rel="noreferrer" onPointerDown={(e) => e.stopPropagation()}>{TOP_UP_URL}</a>{text.slice(i + TOP_UP_URL.length)}</>
}

export class GeneratorShapeUtil extends BaseBoxShapeUtil<GeneratorShape> {
  static override type = GENERATOR
  static override props: RecordProps<GeneratorShape> = {
    w: T.number,
    h: T.number,
    prompt: T.string,
    ratio: T.string,
    resolution: T.string,
    count: T.number,
    workflow: T.string,
    duration: T.number,
    transparent: T.boolean,
    quality: T.string,
    style: T.string,
    cw: T.number,
    ch: T.number,
  }

  static override migrations = createShapePropsMigrationSequence({
    sequence: [
      { id: versions.AddDuration, up: (props) => { props.duration = 5 } },
      { id: versions.AddOptions, up: (props) => Object.assign(props, { transparent: false, quality: 'standard', style: '', cw: 1024, ch: 1024 }) },
    ],
  })

  override getDefaultProps(): GeneratorShape['props'] {
    return { ...GENERATOR_DEFAULTS }
  }

  override canEdit() {
    return false
  }

  override component(shape: GeneratorShape) {
    return <GeneratorCard shape={shape} />
  }

  override getIndicatorPath(shape: GeneratorShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

function GeneratorCard({ shape }: { shape: GeneratorShape }) {
  const job = shape.meta.job as { id: string } | undefined
  const progress = useValue('generator progress', () => (job ? progressAtom.get()[job.id] : undefined), [job?.id])
  const error = useValue('generator error', () => (job ? undefined : resultsAtom.get()[shape.id]?.error), [job?.id, shape.id])
  const p = progress && progress.max > 0 ? Math.min(1, progress.value / progress.max) : 0
  return (
    <HTMLContainer
      className={job ? 'ca-gen-card ca-gen-frame' : 'ca-gen-card'}
      data-running={job ? true : undefined}
    >
      <span className="ca-gen-card__icon">{isVideo(shape.props.workflow) ? Icons.video : Icons.image}</span>
      {error && <div className="ca-gen-card__error" role="alert">{withTopUpLink(error)}</div>}
      {job && <div className="ca-gen-frame__pill">{t('taskDetails.generating')}</div>}
      {job && <div className="ca-gen-ring" data-indeterminate={p > 0 ? undefined : true} style={{ '--ca-p': p } as React.CSSProperties} />}
    </HTMLContainer>
  )
}
