"""Comprobador de integridad referencial cruzada.

Lectura pura del archive + cada artefacto derivado persistido. Reporta
incidencias estructurales sin modificar nada. Cero ejecución de motores
productores.

Cobertura (ADR-0030 §S15 + §enmienda E16):

1. **Integridad self-hash** de los seis dominios canónicos (workspace,
   timeline, snapshot, justification, attestation, assessment).
2. **Integridad referencial** entre artefactos (workspace_hash en
   timelines/snapshots/justifications, evidence/source refs, etc.).
3. **Reconciliación con el audit log** (post-ADR-0019 §enmienda E1):
   cada artefacto persistido debe tener una entry de audit log y su
   ``self_hash`` debe coincidir; cada entry debe apuntar a un artefacto
   presente. Detecta inserciones y borrados que saltan la API auditada.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from aip.attestation import (
    OperatorAttestation,
    compute_attestation_hash,
    decode_attestation,
)
from aip.audit.log import ActionKind, AuditEntry, iter_entries
from aip.integrity.models import (
    INTEGRITY_ENGINE_VERSION,
    INTEGRITY_METHOD_NAME,
    DerivedIntegrityIssue,
    DerivedIntegrityReport,
    IntegrityIssueKind,
)
from aip.justification import (
    InvestigationJustification,
    decode_justification,
    verify_justification_hash,
)
from aip.snapshot import (
    InvestigationSnapshot,
    decode_snapshot,
    verify_snapshot,
)
from aip.storage import layout, tables
from aip.storage.manifest import ArchiveManifest
from aip.timeline import (
    InvestigationTimeline,
    decode_timeline,
    verify_timeline_hash,
)
from aip.workspace import (
    InvestigationWorkspace,
    decode_workspace,
    verify_workspace_hash,
)

# Mapeo ActionKind derivada → prefijo del URI canónico del artefacto.
_DERIVED_ACTION_TO_KIND: dict[ActionKind, str] = {
    ActionKind.BUILD_WORKSPACE: "workspace",
    ActionKind.BUILD_TIMELINE: "timeline",
    ActionKind.BUILD_SNAPSHOT: "snapshot",
    ActionKind.BUILD_JUSTIFICATION: "justification",
    ActionKind.SIGN_ATTESTATION: "attestation",
    ActionKind.ASSESS_AUTHENTICATION: "assessment",
}


def verify_derived_integrity(
    archive_root: Path,
) -> DerivedIntegrityReport:
    """Audita la integridad de los artefactos derivados persistidos.

    Retorna :class:`DerivedIntegrityReport` con conteos por tipo +
    lista canónicamente ordenada de incidencias. Cero modificación del
    archive (lectura pura).
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise FileNotFoundError(
            f"archive not found or invalid at {archive_root}."
        )

    # Manifest actual del archive (para detectar drift).
    current_manifest_hash = _current_manifest_hash(archive_root)

    # Workspaces existentes — indexados por workspace_hash y por id.
    workspaces, workspaces_issues = _collect_workspaces(archive_root)
    workspace_hashes: set[str] = {w.workspace_hash for w in workspaces}

    # Timelines.
    timelines, timeline_issues = _collect_timelines(
        archive_root,
        workspace_hashes=workspace_hashes,
    )
    timeline_hashes: set[str] = {t.timeline_hash for t in timelines}

    # Snapshots.
    _, snapshot_issues = _collect_snapshots(
        archive_root,
        workspace_hashes=workspace_hashes,
        timeline_hashes=timeline_hashes,
    )

    # Justifications.
    justifications, justification_issues = _collect_justifications(
        archive_root,
        workspace_hashes=workspace_hashes,
        current_manifest_hash=current_manifest_hash,
    )

    # Attestations (ADR-0041 + §enmienda E16).
    attestations, attestation_issues = _collect_attestations(archive_root)

    # Reconciliación con audit log (ADR-0019 §enmienda E1).
    persisted_index = _build_persisted_index(
        workspaces=workspaces,
        timelines=timelines,
        justifications=justifications,
        attestations=attestations,
        archive_root=archive_root,
    )
    reconciliation_issues = _reconcile_with_audit_log(
        archive_root, persisted_index=persisted_index
    )

    all_issues = (
        workspaces_issues
        + timeline_issues
        + snapshot_issues
        + justification_issues
        + attestation_issues
        + reconciliation_issues
    )
    all_issues.sort()

    return DerivedIntegrityReport(
        workspaces_checked=len(workspaces),
        timelines_checked=len(timelines),
        snapshots_checked=_count_json(archive_root, "snapshots"),
        justifications_checked=_count_json(
            archive_root, "justifications"
        ),
        attestations_checked=len(attestations),
        assessments_checked=_count_assessments(archive_root),
        issues=tuple(all_issues),
        integrity_engine_version=INTEGRITY_ENGINE_VERSION,
        integrity_method_name=INTEGRITY_METHOD_NAME,
    )


