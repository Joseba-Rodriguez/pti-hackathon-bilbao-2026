// Paneles de la interfaz: cada tarjeta con data-panel se puede minimizar, soltar y arrastrar por su
// cabecera, redimensionar desde la esquina y volver a su sitio. La disposicion se recuerda en este
// navegador (localStorage); "Restablecer paneles" lo deja todo como al principio.
const CLAVE = 'pti-paneles-v1';
let estado = {};
try { estado = JSON.parse(localStorage.getItem(CLAVE) || '{}') || {}; } catch { estado = {}; }
const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(estado)); } catch { /* sin almacenamiento */ } };
let zArriba = 14;

const ICONO_MIN = '<svg viewBox="0 0 24 24"><path d="M6 12h12"/></svg>';
const ICONO_MAX = '<svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>';
const ICONO_SOLTAR = '<svg viewBox="0 0 24 24"><path d="M9 4h11v11"/><path d="M20 4 10 14"/><path d="M15 20H4V9"/></svg>';
const ICONO_ANCLAR = '<svg viewBox="0 0 24 24"><path d="M4 14v6h6"/><path d="M4 20l7-7"/><path d="M14 4h6v6"/><path d="M20 4l-7 7"/></svg>';

function info(p) { return estado[p.dataset.panel] || (estado[p.dataset.panel] = {}); }

function encajar(p) {                                  // que no se salga de la ventana
  const r = p.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  const x = Math.min(Math.max(8, r.left), Math.max(8, W - Math.min(r.width, W - 16) - 8));
  const y = Math.min(Math.max(8, r.top), Math.max(8, H - 48));
  p.style.left = x + 'px'; p.style.top = y + 'px';
}

function soltar(p, r = p.getBoundingClientRect()) {
  if (p.classList.contains('flotante')) return;
  p._origen = { padre: p.parentElement, sig: p.nextElementSibling };
  document.body.appendChild(p);
  p.classList.add('flotante');
  p.style.left = r.left + 'px'; p.style.top = r.top + 'px'; p.style.width = r.width + 'px';
  if (!p.classList.contains('min')) p.style.height = r.height + 'px';
  p.style.zIndex = ++zArriba;
  botones(p);
}

function anclar(p) {
  if (!p.classList.contains('flotante')) return;
  p.classList.remove('flotante');
  ['left', 'top', 'width', 'height', 'zIndex'].forEach((k) => (p.style[k] = ''));
  const o = p._origen || {};
  const padre = document.getElementById(p.dataset.padre) || o.padre || document.body;
  // vuelve a su posicion original entre sus hermanos
  const hermanos = [...padre.children].filter((c) => c.dataset.orden != null);
  const sig = hermanos.find((c) => +c.dataset.orden > +p.dataset.orden);
  padre.insertBefore(p, sig || null);
  const i = info(p); delete i.flot; delete i.x; delete i.y; delete i.w; delete i.h; guardar();
  botones(p);
}

function minimizar(p, si) {
  p.classList.toggle('min', si);
  if (p.classList.contains('flotante')) p.style.height = si ? '' : (info(p).h ? info(p).h + 'px' : '');
  info(p).min = si || undefined; guardar();
  botones(p);
}

function botones(p) {
  const min = p.classList.contains('min'), flot = p.classList.contains('flotante');
  const bm = p.querySelector('.p-min'), bp = p.querySelector('.p-pin');
  bm.innerHTML = min ? ICONO_MAX : ICONO_MIN; bm.title = min ? 'Desplegar' : 'Minimizar';
  bp.innerHTML = flot ? ICONO_ANCLAR : ICONO_SOLTAR; bp.title = flot ? 'Volver a su sitio' : 'Soltar y mover';
}

function arrastrar(p, cab, e) {
  if (e.button !== 0 || e.target.closest('button, input, select, a')) return;
  e.preventDefault();
  if (!p.classList.contains('flotante')) soltar(p);
  p.style.zIndex = ++zArriba;
  const r = p.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
  cab.setPointerCapture(e.pointerId);
  p.classList.add('arrastrando');
  const mover = (ev) => {
    p.style.left = Math.min(Math.max(8 - r.width + 80, ev.clientX - dx), innerWidth - 80) + 'px';
    p.style.top = Math.min(Math.max(8, ev.clientY - dy), innerHeight - 40) + 'px';
  };
  const fin = () => {
    cab.removeEventListener('pointermove', mover); cab.removeEventListener('pointerup', fin); cab.removeEventListener('pointercancel', fin);
    p.classList.remove('arrastrando');
    const i = info(p); i.flot = true; i.x = parseFloat(p.style.left); i.y = parseFloat(p.style.top); guardar();
  };
  cab.addEventListener('pointermove', mover); cab.addEventListener('pointerup', fin); cab.addEventListener('pointercancel', fin);
}

export function activarPaneles() {
  document.querySelectorAll('[data-panel]').forEach((p) => {
    const padre = p.parentElement;
    p.dataset.padre = padre.id || '';
    p.dataset.orden = [...padre.children].indexOf(p);
    const cab = p.querySelector('.t-cab, .ej-cab');
    cab.classList.add('p-asa');
    const ctl = document.createElement('span'); ctl.className = 'p-ctl';
    ctl.innerHTML = '<button class="p-btn p-min"></button><button class="p-btn p-pin"></button>';
    cab.appendChild(ctl);
    ctl.querySelector('.p-min').onclick = (e) => { e.stopPropagation(); minimizar(p, !p.classList.contains('min')); };
    ctl.querySelector('.p-pin').onclick = (e) => { e.stopPropagation(); p.classList.contains('flotante') ? anclar(p) : (soltar(p), guardarPos(p)); };
    cab.addEventListener('pointerdown', (e) => arrastrar(p, cab, e));
    cab.addEventListener('dblclick', (e) => { if (!e.target.closest('button')) minimizar(p, !p.classList.contains('min')); });
    p.addEventListener('pointerdown', () => { if (p.classList.contains('flotante')) p.style.zIndex = ++zArriba; });
    // tamano elegido con la esquina de redimensionar
    new ResizeObserver(() => {
      if (!p.classList.contains('flotante') || p.classList.contains('min') || p.classList.contains('arrastrando')) return;
      const r = p.getBoundingClientRect(), i = info(p);
      if (Math.abs((i.w || 0) - r.width) > 2 || Math.abs((i.h || 0) - r.height) > 2) { i.w = Math.round(r.width); i.h = Math.round(r.height); guardar(); }
    }).observe(p);
    // estado recordado
    const i = estado[p.dataset.panel] || {};
    if (i.min) p.classList.add('min');
    if (i.flot) {
      soltar(p, { left: i.x ?? 100, top: i.y ?? 100, width: i.w || p.getBoundingClientRect().width || 340, height: i.h || 0 });
      if (!i.h || i.min) p.style.height = '';
      encajar(p);
    }
    botones(p);
  });
  addEventListener('resize', () => document.querySelectorAll('.flotante').forEach(encajar));
}
function guardarPos(p) { const i = info(p), r = p.getBoundingClientRect(); i.flot = true; i.x = r.left; i.y = r.top; i.w = Math.round(r.width); guardar(); }

export function restablecerPaneles() {
  document.querySelectorAll('[data-panel]').forEach((p) => { anclar(p); p.classList.remove('min'); botones(p); });
  estado = {}; guardar();
}
