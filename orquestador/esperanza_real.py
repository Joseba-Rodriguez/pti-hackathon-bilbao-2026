"""Esperanza con el robot REAL: esqueleto del orquestador para el hackathon.

Lanza las dos politicas con lerobot-rollout y, entre una y otra, mira la marca verde
con la camara del puesto (OpenCV) y avisa a la familia por Telegram.
NO probado con el brazo real (no lo tenemos): probarlo el sabado paso a paso.

Antes de cada movimiento pregunta si hay una persona mirando con la mano en la alimentacion.

Preparacion (una vez, con el puesto montado):
  1) python orquestador/esperanza_real.py calibrar --camara 1     (SIN vasito en la marca)
       se abre la imagen: clic en el CENTRO de la marca verde y luego en su BORDE. Se guarda en esperanza_real.json
  2) con un vasito LLENO de cada color en la marca:
       python orquestador/esperanza_real.py color manana --camara 1
       python orquestador/esperanza_real.py color mediodia --camara 1
       python orquestador/esperanza_real.py color noche --camara 1
  3) con un vasito VACIO en la marca:   python orquestador/esperanza_real.py vacio --camara 1

Uso:
  python orquestador/esperanza_real.py toma noche --simulacro      (no mueve nada: imprime los comandos)
  python orquestador/esperanza_real.py toma noche                  (de verdad)
  python orquestador/esperanza_real.py mirar --imagen foto.png     (probar la vision con una foto)

Variables: TELEGRAM_TOKEN y TELEGRAM_CHAT (si no estan, el mensaje se imprime).
Editar CONFIG abajo con los puertos, camaras y repos del puesto.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# EDITAR: el puerto del follower (lerobot-find-port, p. ej. COM7) y los indices de las camaras.
CONFIG = {
    "robot": ["--robot.type=so101_follower", "--robot.port=COM_FOLLOWER", "--robot.id=esperanza_follower",
              "--robot.cameras={ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, "
              "wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }"],
    "politicas": {
        "entregar": ("Josebarv01/act_esperanza_entregar",
                     "take the first cup from the loader and place it on the green mark", 20),
        "recoger": ("Josebarv01/act_esperanza_recoger",
                    "pick up the empty cup from the green mark and drop it into the used box", 20),
    },
    "espera_toma_s": 120,   # cuanto se espera a que devuelva el vasito vacio antes de la alerta
}
NOMBRE = {"manana": "de la mañana", "mediodia": "del mediodía", "noche": "de la noche"}
CAL = Path(__file__).with_name("esperanza_real.json")


# ------------------------------------------------------------------ utilidades
def decir(texto):
    print(f"[VOZ] {texto}", flush=True)
    try:
        import pyttsx3
        e = pyttsx3.init(); e.say(texto); e.runAndWait()
    except Exception:
        pass


def familia(texto):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if tok and chat:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=10)
            print(f"[FAMILIA] (Telegram) {texto}")
            return
        except Exception as e:
            print(f"[FAMILIA] Telegram fallo: {e}")
    print(f"[FAMILIA] {texto}")


def foto(camara: int) -> np.ndarray:
    cap = cv2.VideoCapture(camara)
    for _ in range(5):            # descartar los primeros fotogramas (exposicion)
        cap.read()
    ok, img = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"no puedo leer la camara {camara} (¿la tiene abierta lerobot?)")
    return img


def cargar_cal() -> dict:
    return json.loads(CAL.read_text()) if CAL.exists() else {}


def guardar_cal(c: dict):
    CAL.write_text(json.dumps(c, indent=2))
    print(f"guardado en {CAL}")


def recorte(img, cal):
    (cx, cy), r = cal["marca"], cal["radio"]
    R = int(r * 1.5)
    crop = img[max(0, cy - R):cy + R, max(0, cx - R):cx + R]
    return cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)


def lejos(hue, h, tol=12):
    d = np.abs(hue - h)
    return np.minimum(d, 180 - d) >= tol      # el tono es circular (0 = 180)


def validos(hsv, cal):
    """Pixeles con color propio que no son ni la marca verde ni el fondo (mesa/mantel)."""
    hue = hsv[..., 0].astype(int)
    ok = (hsv[..., 1] > 90) & (hsv[..., 2] > 50) & lejos(hue, cal.get("verde", 60))
    for f in cal.get("fondo", []):
        ok &= lejos(hue, f, 8)
    return ok


def mirar(img, cal) -> dict:
    """{'toma': key|None, 'llena': bool|None} con los colores aprendidos en la calibracion."""
    hsv = recorte(img, cal)
    sat = validos(hsv, cal)
    hue = hsv[..., 0].astype(int)
    best, best_n = None, 0
    for key, h in cal.get("colores", {}).items():
        n = int((sat & ~lejos(hue, h, 8)).sum())
        if n > best_n:
            best, best_n = key, n
    if best is None or best_n < 0.08 * hue.size:
        return {"toma": None, "llena": None}
    # pastillas = pixeles saturados que no son ni el vasito ni la marca verde, en el centro
    h, w = hue.shape
    yy, xx = np.mgrid[:h, :w]
    centro = (yy - h / 2) ** 2 + (xx - w / 2) ** 2 < (0.35 * min(h, w)) ** 2
    otros = sat & centro & lejos(hue, cal["colores"][best])
    frac = otros.sum() / max(1, centro.sum())
    umbral = cal.get("umbral_pastillas", 0.03)
    return {"toma": best, "llena": bool(frac > umbral), "frac_pastillas": round(float(frac), 3)}


def rollout(skill: str, simulacro: bool) -> bool:
    repo, task, dur = CONFIG["politicas"][skill]
    cmd = ["lerobot-rollout", "--strategy.type=base", f"--policy.path={repo}", *CONFIG["robot"],
           f"--task={task}", f"--duration={dur}"]
    print("[ROBOT] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    if simulacro:
        return True
    if input("¿Hay una persona mirando el brazo con la mano en la alimentación? (s/n) ").strip().lower() != "s":
        print("cancelado")
        return False
    return subprocess.run(cmd).returncode == 0


# --------------------------------------------------------------------- ordenes
def cmd_calibrar(a):
    img = cv2.imread(a.imagen) if getattr(a, "imagen", None) else foto(a.camara)
    # lerobot trae OpenCV sin ventanas: el clic se hace con matplotlib
    import matplotlib.pyplot as plt
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title("Clic 1: CENTRO de la marca verde.  Clic 2: su BORDE")
    pts = [(int(x), int(y)) for x, y in plt.ginput(2, timeout=0)]
    plt.close()
    if len(pts) < 2:
        print("cancelado")
        return
    c = cargar_cal()
    c["marca"] = list(pts[0])
    c["radio"] = int(np.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
    c.update(fondo_y_verde(img, c))
    guardar_cal(c)


def fondo_y_verde(img, c) -> dict:
    """Tono de la marca (dentro del circulo) y del fondo (anillo de alrededor), sin vasito en la marca."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    d = np.hypot(xx - c["marca"][0], yy - c["marca"][1])
    hue, sat = hsv[..., 0], hsv[..., 1] > 60
    dentro, anillo = (d < 0.8 * c["radio"]) & sat, (d > 1.4 * c["radio"]) & (d < 2.2 * c["radio"]) & sat
    out = {"verde": int(np.median(hue[dentro])) if dentro.any() else 60}
    out["fondo"] = [int(np.median(hue[anillo]))] if anillo.any() else []
    return out