# --------------------------------------------------------------------- helpers


def _current_manifest_hash(archive_root: Path) -> str | None:
    manifest_path = archive_root / layout.MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ArchiveManifest.model_validate(stored).manifest_hash()
    except Exception:
        return None


def _count_json(archive_root: Path, dirname: str) -> int:
    d = archive_root / dirname
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.json") if p.is_file())


# --------------------------------------------------------------------- workspaces


def _collect_workspaces(
    archive_root: Path,
) -> tuple[list[InvestigationWorkspace], list[DerivedIntegrityIssue]]:
    """Carga workspaces persistidos + reporta incidencias.

    Comprueba:
    - decode válido
    - self-hash íntegro
    - cada referencia evidence/assessment resuelve a fila
    - referencias impact_analysis/context_bundle no se validan
      (identifiers opacos por ADR-0036)
    """
    workspaces: list[InvestigationWorkspace] = []
    issues: list[DerivedIntegrityIssue] = []
    dir_path = archive_root / "workspaces"
    if not dir_path.is_dir():
        return workspaces, issues
    for path in sorted(dir_path.glob("*.json")):
        try:
            w = decode_workspace(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="workspace",
                    artifact_id=path.stem,
                    issue_kind=IntegrityIssueKind.DECODE_ERROR.value,
                    detail=f"decode failed: {type(exc).__name__}",
                )
            )
            continue
        if not verify_workspace_hash(w):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="workspace",
                    artifact_id=w.workspace_id,
                    issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
                    detail="workspace_hash recompute mismatch",
                )
            )
            # No skip: seguimos verificando referencias.
        for ref in w.references:
            _check_reference(
                archive_root,
                artifact_kind="workspace",
                artifact_id=w.workspace_id,
                reference_type=ref.reference_type,
                identifier=ref.identifier,
                issues=issues,
            )
        workspaces.append(w)
    return workspaces, issues


def _check_reference(
    archive_root: Path,
    *,
    artifact_kind: str,
    artifact_id: str,
    reference_type: str,
    identifier: str,
    issues: list[DerivedIntegrityIssue],
) -> None:
    """Verifica que evidence/assessment/source identifiers resuelvan a filas."""
    if (
        reference_type == "evidence"
        and tables.read_row(archive_root, "evidence", identifier) is None
    ):
        issues.append(
            DerivedIntegrityIssue(
                artifact_kind=artifact_kind,
                artifact_id=artifact_id,
                issue_kind=(
                    IntegrityIssueKind.EVIDENCE_REFERENCE_DANGLING.value
                ),
                detail=f"evidence {identifier!r} not found",
            )
        )
    elif (
        reference_type == "assessment"
        and tables.read_row(
            archive_root, "authentication_assessments", identifier
        )
        is None
    ):
        issues.append(
            DerivedIntegrityIssue(
                artifact_kind=artifact_kind,
                artifact_id=artifact_id,
                issue_kind=(
                    IntegrityIssueKind.ASSESSMENT_REFERENCE_DANGLING.value
                ),
                detail=f"assessment {identifier!r} not found",
            )
        )
    # impact_analysis y context_bundle: identifiers opacos, no validables
    # (ADR-0036 §reglas). source: workspace no tiene refs de tipo source.


# --------------------------------------------------------------------- timelines


