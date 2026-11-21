"""GEMELO DIGITAL en directo del SO-101 (MuJoCo) con el HUD de la historia PTI.

Ventana de 1280x720:
  izquierda  -> el brazo en 3D (MuJoCo) copiando EN DIRECTO las articulaciones del robot real,
                con el contenedor de muestra que coge y suelta
  derecha    -> lo que ve la camara cenital REAL (con el circulo del laser), fases
                1 APUNTA / 2 COGE / 3 TRAZA / 4 DEJA, telemetria y registro de trazabilidad

Los datos llegan por UDP (127.0.0.1) desde herramientas/lerobot_laser.py, que los envia solo
mientras graba o despliega. Esta app NO abre el robot ni las camaras: no interfiere con nada.

Uso (en otra terminal, con el venv activado, desde E:\\HACKATONLeRobot\\lerobot):
    python ..\\herramientas\\gemelo.py                     laboratorio (zona restringida)
    python ..\\herramientas\\gemelo.py --mision luna       mision lunar
    python ..\\herramientas\\gemelo.py --demo 3            sin robot: reproduce el episodio 3 de pti_coger_v7
Teclas: q salir | m cambiar mision | espacio pausar giro de camara | r reiniciar registro
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import mujoco
import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "lerobot" / "examples" / "so101_mujoco"))
from so101_assets import menagerie_spec  # noqa: E402

PUERTO_ESTADO, PUERTO_IMAGEN = 5055, 5056
MOTORES = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
# articulacion del modelo MuJoCo y signo (de examples/so101_mujoco/so101_mujoco_robot.py)
MODELO = {"shoulder_pan": ("Rotation", -1), "shoulder_lift": ("Pitch", +1), "elbow_flex": ("Elbow", +1),
          "wrist_flex": ("Wrist_Pitch", -1), "wrist_roll": ("Wrist_Roll", +1), "gripper": ("Jaw", +1)}

W, H = 1280, 720
VW, VH = 760, 720             # vista 3D
NARANJA, CIAN, ROJO, BLANCO, GRIS, VERDE = (40, 140, 255), (230, 200, 60), (60, 60, 255), (235, 235, 235), (120, 120, 120), (120, 220, 120)
FUENTE = cv2.FONT_HERSHEY_SIMPLEX
MISIONES = {
    "lab": ("ZONA RESTRINGIDA", "MATERIAL RADIACTIVO - CELDA CALIENTE", "HOY, EN UN LABORATORIO"),
    "luna": ("MISION ARTEMIS - POLO SUR LUNAR", "ROVER + BRAZO SO-101 - AUTONOMIA SUPERVISADA", "MANANA... EN LA LUNA"),
}


# ----------------------------------------------------------------------------- escena
def construir_escena(mision: str):
    spec = menagerie_spec()
    for t in spec.textures:                                   # cielo / suelo segun la mision
        try:
            if t.type == mujoco.mjtTexture.mjTEXTURE_SKYBOX:
                t.rgb1, t.rgb2 = ([0.02, 0.02, 0.04], [0, 0, 0]) if mision == "luna" else ([0.12, 0.13, 0.15], [0.02, 0.02, 0.03])
            elif t.name == "groundplane":
                t.rgb1, t.rgb2 = ([0.55, 0.55, 0.53], [0.50, 0.50, 0.48]) if mision == "luna" else ([0.16, 0.17, 0.19], [0.12, 0.13, 0.15])
        except Exception:
            pass
    wb = spec.worldbody
    # contenedor de muestra (bote de tapa blanca): cuerpo mocap que movemos nosotros
    c = wb.add_body(name="contenedor", mocap=True, pos=[0.22, 0.10, 0.035])
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.022, 0.033, 0], rgba=[0.15, 0.15, 0.17, 1],
               contype=0, conaffinity=0)
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.0235, 0.006, 0], pos=[0, 0, 0.036],
               rgba=[0.95, 0.95, 0.95, 1], contype=0, conaffinity=0)
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.0225, 0.006, 0], pos=[0, 0, 0.012],
               rgba=[1.0, 0.8, 0.0, 1], contype=0, conaffinity=0)       # banda amarilla de peligro
    # almacen blindado (donde empieza) y marca del destino
    a = wb.add_body(name="almacen", mocap=True, pos=[0.22, 0.10, 0.0])
    a.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.04, 0.003, 0], rgba=[1.0, 0.8, 0.0, 0.5],
               contype=0, conaffinity=0)
    d = wb.add_body(name="destino", mocap=True, pos=[0, 0, -1])
    d.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.035, 0.002, 0], rgba=[1, 0.1, 0.1, 0.6],
               contype=0, conaffinity=0)
    m = spec.compile()
    return m, mujoco.MjData(m)


class Gemelo:
    def __init__(self, mision: str):
        self.mision = mision
        self.m, self.d = construir_escena(mision)
        self.adr, self.rango = {}, {}
        for n, (mj, _s) in MODELO.items():
            j = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, mj)
            self.adr[n], self.rango[n] = int(self.m.jnt_qposadr[j]), self.m.jnt_range[j].copy()
        self.pads = [mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_GEOM, g) for g in ("fixed_jaw_pad_2", "moving_jaw_pad_2")]
        self.mocap = {n: int(self.m.body_mocapid[mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, n)])
                      for n in ("contenedor", "almacen", "destino")}
        self.m.vis.global_.offwidth, self.m.vis.global_.offheight = VW, VH
        self.r = mujoco.Renderer(self.m, VH, VW)
        self.cam = mujoco.MjvCamera()
        mujoco.mjv_defaultFreeCamera(self.m, self.cam)
        self.cam.lookat[:] = [0.15, 0.0, 0.10]
        self.cam.distance, self.cam.azimuth, self.cam.elevation = 1.05, 150.0, -30.0
        self.cogido, self.pinza_abierta_antes = False, False
        self.offset = np.zeros(3)

    def poner(self, q: dict):
        for n in MOTORES:
            if n not in q:
                continue
            lo, hi = self.rango[n]
            if n == "gripper":
                v = lo + (hi - lo) * np.clip(q[n], 0, 100) / 100.0
            else:
                v = 0.5 * (lo + hi) + MODELO[n][1] * np.radians(q[n])
            self.d.qpos[self.adr[n]] = np.clip(v, lo, hi)
        mujoco.mj_kinematics(self.m, self.d)

    def punta(self) -> np.ndarray:
        return 0.5 * (self.d.geom_xpos[self.pads[0]] + self.d.geom_xpos[self.pads[1]])

    def actualizar_contenedor(self, pinza: float):
        """Agarre 'logico': la pinza estaba abierta y se cierra sin llegar al tope (hay algo
        dentro) cerca del contenedor -> va pegado a la punta. Al abrir, cae a la mesa."""
        p, c = self.punta(), self.d.mocap_pos[self.mocap["contenedor"]]
        evento = None
        if pinza > 45:
            if self.cogido:
                self.cogido, evento = False, "suelta"
                self.d.mocap_pos[self.mocap["contenedor"]] = [p[0], p[1], 0.035]
            self.pinza_abierta_antes = True
        elif self.pinza_abierta_antes and 6 < pinza < 40 and not self.cogido and p[2] < 0.14:
            if np.linalg.norm(p[:2] - c[:2]) > 0.06:          # primera vez: el almacen esta donde coge
                self.d.mocap_pos[self.mocap["almacen"]] = [p[0], p[1], 0.0]
            self.cogido, evento = True, "coge"
            self.pinza_abierta_antes = False
            self.offset = np.array([0, 0, -0.035])
        if self.cogido:
            self.d.mocap_pos[self.mocap["contenedor"]] = p + self.offset
        return evento

    def render(self, girar: bool) -> np.ndarray:
        if girar:
            self.cam.azimuth = 150 + 25 * np.sin(time.time() * 0.15)
        self.r.update_scene(self.d, camera=self.cam)
        return cv2.cvtColor(self.r.render(), cv2.COLOR_RGB2BGR)


# ----------------------------------------------------------------------------- fuentes de datos
class Udp:
    def __init__(self):
        self.se = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.se.bind(("127.0.0.1", PUERTO_ESTADO)); self.se.setblocking(False)
        self.si = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.si.bind(("127.0.0.1", PUERTO_IMAGEN)); self.si.setblocking(False)
        self.q, self.laser, self.img, self.t = {}, None, None, 0.0

    def leer(self):
        try:
            while True:
                msg = json.loads(self.se.recv(65535))
                if "q" in msg:
                    self.q, self.t = msg["q"], time.time()
                if "laser" in msg:
                    self.laser = msg["laser"]
        except (BlockingIOError, ConnectionResetError, ValueError):
            pass
        try:
            while True:
                buf = self.si.recv(65535)
                self.img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
        except (BlockingIOError, ConnectionResetError):
            pass
        return self.q, self.laser, self.img, (time.time() - self.t) if self.t else None


class Demo:
    """Reproduce un episodio grabado (estado + video cenital) como si fuera el robot en directo."""
    def __init__(self, ep: int):
        import pandas as pd
        d = Path(r"E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01\pti_coger_v7")
        df = pd.read_parquet(d / "data" / "chunk-000" / "file-000.parquet")
        self.s = np.stack(df[df.episode_index == ep]["observation.state"])
        e = pd.read_parquet(d / "meta" / "episodes" / "chunk-000" / "file-000.parquet").set_index("episode_index").loc[ep]
        f = int(e["videos/observation.images.top/file_index"])
        self.cap = cv2.VideoCapture(str(d / "videos" / "observation.images.top" / "chunk-000" / f"file-{f:03d}.mp4"))
        self.cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * float(e["videos/observation.images.top/from_timestamp"]))
        self.i, self.t0, self.img = 0, time.time(), None
        print(f"[demo] episodio {ep}: {len(self.s)} fotogramas")

    def leer(self):
        i = min(int((time.time() - self.t0) * 30), len(self.s) - 1)
        while self.i <= i:
            ok, im = self.cap.read()
            if ok:
                self.img = im
            self.i += 1
        return dict(zip(MOTORES, map(float, self.s[i]))), None, self.img, 0.0


# ----------------------------------------------------------------------------- HUD
def texto(img, s, xy, esc=0.5, color=BLANCO, grosor=1):
    cv2.putText(img, s, xy, FUENTE, esc, color, grosor, cv2.LINE_AA)


def esquinas(img, x0, y0, x1, y1, color, l=14):
    for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        cv2.line(img, (x, y), (x + dx * l, y), color, 2); cv2.line(img, (x, y), (x, y + dy * l), color, 2)


def fase_actual(laser_reciente, cogido, t_suelta, pinza):
    if t_suelta and time.time() - t_suelta < 3:
        return 3
    if cogido:
        return 2
    if laser_reciente:
        return 0
    return 1 if pinza is not None else -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mision", choices=list(MISIONES), default="lab")
    ap.add_argument("--demo", type=int, default=None, help="episodio de pti_coger_v7 a reproducir sin robot")
    ap.add_argument("--captura", default=None, help="guarda una captura a los 12 s y sale (para pruebas)")
    ap.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador (ya esta abierto)")
    a = ap.parse_args()
    t_inicio = time.time()

    g = Gemelo(a.mision)
    fuente = Demo(a.demo) if a.demo is not None else Udp()
    registro: deque = deque(maxlen=7)
    registro.append((time.strftime("%H:%M:%S"), "Sistema listo. Manos humanas en zona: 0"))
    t_laser = t_suelta = 0.0
    n_mov, girar = 0, True
    web = Web()
    if not a.captura and not a.sin_navegador:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{PUERTO_WEB}/")
        print(f"[gemelo] abierto en el navegador: http://127.0.0.1:{PUERTO_WEB}/  (F11 pantalla completa, Ctrl+C aqui para salir)")

    while True:
        q, laser, cam, edad = fuente.leer()
        if laser:
            t_laser = time.time()
        pinza = q.get("gripper") if q else None
        if q:
            g.poner(q)
            ev = g.actualizar_contenedor(pinza)
            p = g.punta() * 100
            if ev == "coge":
                registro.append((time.strftime("%H:%M:%S"), f"COGE contenedor en ({p[0]:.0f}, {p[1]:.0f}) cm"))
            elif ev == "suelta":
                n_mov += 1; t_suelta = time.time()
                g.d.mocap_pos[g.mocap["destino"]] = [p[0] / 100, p[1] / 100, 0.001]
                registro.append((time.strftime("%H:%M:%S"), f"DEJA en ({p[0]:.0f}, {p[1]:.0f}) cm  - mov. #{n_mov}"))

        lienzo = np.zeros((H, W, 3), np.uint8)
        lienzo[:] = (14, 14, 16)
        vista = g.render(girar)
        lienzo[:, :VW] = vista
        titulo, sub, lema = MISIONES[g.mision]

        # --- cabecera sobre la vista 3D
        cv2.rectangle(lienzo, (18, 18), (440, 66), (0, 0, 0), -1)
        cv2.line(lienzo, (18, 18), (18, 66), NARANJA if g.mision == "lab" else VERDE, 3)
        texto(lienzo, titulo, (30, 38), 0.55, NARANJA if g.mision == "lab" else VERDE, 1)
        texto(lienzo, sub, (30, 58), 0.4, GRIS)
        vivo = edad is not None and edad < 1.0
        if int(time.time() * 2) % 2 or not vivo:
            cv2.circle(lienzo, (VW - 150, 36), 6, ROJO if vivo else GRIS, -1)
        texto(lienzo, "EN DIRECTO" if vivo else "ESPERANDO ROBOT", (VW - 138, 41), 0.5, BLANCO if vivo else GRIS)
        texto(lienzo, "GEMELO DIGITAL  -  MuJoCo  -  copia las articulaciones reales", (20, VH - 20), 0.42, GRIS)
        esquinas(lienzo, 8, 8, VW - 8, VH - 8, (70, 70, 70))
        if a.demo is not None:
            texto(lienzo, f"REPRODUCCION episodio {a.demo}", (20, VH - 44), 0.45, CIAN)

        # --- panel derecho
        x0 = VW + 20
        texto(lienzo, "REAL  -  camara cenital", (x0, 34), 0.45, GRIS)
        if cam is not None:
            mini = cv2.resize(cam, (480, 360))
            lienzo[44:404, x0:x0 + 480] = mini
        else:
            cv2.rectangle(lienzo, (x0, 44), (x0 + 480, 404), (40, 40, 40), 1)
            texto(lienzo, "sin imagen", (x0 + 190, 230), 0.5, GRIS)
        esquinas(lienzo, x0, 44, x0 + 480, 404, CIAN)

        # fases
        f = fase_actual(time.time() - t_laser < 1.0, g.cogido, t_suelta, pinza)
        for i, nombre in enumerate(("1 APUNTA", "2 COGE", "3 TRAZA", "4 DEJA")):
            bx = x0 + i * 122
            act = i == f
            cv2.rectangle(lienzo, (bx, 418), (bx + 114, 446), ROJO if act else (40, 40, 40), -1 if act else 1)
            texto(lienzo, nombre, (bx + 14, 438), 0.5, BLANCO if act else GRIS, 2 if act else 1)

        # telemetria
        y = 470
        for n in MOTORES[:5]:
            v = q.get(n, 0.0) if q else 0.0
            texto(lienzo, n.replace("_", " "), (x0, y), 0.38, GRIS)
            cv2.rectangle(lienzo, (x0 + 110, y - 9), (x0 + 330, y - 1), (40, 40, 40), -1)
            cx = x0 + 220 + int(np.clip(v, -110, 110))
            cv2.rectangle(lienzo, (min(cx, x0 + 220), y - 9), (max(cx, x0 + 220), y - 1), CIAN, -1)
            texto(lienzo, f"{v:6.1f} deg", (x0 + 340, y), 0.38, BLANCO)
            y += 17
        texto(lienzo, "pinza", (x0, y), 0.38, GRIS)
        cv2.rectangle(lienzo, (x0 + 110, y - 9), (x0 + 330, y - 1), (40, 40, 40), -1)
        if pinza is not None:
            cv2.rectangle(lienzo, (x0 + 110, y - 9), (x0 + 110 + int(2.2 * np.clip(pinza, 0, 100)), y - 1), NARANJA, -1)
            texto(lienzo, f"{pinza:5.0f} %  {'SUJETA' if g.cogido else ''}", (x0 + 340, y), 0.38, BLANCO)

        # registro de trazabilidad
        y += 26
        texto(lienzo, "REGISTRO DE TRAZABILIDAD", (x0, y), 0.42, NARANJA); y += 4
        for hora, s in list(registro):
            y += 17
            texto(lienzo, f"{hora}  {s}", (x0, y), 0.38, BLANCO)
        texto(lienzo, f"Movimientos: {n_mov}   Dosis operador: 0,00 uSv (simulada)   Manos en zona: 0",
              (x0, H - 34), 0.36, VERDE)
        texto(lienzo, "PTI  -  TU APUNTAS. EL ROBOT HACE EL RESTO.  -  " + lema, (x0, H - 14), 0.36, GRIS)

        if a.captura and time.time() - t_inicio > 12:
            cv2.imwrite(a.captura, lienzo)
            break
        web.publicar(lienzo)
        web.publicar(vista, "3d")
        if cam is not None:
            web.publicar(cam, "camara")
        web.estado = {
            "vivo": bool(vivo), "edad": edad, "fase": int(f), "cogido": bool(g.cogido),
            "laser": bool(time.time() - t_laser < 1.0), "pinza": pinza, "movimientos": n_mov,
            "q": {k: round(float(v), 1) for k, v in (q or {}).items()},
            "punta_cm": [round(float(x), 1) for x in g.punta() * 100] if q else None,
            "registro": [f"{h}  {s}" for h, s in registro], "demo": a.demo is not None,
            "suelta_hace": (time.time() - t_suelta) if t_suelta else None,
        }
        time.sleep(0.02)
        while web.teclas:
            k = web.teclas.popleft()
            if k == "giro":
                girar = not girar
            elif k == "reiniciar":
                registro.clear(); n_mov = 0
            elif k == "mision":
                g = Gemelo("luna" if g.mision == "lab" else "lab")
        if isinstance(fuente, Demo) and fuente.i >= len(fuente.s):
            fuente = Demo(a.demo)


# ----------------------------------------------------------------------------- servidor web (MJPEG)
PUERTO_WEB = 8765
PAGINA = b"""<!doctype html><html><head><meta charset="utf-8"><title>PTI - gemelo digital</title>
<style>html,body{margin:0;height:100%;background:#0e0e10;display:flex;align-items:center;justify-content:center}
img{max-width:100vw;max-height:100vh}#b{position:fixed;bottom:6px;right:8px;opacity:.25;font:12px sans-serif}
#b:hover{opacity:1}button{background:#222;color:#ddd;border:1px solid #444;margin-left:4px;cursor:pointer}</style></head>
<body><img src="/stream"><div id="b">
<button onclick="fetch('/tecla?k=mision')">Lab / Luna (m)</button>
<button onclick="fetch('/tecla?k=giro')">Giro (espacio)</button>
<button onclick="fetch('/tecla?k=reiniciar')">Reiniciar registro (r)</button></div>
<script>document.onkeydown=e=>{const k={m:'mision',' ':'giro',r:'reiniciar'}[e.key];
if(k){fetch('/tecla?k='+k);e.preventDefault()}}</script></body></html>"""


WEB_HTML = AQUI / "gemelo_web.html"   # web "celda caliente" (Pu-239); la vista clasica sigue en /clasico


class Web:
    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.jpgs, self.teclas, self.cond = {}, deque(), threading.Condition()
        self.estado = {}
        yo = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _enviar(self, cuerpo: bytes, tipo: str):
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(cuerpo)

            def do_GET(self):
                if self.path.startswith("/tecla"):
                    yo.teclas.append(self.path.split("k=")[-1])
                    self.send_response(204); self.end_headers(); return
                if self.path.startswith("/estado"):
                    return self._enviar(json.dumps(yo.estado).encode(), "application/json")
                if self.path.startswith("/stream"):
                    nombre = self.path.split("v=")[-1] if "v=" in self.path else "compuesta"
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
                    self.end_headers()
                    try:
                        while True:
                            with yo.cond:
                                yo.cond.wait(1.0)
                                jpg = yo.jpgs.get(nombre)
                            if jpg is None:
                                continue
                            self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                             + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                    except (ConnectionError, OSError):
                        return
                if self.path.startswith("/clasico") or not WEB_HTML.exists():
                    return self._enviar(PAGINA, "text/html; charset=utf-8")
                self._enviar(WEB_HTML.read_bytes(), "text/html; charset=utf-8")

        self.srv = ThreadingHTTPServer(("127.0.0.1", PUERTO_WEB), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def publicar(self, img, nombre: str = "compuesta"):
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            with self.cond:
                self.jpgs[nombre] = buf.tobytes()
                self.cond.notify_all()


if __name__ == "__main__":
    main()
