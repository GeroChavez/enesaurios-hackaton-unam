"""Rutas y constantes globales. Todo es relativo a la raíz del proyecto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dashboard" / "dist"

# Dimensiones del campo NFL (yardas): 120 de largo con zonas de anotación, 53.3 de ancho.
FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3
