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
    python ..\\herramientas\\gemelo.py --demo 3            sin robot: reproduce el episodio 3 de pti_laser_H_centro
                                                       (--dataset pti_coger_v7 para otro dataset)
Web: http://127.0.0.1:8765/ (cabina 3D, herramientas/web/) | /v1 web anterior | /clasico vista MuJoCo
La calibracion del gemelo esta en herramientas/gemelo_calibracion.json (sacada de las grabaciones).
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
# Calibracion sacada de las grabaciones reales (herramientas/calibrar_gemelo.py): signos de cada
# articulacion, homografia camara -> robot y posiciones del soporte y la cartulina.
CAL = json.loads((AQUI / "gemelo_calibracion.json").read_text(encoding="utf-8"))
_SIG = CAL["articulaciones"]["signos"]
MODELO = {"shoulder_pan": ("Rotation", _SIG["shoulder_pan"]), "shoulder_lift": ("Pitch", _SIG["shoulder_lift"]),
          "elbow_flex": ("Elbow", _SIG["elbow_flex"]), "wrist_flex": ("Wrist_Pitch", _SIG["wrist_flex"]),
          "wrist_roll": ("Wrist_Roll", _SIG["wrist_roll"]), "gripper": ("Jaw", +1)}
DESFASE = CAL["articulaciones"].get("desfases_grados", {})   # grados que se suman antes del signo
H_CAM = np.array(CAL["camara_a_robot"]["H"], float)
ESC = CAL["escena"]
SOPORTE = np.array(ESC["soporte_cm"], float) / 100
VASO_R, VASO_H = ESC["vaso_mm"]["diametro"] / 2000, ESC["vaso_mm"]["alto"] / 1000
AGARRE_Z = ESC["altura_agarre_cm"] / 100
CARTULINA = np.array(ESC["cartulina_cm"], np.float32)


