"""Comprueba si la camara cenital se ha MOVIDO o ha cambiado de BRILLO respecto a una grabacion.
Solo lee la camara (no cambia ajustes). Cerrar antes record/rollout/ver_camaras.

    python ..\\herramientas\\comprobar_camara.py                 (compara con pti_laser_G_quieto)
    python ..\\herramientas\\comprobar_camara.py pti_coger_v7    (con otro dataset)

Guarda E:\\HACKATONLeRobot\\_copias\\comprobar_camara.jpg: grabacion | ahora | las dos superpuestas
(si en la superpuesta se ve doble, la camara se ha movido).
"""

import sys
from pathlib import Path

import cv2
import numpy as np

ds = sys.argv[1] if len(sys.argv) > 1 else "pti_laser_G_quieto"
video = Path(rf"E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01\{ds}\videos\observation.images.top\chunk-000\file-000.mp4")
ok, ref = cv2.VideoCapture(str(video)).read()
if not ok:
    raise SystemExit(f"No puedo leer {video}")
cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
for _ in range(15):
    ok, now = cap.read()
cap.release()
if not ok:
    raise SystemExit("No puedo leer la camara 2 (¿la usa otro programa?)")

g1, g2 = (cv2.equalizeHist(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)) for x in (ref, now))
orb = cv2.ORB_create(3000)
k1, d1 = orb.detectAndCompute(g1, None)
k2, d2 = orb.detectAndCompute(g2, None)
m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2), key=lambda x: x.distance)[:400]
p1 = np.float32([k1[x.queryIdx].pt for x in m]); p2 = np.float32([k2[x.trainIdx].pt for x in m])
A, inl = cv2.estimateAffinePartial2D(p1, p2, ransacReprojThreshold=3)
dx, dy = A[0, 2], A[1, 2]
giro = np.degrees(np.arctan2(A[1, 0], A[0, 0]))
movido = abs(dx) > 4 or abs(dy) > 4 or abs(giro) > 0.5
print(f"Posicion: desplazada {dx:+.1f} px en x, {dy:+.1f} px en y, giro {giro:+.2f} grados "
      f"-> {'SE HA MOVIDO: recolocar mirando la imagen superpuesta' if movido else 'OK (no se ha movido)'}")
b_ref, b_now = ref.mean(), now.mean()
print(f"Brillo: grabacion {b_ref:.0f}, ahora {b_now:.0f} -> "
      f"{'DISTINTO: ejecutar  python ..\\herramientas\\camara_laser.py --aplicar  y revisar la luz' if abs(b_now - b_ref) > 15 else 'OK'}")
out = Path(r"E:\HACKATONLeRobot\_copias\comprobar_camara.jpg")
cv2.imwrite(str(out), np.hstack([ref, now, cv2.addWeighted(ref, 0.5, now, 0.5, 0)]))
print(f"Imagen: {out}")
