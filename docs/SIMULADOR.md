# Simulador de Esperanza (SO-101 en MuJoCo): cargador de tomas

> Opcional: es el ensayo que hicimos en casa antes del evento. Para el hackathon no hace falta.
> El código está en [`simulador/`](../simulador); funciona dentro del simulador SO-101 MuJoCo
> (fork de LeRobot 0.6.2 de Juxi-Technology): copiar esos ficheros en `lerobot/examples/so101_mujoco/`.

Ensayo en casa del flujo del hackathon:
grabar demostraciones → entrenar una ACT por habilidad → evaluar → ejecutar la toma completa.

En el simulador, la persona que teleopera se sustituye por un **operador automático**
(un script que calcula los movimientos). En el evento lo hará una persona con el brazo leader.

## La escena

- **Rampa de gravedad** (`piezas/stl/rampa_cargador_esperanza.stl`, generada por `piezas/make_stl.py`). Los vasitos
  ya rellenados esperan en fila; el primero queda en el bolsillo, apoyado en el tope.
- **Vasitos** (`piezas/stl/vasito_esperanza.stl`) de color por toma: naranja = mañana, azul = mediodía,
  morado = noche. Dentro, tres pastillas de colores.
- **Marca verde** de entrega, **caja de usados** y **cámara del puesto** casi cenital sobre la marca.
- Medidas respecto a la base del brazo (x hacia delante, y hacia la izquierda del robot):

| Pieza | Posición |
| --- | --- |
| Centro del bolsillo de la rampa | x = 17 cm, y = 0 (la rampa sube alejándose del robot) |
| Marca verde | x = 18,8 cm, y = −10,5 cm |
| Caja de usados (8,5 × 8,5 cm, 3 cm de alto) | x = 12,5 cm, y = −20,5 cm |

## Qué está simulado y qué no

| Pieza | En el simulador |
| --- | --- |
| Brazo, vasitos, rampa, deslizamiento por gravedad, tope, caja | Física (MuJoCo) |
| Agarre | **Asistido**: al cerrar la pinza, el vasito se une a ella centrado; al abrirla se suelta. En la vida real lo hacen los nervios y el anillo del vasito: hay que probarlo |
| Rozamiento vasito-rampa | **Supuesto 0,10** (cinta de PTFE o PETG liso). El real se mide con la probeta |
| Esperanza | No está simulada: el script oculta las pastillas y devuelve el vasito a la marca |
| Cámara: qué toma es y si está vacío | OpenCV sobre la imagen de la cámara (color del vasito y píxeles de pastilla) |
| Voz y mensaje a la familia | Texto (voz si hay `pyttsx3`; Telegram si hay `TELEGRAM_TOKEN` y `TELEGRAM_CHAT`) |

## Lo que la simulación cambió del diseño de la rampa

Con la rampa original (22°, tope de 7 mm) el sistema **no funcionaba**:
1. El primer vasito se volcaba hacia delante por encima del tope: los de detrás, inclinados
   como la pendiente, lo empujan por el anillo.
2. Con un tope alto, el vasito que baja llega inclinado 22° y no se endereza: la postura del
   primero variaba de 3° a 23° y hasta 3 cm según la recarga.

Con **10° de pendiente y tope de 25 mm**, el primer vasito queda siempre en el mismo sitio
(±3 mm, 3–10° de inclinación) y la recarga funciona. `piezas/make_stl.py` ya tiene esos valores; la rampa
anterior (22°) se conserva solo en local.

**Condición:** con 10°, el vasito tiene que deslizar solo. En la probeta debe empezar a deslizar
a **6° o menos**. Con PLA sobre PLA no ocurrirá: poner cinta de PTFE en el suelo de la rampa o
imprimirla en PETG y lijarla. Si no se consigue, el plan B es el bolsillo con reposición a mano
(ver [HACKATON.md](HACKATON.md)).

## Resultados del ensayo (20-nov-2026)

