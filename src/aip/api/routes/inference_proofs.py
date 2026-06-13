"""GET /api/inference-proofs — read-only access a inference proofs persistidos."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep
from aip.justification.logic import INFERENCE_PROOFS_DIRNAME

router = APIRouter(tags=["inference-proofs"])


@router.get("/inference-proofs")
def list_inference_proofs(archive: ArchiveDep) -> list[dict[str, Any]]:
    """Listado resumido de todos los proofs en ``<archive>/inference-proofs/``."""
    d = archive.root / INFERENCE_PROOFS_DIRNAME
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(d.iterdir(), key=lambda p: p.name):
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "proof_id": data.get("proof_id"),
            "proof_hash": data.get("proof_hash"),
            "target_justification_id": data.get("target_justification_id"),
            "target_justification_hash": data.get("target_justification_hash"),
            "conclusion_claim_id": data.get("conclusion_claim_id"),
            "premise_count": len(data.get("premises", [])),
            "inference_count": len(data.get("inferences", [])),
            "derived_claim_count": len(data.get("derived_claims", [])),
        })
    return out


@router.get("/inference-proofs/{proof_id}")
def get_inference_proof(proof_id: str, archive: ArchiveDep) -> dict[str, Any]:
    """JSON completo del proof. 404 si no existe."""
    path = archive.root / INFERENCE_PROOFS_DIRNAME / f"{proof_id}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"inference proof {proof_id!r} not found",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"malformed proof file: {exc}",
        ) from exc
