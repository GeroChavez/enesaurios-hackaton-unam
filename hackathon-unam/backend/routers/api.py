"""Rutas de la API. Todas cuelgan de /api."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..analytics.decoy import methodology
from ..core.data_store import get_store
from ..schemas import NovaRequest
from ..services import nova_service, play_service
from ..services.play_service import PlayNotFound

router = APIRouter(prefix="/api")

ID = r"^[A-Za-z0-9_.\-]{1,32}$"
GameId = Path(..., pattern=ID, description="Identificador de partido")
PlayId = Path(..., pattern=ID, description="Identificador de jugada")


def _guard(fn, *args):
    try:
        return fn(*args)
    except PlayNotFound as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/data/status")
def data_status():
    return get_store().status()


@router.get("/games")
def games():
    return {"items": get_store().games()}


@router.get("/plays")
def plays(game_id: Optional[str] = Query(None, pattern=ID), q: Optional[str] = Query(None, max_length=100),
          pass_result: Optional[str] = Query(None, pattern=r"^[A-Za-z]{1,4}$", description="C, I, IN, S, R o PASS (C+I+IN)"),
          limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    return get_store().plays(game_id, q, limit, offset, pass_result)


@router.get("/plays/{game_id}/{play_id}")
def play(game_id: str = GameId, play_id: str = PlayId):
    return _guard(play_service.play_detail, game_id, play_id)


@router.get("/plays/{game_id}/{play_id}/tracking")
def play_tracking(game_id: str = GameId, play_id: str = PlayId):
    return _guard(play_service.tracking, game_id, play_id)


@router.get("/plays/{game_id}/{play_id}/dvi")
def play_dvi(game_id: str = GameId, play_id: str = PlayId):
    return _guard(play_service.dvi, game_id, play_id)


@router.get("/plays/{game_id}/{play_id}/graph")
def play_graph(game_id: str = GameId, play_id: str = PlayId, frame: Optional[int] = None, frame_b: Optional[int] = None):
    return _guard(play_service.graph, game_id, play_id, frame, frame_b)


@router.get("/methodology")
def get_methodology():
    return methodology()


@router.get("/nova/status")
def nova_status():
    return nova_service.status()


@router.post("/plays/{game_id}/{play_id}/nova")
def play_nova(body: NovaRequest, game_id: str = GameId, play_id: str = PlayId):
    detail = _guard(play_service.play_detail, game_id, play_id)
    dvi = _guard(play_service.dvi, game_id, play_id)
    if not dvi.get("available"):
        return {"available": False, "error": "No hay DVI calculable para esta jugada; no hay métricas que explicar.",
                "reason": dvi.get("reason")}
    return nova_service.explain(detail, dvi, body.receiver_id, body.question)
