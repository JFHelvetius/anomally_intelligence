"""Firma, verificación, persistencia y gestión de claves (ADR-0041).

Wrapper alrededor de ``cryptography`` para ed25519. Cero rolling-our-own.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from aip._version import SCHEMA_VERSION
from aip.attestation.models import (
    ALLOWED_ARTIFACT_KINDS,
    ATTESTATION_SCHEMA_VERSION,
    SIGNATURE_ALGORITHM,
    OperatorAttestation,
)
from aip.audit import log as audit_log
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.errors import AIPError
from aip.storage.atomic_io import atomic_write_text
from aip.storage.manifest import ArchiveManifest

ATTESTATIONS_DIRNAME: str = "attestations"


class AttestationNotFoundError(AIPError):
    """Atestación solicitada no existe bajo ``<archive>/attestations/``."""

    cli_exit_code = 1


class SignatureVerificationError(AIPError):
    """La firma ed25519 no verifica contra el payload + clave pública."""

    cli_exit_code = 1


# --------------------------------------------------------------------- keys


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Genera un par ed25519 fresco. Usa el RNG criptográfico del sistema."""
    private = Ed25519PrivateKey.generate()
    return private, private.public_key()


def load_private_key(path: Path) -> Ed25519PrivateKey:
    """Carga una clave privada ed25519 desde PEM PKCS#8 sin passphrase."""
    data = path.read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(
            f"private key at {path} is not ed25519 "
            f"(got {type(key).__name__})."
        )
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    """Carga una clave pública ed25519 desde PEM SubjectPublicKeyInfo."""
    data = path.read_bytes()
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(
            f"public key at {path} is not ed25519 "
            f"(got {type(key).__name__})."
        )
    return key


def serialize_private_key_pem(key: Ed25519PrivateKey) -> bytes:
    """Serializa clave privada a PEM PKCS#8 sin passphrase."""
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def serialize_public_key_pem(key: Ed25519PublicKey) -> bytes:
    """Serializa clave pública a PEM SubjectPublicKeyInfo."""
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def compute_public_key_fingerprint(key: Ed25519PublicKey) -> str:
    """SHA-256 hex sobre la representación DER (raw) de la clave pública.

    Estable bit a bit. No depende de comentarios, encabezados PEM, ni
    representación textual.
    """
    der_bytes = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der_bytes).hexdigest()


# --------------------------------------------------------------------- artifact reading


_SELF_HASH_FIELD_BY_KIND: dict[str, str] = {
    "workspace": "workspace_hash",
    "timeline": "timeline_hash",
    "snapshot": "snapshot_hash",
    "justification": "justification_hash",
    "context_bundle": "context_bundle_hash",
    # ADR-0042: ArchiveSnapshot tiene snapshot_hash como self-hash.
    # Aunque colisiona en nombre con InvestigationSnapshot, son
    # distinguidos por artifact_kind ("archive_snapshot" vs "snapshot").
    "archive_snapshot": "snapshot_hash",
}


def extract_artifact_self_hash(
    artifact_kind: str, artifact_path: Path
) -> str:
    """Extrae el self-hash del artefacto persistido.

    Para los cinco artefactos derivados con hash auto-referente, lee la
    clave correspondiente del JSON. Para ``manifest``, calcula el hash
    del manifest stored vía :meth:`ArchiveManifest.manifest_hash`.
    """
    if artifact_kind not in ALLOWED_ARTIFACT_KINDS:
        raise ValueError(
            f"invalid artifact_kind {artifact_kind!r}; "
            f"must be one of {sorted(ALLOWED_ARTIFACT_KINDS)}."
        )
    raw = artifact_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(
            f"artifact at {artifact_path} must be a JSON object."
        )
    if artifact_kind == "manifest":
        # Compute manifest_hash from stored content.
        manifest = ArchiveManifest.model_validate(data)
        return manifest.manifest_hash()
    field = _SELF_HASH_FIELD_BY_KIND[artifact_kind]
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(
            f"artifact at {artifact_path} missing self-hash field "
            f"{field!r} (kind={artifact_kind})."
        )
    return value


# --------------------------------------------------------------------- payload


def _build_signing_payload(
    *,
    artifact_kind: str,
    artifact_hash: str,
    signer_id: str,
    public_key_fingerprint: str,
    signed_at: str,
) -> bytes:
    """JCS canonical bytes que se firman. Pinned por ADR-0041 §algoritmo."""
    payload_obj: dict[str, JsonValue] = {
        "artifact_kind": artifact_kind,
        "artifact_hash": artifact_hash,
        "signer_id": signer_id,
        "public_key_fingerprint": public_key_fingerprint,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signed_at": signed_at,
        "schema_version": ATTESTATION_SCHEMA_VERSION,
    }
    return jcs_canonicalize(cast(JsonValue, payload_obj))


# --------------------------------------------------------------------- sign


