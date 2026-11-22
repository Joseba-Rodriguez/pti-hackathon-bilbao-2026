// Operario de la cabina (personaje propio): tecnico robusto con casco, bigote, mono naranja y taza
// de cafe. Esta FUERA de la celda, tras el cristal plomado, y apunta con el puntero laser al
// objetivo: el haz sale de su mano. Formas organicas (perfiles torneados y volumenes suaves) en vez
// de primitivas sueltas. Se modela en un marco y-arriba (origen en el suelo, mira a +z) y se coloca
// en el marco del robot (z arriba) mirando hacia la celda (-x).
import * as THREE from 'three';

const PIEL = 0xe9b08c, MONO = 0xe2611c, REFLEC = 0xd9dde0, CASCO = 0xf5c400, BOTA = 0x2b2420,
  SUELA = 0x161616, PELO = 0x4a3a2e, GUANTE = 0xeeeeea;

function mat(color, extra = {}) { return new THREE.MeshStandardMaterial({ color, roughness: 0.62, metalness: 0, ...extra }); }
function malla(geo, m, x = 0, y = 0, z = 0, padre) {
  const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; o.receiveShadow = true;
  if (padre) padre.add(o); return o;
}
// solido de revolucion a partir de un perfil [radio, altura] de abajo arriba
const torno = (pts, seg = 48) => new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), seg);
const esfera = (r, ws = 32, hs = 24) => new THREE.SphereGeometry(r, ws, hs);

