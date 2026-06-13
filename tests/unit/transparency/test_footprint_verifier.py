"""Tests for ``aip.transparency.footprint_verifier`` (ADR-0045).

The verifier turns the manual cross-check from ADR-0043 into an automated
machine check. The tests must pin three properties that are load-bearing
for the security story:

1. **HTTPS-only.** ``http://`` URIs are refused even before fetching.
2. **Honest verdicts.** Unsupported kinds, unreachable references, and
   wrong-format payloads each get their own status — never silently
   collapsed into a single "ok".
3. **No mutation of trust.** A verified result includes the *fetched*
   fingerprint so the UI can show "AIP fetched X" without claiming
   "operator IS Y".

All network I/O is mocked; no test reaches the public internet.
"""

from __future__ import annotations

import contextlib
import io
import urllib.error
from collections.abc import Generator
from typing import Any
from unittest import mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aip.attestation.signer import compute_public_key_fingerprint
from aip.errors import AIPError
from aip.transparency import footprint_verifier
from aip.transparency.footprint_verifier import (
    SUPPORTED_KINDS,
    ReferenceVerifyResult,
    verify_declaration,
    verify_reference,
)

# --------------------------------------------------------------- helpers


def _make_ed25519_keypair() -> tuple[Ed25519PrivateKey, str, bytes]:
    """Return (private, fingerprint_hex, pem_bytes) for a fresh ed25519 key."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fp = compute_public_key_fingerprint(pub)
    pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, fp, pem


def _make_ssh_ed25519_line(priv: Ed25519PrivateKey, comment: str = "test-key") -> str:
    """Serialise the public part as the OpenSSH single-line format."""
    pub = priv.public_key()
    ssh_bytes = pub.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return f"{ssh_bytes.decode('ascii')} {comment}"


def _fake_response(body: bytes) -> contextlib.AbstractContextManager[Any]:
    """Mimic ``urlopen``'s context manager API; .read(N) returns body[:N]."""

    @contextlib.contextmanager
    def cm() -> Generator[Any]:
        fake = mock.Mock()
        fake.read.side_effect = lambda n=None: body[:n] if n is not None else body
        yield fake

    return cm()


def _make_urlopen(responses: dict[str, bytes | Exception]):
    """Build a fake ``urlopen`` that dispatches on URL."""

    def fake_urlopen(req: Any, timeout: int) -> Any:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        match = responses.get(url)
        if match is None:
            raise AssertionError(f"unexpected URL in test: {url}")
        if isinstance(match, Exception):
            raise match
        return _fake_response(match)

    return fake_urlopen


# --------------------------------------------------------------- input validation


def test_verify_reference_rejects_empty_kind() -> None:
    with pytest.raises(AIPError, match="kind must be non-empty"):
        verify_reference(kind="", uri="https://x", declared_fingerprint="a" * 64)


def test_verify_reference_rejects_empty_uri() -> None:
    with pytest.raises(AIPError, match="uri must be non-empty"):
        verify_reference(kind="https_pem", uri="", declared_fingerprint="a" * 64)


def test_verify_reference_rejects_empty_fingerprint() -> None:
    with pytest.raises(AIPError, match="declared_fingerprint must be non-empty"):
        verify_reference(kind="https_pem", uri="https://x", declared_fingerprint="")


# --------------------------------------------------------------- unsupported kinds


def test_unknown_kind_returns_unsupported_without_fetching() -> None:
    """A kind outside the closed set must NOT trigger a network fetch. The
    status is informational and the manual cross-check expectation
    surfaces in ``reason``."""
    # No mock installed — if the implementation tried to fetch, urllib
    # would raise because there's no network in tests.
    result = verify_reference(
        kind="dns_txt",
        uri="_aip-key.example.com",
        declared_fingerprint="a" * 64,
    )
    assert result.status == "unsupported"
    assert result.fetched_fingerprint is None
    assert "manually" in (result.reason or "").lower()


# --------------------------------------------------------------- http guardrails


def test_http_scheme_is_refused_before_fetching() -> None:
    """HTTPS-only is non-negotiable: a degraded http:// URI must not be
    silently followed."""
    result = verify_reference(
        kind="https_pem",
        uri="http://example.com/key.pem",
        declared_fingerprint="a" * 64,
    )
    assert result.status == "unreachable"
    assert "non-HTTPS" in (result.reason or "")


