import { atom, react } from 'tldraw'

import { api } from './comfy'
import { resultsAtom } from './jobs'
import { notify } from './notices'
import { onComfyEvent, onReconnect } from './ws'
import { lang, t } from './i18n'
import { wsBodyError } from './wsErrors'

export interface AskOption { id: string; label: string; description?: string }
export interface BotBlock {
  type: string
  text?: string
  name?: string
  input?: Record<string, any>
  id?: string
  status?: string
  duration_ms?: number
  url?: string
  shape?: string
  level?: string
  ask_id?: string
  prompt?: string
  options?: AskOption[]
  min_selections?: number
  max_selections?: number
  allow_other?: boolean
  kind?: string
  selected?: string[]
  other_text?: string
  label?: string
  holder?: string
  srcs?: string[]
  error?: string
  detail?: Record<string, any>
}
export interface BotUsage { input_tokens?: number; output_tokens?: number; cache_read_input_tokens?: number; cost_usd?: number }
export interface BotMessage { id: string; chat_id: string; parent_id: string | null; role: 'user' | 'assistant'; blocks: BotBlock[]; status: string; usage: BotUsage | null; created_at: number }
export interface BotChat { id: string; user: string; project: string; title: string; provider: string; run_mode: 'auto' | 'ask'; pinned: boolean; archived: boolean; busy?: boolean; created_at: number; updated_at: number }
export interface ModelOption { value: string; label: string; group: string }
export interface ProviderInfo { id: string; label: string; available: boolean; version: string; detail: string; logged_in: boolean | null; stateful: boolean; attachments: boolean; branch: boolean; models: string[]; model_options?: ModelOption[] }
export type BotSettings = Record<string, string | boolean | number>

export const TOOL_LABELS: Record<string, string> = {
  ToolSearch: t('bot.findTools'),
  tool_search: t('bot.findTools'),
  server_info: t('bot.checkStatus'),
  get_canvas: t('bot.viewCanvas'),
  view_canvas: t('bot.lookAtCanvas'),
  view_video: t('bot.watchVideo'),
  list_models: t('bot.viewModels'),
  brand_kits: t('bot.viewBrandKit'),
  generate_image: t('bot.generateImage'),
  generate_video: t('bot.generateVideo'),
  edit_image: t('bot.editImage'),
  animate_image: t('common.animateImage'),
  upscale_image: t('common.upscale'),
  remove_background: t('common.removeBackground'),
  expand_image: t('bot.expandImage'),
  split_layers: t('common.splitLayers'),
  change_angle: t('common.multiAngle'),
  replace_text: t('common.editText'),
  edit_region: t('common.inpaint'),
  erase_region: t('common.eraser'),
  move_object: t('common.moveObject'),
  style_transfer: t('common.styleTransfer'),
  vectorize_image: t('imageToolbar.vectorize'),
  extend_video: t('common.extendVideo'),
  upscale_video: t('actions.upscaleVideo'),
  remove_video_background: t('common.removeBackground'),
  generate_music: t('audio.music'),
  generate_sound_effect: t('audio.soundEffect'),
  text_to_speech: t('audio.voiceover'),
  edit_elements: t('imageToolbar.editElements'),
  create_mockup: t('mockup.title'),
  place_design: t('mockup.design'),
  image_to_3d: t('imageToolbar.imageTo3d'),
  wait_generation: t('bot.waitForResults'),
  place_html: t('bot.placeWebPage'),
  create_slides: t('bot.createPpt'),
  add_text: t('bot.addText'),
  add_shape: t('bot.addShape'),
  create_frame: t('bot.createArtboard'),
  update_shapes: t('bot.adjustElements'),
  delete_shapes: t('bot.deleteElements'),
  focus: t('bot.locateElements'),
  memory: t('common.memory'),
  skill: t('bot.skill'),
  custom_workflow: t('customWorkflows.title'),
  ask_user: t('bot.askYou'),
  update_plan: t('bot.plan'),
}

