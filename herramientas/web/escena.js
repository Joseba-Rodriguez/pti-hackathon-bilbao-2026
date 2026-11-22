// Celda caliente en 3D (Three.js). Todo se modela en el marco del ROBOT: metros, x hacia la cartulina,
// y a la izquierda del robot, z hacia arriba, base del brazo en el origen y la mesa en z = 0.
// Las mallas del brazo y sus poses vienen de gemelo.py (MuJoCo), calibrado con las grabaciones.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { Operario } from './operario.js';
import { Astronauta } from './astronauta.js';

const R = (x, y, z) => new THREE.Vector3(x, z, -y);          // marco robot (z arriba) -> mundo Three (y arriba)
const URANIO = 0xb8ff2e;
const SUELO_Z = -0.76;                                          // suelo de la celda (la mesa mide ~76 cm)
const EMISOR_LASER = [1.22, -0.32, 0.64];                        // respaldo: el haz sale de la mano del operario
const CRISTAL_X = 0.98;                                         // pared con ventana de vidrio plomado
const OPERARIO = [1.86, -0.62];                                  // donde esta el operario, en la cabina

const VISTAS = {
  cabina:   { pos: [-0.7, 0.66, 0.52], obj: [1.0, -0.36, 0.3], fov: 54 },
  operario: { pos: [0.45, 0.02, 0.45], obj: [1.86, -0.62, 0.55] },
  operador: { pos: [1.56, 0.36, 0.6], obj: [0.3, -0.02, 0.08] },
  cenital:  { pos: [0.66, 0.0, 0.98],  obj: [0.36, 0.0, 0.0] },
  lateral:  { pos: [0.34, -0.98, 0.26], obj: [0.28, 0.0, 0.10] },
  pinza:    { pos: [0.26, -0.22, 0.20], obj: [0, 0, 0] },      // relativa a la punta
};

// ------------------------------------------------------------------ texturas procedurales
function lienzo(w, h, pintar) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  pintar(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
function ruido(ctx, w, h, base, amp, manchas = 40) {
  ctx.fillStyle = base; ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < manchas; i++) {                           // manchas suaves (humedad, uso)
    const x = Math.random() * w, y = Math.random() * h, r = 40 + Math.random() * 180;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    const a = Math.random() * 0.07;
    g.addColorStop(0, Math.random() < 0.5 ? `rgba(0,0,0,${a})` : `rgba(255,255,255,${a * 0.6})`);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  const img = ctx.getImageData(0, 0, w, h), d = img.data;     // grano
  for (let i = 0; i < d.length; i += 4) {
    const n = (Math.random() - 0.5) * amp;
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  ctx.putImageData(img, 0, 0);
}
const texHormigon = (bloques) => lienzo(1024, 1024, (ctx, w, h) => {
  ruido(ctx, w, h, '#4a4d50', 26, 70);
  if (bloques) {                                                // juntas de bloques de hormigon
    ctx.strokeStyle = 'rgba(0,0,0,.35)'; ctx.lineWidth = 3;
    const bh = h / 8, bw = w / 4;
    for (let f = 0; f <= 8; f++) {
      ctx.beginPath(); ctx.moveTo(0, f * bh); ctx.lineTo(w, f * bh); ctx.stroke();
      for (let c = 0; c <= 4; c++) {
        const x = c * bw + (f % 2) * bw / 2;
        ctx.beginPath(); ctx.moveTo(x, f * bh); ctx.lineTo(x, (f + 1) * bh); ctx.stroke();
      }
    }
  }
});
const texFranjas = () => lienzo(512, 64, (ctx, w, h) => {
  ctx.fillStyle = '#f2b705'; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#141414';
  for (let x = -h; x < w + h; x += 64) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + 32, 0); ctx.lineTo(x + 32 - h, h); ctx.lineTo(x - h, h); ctx.fill(); }
  ruido2(ctx, w, h);
});
function ruido2(ctx, w, h) { const img = ctx.getImageData(0, 0, w, h), d = img.data; for (let i = 0; i < d.length; i += 4) { const n = (Math.random() - .5) * 30; d[i] += n; d[i + 1] += n; d[i + 2] += n; } ctx.putImageData(img, 0, 0); }
function trebol(ctx, cx, cy, r, fondo, tinta) {
  ctx.fillStyle = fondo; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fill();
  ctx.fillStyle = tinta;
  for (const a0 of [-90, 30, 150]) {
    const a = a0 * Math.PI / 180, s = Math.PI / 6;
    ctx.beginPath(); ctx.arc(cx, cy, r * 0.82, a - s, a + s); ctx.arc(cx, cy, r * 0.3, a + s, a - s, true); ctx.fill();
  }
  ctx.beginPath(); ctx.arc(cx, cy, r * 0.19, 0, 7); ctx.fill();
}
const texTapa = () => lienzo(256, 256, (ctx, w) => { ctx.fillStyle = '#c9ccd0'; ctx.fillRect(0, 0, w, w); trebol(ctx, w / 2, w / 2, w * 0.44, '#f2c500', '#111'); });
const texCartel = () => lienzo(1024, 512, (ctx, w, h) => {
  ctx.fillStyle = '#f2c500'; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#111'; ctx.fillRect(14, 14, w - 28, h - 28); ctx.fillStyle = '#f2c500'; ctx.fillRect(26, 26, w - 52, h - 52);
  trebol(ctx, 250, h / 2, 170, '#f2c500', '#111');
  ctx.fillStyle = '#111'; ctx.font = '700 92px Inter, Arial'; ctx.fillText('PELIGRO', 470, 210);
  ctx.font = '600 50px Inter, Arial'; ctx.fillText('RADIACIÓN', 474, 290);
  ctx.font = '500 36px Inter, Arial'; ctx.fillText('CELDA CALIENTE 03', 474, 370);
});
const texRotulo = (texto) => lienzo(1024, 128, (ctx, w, h) => {
  ctx.clearRect(0, 0, w, h); ctx.fillStyle = 'rgba(230,236,240,.85)'; ctx.font = '700 78px Inter, Arial';
  ctx.fillText(texto, 10, 96);
});
const texResplandor = (color) => lienzo(128, 128, (ctx, w) => {
  const g = ctx.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
  g.addColorStop(0, color); g.addColorStop(0.25, color.replace('1)', '.45)')); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, w);
});

