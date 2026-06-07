"""Investigation Snapshot Engine (ADR-0038).

Capa derivada que **congela** un par (workspace, timeline) en un único
artefacto verificable offline. Sólo referencias — cero payload, cero
duplicación, cero interpretación (ADR-0038 §propiedad central).
"""

from __future__ import annotations

from aip.snapshot.builder import (
    SnapshotNotFoundError,
    compute_snapshot_hash,
    create_snapshot,
    decode_snapshot,
    encode_snapshot,
    load_snapshot,
    persist_snapshot,
    snapshot_path,
    verify_snapshot,
)
from aip.snapshot.models import (
    SNAPSHOT_SCHEMA_VERSION,
    InvestigationSnapshot,
    SnapshotReference,
)

__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "InvestigationSnapshot",
    "SnapshotNotFoundError",
    "SnapshotReference",
    "compute_snapshot_hash",
    "create_snapshot",
    "decode_snapshot",
    "encode_snapshot",
    "load_snapshot",
    "persist_snapshot",
    "snapshot_path",
    "verify_snapshot",
]
