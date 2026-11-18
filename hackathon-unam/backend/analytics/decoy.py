"""Decoy Value Index (DVI): indicador EXPERIMENTAL del valor táctico indirecto observable.

Todo se calcula con posiciones reales dentro de la ventana [inicio, lanzamiento] (o hasta el último
cuadro si el lanzamiento no se conoce). Unidades: yardas (yd) y cuadros. No es una probabilidad,
ni una medida causal, ni una métrica oficial de la NFL.

Notación para un receptor no objetivo R, defensores j en D, beneficiario k:
  d_ab(f)  distancia euclidiana entre a y b en el cuadro f
  K(d)     = exp(-d^2 / (2 sigma^2)),  sigma = 3 yd  (núcleo de proximidad, en [0, 1])
  a_j      = media_f K(d_Rj(f))        peso de proximidad R-j en la ventana [s, e]
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from .geometry import dist_to, kinematics, nanmean
from .roles import Player, RECEIVER, TARGET, DEFENDER
from .tracks import Tracks

SIGMA = 3.0
MIN_FRAMES = 5

# clave: (etiqueta, unidad, referencia de saturación, peso)
COMPONENTS: dict[str, dict[str, Any]] = {
    "pdp": dict(
        label="Proximidad defensiva potencial", unit="defensores-equivalentes", ref=1.0, weight=0.25,
        formula="PDP = media_f [ sum_j K(d_Rj(f)) ];  c1 = min(PDP / 1.0, 1)",
        measures="Cuántos defensores estuvieron, en promedio, geométricamente cerca del receptor. "
                 "Un defensor a 0 yd cuenta 1; a 3 yd cuenta 0.61; a 9 yd cuenta 0.01.",
        limitation="Proximidad no es atención visual: no hay datos de mirada ni de asignación de cobertura.",
    ),
    "arrastre": dict(
        label="Arrastre defensivo respecto a la zona de balón", unit="yd", ref=4.0, weight=0.25,
        formula="Δ_j = d_jZ(e) - d_jZ(s);  A = sum_j a_j Δ_j / sum_j a_j  -  media_j Δ_j;  c2 = clip(A / 4, 0, 1)",
        measures="Cuánto más se alejaron de la zona de balón Z los defensores cercanos al receptor "
                 "que el defensor promedio (se resta el movimiento defensivo general como control).",
        limitation="Z es la zona de aterrizaje del balón si existe en los datos; si no, la posición del objetivo "
                   "al final de la ventana. Es una coincidencia espacial, no prueba que el receptor causara el movimiento.",
    ),
    "espacio_objetivo": dict(
        label="Espacio liberado para el receptor objetivo", unit="yd", ref=2.0, weight=0.30,
        formula="b_kj = K(d_kj(s)) / sum_j K(d_kj(s));  G_k = sum_j a_j b_kj [d_kj(e) - d_kj(s)];  c3 = clip(G_T / 2, 0, 1)",
        measures="Aumento de distancia al objetivo T de los defensores que eran relevantes para T y que además "
                 "estuvieron cerca de R (ponderado por a_j).",
        limitation="El objetivo pudo ganar separación por su propia ruta; el índice solo atribuye la parte "
                   "compartida con defensores próximos a R.",
    ),
    "espacio_companeros": dict(
        label="Espacio liberado para otros compañeros", unit="yd", ref=2.0, weight=0.20,
        formula="c4 = clip(media_k G_k / 2, 0, 1)  con k = receptores distintos de R y del objetivo",
        measures="Lo mismo que el componente anterior, promediado sobre los demás receptores.",
        limitation="Depende de cuántos receptores tengan datos; ignora bloqueos y receptores no identificables.",
    ),
}


def methodology() -> dict[str, Any]:
    return {
        "nombre": "Decoy Value Index (DVI)",
        "estado": "Indicador experimental desarrollado por el equipo. No es una probabilidad de éxito, "
                  "no demuestra causalidad y no es una métrica oficial de la NFL.",
        "escala": "DVI = 100 · sum_i(w_i c_i) / sum_i(w_i) sobre los componentes calculables. Cada c_i está en [0, 1].",
        "nucleo": {"sigma_yd": SIGMA, "formula": "K(d) = exp(-d² / (2σ²))"},
        "ventana": "Desde el snap (o primer cuadro) hasta el lanzamiento; si no se conoce, hasta el último cuadro.",
        "componentes": [{"key": k, **{kk: vv for kk, vv in v.items()}} for k, v in COMPONENTS.items()],
        "pesos": "Pesos fijados por criterio del equipo (no ajustados con datos): el espacio liberado para el objetivo "
                 "pesa más porque es el efecto táctico más directo; proximidad y arrastre son indicios de interacción; "
                 "el espacio para otros compañeros es secundario. Las saturaciones (ref) son referencias fijas para "
                 "que la escala sea comparable entre jugadas, no percentiles de la liga.",
        "doble_conteo": "PDP mide proximidad R-defensor; Arrastre mide movimiento relativo a la zona de balón; los dos "
                        "componentes de espacio miden beneficiarios distintos (objetivo / compañeros). Arrastre y espacio "
                        "al objetivo pueden correlacionar porque ambos dependen del movimiento defensivo.",
        "no_calculable": "Si un componente no se puede calcular, se excluye y los pesos restantes se renormalizan; "
                         "se reporta la cobertura de pesos utilizada.",
        "solo_no_objetivo": "El DVI se calcula para receptores que no fueron objetivo del pase.",
    }


def _K(d: np.ndarray) -> np.ndarray:
    return np.exp(-(d ** 2) / (2 * SIGMA ** 2))


def _gain(tr: Tracks, k: int, defs: list[int], a: np.ndarray, s: int, e: int) -> Optional[float]:
    dk = dist_to(tr, k, defs)
    d0, d1 = dk[s], dk[e]
    ok = np.isfinite(d0) & np.isfinite(d1) & np.isfinite(a)
    if ok.sum() < 1:
        return None
    k0 = _K(d0[ok])
    tot = k0.sum()
    if tot < 1e-9:
        return 0.0
    b = k0 / tot
    return float(np.sum(a[ok] * b * (d1[ok] - d0[ok])))


def _zone(tr: Tracks, t_idx: Optional[int], e: int) -> tuple[Optional[tuple[float, float]], str]:
    if tr.ball_land is not None:
        return tr.ball_land, "zona de aterrizaje del balón (columna de los datos)"
    if t_idx is not None:
        x, y = tr.X[e, t_idx], tr.Y[e, t_idx]
        if np.isfinite(x) and np.isfinite(y):
            return (float(x), float(y)), "posición del receptor objetivo al final de la ventana (aproximación)"
    return None, "no disponible"


def _components_at(tr: Tracks, r: int, t_idx: Optional[int], defs: list[int], others: list[int],
                   s: int, e: int, zone: Optional[tuple[float, float]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    dRD = dist_to(tr, r, defs)[s:e + 1]
    Kd = _K(dRD)
    nvalid = np.isfinite(dRD).sum(axis=0)
    a = np.where(nvalid >= MIN_FRAMES, nanmean(Kd, axis=0), np.nan)
    a0 = np.nan_to_num(a, nan=0.0)

    frame_ok = np.isfinite(dRD).any(axis=1)
    if frame_ok.sum() >= MIN_FRAMES:
        pdp = float(np.mean(np.nansum(Kd[frame_ok], axis=1)))
        out["pdp"] = {"raw": pdp, "norm": float(np.clip(pdp / COMPONENTS["pdp"]["ref"], 0, 1))}
    else:
        out["pdp"] = {"raw": None, "norm": None, "note": "Datos insuficientes de defensores cercanos."}

    # arrastre
    if zone is not None and len(defs) >= 2:
        dj0 = np.hypot(tr.X[s, defs] - zone[0], tr.Y[s, defs] - zone[1])
        dj1 = np.hypot(tr.X[e, defs] - zone[0], tr.Y[e, defs] - zone[1])
        delta = dj1 - dj0
        ok = np.isfinite(delta)
        if ok.sum() >= 2:
            w = a0[ok]
            if w.sum() < 1e-6:
                raw, note = 0.0, "Ningún defensor estuvo cerca del receptor."
            else:
                raw, note = float(np.sum(w * delta[ok]) / w.sum() - np.mean(delta[ok])), None
            out["arrastre"] = {"raw": raw, "norm": float(np.clip(raw / COMPONENTS["arrastre"]["ref"], 0, 1)),
                               **({"note": note} if note else {})}
    out.setdefault("arrastre", {"raw": None, "norm": None, "note": "Sin zona de referencia o defensores suficientes."})

    # espacio para objetivo y compañeros
    if t_idx is not None:
        g = _gain(tr, t_idx, defs, a, s, e)
        out["espacio_objetivo"] = ({"raw": g, "norm": float(np.clip(g / COMPONENTS["espacio_objetivo"]["ref"], 0, 1))}
                                   if g is not None else {"raw": None, "norm": None, "note": "Sin datos del objetivo."})
    else:
        out["espacio_objetivo"] = {"raw": None, "norm": None, "note": "Receptor objetivo no identificado."}
    gains = [g for g in (_gain(tr, k, defs, a, s, e) for k in others) if g is not None]
    if gains:
        m = float(np.mean(gains))
        out["espacio_companeros"] = {"raw": m, "norm": float(np.clip(m / COMPONENTS["espacio_companeros"]["ref"], 0, 1)),
                                     "n_beneficiarios": len(gains)}
    else:
        out["espacio_companeros"] = {"raw": None, "norm": None, "note": "No hay otros receptores con datos."}
    return out


def _combine(comps: dict[str, dict]) -> tuple[Optional[float], float]:
    num = den = 0.0
    for k, c in comps.items():
        if c.get("norm") is not None:
            w = COMPONENTS[k]["weight"]
            num += w * c["norm"]
            den += w
    if den == 0 or comps.get("pdp", {}).get("norm") is None:
        return None, 0.0
    return 100.0 * num / den, den


def compute_dvi(tr: Tracks, players: list[Player]) -> dict[str, Any]:
    by_id = {p.id: p for p in players}
    target = next((p for p in players if p.cls == TARGET and p.id in tr.ids), None)
    recvs = [p for p in players if p.cls == RECEIVER and p.id in tr.ids]
    defs_p = [p for p in players if p.cls == DEFENDER and p.id in tr.ids]
    defs = [tr.col(p.id) for p in defs_p]
    t_idx = tr.col(target.id) if target else None

    s0 = tr.start_idx
    e = tr.throw_idx if tr.throw_idx is not None else len(tr.frames) - 1
    result: dict[str, Any] = {
        "available": False, "reason": None,
        "window": {"start_frame": int(tr.frames[s0]), "end_frame": int(tr.frames[e]),
                   "throw_frame": int(tr.frames[tr.throw_idx]) if tr.throw_idx is not None else None,
                   "throw_source": tr.throw_source, "dt_s": tr.dt, "dt_source": tr.dt_source,
                   "arrival_frame": int(tr.frames[tr.arrival_idx]) if tr.arrival_idx is not None else None},
        "parameters": {"sigma_yd": SIGMA, "min_frames": MIN_FRAMES},
        "target_id": target.id if target else None, "receivers": [], "warnings": [],
    }
    if e - s0 + 1 < MIN_FRAMES:
        result["reason"] = "Ventana temporal demasiado corta."
        return result
    if not defs:
        result["reason"] = "No hay defensores identificables con tracking."
        return result
    if not recvs:
        result["reason"] = "No hay receptores no objetivo identificables."
        return result
    if target is None:
        result["warnings"].append("Sin receptor objetivo: no se calculan los componentes de espacio para el objetivo ni el arrastre.")
    if tr.throw_idx is None:
        result["warnings"].append("No se identificó el momento del lanzamiento; la ventana llega al último cuadro.")

    zone, zone_src = _zone(tr, t_idx, e)
    result["zone"] = {"x": zone[0], "y": zone[1]} if zone else None
    result["zone_source"] = zone_src

    for rp in recvs:
        r = tr.col(rp.id)
        valid = np.where(np.isfinite(tr.X[s0:e + 1, r]) & np.isfinite(tr.Y[s0:e + 1, r]))[0]
        if len(valid) < MIN_FRAMES:
            result["receivers"].append({"id": rp.id, "name": rp.name, "position": rp.position, "dvi": None,
                                        "reason": "Receptor con datos insuficientes en la ventana."})
            continue
        s = s0 + int(valid[0])
        others = [tr.col(p.id) for p in recvs if p.id != rp.id]
        comps = _components_at(tr, r, t_idx, defs, others, s, e, zone)
        dvi, cover = _combine(comps)

        series = []
        for ee in range(s + MIN_FRAMES - 1, e + 1):
            c = _components_at(tr, r, t_idx, defs, others, s, ee, zone)
            v, _ = _combine(c)
            series.append({"frame": int(tr.frames[ee]), "t_s": float(tr.t[ee] - tr.t[s]), "dvi": v,
                           **{k: c[k]["norm"] for k in COMPONENTS}})

        dRD = dist_to(tr, r, defs)[s:e + 1]
        kd = _K(dRD)
        a = np.where(np.isfinite(dRD).sum(0) >= MIN_FRAMES, nanmean(kd, axis=0), 0.0)
        near = []
        for j in np.argsort(-a)[:3]:
            if a[j] <= 1e-3:
                continue
            p = defs_p[int(j)]
            near.append({"id": p.id, "name": p.name, "position": p.position, "peso_proximidad": float(a[j]),
                         "distancia_media_yd": float(np.nanmean(dRD[:, j])), "distancia_minima_yd": float(np.nanmin(dRD[:, j]))})
        result["receivers"].append({
            "id": rp.id, "name": rp.name, "position": rp.position, "dvi": dvi, "weight_coverage": cover,
            "components": [{"key": k, "label": COMPONENTS[k]["label"], "unit": COMPONENTS[k]["unit"],
                            "weight": COMPONENTS[k]["weight"], "ref": COMPONENTS[k]["ref"],
                            "raw": comps[k]["raw"], "normalized": comps[k]["norm"],
                            "note": comps[k].get("note"), "n_beneficiarios": comps[k].get("n_beneficiarios")}
                           for k in COMPONENTS],
            "series": series, "closest_defenders": near,
            "kinematics": kinematics(tr, r, s, e),
        })
    done = [r for r in result["receivers"] if r.get("dvi") is not None]
    result["available"] = bool(done)
    if not done:
        result["reason"] = "Ningún receptor tiene datos suficientes."
    result["receivers"].sort(key=lambda r: (r.get("dvi") is None, -(r.get("dvi") or 0)))
    return result
