// PTI Hot Cell · interfaz de operador. Datos de gemelo.py (/estado ~30 Hz); escena 3D en escena.js.
import { Celda } from './escena.js';
import { activarPaneles, restablecerPaneles } from './paneles.js';
activarPaneles();

const $ = (id) => document.getElementById(id);
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const num = (v, d = 1) => (Math.abs(v) < 0.5 * 10 ** -d ? 0 : v).toLocaleString('es-ES', { minimumFractionDigits: d, maximumFractionDigits: d });
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

// ============================================================ narrador (voz neuronal pregrabada)
const narrador = {
  activo: true, audio: null, frases: {}, cola: [],
  async cargar() {
    try { this.frases = (await (await fetch('/web/voz/frases.json')).json()).frases; } catch { this.frases = {}; }
  },
  decir(clave, { cola = false } = {}) {
    const texto = this.frases[clave] || clave;
    if (cola && this.hablando()) { this.cola.push(clave); return; }
    this.cola = [];
    this._parar();
    $('subTxt').textContent = texto;
    $('subtitulo').classList.remove('callado');
    if (!this.activo) return;
    const a = new Audio(`/web/voz/${clave}.mp3`);
    a.onplay = () => document.body.classList.add('hablando');
    a.onended = a.onerror = () => { document.body.classList.remove('hablando'); this.audio = null; this._siguiente(); };
    a.play().catch(() => this._sintetica(texto));
    this.audio = a;
  },
  hablando() { return !!this.audio || speechSynthesis.speaking; },
  _siguiente() { const k = this.cola.shift(); if (k) setTimeout(() => this.decir(k), 250); else $('subtitulo').classList.add('callado'); },
  _parar() { if (this.audio) { this.audio.onended = null; this.audio.pause(); this.audio = null; } speechSynthesis.cancel(); document.body.classList.remove('hablando'); },
  _sintetica(t) {                                    // respaldo: la mejor voz es-ES del navegador
    const vs = speechSynthesis.getVoices().filter((v) => v.lang === 'es-ES' || v.lang === 'es_ES');
    const v = vs.find((v) => /alvaro/i.test(v.name)) || vs.find((v) => /natural|online/i.test(v.name)) || vs[0];
    const u = new SpeechSynthesisUtterance(t); u.lang = 'es-ES'; if (v) u.voice = v; u.rate = 0.98;
    u.onstart = () => document.body.classList.add('hablando');
    u.onend = () => { document.body.classList.remove('hablando'); this._siguiente(); };
    speechSynthesis.speak(u);
  },
  alternar() { this.activo = !this.activo; if (!this.activo) this._parar(); $('bVoz').classList.toggle('on', this.activo); },
};

// ============================================================ sonido (Geiger y avisos)
let audio = null, geiger = false;
const activarAudio = () => { if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)(); };
function clic() {
  if (!audio || !geiger) return;
  const b = audio.createBuffer(1, 240, audio.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / 16);
  const s = audio.createBufferSource(), g = audio.createGain(); g.gain.value = 0.35; s.buffer = b; s.connect(g).connect(audio.destination); s.start();
}
function aviso(notas = [880, 1320]) {                // dos tonos suaves, estilo sistema
  if (!audio) return;
  notas.forEach((f, i) => {
    const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime + i * 0.11;
    o.type = 'sine'; o.frequency.value = f;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.07, t + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
    o.connect(g).connect(audio.destination); o.start(t); o.stop(t + 0.52);
  });
}

// ============================================================ escena
const celda = new Celda($('vista'));
let escenaLista = false;
async function cargarEscena() {
  const esc = await (await fetch('/escena', { cache: 'no-store' })).json();
  await celda.cargar(esc);
  escenaLista = true;
}

// ============================================================ estado del robot
let est = {}, pidiendo = false;
async function leer() {
  if (pidiendo) return; pidiendo = true;
  try { est = await (await fetch('/estado', { cache: 'no-store' })).json(); } catch { est = {}; }
  pidiendo = false;
}
setInterval(leer, 33);