def test_network_error_is_packaged_as_unreachable() -> None:
    fake = _make_urlopen(
        {"https://example.com/k.pem": urllib.error.URLError("dns failure")}
    )
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint="a" * 64,
        )
    assert result.status == "unreachable"
    assert "network error" in (result.reason or "")


def test_404_is_packaged_as_unreachable() -> None:
    fake = _make_urlopen(
        {
            "https://example.com/k.pem": urllib.error.HTTPError(
                url="https://example.com/k.pem",
                code=404,
                msg="Not Found",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(b""),
            )
        }
    )
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint="a" * 64,
        )
    assert result.status == "unreachable"
    assert "404" in (result.reason or "")


# --------------------------------------------------------------- https_pem


def test_https_pem_verifies_matching_fingerprint() -> None:
    _, fp, pem = _make_ed25519_keypair()
    fake = _make_urlopen({"https://example.com/k.pem": pem})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint=fp,
        )
    assert result.status == "verified"
    assert result.fetched_fingerprint == fp
    assert result.reason is None


def test_https_pem_reports_mismatch_with_specific_reason() -> None:
    """A mismatch must report BOTH fingerprints so the operator can see
    which is wrong — declared, or what's actually published."""
    _, fp_a, pem_a = _make_ed25519_keypair()
    _, fp_b, _pem_b = _make_ed25519_keypair()
    assert fp_a != fp_b
    fake = _make_urlopen({"https://example.com/k.pem": pem_a})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint=fp_b,
        )
    assert result.status == "mismatch"
    assert result.fetched_fingerprint == fp_a
    assert result.declared_fingerprint == fp_b


def test_https_pem_rejects_non_ed25519_key() -> None:
    """v1 only supports ed25519. If the URL serves an RSA key, the verdict
    is mismatch (not verified) so the operator catches their key-algo
    mismatch instead of getting a false green."""
    from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415

    rsa_pub = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    rsa_pem = rsa_pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fake = _make_urlopen({"https://example.com/k.pem": rsa_pem})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint="a" * 64,
        )
    assert result.status == "mismatch"
    assert "not ed25519" in (result.reason or "").lower()


def test_https_pem_rejects_garbage_payload() -> None:
    fake = _make_urlopen({"https://example.com/k.pem": b"not a PEM at all"})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="https_pem",
            uri="https://example.com/k.pem",
            declared_fingerprint="a" * 64,
        )
    assert result.status == "mismatch"
    assert "could not parse PEM" in (result.reason or "")


# --------------------------------------------------------------- github_user_keys


def test_github_user_keys_verifies_when_declared_key_is_among_published() -> None:
    """GitHub publishes ALL of a user's SSH keys, one per line. The verifier
    must find the declared one among them, ignoring any others (RSA,
    ECDSA, other ed25519). Otherwise rotating keys would break the
    verification."""
    _, fp_declared, _ = _make_ed25519_keypair()
    priv_declared = Ed25519PrivateKey.generate()
    # Recompute the fingerprint to match the actual key we're about to publish.
    fp_declared = compute_public_key_fingerprint(priv_declared.public_key())

    priv_other = Ed25519PrivateKey.generate()
    body = (
        _make_ssh_ed25519_line(priv_other, "other") + "\n"
        + _make_ssh_ed25519_line(priv_declared, "primary") + "\n"
    ).encode("ascii")

    fake = _make_urlopen({"https://github.com/x.keys": body})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="github_user_keys",
            uri="https://github.com/x.keys",
            declared_fingerprint=fp_declared,
        )
    assert result.status == "verified"
    assert result.fetched_fingerprint == fp_declared


def test_github_user_keys_reports_mismatch_when_declared_key_is_absent() -> None:
    priv_other = Ed25519PrivateKey.generate()
    body = (_make_ssh_ed25519_line(priv_other) + "\n").encode("ascii")
    _, fp_declared, _ = _make_ed25519_keypair()

    fake = _make_urlopen({"https://github.com/x.keys": body})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="github_user_keys",
            uri="https://github.com/x.keys",
            declared_fingerprint=fp_declared,
        )
    assert result.status == "mismatch"
    # The actual fingerprint published is shown for debugging.
    assert result.fetched_fingerprint is not None
    assert result.fetched_fingerprint != fp_declared


