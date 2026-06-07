"""Tests del CLI ``aip assess-authentication`` (ADR-0032 §5).

Cubre el contrato observable:

- Arguments shape (``--archive`` + ``--evidence-id`` + ``--method`` opcional).
- Salida JSON canónica.
- Códigos de salida (0 en éxito, codes de error mapeados).
- Disponibilidad como subcomando top-level.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path

import pytest

from aip import Archive
from aip.cli import main as cli_main
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _canonical_clock() -> dt.datetime:
    return CANONICAL_TS


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _ingest_with_python_api(archive_root: Path, blob: Path) -> str:
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
        clock=_canonical_clock,
    )
    return evidence.hash


# ---------------------------------------------------------------- happy path


def test_cli_assess_outputs_canonical_json(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest_with_python_api(archive_root, blob)

    rc, out, err = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            evidence_hash,
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["action"] == "assess_authentication"
    assert payload["archive_root"] == str(archive_root)
    assess = payload["assessment"]
    assert assess["evidence_id"] == evidence_hash
    assert assess["method"] == "provenance_review"
    assert assess["status"] == "supported"
    assert assess["supporting_source_ids"] == ["blue-book-nara"]
    assert assess["assessment_id"] == f"{evidence_hash}__provenance_review"


def test_cli_assess_accepts_method_flag(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest_with_python_api(archive_root, blob)

    rc, out, _ = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            evidence_hash,
            "--method",
            "manual_research",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["assessment"]["method"] == "manual_research"
    assert (
        payload["assessment"]["assessment_id"]
        == f"{evidence_hash}__manual_research"
    )


def test_cli_assess_accepts_sha256_prefixed_id(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest_with_python_api(archive_root, blob)

    rc, out, _ = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            f"sha256:{evidence_hash}",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    # El payload contiene el hex puro, sin prefijo.
    assert payload["assessment"]["evidence_id"] == evidence_hash


# ---------------------------------------------------------------- error paths


def test_cli_assess_requires_archive(archive_root: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            ["assess-authentication", "--evidence-id", "a" * 64],
            stdout=out,
            stderr=err,
        )


def test_cli_assess_requires_evidence_id(archive_root: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            ["assess-authentication", "--archive", str(archive_root)],
            stdout=out,
            stderr=err,
        )


def test_cli_assess_returns_nonzero_when_archive_missing(tmp_path: Path) -> None:
    rc, _, err = _run(
        [
            "assess-authentication",
            "--archive",
            str(tmp_path / "does-not-exist"),
            "--evidence-id",
            "a" * 64,
        ]
    )
    assert rc != 0
    assert "ArchiveNotFoundError" in err


def test_cli_assess_returns_nonzero_when_evidence_missing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest_with_python_api(archive_root, blob)
    rc, _, err = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            "c" * 64,
        ]
    )
    assert rc != 0
    assert "EvidenceNotFoundError" in err


def test_cli_assess_rejects_invalid_method(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    evidence_hash = _ingest_with_python_api(archive_root, blob)
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            [
                "assess-authentication",
                "--archive",
                str(archive_root),
                "--evidence-id",
                evidence_hash,
                "--method",
                "bayesian_inference",
            ],
            stdout=out,
            stderr=err,
        )


# ---------------------------------------------------------------- discoverability


def test_cli_help_lists_assess_authentication() -> None:
    parser = cli_main.build_parser()
    # argparse expone los nombres de subcomandos en el atributo `choices`
    # del action de subparsers. `choices` puede ser dict o lista según el
    # action; iteramos sobre los valores como str con isinstance defensivo.
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "assess-authentication" in names
