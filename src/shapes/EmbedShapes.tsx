import { useEffect, useRef, useState } from 'react'
import { BaseBoxShapeUtil, HTMLContainer, T, useEditor, useValue, type RecordProps, type TLShape, type TLShapeId } from 'tldraw'
import { Icons } from '../ui/icons'
import { t } from '../i18n'
import { canvasBlob } from '../canvasBlob'

export const LOTTIE = 'ca-lottie'
export const MODEL = 'ca-model'
export const HTML = 'ca-html'
export const AUDIO = 'ca-audio'
export const AUDIO_SIZE: [number, number] = [680, 168]

declare module 'tldraw' {
  export interface TLGlobalShapePropsMap {
    [LOTTIE]: { w: number; h: number; src: string; name: string }
    [MODEL]: { w: number; h: number; src: string; name: string; ext: string; spin: boolean; bg: string }
    [HTML]: { w: number; h: number; html: string; name: string }
    [AUDIO]: { w: number; h: number; src: string; name: string }
  }
}

export type LottieShape = TLShape<typeof LOTTIE>
export type ModelShape = TLShape<typeof MODEL>
export type HtmlShape = TLShape<typeof HTML>
export type AudioShape = TLShape<typeof AUDIO>

function boxPath(shape: TLShape) {
  const { w, h } = shape.props as { w: number; h: number }
  const path = new Path2D()
  path.rect(0, 0, w, h)
  return path
}

export const snapshots = new Map<TLShapeId, () => Promise<Blob>>()

function useEditing(id: TLShapeId) {
  const editor = useEditor()
  return useValue('editing embed', () => editor.getEditingShapeId() === id, [editor, id])
}

function LottieView({ shape }: { shape: LottieShape }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let anim: { destroy: () => void } | null = null
    let alive = true
    void import('lottie-web').then(({ default: lottie }) => {
      if (!alive || !box.current) return
      anim = lottie.loadAnimation({ container: box.current, renderer: 'svg', loop: true, autoplay: true, path: shape.props.src })
    })
    return () => {
      alive = false
      anim?.destroy()
    }
  }, [shape.props.src])
  return <div ref={box} className="ca-embed__lottie" />
}

function ModelView({ shape }: { shape: ModelShape }) {
  const host = useRef<HTMLDivElement>(null)
  const editing = useEditing(shape.id)
  const state = useRef<{ controls?: { enabled: boolean; autoRotate: boolean } }>({})
  const { src, ext, spin, bg } = shape.props

  useEffect(() => {
    let alive = true
    let cleanup = () => {}
    void (async () => {
      const THREE = await import('three')
      const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js')
      const loaders = {
        glb: async () => (await new (await import('three/examples/jsm/loaders/GLTFLoader.js')).GLTFLoader().loadAsync(src)).scene,
        gltf: async () => (await new (await import('three/examples/jsm/loaders/GLTFLoader.js')).GLTFLoader().loadAsync(src)).scene,
        obj: async () => new (await import('three/examples/jsm/loaders/OBJLoader.js')).OBJLoader().loadAsync(src),
        fbx: async () => new (await import('three/examples/jsm/loaders/FBXLoader.js')).FBXLoader().loadAsync(src),
        stl: async () => new THREE.Mesh(await new (await import('three/examples/jsm/loaders/STLLoader.js')).STLLoader().loadAsync(src), new THREE.MeshStandardMaterial({ color: 0xbbbbbb })),
        ply: async () => {
          const geo = await new (await import('three/examples/jsm/loaders/PLYLoader.js')).PLYLoader().loadAsync(src)
          geo.computeVertexNormals()
          return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: geo.hasAttribute('color'), color: geo.hasAttribute('color') ? 0xffffff : 0xbbbbbb }))
        },
      } as Record<string, () => Promise<import('three').Object3D>>
      const object = await (loaders[ext] ?? loaders.glb)()
      if (!alive || !host.current) return
      const el = host.current
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true })
      renderer.setPixelRatio(window.devicePixelRatio)
      renderer.setSize(el.clientWidth, el.clientHeight)
      renderer.outputColorSpace = THREE.SRGBColorSpace
      el.appendChild(renderer.domElement)
      const scene = new THREE.Scene()
      scene.add(new THREE.HemisphereLight(0xffffff, 0x666666, 2.2))
      const sun = new THREE.DirectionalLight(0xffffff, 2)
      sun.position.set(3, 5, 4)
      scene.add(sun)
      const box = new THREE.Box3().setFromObject(object)
      const size = box.getSize(new THREE.Vector3()).length() || 1
      object.position.sub(box.getCenter(new THREE.Vector3()))
      scene.add(object)
      const camera = new THREE.PerspectiveCamera(35, el.clientWidth / el.clientHeight, size / 100, size * 100)
      camera.position.set(size * 0.9, size * 0.6, size * 1.2)
      const controls = new OrbitControls(camera, renderer.domElement)
      controls.enableDamping = true
      state.current.controls = controls
      const resize = new ResizeObserver(() => {
        renderer.setSize(el.clientWidth, el.clientHeight)
        camera.aspect = el.clientWidth / el.clientHeight
        camera.updateProjectionMatrix()
      })
      resize.observe(el)
      renderer.setAnimationLoop(() => {
        controls.update()
        renderer.render(scene, camera)
      })
      snapshots.set(shape.id, () => canvasBlob(renderer.domElement))
      cleanup = () => {
        snapshots.delete(shape.id)
        resize.disconnect()
        renderer.setAnimationLoop(null)
        controls.dispose()
        renderer.dispose()
        renderer.domElement.remove()
      }
    })()
    return () => {
      alive = false
      cleanup()
    }
  }, [src, ext, shape.id])

  useEffect(() => {
    const c = state.current.controls
    if (!c) return
    c.enabled = editing
    c.autoRotate = spin
  })

  return <div ref={host} className="ca-embed__model" style={{ background: bg || undefined }} />
}

