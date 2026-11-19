"""Video de la simulacion de Esperanza (1280x720 o 1920x1080, fluido, con rotulos).

La simulacion se avanza fotograma a fotograma (sin hilos), asi cada fotograma se
renderiza con calma. Una toma completa con el operador automatico:
aviso -> entrega -> camara (toma y llena) -> Esperanza -> camara (vacio) -> recogida -> familia.

    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_video.py --salida ..\\esperanza_simulacion.mp4
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_video.py --hd --salida ..\\esperanza_simulacion_1080p.mp4
"""

from __future__ import annotations

import argparse
import time

import av
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import auto_expert as ax
import esperanza_expert as ee
import esperanza_scene as es

FPS = 30
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
FONT_R = "C:/Windows/Fonts/segoeui.ttf"
PASOS = ["Aviso", "Entrega", "Cámara", "Se la toma", "Cámara", "Recogida", "Familia"]
VERDE = (24, 128, 96)
TOMA_RGB = {k: tuple(int(c * 255) for c in t.rgba[:3]) for k, t in es.TOMAS.items()}
NOMBRE = {"manana": "mañana", "mediodia": "mediodía", "noche": "noche"}


class OfflineSim:
    def __init__(self, cups):
        es.EsperanzaRobot.cups = cups
        self.r = es.EsperanzaRobot(es.EsperanzaRobotConfig(onscreen=False, image_camera=None, top_camera=None,
                                                         settle_s=2.0))
        self.r.connect()
        self.r._stop.set()
        self.r._thread.join()
        self.r._stop_watch.set()
        time.sleep(0.05)
        m, d = self.r.model, self.r.data
        self.m, self.d = m, d
        self.substeps = max(1, round((1 / FPS) / m.opt.timestep))
        self.logic_every = max(1, round(0.01 / m.opt.timestep))
        floor = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        if floor >= 0:
            m.geom_matid[floor] = -1
            m.geom_rgba[floor] = [0.93, 0.91, 0.87, 1]
        self.target = d.qpos.copy()
        self.act = {f"{n}.pos": v for n, v in ax.HOME.items()}

    def step(self, action=None):
        r, d = self.r, self.d
        if action is not None:
            self.act = action
        for name, value in self.act.items():
            name = name.removesuffix(".pos")
            lo, hi = (0.0, 100.0) if name == "gripper" else (-100.0, 100.0)
            self.target[r._qposadr[name]] = r._to_rad(name, min(max(value, lo), hi))
        for i in range(self.substeps):
            d.ctrl[:] = self.target[r._ctrl_joint]
            mujoco.mj_step(self.m, d)
            if i % self.logic_every == 0:
                r._check_grasp()
                if r._reset_objects_requested:
                    r._reset_objects_requested = False
                    r._perform_scene_reset()


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Cam:
    """Camara libre que persigue suavemente el plano de cada fase."""

    SHOTS = {
        # vistos desde el lado de Esperanza (-y), con el robot a la izquierda
        "general": ((0.18, -0.05, 0.06), 0.78, 75, -28),
        "bolsillo": ((0.17, -0.02, 0.05), 0.44, 62, -26),
        "marca": ((0.18, -0.08, 0.04), 0.46, 70, -32),
        "caja": ((0.15, -0.14, 0.04), 0.52, 80, -36),
        "final": ((0.18, -0.06, 0.06), 0.74, 95, -26),
    }

    def __init__(self):
        self.cam = mujoco.MjvCamera()
        self.p = np.array([*self.SHOTS["general"][0], *self.SHOTS["general"][1:]], float)
        self.goal = self.p.copy()

    def set(self, name):
        look, dist, az, el = self.SHOTS[name]
        self.goal = np.array([*look, dist, az, el], float)

    def update(self):
        self.p += (self.goal - self.p) * 0.035
        self.cam.lookat[:] = self.p[:3]
        self.cam.distance, self.cam.azimuth, self.cam.elevation = self.p[3], self.p[4], self.p[5]


