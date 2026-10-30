/** #424: memory-fallback daily quota helpers (pure). Charge only after a real write. */

/** May the memory fallback attempt a write? No quota charge yet — charge only after a real write. */
export function memoryFallbackAllowed(wroteInLoop: boolean, runs: number, daily: number, abilityOn: boolean): boolean {
  return abilityOn && !wroteInLoop && runs < daily
}
