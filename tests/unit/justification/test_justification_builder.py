"""Tests del builder + persistencia + hashes de Justification (ADR-0040)."""

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
from aip.justification import (
    JustificationAnchorNotFoundError,
    JustificationNotFoundError,
    build_justification,
    compute_justification_diff,
    compute_justification_diff_hash,
    compute_justification_hash,
    decode_justification,
    decode_justification_diff,
    encode_justification,
    encode_justification_diff,
    justification_path,
    load_justification,
    persist_justification,
    verify_justification_diff,
    verify_justification_hash,
)
from aip.storage import layout
from aip.workspace import create_workspace, persist_workspace

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


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- error paths


def test_build_raises_when_archive_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_justification(
            archive_root=tmp_path / "ghost",
            conclusion_anchor_type="assessment",
            conclusion_anchor_id="A1",
            justification_id="j",
        )


def test_build_raises_when_archive_not_archive(archive_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_justification(
            archive_root=archive_root,
            conclusion_anchor_type="assessment",
            conclusion_anchor_id="A1",
            justification_id="j",
        )


def test_build_raises_when_anchor_missing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(JustificationAnchorNotFoundError):
        build_justification(
            archive_root=archive_root,
            conclusion_anchor_type="assessment",
            conclusion_anchor_id="ghost__provenance_review",
            justification_id="j",
        )


def test_build_rejects_non_assessment_anchor_type(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(ValueError, match="V1 only supports 'assessment'"):
        build_justification(
            archive_root=archive_root,
            conclusion_anchor_type="hypothesis",
            conclusion_anchor_id="x",
            justification_id="j",
        )


# ---------------------------------------------------------------- happy path


def test_build_minimal_chain_populates_categories(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j-01",
    )
    assert j.justification_id == "j-01"
    assert j.conclusion_anchor_id == a_id
    # minimal_evidence: la evidence + la source citada por el assessment.
    roles = {e.entry_role for e in j.minimal_evidence}
    assert "evidence" in roles
    assert "source" in roles
    # supporting_assessments: el anchor.
    assert len(j.supporting_assessments) == 1
    assert j.supporting_assessments[0].entry_identifier == a_id
    # provenance_chain: al menos un paso (ingest produce un paso).
    assert len(j.provenance_chain) >= 1
    # graph_nodes_used: poblado por dependency chain.
    assert len(j.graph_nodes_used) >= 1
    # intermediate_artifacts: vacío en V1.
    assert j.intermediate_artifacts == ()


def test_build_with_workspace_scope(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(w, archive_root=archive_root)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
        workspace_id="w-01",
    )
    assert j.workspace_hash == w.workspace_hash


def test_build_without_workspace_has_none_workspace_hash(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    assert j.workspace_hash is None


# ---------------------------------------------------------------- determinism


def test_build_is_deterministic_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j1 = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    j2 = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    assert j1 == j2
    assert j1.justification_hash == j2.justification_hash


def test_workspace_scope_changes_hash(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(w, archive_root=archive_root)
    j_no_ws = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    j_ws = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
        workspace_id="w-01",
    )
    assert j_no_ws.justification_hash != j_ws.justification_hash


# ---------------------------------------------------------------- hashing


def test_verify_justification_hash_success(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    assert verify_justification_hash(j) is True


def test_compute_justification_hash_matches_stored(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    assert compute_justification_hash(j) == j.justification_hash


# ---------------------------------------------------------------- encoding


def test_encode_decode_roundtrip(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    payload = encode_justification(j)
    decoded = decode_justification(payload)
    assert decoded == j


def test_encode_is_canonical(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    payload = encode_justification(j)
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
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j-01",
    )
    persist_justification(j, archive_root=archive_root)
    canonical = justification_path(archive_root, "j-01")
    assert canonical.is_file()
    loaded = load_justification(
        archive_root=archive_root, justification_id="j-01"
    )
    assert loaded == j


def test_load_missing_raises(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(JustificationNotFoundError):
        load_justification(
            archive_root=archive_root, justification_id="ghost"
        )


def test_persist_extra_output(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    extra = tmp_path / "out" / "j.json"
    persist_justification(
        j, archive_root=archive_root, extra_output=extra
    )
    canonical = justification_path(archive_root, "j")
    assert extra.read_bytes() == canonical.read_bytes()


# ---------------------------------------------------------------- removability


def test_persistence_does_not_modify_archive_manifest(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    pre = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    persist_justification(j, archive_root=archive_root)
    post = (archive_root / layout.MANIFEST_FILENAME).read_bytes()
    assert pre == post


# ---------------------------------------------------------------- G3 (no engines)


def test_justification_imports_no_forbidden_modules() -> None:
    """ADR-0040 §G3: justification/ no importa de impact/context/
    timeline/snapshot/diff ni de ML/red."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "justification"
    forbidden_aip = {"impact", "context", "timeline", "snapshot", "diff"}
    forbidden_external = {
        "numpy",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "openai",
        "anthropic",
        "requests",
        "urllib",
        "urllib3",
        "httpx",
    }
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    mods.append(n.name)
            for mod in mods:
                parts = mod.split(".")
                if (
                    len(parts) >= 2
                    and parts[0] == "aip"
                    and parts[1] in forbidden_aip
                ):
                    offenders.append((module_path.name, mod))
                if parts[0] in forbidden_external:
                    offenders.append((module_path.name, mod))
    assert offenders == [], (
        f"justification/ imports forbidden modules: {offenders}"
    )


# ---------------------------------------------------------------- diff


def test_compute_diff_identical_yields_unchanged(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    d = compute_justification_diff(j, j)
    assert d.added_entries == ()
    assert d.removed_entries == ()
    assert len(d.unchanged_entries) >= 1


def test_compute_diff_workspace_scope_differs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(w, archive_root=archive_root)
    j_a = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    j_b = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
        workspace_id="w",
    )
    d = compute_justification_diff(j_a, j_b)
    # workspace_hash difiere pero las chain entries (que es lo que el diff
    # compara) son idénticas porque las dos justificaciones están sobre el
    # mismo assessment.
    assert d.added_entries == ()
    assert d.removed_entries == ()
    assert len(d.unchanged_entries) >= 1
    assert d.justification_a_hash != d.justification_b_hash


def test_verify_diff_success(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    d = compute_justification_diff(j, j)
    assert verify_justification_diff(d) is True


def test_compute_diff_hash_matches(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    d = compute_justification_diff(j, j)
    assert compute_justification_diff_hash(d) == d.diff_hash


def test_diff_encode_decode_roundtrip(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j",
    )
    d = compute_justification_diff(j, j)
    payload = encode_justification_diff(d)
    decoded = decode_justification_diff(payload)
    assert decoded == d
