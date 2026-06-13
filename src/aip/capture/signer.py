"""Construcción, firma y verificación de :class:`CaptureCertificate` (Phase 2).

Reutiliza primitivas ed25519 de :mod:`aip.attestation` y JCS de
:mod:`aip.core.hashing`. Cero rolling-our-own crypto.

Flujo de firma (paralelo a Transparency 1A):

1. Hashear el fichero de evidencia en streaming → ``evidence_sha256``.
2. Construir dict canónico sin ``signature`` ni ``certificate_hash``.
3. ``jcs_canonicalize`` → bytes deterministas.
4. ``private_key.sign(bytes)`` → ``signature`` ed25519 hex.
5. Computar ``certificate_hash`` JCS sobre el dict completo excluyendo
   sólo ``certificate_hash`` — incluye la firma, igual que TransparencyManifest.

Flujo de verificación (inverso):

1. Recomputar ``certificate_hash`` → debe coincidir.
2. Si hay clave pública: ``fingerprint`` declarada == fingerprint de la clave
   provista, luego recomputar payload de firma y ed25519-verify.
3. Si hay fichero de evidencia: recomputar su SHA-256 → debe coincidir con
   ``evidence_sha256`` (verificación de "este certificate es para ESTE fichero").
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from aip.attestation.signer import compute_public_key_fingerprint
from aip.capture.models import (
    CAPTURE_SCHEMA_VERSION,
    CERTIFICATE_TYPE,
    SIGNATURE_ALGORITHM,
    CaptureCertificate,
)
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex, sha256_hex_stream


def hash_file(path: Path) -> str:
    """SHA-256 hex en streaming de ``path``. Maneja ficheros grandes sin OOM."""
    with path.open("rb") as fh:
        return sha256_hex_stream(fh)


# --------------------------------------------------------------------- canonical


def _to_canonical_dict(c: CaptureCertificate) -> dict[str, object]:
    """Estructura canónica completa (incluye ``certificate_hash`` y firma)."""
    return {
        "certificate_type": c.certificate_type,
        "schema_version": c.schema_version,
        "evidence_sha256": c.evidence_sha256,
        "operator_id": c.operator_id,
        "captured_at": c.captured_at,
        "device_id": c.device_id,
        "location": c.location,
        "notes": c.notes,
        "public_key_fingerprint": c.public_key_fingerprint,
        "signature": c.signature,
        "signature_algorithm": c.signature_algorithm,
        "certificate_hash": c.certificate_hash,
    }


def compute_certificate_hash(c: CaptureCertificate) -> str:
    """SHA-256 hex JCS del certificate **excluyendo** ``certificate_hash``."""
    data = _to_canonical_dict(c)
    data.pop("certificate_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


# --------------------------------------------------------------------- signing payload


def _build_signing_payload(
    *,
    evidence_sha256: str,
    operator_id: str,
    captured_at: str,
    device_id: str | None,
    location: str | None,
    notes: str | None,
    public_key_fingerprint: str,
) -> bytes:
    """JCS canonical bytes que se firman. Excluye ``signature`` y ``certificate_hash``."""
    payload_obj: dict[str, JsonValue] = {
        "certificate_type": CERTIFICATE_TYPE,
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "evidence_sha256": evidence_sha256,
        "operator_id": operator_id,
        "captured_at": captured_at,
        "device_id": device_id,
        "location": location,
        "notes": notes,
        "public_key_fingerprint": public_key_fingerprint,
        "signature_algorithm": SIGNATURE_ALGORITHM,
    }
    return jcs_canonicalize(cast(JsonValue, payload_obj))


# --------------------------------------------------------------------- sign


def sign_capture(
    *,
    evidence_sha256: str,
    operator_id: str,
    captured_at: str,
    private_key: Ed25519PrivateKey,
    device_id: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> CaptureCertificate:
    """Construye y firma un :class:`CaptureCertificate`.

    ``captured_at`` debe venir ya pre-formateado como ``YYYY-MM-DDTHH:MM:SSZ``
    (segundos, UTC). El caller es responsable de normalizarlo desde input
    libre, igual que en :mod:`aip.attestation.signer`.
    """
    public_key = private_key.public_key()
    fingerprint = compute_public_key_fingerprint(public_key)
    payload = _build_signing_payload(
        evidence_sha256=evidence_sha256,
        operator_id=operator_id,
        captured_at=captured_at,
        device_id=device_id,
        location=location,
        notes=notes,
        public_key_fingerprint=fingerprint,
    )
    signature_bytes = private_key.sign(payload)
    signature_hex = signature_bytes.hex()
    partial = CaptureCertificate(
        certificate_type=CERTIFICATE_TYPE,
        schema_version=CAPTURE_SCHEMA_VERSION,
        evidence_sha256=evidence_sha256,
        operator_id=operator_id,
        captured_at=captured_at,
        device_id=device_id,
        location=location,
        notes=notes,
        public_key_fingerprint=fingerprint,
        signature=signature_hex,
        signature_algorithm=SIGNATURE_ALGORITHM,
        certificate_hash="0" * 64,
    )
    final_hash = compute_certificate_hash(partial)
    return dataclasses.replace(partial, certificate_hash=final_hash)


# --------------------------------------------------------------------- verify


def verify_capture(
    certificate: CaptureCertificate,
    *,
    public_key: Ed25519PublicKey | None = None,
    evidence_file: Path | None = None,
) -> bool:
    """Verifica estructura + (si se proveen) firma criptográfica y match de bytes.

    - Sin ``public_key`` ni ``evidence_file``: sólo recomputa ``certificate_hash``.
    - Con ``public_key``: además verifica fingerprint y ed25519-signature.
    - Con ``evidence_file``: además recomputa SHA-256 del fichero y verifica que
      coincida con ``evidence_sha256`` del certificate.

    Devuelve ``True`` si todas las checks pasan, ``False`` si alguna falla.
    """
    if compute_certificate_hash(certificate) != certificate.certificate_hash:
        return False

    if evidence_file is not None:
        actual_hash = hash_file(evidence_file)
        if actual_hash != certificate.evidence_sha256:
            return False

    if public_key is None:
        return True

    if (
        compute_public_key_fingerprint(public_key)
        != certificate.public_key_fingerprint
    ):
        return False

    payload = _build_signing_payload(
        evidence_sha256=certificate.evidence_sha256,
        operator_id=certificate.operator_id,
        captured_at=certificate.captured_at,
        device_id=certificate.device_id,
        location=certificate.location,
        notes=certificate.notes,
        public_key_fingerprint=certificate.public_key_fingerprint,
    )
    try:
        signature_bytes = bytes.fromhex(certificate.signature)
        public_key.verify(signature_bytes, payload)
        return True
    except (InvalidSignature, ValueError):
        return False