50 demostraciones buenas por habilidad (operador automático), ACT 30 000 pasos, 10 intentos por
habilidad en escenas nuevas:

| Habilidad | Aciertos | Fallos |
| --- | --- | --- |
| entregar | 7/10 | lo tumba al dejarlo (2), fuera de la marca (1) |
| recoger | 7/10 | lo suelta fuera de la caja (3) |

Con el proyecto anterior (pizza) y 23 demostraciones por habilidad, 3/20. **La cantidad y la
consistencia de las demostraciones es lo que más cuenta.** Lecciones para el robot real:
caja de usados más grande (~15 × 15 cm), bajar el vasito hasta casi tocar la mesa antes de soltarlo,
y grabar más demostraciones justo de la fase donde falla.

## Comandos (PowerShell, uno a uno)

Todos desde la carpeta del repo:

```
cd e:\HACKATONLeRobot\lerobot
```

**Nunca uses `uv run`**: reinstalaría PyTorch sin GPU. Usa siempre `.venv\Scripts\...`.

### 1. Ver una toma completa (operador automático, con ventana)

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_orquestador.py
```

Tres tomas seguidas, y la última se la "olvida" (llega la alerta):

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_orquestador.py --tomas 3 --olvido
```

### 2. Grabar demostraciones (50 buenas por habilidad)

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_record.py --episodios 50
```

Datasets en `examples\so101_mujoco\outputs\datasets\esperanza\entregar` y `...\recoger`.

### 3. Entrenar (una ACT por habilidad)

```
.venv\Scripts\python.exe examples\so101_mujoco\auto_train.py --policy.type=act --policy.push_to_hub=false --policy.device=cuda --policy.use_amp=true --dataset.repo_id=local/esperanza_entregar --dataset.root=examples/so101_mujoco/outputs/datasets/esperanza/entregar --dataset.video_backend=pyav --output_dir=examples/so101_mujoco/outputs/train/esperanza/entregar --steps=30000 --batch_size=8 --log_freq=500 --save_freq=10000 --num_workers=4
```

Para la otra, cambia `entregar` por `recoger` (tres veces). `auto_train.py` es `lerobot-train`
con un arreglo para Windows (el enlace `checkpoints/last`).
Todo seguido (grabar, entrenar las dos y evaluar), en Git Bash: `bash examples/so101_mujoco/esperanza_entrenar.sh`.

### 4. Evaluar (10 intentos por habilidad, escenas nuevas)

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_eval.py --intentos 10
```

Otro checkpoint: añade `--checkpoint 020000`. Más reactiva: `--n-action-steps 30`.

### 5. La toma completa con las políticas entrenadas

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_orquestador.py --modo politica --tomas 3
```

### 6. Vídeo de la simulación

```
.venv\Scripts\python.exe examples\so101_mujoco\esperanza_video.py --hd --salida ..\esperanza_simulacion.mp4
```

## Ficheros

| Fichero | Qué hace |
| --- | --- |
| `esperanza_scene.py` | Escena, robot simulado, agarre asistido, visión de la marca |
| `esperanza_expert.py` | Operador automático de `entregar` y `recoger` |
| `esperanza_test.py` | Prueba rápida del operador (varias tomas) |
| `esperanza_record.py` | Graba los dos datasets |
| `esperanza_politica.py` | Carga y ejecuta una ACT entrenada |
| `esperanza_eval.py` | Evalúa cada habilidad por separado |
| `esperanza_orquestador.py` | La toma completa: aviso, habilidades, cámara, familia |
| `esperanza_video.py` | Vídeo con rótulos |
| `esperanza_entrenar.sh` | Grabar + entrenar + evaluar, todo seguido |

## Avisos

- Fork usado: LeRobot 0.6.2 (Juxi-Technology). En el evento probablemente 0.7.x: comprobar `--help`.
- Nada de esto se lleva al evento como dataset o modelo (regla de no traer trabajo entrenado).
- Concepto de demostración, no dispositivo médico.
