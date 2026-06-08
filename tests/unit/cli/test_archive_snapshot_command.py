"""Tests del CLI ``aip archive snapshot`` (ADR-0042 §CLI)."""

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
T0 = dt.datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _seed_archive(tmp_path: Path, archive_root: Path) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    arc = Archive.open(archive_root)
    arc.ingest_evidence(
        blob,
        source_id="src",
        source_name="NARA",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@op",
        clock=_clock(T0),
    )


# ---------------------------------------------------------------- discoverability


def test_archive_snapshot_subcommand_listed() -> None:
    parser = cli_main.build_parser()
    archive_subparser = None
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and "archive" in choices:
            archive_subparser = choices["archive"]
            break
    assert archive_subparser is not None
    actions: set[str] = set()
    for action in archive_subparser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            actions.update(choices.keys())
    assert {"verify", "snapshot"}.issubset(actions)


# ---------------------------------------------------------------- happy path


def test_snapshot_emits_canonical_json(tmp_path: Path, archive_root: Path) -> None:
    _seed_archive(tmp_path, archive_root)
    rc, out, err = _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "2026-06-07T13:00:00Z",
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["generated_at"] == "2026-06-07T13:00:00Z"
    assert len(payload["snapshot_hash"]) == 64
    assert len(payload["manifest_hash"]) == 64
    assert len(payload["audit_log_head_hash"]) == 64
    assert payload["audit_log_total_entries"] >= 1
    # Canonical: keys sorted, trailing newline.
    assert list(payload.keys()) == sorted(payload.keys())
    assert out.endswith("\n")


def test_snapshot_output_file_matches_stdout(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    out_path = tmp_path / "snap.json"
    rc, out, err = _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "2026-06-07T13:00:00Z",
            "--output",
            str(out_path),
        ]
    )
    assert rc == 0, err
    assert out_path.is_file()
    assert out_path.read_text(encoding="utf-8") == out


def test_snapshot_is_read_only(tmp_path: Path, archive_root: Path) -> None:
    """``aip archive snapshot`` no muta el archive (asserción bit-a-bit)."""
    _seed_archive(tmp_path, archive_root)

    def fingerprint() -> dict[str, bytes]:
        return {
            str(p.relative_to(archive_root)): p.read_bytes()
            for p in sorted(archive_root.rglob("*"))
            if p.is_file()
        }

    before = fingerprint()
    rc, _, err = _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "2026-06-07T13:00:00Z",
        ]
    )
    assert rc == 0, err
    after = fingerprint()
    assert before == after


# ---------------------------------------------------------------- input validation


def test_snapshot_rejects_invalid_generated_at(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    rc, _, err = _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "not-a-timestamp",
        ]
    )
    assert rc == 64
    assert "generated-at" in err


# ---------------------------------------------------------------- universal verifier integration


def test_universal_verify_autodetects_archive_snapshot(
    tmp_path: Path, archive_root: Path
) -> None:
    """``aip verify`` debe detectar el nuevo kind y delegar."""
    _seed_archive(tmp_path, archive_root)
    snap_path = tmp_path / "snap.json"
    _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "2026-06-07T13:00:00Z",
            "--output",
            str(snap_path),
        ]
    )
    rc, out, err = _run(["verify", str(snap_path)])
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["artifact_kind"] == "archive_snapshot"
    assert payload["ok"] is True


def test_universal_verify_detects_tampered_archive_snapshot(
    tmp_path: Path, archive_root: Path
) -> None:
    """Editar snapshot_hash en disco invalida la verificación universal."""
    _seed_archive(tmp_path, archive_root)
    snap_path = tmp_path / "snap.json"
    _run(
        [
            "archive",
            "snapshot",
            "--archive-root",
            str(archive_root),
            "--generated-at",
            "2026-06-07T13:00:00Z",
            "--output",
            str(snap_path),
        ]
    )
    data = json.loads(snap_path.read_text(encoding="utf-8"))
    data["snapshot_hash"] = "f" * 64
    snap_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    rc, out, _ = _run(["verify", str(snap_path)])
    assert rc == 1
    assert json.loads(out)["ok"] is False
