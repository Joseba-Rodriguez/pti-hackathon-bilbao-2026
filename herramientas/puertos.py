"""Detecta que puerto COM es el leader y cual el follower, leyendo la tension de los servos.

Solo lee (ping + Present_Voltage). No activa par ni mueve nada.
Leader SO-101: fuente de 5 V. Follower: fuente de 12 V.
Uso:  python herramientas\\puertos.py          -> imprime una linea por brazo
      python herramientas\\puertos.py leader   -> imprime solo el COM del leader (para scripts)
"""

import sys

import scservo_sdk as scs
import serial.tools.list_ports as lp


def tension(port: str) -> float | None:
    ph = scs.PortHandler(port)
    pk = scs.PacketHandler(0)
    try:
        if not (ph.openPort() and ph.setBaudRate(1_000_000)):
            return None
        _, res, _ = pk.ping(ph, 1)
        if res != scs.COMM_SUCCESS:
            return None
        volt, res, _ = pk.read1ByteTxRx(ph, 1, 62)  # Present_Voltage, en decimas de voltio
        return volt / 10 if res == scs.COMM_SUCCESS else None
    except Exception:
        return None
    finally:
        ph.closePort()


brazos = {}
for p in lp.comports():
    if "bluetooth" in (p.description or "").lower():
        continue
    v = tension(p.device)
    if v is not None:
        brazos["leader" if v < 9 else "follower"] = (p.device, v)

if len(sys.argv) > 1:
    print(brazos.get(sys.argv[1], ("NO_DETECTADO",))[0])
else:
    for rol in ("leader", "follower"):
        if rol in brazos:
            print(f"{rol}: {brazos[rol][0]} ({brazos[rol][1]:.1f} V)")
        else:
            print(f"{rol}: NO DETECTADO (revisa fuente, cable y puerto USB)")