// fases: 0 apunta · 1 coge · 2 traslada · 3 deja · -1 en espera
function faseDe(e) {
  if (!e.vivo) return -1;
  if (e.suelta_hace != null && e.suelta_hace < 3) return 3;
  if (e.cogido) return 2;
  if (e.pinza != null && e.pinza > 27) return 1;        // pinza abierta: va a por el contenedor
  if (e.laser) return 0;
  return -1;
}
const FASES = [
  { sup: 'Fase 1', t: 'Objetivo marcado', sub: 'Orden recibida desde fuera de la celda', voz: 'fase0', clase: '' },
  { sup: 'Fase 2', t: 'Extracción', sub: 'El contenedor sale del almacén blindado', voz: 'fase1', clase: 'rojo' },
  { sup: 'Fase 3', t: 'En tránsito', sub: 'El brazo sigue el punto del láser', voz: 'fase2', clase: 'rojo' },
  { sup: 'Fase 4', t: 'Depósito', sub: 'Contenedor liberado en la zona de análisis', voz: 'fase3', clase: 'verde' },
];
const NOMBRES = ['Apunta', 'Coge', 'Traslada', 'Deja'];

let tit;
function titular({ sup, t, sub, clase = '' }) {
  const el = $('titular'); el.className = 'ver ' + clase;
  $('tSup').textContent = sup; $('tT').textContent = t; $('tSub').textContent = sub;
  clearTimeout(tit); tit = setTimeout(() => (el.className = clase), 2600);
}

let prevVivo = false, faseVista = -1, faseDesde = 0, anunciadas = new Set(), esperaDesde = 0;
let prevMovs = null, tInicio = null, tFin = null, dosisMano = 0;

function pintarEstado(ahora) {
  const e = est, vivo = !!e.vivo, movs = e.movimientos ?? 0;
  document.body.classList.toggle('enlace', vivo);
  // enlace
  const pe = $('pEnlace');
  pe.className = 'pastilla ' + (vivo ? 'vivo' : 'aviso');
  pe.querySelector('span').textContent = vivo ? (e.demo ? 'Reproducción' : 'En directo') : 'Sin señal';
  $('camTxt').textContent = vivo ? (e.demo ? 'Grabación' : 'En directo') : 'Real';
  if (vivo && !prevVivo && entrado) { titular({ sup: 'Enlace establecido', t: 'Robot en línea', sub: 'Telemetría en directo' }); narrador.decir('enlace'); aviso([660, 990]); evento('robot', '<b>Telemetría del brazo</b> en directo'); }
  if (!vivo && prevVivo && entrado) { narrador.decir('enlace_perdido'); evento('aviso', 'Telemetría del brazo perdida'); }
  prevVivo = vivo;
  // celda
  const pc = $('pCelda');
  pc.className = 'pastilla ' + (e.cogido ? 'peligro' : 'ok');
  pc.querySelector('span').textContent = e.cogido ? 'Material fuera del blindaje' : 'Celda sellada';
  document.body.classList.toggle('peligro', !!e.cogido);

  // fase (con histeresis de 0,35 s para no anunciar parpadeos)
  const f = faseDe(e);
  if (f !== faseVista) { faseVista = f; faseDesde = ahora; }
  const estable = ahora - faseDesde > 350;
  if (f === -1) { if (!esperaDesde) esperaDesde = ahora; if (ahora - esperaDesde > 4000) { anunciadas.clear(); if (tFin) tInicio = null; } } else esperaDesde = 0;
  if (estable && f >= 0 && !anunciadas.has(f) && entrado) {
    anunciadas.add(f);
    titular(FASES[f]); narrador.decir(FASES[f].voz); aviso(f === 3 ? [990, 1480] : f === 1 ? [740, 980] : [880, 1320]);
  }
  if (f >= 0 && f <= 2 && !tInicio) { tInicio = Date.now(); tFin = null; dosisMano = 0; }
  const pasos = $('pasos').children;
  for (let i = 0; i < 4; i++) {
    pasos[i].classList.toggle('act', i === f);
    pasos[i].classList.toggle('hecho', f > i);
  }
  $('faseTxt').textContent = f >= 0 ? NOMBRES[f] : (vivo ? 'En espera' : 'Sin enlace');
  if (f === -1 && !narrador.hablando() && !narrador.cola.length)
    $('subTxt').textContent = vivo ? (narrador.frases.reposo || 'Brazo en reposo.') : 'Esperando señal del robot';

  // traslado completado
  if (prevMovs !== null && movs > prevMovs) {
    tFin = Date.now(); anunciadas.add(3);
    setTimeout(mostrarResumen, 2200);
  }
  prevMovs = movs;
  const t = tInicio ? ((tFin || Date.now()) - tInicio) / 1000 : 0;
  $('pT').querySelector('span').textContent = 'T+' + fmt(t);
  $('lotes').textContent = `${movs} ${movs === 1 ? 'lote' : 'lotes'}`;

  // laser: aviso en el registro cuando aparece (con la celda de la bandeja)
  if (e.laser_m && !laserVisto && entrado) {
    const c = celda.celdaDe ? celda.celdaDe(e.laser_m[0], e.laser_m[1]) : null;
    evento('laser', `Láser detectado${c ? ` en la <b>celda ${c}</b>` : ''}`);
  }
  if (e.laser_m) { laserVisto = true; laserOff = ahora; } else if (ahora - laserOff > 2500) laserVisto = false;
  pintarRegistro();

  // telemetria
  const q = e.q || {};
  $('telem').innerHTML = ART.map(([k, n]) => {
    const v = q[k];
    if (k === 'gripper') {
      const w = v == null ? 0 : Math.max(0, Math.min(100, v));
      return `<div class="art pinza"><span>${n}</span><div class="b"><i style="left:0;width:${w}%"></i></div><em>${v == null ? '—' : num(v, 0) + ' %'}</em></div>`;
    }
    const c = v == null ? 0 : Math.max(-110, Math.min(110, v)) / 110 * 50;
    return `<div class="art"><span>${n}</span><div class="b"><i style="left:${50 + Math.min(0, c)}%;width:${Math.abs(c)}%"></i></div><em>${v == null ? '—' : num(v, 1) + '°'}</em></div>`;
  }).join('');
}
// ============================================================ registro visual (linea de tiempo)
let laserVisto = false, laserOff = 0;
const eventosUI = [];
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const hora = () => new Date().toLocaleTimeString('es-ES');
function evento(tipo, html) { eventosUI.push({ h: hora(), tipo, html }); if (eventosUI.length > 80) eventosUI.shift(); }
function pintarRegistro() {
  const delRobot = (est.registro || []).map((s) => {
    const h = s.slice(0, 8), t = s.slice(8).trim();
    if (/^COGE/.test(t)) return { h, tipo: 'coge', html: `<b>Coge</b> el contenedor · ${esc(t.replace(/^COGE contenedor en /, ''))}` };
    if (/^DEJA/.test(t)) return { h, tipo: 'deja', html: `<b>Deja</b> el contenedor · ${esc(t.replace(/^DEJA en /, ''))}` };
    return { h, tipo: 'sistema', html: esc(t) };
  });
  const todos = [...delRobot, ...eventosUI].sort((a, b) => (a.h < b.h ? 1 : a.h > b.h ? -1 : 0)).slice(0, 50);
  const html = todos.length
    ? todos.map((e) => `<div class="ev ${e.tipo}"><time>${e.h}</time><span class="nodo"></span><p>${e.html}</p></div>`).join('')
    : '<div class="vacio">Sin eventos todavía.</div>';
  if (pintarRegistro.ultimo !== html) { $('registro').innerHTML = html; pintarRegistro.ultimo = html; }
}

