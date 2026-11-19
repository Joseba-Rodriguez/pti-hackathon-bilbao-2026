"""Escena "Esperanza": cargador de tomas por gravedad para el SO-101 simulado.

Los vasitos llegan YA RELLENADOS (la familia prepara las tomas de la semana) y
esperan en fila en la rampa impresa. El primero queda en el bolsillo delantero,
apoyado contra el tope. El robot solo hace dos cosas:

  1. entregar: coge el primer vasito del bolsillo y lo deja en la marca verde.
     Al sacarlo, el siguiente baja solo por gravedad al bolsillo.
  2. recoger:  coge el vasito vacio de la marca verde y lo echa a la caja de usados.

Piezas: las STL de e:\\HACKATONLeRobot (rampa_cargador_esperanza.stl y
vasito_esperanza.stl, generadas por make_stl.py). Se dibujan con su malla real;
para el choque se usan cajas y cilindros con las MISMAS medidas (MuJoCo trata
una malla como su envolvente convexa, y el canal de la rampa es concavo).

Que es fisico y que es logica:
  * Fisico: brazo, vasitos, rampa (deslizamiento por gravedad), tope, marca, caja.
  * Agarre asistido (simplificacion): al cerrar la pinza sobre el vasito se
    "suelda" a la pinza y se suelta al abrirla. En el robot real lo hacen los
    nervios del vasito y el anillo superior; hay que probarlo en casa.
  * Esperanza (la persona) no esta simulada: el orquestador "se toma" la dosis
    ocultando las pastillas y devuelve el vasito vacio a la marca.
  * Rozamiento vasito-rampa = 0.10 (supuesto: cinta de PTFE). El real se mide con la probeta:
    la rampa a 10 grados necesita que el vasito deslice solo a <= 6 grados.

Medidas en metros; base del brazo = origen; +x hacia delante, +z arriba.
"""

from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mujoco
import numpy as np

import so101_mujoco_robot as smr
from lerobot.robots.config import RobotConfig

HERE = Path(__file__).resolve().parent
# Las STL estan en piezas/stl del repo (se buscan hacia arriba desde este fichero)
PIEZAS = next((d / "piezas" / "stl" for d in HERE.parents if (d / "piezas" / "stl").is_dir()), HERE)
STL_RAMPA = PIEZAS / "rampa_cargador_esperanza.stl"
STL_VASITO = PIEZAS / "vasito_esperanza.stl"
MAT_TOP = 0.007
MM = 0.001

# ------------------------------------------- medidas (copiadas de make_stl.py)
CUP_D, CUP_H, RIM_D, RIM_H, FOOT_D = 38.0, 55.0, 41.0, 6.0, 35.0
GAP, WALL = 5.0, 3.0
W_IN = RIM_D + GAP
POCKET_L, POCKET_ANGLE, BLEND_R = RIM_D + 4, 3.0, 40.0
SLOPE_L = 165.0
ANGLE = float(os.environ.get("ESPERANZA_ANGLE", "10"))

FLOOR0, SIDE_H, LIP_H = 6.0, 22.0, 3.0
CURB_H = float(os.environ.get("ESPERANZA_CURB_H", "25"))   # igual que make_stl.py (era 7: el primer vasito se volcaba)

MU = float(os.environ.get("ESPERANZA_MU", "0.10"))   # rozamiento vasito-rampa (medir con la probeta)
CUP_R = CUP_D / 2 * MM
CUP_HM = CUP_H * MM
RIM_R = RIM_D / 2 * MM

# ------------------------------------------------------------- distribucion
RAMP_X0 = 0.1475                  # borde delantero del bolsillo (cara interior del tope)
POCKET_C = np.array([RAMP_X0 + POCKET_L / 2 * MM, 0.0])   # centro del bolsillo (x = 0.17)
SPOT = np.array([0.188, -0.105])  # marca verde de entrega (Esperanza esta en el lado -y)
DELIVER_AIM = np.array([0.190, -0.115])  # donde apunta la pinza: el vasito cae ~1 cm al lado, justo en la marca
SPOT_R = 0.028
BOX_C = np.array([0.125, -0.205])  # caja de usados
BOX_IN, BOX_H, BOX_WALL = 0.085, 0.030, 0.003
TOP_CAM_POS = [0.17, -0.20, 0.50]   # casi encima de la marca: ve el fondo del vasito (vacio o lleno)
TOP_CAM_LOOK = [0.17, -0.07, 0.0]


