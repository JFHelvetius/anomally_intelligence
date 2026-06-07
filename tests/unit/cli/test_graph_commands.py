"""Tests del CLI ``aip graph {show,explain-assessment,explain-evidence}``."""

from __future__ import annotations

import datetime as dt
import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.cli import main as cli_main
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


def test_cli_graph_subgroup_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "graph" in names


# ---------------------------------------------------------------- show


def test_graph_show_empty_archive(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    # Ingest para crear archive válido, luego limpiar tablas.
    _ingest(archive_root, blob)
    shutil.rmtree(archive_root / "tables")
    (archive_root / "tables").mkdir()
    for table in (
        "evidence",
        "sources",
        "provenance",
        "provenance_steps",
        "authentication_assessments",
    ):
        (archive_root / "tables" / table).mkdir()

    rc, out, _ = _run(["graph", "show", "--archive", str(archive_root)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["action"] == "graph_show"
    assert payload["graph"]["nodes"] == []
    assert payload["graph"]["edges"] == []
    assert payload["graph"]["counts"]["nodes"] == 0
    assert payload["graph"]["integrity"]["ok"] is True


def test_graph_show_populated_archive(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(["graph", "show", "--archive", str(archive_root)])
    assert rc == 0
    payload = json.loads(out)
    g = payload["graph"]
    assert g["counts"]["nodes"] == 3
    assert g["counts"]["edges"] == 3
    assert g["counts"]["nodes_by_kind"]["evidence"] == 1
    assert g["counts"]["nodes_by_kind"]["source"] == 1
    assert g["counts"]["nodes_by_kind"]["assessment"] == 1
    assert g["counts"]["edges_by_kind"]["sourced_from"] == 1
    assert g["counts"]["edges_by_kind"]["assessed_from"] == 1
    assert g["counts"]["edges_by_kind"]["derived_from"] == 1


def test_graph_show_archive_missing(tmp_path: Path) -> None:
    rc, _, err = _run(
        ["graph", "show", "--archive", str(tmp_path / "ghost")]
    )
    assert rc != 0
    assert "ArchiveNotFoundError" in err


def test_graph_show_requires_archive_flag() -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(["graph", "show"], stdout=out, stderr=err)


def test_graph_show_output_is_canonical_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc1, out1, _ = _run(["graph", "show", "--archive", str(archive_root)])
    rc2, out2, _ = _run(["graph", "show", "--archive", str(archive_root)])
    assert rc1 == rc2 == 0
    # Salida bit a bit idéntica.
    assert out1 == out2


def test_graph_show_does_not_modify_archive(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)

    manifest_before = (archive_root / "manifest.json").read_bytes()
    audit_before = (archive_root / "audit.log").read_bytes()

    rc, _, _ = _run(["graph", "show", "--archive", str(archive_root)])
    assert rc == 0

    assert (archive_root / "manifest.json").read_bytes() == manifest_before
    assert (archive_root / "audit.log").read_bytes() == audit_before


def test_graph_show_canonical_json_has_sorted_keys(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(["graph", "show", "--archive", str(archive_root)])
    assert rc == 0
    # Re-parse el JSON y verificamos que serializar con sort_keys=True
    # produce idéntica salida (canonical confirm).
    payload = json.loads(out)
    canonical = json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    assert out == canonical


# ---------------------------------------------------------------- explain-assessment


def test_graph_explain_assessment_existing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    assessment_id = _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "graph",
            "explain-assessment",
            "--archive",
            str(archive_root),
            "--assessment-id",
            assessment_id,
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["exists"] is True
    assert payload["assessment_id"] == assessment_id
    assert payload["assessment"]["kind"] == "assessment"
    assert payload["evidence"]["id"] == evidence_hash
    # transitive_dependencies incluye source.
    kinds = [d["kind"] for d in payload["transitive_dependencies"]]
    assert "source" in kinds


def test_graph_explain_assessment_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "graph",
            "explain-assessment",
            "--archive",
            str(archive_root),
            "--assessment-id",
            "z" * 64 + "__provenance_review",
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["exists"] is False


def test_graph_explain_assessment_requires_both_args(
    tmp_path: Path, archive_root: Path
) -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            [
                "graph",
                "explain-assessment",
                "--archive",
                str(archive_root),
            ],
            stdout=out,
            stderr=err,
        )


# ---------------------------------------------------------------- explain-evidence


def test_graph_explain_evidence_existing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    _assess(archive_root, evidence_hash)
    rc, out, _ = _run(
        [
            "graph",
            "explain-evidence",
            "--archive",
            str(archive_root),
            "--evidence-id",
            evidence_hash,
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["exists"] is True
    assert payload["evidence"]["id"] == evidence_hash
    # Hay 1 assessment derivado, listado en assessments.
    assert len(payload["assessments"]) == 1
    # reverse_dependencies incluye al menos el assessment.
    kinds = [d["kind"] for d in payload["reverse_dependencies"]]
    assert "assessment" in kinds
    # transitive_dependencies incluye al menos la source.
    chain_kinds = [d["kind"] for d in payload["transitive_dependencies"]]
    assert "source" in chain_kinds


def test_graph_explain_evidence_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "graph",
            "explain-evidence",
            "--archive",
            str(archive_root),
            "--evidence-id",
            "f" * 64,
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["exists"] is False


def test_graph_explain_evidence_no_assessments_returns_empty_lists(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)
    rc, out, _ = _run(
        [
            "graph",
            "explain-evidence",
            "--archive",
            str(archive_root),
            "--evidence-id",
            evidence_hash,
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["exists"] is True
    assert payload["assessments"] == []
    assert payload["reverse_dependencies"] == []


# ---------------------------------------------------------------- backwards compatibility


def test_graph_does_not_break_existing_evidence_show(
    tmp_path: Path, archive_root: Path
) -> None:
    """Verifica que añadir el grafo no degrada la salida existente del
    comando `evidence show`. Lectura tras lectura: misma estructura."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest(archive_root, blob)

    rc_pre, out_pre, _ = _run(
        [
            "evidence",
            "show",
            f"sha256:{evidence_hash}",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )

    _ = _run(["graph", "show", "--archive", str(archive_root)])

    rc_post, out_post, _ = _run(
        [
            "evidence",
            "show",
            f"sha256:{evidence_hash}",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )
    assert rc_pre == 0
    assert rc_post == 0
    # El `evidence show` ya tiene estructura conocida; el grafo no la
    # modifica entre lecturas.
    assert json.loads(out_pre) == json.loads(out_post)


def test_graph_does_not_break_archive_verify(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc_pre, out_pre, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )

    _ = _run(["graph", "show", "--archive", str(archive_root)])

    rc_post, out_post, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ]
    )
    assert rc_pre == rc_post == 0
    pre = json.loads(out_pre)
    post = json.loads(out_post)
    # archive_manifest_hash idéntico antes y después del graph show.
    assert (
        pre["summary"]["archive_manifest_hash"]
        == post["summary"]["archive_manifest_hash"]
    )
