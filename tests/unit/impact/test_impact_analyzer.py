"""Tests del analizador de impacto (ADR-0034 §función núcleo).

Cubre las cinco preguntas del spec, determinismo, reproducibilidad,
ciclos defensivos, y errores.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import AssessmentMethod
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph import build_graph
from aip.graph.models import EdgeKind, EvidenceGraph, GraphEdge, GraphNode, NodeKind
from aip.impact import (
    IMPACT_ENGINE_VERSION,
    ImpactReport,
    ImpactRootNotInGraphError,
    analyze_removal_impact,
)
from aip.impact.analyzer import report_to_impact_nodes

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path, *, source_id: str = "blue-book-nara"):
    archive = Archive.open(archive_root)
    return archive.ingest_evidence(
        blob,
        source_id=source_id,
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


def _assess(archive_root: Path, evidence_id: str, method=None):
    archive = Archive.open(archive_root)
    return archive.assess_authentication(
        evidence_id=evidence_id,
        method=method or AssessmentMethod.PROVENANCE_REVIEW,
        clock=_fixed_clock(CANONICAL_TS),
        actor="@test",
    )


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- error paths


def test_analyze_raises_when_root_not_in_graph(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    phantom = GraphNode(kind=NodeKind.EVIDENCE, id="f" * 64)
    with pytest.raises(ImpactRootNotInGraphError):
        analyze_removal_impact(graph, phantom)


def test_report_to_impact_nodes_raises_when_root_not_in_graph(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    phantom = GraphNode(kind=NodeKind.ASSESSMENT, id="ghost__provenance_review")
    with pytest.raises(ImpactRootNotInGraphError):
        report_to_impact_nodes(graph, phantom)


# ---------------------------------------------------------------- empty impact


def test_assessment_root_has_empty_impact(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id)
    report = analyze_removal_impact(graph, target)
    assert report.total_affected_nodes == 0
    assert report.dependency_depth_max == 0
    assert report.affected_assessments == []
    assert report.affected_evidence == []


def test_evidence_root_with_no_assessments_has_empty_impact(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    report = analyze_removal_impact(graph, target)
    assert report.total_affected_nodes == 0
    assert report.affected_assessments == []
    assert report.affected_evidence == []


# ---------------------------------------------------------------- single dependency


def test_evidence_root_with_one_assessment_reports_one_affected(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    report = analyze_removal_impact(graph, target)
    assert report.total_affected_nodes == 1
    assert report.dependency_depth_max == 1
    assert report.affected_assessments == [assessment.assessment_id]


# ---------------------------------------------------------------- branching


def test_evidence_root_with_multiple_assessments_reports_all(
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
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    report = analyze_removal_impact(graph, target)
    assert report.total_affected_nodes == 3
    assert report.dependency_depth_max == 1
    assert len(report.affected_assessments) == 3
    # Canonical order.
    assert report.affected_assessments == sorted(report.affected_assessments)


# ---------------------------------------------------------------- deep chain (source root)


def test_source_root_propagates_to_evidence_and_assessments(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob, source_id="blue-book-nara")
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.SOURCE, id="blue-book-nara")
    report = analyze_removal_impact(graph, target)
    # Source → evidence (depth 1) + assessment vía sourced_from/derived_from.
    assert evidence.hash in report.affected_evidence
    assert len(report.affected_assessments) == 1
    # Depth máxima: assessment vía derived_from (distancia 1) o vía
    # evidence (distancia 2). El BFS toma la mínima = 1.
    assert report.dependency_depth_max >= 1
    assert report.total_affected_nodes == 2


def test_source_root_with_multiple_evidences(tmp_path: Path, archive_root: Path) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    ev_a = _ingest(archive_root, blob_a, source_id="shared-source")
    ev_b = _ingest(archive_root, blob_b, source_id="shared-source")
    _assess(archive_root, ev_a.hash)
    _assess(archive_root, ev_b.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.SOURCE, id="shared-source")
    report = analyze_removal_impact(graph, target)
    # 2 evidence + 2 assessment = 4.
    assert report.total_affected_nodes == 4
    assert set(report.affected_evidence) == {ev_a.hash, ev_b.hash}
    assert len(report.affected_assessments) == 2


# ---------------------------------------------------------------- deterministic ordering


def test_affected_assessments_are_canonically_sorted(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    for method in (
        AssessmentMethod.MANUAL_RESEARCH,
        AssessmentMethod.PROVENANCE_REVIEW,
        AssessmentMethod.CHAIN_OF_CUSTODY_REVIEW,
    ):
        _assess(archive_root, evidence.hash, method)
    graph = build_graph(archive_root)
    report = analyze_removal_impact(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    assert report.affected_assessments == sorted(report.affected_assessments)


def test_impact_nodes_are_canonically_sorted(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob, source_id="shared")
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    nodes = report_to_impact_nodes(graph, GraphNode(kind=NodeKind.SOURCE, id="shared"))
    keys = [(n.distance_from_root, n.node_type, n.node_id) for n in nodes]
    assert keys == sorted(keys)


# ---------------------------------------------------------------- reproducibility


def test_impact_report_is_deterministic_across_runs(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    r1 = analyze_removal_impact(graph, target)
    r2 = analyze_removal_impact(graph, target)
    assert r1 == r2


def test_impact_does_not_modify_archive(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    archive = Archive.open(archive_root)
    pre_hash = archive.verify(full=True).archive_manifest_hash
    graph = build_graph(archive_root)
    analyze_removal_impact(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    post_hash = archive.verify(full=True).archive_manifest_hash
    assert pre_hash == post_hash


# ---------------------------------------------------------------- honesty fields


def test_report_carries_engine_version(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    report = analyze_removal_impact(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    assert report.analysis_engine_version == IMPACT_ENGINE_VERSION


def test_report_carries_schema_version(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    report = analyze_removal_impact(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    assert report.schema_version == SCHEMA_VERSION


def test_report_carries_analysis_method_name(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    report = analyze_removal_impact(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    assert report.analysis_method_name == "dependency_reachability_v1"


# ---------------------------------------------------------------- cycle safety


def test_synthetic_cycle_does_not_loop_forever() -> None:
    """ADR-0034 §función núcleo §cycle safety: el BFS termina aunque
    el grafo de entrada contenga un ciclo (no debería por construcción
    ADR-0033, pero defendemos por seguridad)."""
    a = GraphNode(kind=NodeKind.EVIDENCE, id="a" * 64)
    b = GraphNode(kind=NodeKind.EVIDENCE, id="b" * 64)
    # Cycle: a depends on b, b depends on a. Aristas sintéticas
    # (no son edge types canónicos del modelo V1; permitido para test).
    e1 = GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=a, dst=b)
    e2 = GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=b, dst=a)
    graph = EvidenceGraph(nodes=(a, b), edges=(e1, e2))
    # Sin timeout: si esto cuelga, el BFS no termina.
    report = analyze_removal_impact(graph, a)
    # a no está incluido en sí mismo; b sí.
    assert report.root_node_id == a.id
    assert report.total_affected_nodes == 1
    assert report.dependency_depth_max == 1


def test_root_is_excluded_from_affected_nodes(tmp_path: Path, archive_root: Path) -> None:
    """Un nodo nunca es dependencia inversa de sí mismo."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    report = analyze_removal_impact(graph, target)
    assert evidence.hash not in report.affected_evidence
    assert evidence.hash not in report.affected_assessments


