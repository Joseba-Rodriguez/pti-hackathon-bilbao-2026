"""Genera los audios del NARRADOR de la web (voz neuronal de Microsoft, español de España).

Los MP3 se guardan en herramientas/web/voz/ y la web los reproduce SIN internet.
Solo hace falta internet para generarlos (una vez). Si cambias o añades una frase, vuelve a ejecutar:

    pip install edge-tts            (en cualquier Python, no hace falta el venv de lerobot)
    python herramientas\\generar_voz.py

La web lee voz/frases.json: si una frase no tiene MP3, la dice con la voz del navegador.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

VOZ = "es-ES-AlvaroNeural"          # narrador masculino, castellano
RITMO, TONO = "-6%", "-3Hz"          # un poco más pausado y grave: tono documental

FRASES = {
    "arranque": "Sistema PTI en línea. Celda caliente tres, sellada y en depresión. Bienvenido, operador.",
    "enlace": "Enlace con el brazo establecido. Telemetría en directo.",
    "enlace_perdido": "Atención: se ha perdido la telemetría del brazo.",
    "fase0": "El operador marca el destino con el láser, desde fuera de la celda.",
    "fase1": "Extrayendo el contenedor de uranio del almacén blindado. La radiación en la celda aumenta.",
    "fase2": "Contenedor en tránsito. El brazo sigue el punto del láser.",
    "fase3": "Contenedor depositado. Ninguna persona ha entrado en la celda.",
    "resumen": "Operación completada. Dosis recibida por el operador: cero.",
    "iniciar": "Iniciando secuencia de traslado. Mantenga la mano cerca de la alimentación del brazo.",
    "parar": "Parada solicitada. El brazo se detiene.",
    "reposo": "Brazo en reposo. Celda sellada. Esperando orden del operador.",
    "intro": ("En las celdas calientes, el material radiactivo se manipula detrás de un metro de blindaje. "
              "Hoy, el operador solo tiene que apuntar con un láser. El robot, entrenado con demostraciones humanas, hace el resto."),
}


async def main():
    import edge_tts
    out = Path(__file__).resolve().parent / "web" / "voz"
    out.mkdir(parents=True, exist_ok=True)
    for clave, texto in FRASES.items():
        await edge_tts.Communicate(texto, VOZ, rate=RITMO, pitch=TONO).save(str(out / f"{clave}.mp3"))
        print("ok", clave)
    (out / "frases.json").write_text(json.dumps({"voz": VOZ, "frases": FRASES}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
