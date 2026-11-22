# Instalar y ejecutar en otro portátil (Windows)

Así quedó el proyecto el 22-nov-2026 en el portátil del puesto: Windows 11, GPU NVIDIA, LeRobot 0.6.2
(fork `Juxi-Technology/lerobot`, commit `3bb7b4a`), Python 3.13 en un venv de `uv`.

Los scripts usan rutas fijas `E:\HACKATONLeRobot\...`. Lo más fácil es clonar el repo **en esa ruta**.
Si el portátil no tiene disco `E:`, se crea uno virtual que apunta a cualquier carpeta (paso 0).

Ejecuta cada bloque en PowerShell, de uno en uno.

## 0. Solo si NO hay disco E:

```
mkdir C:\pti
```
```
subst E: C:\pti
```

(`subst` se pierde al reiniciar; vuelve a ejecutarlo después de cada reinicio.)

## 1. Requisitos

- Git, Python 3.13 y `uv` (`pip install uv`).
- Driver de NVIDIA reciente (CUDA 12.8). Sin GPU también funciona la inferencia en CPU, más lenta.
- FFmpeg: los scripts lo buscan en `E:\miniforge3\envs\ffmpeg8\Library\bin`. Si lo tienes en otro
  sitio, basta con que `ffmpeg` esté en el PATH.

## 2. Clonar este repo y LeRobot

```
git clone https://github.com/Joseba-Rodriguez/pti-hackathon-bilbao-2026.git E:\HACKATONLeRobot
```
```
cd E:\HACKATONLeRobot
```
```
git clone https://github.com/Juxi-Technology/lerobot.git lerobot
```
```
git -C lerobot checkout 3bb7b4a
```
```
git clone https://github.com/Juxi-Technology/so101-mujoco.git lerobot\examples\so101_mujoco
```

El último es el modelo 3D del SO-101 que usa el gemelo digital de la web.

## 3. Entorno de Python

```
cd E:\HACKATONLeRobot\lerobot
```
```
uv venv .venv --python 3.13
```
```
uv pip install --python .venv\Scripts\python.exe torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
```
```
uv pip install --python .venv\Scripts\python.exe -e ".[core_scripts,training,feetech]" mujoco==4.0.1 rerun-sdk==0.33.1
```

Comprobar:

```
.\.venv\Scripts\python.exe -c "import lerobot, torch, mujoco; print(lerobot.__version__, torch.cuda.is_available())"
```

## 4. Hugging Face (modelos y datasets)

```
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
```
```
.\.venv\Scripts\hf.exe auth login
```

Los modelos son públicos. Descargar los buenos a `outputs\nube\` (de ahí los lee la web):

```
.\.venv\Scripts\hf.exe download Josebarv01/act_pti_v4_all_data --local-dir outputs\nube\v4_all_data --exclude "checkpoints/*"
```
```
.\.venv\Scripts\hf.exe download Josebarv01/act_pti_v4_all_data_plus --local-dir outputs\nube\v4_all_data_plus --exclude "checkpoints/*"
```

Otros en el Hub: `act_pti_v4_uniforme_53`, `act_pti_v4_saturday_data`, `act_pti_todo_v3`.
`v4_all_data` es el que mejor ha funcionado en el robot.

## 5. Calibración del brazo

**Solo sirve para el mismo SO-101 del puesto.** Si es otro brazo, calibra con
`herramientas\calibrar.ps1` (ver `docs\comandos.md`).

```
mkdir E:\HACKATONLeRobot\hf_cache\lerobot\calibration\robots\so_follower -Force
```
```
mkdir E:\HACKATONLeRobot\hf_cache\lerobot\calibration\teleoperators\so_leader -Force
```
```
copy E:\HACKATONLeRobot\herramientas\calibracion_puesto\follower_puesto.json E:\HACKATONLeRobot\hf_cache\lerobot\calibration\robots\so_follower\
```
```
copy E:\HACKATONLeRobot\herramientas\calibracion_puesto\leader_puesto.json E:\HACKATONLeRobot\hf_cache\lerobot\calibration\teleoperators\so_leader\
```

`follower_puesto.json` es la del follower que se cambió el sábado por la noche (el viejo rompió
el servo de la pinza). Lleva ajustes a mano para que se mueva igual que el viejo:
`wrist_flex` −3,6°, `wrist_roll` −6°, `shoulder_pan` +1,7°. No recalibres ese brazo o se pierden.
Para retocarla: `herramientas\ajustar_calibracion.py` (no mueve el brazo).

## 6. Conectar y comprobar

- Leader a 5 V, follower a 12 V, los dos por USB. Cámaras: cenital índice 2, muñeca índice 1.

```
cd E:\HACKATONLeRobot\lerobot
```
```
.\.venv\Scripts\python.exe ..\herramientas\puertos.py
```

Debe salir `leader: COMx (5.x V)` y `follower: COMy (12.x V)`. Los scripts detectan el puerto solos.

## 7. Lanzar la demo

Doble clic en `PTI_DEMO.bat` (o lo mismo a mano):

```
cd E:\HACKATONLeRobot\lerobot
```
```
$env:HF_HOME = "E:\HACKATONLeRobot\hf_cache"
```
```
.\.venv\Scripts\python.exe ..\herramientas\gemelo.py
```

Se abre `http://127.0.0.1:8765/`. En **Control**: modelo `outputs/nube/v4_all_data`, coeficiente
−0.05 (va siempre a 30 Hz), y **una persona con la mano en la alimentación del follower** antes de
pulsar Start.

## Herramientas útiles

| Script | Para qué | ¿Mueve el brazo? |
| --- | --- | --- |
| `herramientas\puertos.py` | Ver en qué COM está cada brazo | No |
| `herramientas\leer_postura.py COMx` | Leer los grados actuales del follower | No |
| `herramientas\ajustar_calibracion.py COMx wrist_flex=-1` | Corregir grados sin recalibrar | No |
| `herramientas\ver_camaras.py` | Ver las dos cámaras en Rerun | No |
| `herramientas\ir_a_reposo.py COMx` | Llevar el follower a la postura de reposo | **Sí** |
| `herramientas\teleoperar.ps1` | Teleoperar | **Sí** |
| `herramientas\probar.ps1` | Lanzar un modelo desde la terminal | **Sí** |
| `herramientas\grabar_laser.ps1` | Grabar episodios | **Sí** |
| `herramientas\entrenar_nube.ps1` | Entrenar en Hugging Face Jobs | No |

Comprobar la calibración de un brazo nuevo: repetir un episodio grabado y ver si suelta donde el original
(**mueve el brazo**):

```
.\.venv\Scripts\lerobot-replay.exe --robot.type=so101_follower --robot.port=COMx --robot.id=follower_puesto --dataset.repo_id=Josebarv01/pti_todo_v2 --dataset.episode=97
```

Los datasets (`Josebarv01/pti_*`) son **privados**: para el replay o para reentrenar hace falta
entrar en Hugging Face con la cuenta `Josebarv01` o que os den acceso.

Historia completa de lo que se probó y por qué: `docs\DIARIO.md`.
