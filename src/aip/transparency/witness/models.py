"""Modelos de Witness Attestation (Door #3 — cross-operator multi-firma).

Un :class:`WitnessAttestation` es una firma ed25519 emitida por un operador
**distinto** del que publicó un :class:`TransparencyManifest`, atestiguando
que vio ese estado en ese momento. La acumulación de witnesses convierte el
trust model de "confiar en el operador A" a "al menos uno del grupo de
witnesses + A es honesto".

Diferencia con :class:`aip.transparency.TransparencyManifest`:

- Manifest firma el *estado* del archive (cabeza de audit chain, conteos).
  Lo emite el dueño del archive.
- WitnessAttestation firma el *hash de un manifest concreto* publicado por
  otro operador. La emite un tercero después de descargar el manifest.

Lo que **NO** prueba (consistente con ADR-0041):

- Identidad real del witness (sin PKI; ``witness_operator_id`` operator-supplied).
- Momento absoluto de la atestación (``witnessed_at`` operator-supplied; sin TSA).
- Que el witness sea independiente del firmante original (depende del operador
  externo verificar el grafo de relaciones, no del sistema).

Lo que SÍ prueba:

- El tenedor de la clave privada *witness_public_key_fingerprint* vio y avaló
  el manifest cuyo hash es *target_manifest_hash*.
- Si N witnesses independientes co-firman el mismo manifest, falsificar la
  cadena requiere coaccionar a A + a N witnesses simultáneamente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

WITNESS_SCHEMA_VERSION: Final[str] = "1"

SIGNATURE_ALGORITHM: Final[str] = "ed25519-v1"
"""Reuso del mismo algoritmo cerrado que ADR-0041 / Transparency / Capture."""

ATTESTATION_TYPE: Final[str] = "aip.transparency.witness.v1"
"""Discriminador de tipo. v2 sería una clave distinta — los lectores deben
rechazar tipos desconocidos."""

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
_ED25519_SIG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{128}$")
_ISO_UTC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@dataclass(frozen=True)
class WitnessAttestation:
    """Atestación firmada de un witness sobre un :class:`TransparencyManifest`.

    Reglas de inclusión de campos:

    - ``target_manifest_hash`` ata la atestación al manifest exacto. Mover un
      byte en el manifest invalida la firma porque cambia el hash.
    - ``target_manifest_sequence`` permite indexar witnesses por manifest sin
      tener que reabrir cada uno para mirar el hash. Redundante con respecto
      al hash, pero load-bearing para UX/storage.
    - ``target_operator_id`` es para legibilidad humana. No load-bearing —
      el hash ya identifica el manifest unívocamente.
    """

    # ── identificación ────────────────────────────────────────────────
    attestation_type: str
    schema_version: str

    # ── quién atestigua ───────────────────────────────────────────────
    witness_operator_id: str
    witness_public_key_fingerprint: str

    # ── qué se atestigua ──────────────────────────────────────────────
    target_manifest_hash: str
    target_manifest_sequence: int
    target_operator_id: str

    # ── cuándo y por qué ──────────────────────────────────────────────
    witnessed_at: str
    statement: str | None

    # ── firma ─────────────────────────────────────────────────────────
    signature: str
    signature_algorithm: str

    # ── self-hash ─────────────────────────────────────────────────────
    attestation_hash: str

    def __post_init__(self) -> None:
        if self.attestation_type != ATTESTATION_TYPE:
            raise ValueError(
                f"attestation_type must be {ATTESTATION_TYPE!r}; "
                f"got {self.attestation_type!r}."
            )
        if not self.witness_operator_id:
            raise ValueError("witness_operator_id must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.witness_public_key_fingerprint):
            raise ValueError(
                "witness_public_key_fingerprint must be SHA-256 hex lowercase."
            )
        if not _SHA256_HEX_PATTERN.match(self.target_manifest_hash):
            raise ValueError("target_manifest_hash must be SHA-256 hex lowercase.")
        if self.target_manifest_sequence < 0:
            raise ValueError(
                f"target_manifest_sequence must be >= 0, got {self.target_manifest_sequence}."
            )
        if not self.target_operator_id:
            raise ValueError("target_operator_id must be non-empty.")
        if not _ISO_UTC_PATTERN.match(self.witnessed_at):
            raise ValueError(
                "witnessed_at must be ISO-8601 UTC of form YYYY-MM-DDTHH:MM:SSZ."
            )
        if self.statement is not None and not self.statement:
            raise ValueError(
                "statement must be None or non-empty (no empty string)."
            )
        if not _ED25519_SIG_PATTERN.match(self.signature):
            raise ValueError("signature must be ed25519 hex of length 128.")
        if self.signature_algorithm != SIGNATURE_ALGORITHM:
            raise ValueError(
                f"signature_algorithm must be {SIGNATURE_ALGORITHM!r}; "
                f"got {self.signature_algorithm!r}."
            )
        if not _SHA256_HEX_PATTERN.match(self.attestation_hash):
            raise ValueError("attestation_hash must be SHA-256 hex lowercase.")
