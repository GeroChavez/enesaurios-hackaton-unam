"""Pruebas con datos SINTÉTICOS que imitan el esquema real (camelCase, pffScoutingData, balón).
No son datos de la NFL.

Ejecutar desde la raíz del proyecto:  .venv/bin/python -m pytest backend/tests
"""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.analytics.decoy import compute_dvi
from backend.analytics.roles import classify_players
from backend.analytics.targets import infer_target, name_keys
from backend.analytics.tracks import build_tracks
from backend.core import data_store
from backend.core.data_store import DataStore
from backend.main import app
from backend.services import play_service

N, THROW = 40, 30


def write_dataset(d, defender_moves: bool, with_description=True):
    d.mkdir(exist_ok=True)
    rows = []
    for f in range(1, N + 1):
        u = min((f - 1) / (THROW - 1), 1.0)
        d11_y = 13 + 3 * u if defender_moves else 13.0
        v = max(0.0, (f - THROW) / (N - THROW))
        ball = (20 + 10 * v, 26 - 16 * v)
        spec = [(1, "TB", 20.0, 26.0), (2, "TB", 30.0, 10.0), (3, "TB", 30.0, 16.0),
                (11, "DAL", 30.0, d11_y), (12, "DAL", 40.0, 40.0), (None, "football", *ball)]
        for pid, team, x, y in spec:
            rows.append(dict(gameId=1, playId=7, nflId=pid, frameId=f, time="2021-01-01T00:00:00Z", team=team,
                             playDirection="right", x=x, y=y, s=2.0, a=0.5, dis=0.2, o=0, dir=0,
                             event="pass_forward" if (f == THROW and pid == 1) else ("ball_snap" if (f == 1 and pid == 1) else "None")))
    pd.DataFrame(rows).to_csv(d / "tracking_1.csv", index=False)
    pd.DataFrame([dict(gameId=1, playId=7, possessionTeam="TB", defensiveTeam="DAL", passResult="I", quarter=1, down=1, yardsToGo=10,
                       gameClock="10:00", playDescription="(10:00) (Shotgun) Q.Back pass incomplete deep left to W.Target.")]).to_csv(d / "plays.csv", index=False)
    pd.DataFrame([dict(nflId=1, displayName="Quinn Back", officialPosition="QB"), dict(nflId=2, displayName="Will Target", officialPosition="WR"),
                  dict(nflId=3, displayName="Otto Runner", officialPosition="WR"), dict(nflId=11, displayName="Cory Back", officialPosition="CB"),
                  dict(nflId=12, displayName="Sam Safety", officialPosition="FS")]).to_csv(d / "players.csv", index=False)
    pd.DataFrame([dict(gameId=1, playId=7, nflId=i, pff_role=r, pff_positionLinedUp=p) for i, r, p in
                  [(1, "Pass", "QB"), (2, "Pass Route", "WR"), (3, "Pass Route", "WR"), (11, "Coverage", "CB"), (12, "Coverage", "FS")]]
                 ).to_csv(d / "pffScoutingData.csv", index=False)
    pd.DataFrame([dict(gameId=1, week=1, homeTeamAbbr="TB", visitorTeamAbbr="DAL")]).to_csv(d / "games.csv", index=False)


def compute(tmp_path, moves: bool):
    d = tmp_path / "data"
    write_dataset(d, moves)
    store = DataStore(d)
    pdata = store.load_play("1", "7")
    players, _ = classify_players(pdata.df, pdata.target_id, pdata.info)
    tr = build_tracks(pdata.df)
    return tr, players, compute_dvi(tr, players)


def test_name_matching():
    assert "cgodwin" in name_keys("Chris Godwin")
    assert "dmoore" in name_keys("D.J. Moore") and "djmoore" in name_keys("D.J. Moore")
    assert infer_target("pass incomplete to C.Godwin.", {"1": "Chris Godwin", "2": "Mike Evans"}) == "1"
    assert infer_target("pass incomplete short right.", {"1": "Chris Godwin"}) is None


def test_roles_time_and_zone_from_real_like_schema(tmp_path):
    tr, players, res = compute(tmp_path, True)
    cls = {p.id: p.cls for p in players}
    assert cls["1"] == "pasador" and cls["2"] == "objetivo" and cls["3"] == "receptor_no_objetivo"
    assert cls["11"] == "defensor" and cls["ball"] == "balon"
    assert tr.throw_idx == THROW - 1 and tr.start_idx == 0
    assert tr.dt == pytest.approx(0.1, abs=1e-6)        # estimado de dis/s, no del tiempo en segundos
    assert "menor distancia" in res["zone_source"]       # no hay evento de llegada


