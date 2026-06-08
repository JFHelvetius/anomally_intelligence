"""Audit log append-only con cadena de hashes (ADR-0019, ADR-0030 S3).

Módulos:

- :mod:`aip.audit.log` — escritura y lectura de entradas, cadena de hashes,
  bootstrap del archive.
- :mod:`aip.audit.verify` — recorrido y comprobación de integridad de la cadena.
- :mod:`aip.audit.archive_state` — ``ArchiveSnapshot`` (ADR-0042): combina
  ``manifest_hash`` + ``audit_log_head_hash`` en un único valor JCS-canónico
  atestable. Read-only.

Restricción de dependencias (ADR-0030 S3): ``audit`` importa desde ``core`` y
``storage``, nunca desde ``cli``.
"""

from __future__ import annotations

from aip.audit.archive_state import (
    ARCHIVE_SNAPSHOT_SCHEMA_VERSION,
    ArchiveSnapshot,
    compute_archive_snapshot,
    compute_snapshot_hash,
    decode_archive_snapshot,
    encode_archive_snapshot,
    verify_archive_snapshot_hash,
)

__all__ = [
    "ARCHIVE_SNAPSHOT_SCHEMA_VERSION",
    "ArchiveSnapshot",
    "compute_archive_snapshot",
    "compute_snapshot_hash",
    "decode_archive_snapshot",
    "encode_archive_snapshot",
    "verify_archive_snapshot_hash",
]
