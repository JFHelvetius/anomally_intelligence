"""Tests del assembler (ADR-0035 §función núcleo)."""

from __future__ import annotations

import ast
import dataclasses as dc
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import AssessmentMethod
from aip.context import (
    ASSEMBLY_ENGINE_VERSION,
    ASSEMBLY_METHOD_NAME,
    ContextAnchorNotFoundError,
    ContextAssemblyError,
    ContextBundle,
    GraphNeighborhood,
    assemble_context,
    compute_context_bundle_hash,
    verify_bundle_hash,
)
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph import build_graph
from aip.graph.models import GraphNode, NodeKind
from aip.impact import analyze_removal_impact
from aip.storage import layout
from aip.storage.manifest import ArchiveManifest

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(
    archive_root: Path, blob: Path, *, source_id: str = "blue-book-nara"
):
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
    )


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- error paths


def test_assemble_raises_when_archive_missing(tmp_path: Path) -> None:
    with pytest.raises(ContextAssemblyError):
        assemble_context(
            tmp_path / "ghost",
            GraphNode(kind=NodeKind.EVIDENCE, id="a" * 64),
        )


def test_assemble_raises_when_archive_root_not_an_archive(
    archive_root: Path,
) -> None:
    with pytest.raises(ContextAssemblyError):
        assemble_context(
            archive_root, GraphNode(kind=NodeKind.EVIDENCE, id="a" * 64)
        )


