"""Resolución de columnas por alias y clasificación de tablas.

No se asumen nombres fijos: cada columna canónica se busca entre alias conocidos
(insensible a mayúsculas y a guiones bajos). Lo que se detecta se expone en
/api/data/status para que sea auditable.
"""
import re
from typing import Iterable

ALIASES: dict[str, list[str]] = {
    "game": ["game_id", "gameId"],
    "play": ["play_id", "playId"],
    "player": ["nfl_id", "nflId", "player_id", "playerId"],
    "frame": ["frame_id", "frameId", "frame"],
    "x": ["x"],
    "y": ["y"],
    "s": ["s", "speed"],
    "a": ["a", "acceleration"],
    "o": ["o", "orientation"],
    "dir": ["dir", "direction"],
    "name": ["player_name", "displayName", "playerName"],
    "position": ["player_position", "officialPosition", "position"],
    "alignment": ["pff_positionLinedUp"],
    "dis": ["dis"],
    "side": ["player_side", "side"],
    "role": ["pff_role", "player_role", "role"],
    "club": ["club", "team", "teamAbbr"],
    "event": ["event"],
    "time": ["time", "timestamp"],
    "play_direction": ["play_direction", "playDirection"],
    "ball_land_x": ["ball_land_x", "ballLandX"],
    "ball_land_y": ["ball_land_y", "ballLandY"],
    # tablas de jugadas / partidos
    "target": ["target_nfl_id", "targetNflId", "targeted_nfl_id"],
    "possession": ["possession_team", "possessionTeam"],
    "defensive_team": ["defensive_team", "defensiveTeam"],
    "description": ["play_description", "playDescription"],
    "home_team": ["home_team_abbr", "homeTeamAbbr", "home_team"],
    "visitor_team": ["visitor_team_abbr", "visitorTeamAbbr", "visitor_team"],
    "week": ["week"],
    "game_date": ["game_date", "gameDate"],
    "quarter": ["quarter"],
    "down": ["down"],
    "yards_to_go": ["yards_to_go", "yardsToGo"],
    "pass_result": ["pass_result", "passResult"],
    "game_clock": ["game_clock", "gameClock"],
}


def norm(col: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


def resolve(columns: Iterable[str]) -> dict[str, str]:
    """Devuelve {nombre_canónico: columna_real} para las columnas reconocidas."""
    by_norm: dict[str, str] = {}
    for c in columns:
        by_norm.setdefault(norm(c), c)
    out: dict[str, str] = {}
    for canon, alts in ALIASES.items():
        for alt in alts:
            if norm(alt) in by_norm:
                out[canon] = by_norm[norm(alt)]
                break
    return out


def classify(mapping: dict[str, str]) -> str:
    keys = set(mapping)
    if {"game", "play", "player", "frame", "x", "y"} <= keys:
        return "tracking"
    if {"game", "play", "player"} <= keys:
        return "player_play"
    if {"game", "play"} <= keys:
        return "plays"
    if "game" in keys:
        return "games"
    if "player" in keys:
        return "players"
    return "desconocida"


# Columnas que indican que una tabla de tracking trae información descriptiva del jugador.
DESCRIPTIVE = {"side", "role", "position", "club"}
