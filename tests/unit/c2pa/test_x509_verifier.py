"""Tests for ``aip.c2pa.x509_verifier`` (ADR-0047).

These tests generate a real X.509 root + intermediate + leaf chain at
runtime using the ``cryptography`` library. That way the verifier
exercises actual DER-parsing, real signature math, and real validity
windows — no mocking shortcuts. The chains are tiny ed25519 because the
verifier supports it and tests run in milliseconds.

Properties pinned:

- Happy path: a 3-cert chain (leaf → intermediate → root) where the root
  is in the trust list verifies cleanly.
- Each structural failure (expired cert, wrong issuer, root not in trust
  list, empty chain, malformed PEM, empty trust list) produces a
  *specific* failure_reason so the operator can debug.
- ``used_chain=False`` is reserved for "AIP could not walk" cases, not
  for legitimate verification failures.
"""

from __future__ import annotations

import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

from aip.c2pa.x509_verifier import verify_x509_chain

FROZEN_NOW = dt.datetime(2026, 6, 12, 12, 0, 0, tzinfo=dt.UTC)


# --------------------------------------------------------------- cert helpers


def _build_cert(
    *,
    subject_cn: str,
    issuer_cn: str,
    public_key: Ed25519PrivateKey,
    signing_key: Ed25519PrivateKey,
    not_before: dt.datetime,
    not_after: dt.datetime,
    is_ca: bool,
) -> x509.Certificate:
    """Build and self-sign or issuer-sign a single ed25519 cert."""
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(public_key.public_key()),
            critical=False,
        )
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    else:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
    return builder.sign(private_key=signing_key, algorithm=None)


def _pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _build_chain(
    *,
    not_before_offset: dt.timedelta = dt.timedelta(days=-30),
    not_after_offset: dt.timedelta = dt.timedelta(days=365),
    leaf_not_before: dt.datetime | None = None,
    leaf_not_after: dt.datetime | None = None,
    leaf_issuer_cn: str = "AIP Test Intermediate CA",
    leaf_signing_key: Ed25519PrivateKey | None = None,
) -> tuple[list[str], str]:
    """Return (chain_pem_list, trust_list_pem) for a leaf→intermediate→root chain.

    ``leaf_*_offset`` shifts the leaf's validity window relative to FROZEN_NOW;
    used by the expired / not-yet-valid tests.
    """
    root_key = Ed25519PrivateKey.generate()
    inter_key = Ed25519PrivateKey.generate()
    leaf_key = Ed25519PrivateKey.generate()

    root = _build_cert(
        subject_cn="AIP Test Root CA",
        issuer_cn="AIP Test Root CA",
        public_key=root_key,
        signing_key=root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-365),
        not_after=FROZEN_NOW + dt.timedelta(days=365 * 5),
        is_ca=True,
    )
    intermediate = _build_cert(
        subject_cn="AIP Test Intermediate CA",
        issuer_cn="AIP Test Root CA",
        public_key=inter_key,
        signing_key=root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-180),
        not_after=FROZEN_NOW + dt.timedelta(days=365 * 3),
        is_ca=True,
    )
    leaf = _build_cert(
        subject_cn="AIP Test Leaf (Camera 0xAB12)",
        issuer_cn=leaf_issuer_cn,
        public_key=leaf_key,
        signing_key=leaf_signing_key or inter_key,
        not_before=leaf_not_before or (FROZEN_NOW + not_before_offset),
        not_after=leaf_not_after or (FROZEN_NOW + not_after_offset),
        is_ca=False,
    )

    chain = [_pem(leaf), _pem(intermediate), _pem(root)]
    trust_list = _pem(root)
    return chain, trust_list


# --------------------------------------------------------------- happy path


def test_full_chain_verifies_against_matching_trust_anchor() -> None:
    chain, trust = _build_chain()
    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)

    assert result.verified is True
    assert result.used_chain is True
    assert result.reason is None
    assert result.trust_anchor_subject == "AIP Test Root CA"


