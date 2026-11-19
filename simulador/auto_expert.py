"""Operador automatico (experto programado) para el SO-101 simulado.

Sustituye a la persona que teleopera: calcula con cinematica inversa (IK) los
angulos de las articulaciones para llevar la pinza a cada punto de la tarea
"coger el cubo verde y meterlo en la caja", y los devuelve como acciones en las
mismas unidades que el brazo lider real (articulaciones -100..100, pinza 0..100).

Se registra como teleoperador ``so101_scripted`` para usarlo con lerobot-record,
igual que se usaria el brazo lider en el hackathon.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np

from lerobot.teleoperators.config import TeleoperatorConfig
from lerobot.teleoperators.teleoperator import Teleoperator

from so101_assets import BOX_POS, CUBE_HALF, MAT_TOP
from so101_mujoco_robot import (
    GRIPPER,
    JOINT_NAMES,
    MODEL_JOINT,
    SO101MujocoRobotConfig,
    _build_scene,
)

ARM = JOINT_NAMES[:5]  # todas menos la pinza

# Punto de agarre (TCP) en el sistema del cuerpo Fixed_Jaw: entre las dos
# mandibulas, cerca de la punta. Los dedos apuntan hacia -y local; las
# mandibulas cierran a lo largo de x local.
TCP_LOCAL = np.array([-0.016, -0.085, 0.0])

GRIP_OPEN = 75.0
GRIP_CLOSED = 0.0
GRIP_HOME = 50.0


class Kinematics:
    """Copia cinematica de la escena para calcular IK sin tocar la simulacion."""

    def __init__(self) -> None:
        self.model = _build_scene("", SO101MujocoRobotConfig())
        self.data = mujoco.MjData(self.model)
        self.body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "Fixed_Jaw")
        self.rot_w = 0.3  # peso de la orientacion en la IK
        self.adr, self.dof, self.rng, self.sign = {}, {}, {}, {}
        for name in JOINT_NAMES:
            mj_name, sign = MODEL_JOINT[name]
            jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, mj_name)
            self.adr[name] = int(self.model.jnt_qposadr[jid])
            self.dof[name] = int(self.model.jnt_dofadr[jid])
            self.rng[name] = tuple(float(v) for v in self.model.jnt_range[jid])
            self.sign[name] = sign

    # Conversion igual que en so101_mujoco_robot.py
    def to_units(self, name: str, q: float) -> float:
        lo, hi = self.rng[name]
        if name == GRIPPER:
            return 100.0 * (q - lo) / (hi - lo)
        return self.sign[name] * 200.0 * (q - 0.5 * (lo + hi)) / (hi - lo)

    def to_rad(self, name: str, u: float) -> float:
        lo, hi = self.rng[name]
        if name == GRIPPER:
            return lo + (hi - lo) * u / 100.0
        return 0.5 * (lo + hi) + self.sign[name] * (hi - lo) * u / 200.0

    def set_units(self, units: dict[str, float]) -> None:
        for name in JOINT_NAMES:
            self.data.qpos[self.adr[name]] = self.to_rad(name, units[name])
        mujoco.mj_kinematics(self.model, self.data); mujoco.mj_comPos(self.model, self.data)

    def tcp_pose(self) -> tuple[np.ndarray, np.ndarray]:
        R = self.data.xmat[self.body].reshape(3, 3)
        return self.data.xpos[self.body] + R @ TCP_LOCAL, R

    def _ik_once(self, target: np.ndarray, seed: dict[str, float], jaw_axis: np.ndarray,
                 iters: int = 400) -> tuple[dict[str, float], float]:
        """Lleva el TCP a ``target`` con los dedos apuntando hacia abajo y las
        mandibulas cerrando a lo largo de ``jaw_axis`` (vector horizontal).
        Devuelve (articulaciones en unidades, error de posicion en metros)."""
        units = dict(seed)
        self.set_units(units)
        R_goal = jaw_axis  # matriz de rotacion objetivo (ver goal_rot)
        jacp = np.zeros((3, self.model.nv))
        jacr = np.zeros((3, self.model.nv))
        cols = [self.dof[n] for n in ARM]
        q = np.array([self.data.qpos[self.adr[n]] for n in ARM])
        for _ in range(iters):
            pos, R = self.tcp_pose()
            e_pos = target - pos
            # error de orientacion (eje-angulo aproximado)
            e_rot = 0.5 * (np.cross(R[:, 0], R_goal[:, 0]) + np.cross(R[:, 1], R_goal[:, 1])
                           + np.cross(R[:, 2], R_goal[:, 2]))
            if np.linalg.norm(e_pos) < 5e-4 and np.linalg.norm(e_rot) < 1e-2:
                break
            mujoco.mj_jac(self.model, self.data, jacp, jacr, pos, self.body)
            J = np.vstack([jacp[:, cols], self.rot_w * jacr[:, cols]])
            e = np.concatenate([e_pos, self.rot_w * e_rot])
            dq = J.T @ np.linalg.solve(J @ J.T + 1e-4 * np.eye(6), e)
            q = q + np.clip(dq, -0.2, 0.2)
            for i, n in enumerate(ARM):
                lo, hi = self.rng[n]
                q[i] = min(max(q[i], lo), hi)
                self.data.qpos[self.adr[n]] = q[i]
            mujoco.mj_kinematics(self.model, self.data); mujoco.mj_comPos(self.model, self.data)
        for i, n in enumerate(ARM):
            units[n] = self.to_units(n, q[i])
        pos, R = self.tcp_pose()
        rot_err = float(np.linalg.norm(R - R_goal))
        return units, float(np.linalg.norm(target - pos)) + 0.01 * rot_err

    def ik(self, target: np.ndarray, seed: dict[str, float], jaw_axis: np.ndarray
           ) -> tuple[dict[str, float], float]:
        """Prueba varias posturas de partida y se queda con la mejor
        (la primera que converge, empezando por la mas cercana a ``seed``)."""
        seeds = [seed, DOWN_SEED, DOWN_SEED | {"wrist_roll": 46.0}]
        rng = np.random.default_rng(0)
        seeds += [{n: DOWN_SEED[n] + rng.uniform(-30, 30) for n in ARM} | {GRIPPER: 50.0}
                  for _ in range(6)]
        best = None
        for s in seeds:
            u, err = self._ik_once(target, s, jaw_axis)
            if best is None or err < best[1]:
                best = (u, err)
            if err < 0.002:
                break
        return best


def goal_rot(xy: tuple[float, float], tilt_deg: float, flip: bool) -> np.ndarray:
    """Orientacion objetivo de la pinza: dedos hacia abajo, inclinados
    ``tilt_deg`` hacia fuera (alejandose de la base), mandibulas cerrando en
    direccion tangencial."""
    radial = np.array([xy[0], xy[1], 0.0])
    radial /= np.linalg.norm(radial)
    tang = np.cross([0.0, 0.0, 1.0], radial) * (-1.0 if flip else 1.0)
    t = np.radians(tilt_deg)
    finger = np.cos(t) * np.array([0.0, 0.0, -1.0]) + np.sin(t) * radial
    y = -finger  # los dedos apuntan hacia -y local
    x = tang
    return np.column_stack([x, y, np.cross(x, y)])


HOME = {n: 0.0 for n in ARM} | {GRIPPER: GRIP_HOME}
# Postura con la pinza apuntando hacia abajo sobre la mesa (encontrada por muestreo)
DOWN_SEED = {"shoulder_pan": 0.0, "shoulder_lift": -7.0, "elbow_flex": 18.0,
             "wrist_flex": 64.0, "wrist_roll": -46.0, GRIPPER: 50.0}


def plan_pick_place(kin: Kinematics, cube_xy: tuple[float, float],
                    rng: np.random.Generator | None = None) -> list[tuple[dict[str, float], float]]:
    """Lista de (pose objetivo en unidades, segundos para llegar a ella)."""
    rng = rng or np.random.default_rng()
    cube_z = MAT_TOP + CUBE_HALF
    cx, cy = cube_xy
    bx, by = BOX_POS[0], BOX_POS[1]

    chosen_flip: list[bool] = []

    def pose(x, y, z, grip, seed):
        # la inclinacion mas vertical posible que se alcance con precision;
        # el sentido de las mandibulas se decide una vez y se mantiene, para que
        # la muneca no de media vuelta con el cubo agarrado
        flips = chosen_flip or [False, True]
        best = None
        for tilt in (0, 10, 20, 30, 40, 50):
            for flip in flips:
                u, err = kin.ik(np.array([x, y, z]), seed, goal_rot((x, y), tilt, flip))
                jump = sum(abs(u[n] - seed[n]) for n in ARM) if seed is not HOME else 0.0
                score = err + abs(u["wrist_roll"]) / 2e4 + jump / 1e4
                if best is None or score < best[0]:
                    best = (score, u, err, flip)
            if best[2] < 0.004:
                break
        u, err, flip = best[1], best[2], best[3]
        if err > 0.01:
            raise RuntimeError(f"IK no alcanza ({x:.3f},{y:.3f},{z:.3f}): error {err*1000:.1f} mm")
        if not chosen_flip:
            chosen_flip.append(flip)
        u[GRIPPER] = grip
        return u

    # pequenas variaciones de velocidad, como haria una persona
    def t(base):
        return base * float(rng.uniform(0.9, 1.15))

    above = pose(cx, cy, cube_z + 0.08, GRIP_OPEN, HOME)
    down = pose(cx, cy, cube_z + 0.002, GRIP_OPEN, above)
    grasp = dict(down) | {GRIPPER: GRIP_CLOSED}
    lift = pose(cx, cy, cube_z + 0.10, GRIP_CLOSED, down)
    over_box = pose(bx, by, cube_z + 0.10, GRIP_CLOSED, lift)
    lower = pose(bx, by, cube_z + 0.05, GRIP_CLOSED, over_box)
    release = dict(lower) | {GRIPPER: GRIP_OPEN}
    retreat = pose(bx, by, cube_z + 0.12, GRIP_OPEN, lower)

    return [
        (above, t(2.0)),
        (down, t(1.2)),
        (grasp, t(0.8)),
        (grasp, 0.3),  # esperar a que cierre
        (lift, t(1.2)),
        (over_box, t(1.8)),
        (lower, t(0.8)),
        (release, t(0.6)),
        (retreat, t(0.8)),
        (HOME, t(1.8)),
    ]


class Trajectory:
    """Interpola suavemente (curva S) entre poses."""

    def __init__(self, start: dict[str, float], waypoints: list[tuple[dict[str, float], float]]):
        self.segments = []
        prev = start
        t0 = 0.0
        for goal, dur in waypoints:
            self.segments.append((t0, dur, prev, goal))
            t0 += dur
            prev = goal
        self.duration = t0
        self.final = prev

    def __call__(self, t: float) -> dict[str, float]:
        for t0, dur, a, b in self.segments:
            if t < t0 + dur:
                s = (t - t0) / dur
                s = s * s * (3 - 2 * s)
                return {n: a[n] + (b[n] - a[n]) * s for n in JOINT_NAMES}
        return dict(self.final)


# ---------------------------------------------------------------- teleop plugin
@TeleoperatorConfig.register_subclass("so101_scripted")
@dataclass
class SO101ScriptedTeleopConfig(TeleoperatorConfig):
    fps: int = 30


class SO101ScriptedTeleop(Teleoperator):
    """Teleoperador sin persona: reproduce la trayectoria planificada.

    El lanzador (auto_record.py) llama a ``start_episode(cube_xy)`` al empezar
    cada episodio y a ``go_home()`` en la fase de reinicio."""

    config_class = SO101ScriptedTeleopConfig
    name = "so101_scripted"

    def __init__(self, config: SO101ScriptedTeleopConfig):
        super().__init__(config)
        self.config = config
        self.kin: Kinematics | None = None
        self.traj: Trajectory | None = None
        self.tick = 0
        self.last = dict(HOME)
        self.rng = np.random.default_rng(0)
        self._connected = False

    @property
    def action_features(self) -> dict:
        return {f"{n}.pos": float for n in JOINT_NAMES}

    @property
    def feedback_features(self) -> dict:
        return {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        pass

    def connect(self, calibrate: bool = True) -> None:
        self.kin = Kinematics()
        self._connected = True

    events: dict | None = None  # lo asigna auto_record.py para terminar el episodio

    def start_episode(self, cube_xy: tuple[float, float]) -> float:
        self.traj = Trajectory(self.last, plan_pick_place(self.kin, cube_xy, self.rng))
        self.tick = 0
        return self.traj.duration

    def go_home(self) -> None:
        self.events = None
        self.traj = Trajectory(self.last, [(HOME, 1.5)])
        self.tick = 0

    def get_action(self) -> dict:
        if self.traj is not None:
            self.last = self.traj(self.tick / self.config.fps)
            self.tick += 1
            # trayectoria terminada (+0.5 s quieto): fin del episodio
            if self.events is not None and self.tick > (self.traj.duration + 0.5) * self.config.fps:
                self.events["exit_early"] = True
                self.events = None
        return {f"{n}.pos": float(self.last[n]) for n in JOINT_NAMES}

    def send_feedback(self, feedback: dict) -> None:
        pass

    def disconnect(self) -> None:
        self._connected = False
