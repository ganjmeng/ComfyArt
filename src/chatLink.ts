/** Project-page deep link. `?project=` alone is unchanged. `?chat=` without `?project=` is an invalid link. */

export type ChatLink =
  | { kind: 'absent' }
  | { kind: 'invalid' }
  | { kind: 'open'; project: string; chat: string }

export function readChatLink(params: { get(name: string): string | null }): ChatLink {
  const chat = (params.get('chat') ?? '').trim()
  const project = (params.get('project') ?? '').trim()
  if (!chat) return { kind: 'absent' }
  if (!project) return { kind: 'invalid' }
  return { kind: 'open', project, chat }
}

/** Existing chat-read URL. The server requires `project` and checks access before it returns messages. */
export function chatReadPath(project: string, chat: string): string {
  return `/comfyart/bot/chats/${encodeURIComponent(chat)}?project=${encodeURIComponent(project)}`
}

/** Drops a chat read that is still in flight after the link or the open project changes. */
export class ChatReadGate {
  private token = 0

  begin(): number {
    this.token += 1
    return this.token
  }

  invalidate(): void {
    this.token += 1
  }

  isCurrent(token: number): boolean {
    return token === this.token
  }
}
