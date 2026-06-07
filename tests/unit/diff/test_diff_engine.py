"""Tests del Diff Engine (ADR-0039)."""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip.diff import (
    DIFF_SCHEMA_VERSION,
    DiffEntry,
    InvestigationDiff,
    compute_diff,
    compute_diff_hash,
    decode_diff,
    encode_diff,
    verify_diff,
)
from aip.snapshot import InvestigationSnapshot, SnapshotReference


def _ref(
    type_: str = "evidence", identifier: str = "E1", h: str = "a" * 64
) -> SnapshotReference:
    return SnapshotReference(
        reference_type=type_, identifier=identifier, artifact_hash=h
    )


def _snap(
    snapshot_id: str, refs: tuple[SnapshotReference, ...], h: str = "a" * 64
) -> InvestigationSnapshot:
    # Construir un snapshot válido para tests.
    return InvestigationSnapshot(
        snapshot_id=snapshot_id,
        workspace_hash="f" * 64,
        timeline_hash="f" * 64,
        referenced_artifacts=tuple(sorted(refs)),
        snapshot_hash=h,
    )


# ---------------------------------------------------------------- model


def test_schema_version_pinned() -> None:
    assert DIFF_SCHEMA_VERSION == "1"


def test_diff_entry_constructs() -> None:
    e = DiffEntry(
        reference_type="evidence", identifier="E1", artifact_hash="a" * 64
    )
    assert e.reference_type == "evidence"


def test_diff_entry_rejects_bad_hash() -> None:
    with pytest.raises(ValueError):
        DiffEntry(
            reference_type="evidence",
            identifier="E1",
            artifact_hash="not-hex",
        )


def test_diff_frozen() -> None:
    d = InvestigationDiff(
        snapshot_a_hash="a" * 64,
        snapshot_b_hash="b" * 64,
        added_artifacts=(),
        removed_artifacts=(),
        unchanged_artifacts=(),
        diff_hash="c" * 64,
    )
    with pytest.raises(FrozenInstanceError):
        d.snapshot_a_hash = "x"  # type: ignore[misc]


def test_diff_rejects_unsorted_groups() -> None:
    e1 = DiffEntry(
        reference_type="evidence", identifier="E1", artifact_hash="a" * 64
    )
    e2 = DiffEntry(
        reference_type="assessment", identifier="A1", artifact_hash="b" * 64
    )
    # e2 < e1 (assessment < evidence). Pasar (e1, e2) está unsorted.
    with pytest.raises(ValueError, match="canonically sorted"):
        InvestigationDiff(
            snapshot_a_hash="a" * 64,
            snapshot_b_hash="b" * 64,
            added_artifacts=(e1, e2),
            removed_artifacts=(),
            unchanged_artifacts=(),
            diff_hash="c" * 64,
        )


# ---------------------------------------------------------------- compute_diff


def test_compute_diff_identical_snapshots_yields_only_unchanged() -> None:
    refs = (_ref(),)
    s = _snap("s", refs)
    d = compute_diff(s, s)
    assert d.added_artifacts == ()
    assert d.removed_artifacts == ()
    assert len(d.unchanged_artifacts) == 1


def test_compute_diff_added_artifacts() -> None:
    s_a = _snap("a", ())
    s_b = _snap("b", (_ref(identifier="E1"), _ref(identifier="E2")))
    d = compute_diff(s_a, s_b)
    assert len(d.added_artifacts) == 2
    assert d.removed_artifacts == ()


def test_compute_diff_removed_artifacts() -> None:
    s_a = _snap("a", (_ref(identifier="E1"), _ref(identifier="E2")))
    s_b = _snap("b", ())
    d = compute_diff(s_a, s_b)
    assert d.added_artifacts == ()
    assert len(d.removed_artifacts) == 2


