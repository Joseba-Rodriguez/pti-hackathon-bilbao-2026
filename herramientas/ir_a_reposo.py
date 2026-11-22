"""MUEVE EL BRAZO. Lleva el follower DESPACIO (5 s) a la postura de reposo del brazo viejo,
le quita la fuerza para que se asiente solo en sus topes, y mide cuanto se desvia
cada articulacion del brazo viejo.

    python ..\\herramientas\\ir_a_reposo.py COM9
"""
import sys
import time

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

# Mediana del fotograma 0 de los 137 episodios de pti_todo_v3_uniforme (brazo viejo)
REPOSO_VIEJO = {"shoulder_pan": -3.0, "shoulder_lift": -95.8, "elbow_flex": 96.8,
                "wrist_flex": -100.1, "wrist_roll": -9.9, "gripper": 1.1}
SEGUNDOS, HZ = 5.0, 30

port = sys.argv[1] if len(sys.argv) > 1 else "COM9"
robot = SO101Follower(SO101FollowerConfig(port=port, id="follower_puesto"))
robot.connect(calibrate=False)
try:
    ini = robot.bus.sync_read("Present_Position")
    n = int(SEGUNDOS * HZ)
    for i in range(1, n + 1):
        a = i / n
        robot.send_action({f"{m}.pos": ini[m] + (REPOSO_VIEJO[m] - ini[m]) * a for m in ini})
        time.sleep(1 / HZ)
    time.sleep(1.0)
    con_fuerza = robot.bus.sync_read("Present_Position")
    robot.bus.disable_torque()
    time.sleep(2.0)
    suelto = robot.bus.sync_read("Present_Position")
finally:
    robot.disconnect()

print(f"{'articulacion':14s} {'objetivo':>9s} {'con_fuerza':>11s} {'sin_fuerza':>11s} {'desvio':>8s}")
for m in REPOSO_VIEJO:
    print(f"{m:14s} {REPOSO_VIEJO[m]:9.1f} {con_fuerza[m]:11.1f} {suelto[m]:11.1f} {suelto[m] - REPOSO_VIEJO[m]:+8.1f}")
print("desvio = donde se asienta el brazo nuevo en reposo menos donde estaba el viejo (grados; pinza 0-100)")
