# Componentes de terceros

Este repositorio incluye los siguientes componentes de terceros, que se distribuyen con sus propias licencias.

| Componente | Ubicación | Licencia | Origen |
| --- | --- | --- | --- |
| three.js (núcleo y addons) | `herramientas/web/vendor/three/` | MIT, © 2010-2024 Three.js Authors | https://github.com/mrdoob/three.js |
| Inter | `herramientas/web/fonts/inter-*.woff2` | SIL Open Font License 1.1 | https://github.com/rsms/inter |
| JetBrains Mono | `herramientas/web/fonts/jbmono-*.woff2` | SIL Open Font License 1.1 | https://github.com/JetBrains/JetBrainsMono |

Dependencias que no se incluyen en el repositorio y se instalan por separado (ver `docs/INSTALAR.md`):

- [LeRobot](https://github.com/huggingface/lerobot) (Apache 2.0), a través del fork [Juxi-Technology/lerobot](https://github.com/Juxi-Technology/lerobot).
- [so101-mujoco](https://github.com/Juxi-Technology/so101-mujoco): modelo MuJoCo del SO-101 que usa el gemelo digital.
- [MuJoCo](https://github.com/google-deepmind/mujoco) (Apache 2.0), [OpenCV](https://opencv.org/) (Apache 2.0) y [Rerun](https://rerun.io/) (MIT/Apache 2.0).

Los audios de `herramientas/web/voz/` se generaron con `herramientas/generar_voz.py` (voces neuronales de Microsoft a través de `edge-tts`).
