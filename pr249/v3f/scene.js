import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';

const DEG = Math.PI / 180;
const FOV = 35, SHOT_DISTANCE = 6, SPHERE = 1.5, NEAR = 0.8, FAR = 1.1;
const RING_LAT = -40 * DEG, V_MIN = -30, V_MAX = 60, INSET = 0.38;

export const COLORS_MAIN = {
  yaw: 0x00d4ff, pitch: 0xff66ff, dist: 0xffcc00,
  faceBg: '#2a2d36', faceGrid: '#3d4150', faceText: '#aeb4c2',
  front: 0xd8dbe2, edge: 0x1a1a1a, wire: 0x8a93a6,
  insetBorder: 0x8a93a6, insetBg: 0x282828,
};
// Refined cohesive palette for light gray-neutral UI (geometry unchanged)
export const COLORS_V3D = {
  yaw: 0x5B8FB8, pitch: 0xB87A9E, dist: 0xC4A35A,
  faceBg: '#2F333C', faceGrid: '#454B58', faceText: '#C5CAD6',
  front: 0xE2E5EA, edge: 0x22262E, wire: 0x8E96A6,
  insetBorder: 0x8E96A6, insetBg: 0x2A2A2A,
};

function faceTexture(label, C) {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = C.faceBg; g.fillRect(0, 0, 256, 256);
  g.strokeStyle = C.faceGrid;
  for (let i = 0; i <= 256; i += 32) {
    g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 256); g.moveTo(0, i); g.lineTo(256, i); g.stroke();
  }
  g.fillStyle = C.faceText; g.font = 'bold 40px sans-serif';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(label, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshBasicMaterial({ map: tex });
}

function coffeeFront(C) {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#C9A882'; g.fillRect(0, 0, 256, 128);
  g.fillStyle = '#6B4423'; g.fillRect(0, 128, 256, 128);
  g.fillStyle = '#4A8B4A'; g.beginPath(); g.arc(70, 70, 28, 0, Math.PI * 2); g.fill();
  g.fillStyle = '#F2EDE6';
  g.beginPath(); g.roundRect(90, 150, 76, 70, 14); g.fill();
  g.fillStyle = '#E8E0D5';
  g.beginPath(); g.ellipse(128, 158, 30, 10, 0, 0, Math.PI * 2); g.fill();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshBasicMaterial({ map: tex });
}

function handleMesh(color, type) {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.08, 24, 24),
    new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.7, roughness: 0.3 })
  );
  mesh.userData.handle = type;
  mesh.add(new THREE.Mesh(
    new THREE.SphereGeometry(0.12, 16, 16),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25, depthWrite: false, blending: THREE.AdditiveBlending })
  ));
  return mesh;
}

