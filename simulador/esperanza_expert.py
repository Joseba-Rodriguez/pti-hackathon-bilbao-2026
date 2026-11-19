"""Operador automatico (hace de "persona con el brazo leader") para las dos habilidades:

  entregar: HOME -> coger el primer vasito del bolsillo del cargador -> sacarlo
            de lado (por encima del labio bajo) -> dejarlo en la marca verde -> HOME
  recoger:  HOME -> coger el vasito vacio de la marca -> soltarlo dentro de la
            caja de usados -> HOME

El experto conoce la posicion real del vasito (la simulacion se la da); la
politica ACT que aprende de el solo ve las camaras y las articulaciones.
En el hackathon esto lo hace una persona teleoperando con el brazo leader.
"""

from __future__ import annotations

import numpy as np

import auto_expert as ax
import esperanza_scene as es
from so101_mujoco_robot import GRIPPER

SKILLS = ("entregar", "recoger")
TASK_TEXT = {
    "entregar": "take the first cup from the loader and place it on the green mark",
    "recoger": "pick up the empty cup from the green mark and drop it into the used box",
}

OPEN = 65.0             # ~52 mm entre dedos: pasa el anillo de 41 mm
RELEASE = 80.0          # al soltar se abre mas, para no arrastrar el vasito al subir
HOLD = 0.0              # cerrar del todo (el agarre asistido sujeta el vasito)
GRIP_H = 0.030          # altura de agarre sobre el fondo del vasito (por debajo del anillo)
LIFT = 0.050            # cuanto se levanta el vasito al sacarlo del bolsillo
CARRY_BOTTOM = 0.070    # fondo del vasito durante el transporte
DROP_BOTTOM = 0.052     # fondo del vasito al soltarlo en la caja (paredes de 3,7 cm)


class _Kin(ax.Kinematics):
    """IK sobre un punto fijo a la pinza (por defecto el TCP; con el vasito agarrado, su fondo)."""
    point = ax.TCP_LOCAL

    def tcp_pose(self):
        R = self.data.xmat[self.body].reshape(3, 3)
        return self.data.xpos[self.body] + R @ self.point, R


