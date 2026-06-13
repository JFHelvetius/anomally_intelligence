"""Construcción, firma y verificación de :class:`WitnessAttestation`.

Reutiliza primitivas ed25519 de :mod:`aip.attestation` y JCS de
:mod:`aip.core.hashing`. Cero rolling-our-own crypto.

Flujo idéntico al de Transparency 1A y Capture:

1. Construir dict canónico sin ``signature`` ni ``attestation_hash``.
2. ``jcs_canonicalize`` → bytes deterministas.
3. ``private_key.sign(bytes)`` → ``signature`` ed25519 hex.
4. Computar ``attestation_hash`` sobre el dict completo excluyendo sólo el
   propio ``attestation_hash`` — incluye la firma.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from aip.attestation.signer import compute_public_key_fingerprint
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.transparency.models import TransparencyManifest
from aip.transparency.witness.models import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
    WITNESS_SCHEMA_VERSION,
    WitnessAttestation,
)

# --------------------------------------------------------------------- canonical


def _to_canonical_dict(att: WitnessAttestation) -> dict[str, object]:
    """Estructura canónica completa (incluye ``attestation_hash`` y firma)."""
    return {
        "attestation_type": att.attestation_type,
        "schema_version": att.schema_version,
        "witness_operator_id": att.witness_operator_id,
        "witness_public_key_fingerprint": att.witness_public_key_fingerprint,
        "target_manifest_hash": att.target_manifest_hash,
        "target_manifest_sequence": att.target_manifest_sequence,
        "target_operator_id": att.target_operator_id,
        "witnessed_at": att.witnessed_at,
        "statement": att.statement,
        "signature": att.signature,
        "signature_algorithm": att.signature_algorithm,
        "attestation_hash": att.attestation_hash,
    }


def compute_attestation_hash(att: WitnessAttestation) -> str:
    """SHA-256 hex JCS de la attestation **excluyendo** ``attestation_hash``."""
    data = _to_canonical_dict(att)
    data.pop("attestation_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


# --------------------------------------------------------------------- signing payload


def _build_signing_payload(
    *,
    witness_operator_id: str,
    witness_public_key_fingerprint: str,
    target_manifest_hash: str,
    target_manifest_sequence: int,
    target_operator_id: str,
    witnessed_at: str,
    statement: str | None,
) -> bytes:
    """JCS canonical bytes que se firman. Excluye ``signature`` y ``attestation_hash``."""
    payload_obj: dict[str, JsonValue] = {
        "attestation_type": ATTESTATION_TYPE,
        "schema_version": WITNESS_SCHEMA_VERSION,
        "witness_operator_id": witness_operator_id,
        "witness_public_key_fingerprint": witness_public_key_fingerprint,
        "target_manifest_hash": target_manifest_hash,
        "target_manifest_sequence": target_manifest_sequence,
        "target_operator_id": target_operator_id,
        "witnessed_at": witnessed_at,
        "statement": statement,
        "signature_algorithm": SIGNATURE_ALGORITHM,
    }
    return jcs_canonicalize(cast(JsonValue, payload_obj))


# --------------------------------------------------------------------- sign


def sign_witness(
    *,
    target_manifest: TransparencyManifest,
    witness_operator_id: str,
    witnessed_at: str,
    private_key: Ed25519PrivateKey,
    statement: str | None = None,
) -> WitnessAttestation:
    """Construye y firma un :class:`WitnessAttestation` sobre un manifest.

    Los campos ``target_*`` se derivan automáticamente de ``target_manifest``
    para evitar typos. Si el caller quiere firmar un manifest "abstracto" (sin
    tenerlo materializado como objeto), debe construir uno con los valores
    correctos antes de llamar — no exponemos ese atajo en V1 para forzar la
    consistencia bytes-firmados ↔ manifest-real.
    """
    public_key = private_key.public_key()
    fingerprint = compute_public_key_fingerprint(public_key)
    payload = _build_signing_payload(
        witness_operator_id=witness_operator_id,
        witness_public_key_fingerprint=fingerprint,
        target_manifest_hash=target_manifest.manifest_hash,
        target_manifest_sequence=target_manifest.sequence,
        target_operator_id=target_manifest.operator_id,
        witnessed_at=witnessed_at,
        statement=statement,
    )
    signature_bytes = private_key.sign(payload)
    signature_hex = signature_bytes.hex()
    partial = WitnessAttestation(
        attestation_type=ATTESTATION_TYPE,
        schema_version=WITNESS_SCHEMA_VERSION,
        witness_operator_id=witness_operator_id,
        witness_public_key_fingerprint=fingerprint,
        target_manifest_hash=target_manifest.manifest_hash,
        target_manifest_sequence=target_manifest.sequence,
        target_operator_id=target_manifest.operator_id,
        witnessed_at=witnessed_at,
        statement=statement,
        signature=signature_hex,
        signature_algorithm=SIGNATURE_ALGORITHM,
        attestation_hash="0" * 64,
    )
    final_hash = compute_attestation_hash(partial)
    return dataclasses.replace(partial, attestation_hash=final_hash)


# --------------------------------------------------------------------- verify


def verify_witness(
    attestation: WitnessAttestation,
    *,
    public_key: Ed25519PublicKey | None = None,
    target_manifest: TransparencyManifest | None = None,
) -> bool:
    """Verifica estructura + (opcionalmente) firma y match con manifest target.

    - Sin nada: recomputa ``attestation_hash`` (verificación estructural).
    - Con ``public_key`` (la del *witness*): añade verificación ed25519.
    - Con ``target_manifest``: verifica que ``target_manifest_hash`` y
      ``target_manifest_sequence`` y ``target_operator_id`` coincidan
      exactamente con los del manifest provisto.

    Devuelve ``True`` si todas las checks pasan, ``False`` si alguna falla.
    """
    if compute_attestation_hash(attestation) != attestation.attestation_hash:
        return False

    if target_manifest is not None and (
        attestation.target_manifest_hash != target_manifest.manifest_hash
        or attestation.target_manifest_sequence != target_manifest.sequence
        or attestation.target_operator_id != target_manifest.operator_id
    ):
        return False

    if public_key is None:
        return True

    if (
        compute_public_key_fingerprint(public_key)
        != attestation.witness_public_key_fingerprint
    ):
        return False

    payload = _build_signing_payload(
        witness_operator_id=attestation.witness_operator_id,
        witness_public_key_fingerprint=attestation.witness_public_key_fingerprint,
        target_manifest_hash=attestation.target_manifest_hash,
        target_manifest_sequence=attestation.target_manifest_sequence,
        target_operator_id=attestation.target_operator_id,
        witnessed_at=attestation.witnessed_at,
        statement=attestation.statement,
    )
    try:
        signature_bytes = bytes.fromhex(attestation.signature)
        public_key.verify(signature_bytes, payload)
        return True
    except (InvalidSignature, ValueError):
        return False
