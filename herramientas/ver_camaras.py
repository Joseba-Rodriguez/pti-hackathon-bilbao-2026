"""Ver las DOS camaras (cenital con filtro de laser + muneca) en Rerun TODO EL RATO,
sin grabar ni mover el robot. Sirve para colocar la escena, probar el laser y ensayar.

    python ..\\herramientas\\ver_camaras.py

IMPORTANTE: cerrarlo (Ctrl+C) ANTES de lanzar lerobot_laser.py record/rollout o probar.ps1:
en Windows una camara solo la puede abrir un programa a la vez. Durante la grabacion y el
despliegue Rerun ya muestra las camaras (tambien en las pausas entre episodios).
Ademas envia la imagen y el laser al gemelo (herramientas/gemelo.py) si esta abierto.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camara_laser  # noqa: E402
import lerobot_laser as L  # noqa: E402


def main():
    import rerun as rr
    rr.init("pti_camaras", spawn=True)
    cam = L.CFG["camara"]
    top = camara_laser.abrir(cam)
    camara_laser.aplicar(top, cam.get("exposicion", -6), cam.get("saturacion", 80))
    wrist = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    wrist.set(cv2.CAP_PROP_FRAME_WIDTH, 640); wrist.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    mapa, gemelo = L.MapaEnVivo(), L.AlGemelo()
    print("Mostrando camaras en Rerun. Ctrl+C para salir (y SIEMPRE antes de grabar o desplegar).")
    n, t0 = 0, time.time()
    try:
        while True:
            ok, img = top.read()
            if ok:
                laser = L.buscar_laser(img)
                mapa.enviar(img, laser)
                marcada = L.marcar(img)
                gemelo.camara(marcada, laser)
                rr.log("top", rr.Image(cv2.cvtColor(marcada, cv2.COLOR_BGR2RGB)))
                rr.log("laser_visto", rr.Scalars(1.0 if laser else 0.0))
            ok2, w = wrist.read()
            if ok2:
                rr.log("wrist", rr.Image(cv2.cvtColor(w, cv2.COLOR_BGR2RGB)))
            n += 1
            if n % 150 == 0:
                print(f"{n / (time.time() - t0):.0f} fps")
    except KeyboardInterrupt:
        pass
    finally:
        top.release(); wrist.release()


if __name__ == "__main__":
    main()