@dataclass(frozen=True)
class Toma:
    key: str
    nombre: str
    rgba: tuple
    hue: float          # tono en OpenCV (0-180) para reconocerla con la camara


TOMAS = {
    "manana": Toma("manana", "manana", (0.95, 0.55, 0.08, 1), 15.0),
    "mediodia": Toma("mediodia", "mediodia", (0.12, 0.45, 0.90, 1), 106.0),
    "noche": Toma("noche", "noche", (0.38, 0.28, 0.85, 1), 125.0),
}
PILL_RGBA = [(0.85, 0.10, 0.45, 1), (0.15, 0.70, 0.25, 1), (0.90, 0.10, 0.10, 1)]


# ------------------------------------------------------------------ rampa
def floor_profile() -> list[tuple[float, float]]:
    """Superficie del suelo (x, z) en mm, en coordenadas de la STL (igual que make_stl.py)."""
    a0, a1 = math.radians(POCKET_ANGLE), math.radians(ANGLE)
    pts = [(0.0, FLOOR0)]
    half = BLEND_R * math.tan((a1 - a0) / 2)
    xb = POCKET_L - half * math.cos(a0)
    pts.append((xb, FLOOR0 + xb * math.tan(a0)))
    cx = xb - BLEND_R * math.sin(a0)
    cz = pts[-1][1] + BLEND_R * math.cos(a0)
    for k in range(1, 13):
        ang = a0 + (a1 - a0) * k / 12
        pts.append((cx + BLEND_R * math.sin(ang), cz - BLEND_R * math.cos(ang)))
    x2, z2 = pts[-1]
    L = POCKET_L + SLOPE_L
    pts.append((L, z2 + (L - x2) * math.tan(a1)))
    return pts


def ramp_point(s_mm: float) -> tuple[np.ndarray, float]:
    """Punto del suelo a ``s_mm`` de recorrido desde el tope y su pendiente (rad), en el mundo."""
    pts = floor_profile()
    acc = 0.0
    for (xa, za), (xb, zb) in zip(pts, pts[1:]):
        seg = math.hypot(xb - xa, zb - za)
        if acc + seg >= s_mm or (xb, zb) == pts[-1]:
            f = min(1.0, (s_mm - acc) / seg)
            x, z = xa + f * (xb - xa), za + f * (zb - za)
            return (np.array([RAMP_X0 + x * MM, 0.0, MAT_TOP + z * MM]),
                    math.atan2(zb - za, xb - xa))
        acc += seg
    raise ValueError(s_mm)


def quat_y(angle_rad: float) -> list[float]:
    return [math.cos(angle_rad / 2), 0.0, math.sin(angle_rad / 2), 0.0]


def yaw_quat(angle_rad: float) -> list[float]:
    return [math.cos(angle_rad / 2), 0.0, 0.0, math.sin(angle_rad / 2)]


