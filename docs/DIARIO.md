# Diario del equipo PTI (Physical AI Hackathon Bilbao, 20-22 nov 2026)

Todo lo que hacemos, en orden. Sirve para no repetir errores y para el pitch
("qué falló y cómo lo diagnosticamos").

## Viernes 20

### Puesto
- SO-101 conectados al portátil de Joseba (Windows 11, RTX 2060 6 GB). LeRobot 0.6.2 en `lerobot\.venv`.
- Leader COM7 (5,5 V), follower COM8 (12,5 V). ids `leader_puesto` / `follower_puesto`. Calibrados.
- Cámara cenital: índice 2, 640x480.

### Problema: `lerobot-info` fallaba (torchcodec)
- Causa: FFmpeg del sistema es el 9; torchcodec 0.11 solo admite 4–8.
- Solución: FFmpeg 8 compartido en `E:\miniforge3\envs\ffmpeg8` y delante en el PATH.

### Filtro de cámara para el láser
- El punto del láser ocupaba 2–3 píxeles: ACT casi no lo vería.
- Exposición fija -6 y saturación 80 (`herramientas\camara_laser.py`): la escena se oscurece
  y el láser destaca (rojo 128 frente a < 100 del resto).
- `herramientas\lerobot_laser.py` dibuja un círculo rojo de 12 px donde está el láser en cada
  fotograma, igual al grabar y al desplegar.

### Idea final
- Modelo 1 "coger": el bote siempre en el mismo sitio (soporte); el brazo lo coge y lo levanta
  a una postura fija de "llevando".
- Modelo 2 "llevar": desde esa postura, lleva el bote a donde apunta el láser y lo deja.

### Modelo 1, primera prueba (`coger_v2`)
- Dataset `Josebarv01/pti_coger_v2`: 15 episodios, 10 628 fotogramas (episodios de 19 a 32 s, largos).
- Problemas al grabar: el episodio se cortaba solo a los 15 s → `episode_time_s=60`,
  `reset_time_s=300` y se controla con las flechas. Relanzar con el mismo nombre falla
  (la carpeta ya existe) → cambiar de nombre (`v2`, `v3`...) o `--resume=true`.
- Entrenamiento: ACT, 5000 pasos, batch 8, 26 min 42 s en la RTX 2060 (3,1 pasos/s).
- Resultado en el robot: **1 de 5** cogidas bien. "Pilla la idea" pero **tiembla mucho**.
- Siguiente: probar con temporal ensembling (`--policy.n_action_steps=1
  --policy.temporal_ensemble_coeff=0.01`), más episodios y más pasos.

### Modelo 1: más datos antes de reentrenar
- Se lanzó `coger_v3` (20 000 pasos con los mismos 15 episodios) y se **canceló a los pocos
  minutos**: primero más grabaciones (regla: antes de tocar entrenamiento, añadir datos).
  La carpeta `outputs/train/coger_v3` queda a medias: el siguiente entrenamiento usa `coger_v4`.
- Plan: 35 episodios más en `pti_coger_v2` (`--resume=true`) hasta 50, cortos (~10 s) y decididos.
- Probar modelos viendo la cámara en directo: `herramientas\probar.ps1` (Rerun, `--display_data=true`).

### Cámara de muñeca, falsos láser y mesa sin cartulina (~22:00)
- Cámaras: 0 = webcam del portátil, **1 = muñeca**, 2 = cenital. Se graba con top (2) + wrist (1).
  Con otra cámara el dataset cambia: no se puede añadir a `pti_coger_v2`.
- `--display_data=true`: Rerun con las dos cámaras, articulaciones y un **mapa** de la mesa
  (si existe `app/calibracion.json`; el mapa no se graba).
- `pti_coger_v3` (4 episodios) descartado: el filtro ponía un círculo falso sobre la **base
  naranja** del robot en la mitad de los fotogramas. Arreglo: detectar solo picos pequeños
  (top-hat) con rojo > 190. `pti_coger_v4` quedó vacío.
- Error al grabar: "Input voltage error" en el servo 6 del **leader** → revisar su fuente de 5 V.
- Se quita la cartulina: fondo = mesa blanca. `pti_coger_v5` descartado: círculos falsos sobre
  el propio brazo (naranja) en 158 de 935 fotogramas. Arreglo: si el punto rojo está pegado a una
  mancha rojiza grande (> 250 px, el brazo), se descarta. Probado: 0 falsos en esos 935 fotogramas
  y un láser pegado en la mesa se detecta 19 de 19. Se graba en `pti_coger_v6`.

### Dataset bueno del modelo 1: `pti_coger_v7` (~23:15)
- `pti_coger_v6` quedó vacío; se grabó en **`Josebarv01/pti_coger_v7`**: **50 episodios**,
  43 886 fotogramas (19–36 s por episodio), cámaras top (2) + wrist (1), mesa blanca, 446 MB.
- Copias (los vídeos pesan > 100 MB, no caben en GitHub):
  - Hugging Face Hub: https://huggingface.co/datasets/Josebarv01/pti_coger_v7 (público, tamaños verificados).
  - Local: `E:\HACKATONLeRobot\_copias\pti_coger_v7_50ep`.

## Tabla de resultados

| Modelo | Checkpoint | Suavizado | Aciertos | Notas |
| --- | --- | --- | --- | --- |
| coger_v2 | 5000 | no | 1/5 | tiembla mucho |