def _collect_timelines(
    archive_root: Path,
    *,
    workspace_hashes: set[str],
) -> tuple[list[InvestigationTimeline], list[DerivedIntegrityIssue]]:
    timelines: list[InvestigationTimeline] = []
    issues: list[DerivedIntegrityIssue] = []
    dir_path = archive_root / "timelines"
    if not dir_path.is_dir():
        return timelines, issues
    for path in sorted(dir_path.glob("*.json")):
        try:
            t = decode_timeline(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="timeline",
                    artifact_id=path.stem,
                    issue_kind=IntegrityIssueKind.DECODE_ERROR.value,
                    detail=f"decode failed: {type(exc).__name__}",
                )
            )
            continue
        if not verify_timeline_hash(t):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="timeline",
                    artifact_id=t.timeline_id,
                    issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
                    detail="timeline_hash recompute mismatch",
                )
            )
        if t.workspace_hash not in workspace_hashes:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="timeline",
                    artifact_id=t.timeline_id,
                    issue_kind=(
                        IntegrityIssueKind.WORKSPACE_LINK_BROKEN.value
                    ),
                    detail=(
                        f"workspace_hash {t.workspace_hash[:8]}... not in "
                        "<archive>/workspaces/"
                    ),
                )
            )
        # Eventos: artifact_identifier para evidence/assessment debe resolver.
        for event in t.ordered_events:
            if (
                event.artifact_type == "evidence"
                and tables.read_row(
                    archive_root, "evidence", event.artifact_identifier
                )
                is None
            ):
                issues.append(
                    DerivedIntegrityIssue(
                        artifact_kind="timeline",
                        artifact_id=t.timeline_id,
                        issue_kind=(
                            IntegrityIssueKind.EVIDENCE_REFERENCE_DANGLING.value
                        ),
                        detail=(
                            f"event references evidence "
                            f"{event.artifact_identifier!r}"
                        ),
                    )
                )
            elif (
                event.artifact_type == "assessment"
                and tables.read_row(
                    archive_root,
                    "authentication_assessments",
                    event.artifact_identifier,
                )
                is None
            ):
                issues.append(
                    DerivedIntegrityIssue(
                        artifact_kind="timeline",
                        artifact_id=t.timeline_id,
                        issue_kind=(
                            IntegrityIssueKind.ASSESSMENT_REFERENCE_DANGLING.value
                        ),
                        detail=(
                            f"event references assessment "
                            f"{event.artifact_identifier!r}"
                        ),
                    )
                )
        timelines.append(t)
    return timelines, issues


# --------------------------------------------------------------------- snapshots


def _collect_snapshots(
    archive_root: Path,
    *,
    workspace_hashes: set[str],
    timeline_hashes: set[str],
) -> tuple[list[InvestigationSnapshot], list[DerivedIntegrityIssue]]:
    snapshots: list[InvestigationSnapshot] = []
    issues: list[DerivedIntegrityIssue] = []
    dir_path = archive_root / "snapshots"
    if not dir_path.is_dir():
        return snapshots, issues
    for path in sorted(dir_path.glob("*.json")):
        try:
            s = decode_snapshot(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="snapshot",
                    artifact_id=path.stem,
                    issue_kind=IntegrityIssueKind.DECODE_ERROR.value,
                    detail=f"decode failed: {type(exc).__name__}",
                )
            )
            continue
        if not verify_snapshot(s):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="snapshot",
                    artifact_id=s.snapshot_id,
                    issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
                    detail="snapshot_hash recompute mismatch",
                )
            )
        if s.workspace_hash not in workspace_hashes:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="snapshot",
                    artifact_id=s.snapshot_id,
                    issue_kind=(
                        IntegrityIssueKind.WORKSPACE_LINK_BROKEN.value
                    ),
                    detail=(
                        f"workspace_hash {s.workspace_hash[:8]}... not in "
                        "<archive>/workspaces/"
                    ),
                )
            )
        if s.timeline_hash not in timeline_hashes:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="snapshot",
                    artifact_id=s.snapshot_id,
                    issue_kind=(
                        IntegrityIssueKind.TIMELINE_LINK_BROKEN.value
                    ),
                    detail=(
                        f"timeline_hash {s.timeline_hash[:8]}... not in "
                        "<archive>/timelines/"
                    ),
                )
            )
        for ref in s.referenced_artifacts:
            _check_reference(
                archive_root,
                artifact_kind="snapshot",
                artifact_id=s.snapshot_id,
                reference_type=ref.reference_type,
                identifier=ref.identifier,
                issues=issues,
            )
        snapshots.append(s)
    return snapshots, issues