def test_github_user_keys_with_only_rsa_keys_is_mismatch_not_verified() -> None:
    """If the user publishes only RSA on GitHub but declares an ed25519
    fingerprint, the verifier returns mismatch with a clear reason —
    not 'verified' just because the line parsed."""
    rsa_line = (
        "ssh-rsa "
        "AAAAB3NzaC1yc2EAAAADAQABAAAAgQDEd1234567890example "
        "rsa-only-user"
    )
    fake = _make_urlopen({"https://github.com/x.keys": rsa_line.encode("ascii")})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="github_user_keys",
            uri="https://github.com/x.keys",
            declared_fingerprint="a" * 64,
        )
    assert result.status == "mismatch"
    assert "no ed25519 key found" in (result.reason or "").lower()


def test_github_user_keys_ignores_comments_and_blank_lines() -> None:
    priv = Ed25519PrivateKey.generate()
    fp = compute_public_key_fingerprint(priv.public_key())
    body = (
        "# header comment\n"
        "\n"
        f"{_make_ssh_ed25519_line(priv)}\n"
        "\n"
    ).encode("ascii")

    fake = _make_urlopen({"https://github.com/x.keys": body})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        result = verify_reference(
            kind="github_user_keys",
            uri="https://github.com/x.keys",
            declared_fingerprint=fp,
        )
    assert result.status == "verified"


# --------------------------------------------------------------- verify_declaration


def _build_declaration(fp: str, refs: list[dict[str, str]]) -> dict[str, object]:
    return {
        "declaration_type": "aip.transparency.key-declaration.v1",
        "schema_version": "1",
        "operator": {
            "operator_id": "op-x",
            "public_key_fingerprint": fp,
            "external_references": refs,
        },
        "witnesses": [],
    }


def test_verify_declaration_rolls_up_per_reference_results() -> None:
    _, fp, pem = _make_ed25519_keypair()
    decl = _build_declaration(
        fp,
        [
            {"kind": "https_pem", "uri": "https://a.example/k.pem"},
            {"kind": "dns_txt", "uri": "_aip-key.example.com"},  # unsupported
        ],
    )
    fake = _make_urlopen({"https://a.example/k.pem": pem})
    with mock.patch.object(footprint_verifier.urllib.request, "urlopen", fake):
        report = verify_declaration(decl)

    assert report.operator_id == "op-x"
    assert report.declared_fingerprint == fp
    assert len(report.references) == 2
    assert report.verified_count == 1
    assert report.mismatch_count == 0
    assert report.reachable_count == 1
    assert report.supported_count == 1
    statuses = {r.status for r in report.references}
    assert statuses == {"verified", "unsupported"}


def test_verify_declaration_rejects_missing_operator() -> None:
    with pytest.raises(AIPError, match="no 'operator' object"):
        verify_declaration({"declaration_type": "x"})


def test_verify_declaration_rejects_invalid_fingerprint() -> None:
    decl = _build_declaration("not-a-real-fingerprint", [])
    with pytest.raises(AIPError, match="public_key_fingerprint"):
        verify_declaration(decl)


# --------------------------------------------------------------- contract


def test_supported_kinds_is_immutable_set() -> None:
    """The set must be frozen — accidental mutation by callers must fail
    at import time. ADR-0045 declares the vocabulary closed for v1."""
    assert isinstance(SUPPORTED_KINDS, frozenset)
    with pytest.raises(AttributeError):
        SUPPORTED_KINDS.add("anything")  # type: ignore[attr-defined]


def test_reference_verify_result_is_immutable() -> None:
    r = ReferenceVerifyResult(
        kind="https_pem",
        uri="https://example.com/k.pem",
        status="verified",
        fetched_fingerprint="a" * 64,
        declared_fingerprint="a" * 64,
    )
    with pytest.raises(AttributeError):
        r.status = "mismatch"  # type: ignore[misc]
