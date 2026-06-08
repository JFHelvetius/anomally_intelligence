"""Archive State Snapshot (ADR-0042).

Artefacto JCS-canónico que combina los dos hashes archive-wide
existentes en un único valor atestable:

- ``manifest_hash`` (de ``ArchiveManifest``): pinea estado de tablas + blobs
- ``audit_log_head_hash`` (de la última ``AuditEntry``): pinea historia

Antes de ADR-0042 ambos hashes vivían separados; un operador que quisiera
atestar "el archive completo en el momento T" tenía que componerlos
manualmente. Con ``ArchiveSnapshot``, la composición es estándar,
determinista y firmable via ADR-0041.

**Read-only por construcción.** ``compute_archive_snapshot`` sólo lee; el
archive no se modifica. La persistencia (si la hay) es responsabilidad
del caller — el snapshot es un valor canónico, no estado del archive.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from aip.audit.log import (
    ZERO_HASH,
    AuditEntry,
    iter_entries,
)
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.storage import layout
from aip.storage.manifest import ArchiveManifest

ARCHIVE_SNAPSHOT_SCHEMA_VERSION: Final[str] = "1"

_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-f0-9]{64}$"
)
_ISO_UTC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@dataclass(frozen=True)
class ArchiveSnapshot:
    """Estado archive-wide en un instante, JCS-canónico y firmable.

    Cinco campos load-bearing + self-hash:

    - ``manifest_hash``: SHA-256 hex de :class:`ArchiveManifest` actual.
    - ``audit_log_head_hash``: ``entry_hash`` de la última entry del
      ``audit.log``, o :data:`aip.audit.log.ZERO_HASH` si está vacío.
    - ``audit_log_total_entries``: cardinalidad de la cadena (≥ 0).
    - ``generated_at``: ISO-8601 UTC operator-supplied (igual contrato
      que ADR-0041 §signed_at — no TSA en V1).
    - ``snapshot_hash``: JCS self-hash sobre todos los campos
      excluyendo ``snapshot_hash`` mismo. Pattern: ADR-0036 §self-hash.

    **No** prueba veracidad ni autenticación — sólo provee un valor
    canónico que combina los dos hashes archive-wide en uno solo. La
    firma criptográfica se obtiene via ``aip attestation sign`` (ADR-0041
    con ``artifact_kind="archive_snapshot"``).
    """

    manifest_hash: str
    audit_log_head_hash: str
    audit_log_total_entries: int
    generated_at: str
    snapshot_hash: str
    schema_version: str = ARCHIVE_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _SHA256_HEX_PATTERN.match(self.manifest_hash):
            raise ValueError(
                "manifest_hash must be SHA-256 hex lowercase."
            )
        if not _SHA256_HEX_PATTERN.match(self.audit_log_head_hash):
            raise ValueError(
                "audit_log_head_hash must be SHA-256 hex lowercase "
                "(use ZERO_HASH for an empty log)."
            )
        if self.audit_log_total_entries < 0:
            raise ValueError(
                "audit_log_total_entries must be >= 0."
            )
        if not _ISO_UTC_PATTERN.match(self.generated_at):
            raise ValueError(
                "generated_at must be ISO-8601 UTC of form "
                "YYYY-MM-DDTHH:MM:SSZ."
            )
        if not _SHA256_HEX_PATTERN.match(self.snapshot_hash):
            raise ValueError(
                "snapshot_hash must be SHA-256 hex lowercase."
            )


# --------------------------------------------------------------------- compute


def compute_snapshot_hash(snap: ArchiveSnapshot) -> str:
    """SHA-256 hex JCS sobre la canonicalización del snapshot exclude-self."""
    data = _snapshot_to_canonical_dict(snap)
    data.pop("snapshot_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


def _snapshot_to_canonical_dict(
    snap: ArchiveSnapshot,
) -> dict[str, object]:
    return {
        "manifest_hash": snap.manifest_hash,
        "audit_log_head_hash": snap.audit_log_head_hash,
        "audit_log_total_entries": snap.audit_log_total_entries,
        "generated_at": snap.generated_at,
        "snapshot_hash": snap.snapshot_hash,
        "schema_version": snap.schema_version,
    }


def compute_archive_snapshot(
    archive_root: Path,
    *,
    generated_at: dt.datetime,
) -> ArchiveSnapshot:
    """Construye un :class:`ArchiveSnapshot` leyendo el archive.

    Read-only: no escribe nada. Determinista respecto a
    ``(archive_state, generated_at)``: mismos bytes en el archive +
    mismo ``generated_at`` ⇒ mismo ``snapshot_hash``.

    Args:
        archive_root: Raíz del archive.
        generated_at: Instante UTC tz-aware al que se atribuye este
            snapshot. Se serializa con ``microsecond=0`` para
            reproducibility (igual contrato que ADR-0024 L2).

    Raises:
        ValueError: si ``generated_at`` no es tz-aware, o si el manifest
            no se puede deserializar.
        FileNotFoundError: si no existe el manifest del archive.
    """
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware (UTC).")
    iso_at = (
        generated_at.astimezone(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    manifest_hash = _read_manifest_hash(archive_root)
    head_hash, total = _read_audit_head(archive_root)

    partial = ArchiveSnapshot(
        manifest_hash=manifest_hash,
        audit_log_head_hash=head_hash,
        audit_log_total_entries=total,
        generated_at=iso_at,
        snapshot_hash="0" * 64,
    )
    final_hash = compute_snapshot_hash(partial)
    return ArchiveSnapshot(
        manifest_hash=manifest_hash,
        audit_log_head_hash=head_hash,
        audit_log_total_entries=total,
        generated_at=iso_at,
        snapshot_hash=final_hash,
    )


def _read_manifest_hash(archive_root: Path) -> str:
    manifest_path = archive_root / layout.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"manifest not found at {manifest_path}; cannot snapshot."
        )
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ArchiveManifest.model_validate(raw).manifest_hash()


def _read_audit_head(archive_root: Path) -> tuple[str, int]:
    """Devuelve ``(head_hash, total_entries)`` recorriendo el audit log.

    Si el log no existe o está vacío, devuelve ``(ZERO_HASH, 0)``. Esto
    permite snapshots de archives recién creados sin bootstrap (caso
    raro pero legítimo en tests).
    """
    last: AuditEntry | None = None
    total = 0
    for entry in iter_entries(archive_root):
        last = entry
        total += 1
    if last is None:
        return ZERO_HASH, 0
    return last.entry_hash, total


# --------------------------------------------------------------------- encoding


def encode_archive_snapshot(snap: ArchiveSnapshot) -> str:
    """Serializa a JSON canónico (``sort_keys=True``, indent=2, LF final)."""
    data = _snapshot_to_canonical_dict(snap)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def decode_archive_snapshot(payload: str) -> ArchiveSnapshot:
    data = json.loads(payload)
    return ArchiveSnapshot(
        manifest_hash=data["manifest_hash"],
        audit_log_head_hash=data["audit_log_head_hash"],
        audit_log_total_entries=data["audit_log_total_entries"],
        generated_at=data["generated_at"],
        snapshot_hash=data["snapshot_hash"],
        schema_version=data.get(
            "schema_version", ARCHIVE_SNAPSHOT_SCHEMA_VERSION
        ),
    )


def verify_archive_snapshot_hash(snap: ArchiveSnapshot) -> bool:
    """Recomputa ``snapshot_hash`` y compara con el declarado.

    Devuelve ``True`` si la consistencia estructural pasa. La verificación
    archive-wide completa (snapshot vs estado actual del archive) requiere
    recomputar via :func:`compute_archive_snapshot` y comparar campo a campo.
    """
    return compute_snapshot_hash(snap) == snap.snapshot_hash