class EsperanzaExpert:
    def __init__(self, seed: int = 0):
        self.kin = _Kin()
        self.rng = np.random.default_rng(seed)
        self.flip: bool | None = None

    def t(self, base: float) -> float:
        return base * float(self.rng.uniform(0.9, 1.15))

    def pose(self, target, grip, seed, tilts=(0, 5, 10, 15, 20, 30, 40), point=None):
        self.kin.point = ax.TCP_LOCAL if point is None else point
        try:
            return self._pose(target, grip, seed, tilts)
        finally:
            self.kin.point = ax.TCP_LOCAL

    def _pose(self, target, grip, seed, tilts):
        flips = [self.flip] if self.flip is not None else [False, True]
        best = None
        for tilt in tilts:
            for flip in flips:
                u, err = self.kin.ik(np.asarray(target), seed, ax.goal_rot((target[0], target[1]), tilt, flip))
                jump = sum(abs(u[n] - seed[n]) for n in ax.ARM)
                score = err + abs(u["wrist_roll"]) / 2e4 + jump / 1e4
                if best is None or score < best[0]:
                    best = (score, u, err, flip)
            if best[2] < 0.004:
                break
        _, u, err, flip = best
        self.kin.set_units(u)
        pos, _ = self.kin.tcp_pose()
        err = float(np.linalg.norm(np.asarray(target) - pos))
        if err > 0.006:
            raise RuntimeError(f"IK no alcanza {np.round(target, 3)}: error {err * 1000:.1f} mm")
        if self.flip is None:
            self.flip = flip
        u = dict(u)
        u[GRIPPER] = grip
        return u

    def _grasp_point(self, bottom: np.ndarray, axis: np.ndarray) -> np.ndarray:
        return bottom + axis * GRIP_H

    def plan(self, skill: str, cup_bottom: np.ndarray, cup_axis: np.ndarray):
        errors = []
        for flip in (False, True):
            self.flip = flip
            try:
                return self._plan(skill, np.asarray(cup_bottom), np.asarray(cup_axis))
            except RuntimeError as e:
                errors.append(f"flip={flip}: {e}")
        raise RuntimeError("; ".join(errors))

    def _plan(self, skill, bottom, axis):
        home = dict(ax.HOME)
        g = self._grasp_point(bottom, axis)
        # dedos verticales: el agarre endereza el vasito del bolsillo (se apoya unos grados en el
        # tope) y asi viaja y se deja derecho. Si la pinza lo coge inclinado, lo deja inclinado.
        grasp_tilts = (0, 3, 6, 10)
        above = self.pose(g + axis * 0.06, OPEN, home, tilts=grasp_tilts)
        down = self.pose(g, OPEN, above, tilts=grasp_tilts)
        grasp = dict(down) | {GRIPPER: HOLD}
        lift = self.pose(g + [0, 0, LIFT], HOLD, down)
        # donde queda el fondo del vasito en la pinza (el agarre lo centra en el eje de los dedos)
        self.kin.set_units(down)
        R = self.kin.data.xmat[self.kin.body].reshape(3, 3)
        xb = self.kin.data.xpos[self.kin.body]
        tcp = xb + R @ ax.TCP_LOCAL
        up = R[:, 1]
        bottom_local = R.T @ (tcp + up * float((bottom - tcp) @ up) - xb)

        if skill == "entregar":
            # punto de entrega con una pequena variacion, como haria una persona

            sx, sy = es.DELIVER_AIM + self.rng.normal(0, 0.002, 2)
            tgt = np.array([sx, sy, es.MAT_TOP + GRIP_H])
            carry = self.pose([sx, sy, CARRY_BOTTOM], HOLD, lift, point=bottom_local)
            # el fondo del vasito queda 6 mm por encima de la mesa: cae suave, sin empujar la mesa
            place = self.pose([sx, sy, es.MAT_TOP + 0.006], HOLD, carry, tilts=(0, 5, 10), point=bottom_local)
            release = dict(place) | {GRIPPER: RELEASE}
            # apartar la mandibula fija del anillo (hacia la movil, que ya esta abierta) y
            # subir en vertical (tramos cortos: la interpolacion articular no va recta)
            self.kin.set_units(place)
            away = self.kin.data.xmat[self.kin.body].reshape(3, 3)[:, 0] * 0.007   # la fija esta en +x local
            away[2] = 0.0
            side = self.pose(tgt + [0, 0, 0.006] + away, RELEASE, place)
            up1 = self.pose(tgt + [0, 0, 0.030] + away, RELEASE, side)
            up2 = self.pose(tgt + [0, 0, 0.060] + away, RELEASE, up1)
            up3 = self.pose(tgt + [0, 0, 0.095] + away, RELEASE, up2)
            return [(above, self.t(1.6)), (down, self.t(1.0)), (grasp, self.t(0.6)), (grasp, 0.3),
                    (lift, self.t(0.9)), (carry, self.t(1.3)), (place, self.t(0.9)),
                    (release, self.t(0.5)), (side, self.t(0.3)), (up1, self.t(0.4)), (up2, self.t(0.4)),
                    (up3, self.t(0.4)),
                    (home, self.t(1.4))]

        # recoger: a la caja de usados (punto de suelta con variacion)
        bx, by = es.BOX_C + self.rng.uniform(-0.012, 0.012, 2)
        over = self.pose([bx, by, CARRY_BOTTOM], HOLD, lift, point=bottom_local)
        low = self.pose([bx, by, DROP_BOTTOM], HOLD, over, point=bottom_local)
        release = dict(low) | {GRIPPER: OPEN}
        up = self.pose(np.array([bx, by, DROP_BOTTOM + GRIP_H + 0.05]), OPEN, low)
        return [(above, self.t(1.6)), (down, self.t(1.0)), (grasp, self.t(0.6)), (grasp, 0.3),
                (lift, self.t(0.8)), (over, self.t(1.4)), (low, self.t(0.7)),
                (release, self.t(0.4)), (up, self.t(0.6)), (home, self.t(1.4))]


def cup_frame(robot: es.EsperanzaRobot, i: int) -> tuple[np.ndarray, np.ndarray]:
    """Fondo y eje del vasito i (lo que el experto 've')."""
    R = robot.data.xmat[robot.cup_body[i]].reshape(3, 3)
    return robot.cup_pos(i), R[:, 2].copy()


def front_cup(robot: es.EsperanzaRobot) -> int | None:
    """El vasito del bolsillo (el mas cercano al tope que siga en la rampa)."""
    best = None
    for i in range(len(robot.cup_body)):
        p = robot.cup_pos(i)
        if es.RAMP_X0 - 0.005 < p[0] < es.RAMP_X0 + 0.25 and abs(p[1]) < 0.03 and p[2] > es.MAT_TOP + 0.003:
            if best is None or p[0] < robot.cup_pos(best)[0]:
                best = i
    return best