const ART = [['shoulder_pan', 'Base'], ['shoulder_lift', 'Hombro'], ['elbow_flex', 'Codo'], ['wrist_flex', 'Muñeca'], ['wrist_roll', 'Giro muñeca'], ['gripper', 'Pinza']];

function mostrarResumen() {
  const t = tInicio && tFin ? (tFin - tInicio) / 1000 : 0, p = est.punta_cm;
  $('rTiempo').textContent = fmt(t) + ' min';
  $('rDestino').textContent = p ? `(${num(p[0], 0)}, ${num(p[1], 0)}) cm` : '—';
  $('rEvitada').textContent = num(dosisMano, 1) + ' µSv';
  $('resSub').textContent = 'Lote U-235 · #U-0347 · ' + new Date().toLocaleTimeString('es-ES');
  $('resumen').classList.remove('oculta');
  narrador.decir('resumen', { cola: true });
}
$('btnResumen').onclick = () => $('resumen').classList.add('oculta');

// ============================================================ radiacion (simulada, ilustrativa)
let tasa = 0.12, hist = [], acum = 0;
function tasaObjetivo() {
  if (est.cogido) return 2400;                                  // µSv/h junto al contenedor fuera del blindaje
  if (est.movimientos > 0) return 380;                          // depositado sin blindaje en la zona de análisis
  return 0.12;                                                  // fondo con el contenedor en el almacén
}
function radiacion(dt) {
  const obj = tasaObjetivo();
  tasa *= Math.exp(Math.log(obj / tasa) * Math.min(1, dt * 1.6));
  const cpm = tasa * 260 + 25;
  const lambda = cpm / 60 * dt, L = Math.exp(-Math.min(lambda, 30)); let n = 0, p = 1;
  do { n++; p *= Math.random(); } while (p > L); n--;
  for (let i = 0; i < Math.min(n, 5); i++) setTimeout(clic, Math.random() * dt * 1000);
  if (est.cogido) dosisMano += tasa * dt / 3600;
  acum += dt;
  if (acum < 0.2) return; acum = 0;
  const v = tasa * (0.92 + Math.random() * 0.16);
  const caja = document.querySelector('.rad-num');
  if (v >= 1000) { $('tasa').textContent = num(v / 1000, 2); $('tasaU').textContent = 'mSv/h'; }
  else { $('tasa').textContent = num(v, v < 10 ? 2 : 0); $('tasaU').textContent = 'µSv/h'; }
  caja.classList.toggle('alto', v > 10 && v < 1000); caja.classList.toggle('muy', v >= 1000);
  $('cpm').textContent = Math.round(cpm * (0.9 + Math.random() * 0.2)).toLocaleString('es-ES');
  const frac = Math.max(0.03, Math.min(1, (Math.log10(v) + 1) / 5));   // 0,1 µSv/h .. 10 mSv/h
  $('medidor').style.width = (frac * 100) + '%';
  $('medidor').style.setProperty('--ancho-medidor', $('medidor').parentElement.clientWidth + 'px');
  $('dosisMano').textContent = num(dosisMano, 1) + ' µSv';
  hist.push(frac); if (hist.length > 150) hist.shift();
  const c = $('hist'), x = c.getContext('2d'), W = c.width, H = c.height;
  x.clearRect(0, 0, W, H);
  const gr = x.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, 'rgba(198,255,61,.35)'); gr.addColorStop(1, 'rgba(198,255,61,0)');
  x.beginPath(); hist.forEach((f, i) => { const X = i / 149 * W, Y = H - f * (H - 6) - 2; i ? x.lineTo(X, Y) : x.moveTo(X, Y); });
  x.strokeStyle = est.cogido ? '#ff453a' : '#c6ff3d'; x.lineWidth = 2.5; x.stroke();
  x.lineTo((hist.length - 1) / 149 * W, H); x.lineTo(0, H); x.fillStyle = gr; x.fill();
}