# ---------------------------------------------------------------- distance tracking


def test_distance_from_root_is_one_for_direct_neighbors(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    graph = build_graph(archive_root)
    nodes = report_to_impact_nodes(graph, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash))
    assert all(n.distance_from_root == 1 for n in nodes)


def test_distance_is_minimum_for_diamond_graph() -> None:
    """En diamond pattern (root → a → x y root → b → x), la distancia
    de x es 2 vía cualquier camino. BFS encuentra la mínima."""
    root = GraphNode(kind=NodeKind.SOURCE, id="root")
    a = GraphNode(kind=NodeKind.EVIDENCE, id="a" * 64)
    b = GraphNode(kind=NodeKind.EVIDENCE, id="b" * 64)
    x = GraphNode(kind=NodeKind.ASSESSMENT, id="x" * 64 + "__provenance_review")
    # Aristas: x → a (assessed_from), x → b (assessed_from),
    # a → root (sourced_from), b → root (sourced_from).
    edges = (
        GraphEdge(kind=EdgeKind.SOURCED_FROM, src=a, dst=root),
        GraphEdge(kind=EdgeKind.SOURCED_FROM, src=b, dst=root),
        GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=x, dst=a),
        GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=x, dst=b),
    )
    graph = EvidenceGraph(nodes=(root, a, b, x), edges=tuple(sorted(edges)))
    report = analyze_removal_impact(graph, root)
    # a, b están a distancia 1; x a distancia 2.
    assert report.dependency_depth_max == 2
    assert report.total_affected_nodes == 3


# ---------------------------------------------------------------- composability


def test_impact_report_is_dataclass_serializable() -> None:
    """El reporte debe ser convertible a dict (para JSON CLI). Usa
    dataclasses.asdict como prueba de que no hay tipos opacos."""
    r = ImpactReport(
        root_node_id="root",
        affected_assessments=["a", "b"],
        affected_evidence=[],
        dependency_depth_max=1,
        total_affected_nodes=2,
        analysis_engine_version=IMPACT_ENGINE_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    d = dataclasses.asdict(r)
    assert d["root_node_id"] == "root"
    assert d["affected_assessments"] == ["a", "b"]
    assert d["analysis_method_name"] == "dependency_reachability_v1"