def px_a_robot(px) -> list[float] | None:
    """Pixel de la camara cenital (640x480) -> (x, y) en metros del robot."""
    if px is None:
        return None
    p = cv2.perspectiveTransform(np.array([[px[:2]]], float), H_CAM)[0, 0] / 100
    return [round(float(p[0]), 4), round(float(p[1]), 4)]

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
    # contenedor (el vaso real: 41 x 55 mm): cuerpo mocap que movemos nosotros; pos = su centro
    c = wb.add_body(name="contenedor", mocap=True, pos=[SOPORTE[0], SOPORTE[1], VASO_H / 2])
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[VASO_R, VASO_H / 2, 0], rgba=[0.15, 0.15, 0.17, 1],
               contype=0, conaffinity=0)
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[VASO_R + 0.001, 0.005, 0], pos=[0, 0, VASO_H / 2 - 0.004],
               rgba=[0.95, 0.95, 0.95, 1], contype=0, conaffinity=0)
    c.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[VASO_R + 0.0005, 0.005, 0], pos=[0, 0, -0.01],
               rgba=[1.0, 0.8, 0.0, 1], contype=0, conaffinity=0)       # banda amarilla de peligro
    # almacen blindado (el soporte real, calibrado) y marca del destino
    a = wb.add_body(name="almacen", mocap=True, pos=[SOPORTE[0], SOPORTE[1], 0.0])
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
                v = 0.5 * (lo + hi) + MODELO[n][1] * np.radians(q[n] + DESFASE.get(n, 0.0))
            self.d.qpos[self.adr[n]] = np.clip(v, lo, hi)
        mujoco.mj_kinematics(self.m, self.d)

    def punta(self) -> np.ndarray:
        return 0.5 * (self.d.geom_xpos[self.pads[0]] + self.d.geom_xpos[self.pads[1]])

    def actualizar_contenedor(self, pinza: float):
        """Agarre 'logico': la pinza estaba abierta y se cierra sin llegar al tope (hay algo
        dentro) cerca de la mesa -> el vaso va pegado a la punta. Al abrir, se queda DE PIE en
        la mesa justo debajo (nunca atraviesa el suelo).
        Umbrales de las grabaciones: abierta ~35-60, sujetando el vaso ~19-22, cerrada ~1."""
        p, c = self.punta(), self.d.mocap_pos[self.mocap["contenedor"]]
        evento = None
        if pinza > 27:
            if self.cogido:
                self.cogido, evento = False, "suelta"
                self.d.mocap_pos[self.mocap["contenedor"]] = [p[0], p[1], VASO_H / 2]
            self.pinza_abierta_antes = True
        elif self.pinza_abierta_antes and 8 < pinza < 27 and not self.cogido and p[2] < 0.12:
            self.cogido, evento = True, "coge"
            self.pinza_abierta_antes = False
            # si coge el vaso donde esta, se mantiene la posicion relativa (sin saltos); si no,
            # se coloca en la pinza a la altura de agarre medida en las grabaciones
            rel = c - p
            self.offset = rel if np.linalg.norm(rel[:2]) < 0.05 else np.array([0, 0, VASO_H / 2 - AGARRE_Z])
        if self.cogido:
            pos = p + self.offset
            pos[2] = max(pos[2], VASO_H / 2)                 # nunca por debajo de la mesa
            self.d.mocap_pos[self.mocap["contenedor"]] = pos
        return evento

    def reiniciar_contenedor(self):
        self.cogido, self.pinza_abierta_antes = False, False
        self.d.mocap_pos[self.mocap["contenedor"]] = [SOPORTE[0], SOPORTE[1], VASO_H / 2]
        self.d.mocap_pos[self.mocap["destino"]] = [0, 0, -1]

    # --- para la web 3D (Three.js): mallas visuales y su pose en cada instante
    def geoms_visuales(self) -> list[int]:
        if not hasattr(self, "_gv"):
            self._gv = [g for g in range(self.m.ngeom)
                        if self.m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH and self.m.geom_group[g] == 2]
        return self._gv

    def escena(self) -> dict:
        out = []
        for g in self.geoms_visuales():
            mesh = int(self.m.geom_dataid[g])
            nombre = mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_MESH, mesh)
            out.append({"id": g, "malla": nombre, "motor": "Motor" in (nombre or ""),
                        "cuerpo": mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, int(self.m.geom_bodyid[g]))})
        return {"geoms": out, "soporte": SOPORTE.tolist(), "cartulina": (np.array(ESC["cartulina_cm"]) / 100).tolist(),
                "vaso": {"r": VASO_R, "h": VASO_H}}

    def malla(self, g: int) -> bytes:
        """Triangulos (float32 x,y,z) de la malla visual del geom g, en el marco del geom."""
        mesh = int(self.m.geom_dataid[g])
        v0, nv = self.m.mesh_vertadr[mesh], self.m.mesh_vertnum[mesh]
        f0, nf = self.m.mesh_faceadr[mesh], self.m.mesh_facenum[mesh]
        v = self.m.mesh_vert[v0:v0 + nv]
        f = self.m.mesh_face[f0:f0 + nf]
        return np.ascontiguousarray(v[f].reshape(-1, 3), dtype="<f4").tobytes()

    def poses(self) -> list[list[float]]:
        out = []
        for g in self.geoms_visuales():
            q = np.zeros(4)
            mujoco.mju_mat2Quat(q, self.d.geom_xmat[g])
            out.append([round(float(x), 5) for x in (*self.d.geom_xpos[g], *q)])
        return out

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
        self.sm = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)       # camara de muneca
        self.sm.bind(("127.0.0.1", PUERTO_IMAGEN + 1)); self.sm.setblocking(False)
        self.muneca_jpg = None                                           # jpg tal cual llega (nuevo)
        self.q, self.laser, self.img, self.t = {}, None, None, 0.0
        self.llegadas: deque = deque(maxlen=200)     # una por paso del bucle de control del robot

    def hz(self) -> float | None:
        """Pasos por segundo del bucle de control real (deberia ser ~30)."""
        ahora = time.time()
        n = sum(1 for t in self.llegadas if ahora - t < 2.0)
        return round(n / 2.0, 1) if self.t and ahora - self.t < 2.0 else None

    def leer(self):
        try:
            while True:
                msg = json.loads(self.se.recv(65535))
                if "q" in msg:
                    self.q, self.t = msg["q"], time.time()
                    self.llegadas.append(self.t)
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
        try:
            while True:
                self.muneca_jpg = self.sm.recv(65535)
        except (BlockingIOError, ConnectionResetError):
            pass
        return self.q, self.laser, self.img, (time.time() - self.t) if self.t else None


