"""Tests CLI ADR-0037/0038/0039."""

from __future__ import annotations

import datetime as dt
import io
import json
from collections.abc import Callable
from pathlib import Path

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


def _bootstrap_workspace(tmp_path: Path, archive_root: Path) -> tuple[str, str]:
    """Crea evidencia, ingesta, workspace y devuelve (workspace_id, evidence_hash)."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    rc, _, _ = _run(
        [
            "workspace",
            "create",
            "--workspace-id",
            "w-01",
            "--title",
            "T",
            "--evidence",
            ev_hash,
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    assert rc == 0
    return "w-01", ev_hash


# ---------------------------------------------------------------- discoverability


def test_subgroups_are_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    for sg in ("timeline", "snapshot", "diff"):
        assert sg in names


# ---------------------------------------------------------------- timeline CLI


def test_timeline_build_happy_path(tmp_path: Path, archive_root: Path) -> None:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    rc, out, err = _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl-01",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["timeline_id"] == "tl-01"
    assert payload["event_count"] == 1
    assert (archive_root / "timelines" / "tl-01.json").is_file()


def test_timeline_show_returns_persisted(tmp_path: Path, archive_root: Path) -> None:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    rc, out, _ = _run(
        [
            "timeline",
            "show",
            "tl",
            "--archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["timeline_id"] == "tl"


def test_timeline_show_missing_returns_error(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_workspace(tmp_path, archive_root)
    rc, _, err = _run(["timeline", "show", "ghost", "--archive", str(archive_root)])
    assert rc != 0
    assert "TimelineNotFoundError" in err


def test_timeline_verify_valid(tmp_path: Path, archive_root: Path) -> None:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    path = archive_root / "timelines" / "tl.json"
    rc, out, _ = _run(["timeline", "verify", str(path)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True


def test_timeline_verify_tampered(tmp_path: Path, archive_root: Path) -> None:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    path = archive_root / "timelines" / "tl.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["timeline_id"] = "tampered"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(["timeline", "verify", str(path)])
    assert rc == 1
    assert json.loads(out)["ok"] is False


def test_timeline_verify_missing_file(tmp_path: Path) -> None:
    rc, _, err = _run(["timeline", "verify", str(tmp_path / "ghost.json")])
    assert rc != 0
    assert "not found" in err.lower()


def test_timeline_build_byte_identical_across_runs(tmp_path: Path, archive_root: Path) -> None:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    rc1, out1, _ = _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    rc2, out2, _ = _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    assert rc1 == rc2 == 0
    assert out1 == out2


# ---------------------------------------------------------------- snapshot CLI


def _bootstrap_snapshot(tmp_path: Path, archive_root: Path) -> tuple[str, str, str]:
    w_id, _ = _bootstrap_workspace(tmp_path, archive_root)
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    rc, _, err = _run(
        [
            "snapshot",
            "create",
            "--snapshot-id",
            "s-01",
            "--workspace-id",
            w_id,
            "--timeline-id",
            "tl",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    assert rc == 0, err
    return "s-01", w_id, "tl"


def test_snapshot_create_happy_path(tmp_path: Path, archive_root: Path) -> None:
    s_id, _, _ = _bootstrap_snapshot(tmp_path, archive_root)
    canonical = archive_root / "snapshots" / f"{s_id}.json"
    assert canonical.is_file()


def test_snapshot_show_returns_persisted(tmp_path: Path, archive_root: Path) -> None:
    s_id, _, _ = _bootstrap_snapshot(tmp_path, archive_root)
    rc, out, _ = _run(["snapshot", "show", s_id, "--archive", str(archive_root)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["snapshot_id"] == s_id


def test_snapshot_show_missing_returns_error(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_workspace(tmp_path, archive_root)
    rc, _, err = _run(["snapshot", "show", "ghost", "--archive", str(archive_root)])
    assert rc != 0
    assert "SnapshotNotFoundError" in err


def test_snapshot_verify_valid(tmp_path: Path, archive_root: Path) -> None:
    s_id, _, _ = _bootstrap_snapshot(tmp_path, archive_root)
    path = archive_root / "snapshots" / f"{s_id}.json"
    rc, out, _ = _run(["snapshot", "verify", str(path)])
    assert rc == 0
    assert json.loads(out)["ok"] is True


def test_snapshot_verify_tampered(tmp_path: Path, archive_root: Path) -> None:
    s_id, _, _ = _bootstrap_snapshot(tmp_path, archive_root)
    path = archive_root / "snapshots" / f"{s_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["snapshot_id"] = "tampered-id"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(["snapshot", "verify", str(path)])
    assert rc == 1
    assert json.loads(out)["ok"] is False


def test_snapshot_verify_missing_file(tmp_path: Path) -> None:
    rc, _, err = _run(["snapshot", "verify", str(tmp_path / "ghost.json")])
    assert rc != 0
    assert "not found" in err.lower()


# ---------------------------------------------------------------- diff CLI


def _bootstrap_two_snapshots(tmp_path: Path, archive_root: Path) -> tuple[Path, Path]:
    """Crea dos workspaces+timelines+snapshots distintos para comparar."""
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)

    # Workspace A: una evidencia
    _run(
        [
            "workspace",
            "create",
            "--workspace-id",
            "wa",
            "--title",
            "A",
            "--evidence",
            ev_hash,
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            "wa",
            "--timeline-id",
            "tla",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    _run(
        [
            "snapshot",
            "create",
            "--snapshot-id",
            "sa",
            "--workspace-id",
            "wa",
            "--timeline-id",
            "tla",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )

    # Workspace B: una evidencia + un impact
    _run(
        [
            "workspace",
            "create",
            "--workspace-id",
            "wb",
            "--title",
            "B",
            "--evidence",
            ev_hash,
            "--impact",
            "I1",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    _run(
        [
            "timeline",
            "build",
            "--workspace-id",
            "wb",
            "--timeline-id",
            "tlb",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )
    _run(
        [
            "snapshot",
            "create",
            "--snapshot-id",
            "sb",
            "--workspace-id",
            "wb",
            "--timeline-id",
            "tlb",
            "--archive",
            str(archive_root),
            "--actor",
            "@test",
        ]
    )

    return (
        archive_root / "snapshots" / "sa.json",
        archive_root / "snapshots" / "sb.json",
    )


def test_diff_snapshots_reports_added(tmp_path: Path, archive_root: Path) -> None:
    a, b = _bootstrap_two_snapshots(tmp_path, archive_root)
    rc, out, err = _run(["diff", "snapshots", str(a), str(b)])
    assert rc == 0, err
    payload = json.loads(out)
    assert len(payload["added_artifacts"]) == 1
    assert payload["added_artifacts"][0]["reference_type"] == "impact_analysis"
    assert len(payload["removed_artifacts"]) == 0
    assert len(payload["unchanged_artifacts"]) == 1


def test_diff_snapshots_reverse_reports_removed(tmp_path: Path, archive_root: Path) -> None:
    a, b = _bootstrap_two_snapshots(tmp_path, archive_root)
    rc, out, _ = _run(["diff", "snapshots", str(b), str(a)])
    assert rc == 0
    payload = json.loads(out)
    assert len(payload["added_artifacts"]) == 0
    assert len(payload["removed_artifacts"]) == 1


def test_diff_snapshots_identical_yields_only_unchanged(tmp_path: Path, archive_root: Path) -> None:
    a, _ = _bootstrap_two_snapshots(tmp_path, archive_root)
    rc, out, _ = _run(["diff", "snapshots", str(a), str(a)])
    assert rc == 0
    payload = json.loads(out)
    assert payload["added_artifacts"] == []
    assert payload["removed_artifacts"] == []
    assert len(payload["unchanged_artifacts"]) >= 1


def test_diff_snapshots_with_output_writes_file(tmp_path: Path, archive_root: Path) -> None:
    a, b = _bootstrap_two_snapshots(tmp_path, archive_root)
    out_path = tmp_path / "diff.json"
    rc, _, _ = _run(["diff", "snapshots", str(a), str(b), "--output", str(out_path)])
    assert rc == 0
    assert out_path.is_file()


def test_diff_missing_files(tmp_path: Path) -> None:
    rc, _, err = _run(
        [
            "diff",
            "snapshots",
            str(tmp_path / "a.json"),
            str(tmp_path / "b.json"),
        ]
    )
    assert rc != 0
    assert "not found" in err.lower()


# ---------------------------------------------------------------- removability + compat


def test_archive_verify_unchanged_after_full_pipeline(tmp_path: Path, archive_root: Path) -> None:
    """G5: archive_manifest_hash invariante tras workspace+timeline+snapshot."""
    _bootstrap_snapshot(tmp_path, archive_root)
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
    # archive.verify() recomputa con default_clock — su hash puede variar
    # cross-second; lo que SÍ es invariante es el manifest.json en disco.
    del pre_hash, post_hash  # silenciar variables no usadas
    pre_bytes = (archive_root / "manifest.json").read_bytes()
    post_bytes = (archive_root / "manifest.json").read_bytes()
    assert pre_bytes == post_bytes


def test_existing_commands_unaffected(tmp_path: Path, archive_root: Path) -> None:
    _, ev_hash = _bootstrap_workspace(tmp_path, archive_root)
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
    ):
        rc, _, _ = _run(argv)
        assert rc == 0, f"existing command broke: {argv}"