# --------------------------------------------------------------------- justifications


def _collect_justifications(
    archive_root: Path,
    *,
    workspace_hashes: set[str],
    current_manifest_hash: str | None,
) -> tuple[
    list[InvestigationJustification], list[DerivedIntegrityIssue]
]:
    justifications: list[InvestigationJustification] = []
    issues: list[DerivedIntegrityIssue] = []
    dir_path = archive_root / "justifications"
    if not dir_path.is_dir():
        return justifications, issues
    for path in sorted(dir_path.glob("*.json")):
        try:
            j = decode_justification(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="justification",
                    artifact_id=path.stem,
                    issue_kind=IntegrityIssueKind.DECODE_ERROR.value,
                    detail=f"decode failed: {type(exc).__name__}",
                )
            )
            continue
        if not verify_justification_hash(j):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="justification",
                    artifact_id=j.justification_id,
                    issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
                    detail="justification_hash recompute mismatch",
                )
            )
        if (
            current_manifest_hash is not None
            and j.source_manifest_hash != current_manifest_hash
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="justification",
                    artifact_id=j.justification_id,
                    issue_kind=IntegrityIssueKind.MANIFEST_DRIFT.value,
                    detail=(
                        f"source_manifest_hash "
                        f"{j.source_manifest_hash[:8]}... != current "
                        f"{current_manifest_hash[:8]}..."
                    ),
                )
            )
        if (
            j.workspace_hash is not None
            and j.workspace_hash not in workspace_hashes
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="justification",
                    artifact_id=j.justification_id,
                    issue_kind=(
                        IntegrityIssueKind.WORKSPACE_LINK_BROKEN.value
                    ),
                    detail=(
                        f"workspace_hash {j.workspace_hash[:8]}... not in "
                        "<archive>/workspaces/"
                    ),
                )
            )
        # conclusion_anchor (V1: assessment) debe resolver.
        if (
            tables.read_row(
                archive_root,
                "authentication_assessments",
                j.conclusion_anchor_id,
            )
            is None
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="justification",
                    artifact_id=j.justification_id,
                    issue_kind=(
                        IntegrityIssueKind.ASSESSMENT_REFERENCE_DANGLING.value
                    ),
                    detail=(
                        f"conclusion_anchor_id {j.conclusion_anchor_id!r} "
                        "not found"
                    ),
                )
            )
        # Chain entries: cada referencia por rol debe resolver.
        for cat in (
            j.minimal_evidence,
            j.supporting_assessments,
            j.provenance_chain,
        ):
            for entry in cat:
                _check_chain_entry(
                    archive_root,
                    artifact_kind="justification",
                    artifact_id=j.justification_id,
                    entry_role=entry.entry_role,
                    entry_identifier=entry.entry_identifier,
                    issues=issues,
                )
        justifications.append(j)
    return justifications, issues


