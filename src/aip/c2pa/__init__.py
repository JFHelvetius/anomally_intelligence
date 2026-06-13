"""C2PA Capture Attestation Layer (ADR-0046).

Verifies C2PA manifests associated with ingested evidence. AIP does NOT
extract the JUMBF box from binary media files in v1 — the operator
extracts the manifest JSON externally (e.g., ``c2patool extract``) and
hands the JSON to AIP. The module verifies:

- Each manifest's binding to the declared evidence SHA-256.
- Each manifest's signature chain against a configurable trust list.
- Cross-manifest linkage (each manifest's ``parent_manifest_label``
  must reference an actual previous manifest in the chain).

What AIP does NOT do:

- Verify the *truth* of the assertions (e.g., "captured at GPS X,Y" —
  AIP confirms the camera signed that assertion, not that the camera
  was actually there).
- Bind the certificate's signer to a human operator. The cert
  identifies the device manufacturer or editing tool, not the person
  using it.
- Reject evidence that lacks a C2PA manifest. C2PA is an *additional
  layer*; its absence is not a failure.
"""

from __future__ import annotations

from aip.c2pa.models import (
    C2PA_REPORT_SCHEMA_VERSION,
    C2PA_REPORT_TYPE,
    C2PAAssertion,
    C2PAManifest,
    C2PAReport,
    C2PASignatureInfo,
)
from aip.c2pa.verifier import (
    C2PA_ATTESTATIONS_DIRNAME,
    DEFAULT_TRUST_LIST_NAME,
    parse_manifest_json,
    persist_report,
    recompute_signatures_with_trust_list,
    verify_manifest_chain,
)

__all__ = [
    "C2PA_ATTESTATIONS_DIRNAME",
    "C2PA_REPORT_SCHEMA_VERSION",
    "C2PA_REPORT_TYPE",
    "DEFAULT_TRUST_LIST_NAME",
    "C2PAAssertion",
    "C2PAManifest",
    "C2PAReport",
    "C2PASignatureInfo",
    "parse_manifest_json",
    "persist_report",
    "recompute_signatures_with_trust_list",
    "verify_manifest_chain",
]
