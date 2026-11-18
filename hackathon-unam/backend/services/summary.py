"""Resumen táctico determinista (sin IA) construido solo con las métricas ya calculadas."""
from __future__ import annotations

from typing import Any, Optional


def _n(v: Optional[float], d: int = 1) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def local_summary(dvi: dict[str, Any], target_name: Optional[str]) -> Optional[str]:
    if not dvi.get("available"):
        return None
    recs = [r for r in dvi["receivers"] if r.get("dvi") is not None]
    if not recs:
        return None
    top = recs[0]
    who = top.get("name") or f"jugador {top['id']}"
    tgt = target_name or f"jugador {dvi.get('target_id')}"
    inf = " (receptor objetivo inferido por nombre en la descripción)" if dvi.get("target_inferred") else ""
    comps = [c for c in top["components"] if c["normalized"] is not None]
    ranked = sorted(comps, key=lambda c: -(c["weight"] * c["normalized"]))
    lines = [
        f"El pase fue dirigido a {tgt}{inf}. Se evaluaron {len(recs)} receptores no objetivo entre el snap y el lanzamiento.",
        f"El mayor DVI experimental fue el de {who}: {_n(top['dvi'])} de 100 (cobertura de pesos {_n(100 * (top.get('weight_coverage') or 0), 0)} %).",
    ]
    if ranked:
        a = ranked[0]
        lines.append(f"Su mayor aporte fue «{a['label']}»: valor {_n(a['raw'], 2)} {a['unit']}, "
                     f"aporte {_n(100 * a['weight'] * a['normalized'])} puntos.")
    missing = [c["label"] for c in top["components"] if c["normalized"] is None]
    if missing:
        lines.append("No calculables para este receptor: " + "; ".join(missing) + ".")
    near = top.get("closest_defenders") or []
    if near:
        d = near[0]
        lines.append(f"Defensor con mayor proximidad geométrica: {d.get('name') or d['id']} "
                     f"(distancia media {_n(d['distancia_media_yd'])} yd, mínima {_n(d['distancia_minima_yd'])} yd).")
    lines.append("Lectura prudente: son coincidencias espaciales observadas en el tracking. El DVI es experimental, sus parámetros "
                 "no están calibrados y no demuestra que el receptor causara el movimiento defensivo ni mide la mirada de los defensores.")
    return "\n".join(lines)
