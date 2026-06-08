"""Tests de las queries del grafo (ADR-0033 §queries)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph import build_graph, validate_graph_integrity
from aip.graph.models import EdgeKind, EvidenceGraph, GraphEdge, GraphNode, NodeKind
from aip.graph.query import (
    GraphIntegrityIssueKind,
    get_assessments_for_evidence,
    get_dependency_chain,
    get_evidence_for_assessment,
    get_reverse_dependencies,
)

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path):
    archive = Archive.open(archive_root)
    return archive.ingest_evidence(
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


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _assess(archive_root: Path, evidence_id: str, method=None):
    archive = Archive.open(archive_root)
    return archive.assess_authentication(
        evidence_id=evidence_id,
        method=method or AssessmentMethod.PROVENANCE_REVIEW,
        clock=_fixed_clock(CANONICAL_TS),
        actor="@test",
    )


# ---------------------------------------------------------------- get_assessments_for_evidence


def test_get_assessments_for_evidence_empty_when_none(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    assert get_assessments_for_evidence(graph, evidence.hash) == ()


def test_get_assessments_for_evidence_returns_one(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    found = get_assessments_for_evidence(graph, evidence.hash)
    assert len(found) == 1
    assert found[0].kind is NodeKind.ASSESSMENT
    assert found[0].id == assessment.assessment_id


def test_get_assessments_for_evidence_returns_all_methods_sorted(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    for method in (
        AssessmentMethod.MANUAL_RESEARCH,
        AssessmentMethod.PROVENANCE_REVIEW,
        AssessmentMethod.CHAIN_OF_CUSTODY_REVIEW,
    ):
        _assess(archive_root, evidence.hash, method)
    graph = build_graph(archive_root)
    found = get_assessments_for_evidence(graph, evidence.hash)
    assert len(found) == 3
    # Orden estable por (kind.value, id).
    ids = [n.id for n in found]
    assert ids == sorted(ids)


# ---------------------------------------------------------------- get_evidence_for_assessment


def test_get_evidence_for_assessment_returns_evidence(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    result = get_evidence_for_assessment(graph, assessment.assessment_id)
    assert result is not None
    assert result.kind is NodeKind.EVIDENCE
    assert result.id == evidence.hash


def test_get_evidence_for_assessment_returns_none_when_not_found(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    assert get_evidence_for_assessment(graph, "ghost__provenance_review") is None


# ---------------------------------------------------------------- get_dependency_chain


def test_get_dependency_chain_from_source_is_empty(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    source_node = next(n for n in graph.nodes if n.kind is NodeKind.SOURCE)
    assert get_dependency_chain(graph, source_node) == ()


def test_get_dependency_chain_from_evidence_returns_source(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    ev_node = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    chain = get_dependency_chain(graph, ev_node)
    assert len(chain) == 1
    assert chain[0].kind is NodeKind.SOURCE


def test_get_dependency_chain_from_assessment_returns_evidence_and_sources(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    a_node = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id)
    chain = get_dependency_chain(graph, a_node)
    kinds = {n.kind for n in chain}
    # Llega tanto a evidence como a source (via assessed_from y derived_from).
    assert kinds == {NodeKind.EVIDENCE, NodeKind.SOURCE}


# ---------------------------------------------------------------- get_reverse_dependencies


def test_get_reverse_dependencies_from_source_returns_evidence_and_assessments(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    src_node = next(n for n in graph.nodes if n.kind is NodeKind.SOURCE)
    reverse = get_reverse_dependencies(graph, src_node)
    kinds = {n.kind for n in reverse}
    # La Source tiene Evidence dependiente directa (sourced_from) y
    # Assessment dependiente directa (derived_from).
    assert NodeKind.EVIDENCE in kinds
    assert NodeKind.ASSESSMENT in kinds


def test_get_reverse_dependencies_from_evidence_returns_assessments(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    ev_node = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    reverse = get_reverse_dependencies(graph, ev_node)
    assert all(n.kind is NodeKind.ASSESSMENT for n in reverse)
    assert len(reverse) == 1


def test_get_reverse_dependencies_from_assessment_is_empty(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    a_node = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id)
    # Nada depende de un assessment en V1.
    assert get_reverse_dependencies(graph, a_node) == ()


# ---------------------------------------------------------------- transitive ordering


def test_dependency_chain_results_are_canonically_ordered(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    a_node = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id)
    chain = get_dependency_chain(graph, a_node)
    keys = [(n.kind.value, n.id) for n in chain]
    assert keys == sorted(keys)


# ---------------------------------------------------------------- validate_graph_integrity


def test_validate_graph_integrity_clean_graph_has_no_issues(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    assert validate_graph_integrity(graph) == ()


def test_validate_graph_integrity_reports_dangling_dst_on_missing_source(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    src_row = archive_root / "tables" / "sources" / "blue-book-nara.parquet"
    src_row.unlink()
    graph = build_graph(archive_root)
    issues = validate_graph_integrity(graph)
    assert len(issues) == 1
    assert issues[0].kind is GraphIntegrityIssueKind.DANGLING_DST
    assert issues[0].edge.kind is EdgeKind.SOURCED_FROM


def test_validate_graph_integrity_detects_dangling_src() -> None:
    # Construimos un grafo sintético con una arista cuyo src no es nodo.
    phantom_src = GraphNode(kind=NodeKind.ASSESSMENT, id="a" * 64 + "__provenance_review")
    real_dst = GraphNode(kind=NodeKind.EVIDENCE, id="b" * 64)
    edge = GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=phantom_src, dst=real_dst)
    g = EvidenceGraph(nodes=(real_dst,), edges=(edge,))
    issues = validate_graph_integrity(g)
    assert any(i.kind is GraphIntegrityIssueKind.DANGLING_SRC for i in issues)


# ---------------------------------------------------------------- removability


def test_building_graph_does_not_modify_archive(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)

    def snapshot() -> dict[str, bytes]:
        snap: dict[str, bytes] = {}
        for table in (
            "evidence",
            "sources",
            "provenance",
            "provenance_steps",
            "authentication_assessments",
        ):
            for entry in sorted((archive_root / "tables" / table).glob("*.parquet")):
                snap[f"{table}/{entry.name}"] = entry.read_bytes()
        snap["audit.log"] = (archive_root / "audit.log").read_bytes()
        snap["manifest.json"] = (archive_root / "manifest.json").read_bytes()
        return snap

    before = snapshot()
    _ = build_graph(archive_root)
    after = snapshot()
    assert before == after


def test_archive_verify_passes_after_graph_build(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    archive = Archive.open(archive_root)
    pre = archive.verify(full=True)
    assert pre.ok is True
    pre_hash = pre.archive_manifest_hash

    _ = build_graph(archive_root)

    post = archive.verify(full=True)
    assert post.ok is True
    # Manifest hash inalterado: el grafo no escribe nada.
    assert post.archive_manifest_hash == pre_hash
