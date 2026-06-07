"""Tests del builder ``build_graph`` (ADR-0033 §builder)."""

from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive, ArchiveNotFoundError
from aip.analysis.authentication import AssessmentMethod
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph import build_graph
from aip.graph.models import EdgeKind, NodeKind

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path, source_id: str = "blue-book-nara"):
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


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- error paths


def test_build_graph_raises_when_archive_missing(tmp_path: Path) -> None:
    with pytest.raises(ArchiveNotFoundError):
        build_graph(tmp_path / "does-not-exist")


def test_build_graph_raises_when_not_an_archive(archive_root: Path) -> None:
    # archive_root existe pero no tiene la estructura canónica.
    with pytest.raises(ArchiveNotFoundError):
        build_graph(archive_root)


# ---------------------------------------------------------------- empty archive


def test_build_graph_empty_archive_has_no_nodes_or_edges(
    tmp_path: Path, archive_root: Path
) -> None:
    # Ingestamos algo para que el archive tenga estructura canónica,
    # luego limpiamos las tablas a mano para volver a "vacío" lógico.
    # En su lugar, construimos un archive válido pero sin filas.
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    # Borrar todas las filas (mantenemos layout / manifest / audit).
    shutil.rmtree(archive_root / "tables")
    (archive_root / "tables").mkdir()
    for table in (
        "evidence",
        "sources",
        "provenance",
        "provenance_steps",
        "authentication_assessments",
    ):
        (archive_root / "tables" / table).mkdir()

    graph = build_graph(archive_root)
    assert graph.nodes == ()
    assert graph.edges == ()


# ---------------------------------------------------------------- single evidence


def test_build_graph_single_evidence_emits_two_nodes_one_edge(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    graph = build_graph(archive_root)
    # Un evidence + un source = 2 nodos.
    assert len(graph.nodes) == 2
    kinds = {n.kind for n in graph.nodes}
    assert kinds == {NodeKind.EVIDENCE, NodeKind.SOURCE}
    # Una arista sourced_from.
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.kind is EdgeKind.SOURCED_FROM
    assert edge.src.id == evidence.hash
    assert edge.dst.id == "blue-book-nara"


# ---------------------------------------------------------------- multiple evidences


def test_build_graph_multiple_evidences_sharing_source(
    tmp_path: Path, archive_root: Path
) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    ev_a = _ingest(archive_root, blob_a)
    ev_b = _ingest(archive_root, blob_b)
    graph = build_graph(archive_root)
    # 2 evidence + 1 source = 3 nodos.
    assert len(graph.nodes) == 3
    # 2 sourced_from edges.
    sourced_edges = [e for e in graph.edges if e.kind is EdgeKind.SOURCED_FROM]
    assert len(sourced_edges) == 2
    src_ids = {e.src.id for e in sourced_edges}
    assert src_ids == {ev_a.hash, ev_b.hash}


def test_build_graph_multiple_sources(tmp_path: Path, archive_root: Path) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    _ingest(archive_root, blob_a, source_id="source-alpha")
    _ingest(archive_root, blob_b, source_id="source-beta")
    graph = build_graph(archive_root)
    # 2 evidence + 2 source = 4 nodos.
    assert len(graph.nodes) == 4
    sources = {n.id for n in graph.nodes if n.kind is NodeKind.SOURCE}
    assert sources == {"source-alpha", "source-beta"}


# ---------------------------------------------------------------- with assessments


def test_build_graph_with_assessment_emits_three_edge_kinds(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_fixed_clock(CANONICAL_TS),
    )
    graph = build_graph(archive_root)
    # 1 evidence + 1 source + 1 assessment = 3 nodos.
    assert len(graph.nodes) == 3
    kinds = {n.kind for n in graph.nodes}
    assert kinds == {NodeKind.EVIDENCE, NodeKind.SOURCE, NodeKind.ASSESSMENT}
    # 3 aristas: sourced_from (ev → src), assessed_from (a → ev),
    # derived_from (a → src).
    edge_kinds = {e.kind for e in graph.edges}
    assert edge_kinds == {
        EdgeKind.SOURCED_FROM,
        EdgeKind.ASSESSED_FROM,
        EdgeKind.DERIVED_FROM,
    }


def test_build_graph_multiple_assessments_same_evidence(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    for method in (
        AssessmentMethod.MANUAL_RESEARCH,
        AssessmentMethod.PROVENANCE_REVIEW,
        AssessmentMethod.CHAIN_OF_CUSTODY_REVIEW,
    ):
        archive.assess_authentication(
            evidence_id=evidence.hash,
            method=method,
            clock=_fixed_clock(CANONICAL_TS),
        )
    graph = build_graph(archive_root)
    # 1 evidence + 1 source + 3 assessments = 5 nodos.
    assert len(graph.nodes) == 5
    assert (
        sum(1 for n in graph.nodes if n.kind is NodeKind.ASSESSMENT) == 3
    )
    # 1 sourced_from + 3 assessed_from + 3 derived_from = 7 aristas.
    assert len(graph.edges) == 7


# ---------------------------------------------------------------- determinism


def test_build_graph_is_deterministic_across_runs(
    tmp_path: Path, archive_root: Path
) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    _ingest(archive_root, blob_a)
    _ingest(archive_root, blob_b)
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=_ingest(archive_root, blob_a).hash,
        clock=_fixed_clock(CANONICAL_TS),
    )
    g1 = build_graph(archive_root)
    g2 = build_graph(archive_root)
    assert g1 == g2
    assert g1.nodes == g2.nodes
    assert g1.edges == g2.edges


def test_build_graph_nodes_are_canonically_ordered(
    tmp_path: Path, archive_root: Path
) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    _ingest(archive_root, blob_a, source_id="zeta-archive")
    _ingest(archive_root, blob_b, source_id="alpha-archive")
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=_ingest(archive_root, blob_a, source_id="zeta-archive").hash,
        clock=_fixed_clock(CANONICAL_TS),
    )
    graph = build_graph(archive_root)
    # Verificamos orden por (kind.value, id) en posición.
    for i in range(len(graph.nodes) - 1):
        a = graph.nodes[i]
        b = graph.nodes[i + 1]
        assert (a.kind.value, a.id) <= (b.kind.value, b.id)


def test_build_graph_edges_are_canonically_ordered(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=evidence.hash, clock=_fixed_clock(CANONICAL_TS)
    )
    graph = build_graph(archive_root)
    keys = [
        (
            e.kind.value,
            e.src.kind.value,
            e.src.id,
            e.dst.kind.value,
            e.dst.id,
        )
        for e in graph.edges
    ]
    assert keys == sorted(keys)


# ---------------------------------------------------------------- broken refs


def test_build_graph_emits_edge_with_phantom_dst_when_source_deleted(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    # Borrar la fila de Source (rotura de ref).
    src_row = archive_root / "tables" / "sources" / "blue-book-nara.parquet"
    src_row.unlink()
    graph = build_graph(archive_root)
    # Sigue habiendo Evidence en nodos pero no Source.
    assert any(n.kind is NodeKind.EVIDENCE for n in graph.nodes)
    assert not any(n.kind is NodeKind.SOURCE for n in graph.nodes)
    # La arista sourced_from sigue presente con dst phantom.
    sourced = [e for e in graph.edges if e.kind is EdgeKind.SOURCED_FROM]
    assert len(sourced) == 1
    assert sourced[0].src.id == evidence.hash
    assert sourced[0].dst.kind is NodeKind.SOURCE