def sign_artifact(
    *,
    artifact_kind: str,
    artifact_path: Path,
    private_key: Ed25519PrivateKey,
    signer_id: str,
    signed_at: dt.datetime,
) -> OperatorAttestation:
    """Construye una :class:`OperatorAttestation` firmando el self-hash
    del artefacto.

    El ``signed_at`` se serializa a ISO-8601 UTC con microsegundos
    descartados — coherente con el formato del manifest y de los
    timestamps del audit log.
    """
    if artifact_kind not in ALLOWED_ARTIFACT_KINDS:
        raise ValueError(
            f"invalid artifact_kind {artifact_kind!r}; "
            f"must be one of {sorted(ALLOWED_ARTIFACT_KINDS)}."
        )
    if signed_at.tzinfo is None:
        raise ValueError("signed_at must be timezone-aware (UTC).")
    iso_at = (
        signed_at.astimezone(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    artifact_hash = extract_artifact_self_hash(artifact_kind, artifact_path)
    public_key = private_key.public_key()
    fingerprint = compute_public_key_fingerprint(public_key)
    payload = _build_signing_payload(
        artifact_kind=artifact_kind,
        artifact_hash=artifact_hash,
        signer_id=signer_id,
        public_key_fingerprint=fingerprint,
        signed_at=iso_at,
    )
    signature_bytes = private_key.sign(payload)
    signature_hex = signature_bytes.hex()
    partial = OperatorAttestation(
        artifact_kind=artifact_kind,
        artifact_hash=artifact_hash,
        signer_id=signer_id,
        public_key_fingerprint=fingerprint,
        signature=signature_hex,
        signature_algorithm=SIGNATURE_ALGORITHM,
        signed_at=iso_at,
        attestation_hash="0" * 64,
    )
    final_hash = compute_attestation_hash(partial)
    return dataclasses.replace(partial, attestation_hash=final_hash)


# --------------------------------------------------------------------- verify


def verify_attestation(
    attestation: OperatorAttestation,
    *,
    public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Verifica integridad estructural + (si se provee clave pública)
    la firma criptográfica.

    Si ``public_key`` no se provee, sólo recomputa ``attestation_hash``
    (verificación estructural). Para verificación criptográfica completa,
    pasar la clave pública del firmante.

    Devuelve ``True`` si todas las checks pasan; ``False`` si alguna falla.
    """
    if compute_attestation_hash(attestation) != attestation.attestation_hash:
        return False
    if public_key is None:
        return True
    # Verifica que la fingerprint declarada coincida con la clave provista.
    if (
        compute_public_key_fingerprint(public_key)
        != attestation.public_key_fingerprint
    ):
        return False
    payload = _build_signing_payload(
        artifact_kind=attestation.artifact_kind,
        artifact_hash=attestation.artifact_hash,
        signer_id=attestation.signer_id,
        public_key_fingerprint=attestation.public_key_fingerprint,
        signed_at=attestation.signed_at,
    )
    try:
        signature_bytes = bytes.fromhex(attestation.signature)
        public_key.verify(signature_bytes, payload)
        return True
    except (InvalidSignature, ValueError):
        return False


# --------------------------------------------------------------------- hashing


def compute_attestation_hash(att: OperatorAttestation) -> str:
    """SHA-256 hex JCS del modelo excluyendo ``attestation_hash``."""
    data = _attestation_to_canonical_dict(att)
    data.pop("attestation_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


def _attestation_to_canonical_dict(
    att: OperatorAttestation,
) -> dict[str, object]:
    return {
        "artifact_kind": att.artifact_kind,
        "artifact_hash": att.artifact_hash,
        "signer_id": att.signer_id,
        "public_key_fingerprint": att.public_key_fingerprint,
        "signature": att.signature,
        "signature_algorithm": att.signature_algorithm,
        "signed_at": att.signed_at,
        "attestation_hash": att.attestation_hash,
        "schema_version": att.schema_version,
    }


# --------------------------------------------------------------------- persistence


def _attestation_path(archive_root: Path, attestation_id: str) -> Path:
    return archive_root / ATTESTATIONS_DIRNAME / f"{attestation_id}.json"


def persist_attestation(
    att: OperatorAttestation,
    *,
    archive_root: Path,
    attestation_id: str,
    actor: str,
    clock: Callable[[], dt.datetime],
    extra_output: Path | None = None,
) -> Path:
    """Persiste la atestación bajo ``<archive>/attestations/<id>.json``.

    Emite una entry ``SIGN_ATTESTATION`` en el audit log (ADR-0019
    §enmienda E1). ``actor`` y ``clock`` son operator-supplied y entran
    en la cadena hash-encadenada del log; el ``signer_id`` y ``signed_at``
    de la atestación firmada permanecen en el JSON canónico del artefacto.
    """
    target = _attestation_path(archive_root, attestation_id)
    payload = encode_attestation(att)
    atomic_write_text(target, payload)
    if extra_output is not None:
        atomic_write_text(extra_output, payload)
    audit_log.record_derived_artifact(
        archive_root,
        action=audit_log.ActionKind.SIGN_ATTESTATION,
        artifact_kind="attestation",
        artifact_id=attestation_id,
        self_hash=att.attestation_hash,
        actor=actor,
        clock=clock,
        schema_version=SCHEMA_VERSION,
        extra_parameters={
            "signer_id": att.signer_id,
            "public_key_fingerprint": att.public_key_fingerprint,
        },
    )
    return target


def load_attestation(
    *, archive_root: Path, attestation_id: str
) -> OperatorAttestation:
    target = _attestation_path(archive_root, attestation_id)
    if not target.is_file():
        raise AttestationNotFoundError(
            f"attestation {attestation_id!r} not found at {target}."
        )
    return decode_attestation(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- encoding


def encode_attestation(att: OperatorAttestation) -> str:
    data = _attestation_to_canonical_dict(att)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def decode_attestation(payload: str) -> OperatorAttestation:
    data = json.loads(payload)
    return OperatorAttestation(
        artifact_kind=data["artifact_kind"],
        artifact_hash=data["artifact_hash"],
        signer_id=data["signer_id"],
        public_key_fingerprint=data["public_key_fingerprint"],
        signature=data["signature"],
        signature_algorithm=data["signature_algorithm"],
        signed_at=data["signed_at"],
        attestation_hash=data["attestation_hash"],
        schema_version=data.get("schema_version", ""),
    )