def add_ramp(spec: mujoco.MjSpec) -> None:
    wb = spec.worldbody
    W = W_IN + 2 * WALL
    spec.add_mesh(name="rampa", file=str(STL_RAMPA), scale=[MM] * 3)
    # la STL tiene el canal en y = 0..W; aqui se centra en y = 0
    wb.add_geom(name="rampa_visual", type=mujoco.mjtGeom.mjGEOM_MESH, meshname="rampa",
                pos=[RAMP_X0, -W / 2 * MM, MAT_TOP], rgba=[0.42, 0.45, 0.50, 1],
                contype=0, conaffinity=0, group=1)

    def box(name, center, half, quat=(1, 0, 0, 0)):
        g = wb.add_geom(name=name, type=mujoco.mjtGeom.mjGEOM_BOX, size=list(half), pos=list(center),
                        quat=list(quat), rgba=[0.42, 0.45, 0.50, 0.0], group=3, contype=3, conaffinity=3)
        g.friction = [MU, 0.005, 0.0001]
        return g

    pts = floor_profile()
    th = 2.0  # mm de grosor del suelo de choque
    for i, ((xa, za), (xb, zb)) in enumerate(zip(pts, pts[1:])):
        a = math.atan2(zb - za, xb - xa)
        ln = math.hypot(xb - xa, zb - za)
        n = np.array([-math.sin(a), 0, math.cos(a)])
        mid = np.array([(xa + xb) / 2, 0, (za + zb) / 2]) - n * th / 2
        box(f"rampa_suelo_{i}", [RAMP_X0 + mid[0] * MM, 0, MAT_TOP + mid[2] * MM],
            [ln / 2 * MM + 0.0005, W / 2 * MM, th / 2 * MM], quat_y(-a))
        if xa >= POCKET_L - 0.01 or xb > POCKET_L:  # paredes laterales del tramo inclinado
            mid_w = np.array([(xa + xb) / 2, 0, (za + zb) / 2]) + n * SIDE_H / 2
            for sgn in (-1, 1):
                box(f"rampa_pared_{i}_{sgn}", [RAMP_X0 + mid_w[0] * MM, sgn * (W_IN + WALL) / 2 * MM,
                                               MAT_TOP + mid_w[2] * MM],
                    [ln / 2 * MM + 0.0005, WALL / 2 * MM, SIDE_H / 2 * MM], quat_y(-a))
    L = pts[-1][0]
    ztop = pts[-1][1]
    box("rampa_fondo", [RAMP_X0 + (L + WALL / 2) * MM, 0, MAT_TOP + (ztop + SIDE_H) / 2 * MM],
        [WALL / 2 * MM, W / 2 * MM, (ztop + SIDE_H) / 2 * MM])
    box("rampa_tope", [RAMP_X0 - WALL / 2 * MM, 0, MAT_TOP + (FLOOR0 + CURB_H) / 2 * MM],
        [WALL / 2 * MM, W / 2 * MM, (FLOOR0 + CURB_H) / 2 * MM])
    for sgn in (-1, 1):
        box(f"rampa_labio_{sgn}", [RAMP_X0 + POCKET_L / 2 * MM, sgn * (W_IN + WALL) / 2 * MM,
                                   MAT_TOP + (FLOOR0 + LIP_H) / 2 * MM],
            [POCKET_L / 2 * MM, WALL / 2 * MM, (FLOOR0 + LIP_H) / 2 * MM])


# ------------------------------------------------------------------ vasitos
@dataclass
class Vasito:
    """Estado inicial de un vasito en la escena."""
    toma: str
    donde: str = "rampa"          # "rampa" | "marca" | "caja"
    lleno: bool = True
    dxy: tuple = (0.0, 0.0)       # desplazamiento (marca/caja)
    yaw: float = 0.0


def add_cup(spec: mujoco.MjSpec, idx: int, cup: Vasito, ramp_slot: int) -> None:
    wb = spec.worldbody
    t = TOMAS[cup.toma]
    if cup.donde == "rampa":
        # el primero contra el tope; los demas detras, tocandose por el anillo
        # el de delante va casi derecho y los de la pendiente inclinados hacia delante:
        # entre el primero y el segundo hace falta mas hueco para que no se toquen arriba
        s = CUP_R / MM + 0.6 + (0 if ramp_slot == 0 else 62.0 + (ramp_slot - 1) * (RIM_D + 1.5))
        p, a = ramp_point(s)
        n = np.array([-math.sin(a), 0, math.cos(a)])
        pos = p + n * 0.0008
        quat = quat_y(-a)
    elif cup.donde == "marca":
        pos = np.array([SPOT[0] + cup.dxy[0], SPOT[1] + cup.dxy[1], MAT_TOP + 0.0004])
        quat = yaw_quat(cup.yaw)
    else:
        pos = np.array([BOX_C[0] + cup.dxy[0], BOX_C[1] + cup.dxy[1], MAT_TOP + 0.003 + 0.002 + 0.06 * ramp_slot])
        quat = yaw_quat(cup.yaw)
    b = wb.add_body(name=f"vasito_{idx}", pos=list(pos), quat=list(quat))
    b.add_freejoint(name=f"vasito_{idx}_libre")
    b.add_geom(name=f"vasito_{idx}_malla", type=mujoco.mjtGeom.mjGEOM_MESH, meshname="vasito",
               rgba=list(t.rgba), contype=0, conaffinity=0, mass=0.0, group=1)
    for name, r, z0, z1 in (("cuerpo", CUP_R, 0.001, CUP_HM - RIM_H * MM),
                            ("pie", FOOT_D / 2 * MM, 0.0, 0.0015),
                            ("anillo", RIM_R, CUP_HM - RIM_H * MM, CUP_HM)):
        g = b.add_geom(name=f"vasito_{idx}_{name}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[r, (z1 - z0) / 2, 0], pos=[0, 0, (z0 + z1) / 2],
                       rgba=[*t.rgba[:3], 0.0], mass=0.004, group=3, contype=3, conaffinity=3)
        g.friction = [MU, 0.005, 0.0001]
        g.solref = [0.01, 1.0]
    # pastillas (solo visuales): se ven desde la camara cenital
    for k in range(3):
        ang = 2 * math.pi * k / 3 + 0.4
        g = b.add_geom(name=f"vasito_{idx}_pastilla_{k}", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                       size=[0.0055, 0.0055, 0.0025],
                       pos=[0.0075 * math.cos(ang), 0.0075 * math.sin(ang), 0.0045],
                       rgba=list(PILL_RGBA[k]) if cup.lleno else [1, 1, 1, 0],
                       contype=0, conaffinity=0, mass=0.0, group=1)


