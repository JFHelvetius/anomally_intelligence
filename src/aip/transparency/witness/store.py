"""Persistencia, lectura y listado de :class:`WitnessAttestation`.

Layout en el archive del *target operator* (el dueño del manifest que se
atestigua):

    <archive>/transparency/witnesses/
        manifest-000000/
            <witness_attestation_hash>.json
            <witness_attestation_hash>.json
        manifest-000001/
            <witness_attestation_hash>.json
        ...

Estructura por-manifest porque cada manifest puede acumular múltiples
witnesses (de operadores distintos) a lo largo del tiempo. Indexar por
secuencia hace el listado eficiente sin tener que abrir cada fichero.

El witness operator NORMALMENTE no tiene write access al archive del target.
El flujo típico es:

1. Witness W descarga el manifest M del target (o del transparency log público).
2. W ejecuta ``aip transparency witness sign`` → JSON a stdout o ``--output``.
3. W envía el JSON al target operator T (email/PR/HTTP).
4. T copia el JSON a su ``<archive>/transparency/witnesses/manifest-NNNNNN/``.

Este store soporta el paso 4 — para cuando *eres* el target o cuando quieres
testar el flujo end-to-end localmente.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from aip.errors import AIPError
from aip.storage.atomic_io import atomic_write_text
from aip.transparency.store import TRANSPARENCY_DIRNAME
from aip.transparency.witness.models import WitnessAttestation

WITNESSES_DIRNAME: Final[str] = "witnesses"

_MANIFEST_DIR_RE: Final[re.Pattern[str]] = re.compile(r"^manifest-(\d{6,})$")
_WITNESS_FILE_RE: Final[re.Pattern[str]] = re.compile(r"^([a-f0-9]{64})\.json$")


class WitnessError(AIPError):
    """Errores genéricos de operaciones sobre el store de witnesses."""

    cli_exit_code = 1


# --------------------------------------------------------------------- paths


def witnesses_root(archive_root: Path) -> Path:
    return archive_root / TRANSPARENCY_DIRNAME / WITNESSES_DIRNAME


def manifest_witnesses_dir(archive_root: Path, sequence: int) -> Path:
    if sequence < 0:
        raise ValueError(f"sequence must be >= 0, got {sequence}.")
    return witnesses_root(archive_root) / f"manifest-{sequence:06d}"


def witness_path(
    archive_root: Path, sequence: int, attestation_hash: str
) -> Path:
    return manifest_witnesses_dir(archive_root, sequence) / f"{attestation_hash}.json"


# --------------------------------------------------------------------- encode / decode


def encode_witness(att: WitnessAttestation) -> str:
    """Serializa con claves ordenadas e indentación legible. El hash canónico
    sigue siendo el de la representación JCS — esta forma es de presentación."""
    data = {
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
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def decode_witness(payload: str) -> WitnessAttestation:
    data = json.loads(payload)
    return WitnessAttestation(
        attestation_type=data["attestation_type"],
        schema_version=data.get("schema_version", "1"),
        witness_operator_id=data["witness_operator_id"],
        witness_public_key_fingerprint=data["witness_public_key_fingerprint"],
        target_manifest_hash=data["target_manifest_hash"],
        target_manifest_sequence=data["target_manifest_sequence"],
        target_operator_id=data["target_operator_id"],
        witnessed_at=data["witnessed_at"],
        statement=data.get("statement"),
        signature=data["signature"],
        signature_algorithm=data["signature_algorithm"],
        attestation_hash=data["attestation_hash"],
    )


# --------------------------------------------------------------------- reads


def list_witnesses_for_manifest(
    archive_root: Path, sequence: int
) -> list[WitnessAttestation]:
    """Devuelve todos los witnesses de ``manifest-NNNNNN`` ordenados por hash."""
    d = manifest_witnesses_dir(archive_root, sequence)
    if not d.is_dir():
        return []
    out: list[WitnessAttestation] = []
    for entry in sorted(d.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        if _WITNESS_FILE_RE.match(entry.name) is None:
            continue
        try:
            out.append(decode_witness(entry.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return out


def list_all_witnesses(archive_root: Path) -> dict[int, list[WitnessAttestation]]:
    """Devuelve ``{sequence: [WitnessAttestation, ...]}`` para todos los manifests
    con al menos un witness en el archive."""
    root = witnesses_root(archive_root)
    if not root.is_dir():
        return {}
    out: dict[int, list[WitnessAttestation]] = {}
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        m = _MANIFEST_DIR_RE.match(entry.name)
        if m is None:
            continue
        seq = int(m.group(1))
        ws = list_witnesses_for_manifest(archive_root, seq)
        if ws:
            out[seq] = ws
    return out


# --------------------------------------------------------------------- writes


def persist_witness(
    attestation: WitnessAttestation,
    *,
    archive_root: Path,
) -> Path:
    """Escribe el witness atómicamente. Idempotente: si ya existe un fichero
    con el mismo ``attestation_hash``, se conserva (no se sobreescribe).
    """
    target_dir = manifest_witnesses_dir(
        archive_root, attestation.target_manifest_sequence
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{attestation.attestation_hash}.json"
    if target.exists():
        return target
    atomic_write_text(target, encode_witness(attestation))
    return target
