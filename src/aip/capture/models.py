"""Modelos de Capture-at-Source (Phase 2).

Un :class:`CaptureCertificate` es un artefacto firmado que vincula un fichero
de evidencia (por su SHA-256) al momento de captura declarado por el operador
y al dispositivo. Extiende la cadena de procedencia HACIA ATRÁS en el tiempo
respecto de lo que ya cubre el sistema: ``Evidence.ingested_at`` describe
cuándo entró al archive; el certificate describe cuándo se capturó.

Diferencia con :class:`aip.attestation.OperatorAttestation`:

- Attestation firma un artefacto JSON ya persistido en el archive.
- CaptureCertificate firma el *hash del bytes raw* de un fichero **antes** de
  que entre al archive — el ingest puede llegar minutos, horas o años después.

Lo que **NO** prueba (mismas limitaciones que ADR-0041):

- Identidad real del operador (sin PKI; ``operator_id`` operator-supplied).
- Momento absoluto (``captured_at`` operator-supplied; sin TSA en V1).
- Que el dispositivo realmente fuera ese (sin attestation de hardware).
- Que el contenido sea veraz — sólo el vínculo bytes-operador-momento.

Sin motores estadísticos. Sin IA. Sin scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

CAPTURE_SCHEMA_VERSION: Final[str] = "1"

SIGNATURE_ALGORITHM: Final[str] = "ed25519-v1"
"""Misma etiqueta cerrada que ADR-0041 y Transparency. Reusamos
infraestructura ed25519 — cero rolling-our-own crypto."""

CERTIFICATE_TYPE: Final[str] = "aip.capture.certificate.v1"
"""Discriminador de tipo. Si llegase a aparecer v2, será una clave distinta —
los lectores deben rechazar tipos desconocidos."""

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
_ED25519_SIG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{128}$")
_ISO_UTC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@dataclass(frozen=True)
class CaptureCertificate:
    """Vincula un fichero de evidencia (por hash) al momento y operador de captura.

    Los campos opcionales (``device_id``, ``location``, ``notes``) son
    ``str | None`` — ``None`` cuando no se declararon. Se incluyen en la
    serialización canónica como ``null`` para que la estructura del payload
    de firma sea estable independientemente de qué optionals haya.
    """

    # ── identificación ────────────────────────────────────────────────
    certificate_type: str
    schema_version: str

    # ── qué se capturó ────────────────────────────────────────────────
    evidence_sha256: str

    # ── contexto operator-supplied ────────────────────────────────────
    operator_id: str
    captured_at: str
    device_id: str | None
    location: str | None
    notes: str | None

    # ── identidad del firmante ────────────────────────────────────────
    public_key_fingerprint: str
    signature: str
    signature_algorithm: str

    # ── self-hash ─────────────────────────────────────────────────────
    certificate_hash: str

    def __post_init__(self) -> None:
        if self.certificate_type != CERTIFICATE_TYPE:
            raise ValueError(
                f"certificate_type must be {CERTIFICATE_TYPE!r}; "
                f"got {self.certificate_type!r}."
            )
        if not _SHA256_HEX_PATTERN.match(self.evidence_sha256):
            raise ValueError("evidence_sha256 must be SHA-256 hex lowercase.")
        if not self.operator_id:
            raise ValueError("operator_id must be non-empty.")
        if not _ISO_UTC_PATTERN.match(self.captured_at):
            raise ValueError(
                "captured_at must be ISO-8601 UTC of form YYYY-MM-DDTHH:MM:SSZ."
            )
        # Optionals: must be either None or non-empty string (no empty string allowed —
        # forces the operator to leave the field truly absent if nothing to say).
        for field_name in ("device_id", "location", "notes"):
            value: str | None = getattr(self, field_name)
            if value is not None and not value:
                raise ValueError(
                    f"{field_name} must be None or non-empty (no empty string)."
                )
        if not _SHA256_HEX_PATTERN.match(self.public_key_fingerprint):
            raise ValueError("public_key_fingerprint must be SHA-256 hex lowercase.")
        if not _ED25519_SIG_PATTERN.match(self.signature):
            raise ValueError("signature must be ed25519 hex of length 128.")
        if self.signature_algorithm != SIGNATURE_ALGORITHM:
            raise ValueError(
                f"signature_algorithm must be {SIGNATURE_ALGORITHM!r}; "
                f"got {self.signature_algorithm!r}."
            )
        if not _SHA256_HEX_PATTERN.match(self.certificate_hash):
            raise ValueError("certificate_hash must be SHA-256 hex lowercase.")
