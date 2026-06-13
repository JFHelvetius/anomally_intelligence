"""Construcción, firma y verificación de :class:`TransparencyManifest` (Phase 1A).

Reutiliza las primitivas ed25519 de :mod:`aip.attestation` y la
canonicalización JCS de :mod:`aip.core.hashing`. Cero rolling-our-own crypto.

Flujo de firma:

1. Construir el dict canónico sin ``signature`` ni ``manifest_hash``.
2. ``jcs_canonicalize`` → bytes deterministas.
3. ``private_key.sign(bytes)`` → ``signature`` ed25519 hex.
4. Computar ``manifest_hash`` sobre el dict canónico que **incluye** la firma
   y excluye sólo ``manifest_hash`` — así el self-hash ata la firma a la
   identidad del manifest, y manipular la firma cambia el hash que el manifest
   N+1 referencia en ``previous_manifest_hash``.

Flujo de verificación (inverso):

1. Recomputar ``manifest_hash`` excluyendo el campo → debe coincidir.
2. Si hay clave pública: verificar ``fingerprint`` declarada == fingerprint
   de la clave provista, luego recomputar el payload de firma y ed25519-verify.
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
from aip.transparency.models import (
    MANIFEST_TYPE,
    SIGNATURE_ALGORITHM,
    TRANSPARENCY_SCHEMA_VERSION,
    TransparencyManifest,
)

# --------------------------------------------------------------------- canonical dict


def _to_canonical_dict(m: TransparencyManifest) -> dict[str, object]:
    """Estructura canónica completa del manifest (incluye ``manifest_hash``)."""
    return {
        "sequence": m.sequence,
        "signed_at": m.signed_at,
        "manifest_type": m.manifest_type,
        "operator_id": m.operator_id,
        "public_key_fingerprint": m.public_key_fingerprint,
        "archive_manifest_hash": m.archive_manifest_hash,
        "audit_chain_head_hash": m.audit_chain_head_hash,
        "audit_entry_count": m.audit_entry_count,
        "evidence_count": m.evidence_count,
        "attestation_count": m.attestation_count,
        "workspace_count": m.workspace_count,
        "timeline_count": m.timeline_count,
        "snapshot_count": m.snapshot_count,
        "justification_count": m.justification_count,
        "previous_manifest_hash": m.previous_manifest_hash,
        "signature": m.signature,
        "signature_algorithm": m.signature_algorithm,
        "manifest_hash": m.manifest_hash,
        "schema_version": m.schema_version,
    }


def compute_manifest_hash(m: TransparencyManifest) -> str:
    """SHA-256 hex JCS del manifest **excluyendo** ``manifest_hash``.

    Incluye la firma — así un atacante que altere la firma rompe el self-hash
    y, transitivamente, el ``previous_manifest_hash`` del manifest siguiente.
    """
    data = _to_canonical_dict(m)
    data.pop("manifest_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


# --------------------------------------------------------------------- signing payload


def _build_signing_payload(
    *,
    sequence: int,
    signed_at: str,
    operator_id: str,
    public_key_fingerprint: str,
    archive_manifest_hash: str,
    audit_chain_head_hash: str,
    audit_entry_count: int,
    evidence_count: int,
    attestation_count: int,
    workspace_count: int,
    timeline_count: int,
    snapshot_count: int,
    justification_count: int,
    previous_manifest_hash: str,
) -> bytes:
    """JCS canonical bytes que se firman. Excluye ``signature`` y ``manifest_hash``."""
    payload_obj: dict[str, JsonValue] = {
        "sequence": sequence,
        "signed_at": signed_at,
        "manifest_type": MANIFEST_TYPE,
        "operator_id": operator_id,
        "public_key_fingerprint": public_key_fingerprint,
        "archive_manifest_hash": archive_manifest_hash,
        "audit_chain_head_hash": audit_chain_head_hash,
        "audit_entry_count": audit_entry_count,
        "evidence_count": evidence_count,
        "attestation_count": attestation_count,
        "workspace_count": workspace_count,
        "timeline_count": timeline_count,
        "snapshot_count": snapshot_count,
        "justification_count": justification_count,
        "previous_manifest_hash": previous_manifest_hash,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "schema_version": TRANSPARENCY_SCHEMA_VERSION,
    }
    return jcs_canonicalize(cast(JsonValue, payload_obj))


# --------------------------------------------------------------------- sign


def sign_manifest(
    *,
    sequence: int,
    signed_at: str,
    operator_id: str,
    private_key: Ed25519PrivateKey,
    archive_manifest_hash: str,
    audit_chain_head_hash: str,
    audit_entry_count: int,
    evidence_count: int,
    attestation_count: int,
    workspace_count: int,
    timeline_count: int,
    snapshot_count: int,
    justification_count: int,
    previous_manifest_hash: str,
) -> TransparencyManifest:
    """Construye y firma un :class:`TransparencyManifest`.

    ``signed_at`` debe venir ya pre-formateado como ``YYYY-MM-DDTHH:MM:SSZ``
    (igual que ``OperatorAttestation.signed_at``) para mantener una sola
    convención temporal a lo largo del proyecto.
    """
    public_key = private_key.public_key()
    fingerprint = compute_public_key_fingerprint(public_key)
    payload = _build_signing_payload(
        sequence=sequence,
        signed_at=signed_at,
        operator_id=operator_id,
        public_key_fingerprint=fingerprint,
        archive_manifest_hash=archive_manifest_hash,
        audit_chain_head_hash=audit_chain_head_hash,
        audit_entry_count=audit_entry_count,
        evidence_count=evidence_count,
        attestation_count=attestation_count,
        workspace_count=workspace_count,
        timeline_count=timeline_count,
        snapshot_count=snapshot_count,
        justification_count=justification_count,
        previous_manifest_hash=previous_manifest_hash,
    )
    signature_bytes = private_key.sign(payload)
    signature_hex = signature_bytes.hex()

    partial = TransparencyManifest(
        sequence=sequence,
        signed_at=signed_at,
        manifest_type=MANIFEST_TYPE,
        operator_id=operator_id,
        public_key_fingerprint=fingerprint,
        archive_manifest_hash=archive_manifest_hash,
        audit_chain_head_hash=audit_chain_head_hash,
        audit_entry_count=audit_entry_count,
        evidence_count=evidence_count,
        attestation_count=attestation_count,
        workspace_count=workspace_count,
        timeline_count=timeline_count,
        snapshot_count=snapshot_count,
        justification_count=justification_count,
        previous_manifest_hash=previous_manifest_hash,
        signature=signature_hex,
        signature_algorithm=SIGNATURE_ALGORITHM,
        manifest_hash="0" * 64,
    )
    final_hash = compute_manifest_hash(partial)
    return dataclasses.replace(partial, manifest_hash=final_hash)


# --------------------------------------------------------------------- verify


def verify_manifest(
    manifest: TransparencyManifest,
    *,
    public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Verifica integridad estructural + (si se provee clave pública) firma.

    Sin ``public_key``: sólo recomputa ``manifest_hash`` (verificación
    estructural — útil cuando solo se quiere validar la cadena).
    Con ``public_key``: además recomputa el payload de firma y ejecuta
    ed25519-verify. La fingerprint declarada debe coincidir con la clave.

    Devuelve ``True`` si todas las checks pasan; ``False`` si alguna falla.
    """
    if compute_manifest_hash(manifest) != manifest.manifest_hash:
        return False
    if public_key is None:
        return True
    if (
        compute_public_key_fingerprint(public_key)
        != manifest.public_key_fingerprint
    ):
        return False
    payload = _build_signing_payload(
        sequence=manifest.sequence,
        signed_at=manifest.signed_at,
        operator_id=manifest.operator_id,
        public_key_fingerprint=manifest.public_key_fingerprint,
        archive_manifest_hash=manifest.archive_manifest_hash,
        audit_chain_head_hash=manifest.audit_chain_head_hash,
        audit_entry_count=manifest.audit_entry_count,
        evidence_count=manifest.evidence_count,
        attestation_count=manifest.attestation_count,
        workspace_count=manifest.workspace_count,
        timeline_count=manifest.timeline_count,
        snapshot_count=manifest.snapshot_count,
        justification_count=manifest.justification_count,
        previous_manifest_hash=manifest.previous_manifest_hash,
    )
    try:
        signature_bytes = bytes.fromhex(manifest.signature)
        public_key.verify(signature_bytes, payload)
        return True
    except (InvalidSignature, ValueError):
        return False


