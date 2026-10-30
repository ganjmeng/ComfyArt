/** #424: memory fallback quota — charge only after a real write; skip charge when in-loop already wrote. */
import { memoryFallbackAllowed } from '../../src/proactiveQuota'

type Runs = { memory?: number }

/** Mirror take() for memory only — used to simulate post-write charge in the harness. */
function chargeMemory(state: { runs: Runs }, abilityOn: boolean, daily: number): boolean {
  if (!abilityOn || (state.runs.memory ?? 0) >= daily) return false
  state.runs.memory = (state.runs.memory ?? 0) + 1
  return true
}

/** Simulate onTurnDone memory branch (#424): plan → optional learn → charge iff wrote. */
function simulateTurn(opts: {
  wroteInLoop: boolean
  abilityOn: boolean
  daily: number
  runsBefore: number
  learnedCount: number
}): { allowed: boolean; charged: boolean; runsAfter: number } {
  const state = { runs: { memory: opts.runsBefore } as Runs }
  const allowed = memoryFallbackAllowed(opts.wroteInLoop, state.runs.memory ?? 0, opts.daily, opts.abilityOn)
  let charged = false
  if (allowed && opts.learnedCount > 0) charged = chargeMemory(state, opts.abilityOn, opts.daily)
  return { allowed, charged, runsAfter: state.runs.memory ?? 0 }
}

const out: Record<string, unknown> = {}

out.already_wrote_no_charge = simulateTurn({
  wroteInLoop: true, abilityOn: true, daily: 5, runsBefore: 0, learnedCount: 99,
})
out.fallback_wrote_charges = simulateTurn({
  wroteInLoop: false, abilityOn: true, daily: 5, runsBefore: 2, learnedCount: 1,
})
out.fallback_empty_no_charge = simulateTurn({
  wroteInLoop: false, abilityOn: true, daily: 5, runsBefore: 2, learnedCount: 0,
})
out.disabled_no_run = simulateTurn({
  wroteInLoop: false, abilityOn: false, daily: 5, runsBefore: 0, learnedCount: 3,
})
out.at_limit_no_run = simulateTurn({
  wroteInLoop: false, abilityOn: true, daily: 5, runsBefore: 5, learnedCount: 2,
})
out.allowed_matrix = {
  wrote: memoryFallbackAllowed(true, 0, 5, true),
  ok: memoryFallbackAllowed(false, 0, 5, true),
  off: memoryFallbackAllowed(false, 0, 5, false),
  full: memoryFallbackAllowed(false, 5, 5, true),
}

process.stdout.write(JSON.stringify(out) + '\n')