// ------------------------------------------------------------------ contenedor de uranio (el vaso real: 41 x 55 mm)
function contenedor(r, h) {
  const g = new THREE.Group(), eje = new THREE.Group();
  eje.rotation.x = Math.PI / 2;                                // cilindros de Three van en y: los ponemos en z
  g.add(eje);
  const acero = new THREE.MeshStandardMaterial({ color: 0xc8ccd2, metalness: 1, roughness: 0.26 });
  const aceroOsc = new THREE.MeshStandardMaterial({ color: 0x5a6068, metalness: 1, roughness: 0.35 });
  const cil = (rr, hh, y, mat) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(rr, rr, hh, 48), mat); m.position.y = y; m.castShadow = true; m.receiveShadow = true; eje.add(m); return m; };
  const hb = h * 0.3, hv = h * 0.34, ht = h - hb - hv;
  cil(r, hb, -h / 2 + hb / 2, acero);                           // base
  cil(r, ht, h / 2 - ht / 2, acero);                            // parte alta
  // ventana de vidrio de plomo con el nucleo brillante dentro
  const vidrio = new THREE.MeshPhysicalMaterial({ color: 0x9fdc5a, metalness: 0, roughness: 0.05, transparent: true, opacity: 0.32, clearcoat: 1 });
  cil(r * 0.97, hv, -h / 2 + hb + hv / 2, vidrio);
  const nucleo = new THREE.MeshStandardMaterial({ color: 0x223300, emissive: URANIO, emissiveIntensity: 1.8 });
  cil(r * 0.62, hv * 0.96, -h / 2 + hb + hv / 2, nucleo);
  for (let i = 0; i < 4; i++) {                                 // nervios de la pinza (como el vaso impreso)
    const n = new THREE.Mesh(new THREE.BoxGeometry(r * 0.22, hv, r * 0.22), acero);
    const a = i * Math.PI / 2 + Math.PI / 4;
    n.position.set(Math.cos(a) * r * 0.95, -h / 2 + hb + hv / 2, Math.sin(a) * r * 0.95); n.castShadow = true; eje.add(n);
  }
  const franjas = texFranjas(); franjas.wrapS = THREE.RepeatWrapping; franjas.repeat.set(3, 1);
  cil(r * 1.006, h * 0.11, -h / 2 + h * 0.12, new THREE.MeshStandardMaterial({ map: franjas, roughness: 0.6 }));
  cil(r * 1.05, h * 0.07, h / 2 - h * 0.035, aceroOsc);       // tapa
  const tapa = new THREE.Mesh(new THREE.CircleGeometry(r * 0.9, 48), new THREE.MeshStandardMaterial({ map: texTapa(), roughness: 0.5, metalness: 0.2 }));
  tapa.rotation.x = -Math.PI / 2; tapa.position.y = h / 2 + 0.0002; eje.add(tapa);
  const luz = new THREE.PointLight(URANIO, 0.08, 0.25, 2); luz.position.set(0, 0, 0); g.add(luz);
  g.userData = { nucleo, luz };
  return g;
}

// ------------------------------------------------------------------ escenario lunar: piezas y texturas
// roca irregular (icosaedro deformado con ruido suave)
function rocaGeo(r, detalle = 2, sx = 1, sy = 1, sz = 0.7) {
  const geo = new THREE.IcosahedronGeometry(1, detalle), p = geo.attributes.position, v = new THREE.Vector3();
  const f = [Math.random() * 9, Math.random() * 9, Math.random() * 9];
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const n = 1 + 0.18 * Math.sin(v.x * 3.1 + f[0]) * Math.sin(v.y * 2.7 + f[1]) + 0.1 * Math.sin(v.z * 5.3 + f[2]) + 0.05 * Math.sin((v.x + v.y) * 9);
    p.setXYZ(i, v.x * n * r * sx, v.y * n * r * sy, v.z * n * r * sz);
  }
  geo.computeVertexNormals(); return geo;
}
// la muestra de mineral (mismo tamano que el vaso real): roca oscura con cristales que brillan
function mineral(r, h) {
  const g = new THREE.Group();
  const roca = new THREE.Mesh(rocaGeo(1, 3, r * 1.15, r * 1.05, h / 2), new THREE.MeshStandardMaterial({ color: 0x3d3a37, roughness: 0.85, metalness: 0.15, flatShading: true }));
  roca.castShadow = roca.receiveShadow = true; g.add(roca);
  const cristal = new THREE.MeshStandardMaterial({ color: 0x0c2a3a, emissive: 0x38e1ff, emissiveIntensity: 1.3, roughness: 0.15, metalness: 0.1, flatShading: true });
  for (let i = 0; i < 9; i++) {
    const a = i / 9 * Math.PI * 2 + Math.random() * 0.4, el = (Math.random() - 0.3) * 0.9;
    const c = new THREE.Mesh(new THREE.OctahedronGeometry(1, 0), cristal);
    const L = r * (0.35 + Math.random() * 0.35);
    c.scale.set(L * 0.35, L, L * 0.35);
    const dir = new THREE.Vector3(Math.cos(a) * Math.cos(el), Math.sin(a) * Math.cos(el), Math.sin(el) * 1.6).normalize();
    c.position.set(dir.x * r * 0.95, dir.y * r * 0.9, dir.z * h * 0.42);
    c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    g.add(c);
  }
  const luz = new THREE.PointLight(0x38e1ff, 0.05, 0.25, 2); g.add(luz);
  g.userData = { cristal };
  return g;
}
const texTierra = () => lienzo(1024, 512, (ctx, w, h) => {
  ctx.fillStyle = '#1d4f9a'; ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 26; i++) {                                // continentes inventados
    const x = Math.random() * w, y = h * (0.2 + Math.random() * 0.6), rr = 30 + Math.random() * 90;
    ctx.fillStyle = Math.random() < 0.6 ? '#4f7a3a' : '#9a7f52';
    ctx.beginPath();
    for (let k = 0; k < 14; k++) { const a = k / 14 * Math.PI * 2, q = rr * (0.6 + Math.random() * 0.5); ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q * 0.7); }
    ctx.fill();
  }
  ctx.fillStyle = '#f2f6fa'; ctx.fillRect(0, 0, w, h * 0.07); ctx.fillRect(0, h * 0.93, w, h * 0.07);
  for (let i = 0; i < 160; i++) {                               // nubes
    ctx.fillStyle = `rgba(255,255,255,${0.25 + Math.random() * 0.5})`;
    const x = Math.random() * w, y = Math.random() * h;
    ctx.beginPath(); ctx.ellipse(x, y, 20 + Math.random() * 70, 4 + Math.random() * 10, Math.random() * 0.5, 0, 7); ctx.fill();
  }
});
const texCubierta = () => lienzo(512, 512, (ctx, w, h) => {
  ruido(ctx, w, h, '#b9bdc1', 14, 20);
  ctx.strokeStyle = 'rgba(40,44,48,.35)'; ctx.lineWidth = 2;
  for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(i * w / 4, 0); ctx.lineTo(i * w / 4, h); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i * h / 4); ctx.lineTo(w, i * h / 4); ctx.stroke(); }
  ctx.fillStyle = 'rgba(30,32,36,.5)';
  for (let i = 0; i <= 8; i++) for (let j = 0; j <= 8; j++) if (i % 2 === 0 || j % 2 === 0) { ctx.beginPath(); ctx.arc(i * w / 8, j * h / 8, 2.2, 0, 7); ctx.fill(); }
});
const texOro = () => lienzo(512, 512, (ctx, w, h) => {      // manta aislante arrugada
  ctx.fillStyle = '#c9952f'; ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) {
    const x = Math.random() * w, y = Math.random() * h, l = 10 + Math.random() * 50, a = Math.random() * Math.PI;
    ctx.strokeStyle = Math.random() < 0.5 ? `rgba(255,230,150,${Math.random() * 0.35})` : `rgba(90,55,10,${Math.random() * 0.3})`;
    ctx.lineWidth = 1 + Math.random() * 3; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); ctx.stroke();
  }
});
const texSolar = () => lienzo(512, 512, (ctx, w, h) => {
  ctx.fillStyle = '#c8ccd0'; ctx.fillRect(0, 0, w, h);
  const n = 8, m = 6, cw = (w - 20) / n, ch = (h - 20) / m;
  for (let i = 0; i < n; i++) for (let j = 0; j < m; j++) {
    const gr = ctx.createLinearGradient(0, 10 + j * ch, 0, 10 + (j + 1) * ch); gr.addColorStop(0, '#1b2f5e'); gr.addColorStop(1, '#0d1a38');
    ctx.fillStyle = gr; ctx.fillRect(10 + i * cw + 2, 10 + j * ch + 2, cw - 4, ch - 4);
  }
});
const texBandejaMuestras = () => lienzo(512, 512, (ctx, w, h) => {   // rejilla discreta, sin rotulos
  ruido(ctx, w, h, '#5d6166', 12, 10);
  ctx.strokeStyle = 'rgba(20,22,25,.25)'; ctx.lineWidth = 2;
  for (let i = 1; i < 6; i++) { ctx.beginPath(); ctx.moveTo(i * w / 6, 8); ctx.lineTo(i * w / 6, h - 8); ctx.stroke(); ctx.beginPath(); ctx.moveTo(8, i * h / 6); ctx.lineTo(w - 8, i * h / 6); ctx.stroke(); }
  ctx.strokeStyle = 'rgba(242,183,5,.7)'; ctx.lineWidth = 8; ctx.strokeRect(4, 4, w - 8, h - 8);
});

