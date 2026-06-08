"""Tests del modelo ``OperatorAttestation`` (ADR-0041 §modelo)."""

from __future__ import annotations

import dataclasses

import pytest

from aip.attestation import OperatorAttestation
from aip.attestation.models import (
    ALLOWED_ARTIFACT_KINDS,
    ATTESTATION_SCHEMA_VERSION,
    SIGNATURE_ALGORITHM,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_SIG_OK = "0" * 128
_FP_OK = "f" * 64
_TS_OK = "2026-06-07T12:00:00Z"


def _valid(**overrides: object) -> OperatorAttestation:
    base = {
        "artifact_kind": "workspace",
        "artifact_hash": _HASH_A,
        "signer_id": "@operator",
        "public_key_fingerprint": _FP_OK,
        "signature": _SIG_OK,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signed_at": _TS_OK,
        "attestation_hash": _HASH_B,
    }
    base.update(overrides)
    return OperatorAttestation(**base)  # type: ignore[arg-type]


def test_constants_are_pinned() -> None:
    assert ATTESTATION_SCHEMA_VERSION == "1"
    assert SIGNATURE_ALGORITHM == "ed25519-v1"
    assert (
        frozenset(
            {
                "workspace",
                "timeline",
                "snapshot",
                "justification",
                "context_bundle",
                "manifest",
            }
        )
        == ALLOWED_ARTIFACT_KINDS
    )


def test_happy_path_construction() -> None:
    att = _valid()
    assert att.artifact_kind == "workspace"
    assert att.schema_version == "1"


def test_frozen_dataclass() -> None:
    att = _valid()
    with pytest.raises(dataclasses.FrozenInstanceError):
        att.signer_id = "@evil"  # type: ignore[misc]


def test_invalid_artifact_kind_rejected() -> None:
    with pytest.raises(ValueError, match="artifact_kind"):
        _valid(artifact_kind="banana")


def test_artifact_hash_must_be_sha256_hex() -> None:
    with pytest.raises(ValueError, match="artifact_hash"):
        _valid(artifact_hash="not-hex")
    with pytest.raises(ValueError, match="artifact_hash"):
        _valid(artifact_hash="A" * 64)  # uppercase rejected


def test_empty_signer_id_rejected() -> None:
    with pytest.raises(ValueError, match="signer_id"):
        _valid(signer_id="")


def test_public_key_fingerprint_must_be_sha256_hex() -> None:
    with pytest.raises(ValueError, match="public_key_fingerprint"):
        _valid(public_key_fingerprint="g" * 64)


def test_signature_must_be_ed25519_hex_length() -> None:
    with pytest.raises(ValueError, match="signature must be ed25519"):
        _valid(signature="0" * 127)
    with pytest.raises(ValueError, match="signature must be ed25519"):
        _valid(signature="0" * 129)


def test_signature_algorithm_pinned_to_ed25519_v1() -> None:
    with pytest.raises(ValueError, match="signature_algorithm"):
        _valid(signature_algorithm="rsa-pss-v1")


def test_signed_at_iso_utc_only() -> None:
    with pytest.raises(ValueError, match="signed_at"):
        _valid(signed_at="2026-06-07T12:00:00+00:00")  # offset, no Z
    with pytest.raises(ValueError, match="signed_at"):
        _valid(signed_at="2026-06-07 12:00:00Z")  # space


def test_attestation_hash_must_be_sha256_hex() -> None:
    with pytest.raises(ValueError, match="attestation_hash"):
        _valid(attestation_hash="z" * 64)


def test_default_schema_version() -> None:
    att = _valid()
    assert att.schema_version == ATTESTATION_SCHEMA_VERSION
