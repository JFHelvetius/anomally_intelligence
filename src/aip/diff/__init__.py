"""Investigation Diff Engine (ADR-0039).

Capa derivada que compara dos snapshots por set-difference sobre sus
``referenced_artifacts``. **No declara cuál es mejor, peor, más
importante ni más relevante** (ADR-0039 §propiedad central).
"""

from __future__ import annotations

from aip.diff.differ import (
    compute_diff,
    compute_diff_hash,
    decode_diff,
    encode_diff,
    verify_diff,
)
from aip.diff.models import (
    DIFF_SCHEMA_VERSION,
    DiffEntry,
    InvestigationDiff,
)

__all__ = [
    "DIFF_SCHEMA_VERSION",
    "DiffEntry",
    "InvestigationDiff",
    "compute_diff",
    "compute_diff_hash",
    "decode_diff",
    "encode_diff",
    "verify_diff",
]
