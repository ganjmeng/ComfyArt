import { useState } from 'react'

import { t } from '../i18n'

/** #541 「效果示例」: 704×506 contain-centred stage + thumbnail strip. Data-driven from skill.examples;
 *  renders nothing when a skill has none (personal / imported skills, or examples not washed yet). */
export function SkillExamples({ examples }: { examples?: string[] }) {
  const [at, setAt] = useState(0)
  if (!examples?.length) return null
  const cur = examples[Math.min(at, examples.length - 1)]
  return (
    <section className="ca-skillrun__examples" data-testid="skill-run-examples" data-count={examples.length}>
      <div className="ca-skillrun__section">{t('skillRun.examples')}</div>
      <div className="ca-skillrun__stage" data-testid="skill-run-example-stage"><img src={cur} alt="" /></div>
      {examples.length > 1 && (
        <div className="ca-skillrun__strip" role="tablist">
          {examples.map((src, i) => (
            <button key={src} type="button" role="tab" aria-selected={i === at} data-on={i === at || undefined}
              className="ca-skillrun__thumb" data-testid="skill-run-example-thumb" onClick={() => setAt(i)}><img src={src} alt="" /></button>
          ))}
        </div>
      )}
    </section>
  )
}
