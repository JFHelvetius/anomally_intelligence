"""Dataclasses for the C2PA capture attestation layer (ADR-0046).

Mirrors the subset of C2PA manifest structure that AIP cares about: who
signed each manifest, which assertions it carries, and how the chain
links from camera → editor → ... → final asset. The full C2PA spec is
much richer (thumbnail data, ingredient manifests for compositions,
specific assertion schemas per claim type); AIP intentionally extracts
only the structural integrity layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from aip.core.hashing import JsonValue

C2PA_REPORT_SCHEMA_VERSION: Final[str] = "1"
C2PA_REPORT_TYPE: Final[str] = "aip.capture.c2pa.attestation.v1"


@dataclass(frozen=True, slots=True)
class C2PAAssertion:
    """One claim inside a C2PA manifest.

    Common labels: ``c2pa.hash.data`` (binds the manifest to file bytes),
    ``c2pa.actions`` (list of edits applied), ``stds.exif`` (camera EXIF),
    ``c2pa.training-mining`` (AI-training opt-out / opt-in), and many
    third-party assertions starting with the publishing org's domain.
    """

    label: str
    data: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class C2PASignatureInfo:
    """Who signed this manifest, per the embedded X.509 certificate.

    ``issuer_common_name`` is what most cameras put in their cert CN
    (e.g., 'Sony Alpha 1 Camera'). ``issuer_organization`` carries the
    manufacturer / publisher (e.g., 'Sony Imaging Products & Solutions
    Inc.'). ``chain_verified_against`` records which trust list AIP
    used when checking, so the report stays auditable.

    ``verification_mode`` is load-bearing for ADR-0047 honesty:

    - ``"operator-supplied"``: ``chain_verified`` came from the
      manifest JSON as-is. AIP did not check it.
    - ``"in-process"``: AIP walked the X.509 chain locally and computed
      ``chain_verified`` itself. ``cert_chain_pem`` was provided AND a
      trust list was passed to ``verify_manifest_chain``.
    """

    issuer_common_name: str
    issuer_organization: str | None
    cert_serial: str
    not_before: str        # ISO-8601 UTC
    not_after: str         # ISO-8601 UTC
    chain_verified_against: str
    chain_verified: bool
    failure_reason: str | None = None
    cert_chain_pem: tuple[str, ...] = ()
    verification_mode: str = "operator-supplied"


@dataclass(frozen=True, slots=True)
class C2PAManifest:
    """One link of the C2PA manifest chain.

    A camera generates the first manifest (``parent_manifest_label =
    None``). Each subsequent editor adds a manifest whose
    ``parent_manifest_label`` points at the previous one, forming a DAG
    that the verifier walks linearly for v1.
    """

    label: str
    signature_info: C2PASignatureInfo
    assertions: tuple[C2PAAssertion, ...]
    parent_manifest_label: str | None


@dataclass(frozen=True, slots=True)
class C2PAReport:
    """Full result of verifying a C2PA chain for one evidence.

    ``chain_verified`` is True only if EVERY manifest's signature
    verified AND the chain forms a contiguous DAG AND the final
    manifest's ``c2pa.hash.data`` matches the declared evidence SHA-256.
    """

    report_type: str
    schema_version: str
    evidence_sha256: str
    verified_at: str       # ISO-8601 UTC
    trust_list_name: str
    chain_verified: bool
    failure_reason: str | None
    manifests: tuple[C2PAManifest, ...]
    report_hash: str       # SHA-256 of JCS(report minus report_hash)


__all__ = [
    "C2PA_REPORT_SCHEMA_VERSION",
    "C2PA_REPORT_TYPE",
    "C2PAAssertion",
    "C2PAManifest",
    "C2PAReport",
    "C2PASignatureInfo",
]
