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
MIN_RECEIVER_DISP = 2.0   # yd: desplazamiento neto mínimo para definir la dirección de la ruta

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
        label="Arrastre defensivo (seguimiento)", unit="yd", ref=4.0, weight=0.25,
        formula="u = (P_R(e) - P_R(s)) / ||P_R(e) - P_R(s)||;  p_j = (P_j(e) - P_j(s)) · u;  "
                "A = sum_j a_j p_j / sum_j a_j  -  media_j p_j;  c2 = clip(A / 4, 0, 1)",
        measures="Cuánto más se desplazaron los defensores cercanos al receptor en la dirección de la ruta del receptor "
                 "que el defensor promedio (control del movimiento defensivo general). Requiere que R se desplace ≥ 2 yd.",
        limitation="No usa al objetivo ni al balón (evita solaparse con el espacio para el objetivo). Mide coincidencia de "
                   "movimiento: un defensor que baja por su cobertura asignada también aparece como «seguimiento».",
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
        "calibracion": "NINGÚN parámetro está calibrado con datos: σ, los pesos, las saturaciones y el desplazamiento mínimo son "
                       "decisiones del equipo, fijadas a priori para que la escala sea comparable entre jugadas. No se ha "
                       "validado el DVI contra resultados de jugadas ni contra expertos.",
        "observado_vs_inferido": "Observado: posiciones, eventos, roles PFF. Inferido: el receptor objetivo (nombre en la descripción). "
                                 "El DVI depende del objetivo en el componente de espacio para el objetivo y en la lista de beneficiarios.",
        "ventana": "Desde el snap hasta el lanzamiento. Solo se calcula con snap, lanzamiento y receptor objetivo identificados; si falta alguno, la jugada es «no calculable» y se informa el motivo.",
        "componentes": [{"key": k, **{kk: vv for kk, vv in v.items()}} for k, v in COMPONENTS.items()],
        "pesos": "Pesos fijados por criterio del equipo (no ajustados con datos): el espacio liberado para el objetivo "
                 "pesa más porque es el efecto táctico más directo; proximidad y arrastre son indicios de interacción; "
                 "el espacio para otros compañeros es secundario. Las saturaciones (ref) son referencias fijas para "
                 "que la escala sea comparable entre jugadas, no percentiles de la liga.",
        "doble_conteo": "PDP usa solo distancias R-defensor; Arrastre usa la proyección del desplazamiento defensivo sobre la ruta de R "
                        "(sin objetivo ni balón); los componentes de espacio miden la distancia defensor-beneficiario para "
                        "beneficiarios disjuntos (objetivo / otros). Persiste una correlación esperable porque los cuatro dependen "
                        "de las posiciones de los mismos defensores y a_j se reutiliza como peso; no se ha cuantificado.",
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
    """Zona de referencia Z: punto aproximado de llegada del balón (en orden de preferencia)."""
    b = tr.ball_idx
    if tr.ball_land is not None:
        return tr.ball_land, tr.ball_land_source or "columnas de aterrizaje del balón"
    if b is not None and tr.arrival_idx is not None:
        x, y = tr.X[tr.arrival_idx, b], tr.Y[tr.arrival_idx, b]
        if np.isfinite(x) and np.isfinite(y):
            return (float(x), float(y)), "posición del balón en el evento de llegada del pase"
    if b is not None and t_idx is not None and tr.throw_idx is not None:
        d = np.hypot(tr.X[tr.throw_idx:, b] - tr.X[tr.throw_idx:, t_idx], tr.Y[tr.throw_idx:, b] - tr.Y[tr.throw_idx:, t_idx])
        if np.isfinite(d).any():
            k = tr.throw_idx + int(np.nanargmin(d))
            return ((float(tr.X[k, b]), float(tr.Y[k, b])),
                    f"posición del balón en el cuadro de menor distancia al objetivo tras el lanzamiento "
                    f"({float(np.nanmin(d)):.1f} yd); aproximación porque no hay evento de llegada")
    if t_idx is not None:
        x, y = tr.X[e, t_idx], tr.Y[e, t_idx]
        if np.isfinite(x) and np.isfinite(y):
            return (float(x), float(y)), "posición del receptor objetivo al final de la ventana (aproximación débil: sin trayectoria del balón)"
    return None, "no disponible"


