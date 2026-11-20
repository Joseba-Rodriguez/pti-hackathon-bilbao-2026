"""lerobot-record / lerobot-rollout con FILTRO DE LASER en la camara cenital.

El punto del laser ocupa 2-3 pixeles: ACT casi no lo ve. Este envoltorio, en cada
fotograma de la camara cenital, busca el punto (rojo muy por encima de verde y azul,
mancha pequena) y dibuja encima un CIRCULO ROJO GRANDE. Si no hay laser, no dibuja nada.
El dataset se graba ya con el circulo, y al desplegar se aplica el mismo filtro:
grabar y desplegar SIEMPRE con este envoltorio (nunca mezclar con el lerobot-* normal).

Antes de arrancar aplica la exposicion/saturacion guardadas (herramientas/camara_laser.py).

Uso (mismos argumentos que el comando original):
    python ..\\herramientas\\lerobot_laser.py record  --robot.type=... --dataset.repo_id=... ...
    python ..\\herramientas\\lerobot_laser.py rollout --strategy.type=base --policy.path=... ...
    python ..\\herramientas\\lerobot_laser.py probar FOTO.png      (aplica el filtro a una foto)

Ajustes en app/config.json -> "marca_laser".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI.parent / "app" / "config.json"
CFG = json.loads(CONFIG.read_text(encoding="utf-8"))
MARCA = CFG.get("marca_laser", {})
UMBRAL = MARCA.get("umbral", 100)            # rojo - max(verde, azul)
BRILLO_MIN = MARCA.get("brillo_min", 150)    # canal rojo
AREA_MAX = MARCA.get("area_max_px", 60)      # manchas mayores (base naranja...) no son el laser
RADIO = MARCA.get("radio_px", 12)            # tamano del circulo dibujado


def buscar_laser(bgr: np.ndarray):
    b, g, r = (bgr[..., i].astype(np.int16) for i in range(3))
    score = r - np.maximum(g, b)
    mask = ((score > UMBRAL) & (r > BRILLO_MIN)).astype(np.uint8)
    if not mask.any():
        return None
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask)
    best = None
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > AREA_MAX:
            continue
        f = int(score[lab == i].max())
        if best is None or f > best[2]:
            best = (int(round(cent[i][0])), int(round(cent[i][1])), f)
    return best


def marcar(bgr: np.ndarray) -> np.ndarray:
    p = buscar_laser(bgr)
    if p is None:
        return bgr
    out = bgr.copy()
    cv2.circle(out, p[:2], RADIO, (0, 0, 255), -1)          # rojo puro (BGR)
    cv2.circle(out, p[:2], max(2, RADIO // 3), (255, 255, 255), -1)
    return out


def instalar_filtro():
    from lerobot.cameras.opencv import camera_opencv as co

    original = co.OpenCVCamera._postprocess_image
    indice = CFG["camara"]["indice"]

    def _postprocess_image(self, image):
        if str(self.index_or_path) == str(indice):            # solo la camara cenital
            image = marcar(image)                             # image llega en BGR (OpenCV)
        return original(self, image)

    co.OpenCVCamera._postprocess_image = _postprocess_image
    print(f"[filtro laser] activo en la camara {indice} (umbral {UMBRAL}, circulo {RADIO} px)")


def aplicar_exposicion():
    sys.path.insert(0, str(AQUI))
    import camara_laser
    cam = CFG["camara"]
    if "exposicion" not in cam:
        print("[filtro laser] AVISO: no hay exposicion guardada en config.json; uso la de la camara")
        return
    cap = camara_laser.abrir(cam)
    camara_laser.aplicar(cap, cam["exposicion"], cam.get("saturacion", 80))
    cap.release()
    print(f"[filtro laser] camara {cam['indice']}: exposicion {cam['exposicion']}, saturacion {cam.get('saturacion', 80)}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("record", "rollout", "probar"):
        raise SystemExit(__doc__)
    modo, resto = sys.argv[1], sys.argv[2:]
    if modo == "probar":
        img = cv2.imread(resto[0])
        p = buscar_laser(img)
        print("laser:", p)
        salida = Path(resto[0]).with_name(Path(resto[0]).stem + "_marcado.png")
        cv2.imwrite(str(salida), marcar(img))
        print("guardado", salida)
        return
    aplicar_exposicion()
    instalar_filtro()
    sys.argv = [f"lerobot-{modo}"] + resto
    if modo == "record":
        from lerobot.scripts.lerobot_record import main as m
    else:
        from lerobot.scripts.lerobot_rollout import main as m
    m()


if __name__ == "__main__":
    main()
