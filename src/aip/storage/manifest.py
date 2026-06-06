"""``ArchiveManifest`` y su hash canónico (ADR-0016).

V1 implementa un subset operativo del manifest:

- ``schema_version`` (SemVer del esquema de datos).
- ``software_version`` (versión del paquete ``aip`` que generó el manifest).
- ``generated_at`` (timestamp tz-aware UTC, segundo completo, sin microsegundos).
- ``tables`` (``dict[str, TableManifest]`` cubriendo las tablas V1).
- ``blobs_root`` (hash Merkle plano sobre la lista de blobs ordenada por hash).
- ``notes`` (markdown opcional).

Campos del ADR-0016 completo deliberadamente diferidos:

- ``software_commit`` — el proyecto no asume git en V1.
- ``archives_root`` — no hay WARCs en V1 (OSINT diferido).

Reglas de canonicalización (ADR-0016 §JCS):

- :meth:`ArchiveManifest.to_canonical_dict` convierte el modelo a una estructura
  JCS-compatible: ``datetime`` se serializa como ``YYYY-MM-DDTHH:MM:SSZ`` (UTC,
  microsegundos rechazados por validador), claves se ordenan por JCS al hashear.
- :meth:`ArchiveManifest.manifest_hash` produce SHA-256 hex sobre los bytes
  JCS de la estructura canónica.

Notar: el ``manifest_hash`` cambia cuando cambia ``generated_at``. Es
intencional: cada manifest identifica una **medición** del estado del archive
en un instante concreto. Para reproducibilidad en tests, el caller inyecta
``generated_at`` explícitamente.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aip.core.hashing import hash_object, sha256_hex
from aip.storage.layout import (
    OBJECTS_DIRNAME,
    SHA256_ALGO_DIRNAME,
    V1_TABLES,
)

_SHA256_HEX_PATTERN: Final[str] = r"^[a-f0-9]{64}$"

Sha256Hex = Annotated[
    str,
    Field(pattern=_SHA256_HEX_PATTERN, min_length=64, max_length=64),
]


# --------------------------------------------------------------------- models


class TableManifest(BaseModel):
    """Estado canónico de una tabla del archive (ADR-0016)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    partition_hashes: list[Sha256Hex] = Field(default_factory=list)
    row_count: int = Field(ge=0)
    schema_hash: Sha256Hex

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "partition_hashes": list(self.partition_hashes),
            "row_count": self.row_count,
            "schema_hash": self.schema_hash,
        }


