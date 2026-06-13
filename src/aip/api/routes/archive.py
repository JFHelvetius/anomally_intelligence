"""GET /api/archive — estado e integridad del archive."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep
from aip.errors import AIPError
from aip.storage.layout import AUDIT_LOG_FILENAME, MANIFEST_FILENAME

router = APIRouter(prefix="/archive", tags=["archive"])


@router.get("/status")
def archive_status(archive: ArchiveDep) -> dict:
    manifest_path: Path = archive.root / MANIFEST_FILENAME
    audit_path: Path = archive.root / AUDIT_LOG_FILENAME

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None

    audit_entries = 0
    if audit_path.is_file():
        audit_entries = sum(1 for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip())

    return {
        "root": str(archive.root),
        "manifest_hash": manifest.get("manifest_hash") if manifest else None,
        "schema_version": manifest.get("schema_version") if manifest else None,
        "generated_at": manifest.get("generated_at") if manifest else None,
        "audit_entries": audit_entries,
    }


@router.get("/verify")
def archive_verify(archive: ArchiveDep) -> dict:
    try:
        report = archive.verify()
    except AIPError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ok": report.ok,
        "checks": [
            {"name": c.name, "ok": c.ok, "detail": c.detail}
            for c in report.checks
        ],
    }