class Demo:
    """Reproduce un episodio grabado (estado + video cenital) como si fuera el robot en directo."""
    def __init__(self, ep: int, dataset: str = "pti_laser_H_centro"):
        import glob
        import pandas as pd
        d = Path(r"E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01") / dataset
        df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(d / "data" / "*" / "*.parquet")))])
        self.s = np.stack(df[df.episode_index == ep]["observation.state"])
        E = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(d / "meta" / "episodes" / "*" / "*.parquet")))])
        e = E.set_index("episode_index").loc[ep]
        f = int(e["videos/observation.images.top/file_index"])
        ck = int(e.get("videos/observation.images.top/chunk_index", 0))
        self.cap = cv2.VideoCapture(str(d / "videos" / "observation.images.top" / f"chunk-{ck:03d}" / f"file-{f:03d}.mp4"))
        self.cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * float(e["videos/observation.images.top/from_timestamp"]))
        self.i, self.t0, self.img, self.laser = 0, time.time(), None, None
        print(f"[demo] {dataset} episodio {ep}: {len(self.s)} fotogramas")

    @staticmethod
    def circulo_laser(im):
        """El circulo que dibuja lerobot_laser.py (rojo puro, centro blanco, ~25 px) en la grabacion."""
        b, g, r = (im[..., k].astype(np.int16) for k in range(3))
        n, _, st, cen = cv2.connectedComponentsWithStats(((r > 170) & (g < 90) & (b < 90)).astype(np.uint8))
        for k in range(1, n):
            x, y, w, h, a = st[k]
            if 200 < a < 700 and 18 <= w <= 32 and 0.7 < w / h < 1.4 and x > 2 and im[int(cen[k][1]), int(cen[k][0])].min() > 110:
                return [float(cen[k][0]), float(cen[k][1])]
        return None

    def leer(self):
        i = min(int((time.time() - self.t0) * 30), len(self.s) - 1)
        while self.i <= i:
            ok, im = self.cap.read()
            if ok:
                self.img = im
                self.laser = self.circulo_laser(im)
            self.i += 1
        return dict(zip(MOTORES, map(float, self.s[i]))), self.laser, self.img, 0.0


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
    ap.add_argument("--demo", type=int, default=None, help="episodio a reproducir sin robot")
    ap.add_argument("--dataset", default="pti_laser_H_centro", help="dataset del --demo (en hf_cache)")
    ap.add_argument("--captura", default=None, help="guarda una captura a los 12 s y sale (para pruebas)")
    ap.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador (ya esta abierto)")
    a = ap.parse_args()
    t_inicio = time.time()

    g = Gemelo(a.mision)
    fuente = Demo(a.demo, a.dataset) if a.demo is not None else Udp()
    registro: deque = deque(maxlen=7)
    registro.append((time.strftime("%H:%M:%S"), "Sistema listo. Manos humanas en zona: 0"))
    t_laser = t_suelta = 0.0
    n_mov, girar = 0, True
    laser_m = None
    web = Web()
    web.gemelo = g
    if not a.captura and not a.sin_navegador:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{PUERTO_WEB}/")
        print(f"[gemelo] abierto en el navegador: http://127.0.0.1:{PUERTO_WEB}/  (F11 pantalla completa, Ctrl+C aqui para salir)")

    while True:
        q, laser, cam, edad = fuente.leer()
        lm = px_a_robot(laser) if laser else None
        # vale cualquier punto al alcance del brazo (la mesa puede montarse en cualquier sitio),
        # menos junto al soporte: ahi esta el falso positivo conocido (DIARIO, mapa de calor)
        if lm and 0.08 < np.hypot(lm[0], lm[1]) < 0.60 and np.hypot(lm[0] - SOPORTE[0], lm[1] - SOPORTE[1]) > 0.05:
            t_laser = time.time()
            laser_m = lm
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

        vivo = edad is not None and edad < 1.0
        f = fase_actual(time.time() - t_laser < 1.0, g.cogido, t_suelta, pinza)
        cont = g.d.mocap_pos[g.mocap["contenedor"]]
        web.estado = {
            "vivo": bool(vivo), "edad": edad, "fase": int(f), "cogido": bool(g.cogido),
            "laser": bool(time.time() - t_laser < 1.0), "pinza": pinza, "movimientos": n_mov,
            "q": {k: round(float(v), 1) for k, v in (q or {}).items()},
            "punta_cm": [round(float(x), 1) for x in g.punta() * 100] if q else None,
            "registro": [f"{h}  {s}" for h, s in registro], "demo": a.demo is not None,
            "suelta_hace": (time.time() - t_suelta) if t_suelta else None,
            "hz": fuente.hz() if isinstance(fuente, Udp) else 30.0,
            # para la web 3D: poses de las mallas, vaso (centro) y laser, en metros del robot
            "poses": g.poses(), "vaso": [round(float(x), 4) for x in cont],
            "laser_m": laser_m if time.time() - t_laser < 1.0 else None,
            "destino": [round(float(x), 4) for x in g.d.mocap_pos[g.mocap["destino"]][:2]] if n_mov else None,
        }
        if cam is not None:
            web.publicar(cam, "camara")
        if getattr(fuente, "muneca_jpg", None) is not None:              # ya viene en jpg: se reenvia tal cual
            with web.cond:
                web.jpgs["muneca"] = fuente.muneca_jpg
                web.cond.notify_all()
            fuente.muneca_jpg = None
        # la vista clasica (MuJoCo + HUD dibujado) solo se calcula si alguien la esta mirando
        if a.captura or web.mirando("compuesta", "3d"):
            lienzo, vista = dibujar_hud(g, q, pinza, cam, f, vivo, registro, n_mov, girar, a.demo)
            if a.captura and time.time() - t_inicio > 12:
                cv2.imwrite(a.captura, lienzo)
                break
            web.publicar(lienzo)
            web.publicar(vista, "3d")
        time.sleep(0.02)
        while web.teclas:
            k = web.teclas.popleft()
            if k == "giro":
                girar = not girar
            elif k == "reiniciar":
                registro.clear(); n_mov = 0; t_suelta = 0.0
                g.reiniciar_contenedor()
            elif k == "mision":
                g = Gemelo("luna" if g.mision == "lab" else "lab")
                web.gemelo = g
        if isinstance(fuente, Demo) and fuente.i >= len(fuente.s):
            fuente = Demo(a.demo, a.dataset)              # la reproduccion vuelve a empezar de cero
            g.reiniciar_contenedor()
            registro.clear(); n_mov = 0; t_suelta = 0.0; t_laser = 0.0


