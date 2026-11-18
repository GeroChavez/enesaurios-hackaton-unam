"""Identificación de jugadores y roles a partir de los campos reales de la tabla."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

import pandas as pd

from .targets import infer_target

OFFENSE_POS = {"QB", "WR", "TE", "RB", "FB", "HB", "T", "G", "C", "OT", "OG", "OL"}
DEFENSE_POS = {"CB", "S", "FS", "SS", "DB", "LB", "ILB", "OLB", "MLB", "DE", "DT", "NT", "DL"}
RECEIVER_POS = {"WR", "TE", "RB", "FB", "HB"}

TARGET, PASSER, RECEIVER, OFF_OTHER = "objetivo", "pasador", "receptor_no_objetivo", "ofensiva_otro"
DEFENDER, RUSHER, UNKNOWN = "defensor", "defensor_presion", "desconocido"
BALL = "balon"


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
    poss = str(info.get("possession")) if info.get("possession") else None
    deft = str(info.get("defensive_team")) if info.get("defensive_team") else None
    used_inferred = False
    rows = []
    for pid, g in df.groupby("player", sort=True):
        pid = str(pid)
        club = _first(g["club"]) if "club" in g else None
        if pid == "ball" or (club and club.lower() == "football"):
            rows.append(Player(pid, "Balón", None, "neutral", None, BALL, "equipo 'football'"))
            continue
        name = _first(g["name"]) if "name" in g else None
        pos = _first(g["position"]) if "position" in g else None
        role = _first(g["role"]) if "role" in g else None
        side_raw = _first(g["side"]) if "side" in g else None
        rl = role.lower() if role else ""
        basis = []
        side = "desconocida"
        if side_raw and side_raw.lower().startswith("off"):
            side = "ofensiva"; basis.append("columna de lado")
        elif side_raw and side_raw.lower().startswith("def"):
            side = "defensiva"; basis.append("columna de lado")
        elif club and poss:
            side = "ofensiva" if club == poss else ("defensiva" if (not deft or club == deft) else "desconocida")
            basis.append("equipo vs. equipo con posesión")
        elif rl in ("pass", "pass route", "pass block", "passer") or rl.startswith("pass route"):
            side = "ofensiva"; basis.append("rol")
        elif rl in ("coverage", "pass rush"):
            side = "defensiva"; basis.append("rol")
        elif pos and pos.upper() in OFFENSE_POS:
            side, used_inferred = "ofensiva", True; basis.append("posición (inferida)")
        elif pos and pos.upper() in DEFENSE_POS:
            side, used_inferred = "defensiva", True; basis.append("posición (inferida)")
        rows.append(Player(pid, name, pos, side, role, UNKNOWN, " + ".join(basis) or "sin información"))

    # clasificación por rol (columna de rol por jugada si existe; si no, posición)
    has_role = any(p.role_raw for p in rows)
    for p in rows:
        if p.cls == BALL:
            continue
        rl = (p.role_raw or "").lower()
        P = (p.position or "").upper()
        if p.side == "ofensiva":
            if "target" in rl:
                p.cls = TARGET; p.basis += " + rol"
            elif rl == "pass" or "passer" in rl or (not has_role and P == "QB"):
                p.cls = PASSER; p.basis += " + rol" if has_role else " + posición"
            elif ("route" in rl) if has_role else (P in RECEIVER_POS):
                p.cls = RECEIVER; p.basis += " + rol" if has_role else " + posición (inferida)"
            else:
                p.cls = OFF_OTHER
        elif p.side == "defensiva":
            p.cls = RUSHER if "rush" in rl else DEFENDER

    # receptor objetivo: columna explícita > tabla de jugadas > nombre en la descripción
    target_basis = None
    if not any(p.cls == TARGET for p in rows):
        if target_id is not None:
            for p in rows:
                if p.id == target_id and p.side == "ofensiva":
                    p.cls = TARGET; p.basis += " + tabla de jugadas"; target_basis = "tabla de jugadas"
        else:
            cands = {p.id: p.name for p in rows if p.cls == RECEIVER and p.name}
            tid = infer_target(info.get("description"), cands)  # type: ignore[arg-type]
            for p in rows:
                if tid is not None and p.id == tid:
                    p.cls = TARGET; p.basis += " + nombre en la descripción de la jugada (inferido)"
                    target_basis = "nombre en la descripción de la jugada (inferido)"
    if target_basis and "inferido" in target_basis:
        notes.append("El receptor objetivo se infirió comparando el nombre de la descripción con los corredores de ruta de la jugada.")
    if used_inferred:
        notes.append("Algunos lados/roles se infirieron por posición porque faltan columnas explícitas.")
    if not any(p.cls == TARGET for p in rows):
        notes.append("No se pudo identificar al receptor objetivo (p. ej. sack, scramble o pase sin destinatario nombrado): el DVI no es calculable.")
    return rows, notes
