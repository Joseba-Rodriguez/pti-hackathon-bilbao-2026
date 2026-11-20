"""El robot lleva el cubilete a donde apunta el laser.

Bucle:
  1. La camara busca el punto del laser en el mapa virtual.
  2. Si se queda quieto ~1 s dentro de una zona (A, B...), esa es el destino.
  3. Se comprueba que el cubilete esta en INICIO.
  4. Pregunta si hay una persona mirando con la mano en la alimentacion.
  5. Lanza lerobot-rollout con la politica de esa zona (la camara se suelta mientras).
  6. Mira si el cubilete ha llegado a la zona y lo apunta en resultados/intentos.csv
     (la tabla de aciertos y fallos para el jurado).

    python app/orquestador.py --simulacro     (no mueve el robot: imprime el comando)
    python app/orquestador.py                 (de verdad)
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import time
from datetime import datetime

import numpy as np

import vision
from mapa import Vista, leer_escena

RESULTADOS = vision.AQUI.parent / "resultados" / "intentos.csv"


def comando_rollout(cfg: dict, zona: str) -> list[str]:
    pol, rob = cfg["politicas"][zona], cfg["robot"]
    return ["lerobot-rollout", "--strategy.type=base", f"--policy.path={pol['repo']}",
            f"--robot.type={rob['tipo']}", f"--robot.port={rob['puerto']}", f"--robot.id={rob['id']}",
            f"--robot.cameras={rob['camaras']}", f"--task={pol['tarea']}", f"--duration={pol['duracion_s']}"]


def apuntar(zona, ok, detalle):
    RESULTADOS.parent.mkdir(exist_ok=True)
    nuevo = not RESULTADOS.exists()
    with RESULTADOS.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "destino", "acierto", "detalle"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), zona, int(ok), detalle])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--simulacro", action="store_true", help="no mueve el robot")
    p.add_argument("--imagen", default=None, help="probar con una foto fija")
    a = p.parse_args()
    cfg = vision.cargar_config()
    mesa = vision.Mesa(cfg, vision.cargar_calibracion())
    zonas_robot = [k for k in cfg["politicas"] if not k.startswith("_")]
    cam = vision.Camara(cfg, a.imagen)
    vista = Vista(mesa, "Laser → robot · equipo PTI")
    seguidor = vision.SeguidorLaser(cfg["laser"]["segundos_quieto"])
    print("Apunta con el laser a una zona (" + ", ".join(zonas_robot) + "). Cierra la ventana o pulsa q para salir.")
    try:
        while not vista.salir:
            img = cam.foto()
            laser, cm, zona, cubs = leer_escena(img, mesa, cfg)
            # si INICIO esta fuera de la cartulina (tapa blanca sobre mesa blanca) la camara no puede
            # verlo: se confia en que el cubilete este alli
            comprobar = cfg.get("comprobar_inicio", True)
            en_inicio = (not comprobar) or any(mesa.zona_de(c, incluir_inicio=True) == "INICIO" for c in cubs)
            destino = seguidor.actualizar(zona if zona in zonas_robot else None)
            estado = (f"Láser → zona {zona}" if zona else ("Láser fuera de zona" if laser else "Esperando el láser…"))
            if comprobar:
                estado += "   ·   cubilete en INICIO" if en_inicio else "   ·   NO hay cubilete en INICIO"
            vista.dibujar(img, laser, cubs, estado, destino=zona)
            if not destino:
                if a.imagen:
                    time.sleep(0.1)
                continue

            if not en_inicio:
                print(f"Destino {destino}, pero no veo el cubilete en INICIO: colócalo y vuelve a apuntar.")
                seguidor = vision.SeguidorLaser(cfg["laser"]["segundos_quieto"])
                continue
            cmd = comando_rollout(cfg, destino)
            print(f"\n=== Destino: zona {destino}")
            print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
            vista.dibujar(img, laser, cubs, f"Destino: zona {destino}. El robot va a moverse…", destino=destino)
            if a.simulacro:
                print("(simulacro: el robot no se mueve)")
                apuntar(destino, False, "simulacro")
                break
            # el robot no vio el laser al grabar: apagarlo para que la escena sea la misma
            if input("Apaga el láser. ¿Hay una persona mirando el brazo con la mano en la alimentación? (s/n) "
                     ).strip().lower() != "s":
                print("cancelado")
                seguidor = vision.SeguidorLaser(cfg["laser"]["segundos_quieto"])
                continue
            cam.soltar()                                  # lerobot necesita la misma camara
            rc = subprocess.run(cmd).returncode
            time.sleep(1.0)
            img = cam.foto()
            _, _, _, cubs = leer_escena(img, mesa, cfg)
            # la tapa sale desplazada por paralaje: se acepta con mas margen que el laser
            llego = any(mesa.zona_de(c, margen=cfg["cubilete"].get("margen_zona", 1.6)) == destino for c in cubs)
            detalle = "ok" if llego else ("lerobot-rollout fallo" if rc else "el cubilete no esta en la zona")
            apuntar(destino, llego, detalle)
            print(f"Resultado: {'ACIERTO' if llego else 'FALLO'} ({detalle}). Apuntado en {RESULTADOS}")
            vista.dibujar(img, None, cubs, f"Zona {destino}: {'ACIERTO ✔' if llego else 'FALLO ✘'} · "
                          "vuelve a dejar el cubilete en INICIO", destino=destino)
            seguidor = vision.SeguidorLaser(cfg["laser"]["segundos_quieto"])
            time.sleep(2.0)
    finally:
        cam.soltar()


if __name__ == "__main__":
    main()