def cmd_color(a):
    c = cargar_cal()
    hsv = recorte(foto(a.camara), c)
    c.setdefault("colores", {})[a.toma] = int(np.median(hsv[..., 0][validos(hsv, c)]))
    print(f"tono de {a.toma}: {c['colores'][a.toma]}")
    guardar_cal(c)


def cmd_vacio(a):
    c = cargar_cal()
    r = mirar(foto(a.camara), c)
    c["umbral_pastillas"] = round(max(0.02, r.get("frac_pastillas", 0) * 2 + 0.01), 3)
    print(f"vacio visto: {r}; umbral de pastillas = {c['umbral_pastillas']}")
    guardar_cal(c)


def cmd_mirar(a):
    img = cv2.imread(a.imagen) if a.imagen else foto(a.camara)
    print(mirar(img, cargar_cal()))


def cmd_toma(a):
    cal = cargar_cal()
    ver = (lambda: {"toma": a.toma, "llena": True}) if a.simulacro else (lambda: mirar(foto(a.camara), cal))
    decir(f"Esperanza, tu toma {NOMBRE[a.toma]}.")
    if not rollout("entregar", a.simulacro):
        familia(f"Aviso: no he podido entregar la toma {NOMBRE[a.toma]}.")
        return
    v = ver()
    print(f"[CAMARA] {v}")
    if v["toma"] != a.toma or not v["llena"]:
        familia(f"Aviso: el vasito entregado no es la toma {NOMBRE[a.toma]} o está vacío ({v}). No lo tome.")
        return
    t0 = time.time()
    while True:                     # esperar a que vuelva vacio
        if a.simulacro:
            v = {"toma": a.toma, "llena": False}
        else:
            time.sleep(3)
            v = ver()
        if v["toma"] is not None and v["llena"] is False:
            break
        if time.time() - t0 > CONFIG["espera_toma_s"]:
            decir("Esperanza, recuerda tu toma.")
            familia(f"Alerta: Esperanza no se ha tomado la toma {NOMBRE[a.toma]}.")
            return
    print(f"[CAMARA] devuelto: {v}")
    rollout("recoger", a.simulacro)
    familia(f"Esperanza se ha tomado la toma {NOMBRE[a.toma]} a las {datetime.now():%H:%M}.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    for name in ("calibrar", "color", "vacio", "mirar", "toma"):
        s = sub.add_parser(name)
        s.add_argument("--camara", type=int, default=1)
        if name in ("color", "toma"):
            s.add_argument("toma", choices=list(NOMBRE))
        if name in ("mirar", "calibrar"):
            s.add_argument("--imagen", default=None)
        if name == "toma":
            s.add_argument("--simulacro", action="store_true")
    a = p.parse_args()
    {"calibrar": cmd_calibrar, "color": cmd_color, "vacio": cmd_vacio, "mirar": cmd_mirar, "toma": cmd_toma}[a.orden](a)


if __name__ == "__main__":
    sys.exit(main())
