"""Tests del CLI ``aip justification`` y ``aip diff justifications`` (ADR-0040)."""

from __future__ import annotations

import datetime as dt
import io
import json
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
        clock=_fixed_clock(CANONICAL_TS),
    )
    return ev.hash


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


def _bootstrap(tmp_path: Path, archive_root: Path) -> str:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    return _assess(archive_root, ev_hash)


# ---------------------------------------------------------------- discoverability


def test_justification_subgroup_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "justification" in names


# ---------------------------------------------------------------- build


def test_justification_build_happy_path(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    rc, out, err = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j-01",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["justification_id"] == "j-01"
    assert payload["conclusion_anchor_id"] == a_id
    assert payload["conclusion_anchor_type"] == "assessment"
    canonical = archive_root / "justifications" / "j-01.json"
    assert canonical.is_file()


def test_justification_build_extra_output(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    extra = tmp_path / "shared" / "j.json"
    rc, _, _ = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
            "--output",
            str(extra),
        ]
    )
    assert rc == 0
    canonical = archive_root / "justifications" / "j.json"
    assert extra.read_bytes() == canonical.read_bytes()


def test_justification_build_with_workspace_scope(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    # Crear workspace para usar como scope.
    _run(
        [
            "workspace",
            "create",
            "--workspace-id",
            "w",
            "--title",
            "T",
            "--archive",
            str(archive_root),
        ]
    )
    rc, out, _ = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--workspace-id",
            "w",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["workspace_hash"] is not None


def test_justification_build_rejects_invalid_anchor_type(
    tmp_path: Path, archive_root: Path
) -> None:
    _bootstrap(tmp_path, archive_root)
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            [
                "justification",
                "build",
                "--conclusion-anchor-type",
                "hypothesis",  # not in choices
                "--conclusion-anchor-id",
                "x",
                "--justification-id",
                "j",
                "--archive",
                str(archive_root),
            ],
            stdout=out,
            stderr=err,
        )


def test_justification_build_anchor_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    _bootstrap(tmp_path, archive_root)
    rc, _, err = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            "ghost__provenance_review",
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc != 0
    assert "JustificationAnchorNotFoundError" in err


# ---------------------------------------------------------------- show


def test_justification_show_returns_persisted(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    rc, out, _ = _run(
        [
            "justification",
            "show",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["justification_id"] == "j"


def test_justification_show_missing_returns_error(
    tmp_path: Path, archive_root: Path
) -> None:
    _bootstrap(tmp_path, archive_root)
    rc, _, err = _run(
        [
            "justification",
            "show",
            "ghost",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc != 0
    assert "JustificationNotFoundError" in err


# ---------------------------------------------------------------- verify


def test_justification_verify_valid(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    path = archive_root / "justifications" / "j.json"
    rc, out, _ = _run(["justification", "verify", str(path)])
    assert rc == 0
    assert json.loads(out)["ok"] is True


def test_justification_verify_tampered(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    path = archive_root / "justifications" / "j.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["justification_id"] = "tampered"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(["justification", "verify", str(path)])
    assert rc == 1
    assert json.loads(out)["ok"] is False


def test_justification_verify_missing_file(tmp_path: Path) -> None:
    rc, _, err = _run(
        ["justification", "verify", str(tmp_path / "ghost.json")]
    )
    assert rc != 0
    assert "not found" in err.lower()


# ---------------------------------------------------------------- byte-identical


def test_justification_build_byte_identical(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    rc1, out1, _ = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    rc2, out2, _ = _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc1 == rc2 == 0
    assert out1 == out2


# ---------------------------------------------------------------- aip diff justifications


def test_diff_justifications_identical(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    path = archive_root / "justifications" / "j.json"
    rc, out, err = _run(
        ["diff", "justifications", str(path), str(path)]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["added_entries"] == []
    assert payload["removed_entries"] == []
    assert len(payload["unchanged_entries"]) >= 1


def test_diff_justifications_writes_output(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    path = archive_root / "justifications" / "j.json"
    out_path = tmp_path / "diff.json"
    rc, _, _ = _run(
        [
            "diff",
            "justifications",
            str(path),
            str(path),
            "--output",
            str(out_path),
        ]
    )
    assert rc == 0
    assert out_path.is_file()


def test_diff_justifications_missing_files(tmp_path: Path) -> None:
    rc, _, err = _run(
        [
            "diff",
            "justifications",
            str(tmp_path / "a.json"),
            str(tmp_path / "b.json"),
        ]
    )
    assert rc != 0
    assert "not found" in err.lower()


def test_diff_justifications_rejects_schema_mismatch(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    _run(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            a_id,
            "--justification-id",
            "j",
            "--archive",
            str(archive_root),
        ]
    )
    path = archive_root / "justifications" / "j.json"
    # Crear copia con schema_version distinto.
    fake = tmp_path / "fake.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = "99"
    fake.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, _, err = _run(
        ["diff", "justifications", str(path), str(fake)]
    )
    assert rc != 0
    assert "schema_version mismatch" in err


# ---------------------------------------------------------------- backwards compat


def test_existing_commands_unaffected(
    tmp_path: Path, archive_root: Path
) -> None:
    a_id = _bootstrap(tmp_path, archive_root)
    blob = tmp_path / "doc.pdf"
    ev_hash = _ingest(archive_root, blob)
    for argv in (
        [
            "evidence",
            "show",
            f"sha256:{ev_hash}",
            "--archive-root",
            str(archive_root),
        ],
        ["archive", "verify", "--archive-root", str(archive_root)],
        ["graph", "show", "--archive", str(archive_root)],
        ["impact", "evidence", ev_hash, "--archive", str(archive_root)],
        [
            "context",
            "show",
            "evidence",
            ev_hash,
            "--archive",
            str(archive_root),
        ],
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            ev_hash,
        ],
    ):
        rc, _, _ = _run(argv)
        assert rc == 0, f"existing command broke: {argv}"
    assert a_id is not None  # silenciar unused var
