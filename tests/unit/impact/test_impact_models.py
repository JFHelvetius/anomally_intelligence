"""Tests unitarios del modelo de impacto (ADR-0034 §modelo).

Cubre construcción, frozenness, validadores defensivos, honesty fields,
y verifica explícitamente la **ausencia** de tokens prohibidos en el
paquete ``aip.impact`` y su CLI.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip._version import SCHEMA_VERSION
from aip.impact import (
    ANALYSIS_METHOD_NAME,
    IMPACT_ENGINE_VERSION,
    ImpactNode,
    ImpactReport,
)

# ---------------------------------------------------------------- constantes


def test_impact_engine_version_is_semver_string() -> None:
    assert isinstance(IMPACT_ENGINE_VERSION, str)
    assert IMPACT_ENGINE_VERSION != ""
    # SemVer mínimo: tres componentes numéricos separados por puntos.
    parts = IMPACT_ENGINE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_analysis_method_name_is_pinned() -> None:
    # Cierre del nombre del método V1 (ADR-0034 §honesty).
    assert ANALYSIS_METHOD_NAME == "dependency_reachability_v1"


# ---------------------------------------------------------------- ImpactNode


def test_impact_node_constructs_with_three_fields() -> None:
    n = ImpactNode(distance_from_root=1, node_type="assessment", node_id="x")
    assert n.distance_from_root == 1
    assert n.node_type == "assessment"
    assert n.node_id == "x"


def test_impact_node_is_frozen() -> None:
    n = ImpactNode(distance_from_root=1, node_type="assessment", node_id="x")
    with pytest.raises(FrozenInstanceError):
        n.distance_from_root = 2  # type: ignore[misc]


def test_impact_node_orders_by_distance_then_type_then_id() -> None:
    closer = ImpactNode(distance_from_root=1, node_type="zzz", node_id="zzz")
    further = ImpactNode(distance_from_root=2, node_type="aaa", node_id="aaa")
    # distance gana sobre cualquier otro campo: closer va primero.
    assert closer < further


# ---------------------------------------------------------------- ImpactReport (happy)


def _valid_report(**overrides: object) -> ImpactReport:
    base: dict[str, object] = {
        "root_node_id": "abc123",
        "affected_assessments": ["assess-1", "assess-2"],
        "affected_evidence": [],
        "dependency_depth_max": 1,
        "total_affected_nodes": 2,
        "analysis_engine_version": IMPACT_ENGINE_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    base.update(overrides)
    return ImpactReport(**base)  # type: ignore[arg-type]


def test_impact_report_constructs_from_valid_inputs() -> None:
    r = _valid_report()
    assert r.root_node_id == "abc123"
    assert r.affected_assessments == ["assess-1", "assess-2"]
    assert r.affected_evidence == []
    assert r.dependency_depth_max == 1
    assert r.total_affected_nodes == 2
    assert r.analysis_engine_version == IMPACT_ENGINE_VERSION
    assert r.schema_version == SCHEMA_VERSION
    # Default honesty field.
    assert r.analysis_method_name == ANALYSIS_METHOD_NAME


def test_impact_report_is_frozen() -> None:
    r = _valid_report()
    with pytest.raises(FrozenInstanceError):
        r.dependency_depth_max = 99  # type: ignore[misc]


def test_impact_report_uses_analysis_method_name_default() -> None:
    r = _valid_report()
    assert r.analysis_method_name == "dependency_reachability_v1"


def test_impact_report_empty_is_valid() -> None:
    r = ImpactReport(
        root_node_id="root",
        affected_assessments=[],
        affected_evidence=[],
        dependency_depth_max=0,
        total_affected_nodes=0,
        analysis_engine_version=IMPACT_ENGINE_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    assert r.total_affected_nodes == 0


# ---------------------------------------------------------------- ImpactReport (validators)


def test_impact_report_rejects_unsorted_assessments() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _valid_report(affected_assessments=["z", "a"])


def test_impact_report_rejects_duplicate_assessments() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _valid_report(affected_assessments=["a", "a"])


def test_impact_report_rejects_unsorted_evidence() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _valid_report(affected_evidence=["z", "a"])


def test_impact_report_rejects_duplicate_evidence() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _valid_report(affected_evidence=["a", "a"])


def test_impact_report_rejects_negative_depth() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _valid_report(dependency_depth_max=-1)


def test_impact_report_rejects_negative_total() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _valid_report(total_affected_nodes=-1)


# ---------------------------------------------------------------- forbidden tokens

# Lista cerrada de tokens prohibidos por ADR-0034 §componentes excluidos.
# El test verifica que ningún módulo en src/aip/impact/ ni el CLI
# src/aip/cli/impact_commands.py contiene estas palabras. Tokens
# legítimos en español (e.g., "importante" como palabra común) están
# permitidos sólo en comentarios; chequeamos por word-boundary case
# insensitive contra texto plano del fichero.

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "risk_level",
    "danger",
    "dangerous",
    "high_risk",
    "high-risk",
    "likely",
    "likelihood",
    "probability",
    "prior",
    "posterior",
    "bayesian",
    "confidence_score",
    "confidence_percent",
    "confidence_percentage",
    "recommend_action",
    "recommendation",
    "suggested_action",
    "automated_decision",
    "causal_inference",
    "cause_of",
    "effect_size",
)


def _impact_source_files() -> list[Path]:
    """Devuelve todos los .py del paquete impact y de su CLI."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    impact_pkg = repo / "src" / "aip" / "impact"
    cli_module = repo / "src" / "aip" / "cli" / "impact_commands.py"
    files = list(impact_pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_impact_module() -> None:
    """ADR-0034 §componentes excluidos: ninguno de los tokens
    prohibidos aparece en el código del paquete de impacto.

    El test es deliberadamente burdo (substring case-insensitive sobre
    todo el fichero). Una pista en un docstring o variable basta para
    fallar — eso es intencional: la prohibición es estructural.
    """
    offenders: list[tuple[str, str]] = []
    for path in _impact_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], f"Forbidden tokens found (ADR-0034 §componentes excluidos): {offenders}"
