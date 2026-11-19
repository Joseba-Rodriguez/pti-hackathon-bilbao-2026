"""Graba demostraciones de las dos habilidades con el operador automatico.

Cada episodio parte de una escena nueva y distinta (como cambia de verdad de una
toma a otra): cuantos vasitos quedan en la rampa y de que toma, cuantas
recargas lleva ya la rampa, donde ha dejado Esperanza el vasito vacio y cuantos
hay ya en la caja de usados. Si el episodio sale mal, se descarta.

    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_record.py --episodios 50
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_record.py --skills recoger --episodios 10 --ver

En el hackathon esto mismo se hace con lerobot-record y una persona en el brazo
leader (ver HACKATON.md): misma idea, mismos dos datasets.
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import numpy as np

import auto_expert as ax
import esperanza_expert as ee
import esperanza_scene as es
from lerobot.configs.video import RGBEncoderConfig
from lerobot.datasets import LeRobotDataset
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features

ROOT = Path(__file__).resolve().parent / "outputs" / "datasets" / "esperanza"
FPS = 30


def random_scene(skill: str, rng: np.random.Generator) -> tuple[list[es.Vasito], int]:
    """(vasitos, recargas previas)."""
    tomas = list(es.TOMAS)
    n_ramp = int(rng.integers(1, 5)) if skill == "recoger" else int(rng.integers(2, 5))
    cups = [es.Vasito(str(rng.choice(tomas))) for _ in range(n_ramp)]
    if skill == "recoger":
        r, a = rng.uniform(0, 0.012), rng.uniform(0, 2 * np.pi)
        cups.append(es.Vasito(str(rng.choice(tomas)), "marca", False,
                              (r * np.cos(a), r * np.sin(a)), float(rng.uniform(-np.pi, np.pi))))
    for _ in range(int(rng.integers(0, 3))):   # vasitos ya usados en la caja (distraen, como en la realidad)
        cups.append(es.Vasito(str(rng.choice(tomas)), "caja", False,
                              tuple(rng.uniform(-0.015, 0.015, 2)), float(rng.uniform(-np.pi, np.pi))))
    reloads = int(rng.integers(0, min(3, n_ramp))) if skill == "entregar" else 0
    return cups, reloads


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skills", nargs="*", default=list(ee.SKILLS))
    p.add_argument("--episodios", type=int, default=50, help="episodios buenos por habilidad")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ver", action="store_true")
    args = p.parse_args()
    rng = np.random.default_rng(args.seed)
    expert = ee.EsperanzaExpert(seed=args.seed)
    t0 = time.time()

    for skill in args.skills:
        root = ROOT / skill
        if root.exists():
            shutil.rmtree(root)
        ds = None
        good = bad = 0
        while good < args.episodios:
            cups, reloads = random_scene(skill, rng)
            es.EsperanzaRobot.cups = cups
            robot = es.EsperanzaRobot(es.EsperanzaRobotConfig(onscreen=args.ver, settle_s=1.5))
            robot.connect()
            for _ in range(reloads):           # la rampa ya ha entregado algun vasito
                robot.park_cup(ee.front_cup(robot))
                time.sleep(1.8)
            if ds is None:
                features = {**hw_to_dataset_features(robot.action_features, "action"),
                            **hw_to_dataset_features(robot.observation_features, "observation", use_video=True)}
                ds = LeRobotDataset.create(
                    f"local/esperanza_{skill}", fps=FPS, features=features, root=root, robot_type="so101_mujoco",
                    use_videos=True, rgb_encoder=RGBEncoderConfig(vcodec="h264"), encoder_threads=2)

            i = ee.front_cup(robot) if skill == "entregar" else robot.cup_on_spot()
            try:
                if i is None:
                    raise RuntimeError("no hay vasito que coger")
                traj = ax.Trajectory(dict(ax.HOME), expert.plan(skill, *ee.cup_frame(robot, i)))
            except RuntimeError as e:
                print(f"  {skill}: se salta ({e})", flush=True)
                robot.disconnect()
                continue
            t_next = time.perf_counter()
            for k in range(int((traj.duration + 0.5) * FPS)):
                obs = robot.get_observation()
                act = {f"{n}.pos": v for n, v in traj(k / FPS).items()}
                robot.send_action(act)
                ds.add_frame({**build_dataset_frame(ds.features, obs, prefix="observation"),
                              **build_dataset_frame(ds.features, act, prefix="action"),
                              "task": ee.TASK_TEXT[skill]})
                t_next += 1 / FPS
                time.sleep(max(0.0, t_next - time.perf_counter()))
            time.sleep(0.4)
            others_ok = all(robot.cup_tilt_deg(j) < 25 for j in range(len(robot.cup_body))
                            if j != i and robot.cup_pos(j)[0] > 0.1 and robot.cup_specs[j].donde == "rampa")
            ok = (robot.cup_on_spot() == i if skill == "entregar" else robot.cup_in_box(i)) and others_ok
            if ok:
                ds.save_episode(parallel_encoding=False)
                good += 1
            else:
                ds.clear_episode_buffer()
                bad += 1
            print(f"  {skill} #{good}/{args.episodios} ({'guardado' if ok else 'DESCARTADO'}; descartados {bad}) "
                  f"{(time.time() - t0) / 60:.1f} min", flush=True)
            robot.disconnect()
        ds.finalize()
        print(f"FIN {skill}: {good} episodios, {bad} descartados", flush=True)


if __name__ == "__main__":
    main()
