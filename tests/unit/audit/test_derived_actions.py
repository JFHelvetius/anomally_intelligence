"""Tests del contrato ADR-0019 §enmienda E1 — audit chain archive-wide.

Verifica que las 6 acciones derivadas:

- ``ASSESS_AUTHENTICATION``, ``BUILD_WORKSPACE``, ``BUILD_TIMELINE``,
  ``BUILD_SNAPSHOT``, ``BUILD_JUSTIFICATION``, ``SIGN_ATTESTATION``

cumplen las tres garantías estructurales:

G_E1_a — cada persistencia derivada añade exactamente UNA entry.
G_E1_b — la cadena hash-encadenada cubre las 6 acciones y se rompe si
         alguna entry se altera (tampering detectado por el verifier
         existente).
G_E1_c — el ``audit_log_head_hash`` cambia con cada operación derivada;
         dos archives con misma evidencia base pero distintos derivados
         producen heads distintos (= archive-state fingerprint completo).

Tests adicionales:

- ``record_derived_artifact`` rechaza ActionKinds de la capa base.
- ``manifest_hash`` permanece invariante ante operaciones de capa
  derivada (regla S15 / S16: directorios periféricos fuera de V1_TABLES).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.attestation import (
    generate_keypair,
    persist_attestation,
    sign_artifact,
)
from aip.audit.log import (
    ActionKind,
    iter_entries,
    last_entry,
    record_derived_artifact,
)
from aip.audit.verify import verify_chain
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.justification import build_justification, persist_justification
from aip.snapshot import create_snapshot, persist_snapshot
from aip.timeline import build_timeline, persist_timeline
from aip.workspace import create_workspace, persist_workspace

UTC = dt.UTC
T0 = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 6, 4, 0, 1, 0, tzinfo=UTC)


def _clock(ts: dt.datetime):
    return lambda: ts


def _seed_evidence(archive_root: Path, tmp_path: Path) -> str:
    """Ingiere una Evidence base y devuelve su hash.

    El fixture ``archive_root`` da un directorio vacío; ``Archive.open`` +
    ``ingest_evidence`` hace el auto-bootstrap (escribe bootstrap + ingest
    en el audit log).
    """
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
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
        clock=_clock(T0),
    )
    return ev.hash


# ---------------------------------------------------------------- G_E1_a


def test_assess_authentication_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    before = len(list(iter_entries(archive_root)))
    Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash, actor="@reviewer", clock=_clock(T1)
    )
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    entry = after[-1]
    assert entry.action == ActionKind.ASSESS_AUTHENTICATION
    assert entry.actor == "@reviewer"
    assert entry.parameters["self_hash"] == ev_hash
    assert entry.parameters["method"] == AssessmentMethod.PROVENANCE_REVIEW.value


def test_persist_workspace_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    before = len(list(iter_entries(archive_root)))
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w1",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@author", clock=_clock(T1))
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    entry = after[-1]
    assert entry.action == ActionKind.BUILD_WORKSPACE
    assert entry.actor == "@author"
    assert entry.parameters["self_hash"] == ws.workspace_hash
    assert entry.target == f"aip:workspace/{ws.workspace_id}"


def test_persist_timeline_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w1",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@a", clock=_clock(T1))
    tl = build_timeline(archive_root=archive_root, workspace=ws, timeline_id="tl1")
    before = len(list(iter_entries(archive_root)))
    persist_timeline(tl, archive_root=archive_root, actor="@author", clock=_clock(T1))
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    assert after[-1].action == ActionKind.BUILD_TIMELINE
    assert after[-1].parameters["self_hash"] == tl.timeline_hash


def test_persist_snapshot_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w1",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@a", clock=_clock(T1))
    tl = build_timeline(archive_root=archive_root, workspace=ws, timeline_id="tl1")
    persist_timeline(tl, archive_root=archive_root, actor="@a", clock=_clock(T1))
    snap = create_snapshot(snapshot_id="s1", workspace=ws, timeline=tl)
    before = len(list(iter_entries(archive_root)))
    persist_snapshot(snap, archive_root=archive_root, actor="@author", clock=_clock(T1))
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    assert after[-1].action == ActionKind.BUILD_SNAPSHOT


def test_persist_justification_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    a = Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash, actor="@r", clock=_clock(T1)
    )
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a.assessment_id,
        justification_id="j1",
    )
    before = len(list(iter_entries(archive_root)))
    persist_justification(j, archive_root=archive_root, actor="@author", clock=_clock(T1))
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    assert after[-1].action == ActionKind.BUILD_JUSTIFICATION
    assert after[-1].parameters["self_hash"] == j.justification_hash


def test_persist_attestation_appends_exactly_one_audit_entry(
    tmp_path: Path, archive_root: Path
) -> None:
    ev_hash = _seed_evidence(archive_root, tmp_path)
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w1",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@a", clock=_clock(T1))
    ws_path = archive_root / "workspaces" / "w1.json"
    priv, _pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=ws_path,
        private_key=priv,
        signer_id="@op",
        signed_at=T1,
    )
    before = len(list(iter_entries(archive_root)))
    persist_attestation(
        att,
        archive_root=archive_root,
        attestation_id="att-1",
        actor="@op",
        clock=_clock(T1),
    )
    after = list(iter_entries(archive_root))
    assert len(after) == before + 1
    entry = after[-1]
    assert entry.action == ActionKind.SIGN_ATTESTATION
    assert entry.parameters["self_hash"] == att.attestation_hash
    assert entry.parameters["signer_id"] == "@op"
    assert "public_key_fingerprint" in entry.parameters


# ---------------------------------------------------------------- G_E1_b


def test_audit_chain_covers_derived_actions_and_verifies(
    tmp_path: Path, archive_root: Path
) -> None:
    """Tras una secuencia de 5 operaciones derivadas, la cadena verifica."""
    ev_hash = _seed_evidence(archive_root, tmp_path)
    arc = Archive.open(archive_root)
    arc.assess_authentication(evidence_id=ev_hash, actor="@r", clock=_clock(T1))
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@r", clock=_clock(T1))
    tl = build_timeline(archive_root=archive_root, workspace=ws, timeline_id="t1")
    persist_timeline(tl, archive_root=archive_root, actor="@r", clock=_clock(T1))
    snap = create_snapshot(snapshot_id="s", workspace=ws, timeline=tl)
    persist_snapshot(snap, archive_root=archive_root, actor="@r", clock=_clock(T1))

    result = verify_chain(archive_root)
    assert result.ok
    # bootstrap + ingest + 4 derived = 6 entries
    assert result.total_entries == 6


def test_audit_chain_tampering_in_derived_entry_is_detected(
    tmp_path: Path, archive_root: Path
) -> None:
    """Si se altera el ``actor`` de una entry derivada en disco, el
    verifier la detecta porque el ``entry_hash`` ya no coincide."""
    ev_hash = _seed_evidence(archive_root, tmp_path)
    Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash, actor="@original", clock=_clock(T1)
    )
    log_path = archive_root / "audit.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    # Edita la última entry (la ASSESS_AUTHENTICATION).
    last_obj = json.loads(lines[-1])
    last_obj["actor"] = "@evil"
    lines[-1] = json.dumps(last_obj, ensure_ascii=False)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain(archive_root)
    assert not result.ok
    assert result.first_failure_seq == 2  # bootstrap(0) + ingest(1) + assess(2)


# ---------------------------------------------------------------- G_E1_c


def test_audit_log_head_differs_when_derived_operations_differ(
    tmp_path: Path, archive_root: Path
) -> None:
    """Dos archives con misma evidencia base pero distintos derivados
    producen ``audit_log_head_hash`` distintos. Esto es exactamente la
    propiedad que convierte el log en archive-state fingerprint."""
    # Archive A — sólo ingest + assessment.
    ev_hash_a = _seed_evidence(archive_root, tmp_path)
    Archive.open(archive_root).assess_authentication(
        evidence_id=ev_hash_a, actor="@r", clock=_clock(T1)
    )
    head_a = last_entry(archive_root)
    assert head_a is not None

    # Archive B — misma ingest + assessment + workspace persistido.
    archive_b = tmp_path / "archive_b"
    archive_b.mkdir()
    ev_hash_b = _seed_evidence(archive_b, tmp_path)
    assert ev_hash_a == ev_hash_b  # blob es bit-idéntico, mismo hash.
    Archive.open(archive_b).assess_authentication(
        evidence_id=ev_hash_b, actor="@r", clock=_clock(T1)
    )
    ws = create_workspace(
        archive_root=archive_b,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash_b)],
    )
    persist_workspace(ws, archive_root=archive_b, actor="@r", clock=_clock(T1))
    head_b = last_entry(archive_b)
    assert head_b is not None

    assert head_a.entry_hash != head_b.entry_hash, (
        "archive_log_head_hash debería diferenciar archives con distintos "
        "derivados; el log sólo es un fingerprint si refleja el estado real."
    )


# ---------------------------------------------------------------- helper guard


def test_record_derived_artifact_rejects_base_actionkinds(
    tmp_path: Path,
) -> None:
    """``record_derived_artifact`` sólo acepta ActionKinds de la capa
    derivada. Pasar ``INGEST_EVIDENCE`` o ``ARCHIVE_BOOTSTRAP`` debe
    fallar — son responsabilidad de la API de capa base."""
    archive = tmp_path / "arc"
    archive.mkdir()
    with pytest.raises(ValueError, match="derived ActionKind"):
        record_derived_artifact(
            archive,
            action=ActionKind.INGEST_EVIDENCE,
            artifact_kind="evidence",
            artifact_id="x",
            self_hash="a" * 64,
            actor="@x",
            clock=_clock(T1),
            schema_version="0.1.0",
        )
    with pytest.raises(ValueError, match="derived ActionKind"):
        record_derived_artifact(
            archive,
            action=ActionKind.ARCHIVE_BOOTSTRAP,
            artifact_kind="x",
            artifact_id="x",
            self_hash="a" * 64,
            actor="@x",
            clock=_clock(T1),
            schema_version="0.1.0",
        )


# ---------------------------------------------------------------- manifest invariance


def test_derived_audit_entries_do_not_modify_manifest_hash(
    tmp_path: Path, archive_root: Path
) -> None:
    """E1 promete: emitir audit entries derivadas no altera
    ``archive_manifest_hash``. El manifest sólo canonicaliza tables +
    blobs; el audit log es una capa cripto paralela."""
    ev_hash = _seed_evidence(archive_root, tmp_path)
    manifest_path = archive_root / "manifest.json"
    pre_hash = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Crear un workspace (no toca tablas V1).
    ws = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(ws, archive_root=archive_root, actor="@x", clock=_clock(T1))
    post_hash = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert pre_hash == post_hash, "BUILD_WORKSPACE no debe alterar manifest.json (S11 + S16)."