def _check_chain_entry(
    archive_root: Path,
    *,
    artifact_kind: str,
    artifact_id: str,
    entry_role: str,
    entry_identifier: str,
    issues: list[DerivedIntegrityIssue],
) -> None:
    """Verifica resolución de ChainEntry según su rol."""
    if entry_role == "evidence":
        if (
            tables.read_row(archive_root, "evidence", entry_identifier)
            is None
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.EVIDENCE_REFERENCE_DANGLING.value
                    ),
                    detail=f"chain entry references evidence "
                    f"{entry_identifier!r}",
                )
            )
    elif entry_role == "source":
        if (
            tables.read_row(archive_root, "sources", entry_identifier)
            is None
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.SOURCE_REFERENCE_DANGLING.value
                    ),
                    detail=f"chain entry references source "
                    f"{entry_identifier!r}",
                )
            )
    elif entry_role == "assessment":
        if (
            tables.read_row(
                archive_root,
                "authentication_assessments",
                entry_identifier,
            )
            is None
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.ASSESSMENT_REFERENCE_DANGLING.value
                    ),
                    detail=f"chain entry references assessment "
                    f"{entry_identifier!r}",
                )
            )
    elif entry_role == "provenance_step":
        # Identifier formato: f"{evidence_hash}__step{step_id:05d}"
        marker = "__step"
        if marker not in entry_identifier:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.PROVENANCE_STEP_DANGLING.value
                    ),
                    detail=(
                        f"provenance_step identifier malformed: "
                        f"{entry_identifier!r}"
                    ),
                )
            )
            return
        evidence_hash, _step_part = entry_identifier.split(marker, 1)
        if (
            tables.read_row(archive_root, "provenance", evidence_hash)
            is None
        ):
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.PROVENANCE_STEP_DANGLING.value
                    ),
                    detail=(
                        f"provenance row for {evidence_hash[:8]}... "
                        "not found"
                    ),
                )
            )


# --------------------------------------------------------------------- attestations (E16)


def _collect_attestations(
    archive_root: Path,
) -> tuple[list[tuple[str, OperatorAttestation]], list[DerivedIntegrityIssue]]:
    """Carga atestaciones persistidas + reporta incidencias estructurales.

    Para cada ``<archive>/attestations/*.json``:

    - Decode (``DECODE_ERROR`` si falla).
    - Recomputo de ``attestation_hash`` y comparación con el declarado
      (``ATTESTATION_HASH_MISMATCH`` si no coincide).

    NO verifica la firma ed25519 (esa requiere clave pública del
    firmante; verificación criptográfica completa vive en
    ``aip attestation verify --public-key``).

    Devuelve tuplas ``(attestation_id, attestation)`` donde
    ``attestation_id`` es el nombre del archivo (sin extensión), porque
    la atestación no lleva su id en el modelo (ADR-0041 §modelo).
    """
    out: list[tuple[str, OperatorAttestation]] = []
    issues: list[DerivedIntegrityIssue] = []
    dir_path = archive_root / "attestations"
    if not dir_path.is_dir():
        return out, issues
    for path in sorted(dir_path.glob("*.json")):
        attestation_id = path.stem
        try:
            att = decode_attestation(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="attestation",
                    artifact_id=attestation_id,
                    issue_kind=IntegrityIssueKind.DECODE_ERROR.value,
                    detail=f"decode failed: {type(exc).__name__}",
                )
            )
            continue
        if compute_attestation_hash(att) != att.attestation_hash:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind="attestation",
                    artifact_id=attestation_id,
                    issue_kind=(
                        IntegrityIssueKind.ATTESTATION_HASH_MISMATCH.value
                    ),
                    detail="attestation_hash recompute mismatch",
                )
            )
        out.append((attestation_id, att))
    return out, issues


def _count_assessments(archive_root: Path) -> int:
    try:
        return sum(
            1
            for _ in tables.iter_rows(
                archive_root, "authentication_assessments"
            )
        )
    except Exception:
        return 0


# --------------------------------------------------------------------- reconciliation (E16)


