/** One-shot gate. The first call wins; later calls do nothing. Shared by confirm actions so a double click cannot run twice. */
export function firstGate(): () => boolean {
  let used = false
  return () => {
    if (used) return false
    used = true
    return true
  }
}
