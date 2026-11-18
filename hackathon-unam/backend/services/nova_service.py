"""Explicación táctica opcional con Amazon Nova (Bedrock + Strands Agents + boto3).

Reglas: sin llaves en el código, sin verificar variables de credenciales, cliente creado solo con la
región. Si algo falla, se devuelve un mensaje claro y el resto de la plataforma sigue funcionando.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

SYSTEM_PROMPT = (
    "Eres un analista táctico de fútbol americano. Explicas en español, con claridad y prudencia, los resultados de "
    "un motor analítico llamado DECOY IQ. REGLAS: (1) usa SOLO las cifras del JSON recibido; no calcules ni inventes "
    "métricas, jugadores, rutas o eventos. (2) El DVI es un indicador experimental: no es probabilidad de éxito, no "
    "demuestra causalidad y no es métrica oficial de la NFL. (3) No afirmes qué miró un defensor: solo hay "
    "proximidad geométrica (atención defensiva potencial). (4) Distingue coincidencia espacial de causalidad. "
    "(5) Si un dato es nulo o no calculable, dilo. Estructura la respuesta con estos encabezados: "
    "Resumen táctico; Valor indirecto del receptor; Movimientos relevantes; Interpretación de indicadores; "
    "Limitaciones y advertencias."
)


def _settings() -> tuple[str, str]:
    return (os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
            os.environ.get("AWS_REGION", "us-east-1"))


def status() -> dict[str, Any]:
    model, region = _settings()
    return {"model_id": model, "region": region,
            "note": "La disponibilidad real se comprueba al solicitar una explicación; no se verifican credenciales manualmente."}


def _trim(dvi: dict, receiver_id: Optional[str]) -> dict:
    """Reduce el payload: serie temporal submuestreada y, si se pide, un solo receptor."""
    recs = dvi.get("receivers", [])
    if receiver_id:
        recs = [r for r in recs if r.get("id") == receiver_id]
    slim = []
    for r in recs:
        r = dict(r)
        series = r.get("series") or []
        step = max(len(series) // 12, 1)
        r["series"] = series[::step]
        slim.append(r)
    return {**{k: v for k, v in dvi.items() if k not in ("receivers", "notes")}, "receivers": slim}


def explain(context: dict[str, Any], dvi: dict[str, Any], receiver_id: Optional[str], question: Optional[str]) -> dict[str, Any]:
    model_id, region = _settings()
    payload = {
        "jugada": {k: context.get(k) for k in ("game_id", "play_id", "info", "events", "time", "notes")},
        "jugadores": [{k: p[k] for k in ("id", "name", "position", "side", "cls")} for p in context.get("players", [])],
        "dvi": _trim(dvi, receiver_id),
    }
    prompt = ("Datos calculados por el motor analítico (JSON):\n" + json.dumps(payload, ensure_ascii=False, default=str)
              + (f"\n\nEnfoque solicitado por el usuario: {question}" if question else "")
              + (f"\n\nCéntrate en el receptor con id {receiver_id}." if receiver_id else ""))
    base = {"model_id": model_id, "region": region}
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client("bedrock-runtime", region_name=region,
                              config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 1}))
        try:
            from strands import Agent
            from strands.models import BedrockModel

            model = BedrockModel(model_id=model_id, region_name=region, temperature=0.2, max_tokens=1200)
            agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)
            text = str(agent(prompt))
            via = "strands"
        except ImportError:
            resp = client.converse(modelId=model_id, system=[{"text": SYSTEM_PROMPT}],
                                   messages=[{"role": "user", "content": [{"text": prompt}]}],
                                   inferenceConfig={"maxTokens": 1200, "temperature": 0.2})
            text = resp["output"]["message"]["content"][0]["text"]
            via = "boto3"
        return {**base, "available": True, "via": via, "text": text}
    except Exception as exc:  # noqa: BLE001 - nunca propagar detalles sensibles
        name = type(exc).__name__
        hint = ("Amazon Bedrock no está configurado en este entorno (sin credenciales)."
                if "Credentials" in name else
                "No se pudo obtener la explicación de Amazon Nova. Verifica acceso al modelo y la región.")
        return {**base, "available": False, "error": f"{hint} [{name}]"}
