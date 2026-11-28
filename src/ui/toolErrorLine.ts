/** Visible sentence under a failed process row. Never the raw tool JSON or a provider model id. */

function stripModelIds(text: string): string {
  return text
    .split(/(\s+)/)
    .map((part) => {
      if (!part.trim() || /^https?:\/\//i.test(part)) return part
      return part.replace(/^[\w.+-]+(?:\/[\w.+-]+){1,}/, '')
    })
    .join('')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

/** user_message when the tool result is JSON, otherwise a plain error string. Empty when neither is present. */
export function visibleToolError(text: string | undefined | null): string {
  const raw = String(text ?? '').trim().replace(/^\[(?:tool error|error)\]\s*/i, '').trim()
  if (!raw) return ''
  let message = ''
  try {
    const data = JSON.parse(raw) as unknown
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      const row = data as Record<string, unknown>
      const user = typeof row.user_message === 'string' ? row.user_message.trim() : ''
      const err = typeof row.error === 'string' ? row.error.trim() : ''
      message = user || err
    }
  } catch {
    if (!raw.startsWith('{') && !raw.startsWith('[')) message = raw
  }
  message = stripModelIds(message)
  if (!message) return ''
  return message.length > 400 ? `${message.slice(0, 400)}…` : message
}
