"""Encode / decode de :class:`CaptureCertificate` (Phase 2).

Capture certificates **no** tienen un directorio canónico en el archive (a
diferencia de attestations o transparency manifests) — viven junto al fichero
que firman, o en cualquier lugar que el operador decida. La integración con
``aip evidence ingest`` para enlazarlos al provenance chain es vN+1; en V1
operan como artefactos sueltos verificables.
"""

from __future__ import annotations

import json

from aip.capture.models import CaptureCertificate


def encode_certificate(c: CaptureCertificate) -> str:
    """Serializa el certificate a JSON indentado, claves ordenadas.

    Mismo estilo que :func:`aip.attestation.encode_attestation`. El hash
    canónico no depende de esta forma — está fijado por ``certificate_hash``,
    computado desde JCS.
    """
    data = {
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
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def decode_certificate(payload: str) -> CaptureCertificate:
    data = json.loads(payload)
    return CaptureCertificate(
        certificate_type=data["certificate_type"],
        schema_version=data.get("schema_version", "1"),
        evidence_sha256=data["evidence_sha256"],
        operator_id=data["operator_id"],
        captured_at=data["captured_at"],
        device_id=data.get("device_id"),
        location=data.get("location"),
        notes=data.get("notes"),
        public_key_fingerprint=data["public_key_fingerprint"],
        signature=data["signature"],
        signature_algorithm=data["signature_algorithm"],
        certificate_hash=data["certificate_hash"],
    )
