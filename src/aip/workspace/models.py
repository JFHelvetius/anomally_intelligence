"""Modelos del Investigation Workspace (ADR-0036 §modelo).

Dos dataclasses frozen + una enum cerrada + dos constantes. Cero campos
subjetivos. Cero floats. Cero payload de artefactos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

WORKSPACE_SCHEMA_VERSION: Final[str] = "1"
"""SemVer-simple del esquema de workspace (ADR-0036). **Distinto** del
``SCHEMA_VERSION`` del proyecto (ADR-0016): ciclo de vida independiente."""


class ReferenceType(StrEnum):
    """Taxonomía cerrada de tipos de referencia (ADR-0036 §tipos permitidos).

    Cualquier otro valor en construcción de :class:`WorkspaceReference`
    lanza ``ValueError`` (vía :class:`InvalidReferenceTypeError`).
    """

    EVIDENCE = "evidence"
    ASSESSMENT = "assessment"
    IMPACT_ANALYSIS = "impact_analysis"
    CONTEXT_BUNDLE = "context_bundle"


ALLOWED_REFERENCE_TYPES: Final[frozenset[str]] = frozenset(
    rt.value for rt in ReferenceType
)
"""Set inmutable de strings válidos para ``reference_type``. Usado por
validadores y por el CLI para mensajes de error."""


_WORKSPACE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._\-]+$"
)
_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, order=True)
class WorkspaceReference:
    """Referencia a un artefacto existente (ADR-0036 §reglas).

    Identidad canónica: ``(reference_type, identifier)``. **Nunca contiene
    payload** — sólo identifica el artefacto y declara su huella canónica.

    ``artifact_hash`` se deriva exclusivamente de los strings
    ``(reference_type, identifier)`` vía
    :func:`aip.workspace.compute_artifact_hash`. Cero acceso al archive,
    cero ejecución de motores analíticos — propiedad estructural que hace
    G3 (no ejecuta motores) verificable trivialmente.
    """

    reference_type: str
    identifier: str
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.reference_type not in ALLOWED_REFERENCE_TYPES:
            raise ValueError(
                f"invalid reference_type {self.reference_type!r}; "
                f"must be one of {sorted(ALLOWED_REFERENCE_TYPES)}."
            )
        if not self.identifier:
            raise ValueError("WorkspaceReference.identifier must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.artifact_hash):
            raise ValueError(
                "WorkspaceReference.artifact_hash must be SHA-256 hex "
                "lowercase of length 64."
            )


@dataclass(frozen=True)
class InvestigationWorkspace:
    """Workspace inmutable de investigación (ADR-0036 §modelo).

    Es índice reproducible — agrupa referencias a artefactos sin copiar
    sus payloads. Comparable, hasheable y persistible como JSON canónico.

    Reglas (ADR-0036 §reglas):

    - ``references`` no contiene duplicados ``(reference_type, identifier)``.
    - ``references`` está ordenada canónicamente por la clave natural
      de :class:`WorkspaceReference`.
    - ``workspace_id`` y ``title`` no vacíos; ``workspace_id`` filename-safe.
    - ``source_manifest_hash`` y ``workspace_hash``: SHA-256 hex lowercase.
    """

    workspace_id: str
    title: str
    references: tuple[WorkspaceReference, ...]
    source_manifest_hash: str
    workspace_hash: str
    schema_version: str = WORKSPACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError(
                "InvestigationWorkspace.workspace_id must be non-empty."
            )
        if not _WORKSPACE_ID_PATTERN.match(self.workspace_id):
            raise ValueError(
                f"workspace_id {self.workspace_id!r} contains characters "
                "outside [A-Za-z0-9._-]; use ASCII-safe identifiers."
            )
        if not self.title:
            raise ValueError(
                "InvestigationWorkspace.title must be non-empty."
            )
        if not _SHA256_HEX_PATTERN.match(self.source_manifest_hash):
            raise ValueError(
                "source_manifest_hash must be SHA-256 hex lowercase "
                "of length 64."
            )
        if not _SHA256_HEX_PATTERN.match(self.workspace_hash):
            raise ValueError(
                "workspace_hash must be SHA-256 hex lowercase of length 64."
            )
        # Duplicados se detectan por la clave canónica (reference_type, identifier).
        seen: set[tuple[str, str]] = set()
        for ref in self.references:
            key = (ref.reference_type, ref.identifier)
            if key in seen:
                raise ValueError(
                    f"duplicate workspace reference {key}; ADR-0036 §G7."
                )
            seen.add(key)
        # Orden canónico explícito.
        sorted_refs = tuple(sorted(self.references))
        if self.references != sorted_refs:
            raise ValueError(
                "InvestigationWorkspace.references must be canonically "
                "sorted by (reference_type, identifier)."
            )
