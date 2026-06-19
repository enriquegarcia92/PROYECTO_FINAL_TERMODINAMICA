"""Rutas compatibles con desarrollo y ejecutables PyInstaller."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_path(relative: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", project_root()))
    return bundle_root / relative


def results_dir() -> Path:
    if getattr(sys, "frozen", False):
        target = Path.home() / "Documents" / "VLE Gamma-Phi" / "resultados"
    else:
        target = project_root() / "resultados"
    target.mkdir(parents=True, exist_ok=True)
    return target
