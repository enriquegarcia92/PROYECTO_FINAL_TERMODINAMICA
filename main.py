"""Punto de entrada gráfico."""

import os
from pathlib import Path
import sys


def _activate_project_environment() -> None:
    """Reinicia con el Python local cuando se invoca mediante `python3 main.py`."""
    root = Path(__file__).resolve().parent
    candidates = (
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.exists() and Path(sys.executable).absolute() != candidate.absolute():
            os.execv(str(candidate), [str(candidate), str(Path(__file__).resolve()), *sys.argv[1:]])


_activate_project_environment()

try:
    from PySide6.QtCore import QTimer
except ModuleNotFoundError as exc:
    raise SystemExit(
        "No se encontró PySide6. Cree el entorno con `python3 -m venv .venv` "
        "e instale `./.venv/bin/python -m pip install -r requirements.txt`."
    ) from exc

from vle_poc.ui import MainWindow, create_application


def main() -> int:
    app = create_application()
    window = MainWindow()
    window.show()
    if delay := os.environ.get("VLE_POC_AUTOCLOSE_MS"):
        QTimer.singleShot(int(delay), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
