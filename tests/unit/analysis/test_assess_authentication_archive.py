"""Tests del método ``Archive.assess_authentication`` (ADR-0032 §4).

Cubre la orquestación completa:

- Lectura del estado del archive (Evidence + Source + Provenance).
- Aplicación de la regla determinista.
- Persistencia en la tabla ``authentication_assessments``.
- Recomputo del manifest.
- Garantías de no-mutación de Evidence/Source/Provenance/audit (G4 del ADR).
- Idempotencia y determinismo bit a bit.
"""

from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import (
    Archive,
    ArchiveNotFoundError,
    EvidenceNotFoundError,
)
from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import (
    AssessmentMethod,
    AssessmentStatus,
    AuthenticationAssessment,
)
from aip.audit import log as audit_log
from aip.audit.log import iter_entries
from aip.core.evidence import Evidence, EvidenceKind, EvidenceStatus
from aip.core.source import AuthorityLevel, Source, SourceKind
from aip.storage import layout, tables
from aip.storage.manifest import compute_manifest, write_manifest_atomic

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
LATER_TS = dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------- helpers


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest_basic(
    archive_root: Path,
    blob: Path,
    *,
    clock: Callable[[], dt.datetime] | None = None,
):
    archive = Archive.open(archive_root)
    return archive.ingest_evidence(
        blob,
        source_id="blue-book-nara",
        source_name="Project Blue Book records",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@jfhelvetius",
        clock=clock,
    )


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- happy path


def test_assess_returns_supported_for_ingested_evidence(tmp_path: Path, archive_root: Path) -> None:
    # Después de ingest, Evidence tiene Source + Provenance con 1 paso →
    # SUPPORTED por construcción.
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    assessment = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )

    assert assessment.status == AssessmentStatus.SUPPORTED
    assert assessment.evidence_id == evidence.hash
    assert assessment.supporting_source_ids == ["blue-book-nara"]
    assert assessment.method == AssessmentMethod.PROVENANCE_REVIEW
    assert assessment.created_at == LATER_TS


def test_assess_persists_row_in_assessments_table(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    assessment = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )

    # La fila existe en disco bajo el row_id determinista.
    row = tables.read_row(archive_root, "authentication_assessments", assessment.assessment_id)
    assert row is not None
    # Roundtrip por el modelo (Parquet → JCS payload → model).
    parsed = AuthenticationAssessment.model_validate(row)
    assert parsed == assessment


