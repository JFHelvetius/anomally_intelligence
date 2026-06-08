"""Tests del contrato ADR-0030 §enmienda E16 — cobertura E16.

Verifica que ``verify_derived_integrity``:

- Audita atestaciones persistidas (decode + ``attestation_hash`` recomputed).
- Detecta atestaciones con ``attestation_hash`` adulterado.
- Reconcilia con el audit log: cada artefacto persistido debe tener entry
  con ``self_hash`` coincidente, cada entry debe apuntar a artefacto real.

Las tres garantías estructurales de la reconciliación:

- G_E16_a — ``MISSING_AUDIT_ENTRY``: artefacto en disco sin entry.
- G_E16_b — ``MISSING_PERSISTED_ARTIFACT``: entry sin artefacto en disco.
- G_E16_c — ``AUDIT_LOG_HASH_MISMATCH``: hash del archivo ≠ hash declarado
  en la entry más reciente.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.attestation import (
    encode_attestation,
    generate_keypair,
    persist_attestation,
    sign_artifact,
)
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.integrity import (
    IntegrityIssueKind,
    verify_derived_integrity,
)
from aip.workspace import (
    create_workspace,
    encode_workspace,
    persist_workspace,
    verify_workspace_hash,
)

UTC = dt.UTC
TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path) -> str:
    arc = Archive.open(archive_root)
    ev = arc.ingest_evidence(
        blob,
        source_id="nara",
        source_name="NARA",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@seed",
        clock=_clock(TS),
    )
    return ev.hash


def _seed_workspace(tmp_path: Path, archive_root: Path):
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(
        w, archive_root=archive_root, actor="@op", clock=_clock(TS)
    )
    return ev_hash, w


def _seed_attestation(
    tmp_path: Path, archive_root: Path, attestation_id: str = "att-01"
):
    _ev_hash, w = _seed_workspace(tmp_path, archive_root)
    ws_path = archive_root / "workspaces" / f"{w.workspace_id}.json"
    priv, _pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=ws_path,
        private_key=priv,
        signer_id="@op",
        signed_at=TS,
    )
    persist_attestation(
        att,
        archive_root=archive_root,
        attestation_id=attestation_id,
        actor="@op",
        clock=_clock(TS),
    )
    return att


# ---------------------------------------------------------------- attestations


def test_persisted_attestation_is_audited(tmp_path: Path, archive_root: Path) -> None:
    """Una atestación firmada y persistida pasa el integrity check."""
    _seed_attestation(tmp_path, archive_root)
    report = verify_derived_integrity(archive_root)
    assert report.attestations_checked == 1
    assert report.ok, [i for i in report.issues]


def test_attestation_with_tampered_hash_is_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Editar ``attestation_hash`` en disco produce ATTESTATION_HASH_MISMATCH."""
    _seed_attestation(tmp_path, archive_root, attestation_id="att-1")
    att_path = archive_root / "attestations" / "att-1.json"
    data = json.loads(att_path.read_text(encoding="utf-8"))
    data["attestation_hash"] = "c" * 64
    att_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

    report = verify_derived_integrity(archive_root)
    assert not report.ok
    kinds = {
        i.issue_kind
        for i in report.issues
        if i.artifact_id == "att-1"
    }
    assert IntegrityIssueKind.ATTESTATION_HASH_MISMATCH.value in kinds


def test_attestation_decode_error_is_reported(
    tmp_path: Path, archive_root: Path
) -> None:
    """Un JSON malformado en attestations/ produce DECODE_ERROR."""
    _seed_workspace(tmp_path, archive_root)
    att_dir = archive_root / "attestations"
    att_dir.mkdir(parents=True, exist_ok=True)
    (att_dir / "broken.json").write_text("{not json", encoding="utf-8")

    report = verify_derived_integrity(archive_root)
    assert not report.ok
    decode_issues = [
        i
        for i in report.issues
        if i.issue_kind == IntegrityIssueKind.DECODE_ERROR.value
        and i.artifact_id == "broken"
    ]
    assert len(decode_issues) == 1


# ---------------------------------------------------------------- G_E16_a


def test_workspace_without_audit_entry_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Workspace puesto a mano (sin pasar por persist_workspace) produce
    MISSING_AUDIT_ENTRY — la API auditada nunca lo emitió. El workspace
    es internamente consistente (self-hash OK), aislando la garantía."""
    ev_hash, _w = _seed_workspace(tmp_path, archive_root)

    # Construir un workspace internamente consistente con id distinto.
    w_rogue = create_workspace(
        archive_root=archive_root,
        workspace_id="w-rogue",
        title="rogue",
        references_input=[("evidence", ev_hash)],
    )
    assert verify_workspace_hash(w_rogue)
    # Escribir directamente en el path canónico SIN pasar por
    # persist_workspace → no se emite entry de audit log.
    dst = archive_root / "workspaces" / "w-rogue.json"
    dst.write_text(encode_workspace(w_rogue), encoding="utf-8")

    report = verify_derived_integrity(archive_root)
    rogue_issues = [
        i for i in report.issues if i.artifact_id == "w-rogue"
    ]
    assert any(
        i.issue_kind == IntegrityIssueKind.MISSING_AUDIT_ENTRY.value
        for i in rogue_issues
    )


# ---------------------------------------------------------------- G_E16_b


def test_workspace_deleted_after_audit_entry_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Borrar workspace.json deja la entry BUILD_WORKSPACE huérfana →
    MISSING_PERSISTED_ARTIFACT."""
    _seed_workspace(tmp_path, archive_root)
    (archive_root / "workspaces" / "w-01.json").unlink()

    report = verify_derived_integrity(archive_root)
    assert not report.ok
    assert any(
        i.issue_kind
        == IntegrityIssueKind.MISSING_PERSISTED_ARTIFACT.value
        and i.artifact_kind == "workspace"
        and i.artifact_id == "w-01"
        for i in report.issues
    )


