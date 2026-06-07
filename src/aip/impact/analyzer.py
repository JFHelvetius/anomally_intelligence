"""Función núcleo del motor de impacto (ADR-0034 §función núcleo).

Implementa exactamente una operación: cierre transitivo de
reverse-dependencies con tracking de distancia. Función pura sobre el
grafo derivado de ADR-0033.

Sin reloj, sin aleatoriedad, sin estado global mutable, sin filesystem,
sin red.
"""

from __future__ import annotations

from aip._version import SCHEMA_VERSION
from aip.errors import AIPError
from aip.graph.models import EvidenceGraph, GraphNode, NodeKind
from aip.impact.models import (
    IMPACT_ENGINE_VERSION,
    ImpactNode,
    ImpactReport,
)


class ImpactRootNotInGraphError(AIPError):
    """El nodo raíz solicitado no está presente en el grafo.

    Mapea a exit code 1 (consistente con :class:`EvidenceNotFoundError`).
    """

    cli_exit_code = 1


def analyze_removal_impact(
    graph: EvidenceGraph,
    root_node: GraphNode,
) -> ImpactReport:
    """Calcula el reverse-dependency closure de ``root_node``.

    Args:
        graph: :class:`EvidenceGraph` derivado del archive
            (ADR-0033). Sus aristas están canónicamente ordenadas; la
            iteración determinista del BFS depende de esta propiedad.
        root_node: Nodo desde el que se analiza el impacto. Debe estar
            en ``graph.nodes``.

    Raises:
        ImpactRootNotInGraphError: si ``root_node`` no está en el grafo.

    Returns:
        :class:`ImpactReport` con cinco métricas observables. Mismo
        grafo + mismo root ⇒ mismo reporte bit a bit (ADR-0034 §G1).
    """
    if root_node not in graph.node_set():
        raise ImpactRootNotInGraphError(
            f"root node {root_node.kind.value}:{root_node.id!r} not in graph."
        )

    impact_nodes = _bfs_reverse_with_distance(graph, root_node)

    affected_assessments = sorted(
        n.node_id for n in impact_nodes if n.node_type == NodeKind.ASSESSMENT.value
    )
    affected_evidence = sorted(
        n.node_id for n in impact_nodes if n.node_type == NodeKind.EVIDENCE.value
    )
    dependency_depth_max = (
        max((n.distance_from_root for n in impact_nodes), default=0)
    )
    total_affected_nodes = len(impact_nodes)

    return ImpactReport(
        root_node_id=root_node.id,
        affected_assessments=affected_assessments,
        affected_evidence=affected_evidence,
        dependency_depth_max=dependency_depth_max,
        total_affected_nodes=total_affected_nodes,
        analysis_engine_version=IMPACT_ENGINE_VERSION,
        schema_version=SCHEMA_VERSION,
    )


def report_to_impact_nodes(
    graph: EvidenceGraph,
    root_node: GraphNode,
) -> tuple[ImpactNode, ...]:
    """Vista paralela del reporte como tupla de :class:`ImpactNode`.

    Util para consumidores que necesitan ``distance_from_root`` y
    ``node_type`` por nodo (no sólo el agregado del reporte). Ordenado
    canónicamente por la clave natural de :class:`ImpactNode`.

    Misma garantía de determinismo que :func:`analyze_removal_impact`.
    """
    if root_node not in graph.node_set():
        raise ImpactRootNotInGraphError(
            f"root node {root_node.kind.value}:{root_node.id!r} not in graph."
        )
    return _bfs_reverse_with_distance(graph, root_node)


# --------------------------------------------------------------------- internals


def _bfs_reverse_with_distance(
    graph: EvidenceGraph,
    root: GraphNode,
) -> tuple[ImpactNode, ...]:
    """BFS sobre aristas incoming desde ``root``, devolviendo
    :class:`ImpactNode` canónicamente ordenados.

    El nodo raíz se **excluye** del resultado (un nodo no es dependencia
    inversa de sí mismo; ADR-0034 §función núcleo).

    Cycle safety: si el grafo contuviera un ciclo que pasara por ``root``
    (no debería por construcción ADR-0033, pero defendemos), el
    descubrimiento se detiene al volver a ``root`` o al re-encontrar un
    nodo ya en ``distances``. Por tanto el BFS termina siempre en
    ``O(|V| + |E|)``.
    """
    distances: dict[GraphNode, int] = {}
    frontier: list[GraphNode] = [root]
    current_distance = 0
    while frontier:
        next_frontier: list[GraphNode] = []
        for current in frontier:
            for edge in graph.edges:
                if edge.dst != current:
                    continue
                candidate = edge.src
                if candidate == root:
                    continue
                if candidate in distances:
                    continue
                distances[candidate] = current_distance + 1
                next_frontier.append(candidate)
        frontier = next_frontier
        current_distance += 1

    impact_nodes = [
        ImpactNode(
            distance_from_root=dist,
            node_type=node.kind.value,
            node_id=node.id,
        )
        for node, dist in distances.items()
    ]
    impact_nodes.sort()
    return tuple(impact_nodes)
