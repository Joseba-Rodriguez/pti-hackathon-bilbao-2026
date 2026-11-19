# Simulador (opcional)

El ensayo en casa del flujo completo en MuJoCo: escena con la rampa y los vasitos, operador automático
que graba demostraciones, entrenamiento ACT, evaluación y la toma completa.
**Para el hackathon no hace falta.**

Explicación, resultados y comandos: [docs/SIMULADOR.md](../docs/SIMULADOR.md).

Estos ficheros se usan dentro del simulador SO-101 MuJoCo (fork de LeRobot 0.6.2 de
Juxi-Technology): se copian en `lerobot/examples/so101_mujoco/`. Leen las STL de `piezas/stl/`.

| Fichero | Qué hace |
| --- | --- |
| `esperanza_scene.py` | Escena, robot simulado, agarre asistido y visión de la marca |
| `esperanza_expert.py` | Operador automático de `entregar` y `recoger` (+ `auto_expert.py`: cinemática) |
| `esperanza_record.py` | Graba los dos datasets |
| `esperanza_politica.py`, `esperanza_eval.py` | Ejecutar y evaluar una ACT entrenada |
| `esperanza_orquestador.py` | La toma completa en simulación |
| `esperanza_test.py`, `esperanza_video.py` | Prueba rápida y vídeo con rótulos |
| `esperanza_entrenar.sh`, `auto_train.py` | Grabar, entrenar y evaluar, todo seguido |
