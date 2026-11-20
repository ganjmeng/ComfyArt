/** Controllable api for the real startBot → refreshBot → openChat chain. */

type Gate = { path: string; finish: () => void }

export const gates: Gate[] = []
export const chatReads: string[] = []
/** Production selection sampled by the test at each release and chat read. */
let noteSelection: (where: string) => void = () => {}

export function setNoteSelection(fn: (where: string) => void) {
  noteSelection = fn
}

function ok(body: unknown) {
  return { ok: true, status: 200, json: async () => body }
}

function bodyFor(path: string): unknown {
  if (path.startsWith('/comfyart/bot/status')) return { enabled: true, user: 'me', providers: [] }
  if (path.startsWith('/comfyart/settings')) return {}
  if (path.startsWith('/comfyart/bot/chats?')) return { chats: [] }
  if (path.includes('/asks')) return { asks: [] }
  const id = decodeURIComponent(path.split('/comfyart/bot/chats/')[1]?.split('?')[0] ?? '')
  return { chat: { id, project: 'p', user: 'me', title: '', provider: 'local-llm' }, messages: [] }
}

export function api(path: string) {
  if (/^\/comfyart\/bot\/chats\/[^/?]+\?project=/.test(path)) {
    chatReads.push(path)
    noteSelection(`read ${path}`)
    return Promise.resolve(ok(bodyFor(path)))
  }
  if (path.includes('/asks')) return Promise.resolve(ok({ asks: [] }))
  return new Promise((resolve) => {
    let done = false
    gates.push({
      path,
      finish: () => {
        if (done) return
        done = true
        noteSelection(`release ${path}`)
        resolve(ok(bodyFor(path)))
      },
    })
  })
}

export function setAgentPlanConfirmed() {}

export function resetChain() {
  gates.length = 0
  chatReads.length = 0
}

export async function tick() {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

/** Resolve the refresh calls already queued in [start, end), then the loadChats call they unblocked. */
export async function finishRefresh(start: number, syncEnd: number) {
  for (let i = start; i < syncEnd; i++) gates[i].finish()
  await tick()
  for (let i = syncEnd; i < gates.length; i++) {
    if (gates[i].path.startsWith('/comfyart/bot/chats?')) gates[i].finish()
  }
  await tick()
  await tick()
}
