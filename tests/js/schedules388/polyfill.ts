/** Must be imported first — schedules.ts constructs BroadcastChannel at module load. */
const g = globalThis as any
g.window = g
g.document = { hidden: false }
g.Notification = { permission: 'denied', requestPermission: async () => 'denied' }
// Always override — Node's real BroadcastChannel keeps the process alive.
g.BroadcastChannel = class {
  onmessage: any
  postMessage() {}
  addEventListener() {}
  close() {}
}
g.location = { href: 'http://localhost/?project=p1' }
export {}