export const toolName = (name = '') => name.replace(/^mcp__\w+__/, '')
export const toolLabel = (name?: string) => TOOL_LABELS[toolName(name)] ?? toolName(name)

export const providersAtom = atom<ProviderInfo[]>('bot providers', [])
export const botEnabledAtom = atom<boolean | null>('bot enabled', null)
export const settingsAtom = atom<BotSettings>('bot settings', {})
export const chatsAtom = atom<BotChat[]>('bot chats', [])
export const chatIdAtom = atom<string | null>('bot chat id', null)
export const messagesAtom = atom<BotMessage[]>('bot messages', [])
export const newProviderAtom = atom<string>('bot new provider', '')

let project = ''
let me = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await api(path, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, t('err.requestFailed', res.status)))
  return body as T
}

const send = (body: unknown, method = 'POST'): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export async function loadProviders() {
  const status = await json<{ enabled: boolean; user: string; providers: ProviderInfo[] }>('/comfyart/bot/status')
  me = status.user
  botEnabledAtom.set(status.enabled)
  providersAtom.set(status.providers)
}

function applySettings(settings: BotSettings) {
  settingsAtom.set(settings)
}

export async function loadSettings() {
  applySettings(await json<BotSettings>('/comfyart/settings'))
}

export async function saveSettings(patch: BotSettings) {
  applySettings(await json<BotSettings>('/comfyart/settings', send(patch, 'PUT')))
}

export function defaultProvider(): string {
  const providers = providersAtom.get()
  const saved = String(settingsAtom.get()['bot-provider'] ?? '')
  // #219: the built-in agent is the default; a remembered external tool that is no longer detected falls back to it
  return providers.find((p) => p.id === saved && p.available)?.id ?? providers.find((p) => p.id === BUILTIN_AGENT)?.id ?? providers.find((p) => p.available)?.id ?? providers[0]?.id ?? ''
}

export const BUILTIN_AGENT = 'local-llm'
export const NO_KEY_DETAIL = 'no-wavespeed-key'

export const providerLabel = (p: ProviderInfo) => (p.id === BUILTIN_AGENT ? t('agentPicker.builtinAgent') : p.label)

/** #219: the remembered external tool that is gone, so the picker can say it fell back to the built-in agent. */
export function lostProvider(): ProviderInfo | null {
  const saved = String(settingsAtom.get()['bot-provider'] ?? '')
  const p = providersAtom.get().find((x) => x.id === saved)
  return p && !p.available && saved !== BUILTIN_AGENT ? p : null
}

export const currentChat = () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null
export const busy = () => !!currentChat()?.busy

export async function loadChats() {
  chatsAtom.set((await json<{ chats: BotChat[] }>(`/comfyart/bot/chats?project=${encodeURIComponent(project)}`)).chats)
}

export async function openChat(id: string | null) {
  chatIdAtom.set(id)
  if (!id) return messagesAtom.set([])
  const { chat, messages } = await json<{ chat: BotChat; messages: BotMessage[] }>(`/comfyart/bot/chats/${id}`)
  if (chatIdAtom.get() !== id) return
  upsertChat(chat)
  messagesAtom.set(messages)
}

function upsertChat(chat: BotChat) {
  if (chat.project !== project || chat.user !== me) return
  const list = chatsAtom.get()
  chatsAtom.set(list.some((c) => c.id === chat.id) ? list.map((c) => (c.id === chat.id ? { ...c, ...chat } : c)) : [chat, ...list])
}

async function ensureChat(): Promise<BotChat> {
  const current = currentChat()
  if (current) return current
  const provider = newProviderAtom.get() || defaultProvider()
  if (!provider) throw new Error(t('bot.noAgentAvailableConfigureOne'))
  const { chat } = await json<{ chat: BotChat }>('/comfyart/bot/chats', send({ project, provider }))
  upsertChat(chat)
  chatIdAtom.set(chat.id)
  messagesAtom.set([])
  return chat
}

export interface SendInput { text: string; refs: { id: string; src: string; name: string; kind: 'image' | 'video' | 'audio'; transcript?: string }[]; docs: { src: string; name: string }[]; kits: { name: string; description: string; images: string[] }[]; skill?: string; memory?: string; context?: string }