def test_compute_diff_mixed() -> None:
    e1 = _ref(identifier="E1", h="a" * 64)
    e2 = _ref(identifier="E2", h="b" * 64)
    e3 = _ref(identifier="E3", h="c" * 64)
    s_a = _snap("a", (e1, e2))
    s_b = _snap("b", (e2, e3))
    d = compute_diff(s_a, s_b)
    added_ids = {e.identifier for e in d.added_artifacts}
    removed_ids = {e.identifier for e in d.removed_artifacts}
    unchanged_ids = {e.identifier for e in d.unchanged_artifacts}
    assert added_ids == {"E3"}
    assert removed_ids == {"E1"}
    assert unchanged_ids == {"E2"}


def test_compute_diff_results_are_sorted() -> None:
    refs = tuple(
        _ref(identifier=f"E{i}", h=f"{i:064x}") for i in range(5)
    )
    s_a = _snap("a", ())
    s_b = _snap("b", refs)
    d = compute_diff(s_a, s_b)
    keys = [
        (e.reference_type, e.identifier, e.artifact_hash)
        for e in d.added_artifacts
    ]
    assert keys == sorted(keys)


def test_compute_diff_is_deterministic_across_runs() -> None:
    s_a = _snap("a", (_ref(identifier="E1"),))
    s_b = _snap("b", (_ref(identifier="E1"), _ref(identifier="E2")))
    d1 = compute_diff(s_a, s_b)
    d2 = compute_diff(s_a, s_b)
    assert d1 == d2


# ---------------------------------------------------------------- hashing


def test_verify_diff_success() -> None:
    s_a = _snap("a", (_ref(),))
    s_b = _snap("b", (_ref(),))
    d = compute_diff(s_a, s_b)
    assert verify_diff(d) is True


def test_verify_diff_failure_on_tampering() -> None:
    bad = InvestigationDiff(
        snapshot_a_hash="a" * 64,
        snapshot_b_hash="b" * 64,
        added_artifacts=(),
        removed_artifacts=(),
        unchanged_artifacts=(),
        diff_hash="b" * 64,  # no es el correcto
    )
    assert verify_diff(bad) is False


def test_compute_diff_hash_matches() -> None:
    s_a = _snap("a", (_ref(),))
    s_b = _snap("b", (_ref(),))
    d = compute_diff(s_a, s_b)
    assert compute_diff_hash(d) == d.diff_hash


# ---------------------------------------------------------------- encoding


def test_encode_decode_roundtrip() -> None:
    s_a = _snap("a", (_ref(identifier="E1"),))
    s_b = _snap("b", (_ref(identifier="E2"),))
    d = compute_diff(s_a, s_b)
    payload = encode_diff(d)
    decoded = decode_diff(payload)
    assert decoded == d


def test_encode_is_canonical() -> None:
    s_a = _snap("a", (_ref(),))
    s_b = _snap("b", (_ref(),))
    d = compute_diff(s_a, s_b)
    payload = encode_diff(d)
    parsed = json.loads(payload)
    canonical = (
        json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    assert payload == canonical


# ---------------------------------------------------------------- G3 + tokens


def test_diff_imports_no_forbidden_engines() -> None:
    """ADR-0039 §G3: diff/ no importa de graph/impact/context/timeline/analysis."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "diff"
    forbidden = {"graph", "impact", "context", "analysis", "timeline", "workspace"}
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if (
                    len(parts) >= 2
                    and parts[0] == "aip"
                    and parts[1] in forbidden
                ):
                    offenders.append((module_path.name, node.module))
            elif isinstance(node, ast.Import):
                for n in node.names:
                    parts = n.name.split(".")
                    if (
                        len(parts) >= 2
                        and parts[0] == "aip"
                        and parts[1] in forbidden
                    ):
                        offenders.append((module_path.name, n.name))
    assert offenders == [], f"diff/ imports forbidden engines: {offenders}"


_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "danger",
    "likelihood",
    "probability",
    "bayesian",
    "confidence_score",
    "recommendation",
    "ranking",
    "embedding",
    "clustering",
    "causal_inference",
    "hypothesis",
    "explanation",
    "better",
    "worse",
    "important_",
    "relevant_",
    "regression",
    "improvement",
)


def _diff_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "diff"
    cli_module = repo / "src" / "aip" / "cli" / "diff_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_diff_module() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _diff_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], (
        f"Forbidden tokens in diff: {offenders}"
    )
