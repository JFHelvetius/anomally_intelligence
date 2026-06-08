"""Tests del builder + persistencia + hashes de Timeline (ADR-0037)."""

from __future__ import annotations

import ast
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.storage import layout
from aip.timeline import (
    TimelineNotFoundError,
    build_timeline,
    compute_timeline_hash,
    decode_timeline,
    encode_timeline,
    load_timeline,
    persist_timeline,
    timeline_path,
    verify_timeline_hash,
)
from aip.workspace import InvestigationWorkspace, create_workspace

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
        actor="@test",
    )
    return a.assessment_id


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- build


def test_build_timeline_empty_when_no_referenced_artifacts(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl-empty")
    assert tl.event_count == 0
    assert tl.ordered_events == ()
    assert tl.first_timestamp is None
    assert tl.last_timestamp is None


def test_build_timeline_with_evidence_reference(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl-ev")
    assert tl.event_count == 1
    e = tl.ordered_events[0]
    assert e.artifact_type == "evidence"
    assert e.source_reference == "evidence.ingested_at"
    assert e.observed_at == CANONICAL_TS


def test_build_timeline_with_assessment_reference(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("assessment", a_id)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl-a")
    assert tl.event_count == 1
    assert tl.ordered_events[0].artifact_type == "assessment"
    assert tl.ordered_events[0].source_reference == "assessment.created_at"


def test_build_timeline_skips_impact_and_context(tmp_path: Path, archive_root: Path) -> None:
    """impact_analysis y context_bundle se omiten (ADR-0037 §alcance)."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[
            ("evidence", ev_hash),
            ("impact_analysis", "I1"),
            ("context_bundle", "C1"),
        ],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    # Sólo el evento de evidence; los otros dos se omiten.
    assert tl.event_count == 1
    assert tl.ordered_events[0].artifact_type == "evidence"


def test_build_timeline_skips_missing_evidence(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", "f" * 64)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    assert tl.event_count == 0


def test_build_raises_when_archive_missing(tmp_path: Path) -> None:
    # Construir manualmente un workspace válido para forzar la rama
    # temprana de validación del archive.
    w = InvestigationWorkspace(
        workspace_id="w",
        title="t",
        references=(),
        source_manifest_hash="f" * 64,
        workspace_hash="0" * 64,
    )
    with pytest.raises(FileNotFoundError):
        build_timeline(
            archive_root=tmp_path / "ghost",
            workspace=w,
            timeline_id="tl",
        )


# ---------------------------------------------------------------- determinism


def test_build_timeline_is_deterministic_across_runs(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[
            ("evidence", ev_hash),
            ("assessment", _assess(archive_root, ev_hash)),
        ],
    )
    t1 = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    t2 = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    assert t1 == t2
    assert t1.timeline_hash == t2.timeline_hash


# ---------------------------------------------------------------- hashing


def test_verify_timeline_hash_success(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    assert verify_timeline_hash(tl) is True


def test_compute_timeline_hash_matches_stored(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    assert compute_timeline_hash(tl) == tl.timeline_hash


# ---------------------------------------------------------------- encoding


def test_encode_decode_roundtrip(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    payload = encode_timeline(tl)
    decoded = decode_timeline(payload)
    assert decoded == tl


def test_encode_is_canonical(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    payload = encode_timeline(tl)
    parsed = json.loads(payload)
    canonical = json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert payload == canonical


# ---------------------------------------------------------------- persistence


def test_persist_and_load(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl-01")
    persist_timeline(
        tl,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    canonical = timeline_path(archive_root, "tl-01")
    assert canonical.is_file()
    loaded = load_timeline(archive_root=archive_root, timeline_id="tl-01")
    assert loaded == tl


def test_load_missing_raises(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(TimelineNotFoundError):
        load_timeline(archive_root=archive_root, timeline_id="ghost")


def test_persist_extra_output(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    extra = tmp_path / "out" / "tl.json"
    persist_timeline(
        tl,
        archive_root=archive_root,
        extra_output=extra,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    canonical = timeline_path(archive_root, "tl")
    assert extra.read_bytes() == canonical.read_bytes()


# ---------------------------------------------------------------- removability


def test_timeline_does_not_modify_archive_manifest(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    pre = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl")
    persist_timeline(
        tl,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    post = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    assert pre == post


# ---------------------------------------------------------------- G3 (no engines)


def test_timeline_imports_no_forbidden_engines() -> None:
    """ADR-0037 §G3: ningún módulo de ``aip.timeline`` importa de
    ``aip.graph``, ``aip.impact``, ``aip.context``, ``aip.snapshot``
    o ``aip.diff``."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "timeline"
    forbidden = {"graph", "impact", "context", "snapshot", "diff"}
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "aip" and parts[1] in forbidden:
                    offenders.append((module_path.name, node.module))
            elif isinstance(node, ast.Import):
                for n in node.names:
                    parts = n.name.split(".")
                    if len(parts) >= 2 and parts[0] == "aip" and parts[1] in forbidden:
                        offenders.append((module_path.name, n.name))
    assert offenders == [], f"timeline/ imports forbidden engines: {offenders}"
