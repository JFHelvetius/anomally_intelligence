"""GET /api/audit-log — entradas del audit log."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query

from aip.api.deps import ArchiveDep
from aip.storage.layout import AUDIT_LOG_FILENAME

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("")
def list_audit_entries(
    archive: ArchiveDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    path: Path = archive.root / AUDIT_LOG_FILENAME
    if not path.is_file():
        return {"total": 0, "entries": []}

    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    total = len(lines)
    page = lines[offset: offset + limit]

    entries = []
    for line in page:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"total": total, "entries": entries}
