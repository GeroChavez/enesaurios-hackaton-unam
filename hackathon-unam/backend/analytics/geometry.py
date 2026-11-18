"""Distancias, cinemática aproximada y cambios de dirección (yardas, segundos)."""
from __future__ import annotations

import numpy as np

from .tracks import Tracks


def nanmean(a: np.ndarray, axis=None):
    a = np.asarray(a, float)
    c = np.isfinite(a).sum(axis=axis)
    s = np.nansum(a, axis=axis)
    return np.where(c > 0, s / np.maximum(c, 1), np.nan)


def dist_to(tr: Tracks, i: int, js: list[int]) -> np.ndarray:
    """Distancia euclidiana (F, len(js)) entre el jugador i y los jugadores js."""
    return np.hypot(tr.X[:, [i]] - tr.X[:, js], tr.Y[:, [i]] - tr.Y[:, js])


def pair_distance(tr: Tracks, i: int, j: int) -> np.ndarray:
    return np.hypot(tr.X[:, i] - tr.X[:, j], tr.Y[:, i] - tr.Y[:, j])


def velocity(tr: Tracks, i: int) -> tuple[np.ndarray, np.ndarray]:
    if len(tr.t) < 2:
        return np.full(len(tr.t), np.nan), np.full(len(tr.t), np.nan)
    return np.gradient(tr.X[:, i], tr.t), np.gradient(tr.Y[:, i], tr.t)


def kinematics(tr: Tracks, i: int, s: int, e: int) -> dict:
    """Resumen cinemático del jugador i en la ventana [s, e] (índices de frame)."""
    x, y = tr.X[s:e + 1, i], tr.Y[s:e + 1, i]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return {"frames_validos": int(ok.sum())}
    vx, vy = velocity(tr, i)
    vx, vy = vx[s:e + 1], vy[s:e + 1]
    speed = np.hypot(vx, vy)
    ax = np.gradient(speed, tr.t[s:e + 1]) if len(speed) > 1 else np.full_like(speed, np.nan)
    xs, ys = x[ok], y[ok]
    step = np.hypot(np.diff(xs), np.diff(ys))
    ang = np.degrees(np.arctan2(vy, vx))
    moving = np.isfinite(ang) & (speed > 1.0)
    turns = 0.0
    if moving.sum() >= 2:
        d = np.diff(ang[moving])
        d = (d + 180.0) % 360.0 - 180.0
        turns = float(np.abs(d).sum())
    return {
        "frames_validos": int(ok.sum()),
        "recorrido_yd": float(step.sum()),
        "desplazamiento_neto_yd": float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0])),
        "velocidad_media_yds": float(np.nanmean(speed)),
        "velocidad_max_yds": float(np.nanmax(speed)),
        "aceleracion_max_yds2": float(np.nanmax(np.abs(ax))) if np.isfinite(ax).any() else None,
        "cambio_direccion_total_grados": turns,
    }