class Video:
    def __init__(self, path, W, H):
        self.W, self.H = W, H
        s = H / 720
        self.F = {k: ImageFont.truetype(FONT_B if b else FONT_R, int(v * s)) for k, (b, v) in {
            "huge": (True, 58), "title": (True, 30), "sub": (False, 20), "chip": (True, 15), "small": (False, 15),
            "msg": (False, 17)}.items()}
        self.s = s
        self.out = av.open(path, "w")
        self.st = self.out.add_stream("h264", rate=FPS)
        self.st.width, self.st.height, self.st.pix_fmt = W, H, "yuv420p"
        self.st.options = {"crf": "17", "preset": "slow"}

    def write(self, img: Image.Image):
        for p in self.st.encode(av.VideoFrame.from_image(img.convert("RGB"))):
            self.out.mux(p)

    def close(self):
        for p in self.st.encode():
            self.out.mux(p)
        self.out.close()


def draw_overlay(v: Video, img: Image.Image, st: dict, inset: np.ndarray | None) -> Image.Image:
    s, W, H, F = v.s, v.W, v.H, v.F
    o = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(o)
    # pasos arriba
    x, y = int(24 * s), int(22 * s)
    for k, name in enumerate(PASOS):
        done, act = k < st["paso"], k == st["paso"]
        txt = f"{k + 1} · {name}"
        w = dr.textlength(txt, font=F["chip"]) + 22 * s
        fill = (*VERDE, 235) if done or act else (255, 255, 255, 190)
        dr.rounded_rectangle([x, y, x + w, y + 30 * s], int(15 * s), fill=fill,
                             outline=(*VERDE, 255) if act else None, width=int(2 * s))
        dr.text((x + 11 * s, y + 5 * s), txt, font=F["chip"], fill=(255, 255, 255) if done or act else (90, 90, 90))
        x += w + 8 * s
    # rotulo abajo
    if st.get("titulo"):
        tw = max(dr.textlength(st["titulo"], font=F["title"]), dr.textlength(st.get("sub", ""), font=F["sub"]))
        bx, by = int(24 * s), int(H - 112 * s)
        dr.rounded_rectangle([bx, by, bx + tw + 40 * s, by + 88 * s], int(14 * s), fill=(255, 255, 255, 225))
        dr.text((bx + 20 * s, by + 12 * s), st["titulo"], font=F["title"], fill=(30, 35, 40))
        dr.text((bx + 20 * s, by + 52 * s), st.get("sub", ""), font=F["sub"], fill=(90, 95, 100))
    # camara del puesto
    if inset is not None:
        ih, iw = inset.shape[:2]
        ix, iy = int(W - iw - 24 * s), int(70 * s)
        dr.rounded_rectangle([ix - 6 * s, iy - 30 * s, ix + iw + 6 * s, iy + ih + 44 * s], int(10 * s),
                             fill=(255, 255, 255, 230))
        dr.text((ix, iy - 26 * s), "Cámara del puesto", font=F["chip"], fill=(60, 60, 60))
        if st.get("vision"):
            ok = st.get("vision_ok", True)
            dr.text((ix, iy + ih + 10 * s), st["vision"], font=F["chip"], fill=VERDE if ok else (200, 50, 40))
    # movil de la familia
    if st.get("movil"):
        mw, mh = int(300 * s), int(118 * s)
        mx, my = int(W - mw - 24 * s), int(H - mh - 24 * s)
        dr.rounded_rectangle([mx, my, mx + mw, my + mh], int(18 * s), fill=(30, 33, 38, 240))
        dr.ellipse([mx + 16 * s, my + 16 * s, mx + 34 * s, my + 34 * s], fill=VERDE)
        dr.text((mx + 44 * s, my + 13 * s), "Familia · ahora", font=F["chip"], fill=(220, 220, 220))
        yy = my + 44 * s
        for line in st["movil"].split("\n"):
            dr.text((mx + 18 * s, yy), line, font=F["msg"], fill=(255, 255, 255))
            yy += 24 * s
    if st.get("bocadillo"):
        t = st["bocadillo"]
        tw = dr.textlength(t, font=F["title"])
        bx, by = int((W - tw) / 2 - 24 * s), int(80 * s)
        dr.rounded_rectangle([bx, by, bx + tw + 48 * s, by + 56 * s], int(28 * s), fill=(230, 246, 240, 240))
        dr.text((bx + 24 * s, by + 10 * s), t, font=F["title"], fill=(20, 90, 70))
    if st.get("tarjeta"):
        dr.rectangle([0, 0, W, H], fill=(247, 243, 236, int(255 * st.get("tarjeta_a", 1.0))))
        a = int(255 * st.get("tarjeta_a", 1.0))
        for j, (txt, f, col) in enumerate(st["tarjeta"]):
            tw = dr.textlength(txt, font=F[f])
            dr.text(((W - tw) / 2, H * 0.30 + j * 64 * s), txt, font=F[f], fill=(*col, a))
    img = Image.alpha_composite(img.convert("RGBA"), o)
    if inset is not None:
        ih, iw = inset.shape[:2]
        img.paste(Image.fromarray(inset), (int(W - iw - 24 * s), int(70 * s)))
    return img


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", default="esperanza_simulacion.mp4")
    p.add_argument("--hd", action="store_true", help="1920x1080 (si no, 1280x720)")
    p.add_argument("--prueba", default=None, help="carpeta: guarda solo algunos fotogramas PNG")
    args = p.parse_args()
    W, H = (1920, 1080) if args.hd else (1280, 720)

    sim = OfflineSim([es.Vasito("noche"), es.Vasito("manana"), es.Vasito("mediodia"), es.Vasito("noche"),
                      es.Vasito("mediodia", "caja", False, (0.01, -0.01), 0.3)])
    m, d, r = sim.m, sim.d, sim.r
    m.vis.global_.offwidth, m.vis.global_.offheight = W, H
    m.vis.quality.offsamples = 8
    ren = mujoco.Renderer(m, H, W)
    iw, ih = int(300 * H / 720), int(225 * H / 720)
    ren_in = mujoco.Renderer(m, ih, iw)
    ren_eye = mujoco.Renderer(m, 480, 640)
    cam = Cam()
    vid = None if args.prueba else Video(args.salida, W, H)
    st = {"paso": -1}
    n = [0]

    def frame(action=None, inset=False):
        sim.step(action)
        cam.update()
        n[0] += 1
        if args.prueba and n[0] % 45:
            return
        ren.update_scene(d, camera=cam.cam)
        img = Image.fromarray(ren.render())
        ins = None
        if inset:
            ren_in.update_scene(d, camera="top_cam")
            ins = ren_in.render().copy()
        out = draw_overlay(vid or Video.__new__(Video), img, st, ins) if vid else None
        if vid:
            vid.write(out)
        else:
            fake = Video.__new__(Video)
            fake.W, fake.H, fake.s = W, H, H / 720
            fake.F = {k: ImageFont.truetype(FONT_B if b else FONT_R, int(v * fake.s)) for k, (b, v) in {
                "huge": (True, 58), "title": (True, 30), "sub": (False, 20), "chip": (True, 15),
                "small": (False, 15), "msg": (False, 17)}.items()}
            draw_overlay(fake, img, st, ins).convert("RGB").save(f"{args.prueba}/f_{n[0]:04d}.png")

    def hold(sec, inset=False):
        for _ in range(int(sec * FPS)):
            frame(inset=inset)

    def mirar():
        ren_eye.update_scene(d, camera="top_cam")
        return es.mirar_marca(m, d, ren_eye.render())

    def run(traj, inset=False, hooks=None):
        for k in range(int((traj.duration + 0.3) * FPS)):
            t = k / FPS
            if hooks:
                for tt, fn in list(hooks):
                    if t >= tt:
                        fn()
                        hooks.remove((tt, fn))
            frame({f"{nn}.pos": v for nn, v in traj(t).items()}, inset)
        return traj.final

    expert = ee.EsperanzaExpert(seed=3)
    # --- portada
    st.update(tarjeta=[("Esperanza", "huge", (30, 35, 40)),
                       ("Un cargador de tomas y dos movimientos aprendidos", "sub", (90, 95, 100)),
                       ("Simulación del SO-101 · MuJoCo + LeRobot", "small", (120, 120, 120))], tarjeta_a=1.0)
    for k in range(int(2.6 * FPS)):
        st["tarjeta_a"] = 1.0 if k < 1.6 * FPS else 1.0 - (k - 1.6 * FPS) / FPS
        frame()
    st.pop("tarjeta")
    st.update(titulo="La familia carga los vasitos de la semana", sub="Ya rellenados, en orden. La rampa los baja de uno en uno.")
    hold(3.2)

    # --- 1 aviso
    st.update(paso=0, bocadillo="«Esperanza, tu toma de la noche»", titulo="21:00 · aviso por voz",
              sub="El portátil avisa con su altavoz")
    hold(2.6)
    st.pop("bocadillo")

    # --- 2 entrega
    i = ee.front_cup(r)
    st.update(paso=1, titulo="Habilidad 1 · entregar", sub="Coge el primer vasito del bolsillo y lo deja en la marca verde")
    cam.set("bolsillo")
    traj = ax.Trajectory(dict(ax.HOME), expert.plan("entregar", *ee.cup_frame(r, i)))
    last = run(traj, hooks=[(4.6, lambda: cam.set("marca")),
                            (5.0, lambda: st.update(sub="Al sacarlo, el siguiente baja solo por gravedad"))])

    # --- 3 camara
    v1 = mirar()
    st.update(paso=2, titulo="La cámara comprueba la toma", sub="Color del vasito = noche · dentro hay pastillas",
              vision=f"Toma de la {NOMBRE.get(v1['toma'], '?')} (la que toca)  ·  {'llena' if v1['llena'] else 'vacía'}",
              vision_ok=v1["toma"] == "noche" and bool(v1["llena"]))
    hold(3.0, inset=True)

    # --- 4 Esperanza
    st.update(paso=3, titulo="Esperanza se la toma", sub="Coge el vasito y lo devuelve vacío a la marca", vision=None)
    r.park_cup(i)
    hold(1.6, inset=True)
    r.take_dose(i)
    r.place_cup(i, es.SPOT + np.array([0.006, -0.004]), 0.8)
    hold(1.2, inset=True)

    # --- 5 camara
    v2 = mirar()
    st.update(paso=4, titulo="La cámara comprueba que está vacío", sub="Sin pastillas dentro: toma hecha",
              vision=f"Toma de la {NOMBRE.get(v2['toma'], '?')}  ·  {'vacío: tomada' if v2['llena'] is False else 'con pastillas'}",
              vision_ok=v2["llena"] is False)
    hold(2.8, inset=True)

    # --- 6 recogida
    st.update(paso=5, titulo="Habilidad 2 · recoger", sub="Echa el vasito vacío a la caja de usados", vision=None)
    cam.set("caja")
    j = r.cup_on_spot()
    traj = ax.Trajectory(last, expert.plan("recoger", *ee.cup_frame(r, j)))
    run(traj, hooks=[(7.5, lambda: cam.set("final"))])

    # --- 7 familia
    st.update(paso=6, titulo="Mensaje a la familia", sub="Si no se la toma en un rato, llega una alerta",
              movil="Esperanza se ha tomado\nla toma de la noche · 21:04")
    hold(3.6)
    st.update(paso=7, bocadillo="«Buenas noches, Esperanza»")
    hold(2.0)
    st.pop("bocadillo")

    # --- cierre
    st.update(titulo=None, movil=None)
    lines = [("2 habilidades · ~50 demostraciones cada una", "title", (30, 35, 40)),
             ("0 electrónica añadida: una rampa impresa en 3D", "title", (24, 128, 96)),
             ("Simulación: movimientos del operador que graba las demostraciones · agarre asistido", "small", (120, 120, 120)),
             ("Concepto, no es un dispositivo médico", "small", (120, 120, 120))]
    for k in range(int(4.0 * FPS)):
        st.update(tarjeta=lines, tarjeta_a=min(1.0, k / FPS))
        frame()
    if vid:
        vid.close()
    print(f"hecho: {n[0]} fotogramas ({n[0] / FPS:.1f} s) -> {args.salida if vid else args.prueba}")
    print(f"camara: entrega {v1} | devuelto {v2} | vasito en la caja: {r.cup_in_box(i)}")


if __name__ == "__main__":
    main()