// ------------------------------------------------------------------ la celda
export class Celda {
  constructor(div) {
    this.div = div;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.82;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    div.appendChild(this.renderer.domElement);

    const s = this.scene = new THREE.Scene();
    s.background = new THREE.Color(0x05070a);
    s.fog = new THREE.Fog(0x05070a, 3.4, 7.5);
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    s.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    s.environmentIntensity = 0.16;

    this.raiz = new THREE.Group(); this.raiz.rotation.x = -Math.PI / 2; s.add(this.raiz);

    this.camara = new THREE.PerspectiveCamera(36, 1, 0.01, 30);
    this.controles = new OrbitControls(this.camara, this.renderer.domElement);
    this.controles.enableDamping = true; this.controles.dampingFactor = 0.08;
    this.controles.minDistance = 0.18; this.controles.maxDistance = 3.2;
    this.controles.maxPolarAngle = Math.PI * 0.49;
    this.controles.addEventListener('start', () => { this.anim = null; });

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(s, this.camara));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.42, 0.4, 0.93);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.geoms = [];                // mallas del brazo, en el orden de /escena
    this.peligro = 0;               // 0..1 suavizado
    this.t = 0;
    this._luces(); this._sala();
    // todo lo creado hasta aqui es el laboratorio; el escenario lunar (secundario) va aparte
    this._lab = [...s.children.filter((o) => o !== this.raiz), ...this.raiz.children];
    this._ambLab = { fondo: s.background, niebla: s.fog, amb: s.environmentIntensity };
    this.figura = this.operario; this.escenarioActual = 'lab';
    this._luna();
    this.vista('cabina', true);
    addEventListener('resize', () => this.redimensionar()); this.redimensionar();
  }

  redimensionar() {
    const w = this.div.clientWidth || innerWidth, h = this.div.clientHeight || innerHeight;
    this.renderer.setSize(w, h); this.composer.setSize(w, h);
    this.camara.aspect = w / h; this.camara.updateProjectionMatrix();
  }

  _luces() {
    const s = this.scene;
    s.add(new THREE.HemisphereLight(0xbfd2ff, 0x201812, 0.22));
    const clave = new THREE.SpotLight(0xf1f5ff, 8, 4, 0.75, 0.65, 1.6);
    clave.position.copy(R(0.25, 0.35, 1.25)); clave.target.position.copy(R(0.3, 0, 0));
    clave.castShadow = true; clave.shadow.mapSize.set(2048, 2048); clave.shadow.bias = -0.0002; clave.shadow.normalBias = 0.02;
    clave.shadow.camera.near = 0.3; clave.shadow.camera.far = 3;
    s.add(clave, clave.target);
    const relleno = new THREE.SpotLight(0xffe2c0, 2.2, 4, 0.9, 0.9, 1.6);   // luz calida que entra por el cristal
    relleno.position.copy(R(1.3, -0.3, 0.7)); relleno.target.position.copy(R(0.25, 0, 0.05)); s.add(relleno, relleno.target);
    const contra = new THREE.SpotLight(0x8fb6ff, 2.5, 4, 0.8, 0.8, 1.6);
    contra.position.copy(R(-0.6, 0.6, 0.8)); contra.target.position.copy(R(0.2, 0, 0.1)); s.add(contra, contra.target);
    this.luzClave = clave;
    // balizas de alarma (giran cuando el material esta fuera del blindaje)
    this.balizas = [];
    for (const y of [-0.92, 0.92]) {
      const base = R(-0.72, y, 0.78);
      const cupula = new THREE.Mesh(new THREE.SphereGeometry(0.035, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2),
        new THREE.MeshStandardMaterial({ color: 0x331a00, emissive: 0xff8a00, emissiveIntensity: 0.15, transparent: true, opacity: 0.9 }));
      cupula.position.copy(base); s.add(cupula);
      const foco = new THREE.SpotLight(0xff8a00, 0, 3, 0.35, 0.5, 1.5);
      foco.position.copy(base); s.add(foco, foco.target);
      this.balizas.push({ cupula, foco, base });
    }
  }

  _sala() {
    const raiz = this.raiz;
    const add = (m, sombra = true) => { m.receiveShadow = true; m.castShadow = sombra; raiz.add(m); return m; };
    // suelo de hormigon pulido con zona delimitada
    const th = texHormigon(false); th.wrapS = th.wrapT = THREE.RepeatWrapping; th.repeat.set(4, 4);
    const suelo = add(new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.MeshStandardMaterial({ map: th, roughness: 0.55, metalness: 0.05, color: 0x9aa0a6 })), false);
    suelo.position.z = SUELO_Z;
    const tf = texFranjas(); tf.wrapS = THREE.RepeatWrapping; tf.repeat.set(10, 1);
    const franja = (x, y, lx, ly) => { const m = add(new THREE.Mesh(new THREE.PlaneGeometry(lx, ly), new THREE.MeshStandardMaterial({ map: tf, roughness: 0.7 })), false); m.position.set(x, y, SUELO_Z + 0.001); if (ly > lx) m.rotation.z = Math.PI / 2, m.geometry = new THREE.PlaneGeometry(ly, lx); };
    franja(0.3, -0.75, 1.5, 0.07); franja(0.3, 0.75, 1.5, 0.07); franja(-0.43, 0, 0.07, 1.5); franja(1.03, 0, 0.07, 1.5);
    // paredes de bloques de hormigon (blindaje)
    const tb = texHormigon(true); tb.wrapS = tb.wrapT = THREE.RepeatWrapping; tb.repeat.set(2, 1);
    const mpared = new THREE.MeshStandardMaterial({ map: tb, roughness: 0.9, color: 0x8d9298 });
    const pared = (w, h) => new THREE.Mesh(new THREE.PlaneGeometry(w, h), mpared);
    const fondo = add(pared(2.6, 2.1), false); fondo.rotation.set(Math.PI / 2, Math.PI / 2, 0); fondo.position.set(-0.8, 0, SUELO_Z + 1.05);
    for (const sy of [-1, 1]) { const p = add(pared(2.6, 2.1), false); p.rotation.set(Math.PI / 2, sy > 0 ? 0 : Math.PI, 0); p.position.set(0.45, sy * 1.15, SUELO_Z + 1.05); }
    const techo = add(new THREE.Mesh(new THREE.PlaneGeometry(2.6, 2.6), new THREE.MeshStandardMaterial({ color: 0x1a1d21, roughness: 1 })), false);
    techo.rotation.x = Math.PI; techo.position.set(0.3, 0, 1.3);
    for (const y of [-0.35, 0.35]) {                            // paneles de luz del techo
      const p = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.12), new THREE.MeshBasicMaterial({ color: 0xdfe8ff }));
      p.rotation.x = Math.PI; p.position.set(0.3, y, 1.295); raiz.add(p);
    }
    // cartel de peligro y rotulos en la pared del fondo
    const cartel = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.25), new THREE.MeshStandardMaterial({ map: texCartel(), roughness: 0.55 }));
    cartel.rotation.set(Math.PI / 2, Math.PI / 2, 0); cartel.position.set(-0.795, 0.42, 0.42); raiz.add(cartel);
    const rot = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.11), new THREE.MeshBasicMaterial({ map: texRotulo('ZONA CONTROLADA · C-03'), transparent: true, opacity: 0.55 }));
    rot.rotation.set(Math.PI / 2, Math.PI / 2, 0); rot.position.set(-0.795, -0.35, 0.62); raiz.add(rot);
    // estanteria con lotes en espera (decorado)
    const balda = add(new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.7, 0.02), new THREE.MeshStandardMaterial({ color: 0x3a3f45, metalness: 0.8, roughness: 0.4 })));
    balda.position.set(-0.71, -0.42, 0.2);
    for (let i = 0; i < 4; i++) { const c = contenedor(0.0205, 0.055); c.position.set(-0.71, -0.66 + i * 0.12, 0.2 + 0.01 + 0.0275); c.remove(c.userData.luz); raiz.add(c); }
    // mesa de acero inoxidable
    const macero = new THREE.MeshStandardMaterial({ color: 0x7d838a, metalness: 0.9, roughness: 0.42 });
    const tablero = add(new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.95, 0.04), macero));
    tablero.position.set(0.3, 0, -0.02);
    for (const [x, y] of [[-0.25, -0.42], [-0.25, 0.42], [0.85, -0.42], [0.85, 0.42]]) {
      const pata = add(new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.72), macero)); pata.position.set(x, y, SUELO_Z + 0.36);
    }
    // placa de anclaje del robot
    const placa = add(new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.08, 0.006, 48), new THREE.MeshStandardMaterial({ color: 0x24282d, metalness: 0.7, roughness: 0.45 })));
    placa.rotation.x = Math.PI / 2; placa.position.set(0.03, 0, 0.003);
    this._cabina();
  }

  // ---------------------------------------------------------------- datos del gemelo
  async cargar(esc) {
    this._esc = esc;
    const plastico = new THREE.MeshPhysicalMaterial({ color: 0xc22d17, roughness: 0.5, metalness: 0, clearcoat: 0.25, clearcoatRoughness: 0.5, sheen: 0.2 });
    const motor = new THREE.MeshStandardMaterial({ color: 0x15171a, roughness: 0.38, metalness: 0.25 });
    await Promise.all(esc.geoms.map(async (g, i) => {
      const buf = await (await fetch(`/malla/${g.id}.bin`)).arrayBuffer();
      let geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(buf), 3));
      geo = toCreasedNormals(geo, Math.PI / 5);
      const m = new THREE.Mesh(geo, g.motor ? motor : plastico);
      m.castShadow = m.receiveShadow = true; m.visible = false;
      this.raiz.add(m); this.geoms[i] = m;
    }));
    this._bandeja(esc.cartulina);
    // almacen blindado (soporte real calibrado): anillo de plomo con franja de peligro
    const [sx, sy] = esc.soporte;
    const perfil = [new THREE.Vector2(0.026, 0), new THREE.Vector2(0.046, 0), new THREE.Vector2(0.046, 0.026), new THREE.Vector2(0.043, 0.03), new THREE.Vector2(0.026, 0.03)];
    const anillo = new THREE.Mesh(new THREE.LatheGeometry(perfil, 64), new THREE.MeshStandardMaterial({ color: 0x5b6167, metalness: 0.85, roughness: 0.5 }));
    anillo.rotation.x = Math.PI / 2; anillo.position.set(sx, sy, 0); anillo.castShadow = anillo.receiveShadow = true; this.raiz.add(anillo);
    const tf = texFranjas(); tf.wrapS = THREE.RepeatWrapping; tf.repeat.set(5, 1);
    const banda = new THREE.Mesh(new THREE.CylinderGeometry(0.0465, 0.0465, 0.008, 64, 1, true), new THREE.MeshStandardMaterial({ map: tf, roughness: 0.6 }));
    banda.rotation.x = Math.PI / 2; banda.position.set(sx, sy, 0.016); this.raiz.add(banda);
    this.soporte = [sx, sy];
    // el contenedor
    this.vaso = contenedor(esc.vaso.r, esc.vaso.h);
    this.vaso.position.set(sx, sy, esc.vaso.h / 2); this.raiz.add(this.vaso);
    // en la Luna el mismo objeto es una roca con cristales; lo demas del laboratorio se oculta
    this._vasoLab = [...this.vaso.children];
    this.mineral = mineral(esc.vaso.r, esc.vaso.h); this.mineral.visible = false; this.vaso.add(this.mineral);
    this._lab.push(this.bandeja.g, banda);
    this.escenario(this.escenarioActual);
    // laser: punto, halo, onda y haz desde el puntero del operador
    const rojo = texResplandor('rgba(255,40,20,1)');
    this.laser = new THREE.Group(); this.laser.visible = false; this.raiz.add(this.laser);
    const punto = new THREE.Mesh(new THREE.SphereGeometry(0.0035, 16, 12), new THREE.MeshBasicMaterial({ color: 0xff2a14 }));
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: rojo, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    halo.scale.set(0.06, 0.06, 1);
    this.onda = new THREE.Mesh(new THREE.RingGeometry(0.012, 0.014, 48), new THREE.MeshBasicMaterial({ color: 0xff3020, transparent: true, depthWrite: false }));
    this.onda.position.z = 0.0015;
    this.laser.add(punto, halo, this.onda);
    this.laserPos = new THREE.Vector3();
    const haz = new THREE.Mesh(new THREE.CylinderGeometry(0.0011, 0.0011, 1, 8, 1, true),
      new THREE.MeshBasicMaterial({ color: 0xff2a14, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    const halohaz = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 1, 12, 1, true),
      new THREE.MeshBasicMaterial({ color: 0xff2a14, transparent: true, opacity: 0.07, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.haz = new THREE.Group(); this.haz.add(haz, halohaz); this.haz.visible = false; this.raiz.add(this.haz);
    // marca del destino tras soltar
    this.destino = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.034, 64), new THREE.MeshBasicMaterial({ color: 0x32d74b, transparent: true, opacity: 0.8, depthWrite: false }));
    this.destino.position.z = 0.0016; this.destino.visible = false; this.raiz.add(this.destino);
  }

  // Cabina del operador: pared de hormigon con ventana de vidrio plomado, consola con monitores
  // y el operario apuntando con el laser a traves del cristal.
  _cabina() {
    const raiz = this.raiz, X = CRISTAL_X, SZ = SUELO_Z;
    const hormigon = new THREE.MeshStandardMaterial({ color: 0x6f747a, roughness: 0.9 });
    const marco = new THREE.MeshStandardMaterial({ color: 0x2c3036, metalness: 0.8, roughness: 0.4 });
    const caja = (lx, ly, lz, x, y, z, m) => { const b = new THREE.Mesh(new THREE.BoxGeometry(lx, ly, lz), m); b.position.set(x, y, z); b.castShadow = b.receiveShadow = true; raiz.add(b); return b; };
    const V0 = -0.12, V1 = 0.95, VY = 0.95;                       // hueco de la ventana (z) y semiancho (y)
    caja(0.3, 2.3, V0 - SZ, X + 0.15, 0, (SZ + V0) / 2, hormigon);           // antepecho
    caja(0.3, 2.3, 1.3 - V1, X + 0.15, 0, (V1 + 1.3) / 2, hormigon);          // dintel
    for (const s of [-1, 1]) caja(0.3, 1.15 - VY, V1 - V0, X + 0.15, s * (VY + (1.15 - VY) / 2), (V0 + V1) / 2, hormigon);
    for (const s of [-1, 1]) {                                     // marco de acero
      caja(0.05, 2 * VY + 0.06, 0.05, X + 0.3, 0, s > 0 ? V1 : V0, marco);
      caja(0.05, 0.05, V1 - V0, X + 0.3, s * VY, (V0 + V1) / 2, marco);
    }
    const vidrio = new THREE.Mesh(new THREE.PlaneGeometry(2 * VY, V1 - V0), new THREE.MeshPhysicalMaterial({
      color: 0xffe3a8, metalness: 0, roughness: 0.04, transparent: true, opacity: 0.1, clearcoat: 1, depthWrite: false, side: THREE.DoubleSide }));
    vidrio.rotation.set(Math.PI / 2, Math.PI / 2, 0); vidrio.position.set(X + 0.3, 0, (V0 + V1) / 2); raiz.add(vidrio);
    const rot = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.07), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4, map: (() => {
      const c = document.createElement('canvas'); c.width = 1024; c.height = 100; const x = c.getContext('2d');
      x.fillStyle = '#fff'; x.font = '600 56px Inter, Arial'; x.fillText('VIDRIO PLOMADO · 1,2 m Pb-eq', 10, 70);
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })() }));
    rot.rotation.set(Math.PI / 2, Math.PI / 2, 0); rot.position.set(X + 0.335, 0.5, V0 + 0.06); raiz.add(rot);
    // consola del operador con monitores y seta de emergencia
    const cx = X + 0.47, cy = OPERARIO[1];
    const mesa = new THREE.MeshStandardMaterial({ color: 0x3a3f46, metalness: 0.6, roughness: 0.5 });
    caja(0.32, 0.9, 0.05, cx, cy, -0.05, mesa);
    caja(0.3, 0.88, 0.68, cx + 0.02, cy, SZ + 0.34, new THREE.MeshStandardMaterial({ color: 0x23272c, metalness: 0.5, roughness: 0.6 }));
    this.pantallas = [];
    [-0.24, 0.12].forEach((dy, i) => {
      const lienzo = document.createElement('canvas'); lienzo.width = 512; lienzo.height = 320; const x = lienzo.getContext('2d');
      x.fillStyle = '#07131a'; x.fillRect(0, 0, 512, 320); x.strokeStyle = '#2bd4ff'; x.lineWidth = 3;
      x.font = '600 30px "JetBrains Mono", Consolas'; x.fillStyle = '#c6ff3d'; x.fillText(i ? 'CELDA 03 · U-235' : 'BRAZO SO-101', 20, 46);
      x.beginPath(); for (let k = 0; k < 40; k++) x.lineTo(20 + k * 12, 200 - Math.sin(k * 0.5 + i) * 50 - Math.random() * 20); x.stroke();
      x.fillStyle = '#7d8a94'; x.font = '24px "JetBrains Mono", Consolas'; x.fillText(i ? 'dosis operador 0,00 µSv' : 'ACT · 30 Hz · láser', 20, 290);
      const t = new THREE.CanvasTexture(lienzo); t.colorSpace = THREE.SRGBColorSpace;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.19), new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 1 }));
      caja(0.03, 0.33, 0.22, cx - 0.1, cy + dy, 0.12, marco);        // carcasa del monitor
      m.rotation.set(Math.PI / 2, Math.PI / 2, 0);                   // mira hacia el operario (+x)
      m.position.set(cx - 0.084, cy + dy, 0.12); raiz.add(m); this.pantallas.push(m);
    });
    const seta = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.025, 24), new THREE.MeshStandardMaterial({ color: 0xd11a10, roughness: 0.35 }));
    seta.rotation.x = Math.PI / 2; seta.position.set(cx + 0.06, cy + 0.38, -0.012); seta.castShadow = true; raiz.add(seta);
    caja(0.07, 0.07, 0.02, cx + 0.06, cy + 0.38, -0.03, new THREE.MeshStandardMaterial({ color: 0xf2c500 }));
    // luz calida de la cabina sobre el operario
    const luz = new THREE.SpotLight(0xffd9a8, 6, 3, 0.7, 0.8, 1.6);
    luz.position.copy(R(OPERARIO[0] + 0.2, OPERARIO[1] + 0.3, 1.25)); luz.target.position.copy(R(OPERARIO[0], OPERARIO[1], 0.2));
    this.scene.add(luz, luz.target);
    // el operario, de pie tras la consola, mirando a la celda
    this.operario = new Operario();
    this.operario.grupo.position.set(OPERARIO[0], OPERARIO[1], SZ);
    this.operario.grupo.rotation.z = -Math.PI / 2;
    raiz.add(this.operario.grupo);
  }

  // Bandeja de manipulacion de acero inoxidable sobre la zona de trabajo (la cartulina real):
  // 4 x 4 celdas suaves con nervios bajos, borde elevado y franja de seguridad. La celda donde
  // apunta el laser se ilumina en rojo; donde se deposita el contenedor, en verde.
  _bandeja(P) {
    const v = (a, b) => [b[0] - a[0], b[1] - a[1]];
    const e1 = v(P[0], P[1]), e2 = v(P[3], P[2]);                 // lados "hacia fuera del robot"
    const ang = Math.atan2(e1[1] + e2[1], e1[0] + e2[0]);
    const c = [P.reduce((s, p) => s + p[0], 0) / 4, P.reduce((s, p) => s + p[1], 0) / 4];
    const cs = Math.cos(ang), sn = Math.sin(ang);
    const loc = (x, y) => [(x - c[0]) * cs + (y - c[1]) * sn, -(x - c[0]) * sn + (y - c[1]) * cs];
    const us = P.map(p => loc(...p)[0]), vs = P.map(p => loc(...p)[1]);
    const L = (Math.max(...us) - Math.min(...us)) * 0.97, W = (Math.max(...vs) - Math.min(...vs)) * 0.97;
    const N = 4, cl = L / N, cw = W / N, ESP = 0.004;               // 4 x 4 celdas; chapa de 4 mm
    const g = new THREE.Group(); g.position.set(c[0], c[1], 0); g.rotation.z = ang; this.raiz.add(g);
    this.bandeja = { g, loc, L, W, N, cl, cw };
    // chapa superior: inox cepillado con celdas suaves (sin rotulos) y franja de seguridad
    const tex = lienzo(1024, 1024, (ctx, TW, TH) => {
      ctx.fillStyle = '#8e959c'; ctx.fillRect(0, 0, TW, TH);
      for (let i = 0; i < 2600; i++) {                            // cepillado (a lo largo de u)
        const y = Math.random() * TH, a = Math.random() * 0.08;
        ctx.strokeStyle = Math.random() < 0.5 ? `rgba(255,255,255,${a})` : `rgba(0,0,0,${a})`;
        ctx.lineWidth = Math.random() * 1.5; const x = Math.random() * TW;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 80 + Math.random() * 300, y); ctx.stroke();
      }
      const m = 0.045 * TW;                                       // franja de seguridad perimetral
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, TW, TH); ctx.rect(m, m, TW - 2 * m, TH - 2 * m); ctx.clip('evenodd');
      ctx.fillStyle = '#e8b300'; ctx.fillRect(0, 0, TW, TH); ctx.fillStyle = '#151515';
      for (let x = -TH; x < TW + TH; x += 44) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + 22, 0); ctx.lineTo(x + 22 - TH, TH); ctx.lineTo(x - TH, TH); ctx.fill(); }
      ctx.restore();
      const iw = (TW - 2 * m) / N, ih = (TH - 2 * m) / N;
      for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {   // i: u (lejos del robot), j: v
        const x = m + i * iw, y = m + (N - 1 - j) * ih;           // canvas y hacia abajo = -v
        const gr = ctx.createRadialGradient(x + iw / 2, y + ih / 2, 0, x + iw / 2, y + ih / 2, iw * 0.7);
        gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,.06)');
        ctx.fillStyle = gr; ctx.fillRect(x + 6, y + 6, iw - 12, ih - 12);
        ctx.strokeStyle = 'rgba(20,24,28,.14)'; ctx.lineWidth = 1.5; ctx.strokeRect(x + 10, y + 10, iw - 20, ih - 20);
      }
    });
    const acero = new THREE.MeshStandardMaterial({ color: 0x9aa1a8, metalness: 0.92, roughness: 0.38 });
    const tapa = new THREE.MeshStandardMaterial({ map: tex, metalness: 0.85, roughness: 0.42 });
    const chapa = new THREE.Mesh(new THREE.BoxGeometry(L, W, ESP), [acero, acero, acero, acero, tapa, acero]);
    chapa.position.z = -ESP / 2 + 0.002; chapa.receiveShadow = true; g.add(chapa);
    const caja = (lx, ly, lz, x, y, z, mat = acero) => { const b = new THREE.Mesh(new THREE.BoxGeometry(lx, ly, lz), mat); b.position.set(x, y, z); b.castShadow = b.receiveShadow = true; g.add(b); return b; };
    const RB = 0.012, RH = 0.014;                                 // borde elevado
    caja(L + 2 * RB, RB, RH, 0, W / 2 + RB / 2, RH / 2); caja(L + 2 * RB, RB, RH, 0, -W / 2 - RB / 2, RH / 2);
    caja(RB, W, RH, L / 2 + RB / 2, 0, RH / 2); caja(RB, W, RH, -L / 2 - RB / 2, 0, RH / 2);
    const m = 0.045 * L, iL = L - 2 * m, iW = W - 2 * 0.045 * W;   // nervios separadores
    const nervio = new THREE.MeshStandardMaterial({ color: 0x8e959c, metalness: 0.9, roughness: 0.42 });
    for (let k = 1; k < N; k++) {                                 // nervios bajos, casi del color de la chapa
      caja(0.002, iW, 0.001, -iL / 2 + k * iL / N, 0, 0.002 + 0.0005, nervio);
      caja(iL, 0.002, 0.001, 0, -iW / 2 + k * iW / N, 0.002 + 0.0005, nervio);
    }
    for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {   // tornillos de las esquinas
      const t = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.002, 16), nervio);
      t.rotation.x = Math.PI / 2; t.position.set(sx * (L / 2 + RB / 2), sy * (W / 2 + RB / 2), RH + 0.001); g.add(t);
    }
    // resaltes de celda: objetivo (laser) y deposito
    const resalte = (color) => {
      const r = new THREE.Group();
      r.add(new THREE.Mesh(new THREE.PlaneGeometry(iL / N * 0.9, iW / N * 0.9),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false })));
      const borde = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => new THREE.Vector3(a * iL / N * 0.45, b * iW / N * 0.45, 0))),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
      r.add(borde); r.position.z = 0.0042; r.visible = false; g.add(r); return r;
    };
    this.bandeja.objetivo = resalte(0xff2a14);
    this.bandeja.deposito = resalte(0x32d74b);
    this.bandeja.m = m; this.bandeja.iL = iL; this.bandeja.iW = iW;
  }

  // (x, y) del robot -> nombre de celda ("B3") y su centro en la bandeja; null si cae fuera
  celdaDe(x, y, conCentro = false) {
    const b = this.bandeja; if (!b) return null;
    const [u, v] = b.loc(x, y);
    const i = Math.floor((u + b.iL / 2) / (b.iL / b.N)), j = Math.floor((v + b.iW / 2) / (b.iW / b.N));
    if (i < 0 || j < 0 || i >= b.N || j >= b.N) return null;
    const nombre = 'ABCD'[j] + (b.N - i);
    if (!conCentro) return nombre;
    return { nombre, u: -b.iL / 2 + (i + 0.5) * b.iL / b.N, v: -b.iW / 2 + (j + 0.5) * b.iW / b.N };
  }

  actualizar(est, dt) {
    this.t += dt;
    if (this.bandeja) {                                          // celdas iluminadas
      const b = this.bandeja;
      const ob = est.laser_m ? this.celdaDe(est.laser_m[0], est.laser_m[1], true) : null;
      b.objetivo.visible = !!ob;
      if (ob) { b.objetivo.position.x = ob.u; b.objetivo.position.y = ob.v; b.objetivo.children[0].material.opacity = 0.16 + 0.12 * Math.sin(this.t * 6); }
      const de = est.destino ? this.celdaDe(est.destino[0], est.destino[1], true) : null;
      b.deposito.visible = !!de;
      if (de) { b.deposito.position.x = de.u; b.deposito.position.y = de.v; }
    }
    const k = 1 - Math.exp(-dt * 16);                           // suavizado (los datos llegan a ~30 Hz)
    if (est.poses && this.geoms.length) {
      est.poses.forEach((p, i) => {
        const m = this.geoms[i]; if (!m) return;
        const pos = new THREE.Vector3(p[0], p[1], p[2]), q = new THREE.Quaternion(p[4], p[5], p[6], p[3]);
        if (!m.visible) { m.position.copy(pos); m.quaternion.copy(q); m.visible = true; }
        else { m.position.lerp(pos, k); m.quaternion.slerp(q, k); }
      });
    }
    if (this.vaso && est.vaso) this.vaso.position.lerp(new THREE.Vector3(...est.vaso), k);
    // laser
    if (this.laser) {
      const on = !!est.laser_m;
      if (on) {
        const obj = new THREE.Vector3(est.laser_m[0], est.laser_m[1], 0.0045);   // sobre la chapa de la bandeja
        if (!this.laser.visible) this.laserPos.copy(obj); else this.laserPos.lerp(obj, 1 - Math.exp(-dt * 20));
        this.laser.position.copy(this.laserPos);
        const s = (this.t * 1.4) % 1; this.onda.scale.setScalar(1 + s * 2.2); this.onda.material.opacity = 0.8 * (1 - s);
        const a = this.figura ? this.figura.emisor(this.raiz) : new THREE.Vector3(...EMISOR_LASER), b = this.laserPos.clone(), d = b.clone().sub(a);
        this.haz.position.copy(a).addScaledVector(d, 0.5);
        this.haz.scale.set(1, d.length(), 1);
        this.haz.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
      }
      this.laser.visible = on; this.haz.visible = on;
      if (est.destino) { this.destino.visible = true; this.destino.position.set(est.destino[0], est.destino[1], 0.0046); }
      else this.destino.visible = false;
    }
    // ambiente de peligro: balizas girando y nucleo mas intenso cuando el contenedor esta fuera
    const objetivo = est.cogido ? 1 : 0;
    this.peligro += (objetivo - this.peligro) * Math.min(1, dt * 2.5);
    this.balizas.forEach((b, i) => {
      const a = this.t * 4 + i * Math.PI;
      b.foco.intensity = 9 * this.peligro;
      b.foco.target.position.copy(b.base).add(new THREE.Vector3(Math.cos(a), -0.35, Math.sin(a)));
      b.cupula.material.emissiveIntensity = 0.15 + 2.6 * this.peligro * (0.6 + 0.4 * Math.sin(a * 2));
    });
    if (this.vaso) {
      const u = this.vaso.userData;
      u.nucleo.emissiveIntensity = 1.5 + this.peligro * 1.6 + Math.sin(this.t * 3) * 0.25;
      u.luz.intensity = 0.02 + this.peligro * 0.12;
    }
    if (this.figura) this.figura.actualizar(dt, est.laser_m && this.laser ? this.laserPos.clone() : null, this.raiz, this.peligro);
    if (this.mineral && this.mineral.visible) this.mineral.userData.cristal.emissiveIntensity = 1.2 + this.peligro + Math.sin(this.t * 2.2) * 0.3;
    if (this.pantallas) this.pantallas.forEach((m, i) => (m.material.emissiveIntensity = 0.9 + 0.15 * Math.sin(this.t * 3 + i) + this.peligro * 0.6 * (Math.sin(this.t * 10) > 0 ? 1 : 0)));
    this.luzClave.color.setRGB(0.95 + 0.05 * this.peligro, 0.96 - 0.12 * this.peligro, 1 - 0.25 * this.peligro);
    // camara
    if (this.anim) {
      const a = this.anim; a.t = Math.min(1, a.t + dt / a.dur);
      const e = a.t < 0.5 ? 4 * a.t ** 3 : 1 - (-2 * a.t + 2) ** 3 / 2;
      this.camara.position.lerpVectors(a.p0, a.p1, e);
      this.controles.target.lerpVectors(a.o0, a.o1, e);
      if (a.t >= 1) this.anim = null;
    }
    if (this.seguir && !this.anim && this.geoms.length) {                    // seguir la pinza
      const punta = this.punta();
      const t = this.raiz.localToWorld(punta.clone());
      const d = t.clone().sub(this.controles.target);
      this.controles.target.add(d.multiplyScalar(k)); this.camara.position.add(d);
    }
    this.controles.update();
    this.composer.render(dt);
  }

  punta() {   // centro de la mandibula fija, en marco robot
    const m = this.geoms.find((g, i) => g && this._esc && this._esc.geoms[i].cuerpo === 'Fixed_Jaw');
    return m ? m.position.clone() : new THREE.Vector3(0.3, 0, 0.1);
  }

  vista(nombre, inmediata = false) {
    const v = VISTAS[nombre]; if (!v) return;
    this.camara.fov = v.fov || 36; this.camara.updateProjectionMatrix();
    this.seguir = nombre === 'pinza';
    let pos = new THREE.Vector3(...v.pos), obj = new THREE.Vector3(...v.obj);
    if (this.seguir) { const p = this.punta(); obj = p; pos = p.clone().add(new THREE.Vector3(...v.pos)); }
    const P = this.raiz.localToWorld(pos), O = this.raiz.localToWorld(obj);
    if (inmediata) { this.camara.position.copy(P); this.controles.target.copy(O); this.controles.update(); return; }
    this.anim = { t: 0, dur: 1.3, p0: this.camara.position.clone(), p1: P, o0: this.controles.target.clone(), o1: O };
  }

  posOperario() {             // cabeza del operario en marco robot
    return this.figura ? this.raiz.worldToLocal(this.figura.cabeza.getWorldPosition(new THREE.Vector3())) : null;
  }

  // Cambia de escenario: 'lab' (celda caliente, el principal) o 'luna' (rover + astronauta, secundario).
  // El brazo, el laser y el objeto que se mueve son los mismos; solo cambia lo que los rodea.
  escenario(nombre) {
    const luna = nombre === 'luna';
    this.escenarioActual = luna ? 'luna' : 'lab';
    this._lab.forEach((o) => (o.visible = !luna));
    this.lunaG.visible = luna;
    if (this._vasoLab) { this._vasoLab.forEach((o) => (o.visible = !luna)); this.mineral.visible = luna; }
    const s = this.scene;
    s.background = luna ? new THREE.Color(0x000000) : this._ambLab.fondo;
    s.fog = luna ? this.nieblaLuna : this._ambLab.niebla;
    s.environmentIntensity = luna ? 0.1 : this._ambLab.amb;
    this.figura = luna ? this.astronauta : this.operario;
    this.controles.maxDistance = luna ? 5 : 3.2;
    return this.escenarioActual;
  }

  // ---------------------------------------------------------------- escenario lunar (secundario)
  // Rover con el brazo encima, regolito con crateres y rocas, cielo negro con estrellas y la Tierra,
  // sol rasante con sombras duras y un astronauta que marca con el laser el mineral a recoger.
  _luna() {
    const g = this.lunaG = new THREE.Group(); g.visible = false; this.raiz.add(g);
    this.nieblaLuna = new THREE.Fog(0x000000, 9, 24);
    const SZ = SUELO_Z;
    // luz: sol rasante (sombras duras), luz de la Tierra muy tenue y un relleno frio
    const sol = new THREE.DirectionalLight(0xfff6e8, 3.6);
    sol.position.set(-1.6, -2.6, 2.0); sol.target.position.set(0.6, -0.2, SZ);
    sol.castShadow = true; sol.shadow.mapSize.set(2048, 2048); sol.shadow.bias = -0.0004; sol.shadow.normalBias = 0.02;
    Object.assign(sol.shadow.camera, { left: -2.6, right: 2.6, top: 2.6, bottom: -2.6, near: 0.5, far: 9 });
    g.add(sol, sol.target);
    g.add(new THREE.HemisphereLight(0x9db8ff, 0x1a1a1a, 0.22));
    const relleno = new THREE.DirectionalLight(0x8fa8ff, 0.35); relleno.position.set(2, 2, 1); g.add(relleno);

    // regolito: malla con crateres y ondulaciones; zona llana alrededor del rover y del astronauta
    const N = 240, T = 40, geo = new THREE.PlaneGeometry(T, T, N, N), pos = geo.attributes.position;
    const crateres = [];
    for (let i = 0; i < 70; i++) {
      const r = 0.15 + Math.random() ** 2 * 2.2, d = 1.6 + Math.random() * 16, a = Math.random() * Math.PI * 2;
      crateres.push([Math.cos(a) * d + 0.6, Math.sin(a) * d, r]);
    }
    const colores = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i);
      let z = 0.05 * Math.sin(x * 0.7 + 1.3) * Math.cos(y * 0.55) + 0.025 * Math.sin(x * 2.3 + y * 1.7) + 0.008 * Math.sin(x * 9.1) * Math.sin(y * 7.3);
      for (const [cx, cy, r] of crateres) {
        const d = Math.hypot(x - cx, y - cy) / r;
        if (d < 1.35) z += d < 1 ? -0.22 * r * (1 - d * d) : 0.06 * r * Math.sin((d - 1) / 0.35 * Math.PI);
      }
      const lejos = Math.hypot(x - 0.6, y + 0.2);
      z *= Math.min(1, Math.max(0, (lejos - 1.6) / 1.6));            // llano junto al rover
      z += Math.max(0, lejos - 9) * 0.08 * (1 + Math.sin(Math.atan2(y, x) * 5));   // colinas al fondo
      pos.setZ(i, z);
      const c = 0.42 + (Math.random() - 0.5) * 0.06 + z * 0.4;
      colores.set([c, c * 0.985, c * 0.96], i * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colores, 3));
    geo.computeVertexNormals();
    const grano = lienzo(512, 512, (ctx, w, h) => ruido(ctx, w, h, '#8a8986', 60, 120)); grano.wrapS = grano.wrapT = THREE.RepeatWrapping; grano.repeat.set(60, 60);
    const suelo = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: grano, vertexColors: true, roughness: 1, metalness: 0 }));
    suelo.position.set(0.6, 0, SZ); suelo.receiveShadow = true; g.add(suelo);
    // rocas sueltas
    const mroca = new THREE.MeshStandardMaterial({ color: 0x6c6a66, roughness: 0.95, flatShading: true });
    for (let i = 0; i < 90; i++) {
      const a = Math.random() * Math.PI * 2, d = 1.0 + Math.random() * 7, x = 0.6 + Math.cos(a) * d, y = Math.sin(a) * d;
      if (Math.hypot(x - OPERARIO[0], y - OPERARIO[1]) < 0.5 || (x > -0.5 && x < 1.0 && Math.abs(y) < 0.8)) continue;
      const r = 0.02 + Math.random() ** 3 * 0.22, roca = new THREE.Mesh(rocaGeo(r, 1), mroca);
      roca.position.set(x, y, SZ + r * 0.25); roca.rotation.set(Math.random() * 3, Math.random() * 3, Math.random() * 3);
      roca.castShadow = roca.receiveShadow = true; g.add(roca);
    }
    // cielo: estrellas, la Tierra y el disco del sol
    const P = 2600, est = new Float32Array(P * 3);
    for (let i = 0; i < P; i++) {
      const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u);
      est.set([Math.cos(th) * s * 26, Math.sin(th) * s * 26, Math.abs(u) * 26 - 1], i * 3);
    }
    const ge = new THREE.BufferGeometry(); ge.setAttribute('position', new THREE.BufferAttribute(est, 3));
    g.add(new THREE.Points(ge, new THREE.PointsMaterial({ color: 0xffffff, size: 1.4, sizeAttenuation: false, fog: false, transparent: true, opacity: 0.85 })));
    const tierra = new THREE.Mesh(new THREE.SphereGeometry(1.1, 64, 48), new THREE.MeshStandardMaterial({ map: texTierra(), roughness: 0.6, fog: false }));
    tierra.position.set(-14, 9, 9); tierra.rotation.set(0.4, 0.2, 0); g.add(tierra);
    const atm = new THREE.Sprite(new THREE.SpriteMaterial({ map: texResplandor('rgba(110,170,255,1)'), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.45, fog: false }));
    atm.position.copy(tierra.position); atm.scale.set(3.4, 3.4, 1); g.add(atm);
    const disco = new THREE.Sprite(new THREE.SpriteMaterial({ map: texResplandor('rgba(255,250,235,1)'), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, fog: false }));
    disco.position.set(-1.6 * 6, -2.6 * 6, 2.0 * 6); disco.scale.set(2.2, 2.2, 1); g.add(disco);

    this._rover(g);
    // astronauta donde estaba el operario (asi las vistas de camara siguen valiendo)
    this.astronauta = new Astronauta('AITOR ETXALAR');
    this.astronauta.grupo.position.set(OPERARIO[0], OPERARIO[1], SZ);
    this.astronauta.grupo.rotation.z = -Math.PI / 2;
    g.add(this.astronauta.grupo);
  }

  // Rover de seis ruedas con suspension, mastil de camaras, antena y panel solar. La cubierta
  // queda a la altura de la mesa (z = 0): el brazo va anclado encima y la bandeja de muestras
  // ocupa el sitio de la zona de trabajo real.
  _rover(g) {
    const SZ = SUELO_Z;
    const caja = (lx, ly, lz, x, y, z, m) => { const b = new THREE.Mesh(new THREE.BoxGeometry(lx, ly, lz), m); b.position.set(x, y, z); b.castShadow = b.receiveShadow = true; g.add(b); return b; };
    const alu = new THREE.MeshStandardMaterial({ map: texCubierta(), color: 0xd6d8da, metalness: 0.7, roughness: 0.42 });
    const oro = new THREE.MeshStandardMaterial({ map: texOro(), color: 0xffffff, metalness: 1, roughness: 0.32 });
    const negro = new THREE.MeshStandardMaterial({ color: 0x1d2024, metalness: 0.5, roughness: 0.55 });
    const metal = new THREE.MeshStandardMaterial({ color: 0x9aa1a8, metalness: 0.9, roughness: 0.35 });
    caja(1.0, 0.76, 0.05, 0.2, 0, -0.025, alu);                                // cubierta
    caja(0.92, 0.66, 0.24, 0.2, 0, -0.17, oro);                                // cuerpo con aislante dorado
    caja(0.6, 0.5, 0.004, 0.37, 0.05, 0.0005, new THREE.MeshStandardMaterial({ map: texBandejaMuestras(), metalness: 0.6, roughness: 0.6 }));
    // suspension y ruedas
    const RW = 0.15, ZW = SZ + RW, ruedas = [];
    const barra = (a, b, r = 0.016) => {
      const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), d = B.clone().sub(A);
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), 12), metal);
      m.position.copy(A).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
      m.castShadow = true; g.add(m);
    };
    for (const sy of [-1, 1]) {
      const yb = sy * 0.36, yw = sy * 0.49;
      barra([0.2, yb, -0.2], [0.2, sy * 0.42, -0.2], 0.03);                    // eje del balancin
      barra([0.2, sy * 0.42, -0.2], [-0.22, sy * 0.42, ZW + 0.02]);
      barra([0.2, sy * 0.42, -0.2], [0.42, sy * 0.42, -0.32]);
      barra([0.42, sy * 0.42, -0.32], [0.2, sy * 0.42, ZW + 0.02]);
      barra([0.42, sy * 0.42, -0.32], [0.64, sy * 0.42, ZW + 0.02]);
      for (const x of [-0.22, 0.2, 0.64]) {
        const rueda = new THREE.Group(); rueda.position.set(x, yw, ZW); g.add(rueda); ruedas.push(rueda);
        const llanta = new THREE.Mesh(new THREE.CylinderGeometry(RW, RW, 0.11, 40, 1, true), new THREE.MeshStandardMaterial({ color: 0x2a2d31, metalness: 0.6, roughness: 0.6, side: THREE.DoubleSide }));
        llanta.castShadow = llanta.receiveShadow = true; rueda.add(llanta);
        for (let k = 0; k < 18; k++) {                                         // tacos de la banda
          const a = k / 18 * Math.PI * 2, t = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.11, 0.012), negro);
          t.position.set(Math.cos(a) * RW, 0, Math.sin(a) * RW); t.rotation.y = -a; t.castShadow = true; rueda.add(t);
        }
        for (const s of [-1, 1]) {
          const tapa = new THREE.Mesh(new THREE.CircleGeometry(RW * 0.92, 40), metal); tapa.position.y = s * 0.055; tapa.rotation.x = s * -Math.PI / 2; rueda.add(tapa);
        }
        const buje = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.13, 20), negro); rueda.add(buje);
        barra([x, sy * 0.42, ZW + 0.02], [x, yw, ZW], 0.02);
      }
    }
    this.ruedas = ruedas;
    // mastil con cabeza de camaras estereo (detras a la derecha, sin tapar la vista de cabina)
    barra([-0.2, -0.28, 0], [-0.2, -0.28, 0.42], 0.018);
    const cabeza = caja(0.07, 0.2, 0.07, -0.2, -0.28, 0.46, alu);
    for (const s of [-1, 1]) {
      const lente = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.02, 20), new THREE.MeshStandardMaterial({ color: 0x0a0a0a, metalness: 0.2, roughness: 0.05 }));
      lente.rotation.z = Math.PI / 2; lente.position.set(0.04, s * 0.06, 0); cabeza.add(lente);
    }
    // antena de alta ganancia y panel solar
    barra([-0.2, 0.3, 0], [-0.2, 0.3, 0.16], 0.012);
    const plato = new THREE.Mesh(new THREE.SphereGeometry(0.1, 32, 12, 0, Math.PI * 2, 0, Math.PI * 0.32), new THREE.MeshStandardMaterial({ color: 0xe8e8e8, metalness: 0.3, roughness: 0.5, side: THREE.DoubleSide }));
    plato.position.set(-0.2, 0.3, 0.16); plato.rotation.set(-0.9, 0.5, 0); plato.castShadow = true; g.add(plato);
    const panel = caja(0.5, 0.74, 0.012, -0.44, 0, 0.02, new THREE.MeshStandardMaterial({ map: texSolar(), metalness: 0.5, roughness: 0.25 }));
    panel.rotation.y = 0.32;
    // luces de posicion
    for (const sy of [-1, 1]) {
      const l = new THREE.Mesh(new THREE.SphereGeometry(0.012, 12, 8), new THREE.MeshBasicMaterial({ color: sy > 0 ? 0x32d74b : 0xff3b30 }));
      l.position.set(0.7, sy * 0.36, -0.03); g.add(l);
    }
  }

  aPantalla(x, y, z) {        // marco robot -> pixeles de la ventana (o null si queda detras)
    const p = this.raiz.localToWorld(new THREE.Vector3(x, y, z)).project(this.camara);
    if (p.z > 1) return null;
    return { x: (p.x + 1) / 2 * this.div.clientWidth, y: (1 - p.y) / 2 * this.div.clientHeight };
  }
}
