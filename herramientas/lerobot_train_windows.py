"""lerobot-train para Windows sin "Modo de desarrollador".

Al guardar cada checkpoint, lerobot-train crea el enlace ``checkpoints/last``
(symlink). En Windows eso exige el Modo de desarrollador; sin el, el
entrenamiento SE CAE al guardar el primer checkpoint (WinError 1314).
Aqui, si el symlink falla, se crea una "union de directorio" (junction), que
Windows permite sin permisos especiales. ``checkpoints/last/...`` funciona igual,
tambien para --resume.

Uso: exactamente los mismos argumentos que lerobot-train:
    python herramientas\\lerobot_train_windows.py --dataset.repo_id=... --policy.type=act ...
(Si se activa el Modo de desarrollador de Windows, vale el lerobot-train normal.)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import lerobot.common.train_utils as tu

_original = tu.update_last_checkpoint


def _update_last_checkpoint(checkpoint_dir: Path) -> None:
    try:
        return _original(checkpoint_dir)
    except OSError as e:
        import _winapi

        last = Path(checkpoint_dir).parent / "last"
        if os.path.lexists(last):
            if os.path.isjunction(last) or last.is_symlink():
                os.rmdir(last) if os.path.isjunction(last) else last.unlink()
            else:
                raise
        _winapi.CreateJunction(str(Path(checkpoint_dir).resolve()), str(last))
        logging.info("checkpoints/last -> %s (union de directorio; symlink no permitido: %s)",
                     Path(checkpoint_dir).name, e.__class__.__name__)


tu.update_last_checkpoint = _update_last_checkpoint

if __name__ == "__main__":
    import lerobot.scripts.lerobot_train as lt

    lt.update_last_checkpoint = _update_last_checkpoint
    sys.exit(lt.main())