def test_assemble_raises_when_anchor_not_in_graph(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(ContextAnchorNotFoundError):
        assemble_context(
            archive_root, GraphNode(kind=NodeKind.EVIDENCE, id="f" * 64)
        )


def test_assemble_raises_when_manifest_missing(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    # Borramos manifest pero dejamos audit + estructura para que
    # is_archive siga siendo True.
    (archive_root / layout.MANIFEST_FILENAME).unlink()
    with pytest.raises(ContextAssemblyError, match=r"manifest\.json"):
        assemble_context(
            archive_root,
            GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash),
        )


# ---------------------------------------------------------------- evidence anchor


def test_evidence_anchor_populates_evidence_source_provenance(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    assert bundle.anchor_node_kind == "evidence"
    assert bundle.anchor_node_id == evidence.hash
    assert bundle.evidence is not None
    assert bundle.evidence["hash"] == evidence.hash
    assert bundle.source is not None
    assert bundle.source["id"] == "blue-book-nara"
    assert bundle.provenance is not None
    assert bundle.derived_assessments == ()


def test_evidence_anchor_includes_assessments_when_present(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    assert len(bundle.derived_assessments) == 1
    assert bundle.derived_assessments[0]["evidence_id"] == evidence.hash


def test_evidence_anchor_graph_neighborhood_has_upstream_source(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    types_upstream = {n.node_type for n in bundle.graph_neighborhood.upstream}
    assert "source" in types_upstream


def test_evidence_anchor_graph_neighborhood_has_downstream_assessments(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    types_downstream = {
        n.node_type for n in bundle.graph_neighborhood.downstream
    }
    assert "assessment" in types_downstream


def test_evidence_anchor_impact_report_is_present(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    # El reporte agrega lo que devuelve analyze_removal_impact.
    assert bundle.impact_report["total_affected_nodes"] == 1
    assert bundle.impact_report["analysis_method_name"] == (
        "dependency_reachability_v1"
    )


# ---------------------------------------------------------------- assessment anchor


def test_assessment_anchor_resolves_evidence_via_graph(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root,
        GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id),
    )
    assert bundle.anchor_node_kind == "assessment"
    assert bundle.evidence is not None
    assert bundle.evidence["hash"] == evidence.hash
    assert bundle.source is not None
    # derived_assessments incluye sólo el anchor (un único assessment).
    assert len(bundle.derived_assessments) == 1
    assert (
        bundle.derived_assessments[0]["assessment_id"]
        == assessment.assessment_id
    )


def test_assessment_anchor_downstream_is_empty(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    assessment = _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root,
        GraphNode(kind=NodeKind.ASSESSMENT, id=assessment.assessment_id),
    )
    assert bundle.graph_neighborhood.downstream == ()
    # Pero upstream incluye evidencia y source.
    types_upstream = {n.node_type for n in bundle.graph_neighborhood.upstream}
    assert {"evidence", "source"}.issubset(types_upstream)


# ---------------------------------------------------------------- source anchor (API only)


def test_source_anchor_populates_source_only(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob, source_id="custom-src")
    _assess(archive_root, evidence.hash)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.SOURCE, id="custom-src")
    )
    assert bundle.anchor_node_kind == "source"
    assert bundle.evidence is None
    assert bundle.source is not None
    assert bundle.source["id"] == "custom-src"
    assert bundle.provenance is None
    # derived_assessments incluye los que citan esta source.
    assert len(bundle.derived_assessments) == 1


# ---------------------------------------------------------------- determinism


def test_assemble_is_deterministic_bit_for_bit(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    anchor = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    b1 = assemble_context(archive_root, anchor)
    b2 = assemble_context(archive_root, anchor)
    assert b1 == b2
    assert b1.context_bundle_hash == b2.context_bundle_hash


def test_assemble_does_not_modify_archive(
    tmp_path: Path, archive_root: Path
) -> None:
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
    assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    after = snapshot()
    assert before == after


# ---------------------------------------------------------------- hashes encadenados


def test_source_manifest_hash_matches_stored_manifest(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    stored = json.loads(
        (archive_root / "manifest.json").read_text(encoding="utf-8")
    )
    stored_manifest = ArchiveManifest.model_validate(stored)
    assert bundle.source_manifest_hash == stored_manifest.manifest_hash()


def test_context_bundle_hash_self_verifies(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    assert verify_bundle_hash(bundle) is True
    # Recomputo manual coincide.
    assert (
        compute_context_bundle_hash(bundle) == bundle.context_bundle_hash
    )


def test_context_bundle_hash_differs_for_different_anchors(
    tmp_path: Path, archive_root: Path
) -> None:
    blob_a = _write_blob(tmp_path, "a.pdf", b"%PDF-1.4 a")
    blob_b = _write_blob(tmp_path, "b.pdf", b"%PDF-1.4 b")
    ev_a = _ingest(archive_root, blob_a)
    ev_b = _ingest(archive_root, blob_b)
    bundle_a = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=ev_a.hash)
    )
    bundle_b = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=ev_b.hash)
    )
    assert bundle_a.context_bundle_hash != bundle_b.context_bundle_hash


def test_context_bundle_hash_changes_when_state_changes(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    anchor = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    bundle_pre = assemble_context(archive_root, anchor)
    _assess(archive_root, evidence.hash)
    bundle_post = assemble_context(archive_root, anchor)
    # Cambia el grafo + assessments + manifest → cambia ambos hashes.
    assert bundle_pre.context_bundle_hash != bundle_post.context_bundle_hash
    assert bundle_pre.source_manifest_hash != bundle_post.source_manifest_hash


def test_verify_bundle_hash_returns_false_on_tampering() -> None:
    """Bundle construido a mano con hash incorrecto → verify devuelve False."""
    bad_bundle = ContextBundle(
        anchor_node_kind="evidence",
        anchor_node_id="abc",
        evidence=None,
        source=None,
        provenance=None,
        derived_assessments=(),
        graph_neighborhood=GraphNeighborhood(upstream=(), downstream=()),
        impact_report={},
        assembly_engine_version=ASSEMBLY_ENGINE_VERSION,
        assembly_method_name=ASSEMBLY_METHOD_NAME,
        schema_version="0.1.0",
        source_manifest_hash="0" * 64,
        context_bundle_hash="b" * 64,  # incorrecto
    )
    assert verify_bundle_hash(bad_bundle) is False


# ---------------------------------------------------------------- honesty


def test_bundle_carries_honesty_fields(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    bundle = assemble_context(
        archive_root, GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    )
    assert bundle.assembly_engine_version == ASSEMBLY_ENGINE_VERSION
    assert bundle.assembly_method_name == ASSEMBLY_METHOD_NAME
    assert bundle.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------- agregación pura (G3)


def test_assembler_imports_only_existing_engines() -> None:
    """ADR-0035 §G3: el módulo del assembler sólo importa de capas
    productoras canónicas (analysis/graph/impact) y de core/storage.

    Defensa estática: si alguien introduce un import nuevo a una capa
    externa o a una librería ML/red/LLM, este test falla.
    """
    src = Path(__file__).parents[3] / "src" / "aip" / "context" / "assembler.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for n in node.names:
                imported_modules.add(n.name.split(".")[0])

    allowed = {
        "__future__",
        "dataclasses",
        "json",
        "pathlib",
        "typing",  # cast() para JsonValue
        "aip",  # interno
    }
    foreign = imported_modules - allowed
    assert foreign == set(), (
        f"assembler.py imports forbidden modules: {foreign}. "
        f"ADR-0035 §G3 forbids new dependencies in the assembly layer."
    )


def test_assembler_uses_canonical_engine_functions(
    tmp_path: Path, archive_root: Path
) -> None:
    """G3 operativo: el reporte de impacto del bundle es bit-idéntico
    al que produce analyze_removal_impact directamente — el assembler
    no recalcula, agrega."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    evidence = _ingest(archive_root, blob)
    _assess(archive_root, evidence.hash)
    anchor = GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash)
    bundle = assemble_context(archive_root, anchor)
    direct_report = analyze_removal_impact(
        build_graph(archive_root), anchor
    )
    assert bundle.impact_report == dc.asdict(direct_report)
