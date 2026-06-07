"""Investigation Workspace (ADR-0036).

``aip.workspace`` es la **quinta** capa derivada del archive (tras
``aip.analysis``, ``aip.graph``, ``aip.impact`` y ``aip.context``). A
diferencia de las anteriores, su rol no es derivar información del
estado del archive — es **representar el trabajo investigativo**
realizado sobre artefactos derivados existentes.

**Propiedad central (ADR-0036 §propiedad central):**

> Investigation Workspace **agrega referencias** a artefactos existentes.
> **No ejecuta análisis nuevos.** No modifica a ADR-0032/0033/0034/0035.
> No re-procesa outputs. No emite veredictos sobre los artefactos.

El workspace es **índice reproducible**: contiene referencias verificables
a evidence/assessments/impact_analyses/context_bundles, encadenadas al
estado del archive vía ``source_manifest_hash`` y con identidad propia
vía ``workspace_hash`` (verificable offline).
"""

from __future__ import annotations

from aip.workspace.builder import (
    DuplicateReferenceError,
    InvalidReferenceTypeError,
    WorkspaceNotFoundError,
    compute_artifact_hash,
    compute_workspace_hash,
    create_workspace,
    decode_workspace,
    encode_workspace,
    load_workspace,
    persist_workspace,
    verify_workspace_hash,
    workspace_path,
)
from aip.workspace.models import (
    ALLOWED_REFERENCE_TYPES,
    WORKSPACE_SCHEMA_VERSION,
    InvestigationWorkspace,
    ReferenceType,
    WorkspaceReference,
)

__all__ = [
    "ALLOWED_REFERENCE_TYPES",
    "WORKSPACE_SCHEMA_VERSION",
    "DuplicateReferenceError",
    "InvalidReferenceTypeError",
    "InvestigationWorkspace",
    "ReferenceType",
    "WorkspaceNotFoundError",
    "WorkspaceReference",
    "compute_artifact_hash",
    "compute_workspace_hash",
    "create_workspace",
    "decode_workspace",
    "encode_workspace",
    "load_workspace",
    "persist_workspace",
    "verify_workspace_hash",
    "workspace_path",
]
