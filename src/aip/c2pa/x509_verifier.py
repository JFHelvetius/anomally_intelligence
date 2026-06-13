"""In-process X.509 chain verification for C2PA (ADR-0047).

Walks a leaf→root certificate chain and checks every link:

1. Each child cert's signature verifies against the parent's public key.
2. The current time is within each cert's validity window.
3. The root cert is one of the trust anchors supplied via PEM bundle.

What this module does NOT do:

- CRL / OCSP revocation checks (intentionally out of scope; requires
  network at verification time, violates the local-first model).
- Hostname / SAN matching (irrelevant for C2PA device certs).
- Full RFC 5280 PKIX path validation (basic constraints + key usage are
  checked; the more elaborate constraints are not enforced).

The trust list is **operator-supplied as PEM** — AIP ships no default
trust list. ADR-0047 §"Alternativas D" explains why.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

from aip.errors import AIPError

_PEM_BEGIN: Final[str] = "-----BEGIN CERTIFICATE-----"
_PEM_END: Final[str] = "-----END CERTIFICATE-----"


@dataclass(frozen=True, slots=True)
class X509VerifyResult:
    """Result of verifying ONE X.509 chain against a trust list.

    ``used_chain`` distinguishes "AIP walked the chain" from "AIP didn't
    have inputs to do so". A False here with verified=False does NOT
    mean the cert chain is invalid — it means AIP couldn't check.
    """

    verified: bool
    used_chain: bool
    reason: str | None = None
    trust_anchor_subject: str | None = None


def verify_x509_chain(  # noqa: PLR0911, PLR0912 — every branch returns a specific reason
    cert_chain_pem: list[str],
    *,
    trust_list_pem: str,
    now: dt.datetime | None = None,
) -> X509VerifyResult:
    """Verify a leaf→root certificate chain against a PEM trust list.

    ``cert_chain_pem`` must list certs in **leaf-first** order (the cert
    that signed the C2PA manifest first, then each issuer up to and
    including the root). Order matters — AIP does not sort the chain.

    ``trust_list_pem`` is one or more root CA certs concatenated as PEM.
    """
    if not cert_chain_pem:
        return X509VerifyResult(
            verified=False,
            used_chain=False,
            reason="empty certificate chain supplied.",
        )

    moment = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)

    # Parse the chain.
    chain: list[x509.Certificate] = []
    for i, pem in enumerate(cert_chain_pem):
        if not isinstance(pem, str) or _PEM_BEGIN not in pem:
            return X509VerifyResult(
                verified=False,
                used_chain=False,
                reason=f"cert[{i}] is not a PEM-encoded certificate.",
            )
        try:
            cert = x509.load_pem_x509_certificate(pem.encode("ascii"))
        except (ValueError, TypeError) as exc:
            return X509VerifyResult(
                verified=False,
                used_chain=False,
                reason=f"cert[{i}] failed to parse: {exc}",
            )
        chain.append(cert)

    # Parse the trust list.
    try:
        trust_anchors = _load_pem_bundle(trust_list_pem)
    except AIPError as exc:
        return X509VerifyResult(
            verified=False,
            used_chain=False,
            reason=str(exc),
        )
    if not trust_anchors:
        return X509VerifyResult(
            verified=False,
            used_chain=False,
            reason="trust list contains no certificates.",
        )

    # Validity windows — every cert in the chain must be currently valid.
    for i, cert in enumerate(chain):
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
        if moment < not_before:
            return X509VerifyResult(
                verified=False,
                used_chain=True,
                reason=(
                    f"cert[{i}] is not yet valid (not_before={not_before.isoformat()})."
                ),
            )
        if moment > not_after:
            return X509VerifyResult(
                verified=False,
                used_chain=True,
                reason=(
                    f"cert[{i}] has expired (not_after={not_after.isoformat()})."
                ),
            )

    # Signature linkage — each child's signature verifies against parent's
    # public key. The last cert in the chain (chain[-1]) is treated as
    # the self-signed root, OR signed by a trust anchor.
    for i in range(len(chain) - 1):
        child = chain[i]
        parent = chain[i + 1]
        ok, reason = _verify_signed_by(child, parent)
        if not ok:
            return X509VerifyResult(
                verified=False,
                used_chain=True,
                reason=f"cert[{i}] signature does not verify against cert[{i + 1}]: {reason}",
            )

    # Trust anchor match — the supplied chain's root cert must match a
    # cert in the trust list by SubjectKeyIdentifier OR by full DER
    # bytes equality.
    supplied_root = chain[-1]
    matching_anchor = _find_matching_anchor(supplied_root, trust_anchors)
    if matching_anchor is None:
        return X509VerifyResult(
            verified=False,
            used_chain=True,
            reason=(
                "chain's root certificate is not present in the trust list "
                f"(subject={supplied_root.subject.rfc4514_string()})."
            ),
        )

    # If the supplied root differs from the trust anchor (which can happen
    # if both share the same SubjectKeyIdentifier but the supplied chain
    # carries an older or replicated copy), additionally verify the supplied
    # root's signature against the trust anchor. For self-signed roots this
    # is a no-op.
    if supplied_root.fingerprint(hashes.SHA256()) != matching_anchor.fingerprint(
        hashes.SHA256()
    ):
        ok, reason = _verify_signed_by(supplied_root, matching_anchor)
        if not ok:
            return X509VerifyResult(
                verified=False,
                used_chain=True,
                reason=(
                    "supplied root cert does not chain to its matching trust "
                    f"anchor: {reason}"
                ),
            )

    anchor_cn = _common_name(matching_anchor) or matching_anchor.subject.rfc4514_string()
    return X509VerifyResult(
        verified=True,
        used_chain=True,
        reason=None,
        trust_anchor_subject=anchor_cn,
    )


# --------------------------------------------------------------- helpers


def _load_pem_bundle(pem_bundle: str) -> list[x509.Certificate]:
    """Parse one or more PEM certs concatenated in a single string."""
    blocks: list[str] = []
    current: list[str] = []
    inside = False
    for raw_line in pem_bundle.splitlines():
        line = raw_line.rstrip()
        if line == _PEM_BEGIN:
            inside = True
            current = [line]
        elif line == _PEM_END:
            if not inside:
                raise AIPError("trust list PEM contains END without BEGIN.")
            current.append(line)
            blocks.append("\n".join(current))
            current = []
            inside = False
        elif inside:
            current.append(line)
    if inside:
        raise AIPError("trust list PEM contains BEGIN without END.")
    out: list[x509.Certificate] = []
    for i, block in enumerate(blocks):
        try:
            out.append(x509.load_pem_x509_certificate(block.encode("ascii")))
        except (ValueError, TypeError) as exc:
            raise AIPError(
                f"trust list cert[{i}] failed to parse: {exc}"
            ) from exc
    return out


def _verify_signed_by(
    child: x509.Certificate, parent: x509.Certificate
) -> tuple[bool, str | None]:
    """Verify that ``child`` is signed by ``parent``'s key.

    Uses ``cryptography``'s ``verify_directly_issued_by`` when available
    (since v40), which handles all algorithm cases correctly.
    """
    # Modern API.
    if hasattr(child, "verify_directly_issued_by"):
        try:
            child.verify_directly_issued_by(parent)
            return True, None
        except (InvalidSignature, ValueError, TypeError) as exc:
            return False, str(exc)
    # Fallback for older cryptography. We dispatch on the parent key
    # type and verify the TBS bytes.
    return _verify_signed_by_manual(child, parent)


def _verify_signed_by_manual(
    child: x509.Certificate, parent: x509.Certificate
) -> tuple[bool, str | None]:
    pub = parent.public_key()
    sig = child.signature
    tbs = child.tbs_certificate_bytes
    try:
        if isinstance(pub, ed25519.Ed25519PublicKey | ed448.Ed448PublicKey):
            pub.verify(sig, tbs)
        elif isinstance(pub, rsa.RSAPublicKey):
            algo = child.signature_hash_algorithm
            if algo is None:
                return False, "RSA cert has no signature hash algorithm."
            from cryptography.hazmat.primitives.asymmetric import padding  # noqa: PLC0415
            pub.verify(sig, tbs, padding.PKCS1v15(), algo)
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            algo = child.signature_hash_algorithm
            if algo is None:
                return False, "ECDSA cert has no signature hash algorithm."
            pub.verify(sig, tbs, ec.ECDSA(algo))
        else:
            return False, f"unsupported parent public key type {type(pub).__name__}."
    except InvalidSignature:
        return False, "signature does not match parent's public key."
    except (ValueError, TypeError) as exc:
        return False, str(exc)
    return True, None


def _find_matching_anchor(
    supplied_root: x509.Certificate, anchors: list[x509.Certificate]
) -> x509.Certificate | None:
    """Find the trust anchor that matches the supplied root cert.

    Matches first by full DER fingerprint (strict identity), then by the
    SubjectKeyIdentifier extension (if both certs have it). Returns
    ``None`` if no anchor matches.
    """
    supplied_fp = supplied_root.fingerprint(hashes.SHA256())
    for anchor in anchors:
        if anchor.fingerprint(hashes.SHA256()) == supplied_fp:
            return anchor

    supplied_ski = _subject_key_identifier(supplied_root)
    if supplied_ski is not None:
        for anchor in anchors:
            anchor_ski = _subject_key_identifier(anchor)
            if anchor_ski is not None and anchor_ski == supplied_ski:
                return anchor

    # Fallback: match by subject DN + public key bytes.
    for anchor in anchors:
        if (
            anchor.subject == supplied_root.subject
            and anchor.public_key().public_bytes(  # type: ignore[attr-defined]
                encoding=x509.serialization.Encoding.DER,  # type: ignore[attr-defined]
                format=x509.serialization.PublicFormat.SubjectPublicKeyInfo,  # type: ignore[attr-defined]
            )
            == supplied_root.public_key().public_bytes(  # type: ignore[attr-defined]
                encoding=x509.serialization.Encoding.DER,  # type: ignore[attr-defined]
                format=x509.serialization.PublicFormat.SubjectPublicKeyInfo,  # type: ignore[attr-defined]
            )
        ):
            return anchor
    return None


def _subject_key_identifier(cert: x509.Certificate) -> bytes | None:
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    except x509.ExtensionNotFound:
        return None
    return ext.value.key_identifier


def _common_name(cert: x509.Certificate) -> str | None:
    cns = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    if not cns:
        return None
    value = cns[0].value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return str(value)


__all__ = [
    "X509VerifyResult",
    "verify_x509_chain",
]