function chapa(texto) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 96;
  const x = c.getContext('2d');
  x.fillStyle = '#f4f4f0'; x.fillRect(0, 0, 256, 96); x.fillStyle = '#e8651e'; x.fillRect(0, 0, 256, 22);
  x.fillStyle = '#111'; x.font = '700 15px Inter, Arial'; x.fillText('PTI · CELDA 03', 10, 16);
  let px = 34; do { x.font = `700 ${px}px Inter, Arial`; } while (x.measureText(texto).width > 236 && --px > 12);
  x.fillText(texto, 10, 62); x.font = '500 16px Inter, Arial'; x.fillText('dosímetro 0,00 µSv', 10, 86);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Operario {
  constructor() {
    this.grupo = new THREE.Group();                 // marco robot (z arriba)
    const cuerpo = this.cuerpo = new THREE.Group(); // marco y-arriba
    cuerpo.rotation.x = Math.PI / 2;
    this.grupo.add(cuerpo);
    const mono = mat(MONO, { roughness: 0.82 }), piel = mat(PIEL, { roughness: 0.5 }),
      refl = mat(REFLEC, { metalness: 0.35, roughness: 0.28 }), bota = mat(BOTA, { roughness: 0.55 }),
      suela = mat(SUELA, { roughness: 0.9 }), pelo = mat(PELO, { roughness: 0.95 });

    // piernas: perfil torneado (tobillo, gemelo, rodilla, muslo) y botas redondeadas
    for (const s of [-1, 1]) {
      const pierna = malla(torno([[0, 0], [0.062, 0], [0.066, 0.05], [0.078, 0.17], [0.08, 0.25], [0.077, 0.29],
        [0.092, 0.38], [0.106, 0.5], [0.104, 0.57], [0, 0.6]]), mono, s * 0.115, 0.08, 0, cuerpo);
      pierna.scale.z = 0.92;
      const b = malla(new THREE.TorusGeometry(0.075, 0.009, 8, 40), refl, s * 0.115, 0.2, 0, cuerpo); b.rotation.x = Math.PI / 2;
      const empeine = malla(esfera(1, 28, 18), bota, s * 0.115, 0.06, 0.045, cuerpo); empeine.scale.set(0.075, 0.06, 0.135);
      malla(torno([[0, 0], [0.068, 0], [0.07, 0.06], [0, 0.07]], 28), bota, s * 0.115, 0.03, 0, cuerpo);  // cana de la bota
      const pisada = malla(esfera(1, 28, 12), suela, s * 0.115, 0.014, 0.04, cuerpo); pisada.scale.set(0.082, 0.016, 0.148);
    }

    // tronco: un solo volumen torneado (cadera, barriga, pecho, hombros) mas la tripa por delante
    this.tronco = new THREE.Group(); this.tronco.position.y = 0.62; cuerpo.add(this.tronco);
    const torso = malla(torno([[0, -0.02], [0.18, -0.02], [0.24, 0.04], [0.29, 0.16], [0.305, 0.29], [0.295, 0.41],
      [0.28, 0.52], [0.27, 0.6], [0.235, 0.67], [0.15, 0.72], [0.09, 0.745], [0, 0.75]], 56), mono, 0, 0, 0, this.tronco);
    torso.scale.set(1.12, 1, 0.86);
    const tripa = malla(esfera(0.24, 40, 28), mono, 0, 0.27, 0.075, this.tronco); tripa.scale.set(1.08, 1.05, 0.95);
    const cinturon = malla(new THREE.TorusGeometry(0.29, 0.016, 10, 64), mat(0x2a2a2a, { roughness: 0.6 }), 0, 0.08, 0.025, this.tronco);
    cinturon.rotation.x = Math.PI / 2; cinturon.scale.set(1.0, 1.02, 1);
    malla(new THREE.BoxGeometry(0.05, 0.035, 0.012), mat(0x9a9a9a, { metalness: 0.9, roughness: 0.3 }), 0, 0.08, 0.31, this.tronco); // hebilla
    // cremallera y cuello del mono
    const crem = malla(new THREE.CylinderGeometry(0.004, 0.004, 0.42, 6), mat(0x777777, { metalness: 0.8, roughness: 0.4 }), 0, 0.5, 0.235, this.tronco);
    crem.rotation.x = -0.18;
    const cuello = malla(new THREE.TorusGeometry(0.095, 0.022, 12, 40), mono, 0, 0.735, 0.01, this.tronco); cuello.rotation.x = Math.PI / 2 - 0.15;
    const placa = new THREE.Mesh(new THREE.PlaneGeometry(0.13, 0.05), new THREE.MeshStandardMaterial({ map: chapa('AITOR ETXALAR'), roughness: 0.5 }));
    placa.position.set(-0.11, 0.58, 0.238); placa.rotation.set(-0.12, -0.32, 0); this.tronco.add(placa);
    const dosi = malla(new THREE.BoxGeometry(0.038, 0.055, 0.014), mat(0x2f6fd0, { roughness: 0.4 }), 0.115, 0.6, 0.232, this.tronco);
    dosi.rotation.y = 0.32;

    // cuello y cabeza
    malla(torno([[0.085, 0], [0.08, 0.06], [0.078, 0.12], [0, 0.125]], 32), piel, 0, 0.72, 0, this.tronco);
    const cab = this.cabeza = new THREE.Group(); cab.position.set(0, 0.9, 0.012); this.tronco.add(cab);
    const craneo = malla(esfera(0.148, 48, 36), piel, 0, 0.005, 0, cab); craneo.scale.set(0.94, 1.08, 1.0);
    const mandibula = malla(esfera(0.12, 40, 28), piel, 0, -0.068, 0.028, cab); mandibula.scale.set(1.04, 0.78, 0.98);
    for (const s of [-1, 1]) {
      const mof = malla(esfera(0.045, 24, 16), piel, s * 0.07, -0.04, 0.1, cab); mof.scale.set(1, 0.85, 0.75);   // mofletes
      const oreja = malla(esfera(0.034, 20, 14), piel, s * 0.14, -0.005, -0.005, cab); oreja.scale.set(0.42, 1, 0.75);
      const lado = malla(new THREE.SphereGeometry(0.1, 28, 18, 0, Math.PI * 2, 0, Math.PI / 2), pelo, s * 0.088, 0.02, -0.055, cab);   // pelo corto bajo el casco
      lado.scale.set(0.7, 0.75, 1.0);
    }
    const nariz = malla(esfera(0.026, 24, 16), piel, 0, -0.012, 0.15, cab); nariz.scale.set(0.85, 1.15, 1.15);
    malla(esfera(0.018, 16, 12), piel, 0, -0.03, 0.158, cab);                                        // punta de la nariz
    this.ojos = [];
    for (const s of [-1, 1]) {
      const ojo = malla(esfera(0.021, 24, 16), mat(0xf7f4ee, { roughness: 0.25 }), s * 0.05, 0.03, 0.131, cab);
      malla(esfera(0.011, 16, 12), mat(0x4a3324, { roughness: 0.3 }), 0, 0, 0.015, ojo);               // iris
      malla(esfera(0.005, 10, 8), mat(0x080808, { roughness: 0.1 }), 0, 0, 0.022, ojo);
      const parpado = malla(new THREE.SphereGeometry(0.023, 20, 8, 0, Math.PI * 2, 0, Math.PI / 2), piel, 0, 0, 0, ojo);
      parpado.rotation.x = -0.35; ojo.userData.parpado = parpado; this.ojos.push(ojo);
      const ceja = malla(new THREE.CapsuleGeometry(0.0075, 0.038, 4, 10), pelo, s * 0.05, 0.063, 0.135, cab);
      ceja.rotation.set(0, 0, Math.PI / 2 - s * 0.14);
      const big = malla(new THREE.CapsuleGeometry(0.014, 0.045, 6, 12), pelo, s * 0.028, -0.06, 0.145, cab);  // bigote en dos mitades
      big.rotation.set(0.15, 0, Math.PI / 2 + s * 0.32);
    }
    this.boca = malla(esfera(0.026, 20, 12), mat(0x5a1f1a), 0, -0.092, 0.133, cab); this.boca.scale.set(1.3, 0.25, 0.6);
    // casco de obra con cresta y gafas de proteccion subidas
    const cascoMat = mat(CASCO, { roughness: 0.32, side: THREE.DoubleSide });   // se ve tambien desde abajo
    const casco = malla(new THREE.SphereGeometry(0.16, 48, 20, 0, Math.PI * 2, 0, Math.PI / 2), cascoMat, 0, 0.045, -0.005, cab);
    casco.scale.set(1.02, 0.98, 1.06);
    const visera = malla(torno([[0.17, 0], [0.19, 0.004], [0.176, 0.014]], 56), cascoMat, 0, 0.04, 0.012, cab); visera.scale.z = 1.1;
    const cresta = malla(new THREE.CapsuleGeometry(0.014, 0.18, 6, 12), cascoMat, 0, 0.198, -0.005, cab); cresta.rotation.x = Math.PI / 2;
    const banda = malla(new THREE.TorusGeometry(0.152, 0.011, 8, 48), mat(0x2a2a2a), 0, 0.08, 0, cab); banda.rotation.x = Math.PI / 2;
    for (const s of [-1, 1]) {
      const g = malla(new THREE.CylinderGeometry(0.033, 0.033, 0.018, 24), mat(0x9fd3ff, { metalness: 0.2, roughness: 0.05, transparent: true, opacity: 0.75 }), s * 0.052, 0.112, 0.128, cab);
      g.rotation.x = Math.PI / 2 - 0.5;
    }

    // brazos: pivote en el hombro, cuelgan hacia -y; manga torneada, banda reflectante y guante con dedos
    const brazo = (s) => {
      const piv = new THREE.Group(); piv.position.set(s * 0.29, 0.6, 0); this.tronco.add(piv);
      const hombro = malla(esfera(0.082, 28, 20), mono, 0, -0.005, 0, piv); hombro.scale.set(1, 0.9, 0.95);
      malla(torno([[0, 0], [0.044, 0], [0.05, 0.04], [0.057, 0.16], [0.06, 0.23], [0.066, 0.3], [0.074, 0.42], [0.072, 0.48], [0, 0.5]], 36),
        mono, 0, -0.5, 0, piv);
      const b = malla(new THREE.TorusGeometry(0.056, 0.008, 8, 32), refl, 0, -0.36, 0, piv); b.rotation.x = Math.PI / 2;
      const mano = new THREE.Group(); mano.position.y = -0.52; piv.add(mano);
      const g = mat(GUANTE, { roughness: 0.75 });
      malla(torno([[0.046, 0], [0.05, 0.03], [0, 0.035]], 24), g, 0, -0.01, 0, mano);                 // puno del guante
      const palma = malla(esfera(0.04, 24, 18), g, 0, -0.035, 0.004, mano); palma.scale.set(1.05, 1.15, 0.62);
      for (let i = 0; i < 4; i++) {                                // dedos curvados hacia la palma (+z)
        const d = malla(new THREE.CapsuleGeometry(0.0115, 0.035, 4, 10), g, -0.027 + i * 0.018, -0.078, 0.014, mano);
        d.rotation.x = 0.75;
      }
      const pulgar = malla(new THREE.CapsuleGeometry(0.012, 0.03, 4, 10), g, s * -0.04, -0.04, 0.026, mano);
      pulgar.rotation.set(0.6, 0, s * 0.7);
      return { piv, mano };
    };
    this.der = brazo(-1); this.izq = brazo(1);
    // puntero laser en la mano derecha (apunta a lo largo de -y del brazo)
    malla(new THREE.CylinderGeometry(0.011, 0.012, 0.15, 16), mat(0x3a3d42, { metalness: 0.8, roughness: 0.3 }), 0, -0.07, 0.03, this.der.mano);
    this.punta = new THREE.Object3D(); this.punta.position.set(0, -0.15, 0.03); this.der.mano.add(this.punta);
    this.led = malla(new THREE.SphereGeometry(0.008, 10, 8), new THREE.MeshBasicMaterial({ color: 0x551111 }), 0, -0.147, 0.03, this.der.mano);
    // taza de cafe en la izquierda
    const loza = mat(0xf6f3ea, { roughness: 0.35 });
    const taza = malla(torno([[0, 0], [0.035, 0], [0.039, 0.01], [0.042, 0.1], [0.038, 0.1], [0.035, 0.012], [0, 0.012]], 32), loza, 0, -0.08, 0.06, this.izq.mano);
    const asa = malla(new THREE.TorusGeometry(0.024, 0.007, 10, 20), loza, 0.044, -0.03, 0.06, this.izq.mano); asa.rotation.y = Math.PI / 2;
    malla(new THREE.CylinderGeometry(0.037, 0.037, 0.004, 24), mat(0x3b2416, { roughness: 0.2 }), 0, 0.01, 0.06, this.izq.mano);   // cafe
    this.taza = taza;
    // estado de animacion
    this.t = Math.random() * 10; this.parpadeo = 3; this.sorbo = 6; this.bostezo = 14;
    this.qDer = new THREE.Quaternion(); this.qCab = new THREE.Quaternion(); this.yaw = 0;
    this._reposoBrazos();
  }

  _reposoBrazos() {
    this.der.piv.rotation.set(-0.55, 0, -0.12); this.izq.piv.rotation.set(-0.75, 0, 0.18);
    this.qDer.copy(this.der.piv.quaternion);
  }

  // objetivo: Vector3 en marco ROBOT (o null); raiz: el grupo del robot; peligro 0..1
  actualizar(dt, objetivo, raiz, peligro) {
    this.t += dt;
    const k = 1 - Math.exp(-dt * 7);
    // respiracion (mas rapida con el material fuera del blindaje) y botecito de nervios
    const resp = Math.sin(this.t * (1.6 + peligro * 4)) * (0.01 + peligro * 0.008);
    this.tronco.scale.set(1 + resp, 1 - resp * 0.4, 1 + resp);
    this.cuerpo.position.z = peligro * Math.abs(Math.sin(this.t * 9)) * 0.012;
    // peso que se balancea un poco de un pie a otro
    this.tronco.rotation.z = Math.sin(this.t * 0.7) * 0.02;
    // parpadeo
    this.parpadeo -= dt;
    const cerrado = this.parpadeo < 0.12;
    if (this.parpadeo < 0) this.parpadeo = 2 + Math.random() * 3.5;
    this.ojos.forEach((o) => (o.userData.parpado.rotation.x = cerrado ? 0.6 : -0.35 - peligro * 0.5));
    // bostezo de vez en cuando (si no pasa nada)
    this.bostezo -= dt;
    const bost = !objetivo && peligro < 0.1 && this.bostezo < 1.4 && this.bostezo > 0 ? Math.sin((1.4 - this.bostezo) / 1.4 * Math.PI) : 0;
    if (this.bostezo < 0) this.bostezo = 12 + Math.random() * 10;
    this.boca.scale.y = 0.25 + bost * 1.6 + peligro * 0.5;
    // brazo derecho: apunta al objetivo con el puntero
    const objW = objetivo ? raiz.localToWorld(objetivo.clone()) : null;
    if (objW) {
      const p = this.der.piv.parent.worldToLocal(objW.clone()).sub(this.der.piv.position).normalize();
      const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, -1, 0), p);
      this.qDer.slerp(q, k);
      this.der.piv.quaternion.copy(this.qDer);
      this.led.material.color.setHex(0xff2a14);
    } else {
      const reposo = new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.55, 0, -0.12));
      this.qDer.slerp(reposo, k * 0.6); this.der.piv.quaternion.copy(this.qDer);
      this.led.material.color.setHex(0x551111);
    }
    // brazo izquierdo: sorbo de cafe cada pocos segundos cuando no apunta
    this.sorbo -= dt;
    const s = !objW && this.sorbo < 2 && this.sorbo > 0 ? Math.sin((2 - this.sorbo) / 2 * Math.PI) : 0;
    if (this.sorbo < 0) this.sorbo = 7 + Math.random() * 6;
    this.izq.piv.rotation.set(-0.75 - s * 1.55, 0, 0.18 + s * 0.25);
    this.izq.mano.rotation.x = s * 1.2;
    // cabeza: mira al laser o al robot
    const mira = objW || raiz.localToWorld(new THREE.Vector3(0.15, 0, 0.15));
    const prev = this.cabeza.quaternion.clone();
    this.cabeza.lookAt(mira); const q = this.cabeza.quaternion.clone();
    this.cabeza.quaternion.copy(prev).slerp(q, k);
    if (s > 0.3) this.cabeza.rotation.x -= s * 0.25;
  }

  emisor(raiz) {   // punta del puntero en marco robot
    return raiz.worldToLocal(this.punta.getWorldPosition(new THREE.Vector3()));
  }
}
