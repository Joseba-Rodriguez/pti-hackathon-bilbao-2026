# Documentación

Los documentos se escribieron durante el hackathon (20–22 de noviembre de 2026), según se
necesitaban. Los marcados como **históricos** describen fases del proyecto que después se
sustituyeron. Se conservan porque explican cómo llegamos al resultado final.

## Vigentes

| Documento | Para qué sirve |
| --- | --- |
| [INSTALAR.md](INSTALAR.md) | Instalar el proyecto en otro portátil Windows y lanzar la demo, tal como quedó el domingo |
| [DIARIO.md](DIARIO.md) | Diario técnico del equipo: cada grabación, entrenamiento, prueba en el robot, fallo y diagnóstico, con su hora |
| [NARRATIVA.md](NARRATIVA.md) | Historia del proyecto, guion del pitch de 5 minutos, atrezo y preguntas probables del jurado |
| [comandos.md](comandos.md) | Hardware del puesto (tensiones, puertos, ids de calibración) y comandos de LeRobot verificados |

## Planes de grabación

| Documento | Para qué sirve |
| --- | --- |
| [PLAN_LASER.md](PLAN_LASER.md) | Los 50 episodios de «seguir el láser»: reglas comunes y tipos de recorrido por casillas |
| [ESCALETA_CENTRO.md](ESCALETA_CENTRO.md) · [escaleta_centro.html](escaleta_centro.html) | 30 episodios para reforzar el centro de la mesa (tipo H), con versión imprimible |

## Históricos

| Documento | Qué describe |
| --- | --- |
| [PLAN.md](PLAN.md) | Fase 1 (viernes): el cubilete sale de INICIO y va a la zona A o B, con una política ACT por zona y el orquestador de `app/`. Se sustituyó por una sola política que sigue el láser |

## Imágenes

- `img/mapa_calor_*.png`: mapas de calor de dónde se soltó el cubilete en cada conjunto de
  demostraciones. Con ellos decidimos qué episodios grabar y comparamos modelos.
- `img/mapa_virtual.png` y `img/montaje_puesto.png`: el mapa virtual de la mesa y el montaje del puesto.
- `img/web_*.png` y `media/`: la cabina web y los GIF de la demo real.
