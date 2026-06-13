"""Tests for inference-rule vocabulary embedding in HTML reports.

The HTML report's JS verifier mirrors ``aip.justification.logic.verifier``
client-side. To do that without hardcoding a separate JS copy of the rule
table, the report ships the Python vocabulary inline as
``inference_proof_rules``. These tests guarantee that anything the Python
verifier knows about, the JS verifier will also know about — adding a new
rule in Python automatically propagates without code change.
"""

from __future__ import annotations

from aip.justification.logic import ALLOWED_RULES, get_rule
from aip.report.builder import _inference_rule_specs_for_report

REQUIRED_FIELDS = {"name", "min_inputs", "max_inputs", "classification"}
VALID_CLASSIFICATIONS = {"deductive", "weak"}


def test_embedded_rules_cover_full_vocabulary() -> None:
    """Every rule in ALLOWED_RULES must appear in the embedded list.

    If this fails, the JS verifier will reject proofs that the Python
    verifier accepts — a silent inconsistency at the worst possible
    place. Treat any divergence as a release blocker.
    """
    embedded_names = {r["name"] for r in _inference_rule_specs_for_report()}
    assert embedded_names == ALLOWED_RULES


def test_embedded_rules_are_sorted_by_name() -> None:
    """Stable ordering keeps the report bytes deterministic when the same
    archive is exported twice. Important for reproducibility audits."""
    embedded = _inference_rule_specs_for_report()
    names = [r["name"] for r in embedded]
    assert names == sorted(names)


def test_embedded_rule_fields_match_python_spec() -> None:
    """Each embedded rule's arity + classification must agree byte-for-byte
    with the Python source. The JS verifier reads these as canonical."""
    for r in _inference_rule_specs_for_report():
        spec = get_rule(r["name"])
        assert spec is not None, f"rule {r['name']!r} no longer in vocabulary"
        assert r["min_inputs"] == spec.min_inputs
        assert r["max_inputs"] == spec.max_inputs
        assert r["classification"] == spec.classification


def test_embedded_rules_have_only_known_classifications() -> None:
    """Defensive: a typo like ``"deductiv"`` would silently fail to flag
    weak rules in the JS. Pin the closed set explicitly."""
    for r in _inference_rule_specs_for_report():
        assert r["classification"] in VALID_CLASSIFICATIONS


def test_embedded_rules_have_required_fields_only() -> None:
    """The shape must remain stable — JS reads positional-style keys.
    Extra fields are fine (forward-compat) but missing keys would break
    the verifier silently."""
    for r in _inference_rule_specs_for_report():
        missing = REQUIRED_FIELDS - r.keys()
        assert not missing, f"rule {r.get('name')!r} missing fields: {missing}"


def test_unbounded_arity_serialised_as_none() -> None:
    """``conjunction_intro`` and ``abduction_to_best_explanation`` have
    no upper arity bound. JS needs to receive that as ``null`` (which
    json.dumps emits from Python ``None``) so the comparison branch is
    skipped correctly. If this regresses to ``-1`` or ``"unlimited"``, the
    JS verifier will reject valid proofs."""
    by_name = {r["name"]: r for r in _inference_rule_specs_for_report()}
    assert by_name["conjunction_intro"]["max_inputs"] is None
    assert by_name["abduction_to_best_explanation"]["max_inputs"] is None
