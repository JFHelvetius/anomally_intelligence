"""Tests del Snapshot Engine (ADR-0038)."""

from __future__ import annotations

import ast
import datetime as dt
import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip import Archive
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    InvestigationSnapshot,
    SnapshotNotFoundError,
    SnapshotReference,
    compute_snapshot_hash,
    create_snapshot,
    decode_snapshot,
    encode_snapshot,
    load_snapshot,
    persist_snapshot,
    snapshot_path,
    verify_snapshot,
)
from aip.storage import layout
from aip.timeline import build_timeline
from aip.workspace import create_workspace

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


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _w_and_t(tmp_path: Path, archive_root: Path):
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    t = build_timeline(
        archive_root=archive_root, workspace=w, timeline_id="tl"
    )
    return w, t


# ---------------------------------------------------------------- model


def test_schema_version_pinned() -> None:
    assert SNAPSHOT_SCHEMA_VERSION == "1"


def test_snapshot_reference_constructs() -> None:
    r = SnapshotReference(
        reference_type="evidence", identifier="E1", artifact_hash="a" * 64
    )
    assert r.reference_type == "evidence"


def test_snapshot_reference_rejects_bad_hash() -> None:
    with pytest.raises(ValueError):
        SnapshotReference(
            reference_type="evidence",
            identifier="E1",
            artifact_hash="bad",
        )


def test_snapshot_constructs(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s1", workspace=w, timeline=t)
    assert s.snapshot_id == "s1"
    assert s.workspace_hash == w.workspace_hash
    assert s.timeline_hash == t.timeline_hash


def test_snapshot_frozen(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s1", workspace=w, timeline=t)
    with pytest.raises(FrozenInstanceError):
        s.snapshot_id = "x"  # type: ignore[misc]


def test_snapshot_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="outside"):
        InvestigationSnapshot(
            snapshot_id="a/b",
            workspace_hash="f" * 64,
            timeline_hash="f" * 64,
            referenced_artifacts=(),
            snapshot_hash="0" * 64,
        )


def test_snapshot_rejects_duplicate_references() -> None:
    r = SnapshotReference(
        reference_type="evidence", identifier="E1", artifact_hash="a" * 64
    )
    with pytest.raises(ValueError, match="duplicate"):
        InvestigationSnapshot(
            snapshot_id="s",
            workspace_hash="f" * 64,
            timeline_hash="f" * 64,
            referenced_artifacts=(r, r),
            snapshot_hash="0" * 64,
        )


# ---------------------------------------------------------------- determinism


def test_snapshot_is_deterministic_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s1 = create_snapshot(snapshot_id="s1", workspace=w, timeline=t)
    s2 = create_snapshot(snapshot_id="s1", workspace=w, timeline=t)
    assert s1 == s2
    assert s1.snapshot_hash == s2.snapshot_hash


# ---------------------------------------------------------------- hashing


def test_verify_snapshot_success(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    assert verify_snapshot(s) is True


def test_verify_snapshot_failure_on_tampering() -> None:
    bad = InvestigationSnapshot(
        snapshot_id="s",
        workspace_hash="f" * 64,
        timeline_hash="f" * 64,
        referenced_artifacts=(),
        snapshot_hash="b" * 64,  # incorrecto
    )
    assert verify_snapshot(bad) is False


def test_compute_snapshot_hash_matches_stored(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    assert compute_snapshot_hash(s) == s.snapshot_hash


# ---------------------------------------------------------------- encoding


def test_encode_decode_roundtrip(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    payload = encode_snapshot(s)
    decoded = decode_snapshot(payload)
    assert decoded == s


def test_encode_is_canonical(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    payload = encode_snapshot(s)
    parsed = json.loads(payload)
    canonical = (
        json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    assert payload == canonical


# ---------------------------------------------------------------- persistence


def test_persist_and_load(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s1", workspace=w, timeline=t)
    persist_snapshot(s, archive_root=archive_root)
    canonical = snapshot_path(archive_root, "s1")
    assert canonical.is_file()
    loaded = load_snapshot(archive_root=archive_root, snapshot_id="s1")
    assert loaded == s


def test_load_missing_raises(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(SnapshotNotFoundError):
        load_snapshot(archive_root=archive_root, snapshot_id="ghost")


def test_persist_extra_output(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    extra = tmp_path / "out" / "s.json"
    persist_snapshot(s, archive_root=archive_root, extra_output=extra)
    canonical = snapshot_path(archive_root, "s")
    assert extra.read_bytes() == canonical.read_bytes()


# ---------------------------------------------------------------- removability


def test_snapshot_does_not_modify_archive_manifest(
    tmp_path: Path, archive_root: Path
) -> None:
    w, t = _w_and_t(tmp_path, archive_root)
    pre = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    s = create_snapshot(snapshot_id="s", workspace=w, timeline=t)
    persist_snapshot(s, archive_root=archive_root)
    post = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    assert pre == post


# ---------------------------------------------------------------- G3


def test_snapshot_imports_no_forbidden_engines() -> None:
    """ADR-0038 §G3: snapshot/ no importa de graph/impact/context/diff."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "snapshot"
    forbidden = {"graph", "impact", "context", "diff", "analysis"}
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if (
                    len(parts) >= 2
                    and parts[0] == "aip"
                    and parts[1] in forbidden
                ):
                    offenders.append((module_path.name, node.module))
            elif isinstance(node, ast.Import):
                for n in node.names:
                    parts = n.name.split(".")
                    if (
                        len(parts) >= 2
                        and parts[0] == "aip"
                        and parts[1] in forbidden
                    ):
                        offenders.append((module_path.name, n.name))
    assert offenders == [], (
        f"snapshot/ imports forbidden engines: {offenders}"
    )


# ---------------------------------------------------------------- forbidden tokens

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "danger",
    "likelihood",
    "probability",
    "bayesian",
    "confidence_score",
    "recommend_action",
    "recommendation",
    "ranking",
    "embedding",
    "clustering",
    "causal_inference",
    "hypothesis",
    "explanation",
)


def _snapshot_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "snapshot"
    cli_module = repo / "src" / "aip" / "cli" / "snapshot_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_snapshot_module() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _snapshot_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], (
        f"Forbidden tokens in snapshot: {offenders}"
    )
