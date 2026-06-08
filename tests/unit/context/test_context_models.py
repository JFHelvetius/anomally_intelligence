"""Tests del modelo de Context Assembly (ADR-0035 §modelo)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip.context import (
    ASSEMBLY_ENGINE_VERSION,
    ASSEMBLY_METHOD_NAME,
    ContextBundle,
    ContextNode,
    GraphNeighborhood,
)

# ---------------------------------------------------------------- constantes


def test_assembly_engine_version_is_semver() -> None:
    assert isinstance(ASSEMBLY_ENGINE_VERSION, str)
    parts = ASSEMBLY_ENGINE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_assembly_method_name_is_pinned() -> None:
    assert ASSEMBLY_METHOD_NAME == "evidence_centric_v1"


# ---------------------------------------------------------------- ContextNode


def test_context_node_constructs_with_three_fields() -> None:
    n = ContextNode(distance_from_anchor=1, node_type="assessment", node_id="x")
    assert n.distance_from_anchor == 1
    assert n.node_type == "assessment"
    assert n.node_id == "x"


def test_context_node_is_frozen() -> None:
    n = ContextNode(distance_from_anchor=1, node_type="assessment", node_id="x")
    with pytest.raises(FrozenInstanceError):
        n.distance_from_anchor = 2  # type: ignore[misc]


def test_context_node_orders_by_distance_then_type_then_id() -> None:
    closer = ContextNode(distance_from_anchor=1, node_type="zzz", node_id="zzz")
    further = ContextNode(distance_from_anchor=2, node_type="aaa", node_id="aaa")
    assert closer < further


# ---------------------------------------------------------------- GraphNeighborhood


def test_graph_neighborhood_holds_tuples() -> None:
    n = GraphNeighborhood(upstream=(), downstream=())
    assert isinstance(n.upstream, tuple)
    assert isinstance(n.downstream, tuple)


def test_graph_neighborhood_is_frozen() -> None:
    n = GraphNeighborhood(upstream=(), downstream=())
    with pytest.raises(FrozenInstanceError):
        # Asignación a campo de frozen dataclass: mypy lo prohíbe
        # estáticamente (misc) y el runtime lanza FrozenInstanceError.
        n.upstream = (  # type: ignore[misc]
            ContextNode(distance_from_anchor=1, node_type="x", node_id="y"),
        )


# ---------------------------------------------------------------- ContextBundle


def _empty_bundle(**overrides) -> ContextBundle:
    base: dict[str, object] = {
        "anchor_node_kind": "evidence",
        "anchor_node_id": "abc",
        "evidence": None,
        "source": None,
        "provenance": None,
        "derived_assessments": (),
        "graph_neighborhood": GraphNeighborhood(upstream=(), downstream=()),
        "impact_report": {},
        "assembly_engine_version": ASSEMBLY_ENGINE_VERSION,
        "assembly_method_name": ASSEMBLY_METHOD_NAME,
        "schema_version": "0.1.0",
        "source_manifest_hash": "f" * 64,
        "context_bundle_hash": "0" * 64,
    }
    base.update(overrides)
    return ContextBundle(**base)  # type: ignore[arg-type]


def test_context_bundle_is_frozen() -> None:
    b = _empty_bundle()
    with pytest.raises(FrozenInstanceError):
        b.anchor_node_id = "z"  # type: ignore[misc]


def test_context_bundle_holds_immutable_assessments() -> None:
    b = _empty_bundle()
    assert isinstance(b.derived_assessments, tuple)


# ---------------------------------------------------------------- forbidden tokens

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "risk_level",
    "danger",
    "dangerous",
    "high_risk",
    "high-risk",
    "likelihood",
    "probability",
    "bayesian",
    "confidence_score",
    "confidence_percent",
    "recommend_action",
    "recommendation",
    "suggested_action",
    "automated_decision",
    "causal_inference",
    "ranking",
    "summary_text",
)


def _context_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "context"
    cli_module = repo / "src" / "aip" / "cli" / "context_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_context_module() -> None:
    """ADR-0035 §componentes excluidos + §G6: ninguno de los tokens
    prohibidos aparece en el código del paquete de contexto.

    La prohibición es estructural: el bundle agrega, no interpreta.
    """
    offenders: list[tuple[str, str]] = []
    for path in _context_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], f"Forbidden tokens found (ADR-0035 §componentes excluidos): {offenders}"
