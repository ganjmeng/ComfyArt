/** #386: canvas-review state machine (pure). Illegal transitions throw. */

export type ReviewPhase = 'idle' | 'scheduled' | 'exporting' | 'reviewing' | 'notified' | 'failed'

export type ReviewEvent =
  | 'schedule' // arm / re-arm debounce → scheduled
  | 'start_export' // debounce fired → exporting
  | 'start_review' // export done → reviewing
  | 'succeed' // ask ok → notified
  | 'fail' // ask/export error → failed
  | 'cancel' // user/project leave → idle
  | 'ack' // consume terminal → idle

/** Legal edges. Anything else is illegal. */
export const REVIEW_TRANSITIONS: Record<ReviewPhase, Partial<Record<ReviewEvent, ReviewPhase>>> = {
  idle: { schedule: 'scheduled', cancel: 'idle', ack: 'idle' },
  scheduled: { schedule: 'scheduled', start_export: 'exporting', cancel: 'idle' },
  exporting: { start_review: 'reviewing', fail: 'failed', cancel: 'idle' },
  reviewing: { succeed: 'notified', fail: 'failed', cancel: 'idle' },
  notified: { ack: 'idle', cancel: 'idle' },
  failed: { ack: 'idle', cancel: 'idle' },
}

export class IllegalReviewTransition extends Error {
  constructor(readonly from: ReviewPhase, readonly event: ReviewEvent) {
    super(`illegal review transition: ${from} + ${event}`)
    this.name = 'IllegalReviewTransition'
  }
}

/** Apply one event. Throws IllegalReviewTransition when the pair is not in the table. */
export function transition(phase: ReviewPhase, event: ReviewEvent): ReviewPhase {
  const next = REVIEW_TRANSITIONS[phase][event]
  if (!next) throw new IllegalReviewTransition(phase, event)
  return next
}

/** Soft apply: illegal pairs leave phase unchanged and return ok:false (for UI guards). */
export function tryTransition(phase: ReviewPhase, event: ReviewEvent): { ok: true; phase: ReviewPhase } | { ok: false; phase: ReviewPhase } {
  const next = REVIEW_TRANSITIONS[phase][event]
  if (!next) return { ok: false, phase }
  return { ok: true, phase: next }
}

export const REVIEW_PHASES: ReviewPhase[] = ['idle', 'scheduled', 'exporting', 'reviewing', 'notified', 'failed']
export const REVIEW_EVENTS: ReviewEvent[] = ['schedule', 'start_export', 'start_review', 'succeed', 'fail', 'cancel', 'ack']
