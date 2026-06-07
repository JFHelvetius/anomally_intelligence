"""Tests unitarios del dispatcher ``aip.cli.main``.

Estilo CLI (ADR-0017, Pre-F1.D): las opciones globales (``--archive-root``,
``--json``, ``--quiet``, ``--verbose``) viven en los subcomandos. Los tests
siguen ese orden: ``aip evidence ingest <path> --archive-root <root>`` etc.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from aip.cli import main as cli_main


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _ingest_args(
    blob: Path, archive_root: Path, extra: list[str] | None = None
) -> list[str]:
    args = [
        "evidence",
        "ingest",
        str(blob),
        "--archive-root",
        str(archive_root),
        "--source-id",
        "demo-src",
        "--source-name",
        "Demo Source",
        "--source-kind",
        "government_archive",
        "--source-authority",
        "secondary",
        "--ingested-by",
        "@tester",
    ]
    if extra:
        args.extend(extra)
    return args


# ---------------------------------------------------------------- top-level


def test_version_exits_zero_and_prints() -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(["--version"])
    assert exc_info.value.code == 0


def test_help_lists_subcommands() -> None:
    with pytest.raises(SystemExit):
        _run(["--help"])


def test_no_subcommand_errors() -> None:
    with pytest.raises(SystemExit):
        _run([])


def test_json_and_quiet_mutually_exclusive(tmp_path: Path) -> None:
    rc, _out, err = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(tmp_path),
            "--json",
            "--quiet",
        ]
    )
    assert rc == 64  # UsageError
    assert "mutually exclusive" in err


# ---------------------------------------------------------------- ingest


def test_ingest_emits_human_output(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"

    rc, out, _err = _run(_ingest_args(blob, archive))
    assert rc == 0
    assert "Ingested evidence" in out
    assert "Hash:" in out
    assert "sha256:" in out


def test_ingest_emits_json_output(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"

    rc, out, _err = _run(_ingest_args(blob, archive, extra=["--json"]))
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["evidence"]["kind"] == "document_scan"
    assert payload["evidence"]["size_bytes"] == 5


def test_ingest_dry_run_does_not_write_archive(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"

    rc, out, _err = _run(_ingest_args(blob, archive, extra=["--dry-run"]))
    assert rc == 0
    assert "dry-run" in out.lower()
    assert not (archive / "audit.log").exists()


def test_ingest_missing_file_returns_exit_1(tmp_path: Path) -> None:
    rc, _out, err = _run(
        _ingest_args(tmp_path / "nope.pdf", tmp_path / "archive")
    )
    assert rc == 1
    assert "file not found" in err.lower()


def test_ingest_existing_source_inconsistency_returns_1(tmp_path: Path) -> None:
    blob1 = tmp_path / "a.pdf"
    blob1.write_bytes(b"A")
    blob2 = tmp_path / "b.pdf"
    blob2.write_bytes(b"B")
    archive = tmp_path / "archive"

    _run(_ingest_args(blob1, archive))
    args = _ingest_args(blob2, archive)
    args[args.index("Demo Source")] = "Different Name"
    rc, _out, err = _run(args)
    assert rc == 1
    assert "InvalidSourceMetadataError" in err


# ---------------------------------------------------------------- show


def _ingest_and_get_hash(blob: Path, archive: Path) -> str:
    """Ejecuta ingest y devuelve el hash de la evidencia."""
    rc, out, _err = _run(_ingest_args(blob, archive, extra=["--json"]))
    assert rc == 0, f"setup ingest failed: {out}"
    return json.loads(out)["evidence"]["hash"]


def test_show_returns_evidence_view(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
        ]
    )
    assert rc == 0
    assert blob_hash in out
    assert "demo-src" in out


def test_show_uri_form(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, _out, _err = _run(
        [
            "evidence",
            "show",
            f"aip:evidence/sha256:{blob_hash}",
            "--archive-root",
            str(archive),
        ]
    )
    assert rc == 0


def test_show_json_structure(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["evidence"]["hash"] == blob_hash
    assert payload["source"]["id"] == "demo-src"


def test_show_not_found_returns_exit_1(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"x")
    archive = tmp_path / "archive"
    _ingest_and_get_hash(blob, archive)

    rc, _out, err = _run(
        [
            "evidence",
            "show",
            "0" * 64,
            "--archive-root",
            str(archive),
        ]
    )
    assert rc == 1
    assert "EvidenceNotFoundError" in err


def test_show_archive_not_found_returns_exit_1(tmp_path: Path) -> None:
    rc, _out, err = _run(
        [
            "evidence",
            "show",
            "0" * 64,
            "--archive-root",
            str(tmp_path / "ghost"),
        ]
    )
    assert rc == 1
    assert "ArchiveNotFoundError" in err


# ---------------------------------------------------------------- verify


def test_verify_after_ingest_ok(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        ["archive", "verify", "--archive-root", str(archive)]
    )
    assert rc == 0
    assert "Archive integrity verified" in out


def test_verify_quick_skips_blobs(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive),
            "--quick",
        ]
    )
    assert rc == 0
    assert "skipped" in out


def test_verify_json_structure(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive),
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["mode"] == "full"
    assert "audit_chain" in payload["checks"]


def test_verify_no_archive_returns_exit_1(tmp_path: Path) -> None:
    rc, _out, err = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(tmp_path / "ghost"),
        ]
    )
    assert rc == 1
    assert "ArchiveNotFoundError" in err


# ---------------------------------------------------------------- show + derived (ADR-0032)
# ``aip evidence show`` superficiía dos conceptos distintos de "authentication":
# (1) el slot embebido en Evidence (siempre UNVERIFIED en V1, estructural), y
# (2) la lista derived_assessments persistida en la tabla (vacía por defecto;
# poblada por `aip assess-authentication`). Estos tests blindan ambos.


def test_show_json_includes_empty_derived_assessments_list(
    tmp_path: Path,
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    # El campo está presente aunque vacío: contrato observable explícito.
    assert "derived_assessments" in payload
    assert payload["derived_assessments"] == []


def test_show_human_mentions_derived_section_when_empty(
    tmp_path: Path,
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
        ]
    )
    assert rc == 0
    assert "Derived Assessments" in out
    assert "(none)" in out
    # El call-to-action menciona el subcomando concreto para que el lector
    # sepa cómo producir uno.
    assert "aip assess-authentication" in out


def test_show_json_lists_assessments_after_assess(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    # Corremos assess primero.
    rc_a, _out_a, err_a = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive),
            "--evidence-id",
            blob_hash,
        ]
    )
    assert rc_a == 0, err_a

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert len(payload["derived_assessments"]) == 1
    derived = payload["derived_assessments"][0]
    assert derived["evidence_id"] == blob_hash
    assert derived["method"] == "provenance_review"
    assert derived["status"] == "supported"
    assert derived["supporting_source_ids"] == ["demo-src"]
    # Slot embebido SIGUE diciendo unverified — son cosas distintas.
    assert payload["authentication"]["status"] == "unverified"


def test_show_json_lists_multiple_assessments_ordered(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    # Tres assessments con métodos distintos sobre la misma Evidence.
    for method in ("manual_research", "provenance_review", "chain_of_custody_review"):
        rc, _out, _err = _run(
            [
                "assess-authentication",
                "--archive",
                str(archive),
                "--evidence-id",
                blob_hash,
                "--method",
                method,
            ]
        )
        assert rc == 0

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    derived = payload["derived_assessments"]
    assert len(derived) == 3
    # Orden estable por assessment_id (= "{evidence_id}__{method}").
    methods = [d["method"] for d in derived]
    assert methods == sorted(methods)


def test_show_human_lists_assessments_after_assess(tmp_path: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"hello")
    archive = tmp_path / "archive"
    blob_hash = _ingest_and_get_hash(blob, archive)

    rc, _out, _err = _run(
        [
            "assess-authentication",
            "--archive",
            str(archive),
            "--evidence-id",
            blob_hash,
        ]
    )
    assert rc == 0

    rc, out, _err = _run(
        [
            "evidence",
            "show",
            f"sha256:{blob_hash}",
            "--archive-root",
            str(archive),
        ]
    )
    assert rc == 0
    # El método y el status aparecen en la sección humana.
    assert "provenance_review" in out
    assert "supported" in out
    # La diferencia con el slot embebido sigue siendo lisible.
    assert "Authentication (embedded slot)" in out
    assert "Derived Assessments (ADR-0032)" in out
