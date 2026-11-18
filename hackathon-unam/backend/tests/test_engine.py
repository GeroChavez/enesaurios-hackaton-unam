"""Pruebas con datos SINTÉTICOS (generados aquí). No son datos reales de la NFL.

Ejecutar desde la raíz del proyecto:  .venv/bin/python -m pytest backend/tests
"""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.analytics.decoy import compute_dvi
from backend.analytics.roles import classify_players
from backend.analytics.tracks import build_tracks
from backend.core import data_store
from backend.core.data_store import DataStore
from backend.main import app
from backend.services import play_service

N = 30


def synthetic_csv(defender_moves: bool) -> pd.DataFrame:
    rows = []
    for f in range(1, N + 1):
        u = (f - 1) / (N - 1)
        d11_y = 13 + 3 * u if defender_moves else 13.0
        players = [
            (1, "QB", "Passer", "Offense", 20.0, 26.0),
            (2, "WR", "Targeted Receiver", "Offense", 30.0, 10.0),
            (3, "WR", "Other Route Runner", "Offense", 30.0, 16.0),
            (11, "CB", "Defensive Coverage", "Defense", 30.0, d11_y),
            (12, "S", "Defensive Coverage", "Defense", 40.0, 40.0),
        ]
        for pid, pos, role, side, x, y in players:
            rows.append(dict(game_id=1, play_id=7, nfl_id=pid, frame_id=f, x=x, y=y,
                             player_position=pos, player_role=role, player_side=side, play_direction="right",
                             event="pass_forward" if (f == N and pid == 1) else None))
    return pd.DataFrame(rows)


def compute(tmp_path, moves: bool):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    synthetic_csv(moves).to_csv(d / "tracking.csv", index=False)
    store = DataStore(d)
    pdata = store.load_play("1", "7")
    players, _ = classify_players(pdata.df, pdata.target_id, pdata.info)
    tr = build_tracks(pdata.df)
    return tr, compute_dvi(tr, players)


def test_defender_pulled_away_gives_positive_components(tmp_path):
    tr, res = compute(tmp_path, True)
    assert tr.throw_idx == N - 1
    assert res["available"] and res["target_id"] == "2"
    r = res["receivers"][0]
    comp = {c["key"]: c for c in r["components"]}
    assert comp["pdp"]["raw"] > 0.5
    assert comp["espacio_objetivo"]["raw"] > 1.0
    assert comp["arrastre"]["raw"] > 0
    assert 0 < r["dvi"] <= 100


def test_static_defense_gives_zero_space_and_is_reproducible(tmp_path):
    _, a = compute(tmp_path, False)
    _, b = compute(tmp_path, False)
    comp = {c["key"]: c for c in a["receivers"][0]["components"]}
    assert comp["arrastre"]["raw"] == pytest.approx(0.0, abs=1e-9)
    assert comp["espacio_objetivo"]["raw"] == pytest.approx(0.0, abs=1e-9)
    assert a["receivers"][0]["dvi"] == b["receivers"][0]["dvi"]


def test_no_data_directory_is_handled(tmp_path):
    st = DataStore(tmp_path / "no_existe")
    s = st.status()
    assert s["has_data"] is False and st.games() == []


def test_api_endpoints(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    synthetic_csv(True).to_csv(d / "tracking.csv", index=False)
    monkeypatch.setattr(data_store, "_store", DataStore(d))
    play_service._cache.clear()
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/api/data/status").json()["has_data"] is True
    assert c.get("/api/games").json()["items"][0]["game_id"] == "1"
    assert c.get("/api/plays").json()["total"] == 1
    assert c.get("/api/plays/1/7").status_code == 200
    t = c.get("/api/plays/1/7/tracking").json()
    assert len(t["frames"]) == N and len(t["players"]) == 5
    assert c.get("/api/plays/1/7/dvi").json()["available"] is True
    g = c.get("/api/plays/1/7/graph?frame=1&frame_b=30").json()
    assert g["diff"]["changes"]
    assert c.get("/api/plays/9/9/dvi").status_code == 404
    assert c.get("/api/plays/1/7/graph?frame=999").status_code == 422
    assert c.get("/api/methodology").status_code == 200
