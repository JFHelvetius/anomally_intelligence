"""Recolección read-only del estado de un archive AIP para transparency manifests.

Lee:

- ``manifest.json`` (archive manifest hash interno — ADR-0016).
- ``audit.log`` (cabeza de cadena + conteo).
- Conteos por dominio: ``evidence`` (rows en Parquet),
  ``attestations/*.json``, ``workspaces/*.json``, ``timelines/*.json``,
  ``snapshots/*.json``, ``justifications/*.json``.

Esta función es pura: no muta el archive, no escribe nada. El resultado
alimenta directamente :func:`aip.transparency.sign_manifest`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aip.audit import log as audit_log
from aip.errors import AIPError
from aip.storage.layout import MANIFEST_FILENAME
from aip.storage.manifest import ArchiveManifest
from aip.storage.tables import count_rows

_EVIDENCE_TABLE = "evidence"

_DERIVED_DIRS = {
    "attestations":   "attestations",
    "workspaces":     "workspaces",
    "timelines":      "timelines",
    "snapshots":      "snapshots",
    "justifications": "justifications",
}


@dataclass(frozen=True)
class ArchiveState:
    """Snapshot del estado de un archive en un instante de lectura.

    Atributos en el mismo orden que los parámetros de
    :func:`aip.transparency.sign_manifest` para reutilización directa.
    """

    archive_manifest_hash: str
    audit_chain_head_hash: str
    audit_entry_count: int
    evidence_count: int
    attestation_count: int
    workspace_count: int
    timeline_count: int
    snapshot_count: int
    justification_count: int


def _count_json_files(d: Path) -> int:
    if not d.is_dir():
        return 0
    return sum(1 for f in d.iterdir() if f.is_file() and f.suffix == ".json")


def _read_archive_manifest_hash(archive_root: Path) -> str:
    """Lee ``manifest.json`` y recomputa su hash canónico.

    Recomputamos en vez de confiar en un valor cacheado: la propiedad
    "el manifest pinned hashea esto" debe demostrarse en cada lectura.
    """
    target = archive_root / MANIFEST_FILENAME
    if not target.is_file():
        raise AIPError(
            f"archive manifest not found at {target}. "
            "Archive must be bootstrapped before publishing a transparency manifest."
        )
    raw = target.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIPError(
            f"archive manifest at {target} is not valid JSON: {exc}"
        ) from exc
    manifest = ArchiveManifest.model_validate(data)
    return manifest.manifest_hash()


def _read_audit_state(archive_root: Path) -> tuple[str, int]:
    """Devuelve (head_hash, count).

    Para un archive recién bootstrapped, ``count >= 1`` y el head hash es
    el de la entry ``ARCHIVE_BOOTSTRAP``. Un archive sin audit log es
    inválido para publicar.
    """
    last = audit_log.last_entry(archive_root)
    if last is None:
        raise AIPError(
            "audit log is empty or missing. "
            "Archive must be bootstrapped before publishing a transparency manifest."
        )
    count = audit_log.count_entries(archive_root)
    return last.entry_hash, count


def collect_archive_state(archive_root: Path) -> ArchiveState:
    """Lee el estado completo del archive en este instante.

    Read-only. Si el archive está malformado (manifest ausente, audit log
    vacío) levanta :class:`aip.errors.AIPError`.
    """
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found or not a directory: {archive_root}")

    archive_hash = _read_archive_manifest_hash(archive_root)
    audit_head, audit_count = _read_audit_state(archive_root)

    return ArchiveState(
        archive_manifest_hash=archive_hash,
        audit_chain_head_hash=audit_head,
        audit_entry_count=audit_count,
        evidence_count=count_rows(archive_root, _EVIDENCE_TABLE),
        attestation_count=_count_json_files(archive_root / _DERIVED_DIRS["attestations"]),
        workspace_count=_count_json_files(archive_root / _DERIVED_DIRS["workspaces"]),
        timeline_count=_count_json_files(archive_root / _DERIVED_DIRS["timelines"]),
        snapshot_count=_count_json_files(archive_root / _DERIVED_DIRS["snapshots"]),
        justification_count=_count_json_files(archive_root / _DERIVED_DIRS["justifications"]),
    )
