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

/**
 * One startBot call. Cleanup or a later startBot advances the epoch, so a
 * refreshBot().finally from the old call cannot mint a new chat read.
 */
export class InitEpoch {
  private epoch = 0

  begin(): number {
    this.epoch += 1
    return this.epoch
  }

  cancel(): void {
    this.epoch += 1
  }

  current(): number {
    return this.epoch
  }

  isCurrent(epoch: number): boolean {
    return epoch === this.epoch
  }
}

/**
 * Chat id to open when an initialization's refresh finishes.
 * Null means leave the selection alone: cancelled init, no chat param, or the
 * live URL no longer asks for the chat this init captured.
 */
export function settleBotInit(args: {
  epoch: number
  currentEpoch: number
  stale: boolean
  captured: ChatLink
  live: ChatLink
  projectId: string
}): string | null {
  if (args.stale || args.epoch !== args.currentEpoch) return null
  if (args.captured.kind !== 'open' || args.live.kind !== 'open') return null
  if (args.captured.project !== args.projectId || args.live.project !== args.projectId) return null
  if (args.captured.chat !== args.live.chat || args.captured.project !== args.live.project) return null
  return args.live.chat
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
