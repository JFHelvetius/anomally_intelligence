"""Tests del modelo de Investigation Workspace (ADR-0036 §modelo)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip.workspace import (
    ALLOWED_REFERENCE_TYPES,
    WORKSPACE_SCHEMA_VERSION,
    InvestigationWorkspace,
    ReferenceType,
    WorkspaceReference,
    compute_artifact_hash,
)

# ---------------------------------------------------------------- constantes


def test_workspace_schema_version_is_pinned() -> None:
    assert WORKSPACE_SCHEMA_VERSION == "1"


def test_allowed_reference_types_is_closed_taxonomy() -> None:
    assert (
        frozenset({"evidence", "assessment", "impact_analysis", "context_bundle"})
        == ALLOWED_REFERENCE_TYPES
    )


def test_reference_type_enum_matches_allowed_set() -> None:
    assert {rt.value for rt in ReferenceType} == ALLOWED_REFERENCE_TYPES


# ---------------------------------------------------------------- WorkspaceReference


def _valid_ref(**overrides) -> WorkspaceReference:
    base: dict[str, object] = {
        "reference_type": "evidence",
        "identifier": "E001",
        "artifact_hash": compute_artifact_hash("evidence", "E001"),
    }
    base.update(overrides)
    return WorkspaceReference(**base)  # type: ignore[arg-type]


def test_reference_constructs_with_valid_inputs() -> None:
    r = _valid_ref()
    assert r.reference_type == "evidence"
    assert r.identifier == "E001"
    assert len(r.artifact_hash) == 64


def test_reference_is_frozen() -> None:
    r = _valid_ref()
    with pytest.raises(FrozenInstanceError):
        r.identifier = "E999"  # type: ignore[misc]


def test_reference_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="invalid reference_type"):
        WorkspaceReference(
            reference_type="hypothesis",
            identifier="H1",
            artifact_hash="0" * 64,
        )


def test_reference_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        WorkspaceReference(
            reference_type="evidence",
            identifier="",
            artifact_hash="0" * 64,
        )


def test_reference_rejects_non_hex_artifact_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        WorkspaceReference(
            reference_type="evidence",
            identifier="E001",
            artifact_hash="not-a-hash",
        )


def test_reference_orders_by_type_then_identifier() -> None:
    a = WorkspaceReference(
        reference_type="assessment",
        identifier="A001",
        artifact_hash=compute_artifact_hash("assessment", "A001"),
    )
    b = WorkspaceReference(
        reference_type="evidence",
        identifier="E001",
        artifact_hash=compute_artifact_hash("evidence", "E001"),
    )
    # "assessment" < "evidence" lexicograficamente.
    assert a < b


# ---------------------------------------------------------------- artifact_hash


def test_compute_artifact_hash_is_deterministic() -> None:
    a = compute_artifact_hash("evidence", "E001")
    b = compute_artifact_hash("evidence", "E001")
    assert a == b


def test_compute_artifact_hash_distinguishes_inputs() -> None:
    a = compute_artifact_hash("evidence", "E001")
    b = compute_artifact_hash("evidence", "E002")
    c = compute_artifact_hash("assessment", "E001")
    assert len({a, b, c}) == 3


def test_compute_artifact_hash_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="invalid reference_type"):
        compute_artifact_hash("hypothesis", "H1")


def test_compute_artifact_hash_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        compute_artifact_hash("evidence", "")


# ---------------------------------------------------------------- InvestigationWorkspace


def _valid_workspace(**overrides) -> InvestigationWorkspace:
    refs = (
        _valid_ref(
            reference_type="assessment",
            identifier="A001",
            artifact_hash=compute_artifact_hash("assessment", "A001"),
        ),
        _valid_ref(
            reference_type="evidence",
            identifier="E001",
            artifact_hash=compute_artifact_hash("evidence", "E001"),
        ),
    )
    base: dict[str, object] = {
        "workspace_id": "fraud-chain-01",
        "title": "Fraud Investigation",
        "references": refs,
        "source_manifest_hash": "f" * 64,
        "workspace_hash": "0" * 64,
    }
    base.update(overrides)
    return InvestigationWorkspace(**base)  # type: ignore[arg-type]


def test_workspace_constructs_with_valid_inputs() -> None:
    w = _valid_workspace()
    assert w.workspace_id == "fraud-chain-01"
    assert w.title == "Fraud Investigation"
    assert len(w.references) == 2
    assert w.schema_version == "1"


def test_workspace_is_frozen() -> None:
    w = _valid_workspace()
    with pytest.raises(FrozenInstanceError):
        w.title = "Other"  # type: ignore[misc]


def test_workspace_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="workspace_id must be non-empty"):
        _valid_workspace(workspace_id="")


def test_workspace_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="ASCII-safe"):
        _valid_workspace(workspace_id="a/b")


def test_workspace_rejects_empty_title() -> None:
    with pytest.raises(ValueError, match="title must be non-empty"):
        _valid_workspace(title="")


def test_workspace_rejects_bad_source_manifest_hash() -> None:
    with pytest.raises(ValueError, match="source_manifest_hash"):
        _valid_workspace(source_manifest_hash="not-a-hash")


def test_workspace_rejects_bad_workspace_hash() -> None:
    with pytest.raises(ValueError, match="workspace_hash"):
        _valid_workspace(workspace_hash="bad")


def test_workspace_rejects_duplicate_references() -> None:
    dup = _valid_ref(
        reference_type="evidence",
        identifier="E001",
        artifact_hash=compute_artifact_hash("evidence", "E001"),
    )
    with pytest.raises(ValueError, match="duplicate"):
        _valid_workspace(references=(dup, dup))


def test_workspace_rejects_unsorted_references() -> None:
    refs_unsorted = (
        _valid_ref(
            reference_type="evidence",
            identifier="E001",
            artifact_hash=compute_artifact_hash("evidence", "E001"),
        ),
        _valid_ref(
            reference_type="assessment",
            identifier="A001",
            artifact_hash=compute_artifact_hash("assessment", "A001"),
        ),
    )
    with pytest.raises(ValueError, match="canonically sorted"):
        _valid_workspace(references=refs_unsorted)


def test_workspace_accepts_empty_references() -> None:
    w = _valid_workspace(references=())
    assert w.references == ()


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
    "clustering",
    "embedding",
    "ranking",
    "interpret",
    "conclusion",
)


def _workspace_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "workspace"
    cli_module = repo / "src" / "aip" / "cli" / "workspace_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_workspace_module() -> None:
    """ADR-0036 §componentes excluidos + §G6: ningún token interpretativo
    en el código del paquete de workspace.
    """
    offenders: list[tuple[str, str]] = []
    for path in _workspace_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], f"Forbidden tokens found (ADR-0036 §componentes excluidos): {offenders}"
