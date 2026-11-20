"""Ajusta la camara cenital para que el laser se vea mucho mejor.

Baja la exposicion (la escena sale mas oscura y el punto del laser satura) y sube la
saturacion de color. El ajuste QUEDA GUARDADO EN LA CAMARA mientras no se desenchufe,
asi que lerobot-record y lerobot-rollout graban con el. Debe ser EL MISMO al grabar y
al desplegar: ejecuta  --aplicar  antes de cada sesion (y siempre tras desenchufarla).

    python herramientas\\camara_laser.py            ventana en vivo para elegir valores
        teclas:  +/-  exposicion   s/x  saturacion   g  guardar y salir   q  salir sin guardar
    python herramientas\\camara_laser.py --aplicar  aplica lo guardado y sale (sin ventana)

Los valores se guardan en app/config.json -> camara.exposicion / camara.saturacion.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

CONFIG = Path(__file__).resolve().parent.parent / "app" / "config.json"


def abrir(cfg_cam: dict) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(cfg_cam["indice"], cv2.CAP_DSHOW)   # DirectShow: deja fijar la exposicion
    if not cap.isOpened():
        raise SystemExit(f"No puedo abrir la camara {cfg_cam['indice']} (¿la tiene abierta otro programa?)")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg_cam["ancho"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg_cam["alto"])
    return cap


def aplicar(cap, exposicion: float, saturacion: float):
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)                 # exposicion manual
    cap.set(cv2.CAP_PROP_EXPOSURE, exposicion)
    cap.set(cv2.CAP_PROP_SATURATION, saturacion)
    for _ in range(8):                                        # que se asiente
        cap.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cam = cfg["camara"]
    expo, sat = cam.get("exposicion", -6), cam.get("saturacion", 80)
    cap = abrir(cam)
    aplicar(cap, expo, sat)
    if a.aplicar:
        ok, img = cap.read()
        leida = (cap.get(cv2.CAP_PROP_EXPOSURE), cap.get(cv2.CAP_PROP_SATURATION))
        cap.release()
        if not ok:
            raise SystemExit("No pude leer la camara")
        print(f"Camara {cam['indice']}: exposicion {leida[0]:.0f}, saturacion {leida[1]:.0f}, "
              f"brillo medio {img.mean():.0f}. Listo para grabar/desplegar.")
        return

    print(__doc__)
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                print("No leo la camara"); break
            b, g, r = (img[..., i].astype(np.int16) for i in range(3))
            score = r - np.maximum(g, b)
            y, x = np.unravel_index(int(np.argmax(score)), score.shape)
            vista = img.copy()
            cv2.circle(vista, (int(x), int(y)), 14, (0, 255, 0), 2)
            mascara = cv2.cvtColor(np.clip(score * 2, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            txt = f"exposicion {expo}  saturacion {sat}  |  rojo max {int(score.max())}  brillo {img.mean():.0f}"
            cv2.putText(vista, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.imshow("camara (verde = donde cree que esta el laser) | mascara del rojo",
                       np.hstack([vista, mascara]))
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("+"), ord("=")):
                expo += 1; aplicar(cap, expo, sat)
            elif k == ord("-"):
                expo -= 1; aplicar(cap, expo, sat)
            elif k == ord("s"):
                sat += 10; aplicar(cap, expo, sat)
            elif k == ord("x"):
                sat = max(0, sat - 10); aplicar(cap, expo, sat)
            elif k == ord("g"):
                cfg["camara"]["exposicion"], cfg["camara"]["saturacion"] = expo, sat
                CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"Guardado en {CONFIG}: exposicion {expo}, saturacion {sat}")
                break
            elif k == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        time.sleep(0.3)


if __name__ == "__main__":
    main()