def test_attestation_deleted_after_audit_entry_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Borrar attestation.json tras emitir SIGN_ATTESTATION →
    MISSING_PERSISTED_ARTIFACT para attestation."""
    _seed_attestation(tmp_path, archive_root, attestation_id="att-x")
    (archive_root / "attestations" / "att-x.json").unlink()

    report = verify_derived_integrity(archive_root)
    assert any(
        i.issue_kind
        == IntegrityIssueKind.MISSING_PERSISTED_ARTIFACT.value
        and i.artifact_kind == "attestation"
        and i.artifact_id == "att-x"
        for i in report.issues
    )


# ---------------------------------------------------------------- G_E16_c


def test_workspace_replaced_with_different_content_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Sustituir el archivo del workspace por uno con distinto self-hash
    sin re-emitir entry → AUDIT_LOG_HASH_MISMATCH."""
    _seed_workspace(tmp_path, archive_root)
    src = archive_root / "workspaces" / "w-01.json"

    # Construir un workspace alternativo coherente internamente
    # (auto-consistent) pero con distinto contenido + hash.
    blob_b = tmp_path / "doc-b.pdf"
    blob_b.write_bytes(b"%PDF-1.4 different bytes")
    ev_hash_b = _ingest(archive_root, blob_b)
    w_alt = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="alt",  # distinto título → distinto hash
        references_input=[("evidence", ev_hash_b)],
    )
    # Escribir directamente al path sin pasar por persist_workspace
    # (que emitiría una nueva entry y "limpiaría" el mismatch).
    src.write_text(encode_workspace(w_alt), encoding="utf-8")

    report = verify_derived_integrity(archive_root)
    assert not report.ok
    mismatch_issues = [
        i
        for i in report.issues
        if i.issue_kind
        == IntegrityIssueKind.AUDIT_LOG_HASH_MISMATCH.value
        and i.artifact_id == "w-01"
    ]
    assert len(mismatch_issues) == 1


def test_attestation_replaced_with_different_signature_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Sustituir una atestación por otra (mismo id, distinto
    attestation_hash) sin re-emitir entry → AUDIT_LOG_HASH_MISMATCH.

    Este escenario es el motivo central de E16 sobre ADR-0041: una
    atestación reemplazada silenciosamente queda detectada por la
    cadena auditada, aunque la atestación nueva sea internamente
    consistente y verifique self_hash.
    """
    att_original = _seed_attestation(
        tmp_path, archive_root, attestation_id="att-y"
    )
    # Forjar otra atestación con el mismo id pero distinto artifact_hash:
    # creamos un workspace alternativo y volvemos a firmar.
    w_alt = create_workspace(
        archive_root=archive_root,
        workspace_id="w-alt",
        title="other",
        references_input=[],
    )
    persist_workspace(
        w_alt, archive_root=archive_root, actor="@op", clock=_clock(TS)
    )
    ws_alt_path = archive_root / "workspaces" / "w-alt.json"

    priv, _pub = generate_keypair()
    att_new = sign_artifact(
        artifact_kind="workspace",
        artifact_path=ws_alt_path,
        private_key=priv,
        signer_id="@op",
        signed_at=TS,
    )
    assert att_new.attestation_hash != att_original.attestation_hash
    # Sobrescribir att-y.json sin pasar por persist_attestation.
    (archive_root / "attestations" / "att-y.json").write_text(
        encode_attestation(att_new), encoding="utf-8"
    )

    report = verify_derived_integrity(archive_root)
    assert not report.ok
    assert any(
        i.issue_kind
        == IntegrityIssueKind.AUDIT_LOG_HASH_MISMATCH.value
        and i.artifact_kind == "attestation"
        and i.artifact_id == "att-y"
        for i in report.issues
    )


# ---------------------------------------------------------------- assessment reconciliation


def test_assessment_row_reconciled_via_evidence_id(
    tmp_path: Path, archive_root: Path
) -> None:
    """ASSESS_AUTHENTICATION emite entry con self_hash=evidence_id.
    Un archive con assessment + ingest debe pasar reconciliación."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_clock(TS),
        actor="@reviewer",
    )
    report = verify_derived_integrity(archive_root)
    assert report.assessments_checked == 1
    # No issues de reconciliación para el assessment.
    assert not any(
        i.artifact_kind == "assessment" for i in report.issues
    )


# ---------------------------------------------------------------- clean state


def test_clean_full_archive_with_attestation_no_issues(
    tmp_path: Path, archive_root: Path
) -> None:
    """Un archive con ingest + assessment + workspace + attestation
    completos no produce ninguna incidencia en el reporte."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash, clock=_clock(TS), actor="@r"
    )
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-clean",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(
        w, archive_root=archive_root, actor="@op", clock=_clock(TS)
    )
    priv, _pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=archive_root / "workspaces" / "w-clean.json",
        private_key=priv,
        signer_id="@op",
        signed_at=TS,
    )
    persist_attestation(
        att,
        archive_root=archive_root,
        attestation_id="att-clean",
        actor="@op",
        clock=_clock(TS),
    )
    report = verify_derived_integrity(archive_root)
    assert report.ok, [i for i in report.issues]
    assert report.workspaces_checked == 1
    assert report.attestations_checked == 1
    assert report.assessments_checked == 1
