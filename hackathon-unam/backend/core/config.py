"""Rutas y constantes globales. Todo es relativo a la raíz del proyecto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _find_data_dir() -> Path:
    """data/ en la raíz del proyecto; si no existe, data/ en la raíz del repositorio (donde se subió el dataset)."""
    for c in (ROOT / "data", ROOT.parent / "data"):
        if c.is_dir() and next(c.rglob("*.csv"), None) is not None:
            return c
    return ROOT / "data"


DATA_DIR = _find_data_dir()
DIST_DIR = ROOT / "dashboard" / "dist"

# Dimensiones del campo NFL (yardas): 120 de largo con zonas de anotación, 53.3 de ancho.
FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3