# --------------------------------------------------------------------- chain


def verify_chain(manifests: list[TransparencyManifest]) -> tuple[bool, str | None]:
    """Verifica que la lista forme una cadena coherente.

    Reglas:

    - ``sequence`` arranca en 0 y es estrictamente monotónico sin huecos.
    - El primer manifest tiene ``previous_manifest_hash`` = ZERO_HASH.
    - Para i>0, ``manifests[i].previous_manifest_hash == manifests[i-1].manifest_hash``.
    - Cada manifest pasa :func:`verify_manifest` estructuralmente.

    Devuelve ``(True, None)`` si la cadena es válida, o ``(False, motivo)``.
    """
    if not manifests:
        return True, None
    for i, m in enumerate(manifests):
        if m.sequence != i:
            return False, f"sequence mismatch at index {i}: expected {i}, got {m.sequence}"
        if not verify_manifest(m, public_key=None):
            return False, f"manifest at sequence {m.sequence} failed structural verification"
        expected_prev = (
            "0" * 64 if i == 0 else manifests[i - 1].manifest_hash
        )
        if m.previous_manifest_hash != expected_prev:
            return (
                False,
                f"chain break at sequence {m.sequence}: "
                f"previous_manifest_hash={m.previous_manifest_hash[:16]}…, "
                f"expected {expected_prev[:16]}…",
            )
    return True, None
