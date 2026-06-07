"""Modelos del Diff Engine (ADR-0039 §modelo)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

DIFF_SCHEMA_VERSION: Final[str] = "1"

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, order=True)
class DiffEntry:
    """Entrada del diff: referencia presente en una/ambas snapshots."""

    reference_type: str
    identifier: str
    artifact_hash: str

    def __post_init__(self) -> None:
        if not self.reference_type:
            raise ValueError("reference_type must be non-empty.")
        if not self.identifier:
            raise ValueError("identifier must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.artifact_hash):
            raise ValueError("artifact_hash must be SHA-256 hex lowercase.")


@dataclass(frozen=True)
class InvestigationDiff:
    """Diff canónico entre dos snapshots (ADR-0039 §modelo).

    Cero campos de "mejora", "regresión", "importancia". Sólo presencia
    estructural.
    """

    snapshot_a_hash: str
    snapshot_b_hash: str
    added_artifacts: tuple[DiffEntry, ...]
    removed_artifacts: tuple[DiffEntry, ...]
    unchanged_artifacts: tuple[DiffEntry, ...]
    diff_hash: str
    schema_version: str = DIFF_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _SHA256_HEX_PATTERN.match(self.snapshot_a_hash):
            raise ValueError("snapshot_a_hash must be SHA-256 hex lowercase.")
        if not _SHA256_HEX_PATTERN.match(self.snapshot_b_hash):
            raise ValueError("snapshot_b_hash must be SHA-256 hex lowercase.")
        if not _SHA256_HEX_PATTERN.match(self.diff_hash):
            raise ValueError("diff_hash must be SHA-256 hex lowercase.")
        for name, group in (
            ("added_artifacts", self.added_artifacts),
            ("removed_artifacts", self.removed_artifacts),
            ("unchanged_artifacts", self.unchanged_artifacts),
        ):
            sorted_group = tuple(sorted(group))
            if group != sorted_group:
                raise ValueError(
                    f"{name} must be canonically sorted."
                )
