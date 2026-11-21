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
UMBRAL = MARCA.get("umbral", 80)             # cuanto destaca el rojo del punto sobre su entorno
BRILLO_MIN = MARCA.get("brillo_min", 190)    # canal rojo (laser ~230; base naranja <= ~160)
# zona donde buscar (pixeles): la cartulina calibrada si existe app/calibracion.json
try:
    POLIGONO = np.int32(json.loads((AQUI.parent / "app" / "calibracion.json").read_text())["esquinas_px"])
except Exception:
    POLIGONO = None
AREA_MAX = MARCA.get("area_max_px", 60)      # manchas mayores (base naranja...) no son el laser
RADIO = MARCA.get("radio_px", 12)            # tamano del circulo dibujado
ROJIZO = MARCA.get("rojizo", 35)             # rojo - max(verde, azul) para considerar "pieza del brazo"
AREA_BRAZO = MARCA.get("area_brazo_px", 250) # mancha rojiza mayor que esto = brazo (el laser es ~10-60 px)
MARGEN_BRAZO = MARCA.get("margen_brazo_px", 4)  # el laser debe estar al menos a ~4 px del brazo


def buscar_laser(bgr: np.ndarray):
    """El laser es un PICO diminuto y muy brillante; las piezas naranjas del robot son manchas
    grandes de rojo mas apagado. Top-hat: rojo del pixel menos el rojo "de fondo" de su entorno
    (apertura 11x11), asi una zona roja grande da ~0 y solo sobreviven los puntos pequenos."""
    b, g, r = (bgr[..., i].astype(np.int16) for i in range(3))
    score = np.clip(r - np.maximum(g, b), 0, 255).astype(np.uint8)
    pico = cv2.morphologyEx(score, cv2.MORPH_TOPHAT, np.ones((11, 11), np.uint8)).astype(np.int16)
    mask = ((pico > UMBRAL) & (r > BRILLO_MIN)).astype(np.uint8)
    if POLIGONO is not None:                                  # solo dentro de la cartulina
        dentro = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(dentro, [POLIGONO], 1)
        mask &= dentro
    if not mask.any():
        return None
    if not mask.any():
        return None
    # el BRAZO: todo lo rojizo/naranja aunque sea apagado, engordado unos pixeles. Si un
    # candidato cae en una mancha rojiza GRANDE, es una pieza del brazo, no el laser.
    rojizo = ((score > ROJIZO) & (r > 60)).astype(np.uint8)
    rojizo = cv2.dilate(rojizo, np.ones((2 * MARGEN_BRAZO + 1,) * 2, np.uint8))
    nr, lab_r, st_r, _ = cv2.connectedComponentsWithStats(rojizo)
    grande = np.zeros(nr, bool)
    grande[1:] = st_r[1:, cv2.CC_STAT_AREA] > AREA_BRAZO
    mask[grande[lab_r]] = 0
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


# ----------------------------------------------------------------------------- detector v2
# v1 (arriba) pide "rojo > 190 y rojo >> verde/azul": va bien sobre fondo oscuro, pero sobre la mesa
# blanca con luz de dia el fondo ya tiene ~180 en los tres canales y el punto apenas destaca.
# v2 mide el punto CONTRA SU ENTORNO (cuanto sube el rojo respecto a lo que hay alrededor y cuanto
# mas sube el rojo que el verde/azul) y ademas lo SIGUE entre fotogramas: si se pierde un instante
# (desenfoque al moverlo, parpadeo) lo busca cerca de donde estaba con umbral mas bajo y mantiene
# el circulo unos pocos fotogramas. El circulo dibujado es EXACTAMENTE el mismo que en v1.
DETECTOR = MARCA.get("detector", "v2")
V2_SUBIDA_ROJO = MARCA.get("v2_subida_rojo", 45)     # rojo del punto - rojo del entorno
V2_ROJEZ = MARCA.get("v2_rojez", 30)                 # (subida del rojo) - (subida de verde/azul)
V2_BUSQUEDA_PX = MARCA.get("v2_busqueda_px", 45)     # radio de busqueda cerca del ultimo punto
V2_MANTENER = MARCA.get("v2_mantener_fotogramas", 4) # fotogramas que se mantiene si se pierde (~0,13 s)
V2_MARGEN_BRAZO = MARCA.get("v2_margen_brazo_px", 14) # distancia minima al brazo naranja (brillos del brazo)
# zona donde se busca (pixeles x0, y0, x1, y1): las 6 casillas lejanas. Fuera quedan la base del
# robot (arriba), el soporte (arriba-izquierda) y los bordes de la imagen, donde v2 daba falsos.
V2_ZONA = MARCA.get("v2_zona_px", [110, 195, 590, 470])


