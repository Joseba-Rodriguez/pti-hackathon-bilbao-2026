"""Evalua cada habilidad ACT por separado: N intentos, cada uno en una escena nueva.

Mismo criterio que al grabar: entregar = el vasito queda derecho en la marca y
la rampa sigue en orden; recoger = el vasito acaba dentro de la caja.
Anota tambien en que fase falla, que es lo que se ensena en el pitch.

    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_eval.py --intentos 10
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_eval.py --skills entregar --checkpoint 020000
"""

from __future__ import annotations

import argparse
import time

import numpy as np

import esperanza_expert as ee
import esperanza_record as er
import esperanza_scene as es
from esperanza_politica import PolicySkill


def fase(robot, skill, i, start_pos) -> str:
    p = robot.cup_pos(i)
    moved = np.linalg.norm(p - start_pos) > 0.01
    if skill == "entregar":
        if robot.cup_on_spot() == i:
            return "OK"
        if not moved:
            return "no lo coge"
        if robot.cup_tilt_deg(i) > 30:
            return "lo tumba"
        return "lo deja fuera de la marca"
    if robot.cup_in_box(i):
        return "OK"
    if not moved:
        return "no lo coge"
    return "lo suelta fuera de la caja"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skills", nargs="*", default=list(ee.SKILLS))
    p.add_argument("--intentos", type=int, default=10)
    p.add_argument("--checkpoint", default=None, help="p. ej. 020000 (por defecto, el ultimo)")
    p.add_argument("--n-action-steps", type=int, default=None)
    p.add_argument("--seed", type=int, default=1234, help="distinta de la de grabacion: escenas nuevas")
    args = p.parse_args()
    rng = np.random.default_rng(args.seed)

    tabla = {}
    for skill in args.skills:
        pol = PolicySkill(skill, args.checkpoint, args.n_action_steps)
        res = []
        while len(res) < args.intentos:
            cups, reloads = er.random_scene(skill, rng)
            es.EsperanzaRobot.cups = cups
            robot = es.EsperanzaRobot(es.EsperanzaRobotConfig(onscreen=False, settle_s=1.5))
            robot.connect()
            for _ in range(reloads):
                robot.park_cup(ee.front_cup(robot))
                time.sleep(1.8)
            i = ee.front_cup(robot) if skill == "entregar" else robot.cup_on_spot()
            if i is None:
                robot.disconnect()
                continue
            start = robot.cup_pos(i)
            pol.run(robot)
            time.sleep(0.4)
            f = fase(robot, skill, i, start)
            res.append(f)
            print(f"  {skill} #{len(res)}: {f}", flush=True)
            robot.disconnect()
        tabla[skill] = res

    print("\nRESUMEN" + (f" (checkpoint {args.checkpoint})" if args.checkpoint else " (ultimo checkpoint)"))
    for skill, res in tabla.items():
        fallos = [f for f in res if f != "OK"]
        print(f"  {skill}: {res.count('OK')}/{len(res)} aciertos   fallos: "
              + (", ".join(f"{f} x{fallos.count(f)}" for f in sorted(set(fallos))) or "-"))


if __name__ == "__main__":
    main()