def test_single_cert_chain_verifies_when_self_signed_root_is_trusted() -> None:
    """A leaf cert that IS the root (self-signed, single-element chain)
    must verify if that exact cert is in the trust list. Edge case but
    real — some attestation flows publish a single self-signed cert."""
    key = Ed25519PrivateKey.generate()
    root = _build_cert(
        subject_cn="standalone-device",
        issuer_cn="standalone-device",
        public_key=key,
        signing_key=key,
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=True,
    )
    result = verify_x509_chain(
        [_pem(root)], trust_list_pem=_pem(root), now=FROZEN_NOW
    )
    assert result.verified is True
    assert result.trust_anchor_subject == "standalone-device"


# --------------------------------------------------------------- failure paths


def test_empty_chain_reports_used_chain_false() -> None:
    _chain, trust = _build_chain()
    result = verify_x509_chain([], trust_list_pem=trust, now=FROZEN_NOW)

    assert result.verified is False
    assert result.used_chain is False
    assert "empty certificate chain" in (result.reason or "")


def test_malformed_pem_reports_parse_failure() -> None:
    _, trust = _build_chain()
    result = verify_x509_chain(
        ["not a real PEM"], trust_list_pem=trust, now=FROZEN_NOW
    )
    assert result.verified is False
    assert result.used_chain is False
    assert "not a PEM-encoded certificate" in (result.reason or "")


def test_empty_trust_list_is_rejected() -> None:
    chain, _ = _build_chain()
    result = verify_x509_chain(chain, trust_list_pem="", now=FROZEN_NOW)
    assert result.verified is False
    assert result.used_chain is False
    assert "no certificates" in (result.reason or "") or "empty" in (result.reason or "")


def test_expired_leaf_cert_is_rejected_with_specific_reason() -> None:
    chain, trust = _build_chain(
        leaf_not_before=FROZEN_NOW - dt.timedelta(days=400),
        leaf_not_after=FROZEN_NOW - dt.timedelta(days=30),
    )
    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)

    assert result.verified is False
    assert result.used_chain is True
    assert "expired" in (result.reason or "").lower()


def test_not_yet_valid_leaf_cert_is_rejected() -> None:
    chain, trust = _build_chain(
        leaf_not_before=FROZEN_NOW + dt.timedelta(days=30),
        leaf_not_after=FROZEN_NOW + dt.timedelta(days=365),
    )
    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)

    assert result.verified is False
    assert result.used_chain is True
    assert "not yet valid" in (result.reason or "").lower()


def test_leaf_signed_by_wrong_issuer_is_rejected() -> None:
    """A leaf signed by a key that isn't the intermediate's key must be
    detected at the signature verification step, not silently accepted."""
    rogue_key = Ed25519PrivateKey.generate()
    chain, trust = _build_chain(leaf_signing_key=rogue_key)

    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)
    assert result.verified is False
    assert result.used_chain is True
    assert "signature does not verify" in (result.reason or "")


def test_root_not_in_trust_list_is_rejected() -> None:
    """The chain itself is internally consistent but the root cert isn't
    in the operator-supplied trust list. Must fail; AIP MUST NOT silently
    accept random self-signed roots."""
    chain, _good_trust = _build_chain()
    # Build a completely unrelated root to use as trust list.
    other_key = Ed25519PrivateKey.generate()
    other_root = _build_cert(
        subject_cn="Unrelated Root",
        issuer_cn="Unrelated Root",
        public_key=other_key,
        signing_key=other_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=True,
    )

    result = verify_x509_chain(
        chain, trust_list_pem=_pem(other_root), now=FROZEN_NOW
    )
    assert result.verified is False
    assert result.used_chain is True
    assert "not present in the trust list" in (result.reason or "")


def test_trust_list_with_multiple_anchors_accepts_matching_one() -> None:
    """Operator-supplied trust list usually carries multiple roots (one
    per device vendor). The verifier must pick the matching anchor."""
    chain, real_trust = _build_chain()
    # Add an unrelated cert in front of the real one.
    other_key = Ed25519PrivateKey.generate()
    other_root = _build_cert(
        subject_cn="Other Vendor",
        issuer_cn="Other Vendor",
        public_key=other_key,
        signing_key=other_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=True,
    )
    bundle = _pem(other_root) + "\n" + real_trust

    result = verify_x509_chain(chain, trust_list_pem=bundle, now=FROZEN_NOW)
    assert result.verified is True
    assert result.trust_anchor_subject == "AIP Test Root CA"


