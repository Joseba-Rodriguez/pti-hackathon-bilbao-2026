# Plan de grabación: seguir el láser (50 episodios)

Objetivo: el brazo coge el bote, **sigue el punto del láser** con él y, cuando el láser **se apaga**, lo
deja ahí. Se añade a `pti_coger_v7` con `--resume` y se afina desde `coger_v7`.

## Mesa: 9 casillas (vista de la cámara cenital, robot arriba)

```
          izquierda   centro   derecha
cerca        1          2         3      <- NO se usa (muy cerca del brazo, poco margen para maniobrar)
medio        4          5         6
lejos        7          8         9      <- ayer casi vacía: prioridad
```
**Solo las 6 casillas lejanas (4–9).** El láser no entra en la fila 1–3 en ningún episodio.
Antes de empezar, comprobad con el leader que el brazo llega con el bote a las casillas 7, 8 y 9.
Si alguna no llega, sus episodios se pasan a la casilla alcanzable más cercana.

## Reglas para TODOS los episodios
1. Inicio siempre igual: brazo en reposo, bote en el soporte, **láser apagado**, marca roja del bote tapada.
2. Coger el bote y subirlo (igual que ayer). **Entonces** se enciende el láser.
3. El bote va a unos 5 cm de altura, **3–4 cm desplazado del punto y siempre hacia el mismo lado**, para no taparlo.
4. Láser lento (3–5 cm/s). La persona del láser, fuera de la imagen.
5. Al **apagar** el láser: bajar recto, abrir la pinza, subir, volver a reposo y pulsar `→`.
6. Teleopera siempre la misma persona. Episodios de 20–35 s.
7. Si un episodio sale mal (el bote tapa el punto, cae o tiembla), `←` y se repite.

## Los 50 episodios

| Tipo | Nº | Qué hace el láser | Para qué |
| --- | --- | --- | --- |
| A. Recta corta | 10 | Se enciende cerca y va en línea recta a una casilla vecina | Lo básico: seguir |
| B. Recta larga | 10 | Cruza la zona (4→6, 7→9, 4→9, 6→7, 9→4…) | Recorridos largos |
| C. Curva / zigzag / círculo | 8 | Trayectoria curva | Que siga la forma, no un recorrido memorizado |
| D. Con paradas | 8 | Se mueve, **se para 2 s**, sigue y se apaga | Se mueve *porque* se mueve el punto |
| E. Cambio de sentido | 6 | Va hacia un lado y de repente vuelve | Reaccionar al punto |
| F. Salto | 4 | Se apaga 0,5 s y se enciende en otro sitio, que el brazo sigue, y después se apaga | Ir a un punto nuevo |
| G. Casi sin moverse | 4 | Se enciende en un sitio y se apaga a los 2–3 s | Dejar en un punto quieto |

**Dónde se apaga el láser** (es donde se deja el bote): **8–9 veces en cada una de las 6 casillas**.
Hoja para ir marcando:

| Casilla | 4 | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- |
| Objetivo | 8 | 8 | 8 | 9 | 9 | 8 |
| Hechos | | | | | | |

Dentro de cada casilla, variad el punto exacto (no siempre en el centro de la casilla).

Orden: **mezclad los tipos** (no grabéis los 10 de un mismo tipo seguidos), para que el cansancio del
operador no se convierta en un patrón.

## Después
1. Revisar: cuántos episodios hay y el mapa de calor de dónde se suelta (como el de `coger_v7`).
2. Afinar desde `coger_v7` con todo el dataset (~100 episodios), 10 000 pasos (~2 h).
3. Probar con `n_action_steps` bajo y sin suavizado fuerte, para que reaccione rápido al punto.
4. Evaluar: 10 intentos con trayectorias nuevas, apuntando el éxito al seguir y el éxito al dejar.