def test_assess_updates_manifest(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    manifest_before = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    manifest_after = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    assert manifest_before != manifest_after

    # Verify sigue OK tras el assessment (manifest readable + consistente).
    report = archive.verify(full=True)
    assert report.ok is True


def test_assess_accepts_aip_uri_and_sha256_prefix(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)

    a_hex = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    a_prefix = archive.assess_authentication(
        evidence_id=f"sha256:{evidence.hash}", clock=_fixed_clock(LATER_TS), actor="@test"
    )
    a_uri = archive.assess_authentication(
        evidence_id=f"aip:evidence/sha256:{evidence.hash}",
        clock=_fixed_clock(LATER_TS),
        actor="@test",
    )
    # Misma identidad determinista regardless of forma del input.
    assert a_hex.assessment_id == a_prefix.assessment_id == a_uri.assessment_id


# ---------------------------------------------------------------- rule branches via archive


def test_assess_contradicted_when_source_row_missing(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    # Removemos manualmente la fila de Source (sin tocar Evidence/Provenance/audit).
    source_path = archive_root / "tables" / "sources" / "blue-book-nara.parquet"
    assert source_path.is_file()
    source_path.unlink()

    archive = Archive.open(archive_root)
    assessment = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    # La Provenance referencia origin_source_id="blue-book-nara" que ya no
    # existe → referencia rota → CONTRADICTED domina.
    assert assessment.status == AssessmentStatus.CONTRADICTED
    assert assessment.supporting_source_ids == []


def test_assess_partially_supported_when_provenance_has_no_steps(
    tmp_path: Path, archive_root: Path
) -> None:
    # Construimos manualmente un archive con Evidence + Source pero sin
    # Provenance: hay fuente, no hay pasos, referencias intactas.
    layout.ensure_archive_layout(archive_root)
    audit_log.bootstrap(
        archive_root,
        actor="@jfhelvetius",
        clock=_fixed_clock(CANONICAL_TS),
        schema_version=SCHEMA_VERSION,
    )

    source = Source(
        id="blue-book-nara",
        kind=SourceKind.GOVERNMENT_ARCHIVE,
        name="Project Blue Book records",
        authority=AuthorityLevel.SECONDARY,
        jurisdiction="US",
        license="public_domain",
    )
    tables.append_row(archive_root, "sources", source.id, source.model_dump(mode="json"))

    # Fabricamos una Evidence sintética (sin pasar por ingest_evidence).
    fake_hash = "b" * 64
    fake_blob = archive_root / "objects" / "sha256" / "bb" / ("b" * 62)
    fake_blob.parent.mkdir(parents=True, exist_ok=True)
    fake_blob.write_bytes(b"")
    evidence = Evidence(
        hash=fake_hash,
        kind=EvidenceKind.DOCUMENT_TEXT,
        content_uri=f"objects/sha256/bb/{'b' * 62}",
        size_bytes=0,
        mime_type="text/plain",
        source_id=source.id,
        status=EvidenceStatus.ACTIVE,
        ingested_at=CANONICAL_TS,
        ingested_by="@jfhelvetius",
        schema_version=SCHEMA_VERSION,
    )
    tables.append_row(archive_root, "evidence", fake_hash, evidence.model_dump(mode="json"))

    # Manifest mínimo para que is_archive sea True.
    manifest = compute_manifest(
        archive_root,
        schemas=tables.get_schemas(),
        generated_at=CANONICAL_TS,
        software_version="0.0.1",
        schema_version=SCHEMA_VERSION,
    )
    write_manifest_atomic(archive_root / layout.MANIFEST_FILENAME, manifest)

    archive = Archive.open(archive_root)
    assessment = archive.assess_authentication(
        evidence_id=fake_hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    assert assessment.status == AssessmentStatus.PARTIALLY_SUPPORTED
    assert assessment.supporting_source_ids == ["blue-book-nara"]


# ---------------------------------------------------------------- error paths


def test_assess_raises_archive_not_found_when_root_missing(
    tmp_path: Path,
) -> None:
    archive = Archive.open(tmp_path / "does-not-exist")
    with pytest.raises(ArchiveNotFoundError):
        archive.assess_authentication(evidence_id="a" * 64, actor="@test")


def test_assess_raises_archive_not_found_when_not_an_archive(
    archive_root: Path,
) -> None:
    # Directorio existe pero sin la estructura canónica → no es archive.
    archive = Archive.open(archive_root)
    with pytest.raises(ArchiveNotFoundError):
        archive.assess_authentication(evidence_id="a" * 64, actor="@test")


def test_assess_raises_evidence_not_found(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)
    with pytest.raises(EvidenceNotFoundError):
        archive.assess_authentication(evidence_id="c" * 64, actor="@test")


def test_assess_rejects_invalid_evidence_id() -> None:
    archive = Archive.open(Path("/nonexistent"))
    with pytest.raises(ArchiveNotFoundError):
        # Archive not found gana antes incluso de validar el hash; cubrimos
        # ese contrato en lugar de inventar archive válido sólo para el hash.
        archive.assess_authentication(evidence_id="not-a-hash", actor="@test")


# ---------------------------------------------------------------- determinism + idempotency


def test_assess_is_deterministic_bit_for_bit(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)

    a = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    b = archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    # Bit a bit: misma identidad, mismo payload canónico.
    assert a == b
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_re_assess_same_archive_is_idempotent_on_disk(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )

    row_path = (
        archive_root
        / "tables"
        / "authentication_assessments"
        / f"{evidence.hash}__provenance_review.parquet"
    )
    bytes_before = row_path.read_bytes()

    # Segunda invocación con clock inyectado distinto: como el payload
    # incluye created_at, el row_hash cambia y se reescribe el fichero —
    # pero el assessment_id es el mismo (no se duplica la fila).
    archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    bytes_after = row_path.read_bytes()
    # Mismo clock ⇒ mismo payload ⇒ idempotencia (no-op) en append_row.
    assert bytes_before == bytes_after


def test_re_assess_with_different_method_creates_separate_row(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)

    a = archive.assess_authentication(
        evidence_id=evidence.hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_fixed_clock(LATER_TS),
        actor="@test",
    )
    b = archive.assess_authentication(
        evidence_id=evidence.hash,
        method=AssessmentMethod.MANUAL_RESEARCH,
        clock=_fixed_clock(LATER_TS),
        actor="@test",
    )
    assert a.assessment_id != b.assessment_id
    # Hay dos filas en la tabla.
    table_dir = archive_root / "tables" / "authentication_assessments"
    assert len(list(table_dir.glob("*.parquet"))) == 2


# ---------------------------------------------------------------- G4: removability


def test_deleting_assessment_does_not_affect_evidence(tmp_path: Path, archive_root: Path) -> None:
    """G4 (ADR-0032 §1, refinado por ADR-0019 §enmienda E1): borrar el
    row.parquet de un assessment nunca modifica Evidence/Source/Provenance.

    El audit log SÍ cambia (creció con la entry ``ASSESS_AUTHENTICATION``)
    y NO se borra cuando se elimina el row.parquet — eso es exactamente
    lo que un audit log append-only debe hacer: registrar lo que pasó,
    incluso si después se revierte el estado derivado.
    """
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    def snapshot_base_tables() -> dict[str, bytes]:
        snap: dict[str, bytes] = {}
        for table in ("evidence", "sources", "provenance", "provenance_steps"):
            table_dir = archive_root / "tables" / table
            for entry in sorted(table_dir.glob("*.parquet")):
                snap[f"{table}/{entry.name}"] = entry.read_bytes()
        return snap

    before_base = snapshot_base_tables()
    audit_before = list(iter_entries(archive_root))
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash,
        clock=_fixed_clock(LATER_TS),
        actor="@test",
    )
    audit_after_assess = list(iter_entries(archive_root))

    # Borrar todo el directorio de assessments.
    shutil.rmtree(archive_root / "tables" / "authentication_assessments")
    (archive_root / "tables" / "authentication_assessments").mkdir()

    after_base = snapshot_base_tables()
    audit_after_delete = list(iter_entries(archive_root))

    assert before_base == after_base, (
        "Evidence/Source/Provenance cambiaron tras crear+borrar un assessment: G4 violada."
    )
    # El audit log creció con la entry ASSESS_AUTHENTICATION y no se borró.
    assert len(audit_after_assess) == len(audit_before) + 1
    assert audit_after_delete == audit_after_assess
    assert audit_after_assess[-1].action == audit_log.ActionKind.ASSESS_AUTHENTICATION


def test_assessment_emits_audit_log_entry(tmp_path: Path, archive_root: Path) -> None:
    """ADR-0019 §enmienda E1: ``assess_authentication`` emite exactamente
    una entry ``ASSESS_AUTHENTICATION`` con el actor pasado por el
    operador, ancló el ``evidence_id`` como ``self_hash`` y la cadena
    hash-encadenada extiende el `prev_hash` desde la última entry.
    """
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    entries_before = list(iter_entries(archive_root))
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash,
        clock=_fixed_clock(LATER_TS),
        actor="@reviewer",
    )
    entries_after = list(iter_entries(archive_root))

    assert len(entries_after) == len(entries_before) + 1
    new_entry = entries_after[-1]
    assert new_entry.action == audit_log.ActionKind.ASSESS_AUTHENTICATION
    assert new_entry.actor == "@reviewer"
    assert new_entry.parameters["self_hash"] == evidence.hash
    assert new_entry.prev_hash == entries_before[-1].entry_hash


# ---------------------------------------------------------------- list


def test_list_assessments_returns_only_for_requested_evidence(
    tmp_path: Path, archive_root: Path
) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    ev_a = _ingest_basic(archive_root, blob_a, clock=_fixed_clock(CANONICAL_TS))
    ev_b = _ingest_basic(archive_root, blob_b, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=ev_a.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    archive.assess_authentication(
        evidence_id=ev_b.hash, clock=_fixed_clock(LATER_TS), actor="@test"
    )
    archive.assess_authentication(
        evidence_id=ev_a.hash,
        method=AssessmentMethod.MANUAL_RESEARCH,
        clock=_fixed_clock(LATER_TS),
        actor="@test",
    )

    found_a = archive.list_authentication_assessments(ev_a.hash)
    found_b = archive.list_authentication_assessments(ev_b.hash)
    assert len(found_a) == 2
    assert len(found_b) == 1
    # Orden estable por assessment_id.
    assert found_a[0].assessment_id < found_a[1].assessment_id


def test_list_assessments_empty_when_none(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    archive = Archive.open(archive_root)
    assert archive.list_authentication_assessments(evidence.hash) == ()
