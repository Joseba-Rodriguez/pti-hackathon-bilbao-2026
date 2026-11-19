# Esperanza en el hackathon: qué hacer, paso a paso

Basado en la guía oficial (https://hackathonbilbao.eus/guia-so-101, leída el jueves 19-nov) y en
lo aprendido en el simulador ([SIMULADOR.md](SIMULADOR.md)). **(estimado)** = no medido.

**Concepto:** la familia carga la semana en vasitos ya rellenados, en orden, en una rampa impresa.
El robot sabe dos movimientos aprendidos (dos ACT):
1. **entregar**: coger el primer vasito del bolsillo de la rampa y dejarlo en la marca verde.
2. **recoger**: coger el vasito vacío de la marca y echarlo a la caja de usados.
Alrededor: aviso por voz, cámara que comprueba color (toma correcta) y vacío, Telegram a la familia.
Concepto, no dispositivo médico.

## Lo que dice la guía oficial y nos cambia el plan

| Dato oficial | Consecuencia para nosotros |
| --- | --- |
| **No hay GPU en el evento** | Entrenamos en el portátil de Joseba (RTX 2060), y en Colab o HF Jobs si hace falta |
| LeRobot **0.7.0** (`pip install 'lerobot[core_scripts,training,feetech]==0.7.0'`) | Esa versión exacta en todos los portátiles |
| Ubuntu recomendado; Windows con WSL, pero **en WSL las cámaras USB no funcionan** | Usamos **Windows nativo, sin WSL**: probado el jueves con LeRobot 0.7.0 (GPU, cámara y puertos COM; los brazos aún no) |
| Puesto: 2 brazos + 2 cámaras = **4 USB**; cada brazo con su fuente | Llevar hub USB **con alimentación propia** y adaptadores USB-C a USB-A |
| Nota: **30 de 100 puntos son 5 intentos seguidos en directo sin tocar el robot** (6 por acierto) | La rampa es perfecta para esto: 5 vasitos cargados = 5 intentos sin tocar nada |
| 20 puntos son datos y entrenamiento (cantidad, variedad, iterar sobre fallos) | Apuntar episodios grabados, descartados y qué cambió tras el primer entrenamiento |
| Bonus: dataset en Hugging Face (+3) y repositorio reproducible (+2) | Subir los dos datasets y el código |
| Entrega: **vídeo de 1 minuto** + **demo en directo de 3 minutos** | Grabar el vídeo real el sábado por la tarde |
| Por defecto ACT hace 100 000 pasos y guarda cada 20 000 | Poner siempre `--steps` y `--save_freq` |

---

## 1. Hoy jueves (noche)

**Imprimir (en este orden):**
1. `piezas/stl/probeta_rozamiento.stl` (unos 20 min (estimado)). Medir a qué ángulo desliza un vasito:
   tiene que deslizar a **6° o menos**. Si no, poner **cinta de PTFE** y repetir.
2. `piezas/stl/rampa_cargador_esperanza.stl` (la nueva: 10° y tope de 25 mm). Es la larga: lanzarla esta noche.
3. **6 vasitos** (`piezas/stl/vasito_esperanza.stl`): 2 naranjas, 2 azules, 2 morados (mate, nada de blanco, transparente ni brillante).
4. Marca verde de unos 56 mm (o una pegatina verde mate) y una caja baja para los usados.

**Portátil de Joseba: ya instalado (jueves 19-nov), Windows nativo sin WSL.**
LeRobot 0.7.0 + PyTorch 2.14.1 con CUDA 12.6 en `E:\miniforge3\envs\lerobot`; los datos van a
`E:\HACKATONLeRobot\hf_cache`. Comprobado: GPU, cámara, puertos COM, entrenar, guardar y reanudar
checkpoints. **Falta probar con los brazos de verdad** (el viernes, lo primero).

Cada vez que abras una PowerShell:

```
conda activate lerobot
```

```
cd E:\HACKATONLeRobot
```

Comprobar que todo responde (al llegar al puesto, con todo enchufado):

```
powershell -ExecutionPolicy Bypass -File herramientas\comprobar.ps1
```

Diferencias en Windows respecto a la guía oficial (que está pensada para Ubuntu):
- Los puertos son `COM3`, `COM7`... (los da `lerobot-find-port`), no `/dev/ttyACM0`.
- Para entrenar se usa `python herramientas\lerobot_train_windows.py` con los mismos argumentos que
  `lerobot-train`. El `lerobot-train` normal se cae al guardar el primer checkpoint
  (Windows no deja crear el enlace `checkpoints/last`).
- Plan B si los brazos fallan en Windows: WSL2 con `usbipd` (solo vale para los brazos; las
  cámaras no funcionan en WSL) o el portátil de un compañero con Ubuntu.

**Token de Hugging Face con permiso de escritura**, y bot de Telegram para la familia.

**Meter en la mochila:** hub USB con alimentación, adaptadores USB-C a USB-A, regleta, cargadores,
cinta de carrocero, bridas, cinta de PTFE, regla, la rampa, los vasitos, la marca, la caja y
varias decenas de GB libres de disco.

---

## 2. Viernes 16:00–18:00: llegar, demo de LeRobot y preguntas

Preguntar:
- ¿Podemos usar atrezo impreso pasivo (rampa, vasitos, marca, caja)?
- ¿Dónde van las 2 cámaras? Necesitamos **una casi cenital que vea la marca verde y el bolsillo**;
  la otra en la muñeca.
- En los 5 intentos de la demo, ¿un intento puede ser **una toma completa** (entregar, comprobar
  y recoger) o se cuenta cada movimiento?

---

## 3. Viernes 18:00–19:00: montar y prueba decisiva

Etiquetar las dos fuentes de alimentación (leader y follower tienen voltajes distintos; no
cambiarlas). No enchufar ni desenchufar cables con el brazo alimentado.

Colocación respecto al centro de la base del brazo (la del simulador; con el brazo real se ajusta
a ojo y luego **no se mueve nada**; todo marcado con cinta):

| Pieza | Dónde |
| --- | --- |
| Bolsillo de la rampa | 17 cm delante; la rampa sube alejándose del robot |
| Marca verde | 19 cm delante y 10 cm a un lado |
| Caja de usados | 12,5 cm delante y 20 cm a ese mismo lado |

Comandos (uno a uno; sustituir los puertos por los que salgan):

```
conda activate lerobot
```

```
cd E:\HACKATONLeRobot
```

```
$HF_USER = "Josebarv01"
```

```
lerobot-find-port
```

```
lerobot-find-cameras
```

```
lerobot-calibrate --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower
```

```
lerobot-calibrate --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader
```

Teleoperar (**una persona mirando el brazo con la mano en la alimentación**):

```
lerobot-teleoperate --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader --display_data=true
```

**Prueba decisiva:** el operador hace **entregar** 10 veces y **recoger** 10 veces mirando
**solo las imágenes de las cámaras** (si una persona puede así, el modelo puede aprenderlo).
- Abrir la pinza lo justo para pasar el anillo (41 mm) y cerrar sobre el cuerpo.
- Al soltar en la marca: abrir más y apartarse un poco hacia la mandíbula móvil antes de subir
  (en la simulación, la mandíbula fija enganchaba el anillo).
- Si salen 8 de 10 o más sin esfuerzo, plan A. Si cuesta, **plan B**: una persona pone cada
  vasito a mano en el bolsillo (mismas habilidades, mismos datos).
- El leader, fuera de la imagen de las cámaras.

---

## 4. Viernes 19:00–21:00: validar todo de punta a punta con un dataset pequeño

Es lo que pide la guía para el viernes. 5 episodios de **entregar**:

```
lerobot-record --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader --dataset.repo_id=${HF_USER}/esperanza_prueba --dataset.num_episodes=5 --dataset.single_task="take the first cup from the loader and place it on the green mark" --dataset.no_stamp=true
```

Teclas: → o `n` guarda y sigue; ← o `r` repite; `Esc` o `q` para y sube.

Comprobar un episodio en el brazo (persona mirando, mano en la alimentación):

```
lerobot-replay --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --dataset.repo_id=${HF_USER}/esperanza_prueba --dataset.episode=0
```

En el portátil que entrena, 500 pasos para **medir la velocidad** (mirar `step_s` en el registro):

```
python herramientas\lerobot_train_windows.py --dataset.repo_id=${HF_USER}/esperanza_prueba --policy.type=act --output_dir=outputs/train/esperanza_prueba --job_name=esperanza_prueba --policy.device=cuda --steps=500 --save_freq=500 --policy.repo_id=${HF_USER}/act_esperanza_prueba
```

**Con ese `step_s` se decide el plan de entrenamiento** (sección 6). Referencia: en casa, la
RTX 2060 hizo 0,2 s por paso con imágenes de 320×240. Con 640×480 serán varias veces más
(estimado). La guía da como referencia de 2 a 3 h para 100 000 pasos en una RTX 4090.

Probar también el despliegue con ese modelo de prueba (no hará nada útil; es para ver que arranca):

```
lerobot-rollout --strategy.type=base --policy.path=${HF_USER}/act_esperanza_prueba --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --task="take the first cup from the loader and place it on the green mark" --duration=20
```

---

## 5. Viernes noche o sábado a primera hora: grabar las dos habilidades

**50 episodios de cada una** (la guía: unos 50 para coger y dejar; unos 20 episodios por hora (estimado)).
Una sola persona en el leader. Empezar y acabar siempre en la misma postura de reposo.
Sin personas en la imagen durante el episodio.

**entregar.** En la pausa entre episodios, el ayudante quita el vasito de la marca y pone uno lleno
al final de la rampa (que haya de 2 a 4 y se mezclen colores).

```
lerobot-record --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader --dataset.repo_id=${HF_USER}/esperanza_entregar --dataset.num_episodes=50 --dataset.single_task="take the first cup from the loader and place it on the green mark" --dataset.no_stamp=true
```

**recoger.** En la pausa, el ayudante deja un vasito vacío en la marca, cada vez un poco distinto
(hasta 1 cm movido y girado), y de vez en cuando vacía la caja.

```
lerobot-record --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader --dataset.repo_id=${HF_USER}/esperanza_recoger --dataset.num_episodes=50 --dataset.single_task="pick up the empty cup from the green mark and drop it into the used box" --dataset.no_stamp=true
```

Si se corta, se continúa con los mismos argumentos más `--resume=true` (y `--dataset.num_episodes`
= los que faltan). Revisar episodios en https://huggingface.co/spaces/lerobot/visualize_dataset
y **anotar cuántos se graban y cuántos se descartan** (lo pide el jurado).

---

## 6. Entrenar (el portátil de Joseba, y la nube si no da tiempo)

```
python herramientas\lerobot_train_windows.py --dataset.repo_id=${HF_USER}/esperanza_entregar --policy.type=act --output_dir=outputs/train/esperanza_entregar --job_name=esperanza_entregar --policy.device=cuda --steps=30000 --save_freq=10000 --batch_size=8 --policy.repo_id=${HF_USER}/act_esperanza_entregar
```

```
python herramientas\lerobot_train_windows.py --dataset.repo_id=${HF_USER}/esperanza_recoger --policy.type=act --output_dir=outputs/train/esperanza_recoger --job_name=esperanza_recoger --policy.device=cuda --steps=30000 --save_freq=10000 --batch_size=8 --policy.repo_id=${HF_USER}/act_esperanza_recoger
```

Elegir según el `step_s` medido el viernes:
- **≤ 0,25 s/paso:** las dos seguidas en el portátil (≤ 4 h 10 min en total).
- **Más lento:** entregar en el portátil y recoger en paralelo en la nube: Colab (el notebook
  oficial de ACT) o HF Jobs, de pago (añadir `--job.target=a10g-small`). También se puede bajar
  a `--steps=20000`, como sugiere la guía para una primera versión.

Si se corta, se reanuda:

```
python herramientas\lerobot_train_windows.py --config_path=outputs/train/esperanza_entregar/checkpoints/last/pretrained_model/train_config.json --resume=true
```

---

## 7. Sábado: evaluar, corregir y reentrenar (hasta las 14:00 como mucho)

10 intentos por habilidad con la estrategia **episodic**, que además los graba como prueba para
el jurado (el nombre debe empezar por `rollout_`):

```
lerobot-rollout --strategy.type=episodic --policy.path=${HF_USER}/act_esperanza_entregar --robot.type=so101_follower --robot.port=COM_FOLLOWER --robot.id=esperanza_follower --robot.cameras="{ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" --teleop.type=so101_leader --teleop.port=COM_LEADER --teleop.id=esperanza_leader --dataset.repo_id=${HF_USER}/rollout_esperanza_entregar --dataset.num_episodes=10 --dataset.episode_time_s=30 --dataset.reset_time_s=10 --dataset.single_task="take the first cup from the loader and place it on the green mark"
```

- Probar también el checkpoint intermedio con `--policy.pretrained_revision=010000`; a veces es mejor.
- Tabla: acierto o fallo y **en qué fase falla** (no lo coge / lo tumba / fuera de la marca /
  fuera de la caja). Es material del pitch y de los 20 puntos de datos.
- Donde falle siempre, **grabar 10–20 episodios más de esa situación** (`--resume=true`) y
  reentrenar. Cambiar una sola cosa cada vez; antes de tocar hiperparámetros, más datos.
- Si no hace nada sensato: `lerobot-replay` de un episodio y comparar campo a campo los comandos
  de grabación y despliegue (cámaras, id, texto de la tarea).

## 8. Sábado 14:00: congelar. Integrar y grabar el vídeo de 1 minuto

- Integración con `orquestador/esperanza_real.py` (esqueleto: lanza `lerobot-rollout` de cada habilidad,
  mira la marca con OpenCV y avisa por Telegram). Primero `python orquestador/esperanza_real.py calibrar`,
  `color` y `vacio`. Antes, probar `python orquestador/esperanza_real.py toma noche --simulacro`.
- **Grabar el vídeo de 1 minuto** en cuanto salga una toma completa.
- **Ensayar los 5 intentos seguidos** con 5 vasitos en la rampa.
- Orden de recorte: cámara → tecla; voz → pantalla; recoger → fuera. Lo que no se toca:
  entrega la toma correcta y llega el mensaje.

## 9. Domingo: demo de 3 minutos ante el jurado

- Subir los datasets al Hub (+3) y el repositorio con instrucciones (+2).
- Demo: 5 intentos seguidos sin tocar el robot (rampa cargada con 5 vasitos).
- Tener preparadas las respuestas a: cuántos episodios grabamos, cuántos descartamos, qué cambió
  tras el primer entrenamiento y por qué un brazo y no un dispensador.

## Avisos de la guía oficial

- `--robot.id` y `--teleop.id` siempre iguales; nunca darle al leader el id del follower.
- Volver a mirar los puertos con `lerobot-find-port` si se desenchufa algo.
- Si una cámara desaparece, conectarla directa al portátil.
- Luz estable, cámaras fijas y la misma configuración al grabar y al desplegar.
