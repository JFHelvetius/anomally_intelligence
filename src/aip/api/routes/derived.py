"""GET /api/{workspaces,timelines,snapshots,justifications} — artefactos derivados."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from aip.api.deps import ArchiveDep

router = APIRouter(tags=["derived"])

_ARTIFACT_DIRS = {
    "workspaces": "workspaces",
    "timelines": "timelines",
    "snapshots": "snapshots",
    "justifications": "justifications",
}


def _list_artifacts(archive_root: Path, kind: str) -> list[dict]:
    d = archive_root / _ARTIFACT_DIRS[kind]
    if not d.is_dir():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entry: dict = {"id": f.stem}
            for key in (f"{kind[:-1]}_hash", f"{kind[:-1]}_id", "generated_at", "created_at"):
                if key in data:
                    entry[key] = data[key]
            results.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _get_artifact(archive_root: Path, kind: str, artifact_id: str) -> dict:
    path = archive_root / _ARTIFACT_DIRS[kind] / f"{artifact_id}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"{kind[:-1].capitalize()} '{artifact_id}' not found.",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Malformed artifact file.") from exc


@router.get("/workspaces")
def list_workspaces(archive: ArchiveDep) -> list[dict]:
    return _list_artifacts(archive.root, "workspaces")


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, archive: ArchiveDep) -> dict:
    return _get_artifact(archive.root, "workspaces", workspace_id)


@router.get("/timelines")
def list_timelines(archive: ArchiveDep) -> list[dict]:
    return _list_artifacts(archive.root, "timelines")


@router.get("/timelines/{timeline_id}")
def get_timeline(timeline_id: str, archive: ArchiveDep) -> dict:
    return _get_artifact(archive.root, "timelines", timeline_id)


@router.get("/snapshots")
def list_snapshots(archive: ArchiveDep) -> list[dict]:
    return _list_artifacts(archive.root, "snapshots")


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str, archive: ArchiveDep) -> dict:
    return _get_artifact(archive.root, "snapshots", snapshot_id)


@router.get("/justifications")
def list_justifications(archive: ArchiveDep) -> list[dict]:
    return _list_artifacts(archive.root, "justifications")


@router.get("/justifications/{justification_id}")
def get_justification(justification_id: str, archive: ArchiveDep) -> dict:
    return _get_artifact(archive.root, "justifications", justification_id)
