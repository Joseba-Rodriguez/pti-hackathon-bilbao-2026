# Escaleta: 30 episodios para reforzar el CENTRO (tipo H)

Por qué: en el mapa de calor completo (`docs/img/mapa_calor_completo.png`) el centro tiene pocas sueltas
para lo mucho que se usa en la demo, y el robot "se queda pocho" al apuntar al medio. Las casillas 1-2-3
(pegadas al robot) casi no se usan: el brazo no llega bien.

```
            izquierda   centro   derecha
cerca          1          2         3      <- no usar
medio          4         [5]        6      <- PRIORIDAD (sobre todo el 5)
lejos          7          8         9
```

Sueltas que hay ahora (ayer + hoy) y objetivo después de grabar:

| Casilla | 4 | **5** | 6 | 7 | **8** | 9 |
| --- | --- | --- | --- | --- | --- | --- |
| Ahora | 22 | 18 | 11 | 2 | 2 | 1 |
| Se añaden | 2 | **12** | 6 | 3 | **4** | 3 |

## Reglas (las de siempre)
- Fondo negro, bote y soporte **igual que en las grabaciones** (no tapar ni destapar nada nuevo).
- Láser apagado al empezar → coger → encender láser → seguir → apagar → soltar → reposo → `→`.
- Láser despacio; el bote 3–4 cm desplazado del punto, siempre hacia el mismo lado.
- Al llegar al destino: láser **quieto 1–2 s** y luego se apaga. Soltar **recto y limpio**.
- Episodios de 15–25 s. Si sale mal: `←` y se repite.

## Los 30 episodios (marcar al hacerlo)

| # | Empieza el láser en | Recorrido | Se apaga en | ✔ |
| --- | --- | --- | --- | --- |
| 1 | 4 | recto → | **5** | |
| 2 | 6 | recto ← | **5** | |
| 3 | 8 | recto ↑ | **5** | |
| 4 | 7 | diagonal ↗ | **5** | |
| 5 | 9 | diagonal ↖ | **5** | |
| 6 | 5 | se enciende ya en el centro, quieto 3 s | **5** | |
| 7 | 4 | pasa por el 5 sin parar, sigue | 6 | |
| 8 | 6 | pasa por el 5, para 2 s, sigue | 4 | |
| 9 | 4 | curva por abajo (8) | **5** | |
| 10 | 6 | curva por abajo (8) | **5** | |
| 11 | 5 | sale al 4 y vuelve | **5** | |
| 12 | 5 | sale al 6 y vuelve | **5** | |
| 13 | 5 | sale al 8 y vuelve | **5** | |
| 14 | 7 | recto → por abajo | **8** | |
| 15 | 9 | recto ← por abajo | **8** | |
| 16 | 5 | recto ↓ | **8** | |
| 17 | 4 | diagonal ↘ | **8** | |
| 18 | 4 | recto → cruzando el 5 | 6 | |
| 19 | 8 | diagonal ↗ | 6 | |
| 20 | 5 | recto → | 6 | |
| 21 | 9 | recto ↑ | 6 | |
| 22 | 5 | zigzag 4 → 5 → 6 | 6 | |
| 23 | 5 | recto ↓ ← diagonal | 7 | |
| 24 | 4 | recto ↓ | 7 | |
| 25 | 8 | recto ← | 7 | |
| 26 | 5 | diagonal ↘ | 9 | |
| 27 | 6 | recto ↓ | 9 | |
| 28 | 8 | recto → | 9 | |
| 29 | 6 | recto ← cruzando el 5 | 4 | |
| 30 | 8 | diagonal ↖ | 4 | |

Dentro de cada casilla, variar el punto exacto (no siempre el centro de la casilla).

## Después
1. Reviso el dataset (`pti_laser_H_centro`) y actualizo el mapa de calor.
2. Lo junto con todo lo anterior y afino **desde `todo_v1`** en la nube (~15–20 min).