def _candidatos_v2(bgr: np.ndarray, factor: float = 1.0, centro=None):
    b, g, r = (bgr[..., i].astype(np.int16) for i in range(3))
    k = np.ones((15, 15), np.uint8)
    fondo = cv2.morphologyEx(bgr, cv2.MORPH_OPEN, k).astype(np.int16)   # lo que hay alrededor sin el punto
    dr = r - fondo[..., 2]
    dgb = np.maximum(g - fondo[..., 1], b - fondo[..., 0])
    mask = ((dr > V2_SUBIDA_ROJO * factor) & (dr - dgb > V2_ROJEZ * factor)).astype(np.uint8)
    x0, y0, x1, y1 = V2_ZONA
    zona = np.zeros(mask.shape, np.uint8)
    zona[y0:y1, x0:x1] = 1
    mask &= zona
    if POLIGONO is not None:
        dentro = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(dentro, [POLIGONO], 1)
        mask &= dentro
    if centro is not None:                                   # solo cerca del ultimo punto
        cerca = np.zeros(mask.shape, np.uint8)
        cv2.circle(cerca, centro, V2_BUSQUEDA_PX, 1, -1)
        mask &= cerca
    if not mask.any():
        return None
    score = np.clip(r - np.maximum(g, b), 0, 255)             # mismo rechazo del brazo que v1
    rojizo = ((score > ROJIZO) & (r > 60)).astype(np.uint8)
    rojizo = cv2.dilate(rojizo, np.ones((2 * V2_MARGEN_BRAZO + 1,) * 2, np.uint8))
    nr, lab_r, st_r, _ = cv2.connectedComponentsWithStats(rojizo)
    grande = np.zeros(nr, bool)
    grande[1:] = st_r[1:, cv2.CC_STAT_AREA] > AREA_BRAZO
    mask[grande[lab_r]] = 0
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask)
    best = None
    fuerza = dr - dgb
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > AREA_MAX:
            continue
        f = int(fuerza[lab == i].max())
        if best is None or f > best[2]:
            best = (int(round(cent[i][0])), int(round(cent[i][1])), f)
    return best


class Seguidor:
    """Recuerda el ultimo punto para no perderlo en un parpadeo o al moverlo rapido."""

    def __init__(self):
        self.ultimo, self.perdidos = None, 0

    def __call__(self, bgr: np.ndarray):
        p = _candidatos_v2(bgr)
        if p is None and self.ultimo is not None:            # perdido: buscar cerca, mas permisivo
            p = _candidatos_v2(bgr, factor=0.6, centro=self.ultimo)
        if p is not None:
            self.ultimo, self.perdidos = p[:2], 0
            return p
        if self.ultimo is not None and self.perdidos < V2_MANTENER:
            self.perdidos += 1
            return (*self.ultimo, 0)                           # mantener el circulo un instante
        self.ultimo = None
        return None


_seguidor = Seguidor()


def detectar(bgr: np.ndarray):
    """Lo que usan grabar/desplegar: v2 con seguimiento, o v1 si config dice detector = v1."""
    return _seguidor(bgr) if DETECTOR == "v2" else buscar_laser(bgr)


