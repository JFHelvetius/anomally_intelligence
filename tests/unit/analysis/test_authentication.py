"""Tests unitarios del motor derivado de autenticidad (ADR-0032).

Cubre los tres niveles independientes del motor:

1. **Modelo**: ``AuthenticationAssessment`` (frozen, validadores).
2. **Regla determinista**: ``classify`` (cuatro ramas booleanas puras).
3. **Builder**: ``build_authentication_assessment`` (orquesta regla + modelo).

Los tests de integración con ``Archive`` viven en ``tests/unit/test_archive.py``.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from pydantic import ValidationError

from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import (
    RATIONALES,
    AssessmentMethod,
    AssessmentStatus,
    AuthenticationAssessment,
    build_authentication_assessment,
    classify,
    make_assessment_id,
)
from aip.core.hashing import jcs_canonicalize, sha256_hex

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
CANONICAL_EVIDENCE_ID = "a" * 64


# ---------------------------------------------------------------- enums


def test_assessment_status_has_five_closed_values() -> None:
    # Cierre por ADR-0032 §2: si esta lista crece, el ADR debe ser enmendado.
    assert {s.value for s in AssessmentStatus} == {
        "unknown",
        "unverified",
        "partially_supported",
        "supported",
        "contradicted",
    }


def test_assessment_method_has_three_closed_values() -> None:
    assert {m.value for m in AssessmentMethod} == {
        "manual_research",
        "provenance_review",
        "chain_of_custody_review",
    }


def test_rationales_cover_all_statuses() -> None:
    # Garantía: cada status tiene un rationale fijo. Esto evita silencios
    # cuando se añade un status en el futuro sin actualizar RATIONALES.
    assert set(RATIONALES.keys()) == set(AssessmentStatus)


# ---------------------------------------------------------------- model: happy path


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "assessment_id": f"{CANONICAL_EVIDENCE_ID}__provenance_review",
        "evidence_id": CANONICAL_EVIDENCE_ID,
        "created_at": CANONICAL_TS,
        "method": AssessmentMethod.PROVENANCE_REVIEW,
        "status": AssessmentStatus.SUPPORTED,
        "rationale": RATIONALES[AssessmentStatus.SUPPORTED],
        "supporting_source_ids": ["blue-book-nara"],
        "schema_version": SCHEMA_VERSION,
    }
    base.update(overrides)
    return base


def test_model_constructs_from_valid_inputs() -> None:
    a = AuthenticationAssessment(**_valid_kwargs())
    assert a.status == AssessmentStatus.SUPPORTED
    assert a.method == AssessmentMethod.PROVENANCE_REVIEW
    assert a.evidence_id == CANONICAL_EVIDENCE_ID
    assert a.rationale == RATIONALES[AssessmentStatus.SUPPORTED]


def test_model_is_frozen() -> None:
    a = AuthenticationAssessment(**_valid_kwargs())
    with pytest.raises(ValidationError):
        a.status = AssessmentStatus.CONTRADICTED  # type: ignore[misc]


def test_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuthenticationAssessment(**_valid_kwargs(extra_field="x"))


# ---------------------------------------------------------------- model: validators


def test_created_at_naive_is_rejected() -> None:
    naive = dt.datetime(2026, 6, 4, 0, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        AuthenticationAssessment(**_valid_kwargs(created_at=naive))


def test_created_at_with_microseconds_is_rejected() -> None:
    with_micros = dt.datetime(2026, 6, 4, 0, 0, 0, 123, tzinfo=UTC)
    with pytest.raises(ValidationError, match="microsecond=0"):
        AuthenticationAssessment(**_valid_kwargs(created_at=with_micros))


def test_evidence_id_must_be_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        AuthenticationAssessment(**_valid_kwargs(evidence_id="not-a-hash"))


def test_assessment_id_rejects_unsafe_filename() -> None:
    with pytest.raises(ValidationError):
        AuthenticationAssessment(**_valid_kwargs(assessment_id="x/y"))


def test_supporting_source_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        AuthenticationAssessment(**_valid_kwargs(supporting_source_ids=["a", "a"]))


def test_supporting_source_ids_must_be_sorted() -> None:
    with pytest.raises(ValidationError, match="sorted"):
        AuthenticationAssessment(**_valid_kwargs(supporting_source_ids=["b", "a"]))


def test_supporting_source_ids_can_be_empty() -> None:
    a = AuthenticationAssessment(
        **_valid_kwargs(
            status=AssessmentStatus.UNVERIFIED,
            rationale=RATIONALES[AssessmentStatus.UNVERIFIED],
            supporting_source_ids=[],
        )
    )
    assert a.supporting_source_ids == []


# ---------------------------------------------------------------- rule engine: classify


def test_classify_unverified_when_no_source() -> None:
    status, supporting = classify(
        source_exists=False,
        has_provenance_steps=False,
        provenance_reference_intact=True,
    )
    assert status == AssessmentStatus.UNVERIFIED
    assert supporting == []


def test_classify_partially_supported_when_source_but_no_steps() -> None:
    status, _ = classify(
        source_exists=True,
        has_provenance_steps=False,
        provenance_reference_intact=True,
    )
    assert status == AssessmentStatus.PARTIALLY_SUPPORTED


def test_classify_supported_when_all_present() -> None:
    status, _ = classify(
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
    )
    assert status == AssessmentStatus.SUPPORTED


def test_classify_contradicted_when_reference_broken_dominates() -> None:
    # Una referencia rota gana sobre cualquier otro estado.
    for src_exists in (True, False):
        for has_steps in (True, False):
            status, _ = classify(
                source_exists=src_exists,
                has_provenance_steps=has_steps,
                provenance_reference_intact=False,
            )
            assert status == AssessmentStatus.CONTRADICTED


def test_classify_is_pure_no_unknown() -> None:
    # V1 nunca emite UNKNOWN desde classify; está reservado para futuros métodos.
    for src in (True, False):
        for steps in (True, False):
            for ref in (True, False):
                status, _ = classify(
                    source_exists=src,
                    has_provenance_steps=steps,
                    provenance_reference_intact=ref,
                )
                assert status != AssessmentStatus.UNKNOWN


# ---------------------------------------------------------------- assessment_id


def test_make_assessment_id_is_deterministic() -> None:
    a = make_assessment_id(CANONICAL_EVIDENCE_ID, AssessmentMethod.PROVENANCE_REVIEW)
    b = make_assessment_id(CANONICAL_EVIDENCE_ID, AssessmentMethod.PROVENANCE_REVIEW)
    assert a == b
    assert a == f"{CANONICAL_EVIDENCE_ID}__provenance_review"


def test_make_assessment_id_distinguishes_methods() -> None:
    a = make_assessment_id(CANONICAL_EVIDENCE_ID, AssessmentMethod.MANUAL_RESEARCH)
    b = make_assessment_id(CANONICAL_EVIDENCE_ID, AssessmentMethod.PROVENANCE_REVIEW)
    c = make_assessment_id(CANONICAL_EVIDENCE_ID, AssessmentMethod.CHAIN_OF_CUSTODY_REVIEW)
    assert len({a, b, c}) == 3


# ---------------------------------------------------------------- builder


def test_builder_supported_path() -> None:
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["blue-book-nara"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    assert a.status == AssessmentStatus.SUPPORTED
    assert a.supporting_source_ids == ["blue-book-nara"]
    assert a.rationale == RATIONALES[AssessmentStatus.SUPPORTED]
    assert a.assessment_id == f"{CANONICAL_EVIDENCE_ID}__provenance_review"


def test_builder_unverified_path_drops_support() -> None:
    # Sin Source → status UNVERIFIED. Aunque el caller pase supporting,
    # el builder lo descarta para mantener coherencia.
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=False,
        has_provenance_steps=False,
        provenance_reference_intact=True,
        supporting_source_ids=["ghost-id"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    assert a.status == AssessmentStatus.UNVERIFIED
    assert a.supporting_source_ids == []


def test_builder_contradicted_path_drops_support() -> None:
    # Referencia rota → CONTRADICTED. supporting_source_ids vacío aunque
    # source_exists sea True, porque la incoherencia invalida el respaldo.
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=False,
        supporting_source_ids=["blue-book-nara"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    assert a.status == AssessmentStatus.CONTRADICTED
    assert a.supporting_source_ids == []


def test_builder_partially_supported_keeps_sources_sorted() -> None:
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=False,
        provenance_reference_intact=True,
        supporting_source_ids=["zeta-archive", "alpha-archive", "zeta-archive"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    assert a.status == AssessmentStatus.PARTIALLY_SUPPORTED
    # Dedup + sorted: invariante del modelo.
    assert a.supporting_source_ids == ["alpha-archive", "zeta-archive"]


def test_builder_is_deterministic() -> None:
    kwargs = dict(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["blue-book-nara"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    a = build_authentication_assessment(**kwargs)
    b = build_authentication_assessment(**kwargs)
    # Identidad bit a bit del payload canónico.
    assert jcs_canonicalize(a.model_dump(mode="json")) == jcs_canonicalize(
        b.model_dump(mode="json")
    )


def test_builder_uses_schema_version_constant() -> None:
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["s"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    assert a.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------- serialization


def test_model_serializes_to_jcs_compatible_json() -> None:
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["blue-book-nara"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    payload = a.model_dump(mode="json")
    # No floats, no bytes — JCS-compatible.
    canonical = jcs_canonicalize(payload)
    assert sha256_hex(canonical) == sha256_hex(jcs_canonicalize(payload))


def test_model_roundtrip_through_json() -> None:
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["s1", "s2"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    blob = json.dumps(a.model_dump(mode="json"))
    b = AuthenticationAssessment.model_validate(json.loads(blob))
    assert a == b


def test_model_dump_keys_are_canonical() -> None:
    # El payload JCS debe incluir todos los campos esperados.
    a = build_authentication_assessment(
        evidence_id=CANONICAL_EVIDENCE_ID,
        source_exists=True,
        has_provenance_steps=True,
        provenance_reference_intact=True,
        supporting_source_ids=["s"],
        method=AssessmentMethod.PROVENANCE_REVIEW,
        created_at=CANONICAL_TS,
    )
    payload = a.model_dump(mode="json")
    assert set(payload.keys()) == {
        "assessment_id",
        "evidence_id",
        "created_at",
        "method",
        "status",
        "rationale",
        "supporting_source_ids",
        "schema_version",
    }
