import { useEffect, useRef, useState } from 'react'
import type * as T from 'three'

import { anglePrompt } from '../workflows'
import { t } from '../i18n'

export interface Angle { h: number; v: number; z: number }

const DEG = Math.PI / 180
const FOV = 35
const SHOT_DISTANCE = 6
const SPHERE = 1.5
const NEAR = 0.8
const FAR = 1.1
const RING_LAT = -40 * DEG
const V_MIN = -30
const V_MAX = 60
const PICK_PX = 14
const INSET = 0.38
const YAW = 0x00d4ff
const PITCH = 0xff66ff
const DIST = 0xffcc00

type Handle = 'yaw' | 'pitch' | 'distance'
export type AngleView = 'camera' | 'object'

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x))
const wrap = (d: number) => ((d % 360) + 360) % 360
const fit = (a: Angle): Angle => ({ h: Math.round(wrap(a.h)) % 360, v: Math.round(clamp(a.v, V_MIN, V_MAX)), z: Math.round(clamp(a.z, 0, 10) * 10) / 10 })
const handleDistance = (z: number) => FAR - ((FAR - NEAR) * z) / 10

function faceTexture(THREE: typeof T, label: string) {
  const c = document.createElement('canvas')
  c.width = c.height = 256
  const g = c.getContext('2d')!
  g.fillStyle = '#2a2d36'
  g.fillRect(0, 0, 256, 256)
  g.strokeStyle = '#3d4150'
  for (let i = 0; i <= 256; i += 32) {
    g.beginPath()
    g.moveTo(i, 0)
    g.lineTo(i, 256)
    g.moveTo(0, i)
    g.lineTo(256, i)
    g.stroke()
  }
  g.fillStyle = '#aeb4c2'
  g.font = 'bold 40px sans-serif'
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText(label, 128, 128)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return new THREE.MeshBasicMaterial({ map: tex })
}

function handleMesh(THREE: typeof T, color: number, type: Handle) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.08, 24, 24), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.7, roughness: 0.3 }))
  mesh.userData.handle = type
  mesh.add(new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25, depthWrite: false, blending: THREE.AdditiveBlending })))
  return mesh
}

