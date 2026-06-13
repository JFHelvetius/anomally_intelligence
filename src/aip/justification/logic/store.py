"""Encode/decode + paths para :class:`InferenceProof`.

Storage layout (cuando el operador decide persistir un proof junto al archive):

    <archive>/inference-proofs/<proof_id>.json

Convención: ``proof_id`` típicamente coincide con el ``justification_id`` que
prueba, pero no es obligatorio — un proof distinto podría atestar la misma
justification (e.g., un re-análisis con razonamiento alternativo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from aip.errors import AIPError
from aip.justification.logic.models import (
    DerivedClaim,
    InferenceProof,
    InferenceStep,
    Premise,
)

INFERENCE_PROOFS_DIRNAME: Final[str] = "inference-proofs"


class InferenceProofError(AIPError):
    cli_exit_code = 1


def encode_proof(proof: InferenceProof) -> str:
    """JSON canónico (sorted keys, indent=2). El hash canónico está
    fijado por ``proof_hash`` JCS — este formato es de presentación."""
    data = {
        "proof_type": proof.proof_type,
        "schema_version": proof.schema_version,
        "proof_id": proof.proof_id,
        "target_justification_id": proof.target_justification_id,
        "target_justification_hash": proof.target_justification_hash,
        "premises": [
            {
                "id": p.id,
                "text": p.text,
                "evidence_refs": list(p.evidence_refs),
                "kind": p.kind,
            }
            for p in proof.premises
        ],
        "inferences": [
            {
                "id": i.id,
                "rule": i.rule,
                "input_claim_ids": list(i.input_claim_ids),
                "output_claim_id": i.output_claim_id,
                "text": i.text,
            }
            for i in proof.inferences
        ],
        "derived_claims": [
            {"id": c.id, "text": c.text, "inferred_by": c.inferred_by}
            for c in proof.derived_claims
        ],
        "conclusion_claim_id": proof.conclusion_claim_id,
        "proof_hash": proof.proof_hash,
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def decode_proof(payload: str) -> InferenceProof:
    data = json.loads(payload)
    return InferenceProof(
        proof_type=data["proof_type"],
        schema_version=data.get("schema_version", "1"),
        proof_id=data["proof_id"],
        target_justification_id=data["target_justification_id"],
        target_justification_hash=data["target_justification_hash"],
        premises=tuple(
            Premise(
                id=p["id"],
                text=p["text"],
                evidence_refs=tuple(p.get("evidence_refs", [])),
                kind=p["kind"],
            )
            for p in data.get("premises", [])
        ),
        inferences=tuple(
            InferenceStep(
                id=i["id"],
                rule=i["rule"],
                input_claim_ids=tuple(i["input_claim_ids"]),
                output_claim_id=i["output_claim_id"],
                text=i["text"],
            )
            for i in data.get("inferences", [])
        ),
        derived_claims=tuple(
            DerivedClaim(
                id=c["id"],
                text=c["text"],
                inferred_by=c["inferred_by"],
            )
            for c in data.get("derived_claims", [])
        ),
        conclusion_claim_id=data["conclusion_claim_id"],
        proof_hash=data["proof_hash"],
    )


def proof_path(archive_root: Path, proof_id: str) -> Path:
    return archive_root / INFERENCE_PROOFS_DIRNAME / f"{proof_id}.json"


def load_proof(archive_root: Path, proof_id: str) -> InferenceProof:
    target = proof_path(archive_root, proof_id)
    if not target.is_file():
        raise InferenceProofError(
            f"inference proof {proof_id!r} not found at {target}."
        )
    return decode_proof(target.read_text(encoding="utf-8"))
