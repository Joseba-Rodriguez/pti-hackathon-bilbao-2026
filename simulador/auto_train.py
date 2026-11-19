"""lerobot-train con un arreglo para Windows.

En Windows, crear el enlace ``checkpoints/last`` (symlink) exige el "Modo de
desarrollador"; sin el, el entrenamiento se cae al guardar el primer checkpoint.
Aqui, si el symlink falla, se guarda el nombre del ultimo checkpoint en
``checkpoints/last.txt`` y el entrenamiento sigue. Todos los parametros son los
de ``lerobot-train``.
"""

from __future__ import annotations

import logging
import sys

import lerobot.common.train_utils as tu

_original = tu.update_last_checkpoint


def _safe_update_last_checkpoint(checkpoint_dir):
    try:
        return _original(checkpoint_dir)
    except OSError as e:
        last_txt = checkpoint_dir.parent / "last.txt"
        last_txt.write_text(checkpoint_dir.name, encoding="utf-8")
        logging.warning("symlink no permitido (%s); ultimo checkpoint anotado en %s", e, last_txt)


tu.update_last_checkpoint = _safe_update_last_checkpoint

if __name__ == "__main__":
    import lerobot.scripts.lerobot_train as lt

    if hasattr(lt, "update_last_checkpoint"):
        lt.update_last_checkpoint = _safe_update_last_checkpoint
    sys.exit(lt.main())
