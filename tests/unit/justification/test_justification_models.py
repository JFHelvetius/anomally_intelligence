"""Tests del modelo de Justification (ADR-0040 §modelo)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip.justification import (
    ALLOWED_ANCHOR_TYPES,
    ALLOWED_ENTRY_ROLES,
    JUSTIFICATION_ENGINE_VERSION,
    JUSTIFICATION_METHOD_NAME,
    JUSTIFICATION_SCHEMA_VERSION,
    ChainEntry,
    InvestigationJustification,
    JustificationDiff,
    compute_chain_entry_hash,
)

# ---------------------------------------------------------------- constantes


def test_schema_version_pinned() -> None:
    assert JUSTIFICATION_SCHEMA_VERSION == "1"


def test_engine_version_is_semver() -> None:
    parts = JUSTIFICATION_ENGINE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_method_name_pinned() -> None:
    assert JUSTIFICATION_METHOD_NAME == "deductive_chain_v1"


def test_allowed_entry_roles_is_closed() -> None:
    assert frozenset(
        {
            "evidence",
            "source",
            "assessment",
            "provenance_step",
            "graph_node",
        }
    ) == ALLOWED_ENTRY_ROLES


def test_allowed_anchor_types_is_closed() -> None:
    assert frozenset({"assessment"}) == ALLOWED_ANCHOR_TYPES


# ---------------------------------------------------------------- ChainEntry


def _valid_entry(**overrides) -> ChainEntry:
    base: dict[str, object] = {
        "entry_role": "evidence",
        "entry_identifier": "E001",
        "entry_hash": compute_chain_entry_hash("evidence", "E001"),
    }
    base.update(overrides)
    return ChainEntry(**base)  # type: ignore[arg-type]


def test_chain_entry_constructs() -> None:
    e = _valid_entry()
    assert e.entry_role == "evidence"


def test_chain_entry_frozen() -> None:
    e = _valid_entry()
    with pytest.raises(FrozenInstanceError):
        e.entry_role = "x"  # type: ignore[misc]


def test_chain_entry_rejects_invalid_role() -> None:
    with pytest.raises(ValueError, match="invalid entry_role"):
        ChainEntry(
            entry_role="hypothesis",
            entry_identifier="H1",
            entry_hash="0" * 64,
        )


def test_chain_entry_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ChainEntry(
            entry_role="evidence",
            entry_identifier="",
            entry_hash="0" * 64,
        )


def test_chain_entry_rejects_bad_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        ChainEntry(
            entry_role="evidence",
            entry_identifier="E1",
            entry_hash="bad",
        )


def test_chain_entry_orders_by_role_then_identifier() -> None:
    a = _valid_entry(
        entry_role="assessment",
        entry_identifier="A1",
        entry_hash=compute_chain_entry_hash("assessment", "A1"),
    )
    b = _valid_entry(
        entry_role="evidence",
        entry_identifier="E1",
        entry_hash=compute_chain_entry_hash("evidence", "E1"),
    )
    # "assessment" < "evidence"
    assert a < b


# ---------------------------------------------------------------- compute_chain_entry_hash


def test_compute_entry_hash_deterministic() -> None:
    a = compute_chain_entry_hash("evidence", "E1")
    b = compute_chain_entry_hash("evidence", "E1")
    assert a == b


def test_compute_entry_hash_distinguishes() -> None:
    a = compute_chain_entry_hash("evidence", "E1")
    b = compute_chain_entry_hash("evidence", "E2")
    c = compute_chain_entry_hash("assessment", "E1")
    assert len({a, b, c}) == 3


def test_compute_entry_hash_rejects_empty() -> None:
    with pytest.raises(ValueError):
        compute_chain_entry_hash("", "x")
    with pytest.raises(ValueError):
        compute_chain_entry_hash("evidence", "")


# ---------------------------------------------------------------- InvestigationJustification


def _valid_justification(**overrides) -> InvestigationJustification:
    e = _valid_entry()
    a = _valid_entry(
        entry_role="assessment",
        entry_identifier="A1",
        entry_hash=compute_chain_entry_hash("assessment", "A1"),
    )
    base: dict[str, object] = {
        "justification_id": "j-01",
        "conclusion_anchor_type": "assessment",
        "conclusion_anchor_id": "A1",
        "conclusion_anchor_hash": compute_chain_entry_hash(
            "assessment", "A1"
        ),
        "minimal_evidence": (e,),
        "supporting_assessments": (a,),
        "graph_nodes_used": (),
        "intermediate_artifacts": (),
        "provenance_chain": (),
        "workspace_hash": None,
        "source_manifest_hash": "f" * 64,
        "justification_engine_version": JUSTIFICATION_ENGINE_VERSION,
        "justification_method_name": JUSTIFICATION_METHOD_NAME,
        "justification_hash": "0" * 64,
    }
    base.update(overrides)
    return InvestigationJustification(**base)  # type: ignore[arg-type]


def test_justification_constructs() -> None:
    j = _valid_justification()
    assert j.justification_id == "j-01"
    assert j.schema_version == "1"


def test_justification_frozen() -> None:
    j = _valid_justification()
    with pytest.raises(FrozenInstanceError):
        j.justification_id = "x"  # type: ignore[misc]


def test_justification_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _valid_justification(justification_id="")


def test_justification_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="outside"):
        _valid_justification(justification_id="a/b")


def test_justification_rejects_invalid_anchor_type() -> None:
    with pytest.raises(ValueError, match="conclusion_anchor_type"):
        _valid_justification(conclusion_anchor_type="hypothesis")


def test_justification_rejects_empty_anchor_id() -> None:
    with pytest.raises(ValueError, match="conclusion_anchor_id"):
        _valid_justification(conclusion_anchor_id="")


def test_justification_rejects_bad_hashes() -> None:
    with pytest.raises(ValueError, match="conclusion_anchor_hash"):
        _valid_justification(conclusion_anchor_hash="bad")
    with pytest.raises(ValueError, match="source_manifest_hash"):
        _valid_justification(source_manifest_hash="bad")
    with pytest.raises(ValueError, match="justification_hash"):
        _valid_justification(justification_hash="bad")


def test_justification_accepts_none_workspace_hash() -> None:
    j = _valid_justification(workspace_hash=None)
    assert j.workspace_hash is None


def test_justification_rejects_bad_workspace_hash() -> None:
    with pytest.raises(ValueError, match="workspace_hash"):
        _valid_justification(workspace_hash="bad")


def test_justification_rejects_unsorted_category() -> None:
    a = _valid_entry(
        entry_role="evidence",
        entry_identifier="b",
        entry_hash=compute_chain_entry_hash("evidence", "b"),
    )
    b = _valid_entry(
        entry_role="evidence",
        entry_identifier="a",
        entry_hash=compute_chain_entry_hash("evidence", "a"),
    )
    with pytest.raises(ValueError, match="canonically sorted"):
        _valid_justification(minimal_evidence=(a, b))


def test_justification_rejects_duplicate_in_category() -> None:
    e = _valid_entry()
    with pytest.raises(ValueError, match="duplicate"):
        _valid_justification(minimal_evidence=(e, e))


# ---------------------------------------------------------------- JustificationDiff


def test_diff_constructs() -> None:
    d = JustificationDiff(
        justification_a_hash="a" * 64,
        justification_b_hash="b" * 64,
        added_entries=(),
        removed_entries=(),
        unchanged_entries=(),
        diff_hash="c" * 64,
    )
    assert d.schema_version == "1"


def test_diff_rejects_unsorted_group() -> None:
    a = _valid_entry(
        entry_role="evidence",
        entry_identifier="b",
        entry_hash=compute_chain_entry_hash("evidence", "b"),
    )
    b = _valid_entry(
        entry_role="evidence",
        entry_identifier="a",
        entry_hash=compute_chain_entry_hash("evidence", "a"),
    )
    with pytest.raises(ValueError, match="canonically sorted"):
        JustificationDiff(
            justification_a_hash="a" * 64,
            justification_b_hash="b" * 64,
            added_entries=(a, b),
            removed_entries=(),
            unchanged_entries=(),
            diff_hash="c" * 64,
        )


# ---------------------------------------------------------------- forbidden tokens

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "risk_level",
    "danger",
    "dangerous",
    "high_risk",
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
    "embedding",
    "clustering",
    "summary_text",
    "report_text",
    "explanation",
    "better",
    "worse",
    "important_",
    "relevant_",
    "regression",
    "improvement",
    "infer_",
    "predict_",
)


def _justification_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "justification"
    cli_module = repo / "src" / "aip" / "cli" / "justification_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_justification_module() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _justification_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], (
        f"Forbidden tokens in justification (ADR-0040 §G6): "
        f"{offenders}"
    )
