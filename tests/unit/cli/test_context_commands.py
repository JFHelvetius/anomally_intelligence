"""Tests del CLI ``aip context show {evidence,assessment}`` (ADR-0035 §CLI)."""

from __future__ import annotations

import datetime as dt
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import AssessmentMethod
from aip.cli import main as cli_main
from aip.context import ASSEMBLY_ENGINE_VERSION, ASSEMBLY_METHOD_NAME
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path) -> str:
    archive = Archive.open(archive_root)
    evidence = archive.ingest_evidence(
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
        clock=_fixed_clock(CANONICAL_TS),
    )
    return evidence.hash


def _assess(archive_root: Path, evidence_id: str) -> str:
    archive = Archive.open(archive_root)
    a = archive.assess_authentication(
        evidence_id=evidence_id,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_fixed_clock(CANONICAL_TS),
    )
    return a.assessment_id


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------- discoverability


def test_context_subgroup_is_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "context" in names


# ---------------------------------------------------------------- show evidence


def test_context_show_evidence_happy_path(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["exists"] is True
    assert payload["evidence_id"] == evidence_hash
    bundle = payload["bundle"]
    assert bundle["anchor_node_kind"] == "evidence"
    assert bundle["anchor_node_id"] == evidence_hash
    assert bundle["evidence"]["hash"] == evidence_hash
    assert bundle["source"]["id"] == "blue-book-nara"
    assert len(bundle["derived_assessments"]) == 1
    assert bundle["impact_report"]["total_affected_nodes"] == 1


def test_context_show_evidence_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "evidence",
            "f" * 64,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["exists"] is False
    assert payload["bundle"] is None


def test_context_show_evidence_requires_id() -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            ["context", "show", "evidence"], stdout=out, stderr=err
        )


def test_context_show_evidence_requires_archive() -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            ["context", "show", "evidence", "a" * 64],
            stdout=out,
            stderr=err,
        )


# ---------------------------------------------------------------- show assessment


def test_context_show_assessment_happy_path(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    assessment_id = _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "assessment",
            assessment_id,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["exists"] is True
    bundle = payload["bundle"]
    assert bundle["anchor_node_kind"] == "assessment"
    assert bundle["anchor_node_id"] == assessment_id
    # Resuelve la evidencia automáticamente.
    assert bundle["evidence"]["hash"] == evidence_hash


def test_context_show_assessment_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "assessment",
            "ghost__provenance_review",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["exists"] is False


# ---------------------------------------------------------------- archive errors


def test_context_show_archive_missing(tmp_path: Path) -> None:
    rc, _, err = _run(
        [
            "context",
            "show",
            "evidence",
            "a" * 64,
            "--archive",
            str(tmp_path / "ghost"),
        ]
    )
    assert rc != 0
    assert "ContextAssemblyError" in err


# ---------------------------------------------------------------- canonical JSON


def test_context_output_has_sorted_keys(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    canonical = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    assert out == canonical


def test_context_output_is_stable_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc1, out1, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    rc2, out2, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc1 == rc2 == 0
    assert out1 == out2


# ---------------------------------------------------------------- honesty


def test_context_cli_emits_hashes_and_honesty_fields(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    bundle = json.loads(out)["bundle"]
    assert bundle["assembly_engine_version"] == ASSEMBLY_ENGINE_VERSION
    assert bundle["assembly_method_name"] == ASSEMBLY_METHOD_NAME
    assert bundle["schema_version"] == SCHEMA_VERSION
    # SHA-256 hex strings de 64 chars.
    assert len(bundle["source_manifest_hash"]) == 64
    assert len(bundle["context_bundle_hash"]) == 64


# ---------------------------------------------------------------- removability


def test_context_cli_does_not_modify_archive(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)

    manifest_before = (archive_root / "manifest.json").read_bytes()
    audit_before = (archive_root / "audit.log").read_bytes()

    rc, _, _ = _run(
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0

    assert (archive_root / "manifest.json").read_bytes() == manifest_before
    assert (archive_root / "audit.log").read_bytes() == audit_before


# ---------------------------------------------------------------- backwards compat


def test_existing_commands_unaffected_by_context_subgroup(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    for argv in (
        [
            "evidence",
            "show",
            f"sha256:{evidence_hash}",
            "--archive-root",
            str(archive_root),
        ],
        ["archive", "verify", "--archive-root", str(archive_root)],
        ["list-assessments", "--archive", str(archive_root)],
        ["graph", "show", "--archive", str(archive_root)],
        ["impact", "evidence", evidence_hash, "--archive", str(archive_root)],
    ):
        rc, _, _ = _run(argv)
        assert rc == 0, f"existing command broke: {argv}"
