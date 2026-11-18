"""Acceso de solo lectura a los CSV de data/.

Estrategia para tablas grandes de tracking:
1. Al primer uso se lee cada archivo por bloques (solo columnas clave) y se construye un
   índice (partido, jugada) -> (primera fila, nº de filas). Nunca se carga el archivo completo.
2. Para consultar una jugada se leen únicamente sus filas (salto directo cuando son contiguas;
   si no, lectura por bloques con filtro).
Nada se escribe en disco. Todo vive en memoria del proceso.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from .config import DATA_DIR, FIELD_LENGTH, FIELD_WIDTH
from .schema import DESCRIPTIVE, classify, resolve

CHUNK = 500_000
TRACK_COLS = ["game", "play", "player", "frame", "x", "y", "s", "a", "o", "dir", "name",
              "position", "side", "role", "club", "event", "time", "play_direction",
              "ball_land_x", "ball_land_y"]


def idstr(s: pd.Series) -> pd.Series:
    """Identificadores como texto estable (2022091200.0 -> '2022091200')."""
    s = s.dropna()
    if pd.api.types.is_float_dtype(s):
        s = s.astype("int64")
    return s.astype(str)


def to_py(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v if isinstance(v, (str, int, bool)) else str(v)


def _count_rows(path: Path) -> int:
    n, last = 0, b""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 24)
            if not chunk:
                break
            n += chunk.count(b"\n")
            last = chunk[-1:]
    if last not in (b"\n", b""):
        n += 1
    return max(n - 1, 0)


@dataclass
class CsvFile:
    path: Path
    rel: str
    columns: list[str]
    mapping: dict[str, str]
    kind: str
    rows: int
    dtypes: dict[str, str]
    primary: bool = True
    index_map: dict[tuple[str, str], tuple[int, int]] = field(default_factory=dict)
    contiguous: bool = True
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayData:
    game_id: str
    play_id: str
    df: pd.DataFrame            # columnas canónicas
    info: dict[str, Any]        # fila de la tabla de jugadas (si existe)
    game_info: dict[str, Any]
    target_id: Optional[str]
    meta: dict[str, Any]


class DataStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.files: list[CsvFile] = []
        self._lock = threading.RLock()
        self._indexed = False
        self._plays: Optional[pd.DataFrame] = None
        self._games: Optional[pd.DataFrame] = None
        self._players: Optional[pd.DataFrame] = None
        self._plays_map: dict[str, str] = {}
        self._games_map: dict[str, str] = {}
        self._cache: dict[tuple[str, str], PlayData] = {}
        self._scanned = False

    # ---------------------------------------------------------------- escaneo
    def scan(self) -> None:
        with self._lock:
            if self._scanned:
                return
            self.files = []
            if self.data_dir.is_dir():
                for p in sorted(self.data_dir.rglob("*.csv")):
                    try:
                        head = pd.read_csv(p, nrows=2000, low_memory=False)
                    except Exception:  # archivo ilegible o vacío
                        continue
                    mapping = resolve(head.columns)
                    self.files.append(CsvFile(
                        path=p, rel=str(p.relative_to(self.data_dir.parent)), columns=list(head.columns),
                        mapping=mapping, kind=classify(mapping), rows=_count_rows(p),
                        dtypes={c: str(t) for c, t in head.dtypes.items()}))
                tracking = [f for f in self.files if f.kind == "tracking"]
                for f in tracking:
                    f.primary = bool(DESCRIPTIVE & set(f.mapping)) or not any(
                        DESCRIPTIVE & set(g.mapping) for g in tracking)
            self._scanned = True

    @property
    def tracking_files(self) -> list[CsvFile]:
        self.scan()
        return [f for f in self.files if f.kind == "tracking"]

    def _first(self, kind: str) -> Optional[CsvFile]:
        self.scan()
        return next((f for f in self.files if f.kind == kind), None)

    # ---------------------------------------------------------------- índice
    def ensure_index(self) -> None:
        with self._lock:
            if self._indexed:
                return
            for f in self.tracking_files:
                self._index_file(f)
            self._indexed = True

    def _index_file(self, f: CsvFile) -> None:
        m = f.mapping
        use = [m["game"], m["play"], m["player"], m["frame"], m["x"], m["y"]]
        inv = {v: k for k, v in m.items() if v in use}
        parts, offset = [], 0
        q = {"filas": 0, "x_o_y_nulos": 0, "fuera_de_campo": 0, "duplicados_en_bloque": 0, "sin_jugador": 0}
        for chunk in pd.read_csv(f.path, usecols=use, chunksize=CHUNK):
            chunk = chunk.rename(columns=inv)
            n = len(chunk)
            chunk["_pos"] = np.arange(offset, offset + n)
            offset += n
            q["filas"] += n
            q["x_o_y_nulos"] += int(chunk["x"].isna().sum() + chunk["y"].isna().sum())
            q["fuera_de_campo"] += int(((chunk["x"] < -5) | (chunk["x"] > FIELD_LENGTH + 5) |
                                        (chunk["y"] < -5) | (chunk["y"] > FIELD_WIDTH + 5)).sum())
            q["sin_jugador"] += int(chunk["player"].isna().sum())
            q["duplicados_en_bloque"] += int(chunk.duplicated(["game", "play", "player", "frame"]).sum())
            c = chunk.dropna(subset=["game", "play"])
            parts.append(c.groupby(["game", "play"])["_pos"].agg(first="min", last="max", n="count").reset_index())
        f.quality = q
        if not parts:
            return
        full = pd.concat(parts).groupby(["game", "play"], as_index=False).agg(
            first=("first", "min"), last=("last", "max"), n=("n", "sum"))
        full["game"], full["play"] = idstr(full["game"]), idstr(full["play"])
        f.contiguous = bool(((full["last"] - full["first"] + 1) == full["n"]).all())
        f.index_map = {(g, p): (int(a), int(n)) for g, p, a, n in
                       zip(full["game"], full["play"], full["first"], full["n"])}

    # --------------------------------------------------------- tablas auxiliares
    def _aux(self, kind: str) -> tuple[Optional[pd.DataFrame], dict[str, str]]:
        f = self._first(kind)
        if f is None:
            return None, {}
        df = pd.read_csv(f.path, low_memory=False)
        inv = {v: k for k, v in f.mapping.items()}
        keep = df.rename(columns=inv)
        for k in ("game", "play", "player"):
            if k in keep:
                keep[k] = idstr(keep[k]).reindex(keep.index)
        return keep, f.mapping

    def plays_table(self) -> Optional[pd.DataFrame]:
        with self._lock:
            if self._plays is None:
                self._plays, self._plays_map = self._aux("plays")
            return self._plays

    def games_table(self) -> Optional[pd.DataFrame]:
        with self._lock:
            if self._games is None:
                self._games, self._games_map = self._aux("games")
            return self._games

    def players_table(self) -> Optional[pd.DataFrame]:
        with self._lock:
            if self._players is None:
                self._players, _ = self._aux("players")
            return self._players

    # ------------------------------------------------------------- consultas
    def status(self) -> dict[str, Any]:
        self.scan()
        track = self.tracking_files
        if track:
            self.ensure_index()
        plays = {k for f in track for k in f.index_map}
        return {
            "data_dir": "data/",
            "data_dir_exists": self.data_dir.is_dir(),
            "has_data": bool(track),
            "files": [{
                "archivo": f.rel, "tipo": f.kind, "filas": f.rows, "columnas": f.columns,
                "columnas_reconocidas": f.mapping, "tracking_principal": f.primary if f.kind == "tracking" else None,
                "calidad": f.quality or None,
                "contiguo_por_jugada": f.contiguous if f.kind == "tracking" else None,
            } for f in self.files],
            "n_games": len({g for g, _ in plays}),
            "n_plays_with_tracking": len(plays),
            "tracking_rows": sum(f.rows for f in track),
            "notes": self._notes(track),
        }

    def _notes(self, track: list[CsvFile]) -> list[str]:
        notes: list[str] = []
        if not self.data_dir.is_dir() or not self.files:
            notes.append("No hay CSV en data/. La plataforma está lista para recibirlos; no se muestran resultados simulados.")
        elif not track:
            notes.append("Hay CSV pero ninguno tiene game, play, jugador, frame, x e y: no se puede reconstruir tracking.")
        for f in track:
            if not DESCRIPTIVE & set(f.mapping):
                notes.append(f"{f.rel}: sin columnas de lado/rol/posición; se trata como continuación si existe otra tabla de tracking con esa información.")
        return notes

    def games(self) -> list[dict[str, Any]]:
        self.scan()
        if not self.tracking_files:
            return []
        self.ensure_index()
        counts: dict[str, int] = {}
        for f in self.tracking_files:
            for (g, _p) in f.index_map:
                counts[g] = counts.get(g, 0)
        keys = {k for f in self.tracking_files for k in f.index_map}
        for g, _ in keys:
            counts[g] += 1
        gt = self.games_table()
        extra: dict[str, dict] = {}
        if gt is not None and "game" in gt:
            for r in gt.to_dict("records"):
                extra[str(r["game"])] = {k: to_py(r.get(k)) for k in
                                         ("week", "game_date", "home_team", "visitor_team") if k in r}
        out = [{"game_id": g, "n_plays": n, **extra.get(g, {})} for g, n in counts.items()]
        return sorted(out, key=lambda d: d["game_id"])

    def plays(self, game: Optional[str], q: Optional[str], limit: int, offset: int) -> dict[str, Any]:
        self.scan()
        keys = sorted({k for f in self.tracking_files for k in f.index_map}) if self.tracking_files else []
        if self.tracking_files:
            self.ensure_index()
            keys = sorted({k for f in self.tracking_files for k in f.index_map})
        base = pd.DataFrame(keys, columns=["game", "play"])
        base["has_tracking"] = True
        pt = self.plays_table()
        if pt is not None:
            cols = [c for c in ("game", "play", "description", "quarter", "down", "yards_to_go",
                                "possession", "defensive_team", "pass_result", "game_clock", "target")
                    if c in pt.columns]
            sub = pt[cols].drop_duplicates(["game", "play"])
            base = base.merge(sub, on=["game", "play"], how="outer")
            base["has_tracking"] = base["has_tracking"].fillna(False).astype(bool)
        if game:
            base = base[base["game"] == game]
        if q and "description" in base:
            base = base[base["description"].astype(str).str.contains(q, case=False, regex=False, na=False)]
        base = base.sort_values(["game", "play"])
        total = len(base)
        page = base.iloc[offset: offset + limit]
        items = [{("game_id" if k == "game" else "play_id" if k == "play" else k): to_py(v)
                  for k, v in r.items()} for r in page.to_dict("records")]
        return {"total": total, "limit": limit, "offset": offset, "items": items,
                "descripciones_disponibles": pt is not None}

    # ------------------------------------------------------------ una jugada
    def _read_rows(self, f: CsvFile, game: str, play: str) -> Optional[pd.DataFrame]:
        loc = f.index_map.get((game, play))
        if loc is None:
            return None
        first, n = loc
        m = f.mapping
        real = [m[c] for c in TRACK_COLS if c in m]
        inv = {v: k for k, v in m.items() if v in real}
        df = None
        if f.contiguous:
            try:
                df = pd.read_csv(f.path, header=None, names=f.columns, usecols=real,
                                 skiprows=first + 1, nrows=n).rename(columns=inv)
                ok = (idstr(df["game"]) == game).all() and (idstr(df["play"]) == play).all()
                if not ok:
                    df = None
            except Exception:
                df = None
        if df is None:
            frames = []
            for chunk in pd.read_csv(f.path, usecols=real, chunksize=CHUNK):
                chunk = chunk.rename(columns=inv)
                mask = (idstr(chunk["game"]).reindex(chunk.index) == game) & \
                       (idstr(chunk["play"]).reindex(chunk.index) == play)
                if mask.any():
                    frames.append(chunk[mask])
            df = pd.concat(frames, ignore_index=True) if frames else None
        return df

    def load_play(self, game: str, play: str) -> Optional[PlayData]:
        key = (game, play)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        self.scan()
        self.ensure_index()
        primary_parts, cont_parts = [], []
        for f in self.tracking_files:
            part = self._read_rows(f, game, play)
            if part is not None and len(part):
                (primary_parts if f.primary else cont_parts).append(part)
        if not primary_parts and not cont_parts:
            return None
        meta: dict[str, Any] = {"archivos_tracking": [f.rel for f in self.tracking_files if (game, play) in f.index_map]}
        df = self._build_canonical(primary_parts, cont_parts, meta)
        info, ginfo, target = self._lookup_info(game, play)
        df = self._orient(df, info, meta)
        df = self._attach_players(df)
        pd_ = PlayData(game, play, df, info, ginfo, target, meta)
        with self._lock:
            if len(self._cache) > 64:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = pd_
        return pd_

    @staticmethod
    def _numeric(df: pd.DataFrame) -> pd.DataFrame:
        for c in ("frame", "x", "y", "s", "a", "o", "dir", "ball_land_x", "ball_land_y"):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    def _build_canonical(self, prim: list[pd.DataFrame], cont: list[pd.DataFrame], meta: dict) -> pd.DataFrame:
        def clean(d: pd.DataFrame) -> pd.DataFrame:
            d = self._numeric(d.reset_index(drop=True))
            no_player = int(d["player"].isna().sum())
            meta["filas_sin_jugador_descartadas"] = meta.get("filas_sin_jugador_descartadas", 0) + no_player
            d = d.dropna(subset=["player", "frame", "x", "y"])
            d["player"] = idstr(d["player"]).reindex(d.index)
            return d.drop_duplicates(["player", "frame"], keep="first")

        base = clean(pd.concat(prim, ignore_index=True)) if prim else None
        meta["fase_principal"] = "tracking"
        if base is not None:
            base["phase"] = "principal"
        if cont:
            extra = clean(pd.concat(cont, ignore_index=True))
            if base is None:
                base = extra
                base["phase"] = "principal"
            else:
                offset = float(base["frame"].max())
                extra["frame"] = extra["frame"] + offset
                extra["phase"] = "continuacion"
                attrs = [c for c in ("name", "position", "side", "role", "club") if c in base]
                info = base.drop_duplicates("player")[["player"] + attrs]
                extra = extra.drop(columns=[c for c in attrs if c in extra]).merge(info, on="player", how="left")
                meta["continuacion"] = {"frame_offset": offset, "jugadores": int(extra["player"].nunique())}
                base = pd.concat([base, extra], ignore_index=True)
        assert base is not None
        return base.sort_values(["frame", "player"]).reset_index(drop=True)

    def _lookup_info(self, game: str, play: str) -> tuple[dict, dict, Optional[str]]:
        info: dict[str, Any] = {}
        target = None
        pt = self.plays_table()
        if pt is not None:
            row = pt[(pt["game"] == game) & (pt["play"] == play)]
            if len(row):
                r = row.iloc[0]
                info = {k: to_py(v) for k, v in r.items()}
                if "target" in pt.columns and pd.notna(r["target"]):
                    target = str(int(r["target"])) if isinstance(r["target"], (float, np.floating)) else str(r["target"])
        ginfo: dict[str, Any] = {}
        gt = self.games_table()
        if gt is not None:
            row = gt[gt["game"] == game]
            if len(row):
                ginfo = {k: to_py(v) for k, v in row.iloc[0].items()}
        return info, ginfo, target

    def _orient(self, df: pd.DataFrame, info: dict, meta: dict) -> pd.DataFrame:
        """Normaliza para que la ofensiva avance hacia +x (solo si se conoce la dirección)."""
        direction = None
        if "play_direction" in df and df["play_direction"].notna().any():
            direction = str(df["play_direction"].dropna().iloc[0]).lower()
        elif info.get("play_direction"):
            direction = str(info["play_direction"]).lower()
        meta["play_direction_original"] = direction
        if direction == "left":
            df["x"] = FIELD_LENGTH - df["x"]
            df["y"] = FIELD_WIDTH - df["y"]
            for c in ("ball_land_x",):
                if c in df:
                    df[c] = FIELD_LENGTH - df[c]
            if "ball_land_y" in df:
                df["ball_land_y"] = FIELD_WIDTH - df["ball_land_y"]
            for c in ("o", "dir"):
                if c in df:
                    df[c] = (df[c] + 180.0) % 360.0
        meta["orientacion_normalizada"] = direction in ("left", "right")
        return df

    def _attach_players(self, df: pd.DataFrame) -> pd.DataFrame:
        pl = self.players_table()
        if pl is None or "player" not in pl:
            return df
        for c in ("name", "position"):
            if c in pl.columns and (c not in df or df[c].isna().all()):
                m = pl.drop_duplicates("player").set_index("player")[c]
                df[c] = df["player"].map(m)
        return df


_store: Optional[DataStore] = None
_store_lock = threading.Lock()


def get_store() -> DataStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = DataStore()
        return _store
