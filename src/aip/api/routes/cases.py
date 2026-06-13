"""GET /api/cases — investigation cases (workspaces joined with justifications/timelines)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep

router = APIRouter(tags=["cases"])


def _load_dir(d: Path) -> list[dict[str, Any]]:
    if not d.is_dir():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data.setdefault("_id", f.stem)
            results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


@router.get("/cases")
def list_cases(archive: ArchiveDep) -> list[dict]:
    workspaces = _load_dir(archive.root / "workspaces")
    justifications = _load_dir(archive.root / "justifications")
    timelines = _load_dir(archive.root / "timelines")

    just_by_ws: dict[str, dict] = {}
    for j in justifications:
        ws_id = j.get("workspace_id") or j.get("_id")
        if ws_id:
            just_by_ws[ws_id] = j

    tl_count_by_ws: dict[str, int] = {}
    for t in timelines:
        ws_id = t.get("workspace_id")
        if ws_id:
            tl_count_by_ws[ws_id] = tl_count_by_ws.get(ws_id, 0) + 1

    cases = []
    for ws in workspaces:
        ws_id = ws.get("workspace_id") or ws.get("_id", "")
        just = just_by_ws.get(ws_id)
        artifact_refs = ws.get("artifact_refs", [])

        cases.append({
            "id": ws_id,
            "description": ws.get("description") or ws.get("label"),
            "evidence_count": len(artifact_refs),
            "has_timeline": ws_id in tl_count_by_ws,
            "timeline_count": tl_count_by_ws.get(ws_id, 0),
            "conclusion": just.get("conclusion") if just else None,
            "justification_id": (just.get("justification_id") or just.get("_id")) if just else None,
            "created_at": ws.get("generated_at") or ws.get("created_at"),
            "updated_at": (
                (just.get("created_at") or just.get("generated_at"))
                if just
                else (ws.get("generated_at") or ws.get("created_at"))
            ),
        })

    return cases


@router.get("/cases/{case_id}")
def get_case(case_id: str, archive: ArchiveDep) -> dict:
    ws_path = archive.root / "workspaces" / f"{case_id}.json"
    if not ws_path.is_file():
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    try:
        ws = json.loads(ws_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Malformed workspace file.") from exc

    just_dir = archive.root / "justifications"
    justification = None
    if just_dir.is_dir():
        for f in just_dir.glob("*.json"):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
                if j.get("workspace_id") == case_id:
                    justification = j
                    break
            except (json.JSONDecodeError, OSError):
                continue

    return {
        "id": case_id,
        "workspace": ws,
        "justification": justification,
    }