def dibujar_hud(g, q, pinza, cam, f, vivo, registro, n_mov, girar, demo):
    """Vista clasica 1280x720 (en /clasico): MuJoCo a la izquierda y HUD a la derecha."""
    lienzo = np.zeros((H, W, 3), np.uint8)
    lienzo[:] = (14, 14, 16)
    vista = g.render(girar)
    lienzo[:, :VW] = vista
    titulo, sub, lema = MISIONES[g.mision]
    cv2.rectangle(lienzo, (18, 18), (440, 66), (0, 0, 0), -1)
    cv2.line(lienzo, (18, 18), (18, 66), NARANJA if g.mision == "lab" else VERDE, 3)
    texto(lienzo, titulo, (30, 38), 0.55, NARANJA if g.mision == "lab" else VERDE, 1)
    texto(lienzo, sub, (30, 58), 0.4, GRIS)
    if int(time.time() * 2) % 2 or not vivo:
        cv2.circle(lienzo, (VW - 150, 36), 6, ROJO if vivo else GRIS, -1)
    texto(lienzo, "EN DIRECTO" if vivo else "ESPERANDO ROBOT", (VW - 138, 41), 0.5, BLANCO if vivo else GRIS)
    texto(lienzo, "GEMELO DIGITAL  -  MuJoCo  -  copia las articulaciones reales", (20, VH - 20), 0.42, GRIS)
    esquinas(lienzo, 8, 8, VW - 8, VH - 8, (70, 70, 70))
    if demo is not None:
        texto(lienzo, f"REPRODUCCION episodio {demo}", (20, VH - 44), 0.45, CIAN)
    x0 = VW + 20
    texto(lienzo, "REAL  -  camara cenital", (x0, 34), 0.45, GRIS)
    if cam is not None:
        lienzo[44:404, x0:x0 + 480] = cv2.resize(cam, (480, 360))
    else:
        cv2.rectangle(lienzo, (x0, 44), (x0 + 480, 404), (40, 40, 40), 1)
        texto(lienzo, "sin imagen", (x0 + 190, 230), 0.5, GRIS)
    esquinas(lienzo, x0, 44, x0 + 480, 404, CIAN)
    for i, nombre in enumerate(("1 APUNTA", "2 COGE", "3 TRAZA", "4 DEJA")):
        bx = x0 + i * 122
        act = i == f
        cv2.rectangle(lienzo, (bx, 418), (bx + 114, 446), ROJO if act else (40, 40, 40), -1 if act else 1)
        texto(lienzo, nombre, (bx + 14, 438), 0.5, BLANCO if act else GRIS, 2 if act else 1)
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
    y += 26
    texto(lienzo, "REGISTRO DE TRAZABILIDAD", (x0, y), 0.42, NARANJA); y += 4
    for hora, s in list(registro):
        y += 17
        texto(lienzo, f"{hora}  {s}", (x0, y), 0.38, BLANCO)
    texto(lienzo, f"Movimientos: {n_mov}   Dosis operador: 0,00 uSv (simulada)   Manos en zona: 0",
          (x0, H - 34), 0.36, VERDE)
    texto(lienzo, "PTI  -  TU APUNTAS. EL ROBOT HACE EL RESTO.  -  " + lema, (x0, H - 14), 0.36, GRIS)
    return lienzo, vista


