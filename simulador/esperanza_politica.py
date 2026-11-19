"""Carga una politica ACT entrenada (entregar o recoger) y la ejecuta en el robot simulado.

Es lo mismo que hace lerobot-rollout con el robot real, pero dentro de un script,
para poder encadenar habilidades desde el orquestador.
"""

from __future__ import annotations

import time
from pathlib import Path

import torch

import esperanza_expert as ee
from so101_mujoco_robot import JOINT_NAMES

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE / "outputs" / "datasets" / "esperanza"
TRAIN_ROOT = HERE / "outputs" / "train" / "esperanza"
FPS = 30


def checkpoint_path(skill: str, checkpoint: str | None = None) -> Path | None:
    ck = TRAIN_ROOT / skill / "checkpoints"
    if not ck.exists():
        return None
    if checkpoint is None:
        txt = ck / "last.txt"
        checkpoint = txt.read_text().strip() if txt.exists() else None
        if checkpoint is None:
            dirs = sorted(d.name for d in ck.iterdir() if d.is_dir() and d.name.isdigit())
            checkpoint = dirs[-1] if dirs else None
    return ck / checkpoint / "pretrained_model" if checkpoint else None


class PolicySkill:
    def __init__(self, skill: str, checkpoint: str | None = None, n_action_steps: int | None = None):
        from lerobot.datasets import LeRobotDatasetMetadata
        from lerobot.policies import get_policy_class, make_pre_post_processors

        self.skill = skill
        self.path = checkpoint_path(skill, checkpoint)
        if self.path is None or not self.path.exists():
            raise FileNotFoundError(f"no hay politica entrenada para '{skill}' en {TRAIN_ROOT / skill}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy = get_policy_class("act").from_pretrained(str(self.path))
        if n_action_steps:
            self.policy.config.n_action_steps = n_action_steps
        self.policy.to(self.device).eval()
        self.pre, self.post = make_pre_post_processors(
            policy_cfg=self.policy.config, pretrained_path=str(self.path),
            preprocessor_overrides={"device_processor": {"device": str(self.device)}})
        self.meta = LeRobotDatasetMetadata(f"local/esperanza_{skill}", root=DATA_ROOT / skill)
        self.seconds = float(max(self.meta.episodes["length"])) / self.meta.fps + 1.0

    def run(self, robot) -> dict[str, float]:
        from lerobot.common.control_utils import predict_action
        from lerobot.policies.utils import make_robot_action
        from lerobot.utils.feature_utils import build_dataset_frame

        self.policy.reset()
        self.pre.reset()
        self.post.reset()
        t_next = time.perf_counter()
        for _ in range(int(self.seconds * FPS)):
            obs = robot.get_observation()
            frame = build_dataset_frame(self.meta.features, obs, prefix="observation")
            a = predict_action(frame, self.policy, self.device, self.pre, self.post, use_amp=False,
                               task=ee.TASK_TEXT[self.skill], robot_type="so101_mujoco")
            robot.send_action(make_robot_action(a, self.meta.features))
            t_next += 1 / FPS
            time.sleep(max(0.0, t_next - time.perf_counter()))
        obs = robot.get_observation()
        return {n: obs[f"{n}.pos"] for n in JOINT_NAMES}
