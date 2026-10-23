// #109: 「重新提取」 is decided by what the button shows, not by module history.
// RefControls (upstream, unchanged) shows 重新提取 only while its preview <img> is mounted, so a
// request is fresh only when the map we issued for this (src, mode, res) is still on screen.
// Pure and import-free so tests can run it under plain node.

export const previewKey = (src: string, mode: string, res: number) => `${src}\n${mode}\n${res}`

/** fresh iff the URL last returned for `key` is among the preview images currently shown. */
export function wantsFresh(issued: ReadonlyMap<string, string>, key: string, shown: Iterable<string>): boolean {
  const url = issued.get(key)
  if (!url) return false
  for (const s of shown) if (s === url) return true
  return false
}
