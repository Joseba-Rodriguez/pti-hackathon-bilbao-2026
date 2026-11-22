"""Corrige unos grados la calibracion del follower SIN recalibrar. No mueve el brazo
(solo escribe en la memoria de los servos; al terminar los deja sin fuerza).

    python ..\\herramientas\\ajustar_calibracion.py COM9 wrist_flex=-3.6 [shoulder_lift=+1.0 ...]

wrist_flex=-3.6 significa: lo que ahora el brazo lee como X grados pasara a leerse X-3.6.
Asi, al mandarle X grados, la articulacion se ira 3.6 grados mas hacia el lado positivo.
Antes de escribir guarda una copia del archivo de calibracion con la hora.
"""
import shutil
import sys
import time

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

port = sys.argv[1]
cambios = {k: float(v) for k, v in (a.split("=") for a in sys.argv[2:])}
robot = SO101Follower(SO101FollowerConfig(port=port, id="follower_puesto"))
f = robot.calibration_fpath
copia = f.with_name(f.stem + time.strftime("_antes_%H%M%S") + ".json")
shutil.copy(f, copia)
print("copia:", copia)

for m, grados in cambios.items():
    c = robot.calibration[m]
    ticks = round(-grados * 4095 / 360)     # leer X-g  <=>  el centro del rango sube g grados
    if c.range_min == 0 and c.range_max == 4095:
        # vuelta completa (wrist_roll): el rango no se puede desplazar; se mueve el cero del servo.
        # Present_Position = Actual - Homing_Offset  ->  subir el offset baja la lectura
        print(f"{m}: homing_offset {c.homing_offset} -> {c.homing_offset + ticks} ({grados:+} grados)")
        c.homing_offset += ticks
    else:
        print(f"{m}: rango [{c.range_min},{c.range_max}] -> [{c.range_min + ticks},{c.range_max + ticks}] ({grados:+} grados)")
        c.range_min += ticks
        c.range_max += ticks

robot.bus.connect()
try:
    robot.bus.disable_torque()
    robot.bus.write_calibration(robot.calibration)
finally:
    robot.bus.disconnect(disable_torque=True)
robot._save_calibration()
print("guardado en", f)
