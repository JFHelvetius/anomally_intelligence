"""Función núcleo del Context Assembly (ADR-0035 §función núcleo).

**Agregación pura** de los outputs canónicos de ADR-0032/0033/0034.
Cero análisis nuevos. Cero escrituras al archive. Cero reloj. Cero
aleatoriedad.

El assembler invoca exclusivamente:

- ``tables.read_row`` (lectura de tablas).
- ``build_graph`` (ADR-0033).
- ``analyze_removal_impact`` (ADR-0034).
- ``ArchiveManifest.model_validate`` + ``.manifest_hash`` (ADR-0016).

Cualquier ampliación que requiera lógica analítica nueva es bug
arquitectónico — debe negociarse fuera de esta capa, en su propio ADR.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import cast

from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import (
    AuthenticationAssessment as DerivedAuthenticationAssessment,
)
from aip.context.models import (
    ASSEMBLY_ENGINE_VERSION,
    ASSEMBLY_METHOD_NAME,
    ContextBundle,
    ContextNode,
    GraphNeighborhood,
)
from aip.core.evidence import Evidence
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.core.provenance import Provenance
from aip.core.source import Source
from aip.errors import AIPError
from aip.graph import build_graph
from aip.graph.models import EvidenceGraph, GraphNode, NodeKind
from aip.graph.query import (
    get_assessments_for_evidence,
    get_evidence_for_assessment,
)
from aip.impact import analyze_removal_impact
from aip.storage import layout, tables
from aip.storage.manifest import ArchiveManifest


class ContextAssemblyError(AIPError):
    """Error genérico al ensamblar el bundle.

    Causas típicas: ``manifest.json`` ausente cuando el bundle lo
    requiere para `source_manifest_hash`. Mapea a exit code 1.
    """

    cli_exit_code = 1


class ContextAnchorNotFoundError(AIPError):
    """El anchor solicitado no está presente en el grafo del archive.

    Consistente con ``EvidenceNotFoundError`` y
    ``ImpactRootNotInGraphError`` — exit code 1.
    """

    cli_exit_code = 1


# --------------------------------------------------------------------- main


def assemble_context(
    archive_root: Path,
    anchor: GraphNode,
) -> ContextBundle:
    """Construye un :class:`ContextBundle` determinista para ``anchor``.

    Función pura del estado del archive. Cero clock, cero aleatoriedad.
    Mismo archive + mismo anchor ⇒ mismo bundle bit a bit (incluido
    ``context_bundle_hash``).

    Args:
        archive_root: Raíz del archive AIP. Debe ser archive válido y
            tener ``manifest.json`` presente.
        anchor: Nodo desde el que se ensambla. Debe pertenecer al grafo.

    Raises:
        ContextAssemblyError: ``manifest.json`` ausente.
        ContextAnchorNotFoundError: ``anchor`` no aparece en el grafo.
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise ContextAssemblyError(
            f"archive not found or invalid at {archive_root}."
        )

    graph = build_graph(archive_root)
    if anchor not in graph.node_set():
        raise ContextAnchorNotFoundError(
            f"anchor {anchor.kind.value}:{anchor.id!r} not in graph."
        )

    # source_manifest_hash desde el manifest.json en disco.
    manifest_path = archive_root / layout.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ContextAssemblyError(
            "manifest.json required to derive source_manifest_hash "
            "(ADR-0035 §hashes)."
        )
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored_manifest = ArchiveManifest.model_validate(stored)
    source_manifest_hash = stored_manifest.manifest_hash()

    # Resolver evidencia relacionada al anchor.
    related_evidence_id = _resolve_related_evidence_id(graph, anchor)

    evidence_data = _read_evidence(archive_root, related_evidence_id)
    source_data = _read_source_for_anchor(
        archive_root, anchor, evidence_data
    )
    provenance_data = _read_provenance(archive_root, related_evidence_id)
    derived_assessments_data = _read_assessments_for_anchor(
        archive_root, anchor, graph
    )

    # Proyección del grafo (BFS con distancia).
    upstream = _bfs_with_distance(graph, anchor, direction="outgoing")
    downstream = _bfs_with_distance(graph, anchor, direction="incoming")
    neighborhood = GraphNeighborhood(upstream=upstream, downstream=downstream)

    # Reporte de impacto vía ADR-0034 (agregación literal).
    impact_report_dataclass = analyze_removal_impact(graph, anchor)
    impact_report = dataclasses.asdict(impact_report_dataclass)

    # Bundle parcial sin context_bundle_hash (placeholder vacío).
    bundle_without_hash = ContextBundle(
        anchor_node_kind=anchor.kind.value,
        anchor_node_id=anchor.id,
        evidence=evidence_data,
        source=source_data,
        provenance=provenance_data,
        derived_assessments=derived_assessments_data,
        graph_neighborhood=neighborhood,
        impact_report=impact_report,
        assembly_engine_version=ASSEMBLY_ENGINE_VERSION,
        assembly_method_name=ASSEMBLY_METHOD_NAME,
        schema_version=SCHEMA_VERSION,
        source_manifest_hash=source_manifest_hash,
        context_bundle_hash="",
    )

    context_bundle_hash = compute_context_bundle_hash(bundle_without_hash)
    return dataclasses.replace(
        bundle_without_hash, context_bundle_hash=context_bundle_hash
    )