def _build_persisted_index(
    *,
    workspaces: Iterable[InvestigationWorkspace],
    timelines: Iterable[InvestigationTimeline],
    justifications: Iterable[InvestigationJustification],
    attestations: Iterable[tuple[str, OperatorAttestation]],
    archive_root: Path,
) -> dict[str, tuple[str, str, str]]:
    """Construye el índice ``target_uri → (kind, id, self_hash)``.

    Cobertura:

    - workspace / timeline / snapshot / justification — desde colectores.
    - attestation — desde ``_collect_attestations``.
    - assessment — desde la tabla ``authentication_assessments``; el
      ``self_hash`` registrado en el audit log para assessments es el
      ``evidence_id`` (ancla; un assessment no tiene hash propio
      independiente).

    Snapshots se enumeran independientemente leyendo el directorio
    porque su colector no se inserta como dependencia de este índice.
    """
    index: dict[str, tuple[str, str, str]] = {}
    for w in workspaces:
        index[f"aip:workspace/{w.workspace_id}"] = (
            "workspace",
            w.workspace_id,
            w.workspace_hash,
        )
    for t in timelines:
        index[f"aip:timeline/{t.timeline_id}"] = (
            "timeline",
            t.timeline_id,
            t.timeline_hash,
        )
    snapshots_dir = archive_root / "snapshots"
    if snapshots_dir.is_dir():
        for path in sorted(snapshots_dir.glob("*.json")):
            try:
                s = decode_snapshot(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            index[f"aip:snapshot/{s.snapshot_id}"] = (
                "snapshot",
                s.snapshot_id,
                s.snapshot_hash,
            )
    for j in justifications:
        index[f"aip:justification/{j.justification_id}"] = (
            "justification",
            j.justification_id,
            j.justification_hash,
        )
    for attestation_id, att in attestations:
        index[f"aip:attestation/{attestation_id}"] = (
            "attestation",
            attestation_id,
            att.attestation_hash,
        )
    try:
        for raw in tables.iter_rows(
            archive_root, "authentication_assessments"
        ):
            if not isinstance(raw, dict):
                continue
            assessment_id = str(raw.get("assessment_id", ""))
            evidence_id = str(raw.get("evidence_id", ""))
            if assessment_id and evidence_id:
                index[f"aip:assessment/{assessment_id}"] = (
                    "assessment",
                    assessment_id,
                    evidence_id,
                )
    except Exception:
        pass
    return index


def _reconcile_with_audit_log(
    archive_root: Path,
    *,
    persisted_index: dict[str, tuple[str, str, str]],
) -> list[DerivedIntegrityIssue]:
    """Cruza el audit log con el índice de artefactos persistidos.

    Por cada target presente en ambos lados:

    - Si la última entry declara un ``self_hash`` distinto del archivo
      actual → ``AUDIT_LOG_HASH_MISMATCH``.

    Por cada target en disco sin entries → ``MISSING_AUDIT_ENTRY``.
    Por cada target con entries pero sin artefacto en disco →
    ``MISSING_PERSISTED_ARTIFACT``.

    Si ``audit.log`` no existe (archive incompleto / test fixture),
    no se emiten incidencias de reconciliación.
    """
    log_path = archive_root / layout.AUDIT_LOG_FILENAME
    if not log_path.is_file():
        return []

    latest_by_target: dict[str, AuditEntry] = {}
    for entry in iter_entries(archive_root):
        if entry.action not in _DERIVED_ACTION_TO_KIND:
            continue
        latest_by_target[entry.target] = entry

    issues: list[DerivedIntegrityIssue] = []

    for target, (artifact_kind, artifact_id, self_hash) in (
        persisted_index.items()
    ):
        matched: AuditEntry | None = latest_by_target.get(target)
        if matched is None:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.MISSING_AUDIT_ENTRY.value
                    ),
                    detail=(
                        f"target {target!r} present on disk but no "
                        "audit entry references it"
                    ),
                )
            )
            continue
        declared = matched.parameters.get("self_hash", "")
        if declared != self_hash:
            issues.append(
                DerivedIntegrityIssue(
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                    issue_kind=(
                        IntegrityIssueKind.AUDIT_LOG_HASH_MISMATCH.value
                    ),
                    detail=(
                        f"last entry declares self_hash "
                        f"{declared[:8]}... but disk has "
                        f"{self_hash[:8]}..."
                    ),
                )
            )

    for target, entry in latest_by_target.items():
        if target in persisted_index:
            continue
        kind = _DERIVED_ACTION_TO_KIND[entry.action]
        artifact_id = target.split("/", 1)[1] if "/" in target else target
        issues.append(
            DerivedIntegrityIssue(
                artifact_kind=kind,
                artifact_id=artifact_id,
                issue_kind=(
                    IntegrityIssueKind.MISSING_PERSISTED_ARTIFACT.value
                ),
                detail=(
                    f"audit log references {target!r} but no persisted "
                    "artifact found at canonical location"
                ),
            )
        )

    return issues
