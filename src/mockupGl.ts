import { loadImage } from './adjust'
import { canvasBlob } from './canvasBlob'

export interface Placement { x: number; y: number; scale: number; rotation: number; warp: number }
export interface MockupSources { photo: string; depth: string; mask: string; design: string }

const VERTEX = `#version 300 es
in vec2 pos;
out vec2 uv;
void main() { uv = vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5); gl_Position = vec4(pos, 0.0, 1.0); }`

// follow-surface tuning (#70): sample ±SAMPLE_PX photo pixels on a blurred depth, scale the slope by STRENGTH, cap the shift at MAX_SHIFT (uv)
export const SAMPLE_PX = 24
export const STRENGTH = 3
export const MAX_SHIFT = '0.08'
const DEPTH_LOD = 3.5

const FRAGMENT = `#version 300 es
precision highp float;
in vec2 uv;
out vec4 color;
uniform sampler2D photo, depth, mask, design;
uniform vec2 center, size, texel;
uniform float rotation, warp, median, hasDesign, depthLo, depthHi;
uniform vec2 meanSlope;
float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
// depth normalized to the product's own 0..1 range, read from a blurred mip so 8-bit noise does not tear the design
float D(vec2 p) { return clamp((textureLod(depth, p, ${DEPTH_LOD.toFixed(1)}).r - depthLo) / max(depthHi - depthLo, 1e-3), 0.0, 1.0); }
void main() {
  vec4 p = texture(photo, uv);
  color = p;
  if (hasDesign < 0.5) return;
  vec2 st = texel * ${SAMPLE_PX.toFixed(1)};
  // slope minus the product's mean slope: curvature bends the design, a flat tilted plane (tabletop, floor) does not shift it
  vec2 slope = 0.5 * vec2(D(uv + vec2(st.x, 0.0)) - D(uv - vec2(st.x, 0.0)), D(uv + vec2(0.0, st.y)) - D(uv - vec2(0.0, st.y))) - meanSlope;
  vec2 off = warp * ${STRENGTH.toFixed(1)} * slope;
  float n = length(off);
  if (n > ${MAX_SHIFT}) off *= ${MAX_SHIFT} / n;
  vec2 q = uv - off - center;
  float c = cos(-rotation), s = sin(-rotation);
  vec2 local = vec2(c * q.x - s * q.y, s * q.x + c * q.y) / size + 0.5;
  if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0) return;
  vec4 d = texture(design, local);
  float shade = clamp(lum(p.rgb) / max(median, 0.05), 0.0, 1.6);
  float a = d.a * texture(mask, uv).r;
  color = vec4(mix(p.rgb, d.rgb * shade, a), p.a);
}`

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type)!
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? 'shader failed')
  return s
}

function medianLuma(photo: HTMLImageElement, mask: HTMLImageElement) {
  const side = 128
  const c = document.createElement('canvas')
  c.width = c.height = side
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(photo, 0, 0, side, side)
  const p = ctx.getImageData(0, 0, side, side).data
  ctx.drawImage(mask, 0, 0, side, side)
  const m = ctx.getImageData(0, 0, side, side).data
  const values: number[] = []
  for (let i = 0; i < p.length; i += 4) if (m[i] > 128) values.push((0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]) / 255)
  values.sort((a, b) => a - b)
  return values.length ? values[values.length >> 1] : 0.5
}

/** Depth range (1st..99th percentile) and mean ±SAMPLE_PX slope inside the mask, in normalized depth units. */
export function depthStats(depth: Uint8ClampedArray, mask: Uint8ClampedArray, side: number, step: number) {
  const values: number[] = []
  for (let i = 0; i < depth.length; i += 4) if (mask[i] > 128) values.push(depth[i] / 255)
  if (!values.length) for (let i = 0; i < depth.length; i += 4) values.push(depth[i] / 255)
  values.sort((a, b) => a - b)
  const lo = values[Math.floor(values.length * 0.01)], hi = values[Math.min(values.length - 1, Math.floor(values.length * 0.99))]
  const range = Math.max(hi - lo, 1e-3)
  const at = (x: number, y: number) => depth[(Math.min(side - 1, Math.max(0, y)) * side + Math.min(side - 1, Math.max(0, x))) * 4] / 255
  let sx = 0, sy = 0, n = 0
  for (let y = 0; y < side; y++) for (let x = 0; x < side; x++) {
    if (mask[(y * side + x) * 4] <= 128) continue
    sx += (at(x + step, y) - at(x - step, y)) / 2; sy += (at(x, y + step) - at(x, y - step)) / 2; n++
  }
  return { lo, hi, slope: n ? [sx / n / range, sy / n / range] as [number, number] : [0, 0] as [number, number] }
}

