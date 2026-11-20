"""Prueba de la vision con fotos sinteticas (no hace falta camara, laser ni robot).

    python tests/test_vision.py            (imprime OK/FALLO y guarda tests/vista_prueba.png)
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "app"))
import vision  # noqa: E402

CFG = vision.cargar_config()
ANCHO, ALTO = CFG["mesa_cm"]["ancho"], CFG["mesa_cm"]["alto"]
# la camara ve la mesa en perspectiva (trapecio), como en el puesto
ESQ = [(150, 90), (500, 100), (600, 420), (40, 400)]
ZONAS = {"INICIO": (20.0, 24.0), "A": (8.0, 9.0), "B": (32.0, 9.0)}
CALIB = {"esquinas_px": ESQ, "zonas_cm": {k: list(v) for k, v in ZONAS.items()}}


def foto(laser_cm=None, cubiletes_cm=(), color="rojo", ruido=True):
    rng = np.random.default_rng(0)
    img = np.full((480, 640, 3), (60, 55, 50), np.uint8)                       # mesa del puesto (oscura)
    cv2.fillPoly(img, [np.int32(ESQ)], (200, 205, 210))                         # carton claro
    for x, y in ESQ:
        cv2.rectangle(img, (x - 6, y - 6), (x + 6, y + 6), (40, 170, 230), -1)  # cinta de las esquinas
    mesa = vision.Mesa(CFG, CALIB)
    for c in cubiletes_cm:                                                      # cubilete negro (41 mm)
        poly = [mesa.a_px((c[0] + 2.05 * np.cos(t), c[1] + 2.05 * np.sin(t))) for t in np.linspace(0, 2 * np.pi, 40)]
        cv2.fillPoly(img, [np.int32(poly)], (25, 25, 28))
    cv2.circle(img, (330, 350), 9, (40, 40, 150), -1)       # objeto rojo oscuro (no debe confundirse con el laser)
    if laser_cm is not None:
        x, y = (int(round(v)) for v in mesa.a_px(laser_cm))
        halo = (70, 255, 90) if color == "verde" else (90, 90, 255)
        cv2.circle(img, (x, y), 6, halo, -1)
        cv2.circle(img, (x, y), 2, (255, 255, 255), -1)     # centro saturado
    if ruido:
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    return img


def main():
    mesa = vision.Mesa(CFG, CALIB)
    fallos = []

    def check(nombre, cond):
        print(f"  {'OK   ' if cond else 'FALLO'} {nombre}")
        if not cond:
            fallos.append(nombre)

    # geometria: ida y vuelta pixeles <-> cm
    p = mesa.a_px((12.3, 21.7))
    check("pixeles <-> centimetros", np.allclose(mesa.a_cm(p), (12.3, 21.7), atol=0.05))

    img = foto(laser_cm=(31.0, 10.0), cubiletes_cm=[ZONAS["INICIO"]])
    las = vision.detectar_laser(img, CFG["laser"])
    cm = mesa.a_cm(las[:2]) if las else None
    check("ve el laser", las is not None)
    check("el laser esta donde debe (< 1 cm)", cm is not None and np.hypot(*(cm - (31.0, 10.0))) < 1.0)
    check("el laser cae en la zona B", cm is not None and mesa.zona_de(cm) == "B")
    cubs = vision.detectar_cubiletes(mesa.mapa(img), CFG["cubilete"])
    check("ve 1 cubilete", len(cubs) == 1)
    check("el cubilete esta en INICIO", len(cubs) == 1 and mesa.zona_de(cubs[0], incluir_inicio=True) == "INICIO")

    check("sin laser no inventa uno", vision.detectar_laser(foto(cubiletes_cm=[ZONAS["INICIO"]]), CFG["laser"]) is None)
    img2 = foto(laser_cm=(20.0, 15.0))
    las2 = vision.detectar_laser(img2, CFG["laser"])
    check("laser entre zonas -> fuera de zona", las2 is not None and mesa.zona_de(mesa.a_cm(las2[:2])) is None)
    verde = dict(CFG["laser"], color="verde")
    las3 = vision.detectar_laser(foto(laser_cm=(8.5, 9.5), color="verde"), verde)
    check("laser verde en zona A", las3 is not None and mesa.zona_de(mesa.a_cm(las3[:2])) == "A")

    seg = vision.SeguidorLaser(1.0)
    r = [seg.actualizar("A", t) for t in (0.0, 0.5, 1.1)]
    check("espera 1 s quieto antes de decidir", r == [None, None, "A"])
    r2 = [seg.actualizar(z, t) for z, t in (("B", 2.0), ("A", 2.5), ("A", 3.0))]
    check("si el laser se mueve, vuelve a esperar", r2 == [None, None, None])

    # imagen del mapa virtual para ver como queda
    import matplotlib
    matplotlib.use("Agg")
    from mapa import Vista, leer_escena  # noqa: E402
    v = Vista(mesa)
    laser, cm, zona, cubs = leer_escena(img, mesa, CFG)
    v.dibujar(img, laser, cubs, f"Prueba: láser → zona {zona} · cubiletes: {len(cubs)}", destino=zona)
    v.fig.savefig(AQUI / "vista_prueba.png", dpi=80)
    print(f"  (vista guardada en {AQUI / 'vista_prueba.png'})")

    print("RESULTADO:", "TODO OK" if not fallos else f"{len(fallos)} FALLOS")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
