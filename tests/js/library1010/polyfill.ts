/** In-memory BroadcastChannel. Node's built-in channel keeps the process alive. */
const g = globalThis as any
const channels = new Map<string, Set<FakeChannel>>()

class FakeChannel {
  onmessage: ((ev: { data: unknown }) => void) | null = null
  constructor(readonly name: string) {
    if (!channels.has(name)) channels.set(name, new Set())
    channels.get(name)!.add(this)
  }
  postMessage(data: unknown) {
    for (const ch of channels.get(this.name) ?? []) {
      if (ch !== this) ch.onmessage?.({ data })
    }
  }
  close() { channels.get(this.name)?.delete(this) }
  addEventListener() {}
  removeEventListener() {}
}

g.BroadcastChannel = FakeChannel
g.document = { fonts: { add() {} } }
g.FontFace = class {
  constructor(public family: string, public source: string) {}
  load() { return Promise.resolve(this) }
}
