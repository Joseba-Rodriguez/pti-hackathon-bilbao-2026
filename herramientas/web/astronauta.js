// Astronauta del escenario lunar (personaje propio): traje blanco presurizado, mochila de soporte
// vital, casco con visor dorado y una herramienta laser en la mano derecha con la que marca el
// mineral que el rover debe recoger. Misma interfaz que Operario (grupo, cabeza, actualizar, emisor)
// para que la escena pueda usar uno u otro. Marco y-arriba (origen en el suelo, mira a +z).
import * as THREE from 'three';

const TELA = 0xeceae4, GRIS = 0x9aa0a6, OSCURO = 0x2b2f35, AZUL = 0x2d5fa8, ORO = 0xd9a441;

function mat(color, extra = {}) { return new THREE.MeshStandardMaterial({ color, roughness: 0.78, metalness: 0, ...extra }); }
function malla(geo, m, x = 0, y = 0, z = 0, padre) {
  const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; o.receiveShadow = true;
  if (padre) padre.add(o); return o;
}
const torno = (pts, seg = 48) => new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), seg);
const esfera = (r, ws = 32, hs = 24) => new THREE.SphereGeometry(r, ws, hs);
function aro(r, t, padre, y, m) { const a = malla(new THREE.TorusGeometry(r, t, 10, 48), m, 0, y, 0, padre); a.rotation.x = Math.PI / 2; return a; }