# --------------------------------------------------------------------- hashing


def compute_context_bundle_hash(bundle: ContextBundle) -> str:
    """SHA-256 hex de la canonicalización JCS del bundle **excluyendo**
    el campo ``context_bundle_hash``.

    Mismo patrón que :func:`aip.audit.log.compute_entry_hash` de ADR-0019.
    Cualquier consumidor puede recomputar y comparar contra el hash
    declarado para validar integridad del bundle sin acceso al archive.
    """
    data = dataclasses.asdict(bundle)
    data.pop("context_bundle_hash", None)
    # ``_normalize_for_jcs`` garantiza que la estructura resultante es
    # ``JsonValue`` (dict/list/scalar). El cast es seguro por construcción.
    normalized = cast(JsonValue, _normalize_for_jcs(data))
    return sha256_hex(jcs_canonicalize(normalized))


def _normalize_for_jcs(obj: object) -> object:
    """Convierte tuplas a listas recursivamente para que JCS las acepte.

    ``dataclasses.asdict`` preserva las tuplas declaradas en los campos
    (``tuple[ContextNode, ...]`` queda como tupla), pero
    :func:`aip.core.hashing.jcs_canonicalize` sólo acepta ``list`` y
    ``dict`` por construcción (ADR-0024 §formato canónico). Esta función
    es defensiva — no recanonicaliza, sólo cambia contenedor.
    """
    if isinstance(obj, tuple):
        return [_normalize_for_jcs(x) for x in obj]
    if isinstance(obj, list):
        return [_normalize_for_jcs(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_for_jcs(v) for k, v in obj.items()}
    return obj


def verify_bundle_hash(bundle: ContextBundle) -> bool:
    """Verifica que ``context_bundle_hash`` coincide con su recomputo.

    Devuelve ``True`` si el bundle es íntegro estructuralmente. Esta
    función no consulta al archive — verifica la auto-consistencia del
    bundle. Para verificar el anclaje al archive use
    ``bundle.source_manifest_hash`` contra el manifest actual.
    """
    return compute_context_bundle_hash(bundle) == bundle.context_bundle_hash


# --------------------------------------------------------------------- helpers


def _resolve_related_evidence_id(
    graph: EvidenceGraph, anchor: GraphNode
) -> str | None:
    """Devuelve el evidence_id asociado al anchor o ``None``.

    Para anchor evidence: el propio id.
    Para anchor assessment: vía arista ``assessed_from``.
    Para anchor source: no hay evidencia única — ``None``.
    """
    if anchor.kind is NodeKind.EVIDENCE:
        return anchor.id
    if anchor.kind is NodeKind.ASSESSMENT:
        ev_node = get_evidence_for_assessment(graph, anchor.id)
        return ev_node.id if ev_node is not None else None
    return None


def _read_evidence(
    archive_root: Path, evidence_id: str | None
) -> dict[str, object] | None:
    if evidence_id is None:
        return None
    row = tables.read_row(archive_root, "evidence", evidence_id)
    if row is None:
        return None
    # Validamos por el modelo y reserializamos para forma canónica.
    ev = Evidence.model_validate(row)
    return ev.model_dump(mode="json")


def _read_source_for_anchor(
    archive_root: Path,
    anchor: GraphNode,
    evidence_data: dict[str, object] | None,
) -> dict[str, object] | None:
    # Source anchor: directamente.
    if anchor.kind is NodeKind.SOURCE:
        row = tables.read_row(archive_root, "sources", anchor.id)
        if row is None:
            return None
        return Source.model_validate(row).model_dump(mode="json")
    # Otro anchor con Evidence: tomamos su source_id.
    if evidence_data is None:
        return None
    source_id = evidence_data.get("source_id")
    if not isinstance(source_id, str):
        return None
    row = tables.read_row(archive_root, "sources", source_id)
    if row is None:
        return None
    return Source.model_validate(row).model_dump(mode="json")


def _read_provenance(
    archive_root: Path, evidence_id: str | None
) -> dict[str, object] | None:
    if evidence_id is None:
        return None
    row = tables.read_row(archive_root, "provenance", evidence_id)
    if row is None:
        return None
    return Provenance.model_validate(row).model_dump(mode="json")


def _read_assessments_for_anchor(
    archive_root: Path,
    anchor: GraphNode,
    graph: EvidenceGraph,
) -> tuple[dict[str, object], ...]:
    """Lee assessments derivados que tocan al anchor.

    Para evidence anchor: assessments construidos sobre la evidencia.
    Para assessment anchor: el propio assessment (uno).
    Para source anchor: assessments que citan la source en
    ``supporting_source_ids`` (rama ``derived_from`` del grafo).

    Lectura literal de la tabla ``authentication_assessments`` — sin
    ejecutar nuevos análisis.
    """
    if anchor.kind is NodeKind.EVIDENCE:
        ids = sorted(
            n.id for n in get_assessments_for_evidence(graph, anchor.id)
        )
        return _collect_assessment_rows(archive_root, ids)
    if anchor.kind is NodeKind.ASSESSMENT:
        return _collect_assessment_rows(archive_root, [anchor.id])
    # source anchor
    matches: list[str] = []
    for raw in tables.iter_rows(archive_root, "authentication_assessments"):
        a = DerivedAuthenticationAssessment.model_validate(raw)
        if anchor.id in a.supporting_source_ids:
            matches.append(a.assessment_id)
    return _collect_assessment_rows(archive_root, sorted(matches))


def _collect_assessment_rows(
    archive_root: Path, ids: list[str]
) -> tuple[dict[str, object], ...]:
    out: list[dict[str, object]] = []
    for assessment_id in ids:
        row = tables.read_row(
            archive_root, "authentication_assessments", assessment_id
        )
        if row is None:
            continue
        a = DerivedAuthenticationAssessment.model_validate(row)
        out.append(a.model_dump(mode="json"))
    return tuple(out)


def _bfs_with_distance(
    graph: EvidenceGraph,
    start: GraphNode,
    *,
    direction: str,
) -> tuple[ContextNode, ...]:
    """BFS sobre :attr:`EvidenceGraph.edges` en la dirección indicada,
    devolviendo :class:`ContextNode` canónicamente ordenados.

    ``direction="outgoing"`` sigue ``edge.src == current`` (expandiendo
    hacia ``edge.dst``); ``"incoming"`` sigue ``edge.dst == current``
    (expandiendo hacia ``edge.src``).

    El ``start`` se excluye del resultado. Cycle-safe: termina
    siempre en ``O(|V| + |E|)``.
    """
    distances: dict[GraphNode, int] = {}
    frontier: list[GraphNode] = [start]
    current_distance = 0
    while frontier:
        next_frontier: list[GraphNode] = []
        for current in frontier:
            for edge in graph.edges:
                if direction == "outgoing" and edge.src == current:
                    candidate = edge.dst
                elif direction == "incoming" and edge.dst == current:
                    candidate = edge.src
                else:
                    continue
                if candidate == start or candidate in distances:
                    continue
                distances[candidate] = current_distance + 1
                next_frontier.append(candidate)
        frontier = next_frontier
        current_distance += 1

    nodes = [
        ContextNode(
            distance_from_anchor=d,
            node_type=n.kind.value,
            node_id=n.id,
        )
        for n, d in distances.items()
    ]
    nodes.sort()
    return tuple(nodes)
