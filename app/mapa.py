"""Mapa virtual en vivo: la camara y la mesa vista desde arriba (en centimetros),
con las zonas, los cubiletes detectados y el punto del laser.

    python app/mapa.py                     (camara en vivo; cerrar la ventana o pulsar q para salir)
    python app/mapa.py --imagen foto.png   (probar con una foto)
    python app/mapa.py --ajustar           (muestra que pixeles cree que son laser, para ajustar el umbral)
"""

from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

import vision

COLOR_ZONA = {"INICIO": "#9aa0a6"}
PALETA = ["#1a73e8", "#e8710a", "#188038", "#a142f4", "#d93025"]


class Vista:
    def __init__(self, mesa: vision.Mesa, titulo="Mapa virtual · equipo PTI"):
        import matplotlib.pyplot as plt
        self.plt, self.mesa = plt, mesa
        plt.ion()
        self.fig, (self.ax_cam, self.ax_map) = plt.subplots(1, 2, figsize=(13, 5.6))
        self.fig.canvas.manager.set_window_title(titulo)
        self.salir = False
        self.fig.canvas.mpl_connect("key_press_event", lambda e: setattr(self, "salir", e.key == "q" or self.salir))
        self.fig.canvas.mpl_connect("close_event", lambda e: setattr(self, "salir", True))

    def color(self, zona):
        otras = [k for k in self.mesa.zonas if k != "INICIO"]
        return COLOR_ZONA.get(zona) or PALETA[otras.index(zona) % len(PALETA)]

    def dibujar(self, img, laser=None, cubiletes=(), estado="", destino=None, mascara=None):
        m, ax_c, ax_m = self.mesa, self.ax_cam, self.ax_map
        ax_c.clear(); ax_m.clear()
        ax_c.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if mascara is None else mascara, cmap="gray")
        ax_c.set_title("Cámara del puesto" + (" (máscara del láser)" if mascara is not None else ""))
        esq = np.vstack([m.a_px(c) for c in [(0, 0), (m.ancho, 0), (m.ancho, m.alto), (0, m.alto), (0, 0)]])
        ax_c.plot(esq[:, 0], esq[:, 1], "-", color="lime", lw=1)
        mapa_img = m.mapa(img)
        ax_m.imshow(cv2.cvtColor(mapa_img, cv2.COLOR_BGR2RGB), extent=(0, m.ancho, m.alto, 0), alpha=0.55)
        for z, c in m.zonas.items():
            col = self.color(z)
            lw = 4 if z == destino else 2
            ax_m.add_patch(self.plt.Circle(c, m.radio, fill=False, ec=col, lw=lw, ls="--" if z == "INICIO" else "-"))
            ax_m.text(c[0], c[1] - m.radio - 0.8, z, ha="center", color=col, fontsize=12, weight="bold")
            px = m.a_px(c)
            ax_c.text(px[0], px[1], z, ha="center", va="center", color=col, fontsize=10, weight="bold")
        for (x, y) in cubiletes:
            ax_m.add_patch(self.plt.Circle((x, y), 2.05, color="#202124", alpha=0.9))
        if laser is not None:
            cm = m.a_cm(laser[:2])
            ax_c.plot(laser[0], laser[1], "o", ms=16, mfc="none", mec="red", mew=2)
            if m.dentro(cm):
                ax_m.plot(cm[0], cm[1], "*", ms=22, color="red", mec="white")
        # el mapa abarca la cartulina y tambien las zonas que esten fuera (p. ej. INICIO en el soporte)
        zs = np.array(list(m.zonas.values())) if m.zonas else np.zeros((0, 2))
        x0 = min([0] + list(zs[:, 0] - m.radio - 1)); x1 = max([m.ancho] + list(zs[:, 0] + m.radio + 1))
        y0 = min([0] + list(zs[:, 1] - m.radio - 2)); y1 = max([m.alto] + list(zs[:, 1] + m.radio + 1))
        ax_m.add_patch(self.plt.Rectangle((0, 0), m.ancho, m.alto, fill=False, ec="#5f6368", lw=1))
        ax_m.set_xlim(x0, x1); ax_m.set_ylim(y1, y0)
        ax_m.set_aspect("equal")
        ax_m.set_title(f"Mapa virtual ({m.ancho} × {m.alto} cm)")
        ax_m.set_xlabel("cm"); ax_c.axis("off")
        self.fig.suptitle(estado, fontsize=14, color="#202124")
        self.fig.canvas.draw_idle()
        self.plt.pause(0.001)


def leer_escena(img, mesa, cfg):
    """(laser_px o None, laser_cm o None, zona_del_laser, cubiletes_cm)."""
    laser = vision.detectar_laser(img, cfg["laser"], mesa.poligono_px)   # solo dentro de la mesa
    cm = mesa.a_cm(laser[:2]) if laser else None
    zona = mesa.zona_de(cm) if cm is not None and mesa.dentro(cm) else None
    cubiletes = vision.detectar_cubiletes(mesa.mapa(img), cfg["cubilete"])
    return laser, cm, zona, cubiletes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--imagen", default=None)
    p.add_argument("--ajustar", action="store_true")
    a = p.parse_args()
    cfg = vision.cargar_config()
    mesa = vision.Mesa(cfg, vision.cargar_calibracion())
    cam = vision.Camara(cfg, a.imagen)
    vista = Vista(mesa)
    t0, n = time.time(), 0
    try:
        while not vista.salir:
            img = cam.foto()
            laser, cm, zona, cubs = leer_escena(img, mesa, cfg)
            mascara = None
            if a.ajustar:
                b, g, r = (img[..., i].astype(np.int16) for i in range(3))
                sc = (g - np.maximum(r, b)) if cfg["laser"]["color"] == "verde" else (r - np.maximum(g, b))
                mascara = np.clip(sc * 2, 0, 255).astype(np.uint8)
            if laser:
                estado = f"Láser en ({cm[0]:.1f}, {cm[1]:.1f}) cm → " + (f"zona {zona}" if zona else "fuera de zona")
            else:
                estado = "No veo el láser"
            estado += f"   ·   cubiletes: {len(cubs)}"
            vista.dibujar(img, laser, cubs, estado, destino=zona, mascara=mascara)
            n += 1
            if a.imagen:
                vista.plt.ioff(); vista.plt.show()
                break
    finally:
        cam.soltar()
    if n > 1:
        print(f"{n / (time.time() - t0):.1f} imágenes por segundo")


if __name__ == "__main__":
    main()
