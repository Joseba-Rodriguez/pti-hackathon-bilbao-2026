"""Prueba del operador automatico: una toma completa (entregar -> Esperanza se la toma -> recoger).

    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_test.py            (con ventana)
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_test.py --sin-ventana --tomas 3
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

import auto_expert as ax
import esperanza_expert as ee
import esperanza_scene as es

FPS = 30


def run_traj(robot, traj, on_frame=None):
    t_next = time.perf_counter()
    for i in range(int((traj.duration + 0.4) * FPS)):
        a = traj(i / FPS)
        robot.send_action({f"{k}.pos": v for k, v in a.items()})
        if on_frame:
            on_frame(i)
        t_next += 1 / FPS
        time.sleep(max(0.0, t_next - time.perf_counter()))
    return traj.final


def esperanza_se_la_toma(robot, i, rng, espera=1.0):
    """Lo que hace la persona: coge el vasito, se toma la dosis y lo devuelve a la marca (no exacto)."""
    robot.park_cup(i)
    time.sleep(espera)
    robot.take_dose(i)
    d = rng.uniform(0, 0.012) * np.array([np.cos(a := rng.uniform(0, 2 * np.pi)), np.sin(a)])
    robot.place_cup(i, es.SPOT + d, float(rng.uniform(-np.pi, np.pi)))
    time.sleep(0.8)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tomas", type=int, default=1)
    p.add_argument("--sin-ventana", action="store_true")
    p.add_argument("--fotos", default=None, help="carpeta donde guardar fotos de cada fase")
    args = p.parse_args()
    rng = np.random.default_rng(1)
    robot = es.EsperanzaRobot(es.EsperanzaRobotConfig(onscreen=not args.sin_ventana, settle_s=2.0))
    robot.connect()
    expert = ee.EsperanzaExpert(seed=1)
    fotos = Path(args.fotos) if args.fotos else None
    if fotos:
        fotos.mkdir(parents=True, exist_ok=True)

    def foto(name):
        if fotos:
            from PIL import Image
            Image.fromarray(robot.render_top()).save(fotos / f"{name}.png")

    last = dict(ax.HOME)
    ok_total = 0
    for toma in range(args.tomas):
        i = ee.front_cup(robot)
        if i is None:
            print("  el cargador esta vacio")
            break
        foto(f"{toma}_0_inicio")
        b, axis = ee.cup_frame(robot, i)
        last = run_traj(robot, ax.Trajectory(last, expert.plan("entregar", b, axis)))
        time.sleep(0.5)
        on = robot.cup_on_spot()
        vista = es.mirar_marca(robot.model, robot.data, robot.render_top())
        nxt = ee.front_cup(robot)
        print(f"  entregar: vasito {i} ({robot.cup_specs[i].toma}) en la marca: {on == i} | camara: {vista} | "
              f"siguiente en el bolsillo: {nxt}", flush=True)
        foto(f"{toma}_1_entregado")
        if on != i:
            continue
        esperanza_se_la_toma(robot, i, rng)
        vista = es.mirar_marca(robot.model, robot.data, robot.render_top())
        print(f"  Esperanza lo devuelve. camara: {vista}", flush=True)
        foto(f"{toma}_2_devuelto")
        b, axis = ee.cup_frame(robot, i)
        last = run_traj(robot, ax.Trajectory(last, expert.plan("recoger", b, axis)))
        time.sleep(0.8)
        en_caja = robot.cup_in_box(i)
        print(f"  recoger: vasito {i} en la caja: {en_caja}", flush=True)
        foto(f"{toma}_3_recogido")
        ok_total += int(en_caja)
    print(f"RESULTADO: {ok_total}/{args.tomas} tomas completas")
    robot.disconnect()


if __name__ == "__main__":
    main()
