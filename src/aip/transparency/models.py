"""Modelos del Transparency Log (Phase 1A).

Una :class:`TransparencyManifest` es una atestación firmada del estado completo
de un archive AIP en un instante concreto. Forma una cadena append-only via
``previous_manifest_hash`` — manipular un manifest viejo rompe la cadena de
todos los posteriores.

Diferencia con :class:`aip.attestation.OperatorAttestation`:

- Attestation firma un *artefacto* concreto (workspace, justification, etc.).
- TransparencyManifest firma el *estado global* del archive (audit chain head,
  conteos por dominio, hash del manifest interno).

Tres invariantes load-bearing:

1. ``sequence`` monotónico sin huecos: 0, 1, 2, … Manifest N+1 referencia a N.
2. ``previous_manifest_hash`` encadena: cambiar manifest N invalida N+1…∞.
3. ``audit_chain_head_hash`` ata el manifest al estado completo del audit log;
   si el operador altera una entrada vieja, el head cambia y los manifests
   posteriores ya publicados la delatan.

**No** prueba momento absoluto (``signed_at`` es operator-supplied; sin TSA en V1).
**No** prueba identidad real (``operator_id`` sin PKI; igual que ADR-0041).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

TRANSPARENCY_SCHEMA_VERSION: Final[str] = "1"

SIGNATURE_ALGORITHM: Final[str] = "ed25519-v1"
"""Misma etiqueta cerrada que ADR-0041. Reutilizamos la infraestructura
ed25519 del Operator Attestation Engine."""

MANIFEST_TYPE: Final[str] = "aip.transparency.manifest.v1"
"""Discriminador de tipo. Si llegase a aparecer un v2, será una clave
distinta — los lectores deben rechazar tipos desconocidos."""

ZERO_HASH: Final[str] = "0" * 64
"""Sentinela para ``previous_manifest_hash`` del manifest inicial (sequence=0).
Misma convención que el bootstrap del audit log (ADR-0019)."""

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
_ED25519_SIG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{128}$")
_ISO_UTC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@dataclass(frozen=True)
class TransparencyManifest:
    """Atestación firmada del estado de un archive AIP.

    El ``manifest_hash`` se computa al final, sobre los campos canónicos
    incluyendo la firma — esto permite que ``previous_manifest_hash`` en
    el manifest N+1 ate inequívocamente al manifest N firmado completo.
    """

    # ── identidad ─────────────────────────────────────────────────────
    sequence: int
    signed_at: str
    manifest_type: str

    # ── operador ──────────────────────────────────────────────────────
    operator_id: str
    public_key_fingerprint: str

    # ── compromiso de estado ──────────────────────────────────────────
    archive_manifest_hash: str
    audit_chain_head_hash: str
    audit_entry_count: int
    evidence_count: int
    attestation_count: int
    workspace_count: int
    timeline_count: int
    snapshot_count: int
    justification_count: int

    # ── cadena ────────────────────────────────────────────────────────
    previous_manifest_hash: str

    # ── firma ─────────────────────────────────────────────────────────
    signature: str
    signature_algorithm: str

    # ── self-hash ─────────────────────────────────────────────────────
    manifest_hash: str

    # ── schema ────────────────────────────────────────────────────────
    schema_version: str = TRANSPARENCY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError(f"sequence must be >= 0, got {self.sequence}.")
        if not _ISO_UTC_PATTERN.match(self.signed_at):
            raise ValueError(
                "signed_at must be ISO-8601 UTC of form YYYY-MM-DDTHH:MM:SSZ."
            )
        if self.manifest_type != MANIFEST_TYPE:
            raise ValueError(
                f"manifest_type must be {MANIFEST_TYPE!r}; got {self.manifest_type!r}."
            )
        if not self.operator_id:
            raise ValueError("operator_id must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.public_key_fingerprint):
            raise ValueError("public_key_fingerprint must be SHA-256 hex lowercase.")
        for field_name in (
            "archive_manifest_hash",
            "audit_chain_head_hash",
            "previous_manifest_hash",
            "manifest_hash",
        ):
            value: str = getattr(self, field_name)
            if not _SHA256_HEX_PATTERN.match(value):
                raise ValueError(
                    f"{field_name} must be SHA-256 hex lowercase, got {value!r}."
                )
        for field_name in (
            "audit_entry_count",
            "evidence_count",
            "attestation_count",
            "workspace_count",
            "timeline_count",
            "snapshot_count",
            "justification_count",
        ):
            count: int = getattr(self, field_name)
            if count < 0:
                raise ValueError(f"{field_name} must be >= 0, got {count}.")
        if not _ED25519_SIG_PATTERN.match(self.signature):
            raise ValueError("signature must be ed25519 hex of length 128.")
        if self.signature_algorithm != SIGNATURE_ALGORITHM:
            raise ValueError(
                f"signature_algorithm must be {SIGNATURE_ALGORITHM!r}; "
                f"got {self.signature_algorithm!r}."
            )
        if self.sequence == 0 and self.previous_manifest_hash != ZERO_HASH:
            raise ValueError(
                "sequence=0 (bootstrap manifest) must have previous_manifest_hash "
                f"= {ZERO_HASH!r} (all zeros)."
            )