# ----------------------------------------------------------------------------- servidor web (MJPEG)
PUERTO_WEB = int(__import__("os").environ.get("PTI_PUERTO", "8765"))
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


WEB_DIR = AQUI / "web"                 # web nueva (Three.js, voz neuronal): /
WEB_HTML = AQUI / "gemelo_web.html"    # web anterior: /v1 ; la vista clasica sigue en /clasico
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".mp3": "audio/mpeg", ".woff2": "font/woff2", ".png": "image/png",
         ".svg": "image/svg+xml", ".jpg": "image/jpeg"}
LEROBOT = RAIZ / "lerobot"
TAREA = "pick up the cup, follow the laser and place it where the laser turns off"


class Lanzador:
    """Lanza desde la web los comandos de la demo (uno a la vez) y guarda su salida."""

    def __init__(self):
        self.proc, self.nombre, self.salida = None, None, deque(maxlen=300)
        self.t0, self.tiempos, self.seg = 0.0, deque(maxlen=300), None

    def vivo(self):
        return self.proc is not None and self.proc.poll() is None

    def estado(self):
        return {"nombre": self.nombre, "vivo": self.vivo(),
                "codigo": None if self.proc is None else self.proc.poll(), "salida": list(self.salida),
                "t": list(self.tiempos), "ahora": round(time.time() - self.t0, 1) if self.t0 else None,
                "segundos": self.seg, "id": int(self.t0 * 10)}

    def _linea(self, s):
        self.salida.append(s)
        self.tiempos.append(round(time.time() - self.t0, 1))

    def lanzar(self, nombre, args, segundos=None, env_extra=None):
        import os, subprocess, threading
        if self.vivo():
            return f"Ya hay algo en marcha ({self.nombre}). Páralo primero."
        env = dict(os.environ, HF_HOME=str(RAIZ / "hf_cache"), PYTHONUNBUFFERED="1",
                   PATH=r"E:\miniforge3\envs\ffmpeg8\Library\bin;" + os.environ.get("PATH", ""))
        env.update(env_extra or {})
        self.salida.clear(); self.tiempos.clear()
        self.t0, self.seg = time.time(), segundos
        self._linea(f"$ {nombre}")
        self.nombre = nombre
        self.proc = subprocess.Popen([sys.executable, *args], cwd=LEROBOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))

        def leer(p):
            for linea in p.stdout:
                linea = linea.rstrip().split("\r")[-1]       # barras de progreso: quedarse con lo ultimo
                if linea:
                    self._linea(linea[:300])
            self._linea(f"[fin: código {p.wait()}]")
        threading.Thread(target=leer, args=(self.proc,), daemon=True).start()
        return "ok"

    def parar(self):
        import signal, threading
        if not self.vivo():
            return "No hay nada en marcha."
        p = self.proc
        self._linea("[PARANDO: el robot se desconecta y suelta el par; sujeta el brazo si hace falta]")
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT)        # = Ctrl+C: cierre limpio de lerobot
        except Exception:
            p.terminate()

        def rematar():
            try:
                p.wait(timeout=12)
            except Exception:
                p.kill()
                self._linea("[forzado: proceso terminado]")
        threading.Thread(target=rematar, daemon=True).start()
        return "ok"


