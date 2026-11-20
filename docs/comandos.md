# Comandos del puesto (verificados con LeRobot 0.6.2 instalado en `lerobot\.venv`)

## Hardware detectado (20-nov-2026)
- Leader: 5,5 V. Follower: 12,5 V. Ambos con chip CH343 y servos ids 1–6.
- El COM cambia según el puerto USB. `python herramientas\puertos.py` dice cuál es cuál.
- Uno de los USB-C del portátil no detectaba un brazo. Si falta uno: fuente, cable con datos, otro puerto o hub.
- ids fijos para todo el evento: `follower_puesto` y `leader_puesto`. No recalibrar.
- Calibración en `E:\HACKATONLeRobot\hf_cache\lerobot\calibration\` (HF_HOME).

## Scripts
```
powershell -ExecutionPolicy Bypass -File herramientas\calibrar.ps1
powershell -ExecutionPolicy Bypass -File herramientas\teleoperar.ps1
python herramientas\puertos.py
```

## A mano
```
cd E:\HACKATONLeRobot\lerobot
.\.venv\Scripts\Activate.ps1
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
$env:PATH = "E:\miniforge3\envs\ffmpeg8\Library\bin;" + $env:PATH   # FFmpeg 8 para torchcodec (el 9 del sistema no vale)
lerobot-calibrate --robot.type=so101_follower --robot.port=COM8 --robot.id=follower_puesto
lerobot-calibrate --teleop.type=so101_leader --teleop.port=COM7 --teleop.id=leader_puesto
lerobot-teleoperate --robot.type=so101_follower --robot.port=COM8 --robot.id=follower_puesto --teleop.type=so101_leader --teleop.port=COM7 --teleop.id=leader_puesto
```

## Pendiente
- RESUELTO: torchcodec 0.11 admite FFmpeg 4–8 y el del sistema es el 9. FFmpeg 8 compartido en el entorno conda `E:\miniforge3\envs\ffmpeg8`; basta ponerlo delante en el PATH (línea de arriba).
- Cámaras: `lerobot-find-cameras opencv`.