export async function sendMessage(input: SendInput) {
  const chat = await ensureChat()
  await json(`/comfyart/bot/chats/${chat.id}/send`, send({ ...input, lang }))  // #132: server-side replies (loop-guard stop) follow the UI language
}

export async function logDirect(text: string, blocks: BotBlock[]) {
  const chat = await ensureChat()
  await json(`/comfyart/bot/chats/${chat.id}/log`, send({ text, blocks }))
}

export async function stopTurn() {
  const chat = currentChat()
  if (chat?.busy) await json(`/comfyart/bot/chats/${chat.id}/stop`, { method: 'POST' })
}

export async function answerAsk(askId: string, selected: string[], other: string) {
  const chat = currentChat()
  if (chat) await json(`/comfyart/bot/chats/${chat.id}/asks/${askId}/answer`, send({ selected, other_text: other }))
}

export async function updateChat(id: string, patch: Partial<Pick<BotChat, 'title' | 'run_mode' | 'pinned' | 'archived'>>) {
  upsertChat((await json<{ chat: BotChat }>(`/comfyart/bot/chats/${id}`, send(patch, 'PATCH'))).chat)
}

export async function deleteChat(id: string) {
  await json(`/comfyart/bot/chats/${id}`, { method: 'DELETE' })
  chatsAtom.set(chatsAtom.get().filter((c) => c.id !== id))
  if (chatIdAtom.get() === id) await openChat(null)
}

export async function branchFrom(messageId: string) {
  const chat = currentChat()
  if (!chat) return
  const { chat: branch, messages } = await json<{ chat: BotChat; messages: BotMessage[] }>(`/comfyart/bot/chats/${chat.id}/branch`, send({ message_id: messageId }))
  upsertChat(branch)
  chatIdAtom.set(branch.id)
  messagesAtom.set(messages)
}

function patchMessages(chatId: string, messageId: string, fn: (m: BotMessage) => BotMessage) {
  if (chatIdAtom.get() !== chatId) return
  messagesAtom.set(messagesAtom.get().map((m) => (m.id === messageId ? fn(m) : m)))
}

function appendBlock(m: BotMessage, block: BotBlock): BotMessage {
  return { ...m, blocks: [...m.blocks, block] }
}