def gpu() -> dict | None:
    """Memoria y uso de la GPU (nvidia-smi). Si otra cosa la llena, ACT va a 0-2 Hz en vez de 30."""
    import subprocess
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4)
        n, u, t, ut = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"nombre": n, "usada_mb": int(u), "total_mb": int(t), "uso": int(ut)}
    except Exception:
        return None


def modelos_disponibles():
    out = []
    for p in sorted((LEROBOT / "outputs" / "nube").glob("*")):
        if (p / "model.safetensors").exists():
            out.append(f"outputs/nube/{p.name}")
    for p in sorted((LEROBOT / "outputs" / "train").glob("*/checkpoints/last/pretrained_model")):
        out.append(p.relative_to(LEROBOT).as_posix())
    return out


def puerto_follower():
    import subprocess
    r = subprocess.run([sys.executable, str(AQUI / "puertos.py")], capture_output=True, text=True, cwd=LEROBOT)
    for linea in r.stdout.splitlines():
        if linea.startswith("follower:"):
            return linea.split()[1]
    return None


def accion(lz: Lanzador, x: str, prm: dict) -> str:
    if x == "parar":
        return lz.parar()
    if x == "camara_aplicar":
        return lz.lanzar("Ajustar cámara (exposición)", [str(AQUI / "camara_laser.py"), "--aplicar"])
    if x == "camara_comprobar":
        return lz.lanzar("Comprobar cámara", [str(AQUI / "comprobar_camara.py")])
    if x == "puertos":
        return lz.lanzar("Buscar brazos (puertos)", [str(AQUI / "puertos.py")])
    if x == "probar":
        if prm.get("seguro") != "1":
            return "Falta confirmar que hay una persona con la mano en la alimentación."
        modelo = prm.get("modelo", "")
        if modelo not in modelos_disponibles():
            return f"Modelo desconocido: {modelo}"
        com = puerto_follower()
        if not com:
            return "No encuentro el follower (¿enchufado y con alimentación?)."
        g = gpu()
        if g and g["total_mb"] - g["usada_mb"] < 1500 and prm.get("ignorar_gpu") != "1":
            return (f"GPU_LLENA:La GPU tiene {g['usada_mb'] / 1024:.1f} de {g['total_mb'] / 1024:.1f} GB ocupados por otros "
                    "programas. Así el modelo va a 0-2 Hz y el brazo casi no se mueve (pasó a las 18:09: 14 s por paso). "
                    "Cierra lo que use la GPU (generación de voz, render de vídeo, juegos) y vuelve a pulsar Iniciar.")
        seg = str(max(5, min(300, int(prm.get("seg", "45") or 45))))
        args = [str(AQUI / "lerobot_laser.py"), "rollout", "--strategy.type=base", f"--policy.path={modelo}",
                "--robot.type=so101_follower", f"--robot.port={com}", "--robot.id=follower_puesto",
                "--robot.cameras={ top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, "
                "wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30} }",
                f"--task={TAREA}", f"--duration={seg}"]
        coef = prm.get("coef", "-0.05")
        # "async:<coef>": mismo suavizado, pero la red en un hilo aparte -> el bucle va a ~30 Hz
        # en vez de 8-14 Hz (ver EnsembleEnSegundoPlano en lerobot_laser.py)
        # SIEMPRE 30 Hz: todo suavizado va con la red en paralelo (con o sin "async:" en la web)
        env_extra = None
        if coef.startswith("async:"):
            coef = coef.split(":", 1)[1]
        if coef != "bloque10":
            env_extra = {"PTI_ENSEMBLE_ASYNC": "1"}
        args.append("--fps=30")
        if coef == "bloque10":
            args.append("--policy.n_action_steps=10")
        else:
            float(coef)
            args += ["--policy.n_action_steps=1", f"--policy.temporal_ensemble_coeff={coef}"]
        modo = f"{coef}, 30 Hz"
        return lz.lanzar(f"ROBOT: {modelo} ({modo}, {seg} s, {com})", args, segundos=int(seg), env_extra=env_extra)
    return f"Acción desconocida: {x}"