def add_esperanza_workspace(spec: mujoco.MjSpec, cups: list[Vasito]) -> None:
    wb = spec.worldbody
    wb.add_geom(name="workspace_mat", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.22, 0.27, 0.0035],
                pos=[0.20, -0.05, 0.0035], rgba=[0.50, 0.40, 0.30, 1], contype=3, conaffinity=3)  # mantel liso (fondo uniforme)
    wb.add_geom(name="marca_verde", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[SPOT_R, 0.0004, 0],
                pos=[SPOT[0], SPOT[1], MAT_TOP + 0.0004], rgba=[0.10, 0.60, 0.30, 1],
                contype=0, conaffinity=0)
    # caja de usados (abierta por arriba)
    bx, by = BOX_C
    half_in = BOX_IN / 2
    caja_rgba = [0.55, 0.58, 0.66, 1]
    wb.add_geom(name="caja_fondo", type=mujoco.mjtGeom.mjGEOM_BOX,
                size=[half_in + BOX_WALL, half_in + BOX_WALL, 0.0015], pos=[bx, by, MAT_TOP + 0.0015], rgba=caja_rgba,
                contype=3, conaffinity=3)
    for i, (dx, dy, sx, sy) in enumerate(((half_in + BOX_WALL / 2, 0, BOX_WALL / 2, half_in + BOX_WALL),
                                          (-half_in - BOX_WALL / 2, 0, BOX_WALL / 2, half_in + BOX_WALL),
                                          (0, half_in + BOX_WALL / 2, half_in, BOX_WALL / 2),
                                          (0, -half_in - BOX_WALL / 2, half_in, BOX_WALL / 2))):
        wb.add_geom(name=f"caja_pared_{i}", type=mujoco.mjtGeom.mjGEOM_BOX, size=[sx, sy, BOX_H / 2],
                    pos=[bx + dx, by + dy, MAT_TOP + BOX_H / 2], rgba=caja_rgba,
                    contype=3, conaffinity=3)

    add_ramp(spec)
    spec.add_mesh(name="vasito", file=str(STL_VASITO), scale=[MM] * 3)
    n_ramp = n_box = 0
    for i, c in enumerate(cups):
        if c.donde == "rampa":
            add_cup(spec, i, c, n_ramp)
            n_ramp += 1
        elif c.donde == "caja":
            add_cup(spec, i, c, n_box)
            n_box += 1
        else:
            add_cup(spec, i, c, 0)

    fwd = np.array(TOP_CAM_LOOK) - np.array(TOP_CAM_POS); fwd /= np.linalg.norm(fwd)
    xa = np.cross(fwd, [0, 0, 1.0]); xa /= np.linalg.norm(xa)
    tc = wb.add_camera(name="top_cam", pos=TOP_CAM_POS, fovy=55.0)
    tc.alt.type = mujoco.mjtOrientation.mjORIENTATION_XYAXES
    tc.alt.xyaxes = list(xa) + list(np.cross(-fwd, xa))
    look = np.array([0.18, -0.06, 0.05])
    az, el, dist = math.radians(215), math.radians(-28), 0.66
    fwd = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    xa = np.cross(fwd, [0, 0, 1.0]); xa /= np.linalg.norm(xa)
    ya = np.cross(-fwd, xa)
    cam = wb.add_camera(name="vista_general", pos=list(look - dist * fwd), fovy=45.0)
    cam.alt.type = mujoco.mjtOrientation.mjORIENTATION_XYAXES
    cam.alt.xyaxes = list(xa) + list(ya)

    for i in range(len(cups)):
        eq = spec.add_equality(name=f"agarre_{i}", type=mujoco.mjtEq.mjEQ_WELD,
                               objtype=mujoco.mjtObj.mjOBJ_BODY, name1="Fixed_Jaw", name2=f"vasito_{i}")
        eq.active = False


