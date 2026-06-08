"""Constructor, persistencia y verificación de Snapshots (ADR-0038)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from aip._version import SCHEMA_VERSION
from aip.audit import log as audit_log
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.errors import AIPError
from aip.snapshot.models import (
    InvestigationSnapshot,
    SnapshotReference,
)
from aip.storage.atomic_io import atomic_write_text
from aip.timeline.models import InvestigationTimeline
from aip.workspace.models import InvestigationWorkspace

SNAPSHOTS_DIRNAME: str = "snapshots"


class SnapshotNotFoundError(AIPError):
    """Snapshot solicitado no existe bajo ``<archive>/snapshots/``."""

    cli_exit_code = 1


# --------------------------------------------------------------------- create


def create_snapshot(
    *,
    snapshot_id: str,
    workspace: InvestigationWorkspace,
    timeline: InvestigationTimeline,
) -> InvestigationSnapshot:
    """Construye un :class:`InvestigationSnapshot` determinista.

    Sólo agrupa referencias del workspace y los hashes de identidad. **No
    copia payloads. No ejecuta motores** (ADR-0038 §propiedad).
    """
    refs = tuple(
        sorted(
            SnapshotReference(
                reference_type=r.reference_type,
                identifier=r.identifier,
                artifact_hash=r.artifact_hash,
            )
            for r in workspace.references
        )
    )
    partial = InvestigationSnapshot(
        snapshot_id=snapshot_id,
        workspace_hash=workspace.workspace_hash,
        timeline_hash=timeline.timeline_hash,
        referenced_artifacts=refs,
        snapshot_hash="0" * 64,
    )
    final_hash = compute_snapshot_hash(partial)
    return dataclasses.replace(partial, snapshot_hash=final_hash)


# --------------------------------------------------------------------- hashing


def compute_snapshot_hash(snapshot: InvestigationSnapshot) -> str:
    """SHA-256 hex de la canonicalización JCS del snapshot excluyendo
    el propio campo ``snapshot_hash``."""
    data = _snapshot_to_canonical_dict(snapshot)
    data.pop("snapshot_hash", None)
    normalized = cast(JsonValue, data)
    return sha256_hex(jcs_canonicalize(normalized))


def verify_snapshot(snapshot: InvestigationSnapshot) -> bool:
    """Verifica ``snapshot_hash`` offline."""
    return compute_snapshot_hash(snapshot) == snapshot.snapshot_hash


def _snapshot_to_canonical_dict(
    snapshot: InvestigationSnapshot,
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "workspace_hash": snapshot.workspace_hash,
        "timeline_hash": snapshot.timeline_hash,
        "referenced_artifacts": [
            {
                "reference_type": r.reference_type,
                "identifier": r.identifier,
                "artifact_hash": r.artifact_hash,
            }
            for r in snapshot.referenced_artifacts
        ],
        "snapshot_hash": snapshot.snapshot_hash,
        "schema_version": snapshot.schema_version,
    }


# --------------------------------------------------------------------- persistence


def snapshot_path(archive_root: Path, snapshot_id: str) -> Path:
    return archive_root / SNAPSHOTS_DIRNAME / f"{snapshot_id}.json"


def persist_snapshot(
    snapshot: InvestigationSnapshot,
    *,
    archive_root: Path,
    actor: str,
    clock: Callable[[], dt.datetime],
    extra_output: Path | None = None,
) -> Path:
    """Persiste el snapshot y emite ``BUILD_SNAPSHOT`` al audit log
    (ADR-0019 §enmienda E1)."""
    target = snapshot_path(archive_root, snapshot.snapshot_id)
    payload = encode_snapshot(snapshot)
    atomic_write_text(target, payload)
    if extra_output is not None:
        atomic_write_text(extra_output, payload)
    audit_log.record_derived_artifact(
        archive_root,
        action=audit_log.ActionKind.BUILD_SNAPSHOT,
        artifact_kind="snapshot",
        artifact_id=snapshot.snapshot_id,
        self_hash=snapshot.snapshot_hash,
        actor=actor,
        clock=clock,
        schema_version=SCHEMA_VERSION,
    )
    return target


def load_snapshot(
    *, archive_root: Path, snapshot_id: str
) -> InvestigationSnapshot:
    target = snapshot_path(archive_root, snapshot_id)
    if not target.is_file():
        raise SnapshotNotFoundError(
            f"snapshot {snapshot_id!r} not found at {target}."
        )
    return decode_snapshot(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- encoding


def encode_snapshot(snapshot: InvestigationSnapshot) -> str:
    data = _snapshot_to_canonical_dict(snapshot)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def decode_snapshot(payload: str) -> InvestigationSnapshot:
    data = json.loads(payload)
    refs = tuple(
        SnapshotReference(
            reference_type=r["reference_type"],
            identifier=r["identifier"],
            artifact_hash=r["artifact_hash"],
        )
        for r in data.get("referenced_artifacts", [])
    )
    return InvestigationSnapshot(
        snapshot_id=data["snapshot_id"],
        workspace_hash=data["workspace_hash"],
        timeline_hash=data["timeline_hash"],
        referenced_artifacts=refs,
        snapshot_hash=data["snapshot_hash"],
        schema_version=data.get("schema_version", ""),
    )
