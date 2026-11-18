"""Matrices de tracking (frames x jugadores) y detección de eventos."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .events import ARRIVAL_EVENTS, SNAP_EVENTS, THROW_EVENTS

DEFAULT_DT = 0.1
BALL_ID = "ball"


@dataclass
class Tracks:
    frames: np.ndarray            # (F,) identificadores de frame (continuos entre fases)
    ids: list[str]
    X: np.ndarray                 # (F,P) con NaN donde no hay dato
    Y: np.ndarray
    t: np.ndarray                 # (F,) segundos desde el primer frame
    dt: float
    dt_source: str
    start_idx: int                # índice de inicio de ventana (snap si existe)
    throw_idx: Optional[int]
    throw_source: Optional[str]
    arrival_idx: Optional[int]
    ball_land: Optional[tuple[float, float]]
    ball_idx: Optional[int] = None
    start_source: str = "evento de snap"
    ball_land_source: Optional[str] = None

    def col(self, pid: str) -> int:
        return self.ids.index(pid)


def _event_idx(df: pd.DataFrame, frames: np.ndarray, names: set[str]) -> Optional[int]:
    if "event" not in df:
        return None
    ev = df.loc[df["event"].astype(str).str.lower().isin(names), "frame"]
    if ev.empty:
        return None
    return int(np.searchsorted(frames, ev.min()))


def build_tracks(df: pd.DataFrame) -> Tracks:
    df = df.drop_duplicates(["frame", "player"], keep="first")
    frames = np.sort(df["frame"].unique())
    X = df.pivot(index="frame", columns="player", values="x").reindex(frames)
    Y = df.pivot(index="frame", columns="player", values="y").reindex(frames)
    ids = [str(c) for c in X.columns]

    dt, src = DEFAULT_DT, "supuesto: 10 cuadros por segundo (no se pudo estimar)"
    if {"dis", "s"} <= set(df.columns):
        # distancia recorrida por cuadro / velocidad = intervalo entre cuadros
        m = df[(df["s"] > 1.0) & (df["dis"] > 0)]
        if len(m) >= 20:
            est = float((m["dis"] / m["s"]).median())
            if 0.05 <= est <= 0.2:
                dt, src = est, "estimado de dis/s"
    elif "time" in df and df["time"].notna().any() and len(frames) > 1:
        try:
            tt = pd.to_datetime(df["time"], errors="coerce", utc=True).dropna()
            est = (tt.max() - tt.min()).total_seconds() / float(frames[-1] - frames[0])
            if 0.05 <= est <= 0.2:
                dt, src = est, "columna de tiempo (intervalo medio)"
        except Exception:
            pass
    t = (frames - frames[0]) * dt

    snap = _event_idx(df, frames, SNAP_EVENTS)
    throw = _event_idx(df, frames, THROW_EVENTS)
    tsrc = "evento de lanzamiento" if throw is not None else None
    if throw is None and "phase" in df and (df["phase"] == "continuacion").any():
        last_main = df.loc[df["phase"] == "principal", "frame"].max()
        throw = int(np.searchsorted(frames, last_main))
        tsrc = "último cuadro del tracking principal (supuesto: coincide con el lanzamiento)"
    arrival = _event_idx(df, frames, ARRIVAL_EVENTS)

    land = None
    if {"ball_land_x", "ball_land_y"} <= set(df.columns):
        lx, ly = df["ball_land_x"].dropna(), df["ball_land_y"].dropna()
        if len(lx) and len(ly):
            land = (float(lx.iloc[0]), float(ly.iloc[0]))
    return Tracks(frames, ids, X.to_numpy(float), Y.to_numpy(float), t, dt, src,
                  snap if snap is not None else 0, throw, tsrc, arrival, land,
                  ids.index(BALL_ID) if BALL_ID in ids else None,
                  "columnas ball_land de los datos" if land else None,
                  "evento de snap" if snap is not None else "primer cuadro (no hay evento de snap)")
