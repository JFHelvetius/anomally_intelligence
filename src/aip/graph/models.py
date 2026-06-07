"""Modelo de datos del grafo derivado (ADR-0033 §modelo).

Tres tipos de nodo cerrados, tres tipos de arista cerrados, y un
contenedor inmutable :class:`EvidenceGraph`. Todo ``frozen=True`` para
preservar inmutabilidad estructural y permitir uso seguro en ``set`` y
``dict``.

Reglas de ordenamiento canónico (ADR-0033 §determinismo):

- Nodos: por ``(kind.value, id)``.
- Aristas: por ``(kind.value, src.kind.value, src.id, dst.kind.value, dst.id)``.

Estas claves son las **únicas** fuentes de orden en el grafo serializado;
ni el orden de inserción ni el del filesystem influyen.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class NodeKind(StrEnum):
    """Tipos de nodo del grafo derivado (ADR-0033 §modelo). Cerrado por ADR."""

    EVIDENCE = "evidence"
    """Nodo que respalda una fila de la tabla ``evidence``. ``id`` = SHA-256
    hex de la Evidence."""

    SOURCE = "source"
    """Nodo que respalda una fila de la tabla ``sources``. ``id`` =
    ``Source.id`` (cadena estable elegida por el curador)."""

    ASSESSMENT = "assessment"
    """Nodo que respalda una fila de la tabla
    ``authentication_assessments``. ``id`` = ``AuthenticationAssessment.
    assessment_id`` (= ``{evidence_id}__{method}``)."""


class EdgeKind(StrEnum):
    """Tipos de arista del grafo derivado (ADR-0033 §modelo). Cerrado por ADR.

    La dirección **es semántica**: una arista ``A → B`` significa "A
    depende de B" o "A se construyó sobre B". Seguir aristas hacia
    adelante recorre la cadena de dependencias; seguirlas hacia atrás
    recorre los dependientes.
    """

    SOURCED_FROM = "sourced_from"
    """``evidence → source``. La evidencia declara su fuente de origen
    vía ``Evidence.source_id``. Una sola arista por evidencia (modelo V1)."""

    ASSESSED_FROM = "assessed_from"
    """``assessment → evidence``. El assessment se construyó sobre esta
    evidencia. Una sola arista por assessment."""

    DERIVED_FROM = "derived_from"
    """``assessment → source``. El assessment cita esta fuente como
    respaldo en ``supporting_source_ids``. Cero o más por assessment."""


@dataclass(frozen=True, order=True)
class GraphNode:
    """Nodo inmutable del grafo. Identidad = ``(kind, id)``.

    El campo ``kind`` aparece primero para que el orden lexicográfico
    natural de la dataclass coincida con la convención canónica
    declarada en ADR-0033 §determinismo.
    """

    kind: NodeKind
    id: str


@dataclass(frozen=True, order=True)
class GraphEdge:
    """Arista tipada inmutable del grafo. Identidad = ``(kind, src, dst)``.

    Igual que :class:`GraphNode`, el orden canónico se obtiene del orden
    lexicográfico natural de los campos: ``kind`` → ``src`` → ``dst``,
    donde la comparación de :class:`GraphNode` ya respeta el orden
    canónico de nodos.
    """

    kind: EdgeKind
    src: GraphNode
    dst: GraphNode


@dataclass(frozen=True)
class EvidenceGraph:
    """Grafo de procedencia derivado del archive (ADR-0033 §modelo).

    Contenedor inmutable: ``nodes`` y ``edges`` son tuplas ordenadas
    canónicamente. El builder es el único productor; los consumidores
    (queries, CLI) tratan el grafo como read-only.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def node_set(self) -> frozenset[GraphNode]:
        """Devuelve la pertenencia de nodos como ``frozenset`` inmutable.

        Útil para lookups O(1) en queries sin perder la inmutabilidad
        estructural del grafo. La conversión es defensiva: cada llamada
        retorna un nuevo frozenset (los frozenset son baratos de
        construir y siempre seguros).
        """
        return frozenset(self.nodes)


# --------------------------------------------------------------------- canonical keys


def node_sort_key(node: GraphNode) -> tuple[str, str]:
    """Clave canónica para ordenar nodos (ADR-0033 §determinismo)."""
    return (node.kind.value, node.id)


def edge_sort_key(edge: GraphEdge) -> tuple[str, str, str, str, str]:
    """Clave canónica para ordenar aristas (ADR-0033 §determinismo)."""
    return (
        edge.kind.value,
        edge.src.kind.value,
        edge.src.id,
        edge.dst.kind.value,
        edge.dst.id,
    )


# --------------------------------------------------------------------- structural counts

NODE_KINDS: Final[tuple[NodeKind, ...]] = (
    NodeKind.EVIDENCE,
    NodeKind.SOURCE,
    NodeKind.ASSESSMENT,
)
"""Orden canónico para enumeraciones del grafo (e.g., conteos por tipo)."""

EDGE_KINDS: Final[tuple[EdgeKind, ...]] = (
    EdgeKind.SOURCED_FROM,
    EdgeKind.ASSESSED_FROM,
    EdgeKind.DERIVED_FROM,
)
"""Orden canónico para enumeraciones de aristas."""
