"""Modelos del integrity checker (post-ADR-0040 hardening)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

INTEGRITY_ENGINE_VERSION: Final[str] = "1.0.0"
INTEGRITY_METHOD_NAME: Final[str] = "structural_referential_v1"


class IntegrityIssueKind(StrEnum):
    """Taxonomía cerrada de incidencias estructurales.

    Cada valor corresponde a una propiedad observable. Cero estados
    interpretativos.
    """

    HASH_MISMATCH = "hash_mismatch"
    """El self-hash recomputado no coincide con el declarado."""

    MANIFEST_DRIFT = "manifest_drift"
    """``source_manifest_hash`` del artefacto difiere del manifest
    actual del archive."""

    WORKSPACE_LINK_BROKEN = "workspace_link_broken"
    """El artefacto referencia un ``workspace_hash`` que no coincide
    con ningún workspace persistido bajo ``<archive>/workspaces/``."""

    TIMELINE_LINK_BROKEN = "timeline_link_broken"
    """El snapshot referencia un ``timeline_hash`` que no coincide
    con ningún timeline persistido bajo ``<archive>/timelines/``."""

    EVIDENCE_REFERENCE_DANGLING = "evidence_reference_dangling"
    """Una referencia a evidence_hash no resuelve a fila en la
    tabla ``evidence``."""

    SOURCE_REFERENCE_DANGLING = "source_reference_dangling"
    """Una referencia a source_id no resuelve a fila en ``sources``."""

    ASSESSMENT_REFERENCE_DANGLING = "assessment_reference_dangling"
    """Una referencia a assessment_id no resuelve a fila en
    ``authentication_assessments``."""

    PROVENANCE_STEP_DANGLING = "provenance_step_dangling"
    """Una referencia a provenance_step no resuelve al row de Provenance
    correspondiente o al step_id declarado."""

    DECODE_ERROR = "decode_error"
    """El JSON persistido no se puede deserializar al modelo
    correspondiente (corrupción, manipulación, schema_version
    incompatible)."""

    # --- ADR-0030 §enmienda E16 (post-ADR-0041 + ADR-0019 E1) -----------
    ATTESTATION_HASH_MISMATCH = "attestation_hash_mismatch"
    """El ``attestation_hash`` recomputado no coincide con el declarado en
    la atestación persistida bajo ``<archive>/attestations/``."""

    MISSING_AUDIT_ENTRY = "missing_audit_entry"
    """Existe un artefacto derivado persistido en disco sin entry de
    audit log apuntando a su URI canónico. Indica persistencia que
    saltó la API auditada (manual placement o downgrade pre-E1)."""

    MISSING_PERSISTED_ARTIFACT = "missing_persisted_artifact"
    """Existe una entry de audit log para un artefacto derivado cuyo
    archivo de persistencia ya no está presente. Indica borrado fuera
    de la cadena auditada."""

    AUDIT_LOG_HASH_MISMATCH = "audit_log_hash_mismatch"
    """El ``self_hash`` declarado en la entry más reciente del audit log
    para un target dado no coincide con el self-hash actual del artefacto
    persistido. Indica sustitución del artefacto sin re-emitir entry."""


@dataclass(frozen=True, order=True)
class DerivedIntegrityIssue:
    """Incidencia inmutable reportada por el checker.

    Orden canónico natural: ``(artifact_kind, artifact_id, issue_kind,
    detail)``.
    """

    artifact_kind: str
    artifact_id: str
    issue_kind: str
    detail: str


@dataclass(frozen=True)
class DerivedIntegrityReport:
    """Reporte agregado del checker."""

    workspaces_checked: int
    timelines_checked: int
    snapshots_checked: int
    justifications_checked: int
    attestations_checked: int
    assessments_checked: int
    issues: tuple[DerivedIntegrityIssue, ...]
    integrity_engine_version: str
    integrity_method_name: str

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    @property
    def total_checked(self) -> int:
        return (
            self.workspaces_checked
            + self.timelines_checked
            + self.snapshots_checked
            + self.justifications_checked
            + self.attestations_checked
            + self.assessments_checked
        )
