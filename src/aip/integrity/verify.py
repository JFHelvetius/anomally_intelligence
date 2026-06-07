"""Comprobador de integridad referencial cruzada (post-ADR-0040 hardening).

Lectura pura del archive + cada artefacto derivado persistido. Reporta
incidencias estructurales sin modificar nada. Cero ejecución de motores
productores.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    _, justification_issues = _collect_justifications(
        archive_root,
        workspace_hashes=workspace_hashes,
        current_manifest_hash=current_manifest_hash,
    )

    all_issues = (
        workspaces_issues
        + timeline_issues
        + snapshot_issues
        + justification_issues
    )
    all_issues.sort()

    return DerivedIntegrityReport(
        workspaces_checked=len(workspaces),
        timelines_checked=len(timelines),
        snapshots_checked=_count_json(archive_root, "snapshots"),
        justifications_checked=_count_json(
            archive_root, "justifications"
        ),
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
