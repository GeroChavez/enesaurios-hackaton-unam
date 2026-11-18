"""Auditoría reproducible del dataset SIN pandas/numpy (solo biblioteca estándar).

    python -m backend.tools.audit_dataset            # desde la raíz del proyecto (hackathon-unam/)
    python -m backend.tools.audit_dataset --games 10 # solo los primeros 10 partidos (prueba rápida)

Lee data/ en modo solo lectura. Calcula, sobre TODOS los pases (passResult C, I, IN):
  1. cuántos tienen receptor objetivo inferido (nombre de la descripción vs. corredores de ruta PFF),
  2. cuántos cumplen las condiciones del DVI (snap, lanzamiento, ventana >= 5 cuadros, balón, objetivo),
  3. cuántos tienen evento de llegada del pase,
  4. validación cruzada: en jugadas con evento de llegada, ¿el corredor de ruta más cercano al balón
     coincide con el objetivo inferido?
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
from pathlib import Path

from ..analytics.events import ARRIVAL_EVENTS, SNAP_EVENTS, THROW_EVENTS
from ..analytics.targets import infer_target
from ..core.config import DATA_DIR

PASS = ("C", "I", "IN")
MIN_FRAMES = 5


def _read(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=0, help="limita el nº de partidos (0 = todos)")
    args = ap.parse_args()
    base = next((p.parent for p in DATA_DIR.rglob("plays.csv")), None)
    if base is None:
        raise SystemExit(f"No encuentro plays.csv bajo {DATA_DIR}")

    names = {r["nflId"]: r["displayName"] for r in _read(base / "players.csv")}
    roles = collections.defaultdict(dict)
    for r in _read(base / "pffScoutingData.csv"):
        roles[(r["gameId"], r["playId"])][r["nflId"]] = r["pff_role"]
    plays = {(r["gameId"], r["playId"]): r for r in _read(base / "plays.csv")}

    res = collections.Counter()
    by_result = collections.defaultdict(collections.Counter)
    seen_pass = set()
    agree = collections.Counter()

    files = sorted((base / "tracking").glob("tracking_*.csv"))
    if args.games:
        files = files[: args.games]

    for fpath in files:
        cur, ev, rows = None, {}, []

        def flush():
            if cur is None or cur not in plays or plays[cur]["passResult"] not in PASS:
                return
            p = plays[cur]
            seen_pass.add(cur)
            routes = {i: names.get(i, "") for i, r in roles[cur].items() if r == "Pass Route"}
            tg = infer_target(p["playDescription"], routes)
            res["pases"] += 1
            by_result[p["passResult"]]["total"] += 1
            if tg:
                res["con_objetivo_inferido"] += 1
                by_result[p["passResult"]]["con_objetivo_inferido"] += 1
            snaps = [f for f, e in ev.items() if e in SNAP_EVENTS]
            throws = [f for f, e in ev.items() if e in THROW_EVENTS]
            arr = [f for f, e in ev.items() if e in ARRIVAL_EVENTS]
            has_ball = any(r["nflId"] in ("NA", "") for r in rows)
            sn, th = (min(snaps) if snaps else None), (min(throws) if throws else None)
            if sn is None:
                res["sin_snap"] += 1
            if th is None:
                res["sin_lanzamiento"] += 1
            if not has_ball:
                res["sin_balon"] += 1
            if arr:
                res["con_evento_llegada"] += 1
            ok_window = sn is not None and th is not None and th - sn + 1 >= MIN_FRAMES
            if ok_window:
                res["ventana_>=5_cuadros"] += 1
            if tg and ok_window and has_ball:
                res["DVI_calculable"] += 1
                by_result[p["passResult"]]["DVI_calculable"] += 1
            if arr and tg:  # validación cruzada con el balón en la llegada
                fa = min(arr)
                pos = {r["nflId"]: (float(r["x"]), float(r["y"])) for r in rows if int(r["frameId"]) == fa and r["x"]}
                ball = pos.get("NA") or pos.get("")
                cand = {i: pos[i] for i in routes if i in pos}
                if ball and cand:
                    near = min(cand, key=lambda i: math.hypot(cand[i][0] - ball[0], cand[i][1] - ball[1]))
                    agree["comparables"] += 1
                    agree["coinciden"] += int(near == tg)

        for r in _read(fpath):
            k = (r["gameId"], r["playId"])
            if k != cur:
                flush()
                cur, ev, rows = k, {}, []
            rows.append(r)
            if r["event"] not in ("None", "NA", ""):
                ev[int(r["frameId"])] = r["event"]
        flush()

    out = {"partidos_leidos": len(files), "plays_csv_pases_total": sum(1 for p in plays.values() if p["passResult"] in PASS),
           "pases_con_tracking": len(seen_pass), **res,
           "por_resultado": {k: dict(v) for k, v in by_result.items()},
           "validacion_cruzada_llegada": dict(agree)}
    if res.get("pases"):
        out["pct_con_objetivo_inferido"] = round(100 * res["con_objetivo_inferido"] / res["pases"], 1)
        out["pct_DVI_calculable"] = round(100 * res["DVI_calculable"] / res["pases"], 1)
    if agree.get("comparables"):
        out["pct_coincidencia_llegada"] = round(100 * agree["coinciden"] / agree["comparables"], 1)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