function buildScene(THREE: typeof T, el: HTMLDivElement) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.autoClear = false
  el.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.add(new THREE.AmbientLight(0xffffff, 1.2))
  const sun = new THREE.DirectionalLight(0xffffff, 1.5)
  sun.position.set(3, 5, 4)
  scene.add(sun)

  const front = new THREE.MeshBasicMaterial({ color: 0xd8dbe2 })
  const cube = new THREE.BoxGeometry(1, 1, 1)
  const faces = [t('modePanel.right'), t('modePanel.left'), t('modePanel.faceTop'), t('modePanel.faceBottom'), '', t('modePanel.back')].map((label, i) => (i === 4 ? front : faceTexture(THREE, label)))
  scene.add(new THREE.Mesh(cube, faces))
  scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(cube), new THREE.LineBasicMaterial({ color: 0x1a1a1a, transparent: true, opacity: 0.6 })))

  const gizmos = new THREE.Group()
  scene.add(gizmos)
  gizmos.add(new THREE.Mesh(new THREE.SphereGeometry(SPHERE, 12, 8), new THREE.MeshBasicMaterial({ color: 0x8a93a6, wireframe: true, transparent: true, opacity: 0.14, depthWrite: false })))

  const ringR = SPHERE * Math.cos(RING_LAT)
  const ringY = SPHERE * Math.sin(RING_LAT)
  const ring = new THREE.Mesh(new THREE.TorusGeometry(ringR, 0.025, 16, 96), new THREE.MeshBasicMaterial({ color: YAW, transparent: true, opacity: 0.55 }))
  ring.rotation.x = Math.PI / 2
  ring.position.y = ringY
  gizmos.add(ring)

  const yawGroup = new THREE.Group()
  gizmos.add(yawGroup)
  const arc: T.Vector3[] = []
  for (let d = V_MIN; d <= V_MAX; d += 5) arc.push(new THREE.Vector3(0, SPHERE * Math.sin(d * DEG), SPHERE * Math.cos(d * DEG)))
  yawGroup.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(arc), 32, 0.025, 8, false), new THREE.MeshBasicMaterial({ color: PITCH, transparent: true, opacity: 0.55 })))
  const lineGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, 1], 3))
  yawGroup.add(new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: DIST, transparent: true, opacity: 0.55 })))

  const handles = { yaw: handleMesh(THREE, YAW, 'yaw'), pitch: handleMesh(THREE, PITCH, 'pitch'), distance: handleMesh(THREE, DIST, 'distance') }
  gizmos.add(handles.yaw)
  yawGroup.add(handles.pitch, handles.distance)

  const markerMat = new THREE.MeshStandardMaterial({ color: DIST, emissive: DIST, emissiveIntensity: 0.45, roughness: 0.4 })
  const marker = new THREE.Group()
  marker.add(new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.12), markerMat))
  const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.048, 0.08, 16), markerMat)
  lens.rotation.x = Math.PI / 2
  lens.position.z = -0.1
  marker.add(lens)
  gizmos.add(marker)

  const overview = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100)
  const shot = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100)

  const orbit = (h: number, v: number, d: number) => new THREE.Vector3(d * Math.cos(v * DEG) * Math.sin(h * DEG), d * Math.sin(v * DEG), d * Math.cos(v * DEG) * Math.cos(h * DEG))

  const apply = (a: Angle) => {
    const d = handleDistance(a.z)
    yawGroup.rotation.y = a.h * DEG
    handles.yaw.position.set(ringR * Math.sin(a.h * DEG), ringY, ringR * Math.cos(a.h * DEG))
    handles.pitch.position.set(0, SPHERE * Math.sin(a.v * DEG), SPHERE * Math.cos(a.v * DEG))
    handles.distance.position.set(0, d * Math.sin(a.v * DEG), d * Math.cos(a.v * DEG))
    const pos = lineGeo.attributes.position as T.BufferAttribute
    pos.setXYZ(1, 0, d * Math.sin(a.v * DEG), d * Math.cos(a.v * DEG))
    pos.needsUpdate = true
    marker.position.copy(orbit(a.h, a.v, d))
    marker.lookAt(0, 0, 0)
    marker.rotateY(Math.PI)
    shot.position.copy(orbit(a.h, a.v, SHOT_DISTANCE))
    shot.lookAt(0, 0, 0)
    shot.zoom = 1 + (0.875 * a.z) / 10
    shot.updateProjectionMatrix()
  }

  let view: AngleView = 'camera'
  let inset = true

  const render = () => {
    const w = el.clientWidth
    const h = el.clientHeight
    if (!w || !h) return
    renderer.setSize(w, h)
    renderer.setScissorTest(false)
    renderer.clear()
    if (view === 'object') {
      gizmos.visible = false
      shot.aspect = w / h
      shot.updateProjectionMatrix()
      renderer.render(scene, shot)
      return
    }
    overview.aspect = w / h
    const dist = (SPHERE * 1.2) / (Math.tan((FOV / 2) * DEG) * Math.min(1, w / h))
    overview.position.set(2.4, 1.4, 4.2).normalize().multiplyScalar(dist)
    overview.lookAt(0, 0, 0)
    overview.updateProjectionMatrix()
    gizmos.visible = true
    renderer.render(scene, overview)
    if (!inset) return
    shot.aspect = 1
    shot.updateProjectionMatrix()
    const side = Math.round(Math.min(w, h) * INSET)
    gizmos.visible = false
    renderer.setScissorTest(true)
    renderer.setViewport(w - side - 6, 6, side, side)
    renderer.setScissor(w - side - 6, 6, side, side)
    renderer.setClearColor(0x8a93a6, 1)
    renderer.clear()
    renderer.setViewport(w - side - 5, 7, side - 2, side - 2)
    renderer.setScissor(w - side - 5, 7, side - 2, side - 2)
    renderer.setClearColor(0x282828, 1)
    renderer.clear()
    renderer.render(scene, shot)
    renderer.setClearColor(0x000000, 0)
    renderer.setViewport(0, 0, w, h)
    renderer.setScissorTest(false)
  }

  let token = 0
  const setImage = async (src: string | null) => {
    const mine = ++token
    front.map?.dispose()
    front.map = null
    front.color.set(0xd8dbe2)
    if (src) {
      const tex = await new THREE.TextureLoader().loadAsync(src).catch(() => null)
      if (!tex || mine !== token) return tex?.dispose()
      tex.colorSpace = THREE.SRGBColorSpace
      const { width = 1, height = 1 } = tex.image as { width?: number; height?: number }
      const r = width / height
      tex.repeat.set(r > 1 ? 1 / r : 1, r < 1 ? r : 1)
      tex.offset.set((1 - tex.repeat.x) / 2, (1 - tex.repeat.y) / 2)
      front.map = tex
      front.color.set(0xffffff)
    }
    front.needsUpdate = true
    render()
  }

  const ray = new THREE.Raycaster()
  const ndc = new THREE.Vector2()
  const hit = new THREE.Vector3()
  const aim = (e: { clientX: number; clientY: number }) => {
    const r = renderer.domElement.getBoundingClientRect()
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
    ray.setFromCamera(ndc, overview)
    return r
  }
  const pick = (e: { clientX: number; clientY: number }): Handle | null => {
    if (view === 'object') return null
    gizmos.visible = true
    const r = aim(e)
    const list = Object.values(handles)
    const direct = ray.intersectObjects(list, false)[0]
    if (direct) return direct.object.userData.handle
    let best: Handle | null = null
    let bestPx = PICK_PX
    for (const m of list) {
      const p = m.getWorldPosition(new THREE.Vector3()).project(overview)
      const px = Math.hypot(((p.x + 1) / 2) * r.width - (e.clientX - r.left), ((1 - p.y) / 2) * r.height - (e.clientY - r.top))
      if (px < bestPx) [best, bestPx] = [m.userData.handle, px]
    }
    return best
  }
  const drag = (type: Handle, e: { clientX: number; clientY: number }, a: Angle): Angle | null => {
    aim(e)
    const plane = type === 'yaw'
      ? new THREE.Plane(new THREE.Vector3(0, 1, 0), -ringY)
      : new THREE.Plane(new THREE.Vector3(-Math.cos(a.h * DEG), 0, Math.sin(a.h * DEG)), 0)
    if (!ray.ray.intersectPlane(plane, hit)) return null
    if (type === 'yaw') return { ...a, h: Math.atan2(hit.x, hit.z) / DEG }
    const along = hit.x * Math.sin(a.h * DEG) + hit.z * Math.cos(a.h * DEG)
    if (type === 'pitch') return { ...a, v: Math.atan2(hit.y, along) / DEG }
    const proj = along * Math.cos(a.v * DEG) + hit.y * Math.sin(a.v * DEG)
    return { ...a, z: ((FAR - proj) * 10) / (FAR - NEAR) }
  }
  const hover = (type: Handle | null) => {
    for (const [k, m] of Object.entries(handles)) {
      m.scale.setScalar(k === type ? 1.35 : 1)
      ;((m.children[0] as T.Mesh).material as T.MeshBasicMaterial).opacity = k === type ? 0.6 : 0.25
    }
    render()
  }
  const dispose = () => {
    token++
    front.map?.dispose()
    scene.traverse((o) => {
      const m = o as T.Mesh
      m.geometry?.dispose()
      for (const mat of [m.material ?? []].flat()) {
        ;(mat as T.MeshBasicMaterial).map?.dispose()
        mat.dispose()
      }
    })
    renderer.dispose()
    renderer.domElement.remove()
  }
  const setView = (v: AngleView, showInset: boolean) => {
    view = v
    inset = showInset
    render()
  }
  return { canvas: renderer.domElement, apply, render, setImage, setView, pick, drag, hover, dispose }
}