def default_cups() -> list[Vasito]:
    """Como en el video: noche delante y el resto de la semana detras."""
    return [Vasito("noche"), Vasito("manana"), Vasito("mediodia"), Vasito("noche")]


# ------------------------------------------------------------ robot plugin
@RobotConfig.register_subclass("esperanza_mujoco")
@dataclass
class EsperanzaRobotConfig(smr.SO101MujocoRobotConfig):
    image_width: int = 320
    image_height: int = 240
    image_camera: str | None = "sim_cam"
    top_camera: str | None = "top_cam"
    preview_cameras: bool = False
    settle_s: float = 1.2


class EsperanzaRobot(smr.SO101MujocoRobot):
    config_class = EsperanzaRobotConfig
    name = "esperanza_mujoco"
    cups: list[Vasito] = []

    def connect(self, calibrate: bool = True) -> None:
        cups = list(self.cups or default_cups())
        self.cup_specs = cups

        def build(model_path, config):
            spec = smr.menagerie_spec()
            add_esperanza_workspace(spec, cups)
            smr._add_camera_module(spec)
            model = spec.compile()
            smr.harden_mesh_contacts(model)
            return model

        original = smr._build_scene
        smr._build_scene = build
        try:
            super().connect(calibrate)
        finally:
            smr._build_scene = original
        m = self.model
        self.cup_body = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"vasito_{i}") for i in range(len(cups))]
        self.cup_qadr = [int(m.jnt_qposadr[m.body_jntadr[b]]) for b in self.cup_body]
        self.cup_vadr = [int(m.jnt_dofadr[m.body_jntadr[b]]) for b in self.cup_body]
        self.pill_geoms = [[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, f"vasito_{i}_pastilla_{k}")
                            for k in range(3)] for i in range(len(cups))]
        self.eq_id = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, f"agarre_{i}") for i in range(len(cups))]
        self.fj_body = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "Fixed_Jaw")
        self.cup_geoms = [[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, f"vasito_{i}_{n}")
                           for n in ("cuerpo", "pie", "anillo")] for i in range(len(cups))]
        self.held: int | None = None
        self._ops: list = []
        self._ops_lock = threading.Lock()
        self._stop_watch = threading.Event()
        threading.Thread(target=self._watch, daemon=True, name="agarre").start()
        time.sleep(self.config.settle_s)   # que los vasitos se asienten en la rampa

    # ---- operaciones en el hilo de simulacion
    def _run_on_sim(self, fn) -> None:
        with self._ops_lock:
            self._ops.append(fn)
        self._reset_objects_requested = True

    def _perform_scene_reset(self) -> None:
        with self._ops_lock:
            ops, self._ops = self._ops, []
        for fn in ops:
            fn()
        mujoco.mj_forward(self.model, self.data)

    # ---- agarre asistido
    def tcp(self) -> np.ndarray:
        from auto_expert import TCP_LOCAL
        R = self.data.xmat[self.fj_body].reshape(3, 3)
        return self.data.xpos[self.fj_body] + R @ TCP_LOCAL

    def _check_grasp(self) -> None:
        d = self.data
        grip = self._to_units("gripper", float(d.qpos[self._qposadr["gripper"]]))
        if self.held is None and grip < 45:
            tcp = self.tcp()
            for i, b in enumerate(self.cup_body):
                R = d.xmat[b].reshape(3, 3)
                axis_pt = d.xpos[b] + R[:, 2] * np.clip(R[:, 2] @ (tcp - d.xpos[b]), 0, CUP_HM)
                if np.linalg.norm(axis_pt - tcp) < 0.010 and 0.012 < R[:, 2] @ (tcp - d.xpos[b]) < CUP_HM:
                    self.held = i
                    self._run_on_sim(lambda i=i: self._weld(i, True))
                    break
        elif self.held is not None and grip > 52:
            i, self.held = self.held, None
            self._run_on_sim(lambda i=i: self._weld(i, False))

    def _weld(self, i: int, on: bool) -> None:
        e = self.eq_id[i]
        if on:
            # Agarre que se autocentra: el vasito queda con su eje en el eje de los
            # dedos y centrado entre ellos (como lo centran los nervios contra las
            # almohadillas). Corrige unos milimetros y unos grados, no mas.
            d = self.data
            b, f = self.cup_body[i], self.fj_body
            Rf = d.xmat[f].reshape(3, 3)
            tcp = self.tcp()
            up = Rf[:, 1] / np.linalg.norm(Rf[:, 1])          # los dedos apuntan a -y local
            s = float((d.xpos[b] - tcp) @ up)                   # el fondo queda a esta distancia del TCP
            bottom = tcp + up * s
            x = Rf[:, 0] - (Rf[:, 0] @ up) * up
            x /= np.linalg.norm(x)
            Rc = np.column_stack([x, np.cross(up, x), up])
            qc = np.zeros(4)
            mujoco.mju_mat2Quat(qc, Rc.flatten())
            q, v = self.cup_qadr[i], self.cup_vadr[i]
            d.qpos[q:q + 3] = bottom
            d.qpos[q + 3:q + 7] = qc
            d.qvel[v:v + 6] = 0.0
            Rrel = Rf.T @ Rc
            rel_q = np.zeros(4)
            mujoco.mju_mat2Quat(rel_q, Rrel.flatten())
            self.model.eq_data[e][:3] = 0.0
            self.model.eq_data[e][3:6] = Rf.T @ (bottom - d.xpos[f])
            self.model.eq_data[e][6:10] = rel_q
            self.model.eq_data[e][10] = 1.0
        self.data.eq_active[e] = 1 if on else 0
        # mientras va sujeto, el vasito no choca con la pinza (si no, los dedos que se
        # cierran "dentro" de el lo empujan al soltar); con la mesa y la rampa, si
        for g in self.cup_geoms[i]:
            self.model.geom_contype[g] = 2 if on else 3
            self.model.geom_conaffinity[g] = 2 if on else 3

    def _watch(self) -> None:
        while not self._stop_watch.is_set():
            if self.data is not None:
                self._check_grasp()
            time.sleep(0.01)

    def disconnect(self) -> None:
        self._stop_watch.set()
        super().disconnect()

    # ---- lo que hace Esperanza (no simulada): tomarse la dosis y devolver el vasito
    def take_dose(self, i: int) -> None:
        for g in self.pill_geoms[i]:
            self.model.geom_rgba[g][3] = 0.0

    def place_cup(self, i: int, xy, yaw: float = 0.0, z: float | None = None) -> None:
        def op():
            q, v = self.cup_qadr[i], self.cup_vadr[i]
            self.data.qpos[q:q + 3] = [xy[0], xy[1], MAT_TOP + 0.0004 if z is None else z]
            self.data.qpos[q + 3:q + 7] = yaw_quat(yaw)
            self.data.qvel[v:v + 6] = 0.0
        self._run_on_sim(op)

    def park_cup(self, i: int) -> None:
        """La persona se lleva el vasito (fuera de la mesa)."""
        self.place_cup(i, (-0.25, -0.30 - 0.06 * i), 0.0)

    # ---- medidas para evaluar
    def cup_pos(self, i: int) -> np.ndarray:
        return self.data.xpos[self.cup_body[i]].copy()

    def cup_tilt_deg(self, i: int) -> float:
        R = self.data.xmat[self.cup_body[i]].reshape(3, 3)
        return float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1))))

    def cup_in_pocket(self) -> int | None:
        for i in range(len(self.cup_body)):
            p = self.cup_pos(i)
            if np.hypot(p[0] - POCKET_C[0], p[1] - POCKET_C[1]) < 0.012 and p[2] < MAT_TOP + 0.012:
                return i
        return None

    def cup_on_spot(self, tol: float = 0.020) -> int | None:
        for i in range(len(self.cup_body)):
            p = self.cup_pos(i)
            if np.hypot(p[0] - SPOT[0], p[1] - SPOT[1]) < tol and p[2] < MAT_TOP + 0.004 and self.cup_tilt_deg(i) < 10:
                return i
        return None

    def cup_in_box(self, i: int) -> bool:
        p = self.cup_pos(i)
        return bool(abs(p[0] - BOX_C[0]) < BOX_IN / 2 and abs(p[1] - BOX_C[1]) < BOX_IN / 2 and p[2] < MAT_TOP + 0.09)  # puede quedar encima de otro

    def render_top(self, width=640, height=480) -> np.ndarray:
        self.model.vis.global_.offwidth = max(self.model.vis.global_.offwidth, width)
        self.model.vis.global_.offheight = max(self.model.vis.global_.offheight, height)
        ren = mujoco.Renderer(self.model, height, width)
        ren.update_scene(self.data, camera="top_cam")
        img = ren.render().copy()
        ren.close()
        return img


