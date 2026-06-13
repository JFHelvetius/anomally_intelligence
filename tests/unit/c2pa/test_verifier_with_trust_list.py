"""Integration tests for ``verify_manifest_chain`` with a real PEM trust list (ADR-0047).

These tests exercise the full path: parse JSON → recompute signatures
in-process → run structural checks → emit report. The operator-supplied
``chain_verified`` boolean gets explicitly overridden when AIP walks the
chain; tests pin that the override happens AND that the
``verification_mode`` field is set correctly in the persisted report.
"""

from __future__ import annotations

import datetime as dt

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

from aip.c2pa import (
    parse_manifest_json,
    verify_manifest_chain,
)

EVIDENCE_HASH = "a" * 64
FROZEN_NOW = dt.datetime(2026, 6, 12, 12, 0, 0, tzinfo=dt.UTC)


# --------------------------------------------------------------- cert helpers


def _build_cert(
    *, subject_cn: str, issuer_cn: str,
    public_key: Ed25519PrivateKey, signing_key: Ed25519PrivateKey,
    not_before: dt.datetime, not_after: dt.datetime, is_ca: bool,
) -> x509.Certificate:
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
            x509.BasicConstraints(ca=is_ca, path_length=None), critical=True
        )
    )
    return builder.sign(private_key=signing_key, algorithm=None)


def _pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _build_valid_chain_and_trust_list() -> tuple[list[str], str]:
    root_key = Ed25519PrivateKey.generate()
    leaf_key = Ed25519PrivateKey.generate()
    root = _build_cert(
        subject_cn="Test Camera Root",
        issuer_cn="Test Camera Root",
        public_key=root_key,
        signing_key=root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-365),
        not_after=FROZEN_NOW + dt.timedelta(days=365 * 5),
        is_ca=True,
    )
    leaf = _build_cert(
        subject_cn="Test Camera Device",
        issuer_cn="Test Camera Root",
        public_key=leaf_key,
        signing_key=root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=False,
    )
    return [_pem(leaf), _pem(root)], _pem(root)


# --------------------------------------------------------------- fixtures


def _manifest_with_chain(
    *, chain: list[str], operator_says_verified: bool = True,
) -> dict[str, object]:
    """A manifest JSON that includes cert_chain_pem AND a deliberately
    optimistic operator-supplied chain_verified. The whole point of
    ADR-0047 is that AIP can override this when given a trust list."""
    return {
        "label": "camera-001",
        "parent_manifest_label": None,
        "signature_info": {
            "issuer_common_name": "Test Camera Device",
            "issuer_organization": "Test Vendor",
            "cert_serial": "ab:cd:ef",
            "not_before": "2026-05-01T00:00:00Z",
            "not_after": "2027-05-01T00:00:00Z",
            "chain_verified_against": "operator-supplied",
            "chain_verified": operator_says_verified,
            "failure_reason": None,
            "cert_chain_pem": chain,
        },
        "assertions": [
            {"label": "c2pa.hash.data", "data": {"sha256": EVIDENCE_HASH}},
        ],
    }


# --------------------------------------------------------------- mode: in-process verified


def test_with_trust_list_verifies_real_chain_and_marks_in_process() -> None:
    chain, trust = _build_valid_chain_and_trust_list()
    payload = {"manifests": [_manifest_with_chain(chain=chain)]}
    manifests = parse_manifest_json(payload)

    report = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )
    assert report.chain_verified is True
    assert report.failure_reason is None
    assert len(report.manifests) == 1
    sig = report.manifests[0].signature_info
    assert sig.verification_mode == "in-process"
    assert sig.chain_verified is True
    # The trust anchor's CN appears in chain_verified_against.
    assert "Test Camera Root" in sig.chain_verified_against


# --------------------------------------------------------------- mode: AIP overrides operator lie


