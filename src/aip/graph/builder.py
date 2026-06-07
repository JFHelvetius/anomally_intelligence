"""Constructor del :class:`EvidenceGraph` (ADR-0033 §determinismo).

Función pura sobre ``archive_root``. Lee filas de tres tablas
(``evidence``, ``sources``, ``authentication_assessments``) y emite
nodos y aristas canónicamente ordenados.

Reglas (ADR-0033):

- Un nodo aparece si y sólo si existe la fila correspondiente.
- Una arista aparece si la referencia existe en algún campo, aunque su
  destino no esté presente en la tabla destino; ``validate_graph_integrity``
  reporta las roturas en ese caso.
- Sin reloj, sin aleatoriedad, sin estado global mutable.
"""

from __future__ import annotations

from pathlib import Path

from aip.analysis.authentication import (
    AuthenticationAssessment as DerivedAuthenticationAssessment,
)
from aip.core.evidence import Evidence
from aip.core.source import Source
from aip.errors import ArchiveNotFoundError
from aip.graph.models import (
    EdgeKind,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    NodeKind,
    edge_sort_key,
    node_sort_key,
)
from aip.storage import layout, tables

ASSESSMENTS_TABLE = "authentication_assessments"


def build_graph(archive_root: Path) -> EvidenceGraph:
    """Construye un :class:`EvidenceGraph` deterministra a partir del archive.

    Args:
        archive_root: Raíz del archive AIP. Debe existir y ser un archive
            válido (heurística :func:`aip.storage.layout.is_archive`).

    Raises:
        ArchiveNotFoundError: si ``archive_root`` no existe o no es un
            archive AIP válido.

    Returns:
        :class:`EvidenceGraph` con ``nodes`` y ``edges`` ordenados
        canónicamente (ADR-0033 §determinismo). Reproducible bit a bit:
        invocaciones repetidas sobre el mismo archive producen el mismo
        grafo.
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise ArchiveNotFoundError(f"archive not found at {archive_root}.")

    nodes: set[GraphNode] = set()
    edges: set[GraphEdge] = set()

    # 1. Nodos de Evidence + aristas sourced_from.
    for raw in tables.iter_rows(archive_root, "evidence"):
        ev = Evidence.model_validate(raw)
        ev_node = GraphNode(kind=NodeKind.EVIDENCE, id=ev.hash)
        nodes.add(ev_node)
        # La arista se emite siempre; el dst es phantom si la Source no
        # tiene fila (integridad lo reporta).
        src_node = GraphNode(kind=NodeKind.SOURCE, id=ev.source_id)
        edges.add(
            GraphEdge(kind=EdgeKind.SOURCED_FROM, src=ev_node, dst=src_node)
        )

    # 2. Nodos de Source. Puede incluir Sources sin Evidence (orphans
    # legítimos) — el grafo los muestra como nodo aislado.
    for raw in tables.iter_rows(archive_root, "sources"):
        src = Source.model_validate(raw)
        nodes.add(GraphNode(kind=NodeKind.SOURCE, id=src.id))

    # 3. Nodos de Assessment + aristas assessed_from + derived_from.
    for raw in tables.iter_rows(archive_root, ASSESSMENTS_TABLE):
        a = DerivedAuthenticationAssessment.model_validate(raw)
        a_node = GraphNode(kind=NodeKind.ASSESSMENT, id=a.assessment_id)
        nodes.add(a_node)
        ev_node = GraphNode(kind=NodeKind.EVIDENCE, id=a.evidence_id)
        edges.add(
            GraphEdge(kind=EdgeKind.ASSESSED_FROM, src=a_node, dst=ev_node)
        )
        for src_id in a.supporting_source_ids:
            src_node = GraphNode(kind=NodeKind.SOURCE, id=src_id)
            edges.add(
                GraphEdge(kind=EdgeKind.DERIVED_FROM, src=a_node, dst=src_node)
            )

    sorted_nodes = tuple(sorted(nodes, key=node_sort_key))
    sorted_edges = tuple(sorted(edges, key=edge_sort_key))
    return EvidenceGraph(nodes=sorted_nodes, edges=sorted_edges)