# -------------------------------------------------------------- vision
def project_top(model, data, p_world, width: int, height: int) -> tuple[float, float]:
    cid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, "top_cam")
    pos = data.cam_xpos[cid]
    R = data.cam_xmat[cid].reshape(3, 3)
    pc = R.T @ (np.asarray(p_world) - pos)
    f = (height / 2) / np.tan(np.radians(model.cam_fovy[cid]) / 2)
    return width / 2 + f * pc[0] / -pc[2], height / 2 - f * pc[1] / -pc[2]


def mirar_marca(model, data, img: np.ndarray) -> dict:
    """Lo que ve la camara cenital en la marca verde: {'toma': key|None, 'llena': bool|None}.

    Mismo metodo que en el puesto real con OpenCV: recorte alrededor de la
    marca, tono dominante del vasito -> que toma es, y pixeles de colores de
    pastilla dentro de la boca -> llena o vacia.
    """
    h, w = img.shape[:2]
    u, v = project_top(model, data, [SPOT[0], SPOT[1], MAT_TOP + CUP_HM], w, h)
    u2, v2 = project_top(model, data, [SPOT[0] + 0.03, SPOT[1], MAT_TOP + CUP_HM], w, h)
    px_per_m = np.hypot(u2 - u, v2 - v) / 0.03
    r_out = int(0.034 * px_per_m)
    crop = img[max(0, int(v) - r_out):int(v) + r_out, max(0, int(u) - r_out):int(u) + r_out]
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    sat = (hsv[..., 1] > 110) & (hsv[..., 2] > 60)
    green = sat & (np.abs(hsv[..., 0].astype(int) - 60) < 15)   # la marca verde y la pastilla verde
    best, best_n = None, 0
    for key, t in TOMAS.items():
        n = int((sat & (np.abs(hsv[..., 0].astype(int) - t.hue) < 8)).sum())
        if n > best_n:
            best, best_n = key, n
    if best_n < 0.08 * crop.shape[0] * crop.shape[1]:
        return {"toma": None, "llena": None}
    # boca del vasito: buscar el centro por el color del vasito y mirar dentro
    mask = (sat & (np.abs(hsv[..., 0].astype(int) - TOMAS[best].hue) < 8)).astype(np.uint8)
    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()
    r_in = 0.013 * px_per_m
    yy, xx = np.mgrid[:crop.shape[0], :crop.shape[1]]
    inner = (yy - cy) ** 2 + (xx - cx) ** 2 < r_in ** 2
    hue = hsv[..., 0].astype(int)
    pill = sat & inner & ((np.abs(hue - 165) < 12) | (hue < 6) | green)
    return {"toma": best, "llena": bool(pill.sum() > 0.04 * inner.sum())}
