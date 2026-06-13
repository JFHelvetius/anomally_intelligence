"""Persistencia y carga de manifests de transparency log.

Layout en el archive:

    <archive>/transparency/
        manifest-000000.json    ← sequence=0 (bootstrap)
        manifest-000001.json
        manifest-000002.json
        latest.json             ← copia del manifest más reciente (UX)

Nombre del fichero: ``manifest-{sequence:06d}.json``. 6 dígitos cubren hasta
~1M manifests por archive antes de necesitar 7+ — suficiente para décadas a
ritmos razonables (1 publish por hora = 8760/año).

El fichero ``latest.json`` es una conveniencia: el portal de verificación
público lo lee primero para conocer la cabeza de la cadena. No es load-bearing
— se puede regenerar siempre desde los ``manifest-*.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from aip.errors import AIPError
from aip.storage.atomic_io import atomic_write_text
from aip.transparency.models import TransparencyManifest

TRANSPARENCY_DIRNAME: Final[str] = "transparency"
LATEST_FILENAME: Final[str] = "latest.json"

_MANIFEST_FILENAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^manifest-(\d{6,})\.json$"
)


class TransparencyError(AIPError):
    """Error genérico de operación sobre el transparency log."""

    cli_exit_code = 1


# --------------------------------------------------------------------- paths


def transparency_dir(archive_root: Path) -> Path:
    return archive_root / TRANSPARENCY_DIRNAME


def manifest_filename(sequence: int) -> str:
    if sequence < 0:
        raise ValueError(f"sequence must be >= 0, got {sequence}.")
    return f"manifest-{sequence:06d}.json"


def manifest_path(archive_root: Path, sequence: int) -> Path:
    return transparency_dir(archive_root) / manifest_filename(sequence)


def latest_path(archive_root: Path) -> Path:
    return transparency_dir(archive_root) / LATEST_FILENAME


# --------------------------------------------------------------------- encode / decode


def encode_manifest(m: TransparencyManifest) -> str:
    """Serializa el manifest a JSON indentado, claves ordenadas.

    Mismo estilo que :func:`aip.attestation.encode_attestation`. El hash
    canónico no depende de esta forma — está fijado por ``manifest_hash``,
    que se computa desde JCS.
    """
    data = {
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
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def decode_manifest(payload: str) -> TransparencyManifest:
    data = json.loads(payload)
    return TransparencyManifest(
        sequence=data["sequence"],
        signed_at=data["signed_at"],
        manifest_type=data["manifest_type"],
        operator_id=data["operator_id"],
        public_key_fingerprint=data["public_key_fingerprint"],
        archive_manifest_hash=data["archive_manifest_hash"],
        audit_chain_head_hash=data["audit_chain_head_hash"],
        audit_entry_count=data["audit_entry_count"],
        evidence_count=data["evidence_count"],
        attestation_count=data["attestation_count"],
        workspace_count=data["workspace_count"],
        timeline_count=data["timeline_count"],
        snapshot_count=data["snapshot_count"],
        justification_count=data["justification_count"],
        previous_manifest_hash=data["previous_manifest_hash"],
        signature=data["signature"],
        signature_algorithm=data["signature_algorithm"],
        manifest_hash=data["manifest_hash"],
        schema_version=data.get("schema_version", "1"),
    )


# --------------------------------------------------------------------- reads


def list_sequences(archive_root: Path) -> list[int]:
    """Devuelve la lista ordenada de secuencias existentes en disco.

    Ignora ``latest.json`` y cualquier fichero que no encaje el patrón
    ``manifest-NNNNNN.json``.
    """
    d = transparency_dir(archive_root)
    if not d.is_dir():
        return []
    sequences: list[int] = []
    for entry in d.iterdir():
        if not entry.is_file():
            continue
        m = _MANIFEST_FILENAME_RE.match(entry.name)
        if m is None:
            continue
        sequences.append(int(m.group(1)))
    sequences.sort()
    return sequences


def load_manifest(archive_root: Path, sequence: int) -> TransparencyManifest:
    path = manifest_path(archive_root, sequence)
    if not path.is_file():
        raise TransparencyError(
            f"manifest sequence {sequence} not found at {path}"
        )
    return decode_manifest(path.read_text(encoding="utf-8"))


def load_latest(archive_root: Path) -> TransparencyManifest | None:
    """Devuelve el manifest más reciente, o ``None`` si no hay ninguno."""
    sequences = list_sequences(archive_root)
    if not sequences:
        return None
    return load_manifest(archive_root, sequences[-1])


def load_chain(archive_root: Path) -> list[TransparencyManifest]:
    """Carga todos los manifests en orden de secuencia."""
    return [load_manifest(archive_root, s) for s in list_sequences(archive_root)]


def detect_gaps(sequences: list[int]) -> list[int]:
    """Devuelve las secuencias *faltantes* dado un listado ordenado.

    Ejemplo: ``[0, 1, 3]`` → ``[2]``. Para un transparency log saludable
    debe estar siempre vacío.
    """
    if not sequences:
        return []
    expected = set(range(sequences[0], sequences[-1] + 1))
    actual = set(sequences)
    return sorted(expected - actual)


# --------------------------------------------------------------------- writes


def persist_manifest(
    manifest: TransparencyManifest,
    *,
    archive_root: Path,
) -> Path:
    """Escribe ``manifest-NNNNNN.json`` + actualiza ``latest.json`` atómicamente.

    Falla si el fichero de la secuencia ya existe — un publish es idempotente
    por contenido pero no por secuencia: dos manifests con sequence=N firman
    estados distintos y aceptar el segundo silenciosamente sería un bug.
    """
    d = transparency_dir(archive_root)
    d.mkdir(parents=True, exist_ok=True)
    target = manifest_path(archive_root, manifest.sequence)
    if target.exists():
        raise TransparencyError(
            f"manifest already exists for sequence {manifest.sequence} at {target}. "
            f"Refusing to overwrite — each sequence pins a single signed state."
        )
    payload = encode_manifest(manifest)
    atomic_write_text(target, payload)
    atomic_write_text(latest_path(archive_root), payload)
    return target
