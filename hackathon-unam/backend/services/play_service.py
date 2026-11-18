"""Orquesta datos + motor analítico para una jugada."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ..analytics.decoy import compute_dvi, methodology
from ..analytics.graph import DynamicGraph
from ..analytics.roles import Player, classify_players
from ..analytics.tracks import Tracks, build_tracks
from ..core.data_store import PlayData, get_store


class PlayNotFound(Exception):
    pass


@dataclass
class PlayContext:
    data: PlayData
    tracks: Tracks
    players: list[Player]
    notes: list[str]
    _dvi: Optional[dict] = None
    _graph: Optional[DynamicGraph] = None


_cache: dict[tuple[str, str], PlayContext] = {}
_lock = threading.Lock()


def get_context(game: str, play: str) -> PlayContext:
    key = (game, play)
    with _lock:
        if key in _cache:
            return _cache[key]
    data = get_store().load_play(game, play)
    if data is None or data.df.empty:
        raise PlayNotFound(f"No hay tracking para el partido {game}, jugada {play}.")
    players, notes = classify_players(data.df, data.target_id, data.info)
    ctx = PlayContext(data, build_tracks(data.df), players, notes)
    with _lock:
        if len(_cache) > 64:
            _cache.pop(next(iter(_cache)))
        _cache[key] = ctx
    return ctx


def _clean(v: Any) -> Any:
    """Convierte NaN/inf a None y tipos numpy a nativos (JSON válido)."""
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, np.integer):
        return int(v)
    return v


def play_detail(game: str, play: str) -> dict[str, Any]:
    c = get_context(game, play)
    tr = c.tracks
    quality = {
        "frames": int(len(tr.frames)), "jugadores": len(tr.ids),
        "celdas_sin_dato": int(np.isnan(tr.X).sum()),
        "celdas_totales": int(tr.X.size),
    }
    return _clean({
        "game_id": game, "play_id": play, "info": c.data.info, "game_info": c.data.game_info,
        "players": [p.dict() for p in c.players],
        "events": {
            "start_frame": int(tr.frames[tr.start_idx]),
            "throw_frame": int(tr.frames[tr.throw_idx]) if tr.throw_idx is not None else None,
            "throw_source": tr.throw_source,
            "arrival_frame": int(tr.frames[tr.arrival_idx]) if tr.arrival_idx is not None else None,
            "ball_land": {"x": tr.ball_land[0], "y": tr.ball_land[1]} if tr.ball_land else None,
        },
        "time": {"dt_s": tr.dt, "source": tr.dt_source},
        "data_quality": quality, "meta": c.data.meta, "notes": c.notes,
    })


def tracking(game: str, play: str) -> dict[str, Any]:
    c = get_context(game, play)
    tr = c.tracks
    by_id = {p.id: p for p in c.players}
    pl = []
    for i, pid in enumerate(tr.ids):
        p = by_id.get(pid)
        pl.append({
            "id": pid, "name": p.name if p else None, "position": p.position if p else None,
            "side": p.side if p else "desconocida", "class": p.cls if p else "desconocido",
            "x": [None if not np.isfinite(v) else round(float(v), 2) for v in tr.X[:, i]],
            "y": [None if not np.isfinite(v) else round(float(v), 2) for v in tr.Y[:, i]],
        })
    ev = play_detail(game, play)["events"]
    return _clean({"game_id": game, "play_id": play, "frames": [int(f) for f in tr.frames],
                   "t_s": [round(float(t), 3) for t in tr.t], "events": ev, "players": pl,
                   "orientation_normalized": c.data.meta.get("orientacion_normalizada", False)})


def dvi(game: str, play: str) -> dict[str, Any]:
    c = get_context(game, play)
    if c._dvi is None:
        res = compute_dvi(c.tracks, c.players)
        res["game_id"], res["play_id"], res["notes"] = game, play, c.notes
        res["methodology_ref"] = "api/methodology"
        c._dvi = _clean(res)
    return c._dvi


def graph(game: str, play: str, frame: Optional[int], frame_b: Optional[int]) -> dict[str, Any]:
    c = get_context(game, play)
    if c._graph is None:
        c._graph = DynamicGraph(c.tracks, c.players)
    g = c._graph
    out: dict[str, Any] = {"game_id": game, "play_id": play, "nodes": g.nodes(), "radius_yd": g.radius}
    try:
        if frame is not None:
            out["snapshot"] = g.snapshot(frame)
        if frame is not None and frame_b is not None:
            out["diff"] = g.diff(frame, frame_b)
    except KeyError as e:
        raise ValueError(f"El frame {e.args[0]} no existe en esta jugada.")
    if frame is None:
        out["series"] = g.series()
    return _clean(out)


__all__ = ["PlayNotFound", "play_detail", "tracking", "dvi", "graph", "methodology"]
