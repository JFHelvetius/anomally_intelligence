"""Investigation Justification Engine (ADR-0040).

Capa derivada que produce un :class:`InvestigationJustification` —
cadena deductiva categorizada por rol epistémico, anclada a una
conclusión existente (V1: assessment).

**Propiedad central (ADR-0040 §propiedad central):**

> Investigation Justification **enumera estructuralmente** la cadena que
> existe en el archive entre una conclusión y sus dependencias. **No
> infiere. No clasifica. No pondera. No genera lenguaje libre.** Es
> lookup estructurado categorizado por rol epistémico.
"""

from __future__ import annotations

from aip.justification.builder import (
    JustificationAnchorNotFoundError,
    JustificationNotFoundError,
    build_justification,
    compute_chain_entry_hash,
    compute_justification_hash,
    decode_justification,
    encode_justification,
    justification_path,
    load_justification,
    persist_justification,
    verify_justification_hash,
)
from aip.justification.differ import (
    compute_justification_diff,
    compute_justification_diff_hash,
    decode_justification_diff,
    encode_justification_diff,
    verify_justification_diff,
)
from aip.justification.models import (
    ALLOWED_ANCHOR_TYPES,
    ALLOWED_ENTRY_ROLES,
    JUSTIFICATION_ENGINE_VERSION,
    JUSTIFICATION_METHOD_NAME,
    JUSTIFICATION_SCHEMA_VERSION,
    ChainEntry,
    InvestigationJustification,
    JustificationDiff,
)

__all__ = [
    "ALLOWED_ANCHOR_TYPES",
    "ALLOWED_ENTRY_ROLES",
    "JUSTIFICATION_ENGINE_VERSION",
    "JUSTIFICATION_METHOD_NAME",
    "JUSTIFICATION_SCHEMA_VERSION",
    "ChainEntry",
    "InvestigationJustification",
    "JustificationAnchorNotFoundError",
    "JustificationDiff",
    "JustificationNotFoundError",
    "build_justification",
    "compute_chain_entry_hash",
    "compute_justification_diff",
    "compute_justification_diff_hash",
    "compute_justification_hash",
    "decode_justification",
    "decode_justification_diff",
    "encode_justification",
    "encode_justification_diff",
    "justification_path",
    "load_justification",
    "persist_justification",
    "verify_justification_diff",
    "verify_justification_hash",
]