// ============================================================ etiquetas 3D
function etiqueta(el, p, visible) {
  if (!visible || !p) { el.classList.remove('ver'); return; }
  el.classList.add('ver'); el.style.transform = `translate(${p.x - 5}px, ${p.y - 5}px)`;
}
function etiquetas() {
  if (!escenaLista) return;
  const v = est.vaso;
  etiqueta($('etqVaso'), v && celda.aPantalla(v[0], v[1], v[2] + 0.045), !!v);
  $('etqVasoEstado').textContent = est.cogido ? 'Fuera de blindaje · en tránsito' : (est.movimientos ? 'En zona de análisis' : 'En almacén blindado');
  const l = est.laser_m;
  etiqueta($('etqLaser'), l && celda.aPantalla(l[0], l[1], 0.002), !!l);
  const o = celda.posOperario && celda.posOperario();
  etiqueta($('etqOper'), o && celda.aPantalla(o.x, o.y, o.z + 0.28), !!o);
  if (l) { const c = celda.celdaDe(l[0], l[1]); $('etqLaserXY').textContent = (c ? `Celda ${c} · ` : 'Fuera de bandeja · ') + `x ${num(l[0] * 100, 0)} · y ${num(l[1] * 100, 0)} cm`; }
}

// ============================================================ bucle principal
let ultimo = performance.now();
function bucle(ahora) {
  const dt = Math.min(0.1, (ahora - ultimo) / 1000); ultimo = ahora;
  celda.actualizar(est, dt);
  pintarEstado(ahora);
  radiacion(dt);
  etiquetas();
  requestAnimationFrame(bucle);
}
requestAnimationFrame(bucle);
setInterval(() => { $('reloj').textContent = new Date().toLocaleTimeString('es-ES'); }, 500);

// datos verificables que van rotando en la orden de trabajo
const DATOS = [
  'El uranio-235 tiene una semivida de unos 704 millones de años.',
  'Límite de dosis profesional en la UE: 20 mSv al año (Directiva 2013/59/Euratom).',
  'Hoy estas tareas se hacen con telemanipuladores maestro-esclavo y operadores formados.',
  'PTI: un puntero láser y una política ACT aprendida por imitación con LeRobot.',
  'Entrenado con demostraciones humanas grabadas durante este hackathon.',
  'Radiación y material de esta pantalla: simulados. El contenedor real es un vaso vacío.',
];
let iDato = 0;
function rotarDato() { const el = $('datoRot'); el.style.opacity = 0; setTimeout(() => { el.textContent = DATOS[iDato++ % DATOS.length]; el.style.opacity = 1; }, 450); }
rotarDato(); setInterval(rotarDato, 9000);

