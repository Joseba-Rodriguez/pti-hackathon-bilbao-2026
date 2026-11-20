"""Calibracion de la mesa (una vez, con la camara ya fija; repetir solo si se mueve la camara).

Se abre una foto de la camara y se hace clic, por este orden:
  1-4. las 4 esquinas de la mesa (las 4 marcas de cinta): superior izquierda, superior derecha,
       inferior derecha, inferior izquierda (tal como se ven en la imagen)
  5.   el centro de INICIO (donde se deja el cubilete al empezar)
  6+.  el centro de cada zona de destino que haya en config.json -> politicas (A, B, ...)

    python app/calibrar.py
    python app/calibrar.py --imagen foto.png      (probar con una foto)
"""

from __future__ import annotations

import argparse
import json

import cv2
import numpy as np

import vision


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--imagen", default=None)
    a = p.parse_args()
    cfg = vision.cargar_config()
    zonas = [k for k in cfg["politicas"] if not k.startswith("_")]
    pasos = ["esquina SUPERIOR IZQUIERDA", "esquina SUPERIOR DERECHA", "esquina INFERIOR DERECHA",
             "esquina INFERIOR IZQUIERDA", "centro de INICIO"] + [f"centro de la zona {z}" for z in zonas]

    cam = vision.Camara(cfg, a.imagen)
    img = cam.foto()
    cam.soltar()

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    pts = []
    for i, paso in enumerate(pasos):
        ax.set_title(f"Clic {i + 1}/{len(pasos)}: {paso}", fontsize=14)
        fig.canvas.draw()
        clic = plt.ginput(1, timeout=0)
        if not clic:
            print("cancelado")
            return
        x, y = clic[0]
        pts.append((float(x), float(y)))
        ax.plot(x, y, "o", ms=10, mfc="none", mec="lime", mew=2)
        ax.text(x + 8, y - 8, paso.replace("esquina ", "").replace("centro de ", ""), color="lime", fontsize=9)
    plt.close(fig)

    calib = {"esquinas_px": pts[:4], "zonas_cm": {}}
    mesa = vision.Mesa(cfg, calib | {"zonas_cm": {}})
    for nombre, px in zip(["INICIO"] + zonas, pts[4:]):
        calib["zonas_cm"][nombre] = [round(float(v), 1) for v in mesa.a_cm(px)]
    vision.CALIB.write_text(json.dumps(calib, indent=2), encoding="utf-8")
    cv2.imwrite(str(vision.AQUI / "calibracion_foto.png"), img)
    print(f"Guardado en {vision.CALIB}")
    for k, v in calib["zonas_cm"].items():
        print(f"  {k:7s} en ({v[0]:.1f}, {v[1]:.1f}) cm")
    d = {k: np.asarray(v) for k, v in calib["zonas_cm"].items()}
    for z in zonas:
        dist = float(np.hypot(*(d[z] - d["INICIO"])))
        print(f"  INICIO -> {z}: {dist:.1f} cm")


if __name__ == "__main__":
    main()
