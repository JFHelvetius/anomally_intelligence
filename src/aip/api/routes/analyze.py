"""POST /api/analyze/image — Claude Vision anomaly analysis (Phase B)."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["analyze"])

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MODEL = "claude-sonnet-4-6"

_SYSTEM = """\
You are a scientific visual analyst for the Anomaly Intelligence Platform (AIP), \
specializing in UAP (Unidentified Aerial Phenomena) and anomaly investigation.

Analyze the provided image rigorously and objectively. \
Base ALL findings strictly on visual evidence — do not speculate beyond what is shown.

Focus on:
1. All identifiable objects, shapes, and phenomena in the image.
2. Visual anomalies: unusual luminosity, shape irregularities, motion blur, lens artifacts, atmospheric effects.
3. Conventional explanations for each element (aircraft, birds, balloons, stars, drones, weather, reflections, etc.).
4. Image quality and conditions that affect confidence.

CONSTRAINTS:
- Default to "indeterminate" when evidence is insufficient.
- Distinguish between image artifacts and actual objects in the scene.
- Do not invent detail not present in the image.

Respond ONLY with valid JSON, no markdown fences, no extra text. Schema:
{
  "overall_assessment": "anomalous" | "conventional" | "indeterminate",
  "confidence": "high" | "medium" | "low",
  "image_quality": "good" | "fair" | "poor",
  "objects_detected": [
    {
      "description": "string",
      "is_anomalous": boolean,
      "conventional_match": "string or null",
      "location_in_image": "string"
    }
  ],
  "anomalies": [
    {
      "type": "shape | luminosity | motion | atmospheric | artifact | unknown",
      "description": "string",
      "severity": "high | medium | low"
    }
  ],
  "conventional_explanations": ["string"],
  "analysis_notes": "string",
  "recommended_classification": "explained | unexplained | indeterminate | contaminated",
  "recommended_investigation_steps": ["string"],
  "analyst_caveat": "string"
}"""

_USER = "Analyze this image for UAP phenomena and visual anomalies. Return ONLY the JSON object."


@router.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY no está configurada. "
                "Inicia aip-web con: set ANTHROPIC_API_KEY=sk-ant-... && aip-web"
            ),
        )

    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="anthropic no está instalado. Ejecuta: pip install anthropic",
        ) from exc

    content = await file.read()

    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="Imagen demasiado grande (máximo 5 MB).")

    media_type = (file.content_type or "image/jpeg").split(";")[0].strip()
    if media_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no soportado: {media_type}. Usa JPEG, PNG, GIF o WebP.",
        )

    b64 = base64.standard_b64encode(content).decode()

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {"type": "text", "text": _USER},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de Claude API: {exc}") from exc

    raw = response.content[0].text.strip()
    # Strip markdown fences if model added them
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].strip()

    try:
        analysis: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        analysis = {"raw_response": raw, "parse_error": "La respuesta no es JSON válido."}

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "media_type": media_type,
        "model": response.model,
        "analysis": analysis,
    }