// ============================================================ vistas de camara
document.querySelectorAll('#vistas button').forEach((b) => b.onclick = () => {
  document.querySelectorAll('#vistas button').forEach((x) => x.classList.toggle('on', x === b));
  celda.vista(b.dataset.v);
});

// ============================================================ arranque
let entrado = false;
(async function arrancar() {
  const directo = location.search.includes('directo');
  const pasos = [...document.querySelectorAll('#arrPasos li')];
  const marca = async (i, tarea) => { pasos[i].classList.add('cargando'); await Promise.all([tarea, esperar(directo ? 0 : 420)]); pasos[i].classList.remove('cargando'); pasos[i].classList.add('ok'); };
  await narrador.cargar();
  await marca(0, leer());
  await marca(1, esperar(0));
  await marca(2, fetch('/modelos').catch(() => null));
  await marca(3, cargarEscena().catch((e) => console.error('escena', e)));
  await marca(4, esperar(0));
  $('btnEntrar').disabled = false;
  if (directo) entrar(false);
  const v = new URLSearchParams(location.search).get('vista');      // ?vista=cenital|lateral|pinza
  if (v && celda) { celda.vista(v, true); document.querySelectorAll('#vistas button').forEach((x) => x.classList.toggle('on', x.dataset.v === v)); }
})();
function entrar(conVoz = true) {
  $('arranque').classList.add('oculta');
  activarAudio(); entrado = true; prevVivo = !!est.vivo;
  if (conVoz) narrador.decir('arranque');
}
$('btnEntrar').onclick = () => entrar(true);

// ============================================================ botones de la barra
$('bVoz').onclick = () => narrador.alternar();
$('bGeiger').onclick = () => { activarAudio(); geiger = !geiger; $('bGeiger').classList.toggle('on', geiger); };
$('bControl').onclick = () => $('ctl').classList.toggle('abierto');
$('ctlCerrar').onclick = () => $('ctl').classList.remove('abierto');
$('btnIntro').onclick = () => narrador.decir('intro');
function reiniciar() {
  fetch('/tecla?k=reiniciar'); tInicio = null; tFin = null; dosisMano = 0; anunciadas.clear(); prevMovs = null;
  $('resumen').classList.add('oculta');
}
$('btnReiniciar').onclick = reiniciar;
$('btnPaneles').onclick = restablecerPaneles;

// ============================================================ panel de control (lanza comandos via gemelo.py)
let tToast;
function toast(texto, ms = 7000) {
  $('toast').textContent = texto; $('toast').classList.add('ver');
  clearTimeout(tToast); tToast = setTimeout(() => $('toast').classList.remove('ver'), ms);
}
$('toast').onclick = () => $('toast').classList.remove('ver');
async function accion(x, extra = {}) {
  try {
    const r = await (await fetch('/accion?' + new URLSearchParams({ x, ...extra }), { cache: 'no-store' })).json();
    let txt = r.resultado === 'ok' ? '' : r.resultado;
    if (txt.startsWith('GPU_LLENA:')) { txt = txt.slice(10); evento('aviso', '<b>No se inicia:</b> GPU ocupada por otros programas'); }
    $('msg').textContent = txt;
    if (txt) toast(txt, 12000);
  } catch { $('msg').textContent = 'Sin conexión con gemelo.py'; toast('Sin conexión con gemelo.py'); }
  proceso();
}
document.querySelectorAll('[data-accion]').forEach((b) => b.onclick = () => {
  if (b.dataset.accion === 'parar') narrador.decir('parar');
  accion(b.dataset.accion);
});
$('btnParar').onclick = () => { narrador.decir('parar'); accion('parar'); };
$('ejCerrar').onclick = () => { ejOculta = ultimoP ? ultimoP.id : null; document.body.classList.remove('ejec'); };
$('seguro').onchange = () => { $('btnIniciar').disabled = !$('seguro').checked; };
$('btnIniciar').onclick = () => {
  if (!$('seguro').checked) { $('msg').textContent = 'Marca primero la casilla de seguridad.'; return; }
  const extra = { modelo: $('modelo').value, coef: $('coef').value, seg: $('seg').value, seguro: '1' };
  if ($('ignorarGpu').checked) extra.ignorar_gpu = '1';
  accion('probar', extra);
  $('seguro').checked = false; $('btnIniciar').disabled = true;
  reiniciar();
  evento('robot', `<b>Orden de inicio</b> · ${esc($('modelo').value.split('/').pop())}, ${esc($('seg').value)} s`);
  narrador.decir('iniciar');
};