export function outputsOf(blocks: BotBlock[]): string[] {
  const urls: string[] = []
  for (const b of blocks) {
    if (b.type === 'task') urls.push(...(b.srcs ?? []))
    if (b.type === 'tool_result' && toolName(b.name) === 'wait_generation') urls.push(...(b.text?.match(/\/api\/view\?[^"\s\\]*type=\w+/g) ?? []))
  }
  return [...new Set(urls)]
}

const reducers: Record<string, (e: any) => void> = {
  chat_created: (e) => upsertChat(e.chat),
  chat_updated: (e) => upsertChat(e.chat),
  chat_deleted: (e) => {
    chatsAtom.set(chatsAtom.get().filter((c) => c.id !== e.chat_id))
    if (chatIdAtom.get() === e.chat_id) void openChat(null)
  },
  messages_logged: (e) => {
    if (chatIdAtom.get() === e.chat_id) messagesAtom.set([...messagesAtom.get(), ...e.messages])
  },
  message_queued: (e) => {
    if (chatIdAtom.get() === e.chat_id) messagesAtom.set([...messagesAtom.get(), e.user_message])
  },
  turn_start: (e) => {
    chatsAtom.set(chatsAtom.get().map((c) => (c.id === e.chat_id ? { ...c, busy: true } : c)))
    if (chatIdAtom.get() !== e.chat_id) return
    const rest = messagesAtom.get().filter((m) => m.id !== e.user_message.id)
    messagesAtom.set([...rest, e.user_message, e.assistant_message])
  },
  turn_delta: (e) => patchMessages(e.chat_id, e.message_id, (m) => {
    const last = m.blocks.at(-1)
    return last?.type === 'text' ? { ...m, blocks: [...m.blocks.slice(0, -1), { ...last, text: (last.text ?? '') + e.text }] } : appendBlock(m, { type: 'text', text: e.text })
  }),
  turn_thinking: (e) => patchMessages(e.chat_id, e.message_id, (m) => {
    const last = m.blocks.at(-1)
    return last?.type === 'thinking' ? { ...m, blocks: [...m.blocks.slice(0, -1), { ...last, text: (last.text ?? '') + e.text }] } : appendBlock(m, { type: 'thinking', text: e.text })
  }),
  turn_tool_use: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, { type: 'tool_use', name: e.name, input: e.input, id: e.id })),
  turn_tool_result: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, { type: 'tool_result', name: e.name, text: e.text, status: e.status, id: e.id, duration_ms: e.duration_ms })),
  turn_retry: (e) => patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, e.block)),
  turn_ask: (e) => {
    patchMessages(e.chat_id, e.message_id, (m) => appendBlock(m, { type: 'ask', status: 'pending', ...e }))
    if (chatsAtom.get().some((c) => c.id === e.chat_id)) void notify({ kind: 'suggestion', title: t('bot.agentIsWaitingForYour'), body: e.prompt, chat: e.chat_id })
  },
  turn_ask_resolved: (e) => patchMessages(e.chat_id, e.message_id, (m) => ({
    ...m, blocks: m.blocks.map((b) => (b.type === 'ask' && b.ask_id === e.ask_id ? { ...b, status: e.status, selected: e.selected ?? b.selected, other_text: e.other_text ?? b.other_text } : b)),
  })),
  turn_done: (e) => {
    const chat = chatsAtom.get().find((c) => c.id === e.chat_id)
    chatsAtom.set(chatsAtom.get().map((c) => (c.id === e.chat_id ? { ...c, busy: false, ...(e.title ? { title: e.title } : {}) } : c)))
    if (chatIdAtom.get() === e.chat_id) void openChat(e.chat_id)
    if (!chat || e.status === 'aborted') return
    const message = messagesAtom.get().find((m) => m.id === e.message_id)
    const text = message?.blocks.filter((b) => b.type === 'text').map((b) => b.text).join('').trim()
    void notify({
      kind: 'task',
      title: e.status === 'error' ? t('bot.agentFailed', e.title || chat.title || t('botCommands.chat')) : t('bot.agentDone', e.title || chat.title || t('botCommands.chat')),
      body: e.error || text?.slice(0, 200) || undefined,
      chat: e.chat_id,
      srcs: message ? outputsOf(message.blocks).slice(0, 4) : undefined,
    })
  },
}

function watchDirectTasks() {
  return react('direct tasks', () => {
    const results = resultsAtom.get()
    for (const m of messagesAtom.get()) {
      const pending = m.blocks.filter((b) => b.type === 'task' && !b.srcs && !b.error && b.holder && results[b.holder])
      if (!pending.length) continue
      const blocks = m.blocks.map((b) => (pending.includes(b) ? { ...b, srcs: results[b.holder!].srcs, ...(results[b.holder!].error ? { error: results[b.holder!].error } : {}) } : b))
      void api(`/comfyart/bot/chats/${m.chat_id}/messages/${m.id}`, send({ blocks }, 'PATCH'))
      patchMessages(m.chat_id, m.id, () => ({ ...m, blocks }))
    }
  })
}

export async function refreshBot() {
  await Promise.all([loadProviders(), loadSettings()])
  if (botEnabledAtom.get()) await loadChats()
  else chatsAtom.set([])
}

export function startBot(projectId: string, isStale: () => boolean) {
  project = projectId
  void refreshBot()
  const stops = [
    onComfyEvent('comfyart-bot', (e: { event: string }) => {
      if (!isStale()) reducers[e.event]?.(e)
    }),
    watchDirectTasks(),
    onReconnect(() => {
      if (isStale() || !botEnabledAtom.get()) return
      void loadChats().then(() => openChat(chatIdAtom.get()))
    }),
  ]
  return () => stops.forEach((stop) => stop())
}
