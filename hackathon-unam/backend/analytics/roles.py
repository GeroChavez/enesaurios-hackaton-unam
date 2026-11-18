"""Identificación de jugadores y roles a partir de los campos reales de la tabla."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

import pandas as pd

OFFENSE_POS = {"QB", "WR", "TE", "RB", "FB", "HB", "T", "G", "C", "OT", "OG", "OL"}
DEFENSE_POS = {"CB", "S", "FS", "SS", "DB", "LB", "ILB", "OLB", "MLB", "DE", "DT", "NT", "DL"}
RECEIVER_POS = {"WR", "TE", "RB", "FB", "HB"}

TARGET, PASSER, RECEIVER, OFF_OTHER = "objetivo", "pasador", "receptor_no_objetivo", "ofensiva_otro"
DEFENDER, RUSHER, UNKNOWN = "defensor", "defensor_presion", "desconocido"


@dataclass
class Player:
    id: str
    name: Optional[str]
    position: Optional[str]
    side: str                  # ofensiva | defensiva | desconocida
    role_raw: Optional[str]
    cls: str
    basis: str                 # de dónde sale la clasificación

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _first(s: pd.Series) -> Optional[str]:
    s = s.dropna()
    return str(s.iloc[0]) if len(s) else None


def classify_players(df: pd.DataFrame, target_id: Optional[str], info: dict[str, Any]) -> tuple[list[Player], list[str]]:
    notes: list[str] = []
    has = lambda c: c in df.columns and df[c].notna().any()  # noqa: E731
    poss = str(info.get("possession")) if info.get("possession") else None
    deft = str(info.get("defensive_team")) if info.get("defensive_team") else None
    players: list[Player] = []
    used_inferred = False
    for pid, g in df.groupby("player", sort=True):
        name = _first(g["name"]) if "name" in g else None
        pos = _first(g["position"]) if "position" in g else None
        role = _first(g["role"]) if "role" in g else None
        side_raw = _first(g["side"]) if "side" in g else None
        club = _first(g["club"]) if "club" in g else None
        basis = []
        side = "desconocida"
        if side_raw and side_raw.lower().startswith("off"):
            side, _ = "ofensiva", basis.append("columna de lado")
        elif side_raw and side_raw.lower().startswith("def"):
            side, _ = "defensiva", basis.append("columna de lado")
        elif club and poss:
            side = "ofensiva" if club == poss else ("defensiva" if (not deft or club == deft) else "desconocida")
            basis.append("equipo vs. equipo con posesión")
        elif pos and pos.upper() in OFFENSE_POS:
            side, used_inferred = "ofensiva", True
            basis.append("posición (inferida)")
        elif pos and pos.upper() in DEFENSE_POS:
            side, used_inferred = "defensiva", True
            basis.append("posición (inferida)")
        rl = role.lower() if role else ""
        P = (pos or "").upper()
        cls = UNKNOWN
        if side == "ofensiva":
            if "target" in rl or (target_id is not None and str(pid) == target_id):
                cls = TARGET
                basis.append("rol" if "target" in rl else "tabla de jugadas")
            elif "passer" in rl or (not role and P == "QB"):
                cls = PASSER
                basis.append("rol" if role else "posición")
            elif ("route" in rl) if role else (P in RECEIVER_POS):
                cls = RECEIVER
                basis.append("rol" if role else "posición (inferida)")
            else:
                cls = OFF_OTHER
        elif side == "defensiva":
            cls = RUSHER if "rush" in rl else DEFENDER
        players.append(Player(str(pid), name, pos, side, role, cls, " + ".join(basis) or "sin información"))
    if used_inferred:
        notes.append("Algunos lados/roles se infirieron por posición porque faltan columnas explícitas.")
    if not any(p.cls == TARGET for p in players):
        notes.append("No se pudo identificar al receptor objetivo con los campos disponibles: el DVI no es calculable.")
    return players, notes
