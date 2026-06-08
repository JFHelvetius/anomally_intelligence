"""Operator Attestation Engine (ADR-0041).

Capa de atestación criptográfica. Vincula un artefacto a una clave
ed25519 controlada por un operador. La verificación es exógena
(requiere la clave pública del firmante), no endógena (auto-consistente).

**Propiedad central (ADR-0041 §propiedad central):**

> Operator Attestation **vincula un artefacto a una clave criptográfica
> controlada por un operador**. Demuestra que el titular de la clave
> privada vio y avaló el contenido exacto del artefacto. **No** prueba
> identidad real (PKI fuera de scope V1). **No** prueba momento absoluto
> (sin TSA). **No** prueba veracidad del contenido. Sólo el vínculo
> clave-artefacto.

Sin motores estadísticos ni interpretativos: ni IA, ni NLP, ni vectores
densos, ni scoring, ni sugerencias automatizadas. Sólo primitivas
ed25519 vía la librería ``cryptography`` (auditada por la PSF).
"""

from __future__ import annotations

from aip.attestation.models import (
    ALLOWED_ARTIFACT_KINDS,
    ATTESTATION_SCHEMA_VERSION,
    SIGNATURE_ALGORITHM,
    OperatorAttestation,
)
from aip.attestation.signer import (
    AttestationNotFoundError,
    SignatureVerificationError,
    compute_attestation_hash,
    compute_public_key_fingerprint,
    decode_attestation,
    encode_attestation,
    extract_artifact_self_hash,
    generate_keypair,
    load_attestation,
    load_private_key,
    load_public_key,
    persist_attestation,
    serialize_private_key_pem,
    serialize_public_key_pem,
    sign_artifact,
    verify_attestation,
)

__all__ = [
    "ALLOWED_ARTIFACT_KINDS",
    "ATTESTATION_SCHEMA_VERSION",
    "SIGNATURE_ALGORITHM",
    "AttestationNotFoundError",
    "OperatorAttestation",
    "SignatureVerificationError",
    "compute_attestation_hash",
    "compute_public_key_fingerprint",
    "decode_attestation",
    "encode_attestation",
    "extract_artifact_self_hash",
    "generate_keypair",
    "load_attestation",
    "load_private_key",
    "load_public_key",
    "persist_attestation",
    "serialize_private_key_pem",
    "serialize_public_key_pem",
    "sign_artifact",
    "verify_attestation",
]
