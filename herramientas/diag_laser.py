"""Diagnostico del laser: SOLO LEE la camara cenital (no cambia exposicion ni nada) durante unos
segundos y dice, fotograma a fotograma, si el filtro ve el laser y con que fuerza.

    python ..\\herramientas\\diag_laser.py quieto      (laser quieto sobre la mesa)
    python ..\\herramientas\\diag_laser.py moviendo    (laser moviendose despacio)

Cerrar antes cualquier otro programa que use la camara (record, rollout, ver_camaras).
Patron en la linea de fotogramas:  #  = lo ve   .  = no lo ve
  - alternando (#.#.#.)         -> parpadeo (laser con pila baja o luces de la sala)
  - huecos solo al moverlo      -> desenfoque por movimiento (mover mas despacio)
  - casi siempre '.' y rojo<190 -> poca luz del laser frente al fondo (fondo oscuro, pila nueva)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lerobot_laser as L  # noqa: E402


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "quieto"
    cap = cv2.VideoCapture(L.CFG["camara"]["indice"], cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("No puedo abrir la camara (¿la usa otro programa?)")
    for _ in range(10):
        cap.read()
    print(f"Modo {modo}: grabando 6 s... (exposicion de la camara: {cap.get(cv2.CAP_PROP_EXPOSURE)})")
    linea, picos, rojos, t0, n = "", [], [], time.time(), 0
    while time.time() - t0 < 6:
        ok, im = cap.read()
        if not ok:
            continue
        n += 1
        p = L.buscar_laser(im)
        b, g, r = (im[..., i].astype(np.int16) for i in range(3))
        score = np.clip(r - np.maximum(g, b), 0, 255)
        y, x = np.unravel_index(int(np.argmax(score)), score.shape)
        rojos.append(int(r[y, x])); picos.append(int(score[y, x]))
        linea += "#" if p else "."
    cap.release()
    fps = n / 6
    print(f"{n} fotogramas ({fps:.0f} fps).  Visto en {linea.count('#')} de {n} ({100 * linea.count('#') / max(n, 1):.0f} %)")
    for i in range(0, len(linea), 60):
        print("  " + linea[i:i + 60])
    print(f"Punto mas rojo de cada fotograma: rojo medio {np.mean(rojos):.0f} (min {min(rojos)}, max {max(rojos)}; "
          f"el filtro pide > {L.BRILLO_MIN}),  destaque medio {np.mean(picos):.0f} (pide > {L.UMBRAL})")


if __name__ == "__main__":
    main()