export class LottieShapeUtil extends BaseBoxShapeUtil<LottieShape> {
  static override type = LOTTIE
  static override props: RecordProps<LottieShape> = { w: T.number, h: T.number, src: T.string, name: T.string }
  override getDefaultProps(): LottieShape['props'] { return { w: 400, h: 400, src: '', name: 'Lottie' } }
  override component(shape: LottieShape) {
    return <HTMLContainer className="ca-embed"><LottieView shape={shape} /></HTMLContainer>
  }
  override getIndicatorPath(shape: TLShape) { return boxPath(shape) }
}

export class ModelShapeUtil extends BaseBoxShapeUtil<ModelShape> {
  static override type = MODEL
  static override props: RecordProps<ModelShape> = { w: T.number, h: T.number, src: T.string, name: T.string, ext: T.string, spin: T.boolean, bg: T.string }
  override getDefaultProps(): ModelShape['props'] { return { w: 480, h: 480, src: '', name: t('embedShapes.3dModel'), ext: 'glb', spin: true, bg: '' } }
  override canEdit() { return true }
  override component(shape: ModelShape) {
    return <HTMLContainer className="ca-embed" style={{ pointerEvents: this.editor.getEditingShapeId() === shape.id ? 'all' : 'none' }}><ModelView shape={shape} /></HTMLContainer>
  }
  override getIndicatorPath(shape: TLShape) { return boxPath(shape) }
}

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

function AudioView({ shape }: { shape: AudioShape }) {
  const audio = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const stop = (e: React.PointerEvent) => e.stopPropagation()
  const toggle = () => {
    const a = audio.current
    if (a) void (a.paused ? a.play() : a.pause())
  }
  return (
    <div className="ca-audio">
      <audio
        ref={audio}
        src={shape.props.src}
        preload="metadata"
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
      <button type="button" className="ca-audio__play" onPointerDown={stop} onClick={toggle}>{playing ? Icons.pause : Icons.play}</button>
      <div className="ca-audio__body">
        <div className="ca-audio__name">{shape.props.name}</div>
        <input
          className="ca-audio__seek"
          type="range"
          min={0}
          max={duration || 1}
          step={0.01}
          value={time}
          onPointerDown={stop}
          onChange={(e) => { if (audio.current) audio.current.currentTime = Number(e.target.value) }}
        />
        <div className="ca-audio__time">{clock(time)} / {clock(Math.round(duration))}</div>
      </div>
    </div>
  )
}

export class AudioShapeUtil extends BaseBoxShapeUtil<AudioShape> {
  static override type = AUDIO
  static override props: RecordProps<AudioShape> = { w: T.number, h: T.number, src: T.string, name: T.string }
  override getDefaultProps(): AudioShape['props'] { return { w: AUDIO_SIZE[0], h: AUDIO_SIZE[1], src: '', name: t('common.audio') } }
  override component(shape: AudioShape) {
    return <HTMLContainer className="ca-embed"><AudioView shape={shape} /></HTMLContainer>
  }
  override getIndicatorPath(shape: TLShape) { return boxPath(shape) }
}

export class HtmlShapeUtil extends BaseBoxShapeUtil<HtmlShape> {
  static override type = HTML
  static override props: RecordProps<HtmlShape> = { w: T.number, h: T.number, html: T.string, name: T.string }
  override getDefaultProps(): HtmlShape['props'] { return { w: 800, h: 600, html: '', name: t('botCommands.webPage') } }
  override canEdit() { return true }
  override component(shape: HtmlShape) {
    const editing = this.editor.getEditingShapeId() === shape.id
    return (
      <HTMLContainer className="ca-embed" style={{ pointerEvents: editing ? 'all' : 'none' }}>
        <iframe className="ca-embed__html" title={shape.props.name} sandbox="allow-scripts" srcDoc={shape.props.html} />
      </HTMLContainer>
    )
  }
  override getIndicatorPath(shape: TLShape) { return boxPath(shape) }
}