def test_with_trust_list_overrides_operator_lying_chain_verified() -> None:
    """The threat model: operator says chain_verified=true but supplies
    a cert chain that doesn't actually validate. AIP must catch it."""
    # Build a chain where the leaf is NOT signed by the root (rogue
    # signer) — so the chain LOOKS structurally complete but the
    # signature math fails.
    root_key = Ed25519PrivateKey.generate()
    rogue_key = Ed25519PrivateKey.generate()
    leaf_key = Ed25519PrivateKey.generate()
    root = _build_cert(
        subject_cn="Legit Root",
        issuer_cn="Legit Root",
        public_key=root_key,
        signing_key=root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-365),
        not_after=FROZEN_NOW + dt.timedelta(days=365 * 5),
        is_ca=True,
    )
    rogue_leaf = _build_cert(
        subject_cn="Rogue Device",
        issuer_cn="Legit Root",  # claims this issuer...
        public_key=leaf_key,
        signing_key=rogue_key,   # ...but signed by a different key
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=False,
    )
    chain = [_pem(rogue_leaf), _pem(root)]
    trust = _pem(root)

    payload = {"manifests": [_manifest_with_chain(chain=chain)]}
    manifests = parse_manifest_json(payload)

    report = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )

    # Operator said true; AIP says false because the in-process check
    # caught the bad signature.
    assert report.chain_verified is False
    sig = report.manifests[0].signature_info
    assert sig.verification_mode == "in-process"
    assert sig.chain_verified is False
    assert "signature does not verify" in (sig.failure_reason or "")


def test_with_trust_list_overrides_when_root_not_trusted() -> None:
    """Even if the chain is internally consistent, an untrusted root
    must produce chain_verified=False."""
    chain, _good_trust = _build_valid_chain_and_trust_list()
    # Build a DIFFERENT root for the trust list — the supplied chain's
    # root is not present here.
    other_root_key = Ed25519PrivateKey.generate()
    other_root = _build_cert(
        subject_cn="Other Vendor Root",
        issuer_cn="Other Vendor Root",
        public_key=other_root_key,
        signing_key=other_root_key,
        not_before=FROZEN_NOW + dt.timedelta(days=-30),
        not_after=FROZEN_NOW + dt.timedelta(days=365),
        is_ca=True,
    )

    payload = {"manifests": [_manifest_with_chain(chain=chain)]}
    manifests = parse_manifest_json(payload)
    report = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=_pem(other_root),
        now=FROZEN_NOW,
    )

    assert report.chain_verified is False
    sig = report.manifests[0].signature_info
    assert sig.verification_mode == "in-process"
    assert "not present in the trust list" in (sig.failure_reason or "")


# --------------------------------------------------------------- mode: operator-supplied (no chain)


def test_without_cert_chain_pem_falls_back_to_operator_supplied() -> None:
    """If the operator's manifest JSON omits cert_chain_pem, AIP can't
    walk anything even with a trust list. The report must clearly say
    'operator-supplied' so the receptor knows."""
    payload = {
        "manifests": [{
            "label": "camera-001",
            "parent_manifest_label": None,
            "signature_info": {
                "issuer_common_name": "Camera",
                "issuer_organization": "Vendor",
                "cert_serial": "ab:cd",
                "not_before": "2026-01-01T00:00:00Z",
                "not_after": "2027-01-01T00:00:00Z",
                "chain_verified_against": "external-tooling",
                "chain_verified": True,
                "failure_reason": None,
                # no cert_chain_pem
            },
            "assertions": [
                {"label": "c2pa.hash.data", "data": {"sha256": EVIDENCE_HASH}},
            ],
        }]
    }
    manifests = parse_manifest_json(payload)
    _, trust = _build_valid_chain_and_trust_list()

    report = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )
    sig = report.manifests[0].signature_info
    assert sig.verification_mode == "operator-supplied"
    assert sig.chain_verified is True  # the operator's value, untouched.


# --------------------------------------------------------------- mode: no trust list


def test_without_trust_list_pem_keeps_operator_supplied_verdict() -> None:
    """When no trust list is provided, AIP must NOT walk any chain even
    if cert_chain_pem is in the manifest. The operator-supplied value
    rides through unchanged, with the mode explicitly labelled."""
    chain, _trust = _build_valid_chain_and_trust_list()
    payload = {"manifests": [_manifest_with_chain(chain=chain)]}
    manifests = parse_manifest_json(payload)

    report = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=None,
        now=FROZEN_NOW,
    )
    sig = report.manifests[0].signature_info
    assert sig.verification_mode == "operator-supplied"


# --------------------------------------------------------------- determinism


def test_in_process_verification_is_deterministic_for_same_inputs() -> None:
    """The report hash must not depend on wallclock time when ``now`` is
    pinned — operators running AIP on the same archive at the same
    pinned moment compute the same report_hash."""
    chain, trust = _build_valid_chain_and_trust_list()
    payload = {"manifests": [_manifest_with_chain(chain=chain)]}
    manifests = parse_manifest_json(payload)

    r1 = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )
    r2 = verify_manifest_chain(
        manifests,
        evidence_sha256=EVIDENCE_HASH,
        trust_list_pem=trust,
        now=FROZEN_NOW,
    )
    assert r1.report_hash == r2.report_hash