export function buildScene(el, C, labels) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.autoClear = false;
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5);
  sun.position.set(3, 5, 4); scene.add(sun);

  const front = coffeeFront(C);
  const cube = new THREE.BoxGeometry(1, 1, 1);
  const faces = [
    faceTexture(labels.right, C), faceTexture(labels.left, C),
    faceTexture(labels.top, C), faceTexture(labels.bottom, C),
    front, faceTexture(labels.back, C),
  ];
  scene.add(new THREE.Mesh(cube, faces));
  scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(cube), new THREE.LineBasicMaterial({ color: C.edge, transparent: true, opacity: 0.6 })));

  const gizmos = new THREE.Group(); scene.add(gizmos);
  gizmos.add(new THREE.Mesh(new THREE.SphereGeometry(SPHERE, 12, 8), new THREE.MeshBasicMaterial({ color: C.wire, wireframe: true, transparent: true, opacity: 0.14, depthWrite: false })));

  const ringR = SPHERE * Math.cos(RING_LAT), ringY = SPHERE * Math.sin(RING_LAT);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(ringR, 0.025, 16, 96), new THREE.MeshBasicMaterial({ color: C.yaw, transparent: true, opacity: 0.55 }));
  ring.rotation.x = Math.PI / 2; ring.position.y = ringY; gizmos.add(ring);

  const yawGroup = new THREE.Group(); gizmos.add(yawGroup);
  const arc = [];
  for (let d = V_MIN; d <= V_MAX; d += 5) arc.push(new THREE.Vector3(0, SPHERE * Math.sin(d * DEG), SPHERE * Math.cos(d * DEG)));
  yawGroup.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(arc), 32, 0.025, 8, false), new THREE.MeshBasicMaterial({ color: C.pitch, transparent: true, opacity: 0.55 })));
  const lineGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, 1], 3));
  yawGroup.add(new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: C.dist, transparent: true, opacity: 0.55 })));

  const handles = { yaw: handleMesh(C.yaw, 'yaw'), pitch: handleMesh(C.pitch, 'pitch'), distance: handleMesh(C.dist, 'distance') };
  gizmos.add(handles.yaw); yawGroup.add(handles.pitch, handles.distance);

  const markerMat = new THREE.MeshStandardMaterial({ color: C.dist, emissive: C.dist, emissiveIntensity: 0.45, roughness: 0.4 });
  const marker = new THREE.Group();
  marker.add(new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.12), markerMat));
  const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.048, 0.08, 16), markerMat);
  lens.rotation.x = Math.PI / 2; lens.position.z = -0.1; marker.add(lens);
  gizmos.add(marker);

  const overview = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100);
  const shot = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100);
  const orbit = (h, v, d) => new THREE.Vector3(d * Math.cos(v * DEG) * Math.sin(h * DEG), d * Math.sin(v * DEG), d * Math.cos(v * DEG) * Math.cos(h * DEG));
  const handleDistance = (z) => FAR - ((FAR - NEAR) * z) / 10;

  const apply = (a) => {
    const d = handleDistance(a.z);
    yawGroup.rotation.y = a.h * DEG;
    handles.yaw.position.set(ringR * Math.sin(a.h * DEG), ringY, ringR * Math.cos(a.h * DEG));
    handles.pitch.position.set(0, SPHERE * Math.sin(a.v * DEG), SPHERE * Math.cos(a.v * DEG));
    handles.distance.position.set(0, d * Math.sin(a.v * DEG), d * Math.cos(a.v * DEG));
    const pos = lineGeo.attributes.position;
    pos.setXYZ(1, 0, d * Math.sin(a.v * DEG), d * Math.cos(a.v * DEG)); pos.needsUpdate = true;
    marker.position.copy(orbit(a.h, a.v, d)); marker.lookAt(0, 0, 0); marker.rotateY(Math.PI);
    shot.position.copy(orbit(a.h, a.v, SHOT_DISTANCE)); shot.lookAt(0, 0, 0);
    shot.zoom = 1 + (0.875 * a.z) / 10; shot.updateProjectionMatrix();
  };

  let view = 'camera', inset = true;
  const render = () => {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h); renderer.setScissorTest(false); renderer.clear();
    if (view === 'object') {
      gizmos.visible = false; shot.aspect = w / h; shot.updateProjectionMatrix();
      renderer.render(scene, shot); return;
    }
    overview.aspect = w / h;
    const dist = (SPHERE * 1.2) / (Math.tan((FOV / 2) * DEG) * Math.min(1, w / h));
    overview.position.set(2.4, 1.4, 4.2).normalize().multiplyScalar(dist);
    overview.lookAt(0, 0, 0); overview.updateProjectionMatrix();
    gizmos.visible = true; renderer.render(scene, overview);
    if (!inset) return;
    shot.aspect = 1; shot.updateProjectionMatrix();
    const side = Math.round(Math.min(w, h) * INSET);
    gizmos.visible = false; renderer.setScissorTest(true);
    renderer.setViewport(w - side - 6, 6, side, side); renderer.setScissor(w - side - 6, 6, side, side);
    renderer.setClearColor(C.insetBorder, 1); renderer.clear();
    renderer.setViewport(w - side - 5, 7, side - 2, side - 2); renderer.setScissor(w - side - 5, 7, side - 2, side - 2);
    renderer.setClearColor(C.insetBg, 1); renderer.clear();
    renderer.render(scene, shot);
    renderer.setClearColor(0x000000, 0); renderer.setViewport(0, 0, w, h); renderer.setScissorTest(false);
  };

  const setView = (v, showInset) => { view = v; inset = showInset; render(); };
  const dispose = () => {
    scene.traverse((o) => {
      const m = o; m.geometry?.dispose?.();
      for (const mat of [m.material ?? []].flat()) { mat.map?.dispose?.(); mat.dispose?.(); }
    });
    renderer.dispose(); renderer.domElement.remove();
  };
  return { apply, render, setView, dispose, canvas: renderer.domElement };
}
