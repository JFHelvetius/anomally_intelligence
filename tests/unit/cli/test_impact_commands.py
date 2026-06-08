"""Tests del CLI ``aip impact {evidence,assessment}`` (ADR-0034 §CLI)."""

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
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.impact import ANALYSIS_METHOD_NAME, IMPACT_ENGINE_VERSION

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
        actor="@test",
    )
    return a.assessment_id


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------- discoverability


def test_impact_subgroup_is_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "impact" in names


# ---------------------------------------------------------------- impact evidence


def test_impact_evidence_happy_path(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    assessment_id = _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "impact",
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
    assert payload["action"] == "impact_evidence"
    assert payload["evidence_id"] == evidence_hash
    report = payload["report"]
    assert report["root_node_id"] == evidence_hash
    assert report["affected_assessments"] == [assessment_id]
    assert report["dependency_depth_max"] == 1
    assert report["total_affected_nodes"] == 1


def test_impact_evidence_no_assessments_returns_empty(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "impact",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["report"]["total_affected_nodes"] == 0
    assert payload["report"]["affected_assessments"] == []


def test_impact_evidence_not_found_returns_nonzero(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "impact",
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
    assert payload["report"] is None


def test_impact_evidence_requires_positional_id(tmp_path: Path, archive_root: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            ["impact", "evidence", "--archive", str(archive_root)],
            stdout=out,
            stderr=err,
        )


def test_impact_evidence_requires_archive_flag() -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(["impact", "evidence", "a" * 64], stdout=out, stderr=err)


# ---------------------------------------------------------------- impact assessment


def test_impact_assessment_returns_empty_for_terminal_node(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    assessment_id = _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "impact",
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
    # Nada depende de un assessment en V1.
    assert payload["report"]["total_affected_nodes"] == 0
    assert payload["report"]["affected_assessments"] == []
    assert payload["report"]["affected_evidence"] == []


def test_impact_assessment_not_found_returns_nonzero(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "impact",
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


def test_impact_archive_missing(tmp_path: Path) -> None:
    rc, _, err = _run(
        [
            "impact",
            "evidence",
            "a" * 64,
            "--archive",
            str(tmp_path / "ghost"),
        ]
    )
    assert rc != 0
    assert "ArchiveNotFoundError" in err


# ---------------------------------------------------------------- canonical JSON


def test_impact_output_has_sorted_keys(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "impact",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    canonical = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert out == canonical


def test_impact_output_is_stable_across_runs(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc1, out1, _ = _run(
        [
            "impact",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    rc2, out2, _ = _run(
        [
            "impact",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc1 == rc2 == 0
    assert out1 == out2


# ---------------------------------------------------------------- honesty fields in JSON


def test_impact_report_includes_honesty_fields(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "impact",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    report = json.loads(out)["report"]
    assert report["analysis_engine_version"] == IMPACT_ENGINE_VERSION
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["analysis_method_name"] == ANALYSIS_METHOD_NAME


# ---------------------------------------------------------------- removability


def test_impact_cli_does_not_modify_archive(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)

    manifest_before = (archive_root / "manifest.json").read_bytes()
    audit_before = (archive_root / "audit.log").read_bytes()

    rc, _, _ = _run(
        [
            "impact",
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


def test_existing_commands_still_work_after_impact_subgroup_added(
    tmp_path: Path, archive_root: Path
) -> None:
    """Cualquier comando previo a ADR-0034 (ingest/show/verify/assess)
    debe seguir funcionando exactamente igual."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    rc_show, _, _ = _run(
        [
            "evidence",
            "show",
            f"sha256:{evidence_hash}",
            "--archive-root",
            str(archive_root),
        ]
    )
    rc_verify, _, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
        ]
    )
    rc_list, _, _ = _run(["list-assessments", "--archive", str(archive_root)])
    assert rc_show == 0
    assert rc_verify == 0
    assert rc_list == 0


def test_impact_does_not_change_manifest_hash(tmp_path: Path, archive_root: Path) -> None:
    """Confirmación operativa: archive_manifest_hash idéntico antes y
    después de cualquier número de invocaciones de `aip impact`."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)

    rc_pre, out_pre, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )
    assert rc_pre == 0
    pre_hash = json.loads(out_pre)["summary"]["archive_manifest_hash"]

    for _ in range(3):
        _run(
            [
                "impact",
                "evidence",
                evidence_hash,
                "--archive",
                str(archive_root),
            ]
        )

    rc_post, out_post, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )
    assert rc_post == 0
    post_hash = json.loads(out_post)["summary"]["archive_manifest_hash"]
    assert pre_hash == post_hash
