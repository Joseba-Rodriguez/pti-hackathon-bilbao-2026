"""Lee la postura actual del follower (grados, como los ve el modelo) SIN mover el brazo:
no activa el par ni escribe en los motores. Compara con la postura de reposo del dataset.

    python ..\\herramientas\\leer_postura.py COM9
"""
import sys

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

# Postura de reposo del brazo viejo: mediana del fotograma 0 de los 137 episodios de pti_todo_v3_uniforme
REPOSO_VIEJO = {"shoulder_pan": -3.0, "shoulder_lift": -95.8, "elbow_flex": 96.8,
                "wrist_flex": -100.1, "wrist_roll": -9.9, "gripper": 1.1}

port = sys.argv[1] if len(sys.argv) > 1 else "COM9"
robot = SO101Follower(SO101FollowerConfig(port=port, id="follower_puesto"))
robot.bus.connect()  # solo abre el puerto y comprueba los motores; no escribe nada
try:
    pos = robot.bus.sync_read("Present_Position")
finally:
    robot.bus.port_handler.closePort()

print(f"{'articulacion':14s} {'nuevo':>8s} {'viejo':>8s} {'diferencia':>11s}")
for m, v in pos.items():
    print(f"{m:14s} {v:8.1f} {REPOSO_VIEJO[m]:8.1f} {v - REPOSO_VIEJO[m]:+11.1f}")
