"""Tests unitarios de ``aip.core.evidence``."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from aip.core.evidence import (
    AuthenticationAssessment,
    AuthStatus,
    Evidence,
    EvidenceKind,
    EvidenceStatus,
)

# Constantes canónicas para construcción de fixtures sintéticos.
CANONICAL_INGESTED_AT = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.timezone.utc)
SAMPLE_HASH = "1f4a9c0a" + "0" * 56  # 64 chars, válido por forma
SAMPLE_CONTENT_URI = f"objects/sha256/{SAMPLE_HASH[:2]}/{SAMPLE_HASH[2:]}"


def _make_evidence(**overrides: Any) -> Evidence:
    base: dict[str, Any] = {
        "hash": SAMPLE_HASH,
        "kind": EvidenceKind.DOCUMENT_SCAN,
        "content_uri": SAMPLE_CONTENT_URI,
        "size_bytes": 356721,
        "mime_type": "application/pdf",
        "source_id": "blue-book-nara",
        "ingested_at": CANONICAL_INGESTED_AT,
        "ingested_by": "@jfhelvetius",
        "schema_version": "0.1.0",
    }
    base.update(overrides)
    return Evidence(**base)


# ---------------------------------------------------------------- enum cardinalidad


def test_evidence_kind_has_thirteen_values_adr_0006() -> None:
    # Cerrada por ADR-0006; cualquier cambio requiere ADR de enmienda.
    assert len(list(EvidenceKind)) == 13


def test_evidence_status_has_five_values_adr_0006() -> None:
    assert len(list(EvidenceStatus)) == 5


def test_auth_status_has_six_values_adr_0006() -> None:
    assert len(list(AuthStatus)) == 6


# ---------------------------------------------------------------- construcción válida


def test_evidence_constructs_with_canonical_fixture() -> None:
    ev = _make_evidence()
    assert ev.hash == SAMPLE_HASH
    assert ev.kind == EvidenceKind.DOCUMENT_SCAN
    assert ev.status == EvidenceStatus.ACTIVE  # default
    assert ev.authentication.status == AuthStatus.UNVERIFIED  # default conservador
    assert ev.intrinsic_metadata == {}  # default empty dict
    assert ev.notes is None


def test_evidence_aip_uri_format() -> None:
    ev = _make_evidence()
    assert ev.aip_uri() == f"aip:evidence/sha256:{SAMPLE_HASH}"


def test_evidence_zero_size_allowed() -> None:
    # Un fichero vacío es artefacto válido; su hash es e3b0c44...
    ev = _make_evidence(
        hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        size_bytes=0,
    )
    assert ev.size_bytes == 0


# ---------------------------------------------------------------- validaciones de hash


def test_evidence_rejects_uppercase_hash() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(hash=SAMPLE_HASH.upper())


def test_evidence_rejects_short_hash() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(hash="abc")


def test_evidence_rejects_non_hex_hash() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(hash="z" * 64)


def test_evidence_rejects_hash_with_prefix() -> None:
    # El campo `hash` almacena solo el hex; el prefijo `sha256:` vive en aip_uri.
    with pytest.raises(ValidationError):
        _make_evidence(hash="sha256:" + SAMPLE_HASH)


# ---------------------------------------------------------------- otras validaciones


def test_evidence_rejects_negative_size() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(size_bytes=-1)


def test_evidence_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(unexpected_field="x")


def test_evidence_rejects_naive_ingested_at() -> None:
    naive = dt.datetime(2026, 6, 4, 0, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        _make_evidence(ingested_at=naive)


def test_evidence_rejects_windows_path_separator_in_content_uri() -> None:
    with pytest.raises(ValidationError, match="POSIX"):
        _make_evidence(content_uri="objects\\sha256\\1f\\4a")


def test_evidence_rejects_empty_string_fields() -> None:
    with pytest.raises(ValidationError):
        _make_evidence(mime_type="")
    with pytest.raises(ValidationError):
        _make_evidence(source_id="")
    with pytest.raises(ValidationError):
        _make_evidence(ingested_by="")
    with pytest.raises(ValidationError):
        _make_evidence(schema_version="")
    with pytest.raises(ValidationError):
        _make_evidence(content_uri="")


# ---------------------------------------------------------------- inmutabilidad


def test_evidence_is_frozen() -> None:
    ev = _make_evidence()
    with pytest.raises(ValidationError):
        ev.status = EvidenceStatus.RETRACTED  # type: ignore[misc]


def test_evidence_authentication_is_frozen() -> None:
    a = AuthenticationAssessment()
    with pytest.raises(ValidationError):
        a.status = AuthStatus.AUTHENTIC  # type: ignore[misc]


# ---------------------------------------------------------------- authentication


def test_authentication_default_is_unverified() -> None:
    a = AuthenticationAssessment()
    assert a.status == AuthStatus.UNVERIFIED
    assert a.assessor is None
    assert a.assessed_at is None
    assert a.method is None


def test_authentication_rejects_naive_assessed_at() -> None:
    naive = dt.datetime(2026, 6, 4, 0, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        AuthenticationAssessment(assessed_at=naive)


def test_authentication_accepts_aware_assessed_at() -> None:
    a = AuthenticationAssessment(
        status=AuthStatus.PROVISIONALLY_AUTHENTIC,
        assessor="@reviewer",
        assessed_at=CANONICAL_INGESTED_AT,
        method="metadata_review",
    )
    assert a.status == AuthStatus.PROVISIONALLY_AUTHENTIC
    assert a.assessor == "@reviewer"
    assert a.assessed_at == CANONICAL_INGESTED_AT
