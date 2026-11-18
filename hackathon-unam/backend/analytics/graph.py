"""Grafo dinámico ofensiva-defensa.

Nodos: receptores (objetivo y no objetivo), pasador y defensores con datos.
Aristas (solo entre ofensivo y defensor): existe en el cuadro f si d_ij(f) <= R (por defecto 8 yd),
con peso w_ij(f) = K(d_ij(f)) = exp(-d²/(2σ²)), σ = 3 yd. La variación de una arista entre dos cuadros
es Δd = d_ij(f_b) - d_ij(f_a); Δd > 0 significa que se separan. Son relaciones geométricas, no de causalidad.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .decoy import SIGMA
from .roles import DEFENDER, OFF_OTHER, PASSER, Player, RECEIVER, TARGET
from .tracks import Tracks

RADIUS = 8.0
TOL = 0.5  # yd: umbral para considerar que una arista "se aleja" o "se acerca"


class DynamicGraph:
    def __init__(self, tr: Tracks, players: list[Player], radius: float = RADIUS):
        self.tr, self.radius = tr, radius
        off = [p for p in players if p.cls in (TARGET, RECEIVER, PASSER) and p.id in tr.ids]
        dfn = [p for p in players if p.cls == DEFENDER and p.id in tr.ids]
        self.off, self.dfn = off, dfn
        oi = [tr.col(p.id) for p in off]
        di = [tr.col(p.id) for p in dfn]
        if oi and di:
            self.D = np.hypot(tr.X[:, oi][:, :, None] - tr.X[:, di][:, None, :],
                              tr.Y[:, oi][:, :, None] - tr.Y[:, di][:, None, :])   # (F, O, D)
        else:
            self.D = np.full((len(tr.frames), len(oi), len(di)), np.nan)

    def nodes(self) -> list[dict[str, Any]]:
        return [{"id": p.id, "name": p.name, "position": p.position, "class": p.cls} for p in self.off + self.dfn]

    def _idx(self, frame: int) -> int:
        i = int(np.searchsorted(self.tr.frames, frame))
        if i >= len(self.tr.frames) or self.tr.frames[i] != frame:
            raise KeyError(frame)
        return i

    def snapshot(self, frame: int) -> dict[str, Any]:
        i = self._idx(frame)
        edges = []
        for a, o in enumerate(self.off):
            for b, d in enumerate(self.dfn):
                v = self.D[i, a, b]
                if np.isfinite(v) and v <= self.radius:
                    edges.append({"source": o.id, "target": d.id, "distance_yd": float(v),
                                  "weight": float(np.exp(-v ** 2 / (2 * SIGMA ** 2)))})
        possible = max(len(self.off) * len(self.dfn), 1)
        return {"frame": frame, "radius_yd": self.radius, "edges": edges,
                "density": len(edges) / possible}

    def diff(self, frame_a: int, frame_b: int) -> dict[str, Any]:
        ia, ib = self._idx(frame_a), self._idx(frame_b)
        changes = []
        for a, o in enumerate(self.off):
            for b, d in enumerate(self.dfn):
                da, db = self.D[ia, a, b], self.D[ib, a, b]
                if not (np.isfinite(da) and np.isfinite(db)) or min(da, db) > self.radius:
                    continue
                delta = float(db - da)
                state = "se_aleja" if delta > TOL else "se_acerca" if delta < -TOL else "estable"
                changes.append({"source": o.id, "target": d.id, "distance_a_yd": float(da), "distance_b_yd": float(db),
                                "delta_yd": delta, "state": state})
        changes.sort(key=lambda c: -abs(c["delta_yd"]))
        return {"frame_a": frame_a, "frame_b": frame_b, "radius_yd": self.radius, "changes": changes}

    def series(self) -> list[dict[str, Any]]:
        """Por cada nodo ofensivo: grado ponderado, defensor más cercano y conteo en radio, por cuadro."""
        out = []
        for a, o in enumerate(self.off):
            row = self.D[:, a, :]
            if row.shape[1] == 0:
                continue
            w = np.where(np.isfinite(row), np.exp(-row ** 2 / (2 * SIGMA ** 2)), 0.0)
            valid = np.isfinite(row).any(axis=1)
            near = np.where(valid, np.nanmin(np.where(np.isfinite(row), row, np.inf), axis=1), np.nan)
            near[~np.isfinite(near)] = np.nan
            cnt = np.nansum(np.where(np.isfinite(row), row <= self.radius, False), axis=1)
            out.append({"id": o.id, "class": o.cls, "frames": [int(f) for f in self.tr.frames],
                        "weighted_degree": [float(v) if ok else None for v, ok in zip(w.sum(1), valid)],
                        "nearest_defender_yd": [float(v) if np.isfinite(v) else None for v in near],
                        "defenders_in_radius": [int(c) if ok else None for c, ok in zip(cnt, valid)]})
        return out
