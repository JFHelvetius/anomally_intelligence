"""Modelos del Justification Engine (ADR-0040 §modelo)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

JUSTIFICATION_SCHEMA_VERSION: Final[str] = "1"
JUSTIFICATION_ENGINE_VERSION: Final[str] = "1.0.0"
JUSTIFICATION_METHOD_NAME: Final[str] = "deductive_chain_v1"

ALLOWED_ENTRY_ROLES: Final[frozenset[str]] = frozenset(
    {
        "evidence",
        "source",
        "assessment",
        "provenance_step",
        "graph_node",
    }
)
"""Taxonomía cerrada de roles epistémicos para entradas de la cadena."""

ALLOWED_ANCHOR_TYPES: Final[frozenset[str]] = frozenset({"assessment"})
"""V1 sólo soporta assessment como conclusión anchor. Ampliación
requiere ADR de enmienda."""

_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-]+$")
_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-f0-9]{64}$"
)


@dataclass(frozen=True, order=True)
class ChainEntry:
    """Entrada inmutable de la cadena justificatoria.

    Identidad canónica: ``(entry_role, entry_identifier)``. ``entry_hash``
    es función pura de los strings de identidad
    (:func:`compute_chain_entry_hash`) — cero ejecución de motores,
    cero acceso al archive (ADR-0040 §G3).
    """

    entry_role: str
    entry_identifier: str
    entry_hash: str

    def __post_init__(self) -> None:
        if self.entry_role not in ALLOWED_ENTRY_ROLES:
            raise ValueError(
                f"invalid entry_role {self.entry_role!r}; "
                f"must be one of {sorted(ALLOWED_ENTRY_ROLES)}."
            )
        if not self.entry_identifier:
            raise ValueError("entry_identifier must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.entry_hash):
            raise ValueError(
                "entry_hash must be SHA-256 hex lowercase of length 64."
            )


@dataclass(frozen=True)
class InvestigationJustification:
    """Cadena deductiva canónica anclada a una conclusión (ADR-0040)."""

    justification_id: str
    conclusion_anchor_type: str
    conclusion_anchor_id: str
    conclusion_anchor_hash: str
    minimal_evidence: tuple[ChainEntry, ...]
    supporting_assessments: tuple[ChainEntry, ...]
    graph_nodes_used: tuple[ChainEntry, ...]
    intermediate_artifacts: tuple[ChainEntry, ...]
    provenance_chain: tuple[ChainEntry, ...]
    workspace_hash: str | None
    source_manifest_hash: str
    justification_engine_version: str
    justification_method_name: str
    justification_hash: str
    schema_version: str = JUSTIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.justification_id:
            raise ValueError("justification_id must be non-empty.")
        if not _ID_PATTERN.match(self.justification_id):
            raise ValueError(
                f"justification_id {self.justification_id!r} contains "
                "characters outside [A-Za-z0-9._-]."
            )
        if self.conclusion_anchor_type not in ALLOWED_ANCHOR_TYPES:
            raise ValueError(
                f"invalid conclusion_anchor_type "
                f"{self.conclusion_anchor_type!r}; must be one of "
                f"{sorted(ALLOWED_ANCHOR_TYPES)}."
            )
        if not self.conclusion_anchor_id:
            raise ValueError("conclusion_anchor_id must be non-empty.")
        for field_name, value in (
            ("conclusion_anchor_hash", self.conclusion_anchor_hash),
            ("source_manifest_hash", self.source_manifest_hash),
            ("justification_hash", self.justification_hash),
        ):
            if not _SHA256_HEX_PATTERN.match(value):
                raise ValueError(
                    f"{field_name} must be SHA-256 hex lowercase."
                )
        if self.workspace_hash is not None and not _SHA256_HEX_PATTERN.match(
            self.workspace_hash
        ):
            raise ValueError(
                "workspace_hash must be SHA-256 hex lowercase or None."
            )
        if not self.justification_engine_version:
            raise ValueError(
                "justification_engine_version must be non-empty."
            )
        if not self.justification_method_name:
            raise ValueError(
                "justification_method_name must be non-empty."
            )
        # Canonical sorting + no duplicates per category.
        for cat_name, cat_value in (
            ("minimal_evidence", self.minimal_evidence),
            ("supporting_assessments", self.supporting_assessments),
            ("graph_nodes_used", self.graph_nodes_used),
            ("intermediate_artifacts", self.intermediate_artifacts),
            ("provenance_chain", self.provenance_chain),
        ):
            sorted_value = tuple(sorted(cat_value))
            if cat_value != sorted_value:
                raise ValueError(
                    f"{cat_name} must be canonically sorted by "
                    "(entry_role, entry_identifier)."
                )
            keys = [
                (e.entry_role, e.entry_identifier) for e in cat_value
            ]
            if len(set(keys)) != len(keys):
                raise ValueError(
                    f"{cat_name} contains duplicate entries."
                )


@dataclass(frozen=True)
class JustificationDiff:
    """Set-difference puro entre dos justificaciones (ADR-0040)."""

    justification_a_hash: str
    justification_b_hash: str
    added_entries: tuple[ChainEntry, ...]
    removed_entries: tuple[ChainEntry, ...]
    unchanged_entries: tuple[ChainEntry, ...]
    diff_hash: str
    schema_version: str = JUSTIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name, value in (
            ("justification_a_hash", self.justification_a_hash),
            ("justification_b_hash", self.justification_b_hash),
            ("diff_hash", self.diff_hash),
        ):
            if not _SHA256_HEX_PATTERN.match(value):
                raise ValueError(
                    f"{field_name} must be SHA-256 hex lowercase."
                )
        for cat_name, cat_value in (
            ("added_entries", self.added_entries),
            ("removed_entries", self.removed_entries),
            ("unchanged_entries", self.unchanged_entries),
        ):
            sorted_value = tuple(sorted(cat_value))
            if cat_value != sorted_value:
                raise ValueError(
                    f"{cat_name} must be canonically sorted."
                )