def _components_at(tr: Tracks, r: int, t_idx: Optional[int], defs: list[int], others: list[int],
                   s: int, e: int) -> dict[str, dict]:
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

    # arrastre / seguimiento: proyección del desplazamiento defensivo sobre la dirección de la ruta de R
    rx, ry = tr.X[e, r] - tr.X[s, r], tr.Y[e, r] - tr.Y[s, r]
    rn = float(np.hypot(rx, ry))
    if rn >= MIN_RECEIVER_DISP and len(defs) >= 2:
        ux, uy = rx / rn, ry / rn
        proj = (tr.X[e, defs] - tr.X[s, defs]) * ux + (tr.Y[e, defs] - tr.Y[s, defs]) * uy
        ok = np.isfinite(proj)
        if ok.sum() >= 2:
            w = a0[ok]
            if w.sum() < 1e-6:
                raw, note = 0.0, "Ningún defensor estuvo cerca del receptor."
            else:
                raw, note = float(np.sum(w * proj[ok]) / w.sum() - np.mean(proj[ok])), None
            out["arrastre"] = {"raw": raw, "norm": float(np.clip(raw / COMPONENTS["arrastre"]["ref"], 0, 1)),
                               **({"note": note} if note else {})}
    out.setdefault("arrastre", {"raw": None, "norm": None,
                                "note": f"El receptor se desplazó menos de {MIN_RECEIVER_DISP:.0f} yd: sin dirección de ruta."})

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
                   "arrival_frame": int(tr.frames[tr.arrival_idx]) if tr.arrival_idx is not None else None,
                   "start_source": tr.start_source},
        "parameters": {"sigma_yd": SIGMA, "min_frames": MIN_FRAMES},
        "target_id": target.id if target else None, "receivers": [], "warnings": [],
    }
    if target is None or tr.throw_idx is None:
        result["reason"] = ("No hay receptor objetivo identificado." if target is None else
                            "No se identificó el lanzamiento (jugada sin pase, sack o scramble).")
        return result
    if tr.start_source != "evento de snap":
        result["reason"] = "No hay evento de snap: no se puede delimitar la ventana de análisis."
        return result
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
    if result["target_inferred"]:
        result["warnings"].append("El receptor objetivo es una INFERENCIA (nombre en la descripción de la jugada), no un dato oficial.")

    zone, zone_src = _zone(tr, t_idx, e)
    result["zone"] = {"x": zone[0], "y": zone[1]} if zone else None
    result["zone_source"] = zone_src + " · solo visualización: NO entra al cálculo del DVI"
    result["target_inferred"] = "inferido" in target.basis
    result["target_basis"] = target.basis

    for rp in recvs:
        r = tr.col(rp.id)
        valid = np.where(np.isfinite(tr.X[s0:e + 1, r]) & np.isfinite(tr.Y[s0:e + 1, r]))[0]
        if len(valid) < MIN_FRAMES:
            result["receivers"].append({"id": rp.id, "name": rp.name, "position": rp.position, "dvi": None,
                                        "reason": "Receptor con datos insuficientes en la ventana."})
            continue
        s = s0 + int(valid[0])
        others = [tr.col(p.id) for p in recvs if p.id != rp.id]
        comps = _components_at(tr, r, t_idx, defs, others, s, e)
        dvi, cover = _combine(comps)

        series = []
        for ee in range(s + MIN_FRAMES - 1, e + 1):
            c = _components_at(tr, r, t_idx, defs, others, s, ee)
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
