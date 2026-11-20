"""Vision de la mesa: camara -> mapa virtual (centimetros), laser, zonas y cubiletes.

Todo con OpenCV y numpy, sin modelos: rapido y facil de ajustar en el puesto.
La calibracion (calibrar.py) guarda en calibracion.json:
  - las 4 esquinas de la mesa en la imagen (pixeles)
  - el centro de INICIO y de cada zona de destino (centimetros de mesa)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "config.json"
CALIB = AQUI / "calibracion.json"
PX_POR_CM = 10          # resolucion del mapa virtual


def cargar_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def cargar_calibracion() -> dict:
    if not CALIB.exists():
        raise SystemExit("Falta la calibracion: ejecuta primero  python app/calibrar.py")
    return json.loads(CALIB.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ camara
class Camara:
    """Abre la camara solo mientras se usa (lerobot-rollout necesita la misma camara libre)."""

    def __init__(self, cfg: dict, imagen: str | None = None):
        self.cfg, self.imagen, self.cap = cfg["camara"], imagen, None

    def foto(self) -> np.ndarray:
        if self.imagen:
            img = cv2.imread(self.imagen)
            if img is None:
                raise SystemExit(f"No puedo leer la imagen {self.imagen}")
            return img
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.cfg["indice"])
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["ancho"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["alto"])
            for _ in range(5):          # la exposicion tarda unos fotogramas en ajustarse
                self.cap.read()
        ok, img = self.cap.read()
        if not ok:
            raise RuntimeError(f"No puedo leer la camara {self.cfg['indice']} (¿la tiene abierta otro programa?)")
        return img

    def soltar(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            time.sleep(0.3)


# ---------------------------------------------------------------- geometria
class Mesa:
    """Pasa de pixeles de la camara a centimetros de mesa y al reves."""

    def __init__(self, cfg: dict, calib: dict):
        self.ancho, self.alto = cfg["mesa_cm"]["ancho"], cfg["mesa_cm"]["alto"]
        src = np.float32(calib["esquinas_px"])                     # sup-izq, sup-der, inf-der, inf-izq
        dst = np.float32([[0, 0], [self.ancho, 0], [self.ancho, self.alto], [0, self.alto]])
        self.H = cv2.getPerspectiveTransform(src, dst)
        self.Hinv = np.linalg.inv(self.H)
        self.zonas = {k: np.float32(v) for k, v in calib["zonas_cm"].items()}  # incluye "INICIO"
        self.radio = cfg["zona_radio_cm"]
        self.poligono_px = np.float32(calib["esquinas_px"])      # la mesa en la imagen

    def a_cm(self, px) -> np.ndarray:
        p = cv2.perspectiveTransform(np.float32([[px]]), self.H)[0, 0]
        return p

    def a_px(self, cm) -> np.ndarray:
        return cv2.perspectiveTransform(np.float32([[cm]]), self.Hinv)[0, 0]

    def dentro(self, cm) -> bool:
        return 0 <= cm[0] <= self.ancho and 0 <= cm[1] <= self.alto

    def zona_de(self, cm, incluir_inicio=False) -> str | None:
        best, dmin = None, self.radio
        for k, c in self.zonas.items():
            if k == "INICIO" and not incluir_inicio:
                continue
            d = float(np.hypot(*(np.asarray(cm) - c)))
            if d <= dmin:
                best, dmin = k, d
        return best

    def mapa(self, img: np.ndarray) -> np.ndarray:
        """Vista cenital rectificada de la mesa (PX_POR_CM pixeles por centimetro)."""
        S = np.diag([PX_POR_CM, PX_POR_CM, 1.0])
        return cv2.warpPerspective(img, S @ self.H, (int(self.ancho * PX_POR_CM), int(self.alto * PX_POR_CM)))


# -------------------------------------------------------------------- laser
def detectar_laser(img: np.ndarray, cfg_laser: dict, area_px=None):
    """Punto del laser en la imagen: (x_px, y_px, intensidad) o None.

    El centro del punto suele salir blanco (saturado) y alrededor un halo del color del
    laser; se busca ese halo (canal del color muy por encima de los otros dos y brillante)
    y se toma el centro de la mancha mas intensa de tamano razonable.
    ``area_px``: poligono (pixeles) donde buscar, p. ej. la mesa calibrada. Fuera de el se
    ignora todo (la base naranja del robot, un cuter...).
    """
    b, g, r = (img[..., i].astype(np.int16) for i in range(3))
    if cfg_laser["color"] == "verde":
        canal, score = g, g - np.maximum(r, b)
    else:
        canal, score = r, r - np.maximum(g, b)
    mask = ((score > cfg_laser["umbral"]) & (canal > cfg_laser["brillo_min"])).astype(np.uint8)
    if area_px is not None:
        dentro = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(dentro, [np.int32(area_px)], 1)
        mask &= dentro
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))       # une el halo alrededor del centro blanco
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask)
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if not cfg_laser["area_min_px"] <= area <= cfg_laser["area_max_px"]:
            continue
        fuerza = int(score[lab == i].max())
        if best is None or fuerza > best[2]:
            best = (float(cent[i][0]), float(cent[i][1]), fuerza)
    return best


# ---------------------------------------------------------------- cubiletes
def detectar_cubiletes(mapa_img: np.ndarray, cfg_cub: dict) -> list[tuple[float, float]]:
    """Centros (cm) de los cubiletes en el mapa rectificado.

    ``tapa: "clara"``: cubilete con tapa blanca sobre fondo oscuro (pixeles MAS claros que el umbral).
    ``tapa: "oscura"``: cubilete negro sobre fondo claro (pixeles MAS oscuros que el umbral).
    """
    gris = cv2.cvtColor(mapa_img, cv2.COLOR_BGR2GRAY)
    if cfg_cub.get("tapa", "oscura") == "clara":
        mask = (gris > cfg_cub["umbral_gris"]).astype(np.uint8)
    else:
        mask = (gris < cfg_cub["umbral_gris"]).astype(np.uint8)
    # ignorar el borde de la cartulina: ahi asoma la mesa (blanca) y no habra cubiletes
    b = int(cfg_cub.get("margen_borde_cm", 2) * PX_POR_CM)
    if b > 0:
        mask[:b, :] = 0; mask[-b:, :] = 0; mask[:, :b] = 0; mask[:, -b:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, _, stats, cent = cv2.connectedComponentsWithStats(mask)
    a_min, a_max = cfg_cub["area_min_cm2"] * PX_POR_CM ** 2, cfg_cub["area_max_cm2"] * PX_POR_CM ** 2
    return [(float(cent[i][0]) / PX_POR_CM, float(cent[i][1]) / PX_POR_CM)
            for i in range(1, n) if a_min <= stats[i, cv2.CC_STAT_AREA] <= a_max]


class SeguidorLaser:
    """Confirma una zona cuando el laser se queda quieto en ella `segundos_quieto` segundos."""

    def __init__(self, segundos: float):
        self.segundos, self.zona, self.desde = segundos, None, 0.0

    def actualizar(self, zona: str | None, ahora: float | None = None) -> str | None:
        ahora = time.time() if ahora is None else ahora
        if zona != self.zona:
            self.zona, self.desde = zona, ahora
            return None
        if zona is not None and ahora - self.desde >= self.segundos:
            return zona
        return None
