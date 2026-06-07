"""Comparador de Justificaciones (ADR-0040 §CLI diff justifications).

Set-difference puro sobre las cinco categorías de la cadena. Cero
"mejor"/"peor", cero ponderación.
"""

from __future__ import annotations

import dataclasses
import json
from typing import cast

from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.justification.models import (
    ChainEntry,
    InvestigationJustification,
    JustificationDiff,
)

# --------------------------------------------------------------------- compute


def compute_justification_diff(
    a: InvestigationJustification,
    b: InvestigationJustification,
) -> JustificationDiff:
    """Set-difference puro entre dos justificaciones.

    Compara todas las entries (todas las categorías combinadas) por su
    tripla canónica ``(entry_role, entry_identifier, entry_hash)``.
    """
    a_keys: set[tuple[str, str, str]] = _collect_entry_keys(a)
    b_keys: set[tuple[str, str, str]] = _collect_entry_keys(b)

    added = tuple(sorted(_keys_to_entries(b_keys - a_keys)))
    removed = tuple(sorted(_keys_to_entries(a_keys - b_keys)))
    unchanged = tuple(sorted(_keys_to_entries(a_keys & b_keys)))

    partial = JustificationDiff(
        justification_a_hash=a.justification_hash,
        justification_b_hash=b.justification_hash,
        added_entries=added,
        removed_entries=removed,
        unchanged_entries=unchanged,
        diff_hash="0" * 64,
    )
    final_hash = compute_justification_diff_hash(partial)
    return dataclasses.replace(partial, diff_hash=final_hash)


def _collect_entry_keys(
    j: InvestigationJustification,
) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for category in (
        j.minimal_evidence,
        j.supporting_assessments,
        j.graph_nodes_used,
        j.intermediate_artifacts,
        j.provenance_chain,
    ):
        for e in category:
            out.add((e.entry_role, e.entry_identifier, e.entry_hash))
    return out


def _keys_to_entries(
    keys: set[tuple[str, str, str]],
) -> list[ChainEntry]:
    return [
        ChainEntry(
            entry_role=k[0], entry_identifier=k[1], entry_hash=k[2]
        )
        for k in keys
    ]


# --------------------------------------------------------------------- hashing


def compute_justification_diff_hash(d: JustificationDiff) -> str:
    data = _diff_to_canonical_dict(d)
    data.pop("diff_hash", None)
    normalized = cast(JsonValue, data)
    return sha256_hex(jcs_canonicalize(normalized))


def verify_justification_diff(d: JustificationDiff) -> bool:
    return compute_justification_diff_hash(d) == d.diff_hash


def _diff_to_canonical_dict(d: JustificationDiff) -> dict[str, object]:
    return {
        "justification_a_hash": d.justification_a_hash,
        "justification_b_hash": d.justification_b_hash,
        "added_entries": [_entry_dict(e) for e in d.added_entries],
        "removed_entries": [_entry_dict(e) for e in d.removed_entries],
        "unchanged_entries": [
            _entry_dict(e) for e in d.unchanged_entries
        ],
        "diff_hash": d.diff_hash,
        "schema_version": d.schema_version,
    }


def _entry_dict(e: ChainEntry) -> dict[str, str]:
    return {
        "entry_role": e.entry_role,
        "entry_identifier": e.entry_identifier,
        "entry_hash": e.entry_hash,
    }


# --------------------------------------------------------------------- encoding


def encode_justification_diff(d: JustificationDiff) -> str:
    data = _diff_to_canonical_dict(d)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def decode_justification_diff(payload: str) -> JustificationDiff:
    data = json.loads(payload)
    return JustificationDiff(
        justification_a_hash=data["justification_a_hash"],
        justification_b_hash=data["justification_b_hash"],
        added_entries=_decode_entries(data.get("added_entries", [])),
        removed_entries=_decode_entries(data.get("removed_entries", [])),
        unchanged_entries=_decode_entries(
            data.get("unchanged_entries", [])
        ),
        diff_hash=data["diff_hash"],
        schema_version=data.get("schema_version", ""),
    )


def _decode_entries(raw: list[dict[str, str]]) -> tuple[ChainEntry, ...]:
    return tuple(
        ChainEntry(
            entry_role=e["entry_role"],
            entry_identifier=e["entry_identifier"],
            entry_hash=e["entry_hash"],
        )
        for e in raw
    )