class Web:
    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.jpgs, self.teclas, self.cond = {}, deque(), threading.Condition()
        self.estado = {}
        self.lanzador = Lanzador()
        self.gemelo = None
        self.clientes: dict[str, int] = {}
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
                if self.path.split("?")[0] in ("/accion", "/proceso", "/modelos", "/gpu"):
                    from urllib.parse import parse_qs, urlparse
                    u = urlparse(self.path)
                    prm = {k: v[0] for k, v in parse_qs(u.query).items()}
                    if u.path == "/modelos":
                        r = modelos_disponibles()
                    elif u.path == "/gpu":
                        r = gpu()
                    elif u.path == "/proceso":
                        r = yo.lanzador.estado()
                    else:
                        try:
                            r = {"resultado": accion(yo.lanzador, prm.get("x", ""), prm)}
                        except Exception as e:
                            r = {"resultado": f"Error: {e}"}
                    return self._enviar(json.dumps(r).encode(), "application/json")
                if self.path.startswith("/stream"):
                    nombre = self.path.split("v=")[-1] if "v=" in self.path else "compuesta"
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
                    self.end_headers()
                    yo.clientes[nombre] = yo.clientes.get(nombre, 0) + 1
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
                    finally:
                        yo.clientes[nombre] -= 1
                if self.path.startswith("/escena"):
                    return self._enviar(json.dumps(yo.gemelo.escena()).encode(), "application/json")
                if self.path.startswith("/malla/"):
                    try:
                        gid = int(self.path.split("/")[-1].split(".")[0])
                        assert gid in yo.gemelo.geoms_visuales()
                    except Exception:
                        self.send_response(404); self.end_headers(); return
                    return self._enviar(yo.gemelo.malla(gid), "application/octet-stream")
                if self.path.startswith("/web/"):
                    ruta = (WEB_DIR / self.path[5:].split("?")[0]).resolve()
                    if WEB_DIR.resolve() not in ruta.parents or not ruta.is_file():
                        self.send_response(404); self.end_headers(); return
                    return self._enviar(ruta.read_bytes(), TIPOS.get(ruta.suffix, "application/octet-stream"))
                if self.path.startswith("/clasico") or not WEB_HTML.exists():
                    return self._enviar(PAGINA, "text/html; charset=utf-8")
                if self.path.startswith("/v1") or not (WEB_DIR / "index.html").exists():
                    return self._enviar(WEB_HTML.read_bytes(), "text/html; charset=utf-8")
                self._enviar((WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")

        self.srv = ThreadingHTTPServer(("127.0.0.1", PUERTO_WEB), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def mirando(self, *nombres: str) -> bool:
        return any(self.clientes.get(n, 0) > 0 for n in nombres)

    def publicar(self, img, nombre: str = "compuesta"):
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            with self.cond:
                self.jpgs[nombre] = buf.tobytes()
                self.cond.notify_all()


if __name__ == "__main__":
    main()
