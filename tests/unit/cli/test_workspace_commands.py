"""Tests del CLI ``aip workspace {create,show,verify}`` (ADR-0036 §CLI)."""

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


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------- discoverability


def test_workspace_subgroup_is_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "workspace" in names


# ---------------------------------------------------------------- create


def _create_args(
    archive_root: Path, *, output: Path | None = None
) -> list[str]:
    args = [
        "workspace",
        "create",
        "--workspace-id",
        "fraud-chain-01",
        "--title",
        "Fraud Investigation",
        "--evidence",
        "E001",
        "--evidence",
        "E005",
        "--assessment",
        "A002",
        "--impact",
        "I003",
        "--context",
        "C001",
        "--archive",
        str(archive_root),
    ]
    if output is not None:
        args.extend(["--output", str(output)])
    return args


def test_workspace_create_happy_path(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, out, err = _run(_create_args(archive_root))
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["workspace_id"] == "fraud-chain-01"
    assert payload["title"] == "Fraud Investigation"
    assert len(payload["references"]) == 5
    # Persiste en localización canónica del archive.
    canonical = archive_root / "workspaces" / "fraud-chain-01.json"
    assert canonical.is_file()


def test_workspace_create_extra_output(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    extra = tmp_path / "shared" / "fraud-chain-01.json"
    rc, _, _ = _run(_create_args(archive_root, output=extra))
    assert rc == 0
    canonical = archive_root / "workspaces" / "fraud-chain-01.json"
    assert extra.read_bytes() == canonical.read_bytes()


def test_workspace_create_rejects_duplicate_evidence(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, _, err = _run(
        [
            "workspace",
            "create",
            "--workspace-id",
            "x",
            "--title",
            "t",
            "--evidence",
            "E1",
            "--evidence",
            "E1",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc != 0
    assert "duplicate" in err.lower()


def test_workspace_create_requires_workspace_id(
    tmp_path: Path, archive_root: Path
) -> None:
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(SystemExit):
        cli_main.main(
            [
                "workspace",
                "create",
                "--title",
                "t",
                "--archive",
                str(archive_root),
            ],
            stdout=out,
            stderr=err,
        )


# ---------------------------------------------------------------- show


def test_workspace_show_returns_persisted_workspace(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    _run(_create_args(archive_root))
    rc, out, _ = _run(
        [
            "workspace",
            "show",
            "fraud-chain-01",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["workspace_id"] == "fraud-chain-01"
    assert len(payload["references"]) == 5


def test_workspace_show_missing_returns_error(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc, _, err = _run(
        [
            "workspace",
            "show",
            "ghost-workspace",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc != 0
    assert "WorkspaceNotFoundError" in err


# ---------------------------------------------------------------- verify


def test_workspace_verify_returns_zero_for_valid_workspace(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    _run(_create_args(archive_root))
    canonical = archive_root / "workspaces" / "fraud-chain-01.json"
    rc, out, _ = _run(["workspace", "verify", str(canonical)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True


def test_workspace_verify_returns_one_for_tampered_workspace(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    _run(_create_args(archive_root))
    canonical = archive_root / "workspaces" / "fraud-chain-01.json"
    data = json.loads(canonical.read_text(encoding="utf-8"))
    # Modificar título sin recomputar hash → tampering.
    data["title"] = "Tampered"
    canonical.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(["workspace", "verify", str(canonical)])
    assert rc == 1
    payload = json.loads(out)
    assert payload["ok"] is False


def test_workspace_verify_missing_file_returns_error(tmp_path: Path) -> None:
    rc, _, err = _run(["workspace", "verify", str(tmp_path / "ghost.json")])
    assert rc != 0
    assert "not found" in err.lower()


# ---------------------------------------------------------------- canonical


def test_workspace_create_output_is_canonical_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    rc1, out1, _ = _run(_create_args(archive_root))
    # Re-crear sobreescribe; mismas entradas ⇒ misma salida.
    rc2, out2, _ = _run(_create_args(archive_root))
    assert rc1 == rc2 == 0
    assert out1 == out2


# ---------------------------------------------------------------- backwards compat


def test_archive_verify_passes_after_workspace_operations(
    tmp_path: Path, archive_root: Path
) -> None:
    """G5: aip archive verify sigue OK tras múltiples workspace ops."""
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
    assert rc_pre == 0
    pre_hash = json.loads(out_pre)["summary"]["archive_manifest_hash"]

    for wid in ("w1", "w2", "w3"):
        rc, _, _ = _run(
            [
                "workspace",
                "create",
                "--workspace-id",
                wid,
                "--title",
                wid,
                "--evidence",
                "E1",
                "--archive",
                str(archive_root),
            ]
        )
        assert rc == 0

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
    # archive_manifest_hash invariante (G5).
    assert pre_hash == post_hash


def test_existing_commands_unaffected_by_workspace_subgroup(
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
        ["graph", "show", "--archive", str(archive_root)],
        ["impact", "evidence", evidence_hash, "--archive", str(archive_root)],
        [
            "context",
            "show",
            "evidence",
            evidence_hash,
            "--archive",
            str(archive_root),
        ],
    ):
        rc, _, _ = _run(argv)
        assert rc == 0, f"existing command broke: {argv}"