function sampleDepth(depth: HTMLImageElement, mask: HTMLImageElement, photoWidth: number) {
  const side = 256
  const c = document.createElement('canvas')
  c.width = c.height = side
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(depth, 0, 0, side, side)
  const d = ctx.getImageData(0, 0, side, side).data
  ctx.drawImage(mask, 0, 0, side, side)
  const m = ctx.getImageData(0, 0, side, side).data
  return depthStats(d, m, side, Math.max(1, Math.round((SAMPLE_PX * side) / photoWidth)))
}

export class MockupRenderer {
  readonly gl: WebGL2RenderingContext
  private program: WebGLProgram
  private textures: Partial<Record<keyof MockupSources, WebGLTexture>> = {}
  private loaded: Partial<MockupSources> = {}
  private median = 0.5
  private depth = { lo: 0, hi: 1, slope: [0, 0] as [number, number] }
  private photoSize: [number, number] = [1, 1]
  private designAspect = 1

  constructor(readonly canvas: HTMLCanvasElement) {
    const gl = canvas.getContext('webgl2', { preserveDrawingBuffer: true, premultipliedAlpha: false })
    if (!gl) throw new Error('WebGL2 is not available')
    this.gl = gl
    const program = gl.createProgram()!
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX))
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT))
    gl.linkProgram(program)
    this.program = program
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer())
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
    const at = gl.getAttribLocation(program, 'pos')
    gl.enableVertexAttribArray(at)
    gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0)
  }

  async load(sources: MockupSources) {
    const gl = this.gl
    const changed = (Object.keys(sources) as (keyof MockupSources)[]).filter((k) => sources[k] !== this.loaded[k])
    const images: Partial<Record<keyof MockupSources, HTMLImageElement>> = {}
    await Promise.all(changed.filter((k) => sources[k]).map(async (k) => { images[k] = await loadImage(sources[k]) }))
    for (const k of changed) {
      const img = images[k]
      if (!img) { delete this.textures[k]; continue }
      const tex = this.textures[k] ?? gl.createTexture()!
      gl.bindTexture(gl.TEXTURE_2D, tex)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img)
      if (k === 'depth') gl.generateMipmap(gl.TEXTURE_2D)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, k === 'depth' ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
      this.textures[k] = tex
      if (k === 'photo') this.photoSize = [img.naturalWidth, img.naturalHeight]
      if (k === 'design') this.designAspect = img.naturalHeight / img.naturalWidth
    }
    if (images.photo || images.mask) this.median = medianLuma(images.photo ?? await loadImage(sources.photo), images.mask ?? await loadImage(sources.mask))
    if ((images.depth || images.mask || images.photo) && sources.depth && sources.mask)
      this.depth = sampleDepth(images.depth ?? await loadImage(sources.depth), images.mask ?? await loadImage(sources.mask), this.photoSize[0])
    this.loaded = { ...sources }
  }

  draw(p: Placement) {
    const { gl, program } = this
    gl.viewport(0, 0, this.canvas.width, this.canvas.height)
    gl.useProgram(program)
    const names = ['photo', 'depth', 'mask', 'design'] as const
    names.forEach((n, i) => {
      gl.activeTexture(gl.TEXTURE0 + i)
      gl.bindTexture(gl.TEXTURE_2D, this.textures[n] ?? null)
      gl.uniform1i(gl.getUniformLocation(program, n), i)
    })
    const [pw, ph] = this.photoSize
    gl.uniform2f(gl.getUniformLocation(program, 'center'), p.x, p.y)
    gl.uniform2f(gl.getUniformLocation(program, 'size'), p.scale, (p.scale * this.designAspect * pw) / ph)
    gl.uniform2f(gl.getUniformLocation(program, 'texel'), 1 / pw, 1 / ph)
    gl.uniform1f(gl.getUniformLocation(program, 'rotation'), p.rotation)
    gl.uniform1f(gl.getUniformLocation(program, 'warp'), p.warp)
    gl.uniform1f(gl.getUniformLocation(program, 'median'), this.median)
    gl.uniform1f(gl.getUniformLocation(program, 'depthLo'), this.depth.lo)
    gl.uniform1f(gl.getUniformLocation(program, 'depthHi'), this.depth.hi)
    gl.uniform2f(gl.getUniformLocation(program, 'meanSlope'), this.depth.slope[0], this.depth.slope[1])
    gl.uniform1f(gl.getUniformLocation(program, 'hasDesign'), this.textures.design ? 1 : 0)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
  }

  get size() { return this.photoSize }
}

export async function bakeMockup(sources: MockupSources, placement: Placement): Promise<Blob> {
  const canvas = document.createElement('canvas')
  const r = new MockupRenderer(canvas)
  await r.load(sources)
  ;[canvas.width, canvas.height] = r.size
  r.draw(placement)
  return canvasBlob(canvas)
}
