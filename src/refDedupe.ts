/** #389: one composer chip per canvas shape, even when it is both selected and @-mentioned. Dedupe by id, never by name. */
export function mergeRefIds<T extends string>(selected: readonly T[], hidden: readonly T[], extra: readonly T[]): T[] {
  const out: T[] = []
  for (const id of [...selected.filter((x) => !hidden.includes(x)), ...extra]) if (!out.includes(id)) out.push(id)
  return out
}

/** #389: removing the single chip drops the id from every source (@ list and selection), so nothing reappears. */
export function removeRefId<T extends string>(id: T, selected: readonly T[], hidden: readonly T[], extra: readonly T[]): { hidden: T[]; extra: T[] } {
  return {
    extra: extra.filter((x) => x !== id),
    hidden: selected.includes(id) && !hidden.includes(id) ? [...hidden, id] : [...hidden],
  }
}
