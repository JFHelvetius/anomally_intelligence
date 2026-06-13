"""GET /api/transparency/* — read-only access to transparency log (Phase 1B).

Serve manifests + operator public key so the static verification portal can
pull them and verify client-side using WebCrypto / noble-curves.

All routes are pure file reads. No verification happens here — verification
is the portal's job, by design.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from aip.api.deps import ArchiveDep
from aip.notarize import (
    OTS_EXTENSION,
    decode_dtf_from_bytes,
    verify_proof,
)
from aip.transparency.key_declaration import (
    check_consistency,
    load_declaration,
)
from aip.transparency.store import (
    LATEST_FILENAME,
    TRANSPARENCY_DIRNAME,
    list_sequences,
    manifest_path,
)
from aip.transparency.witness import (
    encode_witness,
    list_all_witnesses,
    list_witnesses_for_manifest,
)

router = APIRouter(tags=["transparency"], prefix="/transparency")

_PUBLIC_KEY_FILENAME = "public-key.pem"


def _summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Compact summary fields for the list endpoint."""
    return {
        "sequence": data["sequence"],
        "manifest_hash": data["manifest_hash"],
        "previous_manifest_hash": data["previous_manifest_hash"],
        "audit_chain_head_hash": data["audit_chain_head_hash"],
        "audit_entry_count": data["audit_entry_count"],
        "evidence_count": data["evidence_count"],
        "attestation_count": data["attestation_count"],
        "signed_at": data["signed_at"],
        "operator_id": data["operator_id"],
        "public_key_fingerprint": data["public_key_fingerprint"],
    }


@router.get("/status")
def transparency_status(archive: ArchiveDep) -> dict[str, Any]:
    """Cabeza del log + flag de disponibilidad de public key."""
    sequences = list_sequences(archive.root)
    pk_path = archive.root / TRANSPARENCY_DIRNAME / _PUBLIC_KEY_FILENAME
    head = None
    if sequences:
        path = manifest_path(archive.root, sequences[-1])
        if path.is_file():
            head = _summarize(json.loads(path.read_text(encoding="utf-8")))
    return {
        "manifest_count": len(sequences),
        "head": head,
        "public_key_available": pk_path.is_file(),
        "transparency_dir": TRANSPARENCY_DIRNAME,
        "latest_filename": LATEST_FILENAME,
    }


@router.get("/manifests")
def list_manifests(archive: ArchiveDep) -> list[dict[str, Any]]:
    """Todos los manifests ordenados por secuencia, con campos resumidos."""
    out: list[dict[str, Any]] = []
    for seq in list_sequences(archive.root):
        path = manifest_path(archive.root, seq)
        if not path.is_file():
            continue
        try:
            out.append(_summarize(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError):
            continue
    return out


@router.get("/manifests/{sequence}")
def get_manifest(sequence: int, archive: ArchiveDep) -> dict[str, Any]:
    """Devuelve el manifest completo (incluye signature, manifest_hash, todos los counts)."""
    path = manifest_path(archive.root, sequence)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"manifest {sequence} not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="malformed manifest file") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="malformed manifest file")
    return data


@router.get("/witnesses")
def list_witnesses(archive: ArchiveDep) -> dict[str, list[dict[str, Any]]]:
    """Devuelve todos los witnesses organizados por secuencia de manifest.

    Forma: ``{"<sequence>": [<full WitnessAttestation>, ...]}`` con el JSON
    canónico (sorted-keys) del store. El portal verifica client-side; el
    backend solo entrega bytes.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for seq, witnesses in list_all_witnesses(archive.root).items():
        out[str(seq)] = [json.loads(encode_witness(w)) for w in witnesses]
    return out


@router.get("/witnesses/{sequence}")
def list_witnesses_for(
    sequence: int, archive: ArchiveDep
) -> list[dict[str, Any]]:
    """Devuelve los witnesses de un manifest concreto. Lista vacía si none."""
    return [
        json.loads(encode_witness(w))
        for w in list_witnesses_for_manifest(archive.root, sequence)
    ]


@router.get("/notarization/{sequence}")
def get_notarization(sequence: int, archive: ArchiveDep) -> dict[str, Any] | None:
    """Devuelve resumen del proof OpenTimestamps de un manifest concreto.

    ``None`` si no hay ``.ots`` publicado para esa secuencia (caso normal —
    no todos los manifests se notarizan, depende del operador).
    """
    ots_path = (
        archive.root
        / TRANSPARENCY_DIRNAME
        / f"manifest-{sequence:06d}.json{OTS_EXTENSION}"
    )
    if not ots_path.is_file():
        return None
    try:
        dtf = decode_dtf_from_bytes(ots_path.read_bytes())
        result = verify_proof(dtf, expected_sha256=dtf.file_digest)
    except (OSError, ValueError):
        return None
    return {
        "ots_filename": ots_path.name,
        "leaf_sha256": dtf.file_digest.hex(),
        "bitcoin_anchors": [
            {
                "height": c.height,
                "expected_merkle_root_le_hex": c.expected_merkle_root_le.hex(),
            }
            for c in result.bitcoin_claims
        ],
        "pending_count": len(result.pending_claims),
        "pending_calendars": [p.calendar_uri for p in result.pending_claims],
    }


@router.get("/key-declaration")
def get_key_declaration(archive: ArchiveDep) -> dict[str, Any]:
    """Return the operator's key declaration (ADR-0043) and a consistency
    report comparing it against the on-disk public keys.

    The declaration itself is operator-supplied JSON; this endpoint does
    not verify the external references. It only surfaces them so the
    operator dashboard and the public portal can render the trust
    footprint, and reports inconsistencies that would otherwise stay
    silent (e.g., a declared witness fingerprint that has no matching
    ``.pem`` in ``transparency/witness-keys/``).

    Always 200. Absent declaration is a normal state, not an error;
    ``declaration: null`` + ``consistency.declaration_present: false``
    tells the UI to render the honest 'no declaration' warning.
    """
    declaration = load_declaration(archive.root)
    consistency = check_consistency(archive.root)
    return {
        "declaration": declaration,
        "consistency": {
            "declaration_present": consistency.declaration_present,
            "operator_fingerprint_declared": (
                consistency.operator_fingerprint_declared
            ),
            "operator_fingerprint_actual": (
                consistency.operator_fingerprint_actual
            ),
            "operator_matches": consistency.operator_matches,
            "witnesses_declared": consistency.witnesses_declared,
            "witnesses_in_archive": consistency.witnesses_in_archive,
            "declared_witnesses_without_pem": (
                consistency.declared_witnesses_without_pem
            ),
            "extra_witness_pems_not_declared": (
                consistency.extra_witness_pems_not_declared
            ),
            "ok": consistency.ok,
        },
    }


@router.get("/public-key", response_class=PlainTextResponse)
def get_public_key(archive: ArchiveDep) -> str:
    """Sirve la clave pública del operador en PEM SPKI si está publicada.

    Convención: el operador copia su ``op.pub`` a
    ``<archive>/transparency/public-key.pem`` para que el portal y los
    verificadores externos puedan obtenerla. El fingerprint que va en cada
    manifest la identifica unívocamente — si el operador rota su clave,
    cambia el fingerprint y el portal debe avisar.
    """
    target = archive.root / TRANSPARENCY_DIRNAME / _PUBLIC_KEY_FILENAME
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"operator public key not published. Copy your ed25519 public "
                f"key (PEM SubjectPublicKeyInfo) to {TRANSPARENCY_DIRNAME}/{_PUBLIC_KEY_FILENAME}."
            ),
        )
    return target.read_text(encoding="utf-8")