// --- lectura de la salida de lerobot-rollout: etapas, velocidad y errores
const ETAPAS = [
  { ini: /Loading policy/, fin: /Policy loaded/, txt: 'Cargando el modelo' },
  { ini: /Connecting robot/, fin: /Robot connected/, txt: 'Conectando brazo y cámaras' },
  { ini: /control loop started/, fin: /Duration limit reached|control loop ended/, txt: 'El robot se mueve solo' },
  { ini: /Returning robot to initial position/, fin: /Disconnecting robot|Rollout finished/, txt: 'Volviendo a la posición inicial' },
  { ini: /\[fin: c/, fin: /\[fin: c/, txt: 'Fin' },
];
function analizar(p) {
  const r = { ini: Array(5).fill(null), fin: Array(5).fill(null), hzLog: null, hzFinal: null, infer: null, error: null, parando: false };
  (p.salida || []).forEach((l, i) => {
    const t = p.t ? p.t[i] : null;
    ETAPAS.forEach((e, k) => { if (r.ini[k] == null && e.ini.test(l)) r.ini[k] = t; if (r.fin[k] == null && e.fin.test(l)) r.fin[k] = t; });
    let m;
    if ((m = l.match(/running slower \(([\d.]+) Hz\)/))) r.hzLog = parseFloat(m[1]);
    if ((m = l.match(/effective cadence: ([\d.]+) Hz/))) r.hzFinal = parseFloat(m[1]);
    if ((m = l.match(/infer\s+mean\s+([\d.]+) ms/))) r.infer = parseFloat(m[1]);
    if (!r.error && /Traceback|Error:|Exception|Could not|could not/.test(l)) r.error = l;
    if (/\[PARANDO/.test(l)) r.parando = true;
  });
  return r;
}
function traducir(l) {            // linea del proceso -> [tipo, texto legible]; null = no mostrar
  let m;
  if (/Redirects are currently not supported|^\s*$/.test(l)) return null;
  if (l.startsWith('$ ')) return ['hito', 'Lanzado: ' + l.slice(2)];
  if ((m = l.match(/Loading policy from '([^']+)'/))) return ['hito', `Cargando el modelo ${m[1]}`];
  if ((m = l.match(/Policy loaded: type=(\w+), device=(\w+)/))) return ['ok', `Modelo cargado (${m[1].toUpperCase()} en ${m[2] === 'cuda' ? 'GPU' : m[2]})`];
  if (/Connecting robot/.test(l)) return ['hito', 'Conectando el brazo y las cámaras'];
  if ((m = l.match(/OpenCVCamera\((\d+)\) connected/))) return ['ok', `Cámara ${m[1]} conectada`];
  if ((m = l.match(/OpenCVCamera\((\d+)\) disconnected/))) return ['tenue', `Cámara ${m[1]} desconectada`];
  if (/SOFollower connected/.test(l)) return ['ok', 'Brazo conectado'];
  if (/SOFollower disconnected/.test(l)) return ['tenue', 'Brazo desconectado (sin par)'];
  if (/control loop started/.test(l)) return ['ok', '▶ El robot se mueve solo (política ACT)'];
  if ((m = l.match(/running slower \(([\d.]+) Hz\)/))) return ['aviso', `⚠ Va lento: ${m[1]} pasos/s (debería ir a 30)`];
  if (/Duration limit reached/.test(l)) return ['hito', 'Tiempo cumplido'];
  if (/Returning robot to initial position/.test(l)) return ['hito', 'Volviendo a la posición inicial'];
  if ((m = l.match(/effective cadence: ([\d.]+) Hz/))) return [parseFloat(m[1]) < 15 ? 'aviso' : 'ok', `Velocidad media: ${m[1]} pasos/s`];
  if ((m = l.match(/infer\s+mean\s+([\d.]+) ms/))) return [parseFloat(m[1]) > 60 ? 'aviso' : 'tenue', `Inferencia: ${num(parseFloat(m[1]), 0)} ms por paso de media`];
  if (/Rollout finished/.test(l)) return ['ok', 'Ejecución terminada'];
  if ((m = l.match(/^\[fin: código (-?\d+)\]/))) return m[1] === '0' ? ['ok', '✔ Proceso terminado'] : ['error', `✖ Terminó con error (código ${m[1]})`];
  if (/^\[PARANDO/.test(l)) return ['aviso', '■ Parando: el brazo se desconecta y suelta el par'];
  if (/Traceback|Error|Exception/.test(l)) return ['error', l];
  if (/^\[(filtro laser|gemelo|mapa)\]/.test(l)) return ['tenue', l];
  m = l.match(/^(INFO|WARNING|DEBUG)\s+\S+\s+\S+\s+\S+\s+(.*)$/);
  if (m) return [m[1] === 'WARNING' ? 'aviso' : 'tenue', m[2]];
  return ['', l];
}
const fmtT = (t) => (t == null ? '—' : '+' + num(t, t < 10 ? 1 : 0) + ' s');

let ultimoP = null, ejOculta = null, runVisto = null, etapasDichas = new Set(), gpuInfo = null, lentoDesde = 0;
async function proceso() {
  let p;
  try { p = await (await fetch('/proceso', { cache: 'no-store' })).json(); } catch { return; }
  ultimoP = p;
  document.body.classList.toggle('corriendo', !!p.vivo);
  // consola legible
  const crudo = $('verOriginal').checked;
  const filas = (p.salida || []).map((l, i) => {
    const tr = crudo ? ['', l] : traducir(l);
    return tr ? `<div class="ln ${tr[0]}"><time>${p.t ? fmtT(p.t[i]) : ''}</time><span>${esc(tr[1])}</span></div>` : '';
  }).join('');
  const c = $('consola'), abajo = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
  const html = filas || '<div class="ln tenue"><time></time><span>Sin procesos.</span></div>';
  if (proceso.ultimo !== html) { c.innerHTML = html; proceso.ultimo = html; if (abajo) c.scrollTop = c.scrollHeight; }
  // tarjeta de ejecucion (solo para el robot); el resto de procesos avisa con un toast al terminar
  const robot = (p.nombre || '').startsWith('ROBOT');
  if (!robot) {
    document.body.classList.remove('ejec');
    if (p.id && p.id !== runVisto && !p.vivo && p.codigo != null) {
      runVisto = p.id;
      toast(`${p.nombre}: ${p.codigo === 0 ? 'terminado' : 'error (código ' + p.codigo + ')'} · detalles en Control`, 5000);
    }
    return;
  }
  if (p.id !== runVisto) { runVisto = p.id; etapasDichas = new Set(); lentoDesde = 0; }
  const a = analizar(p), ahora = p.ahora || 0;
  const recien = p.vivo || (p.t && p.t.length && ahora - p.t[p.t.length - 1] < 120);
  document.body.classList.toggle('ejec', !!recien && ejOculta !== p.id);
  // etapas
  let act = 0;
  for (let k = 0; k < 5; k++) if (a.ini[k] != null) act = k;
  const fin = a.ini[4] != null, ok = fin && p.codigo === 0 && !a.error;
  const lis = $('ejEtapas').children;
  for (let k = 0; k < 5; k++) {
    const hecha = a.fin[k] != null || (fin && k < 4 && a.ini[k] != null) || (k === 4 && ok);
    const mal = (k === 4 && fin && !ok) || (a.error && !fin && k === act);
    lis[k].className = mal ? 'mal' : hecha ? 'hecha' : (k === act && !fin) ? 'act' : '';
    lis[k].querySelector('small').textContent = fmtT(a.fin[k] ?? a.ini[k]);
    if (a.ini[k] != null && !etapasDichas.has(k)) {        // cada etapa nueva, al registro visual
      etapasDichas.add(k);
      if (k === 2) {
        evento('marcha', '<b>El robot se mueve solo</b> · política ACT');
        titular({ sup: 'Robot autónomo', t: 'En marcha', sub: 'La política aprendida controla el brazo', clase: 'verde' });
        aviso([660, 990, 1320]);
      } else if (k === 4) evento(ok ? 'robot' : 'error', ok ? '<b>Ejecución terminada</b>' : `<b>Terminó con error</b> (código ${p.codigo})`);
      else evento('robot', ETAPAS[k].txt);
    }
  }
  const marcha = a.ini[2] != null && a.fin[2] == null && p.vivo;
  const hz = marcha ? (est.vivo && est.hz != null ? est.hz : a.hzLog) : (a.hzFinal ?? null);
  const lento = marcha && hz != null && hz < 8;
  if (lento && !lentoDesde) lentoDesde = performance.now();
  if (!lento) lentoDesde = 0;
  $('ejec').className = 'vidrio ' + (a.error || (fin && !ok) ? 'error' : fin ? 'fin' : lento ? 'lento' : marcha ? 'marcha' : 'prep');
  $('ejTitulo').textContent = a.parando && !fin ? 'Parando el robot' : fin ? (ok ? 'Ejecución terminada' : 'Error en la ejecución')
    : marcha ? 'Robot en marcha · autónomo' : a.ini[3] != null ? 'Volviendo a reposo'
    : a.ini[2] != null ? 'Tiempo cumplido' : a.ini[1] != null ? 'Conectando brazo y cámaras' : 'Preparando el modelo';
  $('ejModelo').textContent = p.nombre.replace(/^ROBOT:\s*/, '');
  const seg = p.segundos || 0;
  if (marcha && seg) {
    const resto = Math.max(0, seg - (ahora - a.ini[2]));
    $('ejReloj').textContent = fmt(resto); $('ejBarra').style.width = (100 * (1 - resto / seg)) + '%';
  } else {
    $('ejReloj').textContent = fmt(p.vivo ? ahora : (p.t && p.t.length ? p.t[p.t.length - 1] : 0));
    $('ejBarra').style.width = fin || a.fin[2] != null ? '100%' : '0%';
  }
  const hzEl = $('ejHz');
  hzEl.className = 'ej-hz ' + (hz == null ? '' : hz >= 20 ? 'bueno' : hz >= 8 ? 'regular' : 'malo');
  hzEl.querySelector('b').textContent = hz == null ? '—' : `${num(hz, 1)} pasos/s`;
  // avisos claros
  const av = $('ejAviso');
  let txt = '', rojo = false;
  if (a.error && !ok) { txt = 'Error: ' + a.error.slice(0, 220) + ' · detalles en Control.'; rojo = true; }
  else if ((lento && performance.now() - lentoDesde > 2500) || (fin && a.hzFinal != null && a.hzFinal < 8)) {
    const gpuLlena = gpuInfo && gpuInfo.total_mb - gpuInfo.usada_mb < 1500;
    txt = `El control va a ${num(hz ?? a.hzFinal, 1)} pasos/s y debería ir a 30: el brazo apenas se mueve.` +
      (a.infer ? ` Cada inferencia tarda ${num(a.infer, 0)} ms.` : '') +
      (gpuLlena ? ` La GPU está casi llena (${num(gpuInfo.usada_mb / 1024, 1)} de ${num(gpuInfo.total_mb / 1024, 1)} GB): cierra lo que la esté usando.`
        : ' Causa probable: otro programa usando la GPU.');
  }
  av.textContent = txt; av.className = 'ej-aviso' + (txt ? ' ver' : '') + (rojo ? ' rojo' : '');
}
setInterval(proceso, 600);

async function leerGpu() {
  try { gpuInfo = await (await fetch('/gpu', { cache: 'no-store' })).json(); } catch { gpuInfo = null; }
  const g = gpuInfo, el = $('gpuCtl'), ej = $('ejGpu');
  if (!g) { el.querySelector('b').textContent = 'sin datos'; ej.querySelector('b').textContent = '—'; return; }
  const libre = g.total_mb - g.usada_mb, txt = `${num(g.usada_mb / 1024, 1)} / ${num(g.total_mb / 1024, 1)} GB`;
  el.classList.toggle('llena', libre < 1500);
  el.querySelector('i').style.width = (100 * g.usada_mb / g.total_mb) + '%';
  el.querySelector('b').textContent = txt + (libre < 1500 ? ' · llena' : '');
  ej.className = 'ej-gpu ' + (libre < 1500 ? 'malo' : libre < 2500 ? 'regular' : 'bueno');
  ej.querySelector('b').textContent = `${txt} · ${g.uso} %`;
}
leerGpu(); setInterval(leerGpu, 3000);
$('verOriginal').onchange = () => { proceso.ultimo = null; proceso(); };
(async () => {
  try {
    const ms = await (await fetch('/modelos')).json();
    $('modelo').innerHTML = ms.map((m) => `<option ${m.includes('todo_v1') ? 'selected' : ''}>${m}</option>`).join('');
  } catch { /* sin servidor */ }
})();

// ============================================================ teclado
document.addEventListener('keydown', (e) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  if (!entrado && e.key === 'Enter' && !$('btnEntrar').disabled) return entrar(true);
  const vistas = { 1: 'cabina', 2: 'operador', 3: 'cenital', 4: 'lateral', 5: 'pinza', 6: 'operario' };
  if (e.key === 'p') return restablecerPaneles();
  if (vistas[e.key]) document.querySelector(`#vistas [data-v="${vistas[e.key]}"]`).click();
  else if (e.key === 'v') narrador.alternar();
  else if (e.key === 'g') $('bGeiger').click();
  else if (e.key === 'c') $('bControl').click();
  else if (e.key === 'i') narrador.decir('intro');
  else if (e.key === 'r') reiniciar();
  else if (e.key === 'Escape') { $('resumen').classList.add('oculta'); $('ctl').classList.remove('abierto'); }
});
