"""GET /api/attestations — lista y detalle de atestaciones."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep

router = APIRouter(prefix="/attestations", tags=["attestations"])

_ATTESTATIONS_DIR = "attestations"


def _attestations_dir(archive_root: Path) -> Path:
    return archive_root / _ATTESTATIONS_DIR


@router.get("")
def list_attestations(archive: ArchiveDep) -> list[dict]:
    d = _attestations_dir(archive.root)
    if not d.is_dir():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "id": f.stem,
                "artifact_kind": data.get("artifact_kind"),
                "signer_id": data.get("signer_id"),
                "signed_at": data.get("signed_at"),
                "attestation_hash": data.get("attestation_hash"),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return results


@router.get("/{attestation_id}")
def get_attestation(attestation_id: str, archive: ArchiveDep) -> dict:
    path = _attestations_dir(archive.root) / f"{attestation_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Attestation '{attestation_id}' not found.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Malformed attestation file.") from exc