class ArchiveManifest(BaseModel):
    """Manifiesto del estado del archive en un instante (ADR-0016, V1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(min_length=1)
    software_version: str = Field(min_length=1)
    generated_at: dt.datetime
    tables: dict[str, TableManifest]
    blobs_root: Sha256Hex
    notes: str | None = None

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_tz_aware_and_subsecond_zero(
        cls, value: dt.datetime
    ) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError(
                "ArchiveManifest.generated_at must be timezone-aware (use UTC)."
            )
        if value.microsecond != 0:
            raise ValueError(
                "ArchiveManifest.generated_at must have microsecond=0 for "
                "canonical reproducibility (ADR-0024 L2)."
            )
        return value

    def to_canonical_dict(self) -> dict[str, object]:
        """Estructura JCS-compatible del manifest.

        ``generated_at`` se serializa como ``YYYY-MM-DDTHH:MM:SSZ``. Las
        tablas se ordenan por nombre para estabilidad (el JCS posterior
        las reordenará, pero ordenarlas aquí simplifica la inspección).
        """
        generated_iso = (
            self.generated_at.astimezone(dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        )
        return {
            "schema_version": self.schema_version,
            "software_version": self.software_version,
            "generated_at": generated_iso,
            "tables": {
                name: tm.to_canonical_dict()
                for name, tm in sorted(self.tables.items())
            },
            "blobs_root": self.blobs_root,
            "notes": self.notes,
        }

    def manifest_hash(self) -> str:
        """SHA-256 hex sobre la canonicalización JCS del manifest."""
        return hash_object(self.to_canonical_dict())


# --------------------------------------------------------------------- compute


def _list_blob_hashes(root: Path) -> list[str]:
    """Recorre ``<root>/objects/sha256/`` y devuelve los hashes ordenados."""
    objects_root = root / OBJECTS_DIRNAME / SHA256_ALGO_DIRNAME
    if not objects_root.is_dir():
        return []
    hashes: list[str] = []
    # Lectura determinista: ordenamos los listados a cada nivel.
    for prefix_entry in sorted(objects_root.iterdir(), key=lambda p: p.name):
        if not prefix_entry.is_dir():
            continue
        if len(prefix_entry.name) != 2:
            continue
        for blob_entry in sorted(prefix_entry.iterdir(), key=lambda p: p.name):
            if not blob_entry.is_file():
                continue
            if len(blob_entry.name) != 62:
                continue
            hashes.append(prefix_entry.name + blob_entry.name)
    return hashes


def _compute_blobs_root(root: Path) -> str:
    """Merkle root simplificado: SHA-256 sobre la lista JCS de hashes ordenada.

    Se prefiere lista plana a árbol Merkle real en V1: el coste de un árbol
    Merkle no se justifica para inventarios modestos y el resultado es
    igualmente reproducible bit a bit dada una misma colección de blobs.
    """
    return hash_object(_list_blob_hashes(root))


def _compute_table_manifest(
    root: Path,
    *,
    table_name: str,
    schema_bytes: bytes,
) -> TableManifest:
    # Hashes lógicos (sobre ``payload_jcs`` por fila), no bytes Parquet.
    # ADR-0024 §formato canónico vs. motor: el manifest describe contenido
    # lógico, estable entre versiones del writer Parquet.
    from aip.storage.tables import list_row_hashes, count_rows

    partition_hashes = list_row_hashes(root, table_name)
    row_count = count_rows(root, table_name)
    schema_hash = sha256_hex(schema_bytes)
    return TableManifest(
        partition_hashes=partition_hashes,
        row_count=row_count,
        schema_hash=schema_hash,
    )


def compute_manifest(
    root: Path,
    *,
    schemas: dict[str, bytes],
    generated_at: dt.datetime,
    software_version: str,
    schema_version: str,
    notes: str | None = None,
) -> ArchiveManifest:
    """Construye un :class:`ArchiveManifest` desde el estado actual del archive.

    Args:
        root: Raíz del archive (debe contener al menos el layout V1).
        schemas: Por tabla V1, los bytes canónicos del esquema (se hashean).
            Todas las tablas en :data:`V1_TABLES` deben estar presentes; el
            extra se ignora silenciosamente.
        generated_at: Instante UTC tz-aware al que se atribuye este snapshot.
        software_version: Versión del paquete ``aip`` que genera el manifest.
        schema_version: SemVer del esquema lógico de datos (ADR-0016).

    Raises:
        ValueError: si falta el esquema canónico de alguna tabla V1.
    """
    missing = [t for t in V1_TABLES if t not in schemas]
    if missing:
        raise ValueError(
            f"compute_manifest: missing canonical schema bytes for V1 tables: "
            f"{missing}. Provide one entry per V1_TABLES in `schemas`."
        )

    tables: dict[str, TableManifest] = {
        name: _compute_table_manifest(
            root,
            table_name=name,
            schema_bytes=schemas[name],
        )
        for name in V1_TABLES
    }

    return ArchiveManifest(
        schema_version=schema_version,
        software_version=software_version,
        generated_at=generated_at,
        tables=tables,
        blobs_root=_compute_blobs_root(root),
        notes=notes,
    )


# --------------------------------------------------------------------- I/O helpers
# Notar: la escritura/lectura física del fichero ``manifest.json`` se delega a
# ``cli`` (Paso 11) cuando aplique. Aquí solo se ofrecen helpers atómicos para
# evitar manifestos corruptos por escritura interrumpida.


def write_manifest_atomic(
    target: Path,
    manifest: ArchiveManifest,
) -> None:
    """Escribe el manifest al path ``target`` de forma atómica.

    Estrategia: escribir a un fichero temporal en el mismo directorio y luego
    ``os.replace``. Defensa mínima contra ficheros parcialmente escritos.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    # Serializamos a JSON canónico (JCS-compatible). Para legibilidad humana
    # **no** usamos JCS literal en el fichero — usamos la forma indentada del
    # mismo contenido. El hash que importa es el de la forma canónica
    # devuelta por :meth:`manifest_hash`, no la del fichero en disco.
    import json

    payload = manifest.to_canonical_dict()
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)
