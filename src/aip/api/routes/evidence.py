"""GET /api/evidence — lista y detalle de evidencia."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep
from aip.archive import CAPTURE_CERTIFICATES_DIRNAME
from aip.audit import log as audit_log
from aip.core.provenance import ProvenanceStep
from aip.errors import AIPError, EvidenceNotFoundError
from aip.justification.logic.store import INFERENCE_PROOFS_DIRNAME
from aip.storage import tables
from aip.transparency.store import list_sequences, manifest_path

router = APIRouter(prefix="/evidence", tags=["evidence"])


def _find_capture_cert_hash(steps: tuple[ProvenanceStep, ...]) -> str | None:
    """Busca el primer ``capture_certificate_hash`` declarado en los parameters
    de cualquier step. Phase 2 lo emite siempre en el step 1 (ORIGINAL_CAPTURE)
    cuando se ingestó con ``--capture-cert``."""
    for st in steps:
        if st.parameters and "capture_certificate_hash" in st.parameters:
            return st.parameters["capture_certificate_hash"]
    return None


def _find_audit_entry_for_evidence(
    archive_root: Path, evidence_hash: str
) -> dict[str, Any] | None:
    """Walk audit.log para encontrar el INGEST_EVIDENCE entry de este hash.

    Devuelve dict con ``seq``, ``timestamp``, ``actor``, ``entry_hash`` y
    ``parameters`` si lo encuentra; ``None`` si no.
    """
    target_uri = f"aip:evidence/sha256:{evidence_hash}"
    for entry in audit_log.iter_entries(archive_root):
        if (
            entry.action == audit_log.ActionKind.INGEST_EVIDENCE
            and entry.target == target_uri
        ):
            return {
                "seq": entry.seq,
                "timestamp": entry.timestamp.isoformat(),
                "actor": entry.actor,
                "entry_hash": entry.entry_hash,
                "parameters": dict(entry.parameters),
            }
    return None


def _coverage_manifests(
    archive_root: Path, evidence_audit_seq: int
) -> list[dict[str, Any]]:
    """Manifests cuyo ``audit_entry_count`` cubre el seq de esta evidencia.

    Regla: manifest M cubre evidencia con seq=N si M.audit_entry_count > N
    (porque audit_entry_count = total entries hasta el momento de firma; si
    es > N, todas las entries 0..N están incluidas en M.audit_chain_head_hash).
    """
    out: list[dict[str, Any]] = []
    for seq in list_sequences(archive_root):
        path = manifest_path(archive_root, seq)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("audit_entry_count", 0) > evidence_audit_seq:
            out.append({
                "sequence": data["sequence"],
                "manifest_hash": data["manifest_hash"],
                "signed_at": data["signed_at"],
                "operator_id": data["operator_id"],
                "public_key_fingerprint": data["public_key_fingerprint"],
                "audit_entry_count": data["audit_entry_count"],
                "audit_chain_head_hash": data["audit_chain_head_hash"],
            })
    return out


_ABDUCTION_RULE = "abduction_to_best_explanation"


def _inference_proofs_referencing(
    archive_root: Path, evidence_hash: str
) -> list[dict[str, Any]]:
    """Scan ``<archive>/inference-proofs/*.json`` por proofs que tengan este
    hash en ``premises[].evidence_refs``."""
    d = archive_root / INFERENCE_PROOFS_DIRNAME
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
        matched_premise_id: str | None = None
        for p in data.get("premises", []):
            if evidence_hash in p.get("evidence_refs", []):
                matched_premise_id = p.get("id")
                break
        if matched_premise_id is None:
            continue
        weak_count = sum(
            1
            for i in data.get("inferences", [])
            if i.get("rule") == _ABDUCTION_RULE
        )
        out.append({
            "proof_id": data.get("proof_id"),
            "proof_hash": data.get("proof_hash"),
            "target_justification_id": data.get("target_justification_id"),
            "target_justification_hash": data.get("target_justification_hash"),
            "conclusion_claim_id": data.get("conclusion_claim_id"),
            "matched_premise_id": matched_premise_id,
            "inference_count": len(data.get("inferences", [])),
            "weak_inference_count": weak_count,
        })
    return out


def _load_capture_certificate(archive_root: Path, cert_hash: str) -> dict[str, Any] | None:
    """Lee el sidecar ``<archive>/capture-certificates/<cert_hash>.json``.

    Devuelve ``None`` si el fichero no existe o está malformado — el caller
    decide si eso es un problema o si simplemente no hay cert publicado.
    """
    target = archive_root / CAPTURE_CERTIFICATES_DIRNAME / f"{cert_hash}.json"
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@router.get("")
def list_evidence(archive: ArchiveDep) -> list[dict]:
    rows = list(tables.iter_rows(archive.root, "evidence"))
    return [
        {
            "hash": r.get("hash"),
            "kind": r.get("kind"),
            "mime_type": r.get("mime_type"),
            "size_bytes": r.get("size_bytes"),
            "ingested_at": r.get("ingested_at"),
            "ingested_by": r.get("ingested_by"),
            "source_id": r.get("source_id"),
        }
        for r in rows
        if isinstance(r, dict)
    ]


@router.get("/{evidence_hash}")
def get_evidence(evidence_hash: str, archive: ArchiveDep) -> dict:
    try:
        view = archive.show_evidence(evidence_hash)
    except EvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIPError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    e = view.evidence
    s = view.source
    p = view.provenance

    # Capture certificate (Phase 2 integration). Inline when available so el
    # frontend muestra origen firmado sin un round-trip extra.
    cert_hash = _find_capture_cert_hash(view.provenance_steps)
    capture_certificate = (
        _load_capture_certificate(archive.root, cert_hash) if cert_hash else None
    )

    # Trust Timeline data (Phase Trust Timeline). Recolecta:
    # - audit entry de esta evidencia (seq + timestamp)
    # - manifests de transparency que cubren ese audit seq
    # - inference proofs que referencian esta evidencia en sus premises
    audit_entry = _find_audit_entry_for_evidence(archive.root, evidence_hash)
    coverage_manifests = (
        _coverage_manifests(archive.root, audit_entry["seq"])
        if audit_entry is not None
        else []
    )
    proofs_referencing = _inference_proofs_referencing(archive.root, evidence_hash)

    return {
        "evidence": {
            "hash": e.hash,
            "kind": e.kind.value,
            "mime_type": e.mime_type,
            "size_bytes": e.size_bytes,
            "content_uri": e.content_uri,
            "ingested_at": e.ingested_at.isoformat(),
            "ingested_by": e.ingested_by,
            "source_id": e.source_id,
            "notes": e.notes,
            "status": e.status.value,
        },
        "source": {
            "id": s.id,
            "name": s.name,
            "kind": s.kind.value,
            "authority_level": s.authority.value,
            "jurisdiction": s.jurisdiction,
            "license": s.license,
        },
        "provenance": {
            "evidence_hash": p.evidence_hash,
            "gaps": [g.description for g in p.gaps],
            "steps": [
                {
                    "step_index": st.step_id,
                    "kind": st.kind.value,
                    "actor": st.actor,
                    "description": st.notes,
                    "timestamp": st.timestamp.isoformat() if st.timestamp else None,
                    "parameters": dict(st.parameters),
                }
                for st in view.provenance_steps
            ],
        },
        "capture_certificate": capture_certificate,
        "audit_entry": audit_entry,
        "coverage_manifests": coverage_manifests,
        "inference_proofs_referencing": proofs_referencing,
        "derived_assessments": [
            {
                "method": a.method.value,
                "status": a.status.value,
                "assessed_at": a.assessed_at.isoformat(),
                "assessed_by": a.assessed_by,
            }
            for a in view.derived_assessments
        ],
    }