type Scene = ReturnType<typeof buildScene>

export function AnglePreview({ value, src, onChange }: { value: Angle; src: string | null; onChange: (a: Angle) => void }) {
  const host = useRef<HTMLDivElement>(null)
  const scene = useRef<Scene | null>(null)
  const latest = useRef({ value, src, onChange })
  latest.current = { value, src, onChange }
  const [view, setView] = useState<AngleView>('camera')
  const [inset, setInset] = useState(true)
  const viewState = useRef({ view, inset })
  viewState.current = { view, inset }

  useEffect(() => {
    let alive = true
    let cleanup = () => {}
    void import('three').then((THREE) => {
      const el = host.current
      if (!alive || !el) return
      const s = buildScene(THREE, el)
      scene.current = s
      s.apply(latest.current.value)
      s.setView(viewState.current.view, viewState.current.inset)
      void s.setImage(latest.current.src)
      const resize = new ResizeObserver(() => s.render())
      resize.observe(el)
      let dragging: Handle | 'free' | null = null
      let last = { x: 0, y: 0 }
      const set = (a: Angle | null) => a && latest.current.onChange(fit(a))
      const down = (e: PointerEvent) => {
        dragging = s.pick(e) ?? 'free'
        last = { x: e.clientX, y: e.clientY }
        s.canvas.setPointerCapture(e.pointerId)
        s.canvas.style.cursor = 'grabbing'
      }
      const move = (e: PointerEvent) => {
        const a = latest.current.value
        if (dragging === 'free') set({ ...a, h: a.h - (e.clientX - last.x) * 0.5, v: a.v + (e.clientY - last.y) * 0.5 })
        else if (dragging) set(s.drag(dragging, e, a))
        else {
          const over = s.pick(e)
          s.hover(over)
          s.canvas.style.cursor = over ? 'grab' : ''
        }
        last = { x: e.clientX, y: e.clientY }
      }
      const up = (e: PointerEvent) => {
        dragging = null
        s.canvas.releasePointerCapture(e.pointerId)
        s.canvas.style.cursor = ''
      }
      const wheel = (e: WheelEvent) => {
        e.preventDefault()
        set({ ...latest.current.value, z: latest.current.value.z - e.deltaY * 0.01 })
      }
      s.canvas.addEventListener('pointerdown', down)
      s.canvas.addEventListener('pointermove', move)
      s.canvas.addEventListener('pointerup', up)
      s.canvas.addEventListener('pointercancel', up)
      s.canvas.addEventListener('wheel', wheel, { passive: false })
      cleanup = () => {
        resize.disconnect()
        s.dispose()
        scene.current = null
      }
    })
    return () => {
      alive = false
      cleanup()
    }
  }, [])

  useEffect(() => {
    scene.current?.apply(value)
    scene.current?.render()
  }, [value.h, value.v, value.z])

  useEffect(() => {
    void scene.current?.setImage(src)
  }, [src])

  useEffect(() => {
    scene.current?.setView(view, inset)
  }, [view, inset])

  return (
    <div className="ca-angle">
      <div className="ca-angle__bar">
        <button type="button" className="ca-panel__chip" data-on={view === 'camera' || undefined} title={t('modePanel.cameraViewTooltip')} aria-pressed={view === 'camera'} onClick={() => setView('camera')}>{t('modePanel.cameraView')}</button>
        <button type="button" className="ca-panel__chip" data-on={view === 'object' || undefined} title={t('modePanel.objectViewTooltip')} aria-pressed={view === 'object'} onClick={() => setView('object')}>{t('modePanel.objectView')}</button>
        <button type="button" className="ca-panel__chip ca-angle__inset" data-on={(view === 'camera' && inset) || undefined} disabled={view === 'object'} title={inset ? t('modePanel.hideShotPreview') : t('modePanel.showShotPreview')} aria-pressed={view === 'camera' && inset} onClick={() => setInset(!inset)}>{t('modePanel.shotPreview')}</button>
      </div>
      <div ref={host} className="ca-angle__view" />
      <div className="ca-angle__prompt" title={anglePrompt(value.h, value.v, value.z)}>{anglePrompt(value.h, value.v, value.z).replace(/^<\w+> /, '')}</div>
    </div>
  )
}