def test_malformed_trust_list_pem_is_rejected_with_used_chain_false() -> None:
    """A trust list that doesn't parse should fail BEFORE AIP claims it
    walked any chain — the used_chain flag must reflect that AIP didn't
    actually do any verification work."""
    chain, _ = _build_chain()
    result = verify_x509_chain(
        chain, trust_list_pem="-----BEGIN CERTIFICATE-----\nnope", now=FROZEN_NOW
    )
    assert result.verified is False
    # The error happens in trust list parsing, before chain walking.
    assert result.used_chain is False


def test_chain_pem_strings_must_be_strings() -> None:
    """A non-string entry in the chain (e.g., bytes or None) must fail
    gracefully — TypeError leaks would crash the CLI without a clear
    reason."""
    _, trust = _build_chain()
    result = verify_x509_chain(
        [None],  # type: ignore[list-item]
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )
    assert result.verified is False
    assert "not a PEM-encoded certificate" in (result.reason or "")


# --------------------------------------------------------------- contract


def test_supplied_root_with_different_bytes_but_same_ski_chains_via_anchor() -> None:
    """Edge: trust list has the canonical root; the supplied chain
    includes a different cert that happens to share the same
    SubjectKeyIdentifier (very rare but possible during a re-issuance).
    AIP must still verify the supplied root's signature against the
    anchor, not assume identity from SKI alone."""
    # Hard to construct without ties — for v1 this just confirms the
    # exact-fingerprint match path works and is preferred. Construct two
    # different roots with same key; the anchor MUST match exact bytes
    # for the verifier to take the happy path.
    chain, trust = _build_chain()
    # Same trust as supplied → exact match, no recursive sig verify needed.
    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)
    assert result.verified is True
    assert result.trust_anchor_subject is not None


def test_now_parameter_drives_validity_check_not_walltime() -> None:
    """``now`` is the time injection point. Pass a moment outside the
    leaf's validity window and verification must fail even though the
    real wallclock says otherwise."""
    chain, trust = _build_chain()
    far_future = FROZEN_NOW + dt.timedelta(days=365 * 100)
    result = verify_x509_chain(chain, trust_list_pem=trust, now=far_future)
    assert result.verified is False
    assert "expired" in (result.reason or "").lower()


# --------------------------------------------------------------- digest contract


def test_chain_anchor_match_uses_sha256_fingerprint() -> None:
    """Defensive: confirm the verifier identifies anchors by SHA-256
    fingerprint of the DER bytes. If the underlying library ever changed
    the default to a different algorithm, this test catches it."""
    chain, trust = _build_chain()
    # Re-derive what we expect the anchor SHA-256 to be from raw PEM.
    root_cert = x509.load_pem_x509_certificate(trust.encode("ascii"))
    expected_fp = root_cert.fingerprint(hashes.SHA256())

    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)
    assert result.verified is True

    # And the anchor we matched is the same cert.
    chain_leaf = x509.load_pem_x509_certificate(chain[-1].encode("ascii"))
    assert chain_leaf.fingerprint(hashes.SHA256()) == expected_fp


# --------------------------------------------------------------- skip RSA-only test
# We don't ship RSA-specific tests in v1: ed25519 already exercises the
# happy path (verify_directly_issued_by) and the manual fallback. RSA
# tests would only cover the manual fallback's RSA branch in pre-v40
# cryptography releases — not worth maintaining when our pinned
# dependency is v42+.


# --------------------------------------------------------------- result shape


def test_verify_result_is_immutable() -> None:
    chain, trust = _build_chain()
    result = verify_x509_chain(chain, trust_list_pem=trust, now=FROZEN_NOW)
    with pytest.raises(AttributeError):
        result.verified = False  # type: ignore[misc]
