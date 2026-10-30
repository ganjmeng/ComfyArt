// #410: every process-rail kind, live + done, for the agent-loop audit harness. $0 mocks, no network.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
setLang(q.get('lang') === 'en' ? 'en' : 'zh')
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const use = (id: string, name: string, input: any = {}) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text = '{}', status = 'success') => (
  { type: 'tool_result', id, name, status, text }
)

type Msg = { id: string; role: string; status: string; blocks: any[] }

const scenes: Record<string, Msg> = {
  // No-tool turn: thought → reply only (issue comment #3)
  'no-tool-live': {
    id: 'nt-live', role: 'assistant', status: 'streaming',
    blocks: [{ type: 'thinking', text: 'Plain answer, no tools.' }],
  },
  'no-tool-done': {
    id: 'nt-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Plain answer, no tools.' },
      { type: 'text', text: 'Here is a short reply.' },
    ],
  },
  // Thought live / done on a multi-step rail
  'thought-live': {
    id: 'th-live', role: 'assistant', status: 'streaming',
    blocks: [{ type: 'thinking', text: 'Planning the next step.' }],
  },
  'thought-done': {
    id: 'th-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Planning the next step.' },
      { type: 'text', text: 'Ready.' },
    ],
  },
  // Skill load
  'skill-live': {
    id: 'sk-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Load skill.' },
      use('s1', 'mcp__comfyart__skill', { action: 'load', name: 'poster' }),
    ],
  },
  'skill-done': {
    id: 'sk-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Load skill.' },
      use('s1', 'mcp__comfyart__skill', { action: 'load', name: 'poster' }),
      res('s1', 'mcp__comfyart__skill', '{"name":"poster"}'),
      { type: 'text', text: 'Skill on.' },
    ],
  },
  // Skill file read
  'skill-file-live': {
    id: 'sf-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Read skill file.' },
      use('sf1', 'mcp__comfyart__skill', { action: 'read', name: 'poster', path: 'SKILL.md' }),
    ],
  },
  'skill-file-done': {
    id: 'sf-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Read skill file.' },
      use('sf1', 'mcp__comfyart__skill', { action: 'read', name: 'poster', path: 'SKILL.md' }),
      res('sf1', 'mcp__comfyart__skill', '{"content":"# poster"}'),
      { type: 'text', text: 'Read.' },
    ],
  },
  // Search live + done with page count
  'search-live': {
    id: 'se-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Search.' },
      use('w1', 'WebSearch', { query: 'fuji', num_results: 3 }),
    ],
  },
  'search-done': {
    id: 'se-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Search.' },
      use('w1', 'WebSearch', { query: 'fuji', num_results: 3 }),
      res('w1', 'WebSearch', '{"results":[{"url":"https://www.google.com/search?q=fuji"},{"url":"https://en.wikipedia.org/wiki/Fuji"},{"url":"https://example.com/fuji"}]}'),
      { type: 'text', text: 'Found.' },
    ],
  },
  // Image generate live / done (model name row)
  'image-live': {
    id: 'im-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Draw.' },
      use('g1', 'mcp__comfyart__generate_image', { model: 'GPT Image Flare', prompt: 'apple', ratio: '1:1' }),
    ],
  },
  'image-done': {
    id: 'im-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Draw.' },
      use('g1', 'mcp__comfyart__generate_image', { model: 'GPT Image Flare', prompt: 'apple', ratio: '1:1' }),
      res('g1', 'mcp__comfyart__generate_image', '{"prompt_id":"p1"}'),
      { type: 'text', text: 'Done.' },
    ],
  },
  // Video generate live
  'video-live': {
    id: 'vi-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Animate.' },
      use('v1', 'mcp__comfyart__generate_video', { model: 'Seedance Lite', prompt: 'wave' }),
    ],
  },
  'video-done': {
    id: 'vi-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Animate.' },
      use('v1', 'mcp__comfyart__generate_video', { model: 'Seedance Lite', prompt: 'wave' }),
      res('v1', 'mcp__comfyart__generate_video', '{"prompt_id":"p2"}'),
      { type: 'text', text: 'Clip ready.' },
    ],
  },
  // Memory updating (live) + memory_updated done with retrieved
  'memory-live': {
    id: 'me-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Remember.' },
      use('m1', 'mcp__comfyart__memory', { action: 'add', text: 'Brand: Klein blue' }),
    ],
  },
  'memory-done': {
    id: 'me-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Remember.' },
      use('m1', 'mcp__comfyart__memory', { action: 'add', text: 'Brand: Klein blue' }),
      res('m1', 'mcp__comfyart__memory', '{"ids":["mem1"]}'),
      { type: 'memory_updated', memory_ids: ['mem1'], texts: ['Brand: Klein blue'], tool_id: 'm1', tool_ids: ['m1'], updated_ids: ['mem1'], count: 1 },
      { type: 'thinking', text: 'Now reply with the fact.' },
      { type: 'text', text: 'Saved Klein blue.' },
    ],
  },
  // Code family
  'code-live': {
    id: 'co-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Write code.' },
      use('c0', 'writing_code', {}),
      use('c1', 'Write', { path: 'a.tsx' }),
    ],
  },
  'code-done': {
    id: 'co-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Write code.' },
      use('c0', 'writing_code', {}),
      res('c0', 'writing_code', '{}'),
      use('c1', 'Write', { path: 'a.tsx' }),
      res('c1', 'Write', '{}'),
      use('c2', 'Edit', { path: 'a.tsx' }),
      res('c2', 'Edit', '{}'),
      use('c3', 'validate_workflow', {}),
      res('c3', 'validate_workflow', '{}'),
      use('c4', 'preview_artifact', {}),
      res('c4', 'preview_artifact', '{}'),
      { type: 'text', text: 'Code ready.' },
    ],
  },
  // Generic canvas tool on the rail
  'tool-live': {
    id: 'to-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Inspect canvas.' },
      use('t1', 'mcp__comfyart__get_canvas', {}),
    ],
  },
  'tool-done': {
    id: 'to-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'Inspect canvas.' },
      use('t1', 'mcp__comfyart__get_canvas', {}),
      res('t1', 'mcp__comfyart__get_canvas', '{"shapes":[]}'),
      { type: 'text', text: 'Empty canvas.' },
    ],
  },
  // Outputting… after a finished thought while reply streams
  'outputting-live': {
    id: 'out-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'Compose reply.' },
      { type: 'text', text: 'Partial…' },
    ],
  },
  // Full reference-like chain: thought → skill → thought → search (live)
  'chain-live': {
    id: 'ch-live', role: 'assistant', status: 'streaming',
    blocks: [
      { type: 'thinking', text: 'First plan.' },
      use('s1', 'mcp__comfyart__skill', { action: 'load', name: 'poster' }),
      res('s1', 'mcp__comfyart__skill', '{"name":"poster"}'),
      { type: 'thinking', text: 'Need web facts.' },
      use('w1', 'WebSearch', { query: 'poster trends', num_results: 2 }),
    ],
  },
  'chain-done': {
    id: 'ch-done', role: 'assistant', status: 'done',
    blocks: [
      { type: 'thinking', text: 'First plan.' },
      use('s1', 'mcp__comfyart__skill', { action: 'load', name: 'poster' }),
      res('s1', 'mcp__comfyart__skill', '{"name":"poster"}'),
      { type: 'thinking', text: 'Need web facts.' },
      use('w1', 'WebSearch', { query: 'poster trends', num_results: 2 }),
      res('w1', 'WebSearch', '{"results":[{"url":"https://example.com/a"},{"url":"https://example.com/b"}]}'),
      use('g1', 'mcp__comfyart__generate_image', { model: 'GPT Image Flare', prompt: 'poster' }),
      res('g1', 'mcp__comfyart__generate_image', '{"prompt_id":"p1"}'),
      { type: 'text', text: 'Poster ready.' },
    ],
  },
}

const scene = q.get('scene') || 'chain-done'
const m = scenes[scene] || scenes['chain-done']

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 392, padding: 16 }}>
    <div className="ca-chat">
      <div className="ca-chat__bot" data-scene={scene} id="scene">
        <AssistantBlocks editor={null as any} m={m as any} />
      </div>
    </div>
  </div>,
)
;(globalThis as any).__ready = true
;(globalThis as any).__scenes = Object.keys(scenes)
