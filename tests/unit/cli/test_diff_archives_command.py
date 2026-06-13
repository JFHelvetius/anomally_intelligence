"""CLI tests for ``aip diff archives``.

These tests exercise argparse wiring + exit codes + JSON shape end-to-end
through ``aip.cli.main``. The detailed comparison semantics live in
``tests/unit/archive_compare/test_comparator.py``; here we only confirm
the CLI surface is honest.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.cli import main as cli_main
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _ingest(archive_root: Path, blob: Path) -> str:
    archive = Archive.open(archive_root)
    ev = archive.ingest_evidence(
        blob,
        source_id="src-x",
        source_name="Source X",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@tester",
        clock=_fixed_clock(CANONICAL_TS),
    )
    return ev.hash


@pytest.fixture
def two_archives(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "archive-a"
    a.mkdir()
    b = tmp_path / "archive-b"
    b.mkdir()
    return a, b


def test_diff_archives_exits_zero_when_no_shared_artifacts(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    rc, out, _err = _run(["diff", "archives", str(a), str(b)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["shared_evidence_count"] == 0
    assert payload["has_divergence"] is False


def test_diff_archives_reports_consistent_shared_evidence(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    a, b = two_archives
    blob_a = tmp_path / "blob-a.pdf"
    blob_b = tmp_path / "blob-b.pdf"
    blob_a.write_bytes(b"%PDF-1.4 same-bytes")
    blob_b.write_bytes(b"%PDF-1.4 same-bytes")
    _ingest(a, blob_a)
    _ingest(b, blob_b)

    rc, out, _err = _run(["diff", "archives", str(a), str(b)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["shared_evidence_count"] == 1
    assert payload["shared_evidence"][0]["audit_params_match"] is True
    assert payload["has_divergence"] is False


def test_diff_archives_exits_one_on_tampered_size_bytes(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    a, b = two_archives
    blob_a = tmp_path / "blob-a.pdf"
    blob_b = tmp_path / "blob-b.pdf"
    blob_a.write_bytes(b"%PDF-1.4 same")
    blob_b.write_bytes(b"%PDF-1.4 same")
    _ingest(a, blob_a)
    _ingest(b, blob_b)
    # Tamper B's audit log.
    log_path = b / "audit.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for raw in lines:
        entry = json.loads(raw)
        if entry.get("action") == "ingest_evidence":
            entry["parameters"]["size_bytes"] = "1"
        rewritten.append(json.dumps(entry, sort_keys=True))
    log_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    rc, out, _err = _run(["diff", "archives", str(a), str(b)])
    assert rc == 1
    payload = json.loads(out)
    assert payload["has_divergence"] is True
    assert payload["ok"] is False
    diverging = payload["shared_evidence"][0]["diverging_param_fields"]
    assert "size_bytes" in diverging


def test_diff_archives_respects_explicit_labels(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    rc, out, _err = _run(
        [
            "diff",
            "archives",
            str(a),
            str(b),
            "--label-a",
            "Operator-North",
            "--label-b",
            "Operator-South",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["archive_a_label"] == "Operator-North"
    assert payload["archive_b_label"] == "Operator-South"


def test_diff_archives_errors_on_missing_root(tmp_path: Path) -> None:
    rc, _out, err = _run(
        [
            "diff",
            "archives",
            str(tmp_path / "missing-a"),
            str(tmp_path / "missing-b"),
        ]
    )
    assert rc != 0
    assert "archive root not found" in err


def test_diff_archives_subcommand_discoverable() -> None:
    parser = cli_main.build_parser()
    # Walk to ``diff`` subgroup, confirm ``archives`` is registered.
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and "diff" in choices:
            diff_parser = choices["diff"]
            for sub_action in diff_parser._actions:
                sub_choices = getattr(sub_action, "choices", None)
                if isinstance(sub_choices, dict) and "archives" in sub_choices:
                    return
    raise AssertionError("'aip diff archives' not registered in CLI tree")
