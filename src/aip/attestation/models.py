"""Modelos del Operator Attestation Engine (ADR-0041 §modelo)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

ATTESTATION_SCHEMA_VERSION: Final[str] = "1"

SIGNATURE_ALGORITHM: Final[str] = "ed25519-v1"
"""Etiqueta cerrada del algoritmo. V1 sólo soporta ed25519. Cualquier
otro valor requiere ADR de enmienda."""

ALLOWED_ARTIFACT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "workspace",
        "timeline",
        "snapshot",
        "justification",
        "context_bundle",
        "manifest",
    }
)
"""Taxonomía cerrada de artefactos firmables en V1."""

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-f0-9]{64}$"
)
_ED25519_SIG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-f0-9]{128}$"
)
_ISO_UTC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@dataclass(frozen=True)
class OperatorAttestation:
    """Atestación inmutable que vincula un artefacto a una clave ed25519.

    **No** prueba identidad real del firmante (``signer_id`` es
    operator-supplied; PKI fuera de scope V1). **No** prueba momento
    absoluto (``signed_at`` es operator-supplied; sin TSA). **No**
    prueba veracidad del contenido. Sólo el vínculo clave-artefacto.
    """

    artifact_kind: str
    artifact_hash: str
    signer_id: str
    public_key_fingerprint: str
    signature: str
    signature_algorithm: str
    signed_at: str
    attestation_hash: str
    schema_version: str = ATTESTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.artifact_kind not in ALLOWED_ARTIFACT_KINDS:
            raise ValueError(
                f"invalid artifact_kind {self.artifact_kind!r}; "
                f"must be one of {sorted(ALLOWED_ARTIFACT_KINDS)}."
            )
        if not _SHA256_HEX_PATTERN.match(self.artifact_hash):
            raise ValueError(
                "artifact_hash must be SHA-256 hex lowercase."
            )
        if not self.signer_id:
            raise ValueError("signer_id must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.public_key_fingerprint):
            raise ValueError(
                "public_key_fingerprint must be SHA-256 hex lowercase."
            )
        if not _ED25519_SIG_PATTERN.match(self.signature):
            raise ValueError(
                "signature must be ed25519 hex of length 128."
            )
        if self.signature_algorithm != SIGNATURE_ALGORITHM:
            raise ValueError(
                f"signature_algorithm must be {SIGNATURE_ALGORITHM!r}; "
                f"got {self.signature_algorithm!r}."
            )
        if not _ISO_UTC_PATTERN.match(self.signed_at):
            raise ValueError(
                "signed_at must be ISO-8601 UTC of form "
                "YYYY-MM-DDTHH:MM:SSZ."
            )
        if not _SHA256_HEX_PATTERN.match(self.attestation_hash):
            raise ValueError(
                "attestation_hash must be SHA-256 hex lowercase."
            )
