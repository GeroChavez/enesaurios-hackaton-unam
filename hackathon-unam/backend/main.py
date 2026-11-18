"""DECOY IQ: API FastAPI. Ejecuta: .venv/bin/uvicorn backend.main:app --reload"""
import os
from pathlib import Path


def cargar_env():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .core.config import DIST_DIR  # noqa: E402
from .routers.api import router  # noqa: E402

app = FastAPI(title="DECOY IQ", description="Valor táctico indirecto de receptores (NFL tracking)")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(router)

# Sirve el build del dashboard (si existe) en la misma URL. Debe montarse al final.
if DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="dashboard")
