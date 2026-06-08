"""Tests de detección de tampering del contenido del manifest (P4)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

from aip import Archive
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.storage import layout

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path) -> str:
    archive = Archive.open(archive_root)
    ev = archive.ingest_evidence(
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
        clock=_clock(CANONICAL_TS),
    )
    return ev.hash


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _load_manifest(archive_root: Path) -> dict[str, object]:
    return json.loads((archive_root / layout.MANIFEST_FILENAME).read_text(encoding="utf-8"))


def _save_manifest(archive_root: Path, data: dict[str, object]) -> None:
    (archive_root / layout.MANIFEST_FILENAME).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------- clean


def test_clean_archive_passes_content_check(tmp_path: Path, archive_root: Path) -> None:
    """Backward compat: archive limpio sigue pasando."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    assert report.ok is True
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is True
    assert "matches" in manifest_check.detail


# ---------------------------------------------------------------- tampering


def test_detects_row_count_tampering(tmp_path: Path, archive_root: Path) -> None:
    """Cambiar row_count de una tabla sin tocar los parquet files."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    # Tamper: row_count de evidence pasa de 1 a 0.
    data["tables"]["evidence"]["row_count"] = 0  # type: ignore[index]
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "row_count" in manifest_check.detail
    assert "DIVERGES" in manifest_check.detail


def test_detects_schema_hash_tampering(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    data["tables"]["evidence"]["schema_hash"] = "0" * 64  # type: ignore[index]
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "schema_hash" in manifest_check.detail


def test_detects_table_removed_from_manifest(tmp_path: Path, archive_root: Path) -> None:
    """Quitar una entrada de tables.{} para ocultar tabla del manifest."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    tables = data["tables"]
    assert isinstance(tables, dict)
    # Eliminar authentication_assessments (presente como tabla V1 vacía).
    del tables["authentication_assessments"]
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "tables.keys mismatch" in manifest_check.detail
    assert "missing" in manifest_check.detail


def test_detects_blobs_root_tampering(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    data["blobs_root"] = "f" * 64
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "blobs_root" in manifest_check.detail


def test_detects_schema_version_tampering(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    data["schema_version"] = "99.99.99"
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "schema_version" in manifest_check.detail


def test_detects_notes_tampering(tmp_path: Path, archive_root: Path) -> None:
    """Añadir notes arbitrarios al manifest persistido."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    data["notes"] = "injected note"
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "notes" in manifest_check.detail


def test_detects_partition_hashes_tampering(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    data = _load_manifest(archive_root)
    # Añadir partition_hash falsificado a la tabla evidence.
    data["tables"]["evidence"]["partition_hashes"].append(  # type: ignore[index]
        "a" * 64
    )
    _save_manifest(archive_root, data)
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "partition_hashes" in manifest_check.detail


# ---------------------------------------------------------------- ignored fields


def test_generated_at_difference_does_not_trigger(tmp_path: Path, archive_root: Path) -> None:
    """generated_at SIEMPRE difiere entre stored y recomputed; no debe
    ser reportado como divergencia."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    # No alteramos el manifest: ya tiene generated_at canónico distinto al
    # default_clock que usará verify.
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is True


# ---------------------------------------------------------------- error paths


def test_missing_manifest_still_reports_missing(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    (archive_root / layout.MANIFEST_FILENAME).unlink()
    archive = Archive.open(archive_root)
    # is_archive requires manifest OR audit.log; audit.log exists, so still archive.
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "missing" in manifest_check.detail


def test_unparseable_manifest_reports_parse_error(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    (archive_root / layout.MANIFEST_FILENAME).write_text("not valid json {", encoding="utf-8")
    archive = Archive.open(archive_root)
    report = archive.verify(full=True)
    manifest_check = next(c for c in report.checks if c.name == "manifest")
    assert manifest_check.ok is False
    assert "parse error" in manifest_check.detail
