"""Modelos del Snapshot Engine (ADR-0038 §modelo)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

SNAPSHOT_SCHEMA_VERSION: Final[str] = "1"

_SNAPSHOT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._\-]+$"
)
_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, order=True)
class SnapshotReference:
    """Referencia inmutable a un artefacto. Sin payload (ADR-0038 §propiedad)."""

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
class InvestigationSnapshot:
    """Snapshot canónico de una investigación (ADR-0038 §modelo)."""

    snapshot_id: str
    workspace_hash: str
    timeline_hash: str
    referenced_artifacts: tuple[SnapshotReference, ...]
    snapshot_hash: str
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("snapshot_id must be non-empty.")
        if not _SNAPSHOT_ID_PATTERN.match(self.snapshot_id):
            raise ValueError(
                f"snapshot_id {self.snapshot_id!r} contains characters "
                "outside [A-Za-z0-9._-]."
            )
        if not _SHA256_HEX_PATTERN.match(self.workspace_hash):
            raise ValueError("workspace_hash must be SHA-256 hex lowercase.")
        if not _SHA256_HEX_PATTERN.match(self.timeline_hash):
            raise ValueError("timeline_hash must be SHA-256 hex lowercase.")
        if not _SHA256_HEX_PATTERN.match(self.snapshot_hash):
            raise ValueError("snapshot_hash must be SHA-256 hex lowercase.")
        sorted_refs = tuple(sorted(self.referenced_artifacts))
        if self.referenced_artifacts != sorted_refs:
            raise ValueError(
                "referenced_artifacts must be canonically sorted."
            )
        seen: set[tuple[str, str]] = set()
        for ref in self.referenced_artifacts:
            key = (ref.reference_type, ref.identifier)
            if key in seen:
                raise ValueError(
                    f"duplicate snapshot reference {key}."
                )
            seen.add(key)
