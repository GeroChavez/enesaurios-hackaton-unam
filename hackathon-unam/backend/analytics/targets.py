"""Inferencia del receptor objetivo a partir de la descripción de la jugada (sin pandas).

La tabla de jugadas del dataset no trae el receptor objetivo, pero la descripción lo nombra
("... pass incomplete deep right to C.Godwin."). Se compara contra los corredores de ruta de ESA
jugada; solo se acepta una coincidencia única. Es una inferencia por nombre, no un campo oficial.
"""
from __future__ import annotations

import re
from typing import Optional

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _letters(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def name_keys(display_name: str) -> set[str]:
    toks = [t for t in display_name.replace(",", " ").split() if t]
    while len(toks) > 1 and _letters(toks[-1]) in SUFFIXES:
        toks.pop()
    if len(toks) < 2:
        return set()
    first, last = toks[0], _letters("".join(toks[1:]))
    keys = {_letters(first)[:1] + last}
    if "." in first:  # iniciales tipo D.J.
        keys.add(_letters(first) + last)
    return {k for k in keys if len(k) > 2}


def infer_target(description: Optional[str], candidates: dict[str, str]) -> Optional[str]:
    """candidates: {id: displayName}. Devuelve el id si hay exactamente una coincidencia."""
    if not description:
        return None
    text = _letters(description)
    hits = [pid for pid, name in candidates.items()
            if any((p + k) in text for k in name_keys(name) for p in ("to", "intendedfor"))]
    return hits[0] if len(hits) == 1 else None
