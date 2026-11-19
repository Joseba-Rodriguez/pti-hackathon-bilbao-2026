"""Orquestador de Esperanza: una o varias tomas completas, de principio a fin.

  1. aviso      "Esperanza, tu toma de la noche" (voz si hay pyttsx3; si no, texto)
  2. entregar   habilidad 1 (politica ACT o el operador automatico)
  3. camara     el vasito de la marca es la toma que toca y esta lleno
  4. Esperanza  se la toma y devuelve el vasito (en la simulacion lo hace este script)
  5. camara     el vasito ha vuelto vacio
  6. recoger    habilidad 2
  7. familia    mensaje "tomada a las 21:04" (Telegram si hay TELEGRAM_TOKEN y TELEGRAM_CHAT;
                si no, se imprime). Si no se la toma a tiempo: alerta.

    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_orquestador.py
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_orquestador.py --modo politica --tomas 3
    .venv\\Scripts\\python.exe examples\\so101_mujoco\\esperanza_orquestador.py --olvido   (simula que no se la toma)

La pauta es el orden en que la familia carga los vasitos en la rampa (p. ej. la
semana: manana, mediodia, noche, manana...). El orquestador solo comprueba, por
el color, que el vasito que sale es el de la hora que toca.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import numpy as np

import auto_expert as ax
import esperanza_expert as ee
import esperanza_scene as es

PAUTA = [("08:00", "manana"), ("14:00", "mediodia"), ("21:00", "noche")]
NOMBRE = {"manana": "de la mañana", "mediodia": "del mediodía", "noche": "de la noche"}


def decir(texto: str) -> None:
    print(f"  [VOZ]     {texto}", flush=True)
    try:
        import pyttsx3  # opcional
        eng = pyttsx3.init()
        eng.say(texto)
        eng.runAndWait()
    except Exception:
        pass


def avisar_familia(texto: str) -> None:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if token and chat:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10)
            print(f"  [FAMILIA] (Telegram) {texto}", flush=True)
            return
        except Exception as e:
            print(f"  [FAMILIA] Telegram fallo ({e}); mensaje: {texto}", flush=True)
            return
    print(f"  [FAMILIA] {texto}", flush=True)


class Habilidades:
    def __init__(self, modo: str):
        self.modo = modo
        self.expert = ee.EsperanzaExpert(seed=int(time.time()) % 1000)
        self.pol = {}
        self.last = dict(ax.HOME)

    def run(self, robot, skill: str) -> None:
        if self.modo == "politica":
            if skill not in self.pol:
                from esperanza_politica import PolicySkill
                self.pol[skill] = PolicySkill(skill)
            self.last = self.pol[skill].run(robot)
            return
        i = ee.front_cup(robot) if skill == "entregar" else robot.cup_on_spot()
        if i is None:
            raise RuntimeError(f"{skill}: no veo el vasito")
        traj = ax.Trajectory(self.last, self.expert.plan(skill, *ee.cup_frame(robot, i)))
        for k in range(int((traj.duration + 0.4) * 30)):
            robot.send_action({f"{n}.pos": v for n, v in traj(k / 30).items()})
            time.sleep(1 / 30)
        self.last = traj.final


def mirar(robot) -> dict:
    return es.mirar_marca(robot.model, robot.data, robot.render_top())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--modo", choices=["experto", "politica"], default="experto")
    p.add_argument("--tomas", type=int, default=1)
    p.add_argument("--olvido", action="store_true", help="simula que Esperanza no se toma la ultima dosis")
    p.add_argument("--sin-ventana", action="store_true")
    args = p.parse_args()
    rng = np.random.default_rng()

    # la familia ha cargado la rampa con las proximas tomas, en orden
    start = 2  # empezamos por la noche, como en el video
    carga = [PAUTA[(start + k) % 3][1] for k in range(4)]
    es.EsperanzaRobot.cups = [es.Vasito(t) for t in carga]
    robot = es.EsperanzaRobot(es.EsperanzaRobotConfig(onscreen=not args.sin_ventana, settle_s=2.0))
    robot.connect()
    hab = Habilidades(args.modo)
    print("=" * 66)
    print(f"ESPERANZA | modo: {args.modo} | rampa cargada con: {', '.join(carga)}")
    print("=" * 66)
    resumen = []
    for k in range(args.tomas):
        hora, toma = PAUTA[(start + k) % 3]
        print(f"\n--- {hora}  toma {NOMBRE[toma]} ---")
        decir(f"Esperanza, tu toma {NOMBRE[toma]}.")
        hab.run(robot, "entregar")
        time.sleep(0.4)
        i = robot.cup_on_spot()
        vista = mirar(robot)
        print(f"  [CAMARA]  en la marca: {vista}")
        if i is None or vista["toma"] is None:
            avisar_familia(f"Aviso: no he podido entregar la toma {NOMBRE[toma]} ({hora}). Revisad el cargador.")
            resumen.append((hora, toma, "fallo al entregar"))
            break
        if vista["toma"] != toma or not vista["llena"]:
            avisar_familia(f"Aviso: el vasito de las {hora} no es el que toca ({vista}). No lo tome.")
            resumen.append((hora, toma, "vasito equivocado"))
            break

        olvido = args.olvido and k == args.tomas - 1
        if olvido:
            print("  [SIM]     Esperanza no coge el vasito...")
            time.sleep(2.0)
            decir("Esperanza, recuerda tu toma.")
            time.sleep(2.0)
            avisar_familia(f"Alerta: Esperanza no se ha tomado la toma {NOMBRE[toma]} ({hora}).")
            resumen.append((hora, toma, "NO tomada (alerta enviada)"))
            break
        print("  [SIM]     Esperanza coge el vasito, se la toma y lo devuelve a la marca")
        robot.park_cup(i)
        time.sleep(1.0)
        robot.take_dose(i)
        d = rng.uniform(0, 0.012) * np.array([np.cos(a := rng.uniform(0, 2 * np.pi)), np.sin(a)])
        robot.place_cup(i, es.SPOT + d, float(rng.uniform(-np.pi, np.pi)))
        time.sleep(0.8)
        vista = mirar(robot)
        print(f"  [CAMARA]  vasito devuelto: {vista}")
        if vista["llena"]:
            avisar_familia(f"Aviso: el vasito de las {hora} ha vuelto con pastillas.")
            resumen.append((hora, toma, "devuelto lleno"))
            break
        hab.run(robot, "recoger")
        time.sleep(0.5)
        en_caja = robot.cup_in_box(i)
        print(f"  [ROBOT]   vasito a la caja de usados: {en_caja}")
        hecha = (datetime.strptime(hora, "%H:%M") + timedelta(minutes=4)).strftime("%H:%M")
        avisar_familia(f"Esperanza se ha tomado la toma {NOMBRE[toma]} a las {hecha}.")
        if k == args.tomas - 1:
            decir("Buenas noches, Esperanza." if toma == "noche" else "Gracias, Esperanza.")
        resumen.append((hora, toma, "tomada" + ("" if en_caja else " (vasito fuera de la caja)")))

    print("\nRESUMEN DEL DIA")
    for hora, toma, estado in resumen:
        print(f"  {hora}  {toma:9s} {estado}")
    print(json.dumps({"tomas": resumen}, ensure_ascii=False))
    robot.disconnect()


if __name__ == "__main__":
    main()