def marcar(bgr: np.ndarray, p="buscar") -> np.ndarray:
    if isinstance(p, str):
        p = detectar(bgr)
    if p is None:
        return bgr
    out = bgr.copy()
    cv2.circle(out, p[:2], RADIO, (0, 0, 255), -1)          # rojo puro (BGR)
    cv2.circle(out, p[:2], max(2, RADIO // 3), (255, 255, 255), -1)
    return out


class MapaEnVivo:
    """Si existe app/calibracion.json, envia a Rerun la mesa vista desde arriba (cm) con las
    zonas y el laser, unas 5 veces por segundo. Solo se ve en pantalla: NO se graba en el dataset."""

    def __init__(self):
        self.mesa, self.t = None, 0.0
        try:
            sys.path.insert(0, str(AQUI.parent / "app"))
            import vision
            self.vision = vision
            self.mesa = vision.Mesa(CFG, vision.cargar_calibracion())
            print("[mapa] calibracion encontrada: el mapa se vera en Rerun (entidad 'mapa')")
        except BaseException as e:                       # cargar_calibracion lanza SystemExit
            print(f"[mapa] sin mapa (falta calibrar con  python ..\\app\\calibrar.py): {e}")

    def enviar(self, bgr: np.ndarray, laser):
        import time
        if self.mesa is None or time.time() - self.t < 0.2:
            return
        self.t = time.time()
        try:
            import rerun as rr
            m, P = self.mesa, self.vision.PX_POR_CM
            mapa = m.mapa(bgr)
            for z, c in m.zonas.items():
                if m.dentro(c):
                    cv2.circle(mapa, (int(c[0] * P), int(c[1] * P)), int(m.radio * P), (255, 200, 0), 2)
                    cv2.putText(mapa, z, (int(c[0] * P) - 10, int(c[1] * P) + 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 0), 2)
            if laser is not None:
                cm = m.a_cm(laser[:2])
                if m.dentro(cm):
                    cv2.drawMarker(mapa, (int(cm[0] * P), int(cm[1] * P)), (0, 0, 255),
                                   cv2.MARKER_STAR, 40, 3)
                    cv2.putText(mapa, f"laser ({cm[0]:.0f}, {cm[1]:.0f}) cm", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            rr.log("mapa", rr.Image(cv2.cvtColor(mapa, cv2.COLOR_BGR2RGB)))
        except Exception:
            pass                                          # el mapa nunca debe parar la grabacion


class AlGemelo:
    """Envia por UDP local a herramientas/gemelo.py las articulaciones, el laser y la imagen
    cenital. UDP sin conexion: si el gemelo no esta abierto, no pasa nada."""

    def __init__(self):
        import socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.t_img = 0.0

    def _tx(self, datos: bytes, puerto: int):
        try:
            self.s.sendto(datos, ("127.0.0.1", puerto))
        except Exception:
            pass                                          # nunca debe parar el robot

    def estado(self, q: dict):
        self._tx(json.dumps({"q": q}).encode(), 5055)

    def camara(self, bgr: np.ndarray, laser):
        import time
        self._tx(json.dumps({"laser": None if laser is None else list(laser[:2])}).encode(), 5055)
        if time.time() - self.t_img > 0.08:               # ~12 imagenes/s, cabe en un datagrama
            self.t_img = time.time()
            ok, buf = cv2.imencode(".jpg", cv2.resize(bgr, (480, 360)), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok and len(buf) < 60000:
                self._tx(buf.tobytes(), 5056)


def instalar_filtro():
    from lerobot.cameras.opencv import camera_opencv as co

    original = co.OpenCVCamera._postprocess_image
    indice = CFG["camara"]["indice"]
    mapa = MapaEnVivo()
    gemelo = AlGemelo()

    def _postprocess_image(self, image):
        if str(self.index_or_path) == str(indice):            # solo la camara cenital
            laser = detectar(image)                           # image llega en BGR (OpenCV)
            mapa.enviar(image, laser)
            image = marcar(image, laser)
            gemelo.camara(image, laser)
        return original(self, image)

    co.OpenCVCamera._postprocess_image = _postprocess_image

    try:                                                  # articulaciones reales -> gemelo digital
        from lerobot.robots.so_follower.so_follower import SOFollower
        obs_original = SOFollower.get_observation

        def get_observation(self, *a, **k):
            obs = obs_original(self, *a, **k)
            try:
                gemelo.estado({kk[:-4]: float(v) for kk, v in obs.items() if kk.endswith(".pos")})
            except Exception:
                pass
            return obs

        SOFollower.get_observation = get_observation
        print("[gemelo] enviando articulaciones y camara a herramientas/gemelo.py (UDP 5055/5056)")
    except Exception as e:
        print(f"[gemelo] no disponible: {e}")
    print(f"[filtro laser] activo en la camara {indice} (detector {DETECTOR}, circulo {RADIO} px)")


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
    # Parada desde la web (gemelo.py manda CTRL_BREAK): convertirla en el mismo Ctrl+C de siempre,
    # para que lerobot cierre limpio (para el bucle y desconecta el robot) en vez de morir de golpe.
    import signal
    if hasattr(signal, "SIGBREAK"):
        def _parar(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGBREAK, _parar)
    # Al conectar, lerobot escribe la configuracion de cada servo (par, Lock...) con UN solo intento
    # (num_retry=0): un paquete perdido en el bus y se cae todo ("There is no status packet").
    # Reintentamos esas escrituras sueltas hasta 3 veces. Las ordenes de movimiento van por sync_write
    # y no pasan por aqui.
    try:
        from lerobot.motors.feetech.feetech import FeetechMotorsBus
        _write = FeetechMotorsBus.write

        def write(self, *a, num_retry: int = 0, **k):
            return _write(self, *a, num_retry=max(num_retry, 3), **k)

        FeetechMotorsBus.write = write
    except Exception as e:
        print(f"[reintentos] no aplicados: {e}")
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
