"""Tests unitarios de ``aip.archive`` (API Python pública)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import (
    Archive,
    ArchiveNotFoundError,
    EvidenceNotFoundError,
    InvalidSourceMetadataError,
)
from aip.audit.log import count_entries, iter_entries
from aip.core.evidence import EvidenceKind, EvidenceStatus
from aip.core.source import AuthorityLevel, SourceKind

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


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


# ---------------------------------------------------------------- ingest


def test_ingest_creates_archive_layout_and_evidence(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    assert evidence.kind == EvidenceKind.DOCUMENT_SCAN
    assert evidence.size_bytes == len(b"%PDF-1.4 sample")
    assert evidence.status == EvidenceStatus.ACTIVE
    assert evidence.ingested_by == "@jfhelvetius"
    assert evidence.ingested_at == CANONICAL_TS
    assert evidence.schema_version == "0.1.0"

    # Blob copiado a CAOS.
    blob_path = archive_root / "objects" / "sha256" / evidence.hash[:2] / evidence.hash[2:]
    assert blob_path.is_file()
    assert blob_path.read_bytes() == b"%PDF-1.4 sample"

    # Manifest emitido.
    assert (archive_root / "manifest.json").is_file()

    # Audit log con bootstrap + ingest.
    entries = list(iter_entries(archive_root))
    assert len(entries) == 2
    assert entries[0].action.value == "archive_bootstrap"
    assert entries[1].action.value == "ingest_evidence"
    assert entries[1].target == evidence.aip_uri()


def test_ingest_is_idempotent(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    first = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    second = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))
    assert first.hash == second.hash

    # No se duplican audit entries (1 bootstrap + 1 ingest = 2).
    assert count_entries(archive_root) == 2


def test_ingest_dry_run_writes_nothing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"hello")
    archive = Archive.open(archive_root)
    evidence = archive.ingest_evidence(
        blob,
        source_id="blue-book-nara",
        source_name="Project Blue Book records",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@jfhelvetius",
        dry_run=True,
        clock=_fixed_clock(CANONICAL_TS),
    )
    assert evidence.size_bytes == 5
    # Nada escrito.
    assert not (archive_root / "manifest.json").exists()
    assert not (archive_root / "audit.log").exists()
    assert not list((archive_root / "objects" / "sha256").iterdir()) if (
        archive_root / "objects" / "sha256"
    ).is_dir() else True


def test_ingest_requires_source_metadata_when_new(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"x")
    archive = Archive.open(archive_root)
    with pytest.raises(InvalidSourceMetadataError):
        archive.ingest_evidence(
            blob,
            source_id="never-seen",
            ingested_by="@x",
            clock=_fixed_clock(CANONICAL_TS),
        )


def test_ingest_rejects_inconsistent_existing_source(
    tmp_path: Path, archive_root: Path
) -> None:
    blob1 = _write_blob(tmp_path, "a.pdf", b"AAA")
    blob2 = _write_blob(tmp_path, "b.pdf", b"BBB")
    _ingest_basic(archive_root, blob1, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    with pytest.raises(InvalidSourceMetadataError, match="contradicts"):
        archive.ingest_evidence(
            blob2,
            source_id="blue-book-nara",
            source_name="Different Name",  # contradice la registrada
            source_kind=SourceKind.GOVERNMENT_ARCHIVE,
            source_authority=AuthorityLevel.SECONDARY,
            evidence_kind=EvidenceKind.DOCUMENT_SCAN,
            mime_type="application/pdf",
            ingested_by="@jfhelvetius",
            clock=_fixed_clock(CANONICAL_TS),
        )


def test_ingest_missing_file_raises(archive_root: Path) -> None:
    archive = Archive.open(archive_root)
    with pytest.raises(FileNotFoundError):
        archive.ingest_evidence(
            Path("does-not-exist.pdf"),
            source_id="x",
            source_name="x",
            source_kind=SourceKind.UNKNOWN,
            source_authority=AuthorityLevel.UNATTRIBUTABLE,
            ingested_by="@x",
            clock=_fixed_clock(CANONICAL_TS),
        )


# ---------------------------------------------------------------- show


def test_show_returns_full_view(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    view = archive.show_evidence(evidence.hash)

    assert view.evidence.hash == evidence.hash
    assert view.source.id == "blue-book-nara"
    assert view.provenance is not None
    assert len(view.provenance_steps) == 1
    assert view.provenance_steps[0].step_id == 1


def test_show_accepts_uri_form(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"hello")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    view = archive.show_evidence(f"aip:evidence/sha256:{evidence.hash}")
    assert view.evidence.hash == evidence.hash


def test_show_accepts_sha256_prefix(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"hello")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    view = archive.show_evidence(f"sha256:{evidence.hash}")
    assert view.evidence.hash == evidence.hash


def test_show_evidence_not_found(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"hi")
    _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    with pytest.raises(EvidenceNotFoundError):
        archive.show_evidence("0" * 64)


def test_show_archive_not_found(tmp_path: Path) -> None:
    archive = Archive.open(tmp_path / "ghost")
    with pytest.raises(ArchiveNotFoundError):
        archive.show_evidence("0" * 64)


# ---------------------------------------------------------------- verify


def test_verify_empty_archive_reports_failure(archive_root: Path) -> None:
    # Sin bootstrap → no es archive válido (no hay audit.log ni manifest.json).
    archive = Archive.open(archive_root)
    with pytest.raises(ArchiveNotFoundError):
        archive.verify()


def test_verify_after_ingest_ok(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    assert report.ok is True
    assert report.counts["evidences"] == 1
    assert report.counts["sources"] == 1
    assert report.counts["audit_entries"] == 2


def test_verify_detects_blob_tampering(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    # Tampering del blob bajo CAOS.
    blob_path = archive_root / "objects" / "sha256" / evidence.hash[:2] / evidence.hash[2:]
    blob_path.write_bytes(b"tampered content")

    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    assert report.ok is False
    blobs_check = next(c for c in report.checks if c.name == "blobs")
    assert blobs_check.ok is False


def test_verify_quick_skips_blob_rehash(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"hi")
    _ingest_basic(archive_root, blob, clock=_fixed_clock(CANONICAL_TS))

    archive = Archive.open(archive_root)
    report = archive.verify(full=False)
    assert report.ok is True
    blobs_check = next(c for c in report.checks if c.name == "blobs")
    assert "skipped" in blobs_check.detail
