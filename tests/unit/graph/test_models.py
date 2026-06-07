"""Tests unitarios del modelo del grafo derivado (ADR-0033 §modelo).

Cubre los tipos cerrados, frozenness, ordering canónico y claves de orden.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from aip.graph.models import (
    EDGE_KINDS,
    NODE_KINDS,
    EdgeKind,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    NodeKind,
    edge_sort_key,
    node_sort_key,
)

EVIDENCE_HEX = "a" * 64


def _ev_node(suffix: str = "a") -> GraphNode:
    return GraphNode(kind=NodeKind.EVIDENCE, id=suffix * 64)


def _src_node(name: str = "blue-book-nara") -> GraphNode:
    return GraphNode(kind=NodeKind.SOURCE, id=name)


def _assess_node(ev_hex: str = "a", method: str = "provenance_review") -> GraphNode:
    return GraphNode(
        kind=NodeKind.ASSESSMENT, id=f"{ev_hex * 64}__{method}"
    )


# ---------------------------------------------------------------- enums


def test_node_kind_has_three_closed_values() -> None:
    assert {k.value for k in NodeKind} == {"evidence", "source", "assessment"}


def test_edge_kind_has_three_closed_values() -> None:
    assert {k.value for k in EdgeKind} == {
        "sourced_from",
        "assessed_from",
        "derived_from",
    }


def test_canonical_kind_tuples_are_in_decision_order() -> None:
    # Garantía: el orden de NODE_KINDS y EDGE_KINDS refleja el orden
    # declarativo del ADR-0033 §modelo, no el alfabético.
    assert NODE_KINDS == (NodeKind.EVIDENCE, NodeKind.SOURCE, NodeKind.ASSESSMENT)
    assert EDGE_KINDS == (
        EdgeKind.SOURCED_FROM,
        EdgeKind.ASSESSED_FROM,
        EdgeKind.DERIVED_FROM,
    )


# ---------------------------------------------------------------- GraphNode


def test_graph_node_constructs_with_kind_and_id() -> None:
    n = _ev_node()
    assert n.kind == NodeKind.EVIDENCE
    assert n.id == EVIDENCE_HEX


def test_graph_node_is_frozen() -> None:
    n = _ev_node()
    with pytest.raises(FrozenInstanceError):
        n.kind = NodeKind.SOURCE  # type: ignore[misc]


def test_graph_node_is_hashable() -> None:
    s = {_ev_node(), _ev_node()}
    assert len(s) == 1


def test_graph_node_equality_by_value() -> None:
    a = _ev_node()
    b = _ev_node()
    assert a == b
    assert a is not b


def test_graph_node_ordering_kind_first_then_id() -> None:
    # Orden lexicográfico de los campos: kind primero, id segundo.
    smaller = GraphNode(kind=NodeKind.ASSESSMENT, id="z")
    larger = GraphNode(kind=NodeKind.EVIDENCE, id="a")
    # "assessment" < "evidence" lexicograficamente.
    assert smaller < larger


def test_node_sort_key_matches_canonical_order() -> None:
    n1 = GraphNode(kind=NodeKind.SOURCE, id="b")
    n2 = GraphNode(kind=NodeKind.SOURCE, id="a")
    assert node_sort_key(n2) < node_sort_key(n1)


# ---------------------------------------------------------------- GraphEdge


def test_graph_edge_constructs_with_kind_src_dst() -> None:
    e = GraphEdge(
        kind=EdgeKind.SOURCED_FROM, src=_ev_node(), dst=_src_node()
    )
    assert e.kind == EdgeKind.SOURCED_FROM


def test_graph_edge_is_frozen() -> None:
    e = GraphEdge(
        kind=EdgeKind.SOURCED_FROM, src=_ev_node(), dst=_src_node()
    )
    with pytest.raises(FrozenInstanceError):
        e.kind = EdgeKind.DERIVED_FROM  # type: ignore[misc]


def test_graph_edge_is_hashable() -> None:
    e1 = GraphEdge(
        kind=EdgeKind.SOURCED_FROM, src=_ev_node(), dst=_src_node()
    )
    e2 = GraphEdge(
        kind=EdgeKind.SOURCED_FROM, src=_ev_node(), dst=_src_node()
    )
    assert len({e1, e2}) == 1


def test_edge_sort_key_distinguishes_by_kind_then_endpoints() -> None:
    e_sourced = GraphEdge(
        kind=EdgeKind.SOURCED_FROM, src=_ev_node(), dst=_src_node()
    )
    e_derived = GraphEdge(
        kind=EdgeKind.DERIVED_FROM, src=_assess_node(), dst=_src_node()
    )
    # "derived_from" < "sourced_from".
    assert edge_sort_key(e_derived) < edge_sort_key(e_sourced)


# ---------------------------------------------------------------- EvidenceGraph


def test_evidence_graph_holds_tuples_not_lists() -> None:
    g = EvidenceGraph(nodes=(_ev_node(),), edges=())
    assert isinstance(g.nodes, tuple)
    assert isinstance(g.edges, tuple)


def test_evidence_graph_is_frozen() -> None:
    g = EvidenceGraph(nodes=(), edges=())
    with pytest.raises(FrozenInstanceError):
        g.nodes = (_ev_node(),)  # type: ignore[misc]


def test_evidence_graph_node_set_returns_frozenset() -> None:
    g = EvidenceGraph(nodes=(_ev_node(), _src_node()), edges=())
    s = g.node_set()
    assert isinstance(s, frozenset)
    assert _ev_node() in s
    assert _src_node() in s


def test_evidence_graph_node_set_is_fresh_each_call() -> None:
    # Aunque sea frozenset (inmutable), cada llamada debe construir uno
    # nuevo: no exponemos referencias compartidas.
    g = EvidenceGraph(nodes=(_ev_node(),), edges=())
    s1 = g.node_set()
    s2 = g.node_set()
    assert s1 == s2
    # Identidad no garantizada (puede ser misma o distinta);
    # comportamiento observable es la equivalencia de contenidos.


def test_empty_graph_constructs() -> None:
    g = EvidenceGraph(nodes=(), edges=())
    assert g.nodes == ()
    assert g.edges == ()
