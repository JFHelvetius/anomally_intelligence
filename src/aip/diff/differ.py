"""Comparador de Snapshots (ADR-0039 §propiedad central)."""

from __future__ import annotations

import dataclasses
import json
from typing import cast

from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.diff.models import DiffEntry, InvestigationDiff
from aip.snapshot.models import InvestigationSnapshot

# --------------------------------------------------------------------- compute


def compute_diff(
    snapshot_a: InvestigationSnapshot,
    snapshot_b: InvestigationSnapshot,
) -> InvestigationDiff:
    """Calcula el diff estructural entre dos snapshots por set-difference.

    Sólo presencia/ausencia de artefactos por su tripla
    (reference_type, identifier, artifact_hash). Cero orden subjetivo.
    """
    a_keys: set[tuple[str, str, str]] = {
        (r.reference_type, r.identifier, r.artifact_hash)
        for r in snapshot_a.referenced_artifacts
    }
    b_keys: set[tuple[str, str, str]] = {
        (r.reference_type, r.identifier, r.artifact_hash)
        for r in snapshot_b.referenced_artifacts
    }

    added = tuple(sorted(_make_entries(b_keys - a_keys)))
    removed = tuple(sorted(_make_entries(a_keys - b_keys)))
    unchanged = tuple(sorted(_make_entries(a_keys & b_keys)))

    partial = InvestigationDiff(
        snapshot_a_hash=snapshot_a.snapshot_hash,
        snapshot_b_hash=snapshot_b.snapshot_hash,
        added_artifacts=added,
        removed_artifacts=removed,
        unchanged_artifacts=unchanged,
        diff_hash="0" * 64,
    )
    final_hash = compute_diff_hash(partial)
    return dataclasses.replace(partial, diff_hash=final_hash)


def _make_entries(
    keys: set[tuple[str, str, str]],
) -> list[DiffEntry]:
    return [
        DiffEntry(
            reference_type=k[0], identifier=k[1], artifact_hash=k[2]
        )
        for k in keys
    ]


# --------------------------------------------------------------------- hashing


def compute_diff_hash(diff: InvestigationDiff) -> str:
    """SHA-256 hex de la canonicalización JCS del diff excluyendo
    el propio campo ``diff_hash``."""
    data = _diff_to_canonical_dict(diff)
    data.pop("diff_hash", None)
    normalized = cast(JsonValue, data)
    return sha256_hex(jcs_canonicalize(normalized))


def verify_diff(diff: InvestigationDiff) -> bool:
    """Verifica ``diff_hash`` offline."""
    return compute_diff_hash(diff) == diff.diff_hash


def _diff_to_canonical_dict(
    diff: InvestigationDiff,
) -> dict[str, object]:
    return {
        "snapshot_a_hash": diff.snapshot_a_hash,
        "snapshot_b_hash": diff.snapshot_b_hash,
        "added_artifacts": [_entry_dict(e) for e in diff.added_artifacts],
        "removed_artifacts": [
            _entry_dict(e) for e in diff.removed_artifacts
        ],
        "unchanged_artifacts": [
            _entry_dict(e) for e in diff.unchanged_artifacts
        ],
        "diff_hash": diff.diff_hash,
        "schema_version": diff.schema_version,
    }


def _entry_dict(e: DiffEntry) -> dict[str, str]:
    return {
        "reference_type": e.reference_type,
        "identifier": e.identifier,
        "artifact_hash": e.artifact_hash,
    }


# --------------------------------------------------------------------- encoding


def encode_diff(diff: InvestigationDiff) -> str:
    data = _diff_to_canonical_dict(diff)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def decode_diff(payload: str) -> InvestigationDiff:
    data = json.loads(payload)
    return InvestigationDiff(
        snapshot_a_hash=data["snapshot_a_hash"],
        snapshot_b_hash=data["snapshot_b_hash"],
        added_artifacts=tuple(
            DiffEntry(**e) for e in data.get("added_artifacts", [])
        ),
        removed_artifacts=tuple(
            DiffEntry(**e) for e in data.get("removed_artifacts", [])
        ),
        unchanged_artifacts=tuple(
            DiffEntry(**e) for e in data.get("unchanged_artifacts", [])
        ),
        diff_hash=data["diff_hash"],
        schema_version=data.get("schema_version", ""),
    )