def test_defender_pulled_away_gives_positive_components(tmp_path):
    _, _, res = compute(tmp_path, True)
    assert res["available"] and res["target_id"] == "2"
    r = res["receivers"][0]
    comp = {c["key"]: c for c in r["components"]}
    assert comp["pdp"]["raw"] > 0.5
    assert comp["espacio_objetivo"]["raw"] > 1.0
    assert 0 < r["dvi"] <= 100
    assert res["target_inferred"] is True               # el objetivo sale de la descripción, no de un dato oficial


def test_static_defense_gives_zero_space_and_is_reproducible(tmp_path):
    _, _, a = compute(tmp_path, False)
    _, _, b = compute(tmp_path, False)
    comp = {c["key"]: c for c in a["receivers"][0]["components"]}
    assert comp["espacio_objetivo"]["raw"] == pytest.approx(0.0, abs=1e-9)
    assert comp["arrastre"]["raw"] is None or comp["arrastre"]["raw"] == pytest.approx(0.0, abs=1e-9)
    assert a["receivers"][0]["dvi"] == b["receivers"][0]["dvi"]


def _unavailable(tmp_path, mutate):
    d = tmp_path / "data"
    write_dataset(d, True)
    mutate(d)
    store = DataStore(d)
    pdata = store.load_play("1", "7")
    players, _ = classify_players(pdata.df, pdata.target_id, pdata.info)
    return compute_dvi(build_tracks(pdata.df), players)


def test_play_without_throw_is_not_computable(tmp_path):
    def m(d):
        df = pd.read_csv(d / "tracking_1.csv")
        df["event"] = df["event"].replace({"pass_forward": "None"})
        df.to_csv(d / "tracking_1.csv", index=False)
    res = _unavailable(tmp_path, m)
    assert res["available"] is False and "lanzamiento" in res["reason"]


def test_play_without_identifiable_target_is_not_computable(tmp_path):
    def m(d):
        p = pd.read_csv(d / "plays.csv")
        p["playDescription"] = "(10:00) (Shotgun) Q.Back pass incomplete deep left."
        p.to_csv(d / "plays.csv", index=False)
    res = _unavailable(tmp_path, m)
    assert res["available"] is False and "objetivo" in res["reason"]


def test_play_without_snap_is_not_computable(tmp_path):
    def m(d):
        df = pd.read_csv(d / "tracking_1.csv")
        df["event"] = df["event"].replace({"ball_snap": "None"})
        df.to_csv(d / "tracking_1.csv", index=False)
    res = _unavailable(tmp_path, m)
    assert res["available"] is False and "snap" in res["reason"]


def test_no_data_directory_is_handled(tmp_path):
    st = DataStore(tmp_path / "no_existe")
    s = st.status()
    assert s["has_data"] is False and st.games() == []


def test_api_endpoints(tmp_path, monkeypatch):
    d = tmp_path / "data"
    write_dataset(d, True)
    monkeypatch.setattr(data_store, "_store", DataStore(d))
    play_service._cache.clear()
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    st = c.get("/api/data/status").json()
    assert st["has_data"] is True and st["n_tracking_files"] == 1 and st["n_plays"] == 1
    assert c.get("/api/games").json()["items"][0]["game_id"] == "1"
    assert c.get("/api/plays?pass_result=PASS").json()["total"] == 1
    assert c.get("/api/plays?pass_result=S").json()["total"] == 0
    assert c.get("/api/plays/1/7").status_code == 200
    t = c.get("/api/plays/1/7/tracking").json()
    assert len(t["frames"]) == N and len(t["players"]) == 6
    assert c.get("/api/plays/1/7/dvi").json()["available"] is True
    g = c.get("/api/plays/1/7/graph?frame=1&frame_b=30").json()
    assert g["diff"]["changes"]
    assert c.get("/api/plays/9/9/dvi").status_code == 404
    assert c.get("/api/plays/1/7/graph?frame=999").status_code == 422
    assert c.get("/api/methodology").status_code == 200


@pytest.mark.skipif(not data_store.DATA_DIR.is_dir() or next(data_store.DATA_DIR.rglob("*.csv"), None) is None,
                    reason="dataset real no disponible")
def test_real_dataset_schema_is_recognized():
    st = DataStore(data_store.DATA_DIR)
    st.scan()
    kinds = [f.kind for f in st.files]
    assert len(st.files) == 126
    assert kinds.count("tracking") == 122
    assert {"games", "plays", "players", "player_play"} <= set(kinds)
