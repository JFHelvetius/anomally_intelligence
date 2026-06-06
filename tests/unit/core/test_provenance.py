"""Tests unitarios de ``aip.core.provenance``."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from aip.core.provenance import (
    GapDescription,
    Provenance,
    ProvenanceStep,
    StepKind,
)

CANONICAL_ATTESTED_AT = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.UTC)
SAMPLE_EVIDENCE_HASH = "1f4a9c0a" + "0" * 56
SAMPLE_INPUT_HASH = "abcdef01" + "0" * 56
SAMPLE_OUTPUT_HASH = "fedcba98" + "0" * 56


def _make_step(**overrides: Any) -> ProvenanceStep:
    base: dict[str, Any] = {
        "step_id": 1,
        "kind": StepKind.ORIGINAL_CAPTURE,
    }
    base.update(overrides)
    return ProvenanceStep(**base)


def _make_provenance(**overrides: Any) -> Provenance:
    base: dict[str, Any] = {
        "evidence_hash": SAMPLE_EVIDENCE_HASH,
        "origin_source_id": "blue-book-nara",
        "attestor": "@jfhelvetius",
        "attested_at": CANONICAL_ATTESTED_AT,
    }
    base.update(overrides)
    return Provenance(**base)


# ---------------------------------------------------------------- StepKind


def test_step_kind_has_twelve_values_adr_0005() -> None:
    assert len(list(StepKind)) == 12


# ---------------------------------------------------------------- GapDescription


def test_gap_constructs_and_freezes() -> None:
    g = GapDescription(description="pasos intermedios desconocidos")
    assert g.description == "pasos intermedios desconocidos"
    with pytest.raises(ValidationError):
        g.description = "other"  # type: ignore[misc]


def test_gap_rejects_empty_description() -> None:
    with pytest.raises(ValidationError):
        GapDescription(description="")


def test_gap_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        GapDescription(description="x", level="high")  # type: ignore[call-arg]


# ---------------------------------------------------------------- ProvenanceStep


def test_step_constructs_with_minimal_required() -> None:
    s = _make_step()
    assert s.step_id == 1
    assert s.kind == StepKind.ORIGINAL_CAPTURE
    assert s.actor is None
    assert s.timestamp is None
    assert s.inputs == []
    assert s.outputs == []
    assert s.parameters == {}


def test_step_accepts_full_optional_fields() -> None:
    s = _make_step(
        actor="@scanner-operator",
        timestamp=CANONICAL_ATTESTED_AT,
        inputs=[SAMPLE_INPUT_HASH],
        outputs=[SAMPLE_OUTPUT_HASH],
        parameters={"dpi": "300", "software": "Capture One 22"},
        notes="Escaneo a 300 DPI desde original mecanografiado.",
    )
    assert s.actor == "@scanner-operator"
    assert s.parameters["dpi"] == "300"


def test_step_rejects_step_id_zero() -> None:
    with pytest.raises(ValidationError):
        _make_step(step_id=0)


def test_step_rejects_naive_timestamp() -> None:
    naive = dt.datetime(2026, 6, 4, 0, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        _make_step(timestamp=naive)


def test_step_rejects_bad_input_hash() -> None:
    with pytest.raises(ValidationError):
        _make_step(inputs=["not-a-hash"])


def test_step_rejects_uppercase_output_hash() -> None:
    with pytest.raises(ValidationError):
        _make_step(outputs=[SAMPLE_OUTPUT_HASH.upper()])


def test_step_rejects_non_string_parameter_value() -> None:
    with pytest.raises(ValidationError):
        _make_step(parameters={"dpi": 300})  # type: ignore[dict-item]


def test_step_is_frozen() -> None:
    s = _make_step()
    with pytest.raises(ValidationError):
        s.kind = StepKind.OCR  # type: ignore[misc]


def test_step_rejects_empty_actor_string() -> None:
    with pytest.raises(ValidationError):
        _make_step(actor="")


# ---------------------------------------------------------------- Provenance básico


def test_provenance_constructs_empty_chain() -> None:
    p = _make_provenance()
    assert p.steps == []
    assert p.gaps == []
    assert p.is_complete is False
    assert p.evidence_hash == SAMPLE_EVIDENCE_HASH


def test_provenance_constructs_with_minimal_chain() -> None:
    p = _make_provenance(
        steps=[_make_step()],
        gaps=[GapDescription(description="ingestión inicial sin reconstrucción previa")],
    )
    assert len(p.steps) == 1
    assert len(p.gaps) == 1


def test_provenance_rejects_naive_attested_at() -> None:
    naive = dt.datetime(2026, 6, 4, 0, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        _make_provenance(attested_at=naive)


def test_provenance_rejects_bad_evidence_hash() -> None:
    with pytest.raises(ValidationError):
        _make_provenance(evidence_hash="abc")


def test_provenance_rejects_empty_origin_source_id() -> None:
    with pytest.raises(ValidationError):
        _make_provenance(origin_source_id="")


def test_provenance_rejects_empty_attestor() -> None:
    with pytest.raises(ValidationError):
        _make_provenance(attestor="")


def test_provenance_is_frozen() -> None:
    p = _make_provenance()
    with pytest.raises(ValidationError):
        p.is_complete = True  # type: ignore[misc]


def test_provenance_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _make_provenance(signed_by="anyone")


# ---------------------------------------------------------------- validadores cruzados


def test_provenance_rejects_duplicate_step_ids() -> None:
    s1 = _make_step(step_id=1, kind=StepKind.ORIGINAL_CAPTURE)
    s2 = _make_step(step_id=1, kind=StepKind.ANALOG_TO_DIGITAL)
    with pytest.raises(ValidationError, match="duplicate step_id"):
        _make_provenance(steps=[s1, s2])


def test_provenance_complete_with_gaps_rejected() -> None:
    gap = GapDescription(description="paso intermedio desconocido")
    with pytest.raises(ValidationError, match="complete"):
        _make_provenance(is_complete=True, gaps=[gap])


def test_provenance_complete_without_gaps_allowed() -> None:
    p = _make_provenance(is_complete=True)
    assert p.is_complete is True
    assert p.gaps == []


def test_provenance_incomplete_with_gaps_allowed() -> None:
    gap = GapDescription(description="paso intermedio desconocido")
    p = _make_provenance(is_complete=False, gaps=[gap])
    assert p.is_complete is False
    assert len(p.gaps) == 1