function placaNombre(texto) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const x = c.getContext('2d');
  x.fillStyle = '#e9e7e1'; x.fillRect(0, 0, 256, 64); x.fillStyle = '#2d5fa8'; x.fillRect(0, 0, 256, 14);
  x.fillStyle = '#fff'; x.font = '700 10px Inter, Arial'; x.fillText('PTI · EVA-1 · ROVER SO-101', 8, 11);
  x.fillStyle = '#111'; let px = 28; do { x.font = `700 ${px}px Inter, Arial`; } while (x.measureText(texto).width > 238 && --px > 10);
  x.fillText(texto, 8, 48);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Astronauta {
  constructor(nombre = 'AITOR ETXALAR') {
    this.grupo = new THREE.Group();
    const cuerpo = this.cuerpo = new THREE.Group(); cuerpo.rotation.x = Math.PI / 2; this.grupo.add(cuerpo);
    const tela = mat(TELA), gris = mat(GRIS, { metalness: 0.55, roughness: 0.4 }), osc = mat(OSCURO, { roughness: 0.6 }),
      azul = mat(AZUL, { roughness: 0.55 });

    // piernas con fuelles en rodilla y botas lunares
    for (const s of [-1, 1]) {
      malla(torno([[0, 0], [0.085, 0], [0.09, 0.06], [0.098, 0.2], [0.096, 0.27], [0.11, 0.4], [0.125, 0.52], [0.122, 0.6], [0, 0.62]]),
        tela, s * 0.125, 0.12, 0, cuerpo);
      for (const y of [0.37, 0.39, 0.41]) { const a = aro(0.1, 0.008, cuerpo, y, tela); a.position.x = s * 0.125; }
      const a = aro(0.094, 0.012, cuerpo, 0.15, gris); a.position.x = s * 0.125;           // anillo de union con la bota
      malla(torno([[0, 0], [0.09, 0], [0.095, 0.05], [0.09, 0.15], [0, 0.155]], 32), tela, s * 0.125, 0.02, 0, cuerpo);
      const punta = malla(esfera(1, 28, 18), tela, s * 0.125, 0.06, 0.05, cuerpo); punta.scale.set(0.095, 0.065, 0.15);
      const suela = malla(esfera(1, 28, 12), osc, s * 0.125, 0.018, 0.04, cuerpo); suela.scale.set(0.1, 0.02, 0.165);
    }

    // torso rigido (HUT) con la unidad de control en el pecho y la mochila de soporte vital
    this.tronco = new THREE.Group(); this.tronco.position.y = 0.7; cuerpo.add(this.tronco);
    const torso = malla(torno([[0, -0.02], [0.2, -0.02], [0.25, 0.05], [0.275, 0.18], [0.28, 0.32], [0.285, 0.44],
      [0.28, 0.54], [0.25, 0.61], [0.17, 0.66], [0, 0.67]], 56), tela, 0, 0, 0, this.tronco);
    torso.scale.set(1.15, 1, 0.9);
    aro(0.27, 0.014, this.tronco, 0.02, gris).scale.set(1.15, 0.9, 1);                      // cintura
    const dcm = malla(new THREE.BoxGeometry(0.2, 0.11, 0.07), mat(0xd8d6d0, { roughness: 0.5 }), 0, 0.36, 0.25, this.tronco);
    dcm.rotation.x = 0.15;
    [[0xd23b2a, -0.06], [0xf2c500, -0.02], [0x32a852, 0.02], [0x2d5fa8, 0.06]].forEach(([c, x]) => {
      const b = malla(new THREE.CylinderGeometry(0.011, 0.011, 0.012, 16), mat(c, { roughness: 0.4 }), x, 0.0, 0.04, dcm); b.rotation.x = Math.PI / 2;
    });
    const placa = new THREE.Mesh(new THREE.PlaneGeometry(0.15, 0.0375), new THREE.MeshStandardMaterial({ map: placaNombre(nombre), roughness: 0.5 }));
    placa.position.set(0, 0.5, 0.232); placa.rotation.x = -0.32; this.tronco.add(placa);
    for (const s of [-1, 1]) { const f = malla(new THREE.BoxGeometry(0.035, 0.06, 0.01), azul, s * 0.2, 0.47, 0.18, this.tronco); f.rotation.y = s * 0.6; }
    const mochila = malla(new THREE.BoxGeometry(0.52, 0.62, 0.24), tela, 0, 0.33, -0.33, this.tronco);
    mochila.geometry.translate(0, 0, 0);
    const tapa = malla(new THREE.CylinderGeometry(0.12, 0.12, 0.52, 32, 1, false, 0, Math.PI), tela, 0, 0.64, -0.33, this.tronco);
    tapa.rotation.z = Math.PI / 2; tapa.scale.set(1, 1, 1);
    malla(new THREE.BoxGeometry(0.4, 0.1, 0.03), gris, 0, 0.1, -0.46, this.tronco);
    const antena = malla(new THREE.CylinderGeometry(0.004, 0.004, 0.3, 8), gris, 0.2, 0.85, -0.38, this.tronco); antena.rotation.z = -0.1;
    // mangueras de la mochila a la unidad del pecho
    for (const s of [-1, 1]) {
      const curva = new THREE.CatmullRomCurve3([new THREE.Vector3(s * 0.08, 0.33, 0.27), new THREE.Vector3(s * 0.22, 0.25, 0.26),
        new THREE.Vector3(s * 0.3, 0.2, 0.05), new THREE.Vector3(s * 0.28, 0.3, -0.2)]);
      malla(new THREE.TubeGeometry(curva, 24, 0.012, 8), s > 0 ? azul : mat(0xd23b2a, { roughness: 0.5 }), 0, 0, 0, this.tronco);
    }

    // casco: anillo de cuello, burbuja, carcasa protectora, visor dorado y luces
    const cab = this.cabeza = new THREE.Group(); cab.position.set(0, 0.84, 0.02); this.tronco.add(cab);
    aro(0.16, 0.022, this.tronco, 0.665, gris);
    const carcasa = malla(new THREE.SphereGeometry(0.205, 48, 32, 0, Math.PI * 2, 0, Math.PI * 0.62), tela, 0, 0.0, 0, cab);
    carcasa.rotation.x = -0.25;
    this.visor = malla(new THREE.SphereGeometry(0.196, 48, 32, Math.PI * 0.12, Math.PI * 0.76, Math.PI * 0.22, Math.PI * 0.5),
      new THREE.MeshPhysicalMaterial({ color: ORO, metalness: 1, roughness: 0.07, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 2.2 }), 0, -0.01, 0.006, cab);
    this.visor.rotation.y = 0;
    malla(new THREE.SphereGeometry(0.188, 32, 24), mat(0x0c0d10, { roughness: 0.3 }), 0, -0.01, 0, cab);   // interior oscuro
    for (const s of [-1, 1]) {
      const caja = malla(new THREE.BoxGeometry(0.045, 0.05, 0.08), tela, s * 0.2, 0.06, 0.02, cab);
      const foco = malla(new THREE.CylinderGeometry(0.016, 0.016, 0.01, 20), new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0xfff3d6, emissiveIntensity: 1.6 }), 0, 0, 0.042, caja);
      foco.rotation.x = Math.PI / 2;
    }

    // brazos: hombro rigido, manga con fuelles, guantes oscuros con manguito
    const brazo = (s) => {
      const piv = new THREE.Group(); piv.position.set(s * 0.33, 0.56, 0); this.tronco.add(piv);
      aro(0.085, 0.016, piv, 0.0, gris).rotation.set(0, 0, Math.PI / 2);
      malla(esfera(0.095, 28, 20), tela, 0, -0.03, 0, piv);
      malla(torno([[0, 0], [0.058, 0], [0.065, 0.05], [0.07, 0.17], [0.072, 0.24], [0.082, 0.32], [0.09, 0.44], [0.085, 0.5], [0, 0.52]], 36),
        tela, 0, -0.52, 0, piv);
      for (const y of [-0.25, -0.27, -0.29]) aro(0.075, 0.007, piv, y, tela);
      aro(0.064, 0.012, piv, -0.47, gris);                                                  // union con el guante
      const mano = new THREE.Group(); mano.position.y = -0.54; piv.add(mano);
      const guante = mat(0x3a3f47, { roughness: 0.7 });
      malla(torno([[0.068, 0.0], [0.06, 0.04], [0.058, 0.07]], 28), azul, 0, -0.03, 0, mano);   // manguito
      const palma = malla(esfera(0.045, 24, 18), guante, 0, -0.045, 0.004, mano); palma.scale.set(1.08, 1.15, 0.68);
      for (let i = 0; i < 4; i++) {
        const d = malla(new THREE.CapsuleGeometry(0.013, 0.036, 4, 10), guante, -0.03 + i * 0.02, -0.09, 0.016, mano); d.rotation.x = 0.8;
      }
      const pulgar = malla(new THREE.CapsuleGeometry(0.014, 0.03, 4, 10), guante, s * -0.045, -0.05, 0.03, mano); pulgar.rotation.set(0.6, 0, s * 0.7);
      return { piv, mano };
    };
    this.der = brazo(-1); this.izq = brazo(1);
    // herramienta laser en la derecha (apunta a lo largo de -y del brazo)
    const metal = mat(0x50555c, { metalness: 0.85, roughness: 0.3 });
    malla(new THREE.BoxGeometry(0.05, 0.16, 0.05), mat(0xd8d6d0, { roughness: 0.5 }), 0, -0.09, 0.04, this.der.mano);
    malla(new THREE.CylinderGeometry(0.014, 0.018, 0.06, 16), metal, 0, -0.2, 0.04, this.der.mano);
    this.punta = new THREE.Object3D(); this.punta.position.set(0, -0.235, 0.04); this.der.mano.add(this.punta);
    this.led = malla(new THREE.SphereGeometry(0.01, 10, 8), new THREE.MeshBasicMaterial({ color: 0x551111 }), 0, -0.232, 0.04, this.der.mano);
    // pantalla de muneca en la izquierda (la consulta de vez en cuando)
    malla(new THREE.BoxGeometry(0.07, 0.05, 0.02), mat(0x1b1e22, { emissive: 0x2bd4ff, emissiveIntensity: 0.25 }), 0, 0.03, 0.07, this.izq.mano);

    this.t = Math.random() * 10; this.consulta = 8;
    this.qDer = new THREE.Quaternion();
    this.der.piv.rotation.set(-0.45, 0, -0.18); this.izq.piv.rotation.set(-0.3, 0, 0.22);
    this.qDer.copy(this.der.piv.quaternion);
  }

  // objetivo: Vector3 en marco ROBOT (o null); raiz: el grupo del robot; peligro 0..1 (aqui: mineral en la pinza)
  actualizar(dt, objetivo, raiz, peligro) {
    this.t += dt;
    const k = 1 - Math.exp(-dt * 5);                               // gestos mas lentos: traje presurizado
    // baja gravedad: balanceo suave y respiracion dentro del traje
    this.cuerpo.position.z = Math.abs(Math.sin(this.t * 0.9)) * 0.006 + peligro * Math.abs(Math.sin(this.t * 3)) * 0.01;
    this.tronco.rotation.z = Math.sin(this.t * 0.6) * 0.025;
    this.tronco.scale.y = 1 + Math.sin(this.t * 1.4) * 0.004;
    const objW = objetivo ? raiz.localToWorld(objetivo.clone()) : null;
    if (objW) {
      const p = this.der.piv.parent.worldToLocal(objW.clone()).sub(this.der.piv.position).normalize();
      this.qDer.slerp(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, -1, 0), p), k);
      this.led.material.color.setHex(0xff2a14);
    } else {
      this.qDer.slerp(new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.45, 0, -0.18)), k * 0.6);
      this.led.material.color.setHex(0x551111);
    }
    this.der.piv.quaternion.copy(this.qDer);
    // consulta la pantalla de la muneca cuando no apunta
    this.consulta -= dt;
    const c = !objW && this.consulta < 2.5 && this.consulta > 0 ? Math.sin((2.5 - this.consulta) / 2.5 * Math.PI) : 0;
    if (this.consulta < 0) this.consulta = 9 + Math.random() * 6;
    this.izq.piv.rotation.set(-0.3 - c * 1.3, -c * 0.5, 0.22 - c * 0.5);
    // el casco gira poco (va unido al torso): mira a medias hacia el objetivo o hacia el rover
    const mira = objW || raiz.localToWorld(new THREE.Vector3(0.2, 0, 0.1));
    const prev = this.cabeza.quaternion.clone();
    this.cabeza.lookAt(mira);
    const q = new THREE.Quaternion().slerp(this.cabeza.quaternion, 0.35);
    if (c > 0.3) q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(c * 0.3, 0, 0)));
    this.cabeza.quaternion.copy(prev).slerp(q, k);
  }

  emisor(raiz) { return raiz.worldToLocal(this.punta.getWorldPosition(new THREE.Vector3())); }
}
