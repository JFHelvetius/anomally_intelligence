"""APIs de consulta sobre :class:`EvidenceGraph` (ADR-0033 §queries).

Todas las funciones son **deterministas** y devuelven resultados
**canónicamente ordenados** (mismo input → mismo output, mismo
ordenamiento). No mantienen estado, no acceden al filesystem, no usan
reloj.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aip.graph.models import (
    EdgeKind,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    NodeKind,
    edge_sort_key,
    node_sort_key,
)

# --------------------------------------------------------------------- integrity


class GraphIntegrityIssueKind(StrEnum):
    """Tipos de problema reportados por :func:`validate_graph_integrity`."""

    DANGLING_SRC = "dangling_src"
    """La arista tiene un nodo origen que no está en ``graph.nodes``."""

    DANGLING_DST = "dangling_dst"
    """La arista tiene un nodo destino que no está en ``graph.nodes``."""


@dataclass(frozen=True, order=True)
class GraphIntegrityIssue:
    """Problema de integridad estructural del grafo (ADR-0033 §queries)."""

    kind: GraphIntegrityIssueKind
    edge: GraphEdge


def validate_graph_integrity(
    graph: EvidenceGraph,
) -> tuple[GraphIntegrityIssue, ...]:
    """Reporta aristas con extremos que no son nodos del grafo.

    Orden canónico del resultado: por
    ``(issue.kind.value, edge_sort_key(issue.edge))``. Reportar **todos**
    los problemas (no abortar al primer hallazgo) permite a un operador
    decidir si reparar o aceptar el estado.
    """
    node_set = graph.node_set()
    issues: list[GraphIntegrityIssue] = []
    for edge in graph.edges:
        if edge.src not in node_set:
            issues.append(
                GraphIntegrityIssue(
                    kind=GraphIntegrityIssueKind.DANGLING_SRC, edge=edge
                )
            )
        if edge.dst not in node_set:
            issues.append(
                GraphIntegrityIssue(
                    kind=GraphIntegrityIssueKind.DANGLING_DST, edge=edge
                )
            )
    issues.sort(key=lambda i: (i.kind.value, edge_sort_key(i.edge)))
    return tuple(issues)


# --------------------------------------------------------------------- focused queries


def get_assessments_for_evidence(
    graph: EvidenceGraph, evidence_id: str
) -> tuple[GraphNode, ...]:
    """Devuelve assessments que se construyeron sobre ``evidence_id``.

    Sigue las aristas ``assessed_from`` en reverso. Resultado ordenado
    canónicamente por ``(kind.value, id)``.
    """
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence_id)
    found: set[GraphNode] = set()
    for edge in graph.edges:
        if edge.kind is EdgeKind.ASSESSED_FROM and edge.dst == target:
            found.add(edge.src)
    return tuple(sorted(found, key=node_sort_key))


def get_evidence_for_assessment(
    graph: EvidenceGraph, assessment_id: str
) -> GraphNode | None:
    """Devuelve la evidencia referenciada por ``assessment_id``.

    Como un :class:`AuthenticationAssessment` referencia exactamente una
    Evidence (modelo V1), el resultado es ``GraphNode`` único o
    ``None`` si el assessment no aparece en el grafo o no tiene arista
    saliente ``assessed_from`` (caso anómalo).
    """
    src = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment_id)
    for edge in graph.edges:
        if edge.kind is EdgeKind.ASSESSED_FROM and edge.src == src:
            return edge.dst
    return None


# --------------------------------------------------------------------- transitive


def get_dependency_chain(
    graph: EvidenceGraph, node: GraphNode
) -> tuple[GraphNode, ...]:
    """Cierre transitivo de **dependencias** del nodo (BFS outgoing).

    Para un assessment: incluye su Evidence y todas las Sources citadas.
    Para una Evidence: incluye su Source.
    Para una Source: vacía (las Sources no dependen de nada).

    Resultado ordenado canónicamente; **excluye** el nodo de partida
    (un nodo no es dependencia de sí mismo).
    """
    return _bfs_transitive(graph, node, direction="outgoing")


def get_reverse_dependencies(
    graph: EvidenceGraph, node: GraphNode
) -> tuple[GraphNode, ...]:
    """Cierre transitivo de **dependientes** del nodo (BFS incoming).

    Para una Source: incluye todas las Evidence que la citan + todos los
    Assessment que la citan + todos los Assessment que dependen
    transitivamente vía esas Evidence.
    Para una Evidence: incluye todos los Assessment construidos sobre ella.
    Para un Assessment: vacía (nada depende de un assessment en V1).

    Resultado ordenado canónicamente; **excluye** el nodo de partida.
    """
    return _bfs_transitive(graph, node, direction="incoming")


# --------------------------------------------------------------------- internals


def _bfs_transitive(
    graph: EvidenceGraph,
    start: GraphNode,
    *,
    direction: str,
) -> tuple[GraphNode, ...]:
    """BFS sobre :attr:`EvidenceGraph.edges` en la dirección indicada.

    ``direction="outgoing"`` sigue aristas ``src == n``; ``"incoming"``
    sigue aristas ``dst == n``. La iteración se hace sobre la tupla de
    aristas, que ya está canónicamente ordenada — por tanto el conjunto
    visitado es estable bit a bit independiente de la iteración interna
    de Python sobre ``set``.
    """
    visited: set[GraphNode] = set()
    frontier: list[GraphNode] = [start]
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
                if candidate == start:
                    # Defensa contra ciclos pasando por el origen;
                    # los grafos AIP son DAG por construcción, pero
                    # la guarda hace explícita la propiedad.
                    continue
                if candidate not in visited:
                    visited.add(candidate)
                    next_frontier.append(candidate)
        frontier = next_frontier
    return tuple(sorted(visited, key=node_sort_key))
