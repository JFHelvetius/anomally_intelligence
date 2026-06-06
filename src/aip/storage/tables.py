"""Capa append-only sobre tablas Parquet (ADR-0015, ADR-0024).

V1 implementa un patrón **una fila por fichero Parquet**, donde:

- El nombre del fichero codifica la identidad de la fila (``row_id``).
- El payload se almacena como bytes JCS-canonicalizados en una columna
  binaria, junto a una columna ``row_hash`` con el SHA-256 del payload.
- El esquema Arrow es idéntico para todas las tablas V1 (``row_hash`` +
  ``payload_jcs``). El ``schema_hash`` por tabla **no** se deriva del schema
  Arrow real, sino de una identidad semántica por tabla. Esta separación es
  consistente con ADR-0024 §formato canónico vs. motor: el hash del manifest
  describe el contenido lógico, no los bytes Parquet (que pueden variar
  entre versiones del writer).

Trade-offs declarados (ADR-0024 L2, ADR-0031 R5):

- Sin queries columnares reales: el payload va en bytes opacos. Aceptable
  para V1 (≤ pocos rows por tabla en la demo Pre-F1.C). Cualquier consulta
  por campos no-identidad recorre todos los ficheros.
- Bytes Parquet no son hasheables como identidad lógica entre writers; por
  eso la canonicalización vive en el payload JCS, no en el fichero entero.
- El nombre del fichero es la identidad. Si dos rows distintos colisionan
  en ``row_id``, la segunda escritura sobreescribe — pero el caller debe
  garantizar unicidad de ``row_id`` por tabla (V1: Evidence.hash, Source.id,
  Provenance.evidence_hash, ``<evidence_hash>__step<N>`` para steps).

Restricción de dependencias (ADR-0030 S2): este módulo importa desde
``aip.core`` y desde ``aip.storage.layout``. Nunca desde ``audit`` o ``cli``.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pyarrow as pa
import pyarrow.parquet as pq

from aip.core.hashing import JsonValue, hash_object, jcs_canonicalize, sha256_hex
from aip.storage.layout import TABLES_DIRNAME, V1_TABLES

# --------------------------------------------------------------------- constants

# Esquema Arrow único para todas las tablas V1. Cada fichero contiene una sola
# fila con (row_hash, payload_jcs).
ROW_ARROW_SCHEMA: Final[pa.Schema] = pa.schema(
    [
        pa.field("row_hash", pa.string(), nullable=False),
        pa.field("payload_jcs", pa.binary(), nullable=False),
    ]
)

# Identidad semántica del esquema lógico por tabla. Estas bytes se hashean
# para producir el ``schema_hash`` del :class:`TableManifest`. Son las mismas
# que el manifest hash pinned del Paso 6 (test_manifest_hash.py).
_SEMANTIC_SCHEMA_BYTES: Final[dict[str, bytes]] = {
    name: f"schema:{name}".encode() for name in V1_TABLES
}

# Filenames seguros: solo ASCII alfanumérico + `_` `-` `.`. Validado al
# construir paths para evitar inyección o caracteres no portables.
_SAFE_FILENAME_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-]+$")

_PARQUET_SUFFIX: Final[str] = ".parquet"


# --------------------------------------------------------------------- schema accessor


def get_schemas() -> dict[str, bytes]:
    """Bytes canónicos de los esquemas lógicos por tabla V1.

    Estos son los bytes que :func:`aip.storage.manifest.compute_manifest`
    espera en su parámetro ``schemas``. Mantenerlos estables es prerrequisito
    de que el ``manifest_hash`` sea reproducible bit a bit.
    """
    return dict(_SEMANTIC_SCHEMA_BYTES)


# --------------------------------------------------------------------- helpers


def _validate_table(table_name: str) -> None:
    if table_name not in V1_TABLES:
        raise ValueError(
            f"unknown V1 table {table_name!r}; expected one of {list(V1_TABLES)}."
        )


def _validate_row_id(row_id: str) -> None:
    if not row_id:
        raise ValueError("row_id must not be empty.")
    if not _SAFE_FILENAME_RE.match(row_id):
        raise ValueError(
            f"row_id {row_id!r} contains characters outside [A-Za-z0-9._-]. "
            "Use deterministic ASCII identifiers."
        )


def _path_for(root: Path, table_name: str, row_id: str) -> Path:
    return root / TABLES_DIRNAME / table_name / f"{row_id}{_PARQUET_SUFFIX}"


# --------------------------------------------------------------------- writes


def append_row(
    root: Path,
    table_name: str,
    row_id: str,
    payload: JsonValue,
) -> str:
    """Escribe una fila a la tabla ``table_name`` bajo identidad ``row_id``.

    Args:
        root: Raíz del archive.
        table_name: Nombre de tabla (debe estar en :data:`V1_TABLES`).
        row_id: Identidad textual ASCII del row. Forma el nombre del fichero.
        payload: Estructura JCS-compatible (sin floats, sin bytes, etc.).

    Returns:
        El ``row_hash`` (SHA-256 hex del JCS del payload).

    Idempotencia: si el fichero ya existe y su ``row_hash`` coincide, se
    deja tal cual. Si existe pero con distinto ``row_hash``, se sobreescribe
    atómicamente (el caller debe entender la semántica de ``row_id``).
    """
    _validate_table(table_name)
    _validate_row_id(row_id)

    payload_bytes = jcs_canonicalize(payload)
    row_hash = sha256_hex(payload_bytes)

    target = _path_for(root, table_name, row_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_file():
        existing = _read_row_hash_and_payload(target)
        if existing is not None and existing[0] == row_hash:
            return row_hash  # idempotent no-op

    table = pa.Table.from_pylist(
        [{"row_hash": row_hash, "payload_jcs": payload_bytes}],
        schema=ROW_ARROW_SCHEMA,
    )

    tmp = target.with_suffix(target.suffix + ".tmp")
    pq.write_table(table, tmp, compression="zstd", use_dictionary=False)
    os.replace(tmp, target)
    return row_hash


# --------------------------------------------------------------------- reads


def read_row(
    root: Path,
    table_name: str,
    row_id: str,
) -> JsonValue | None:
    """Lee una fila por su identidad. ``None`` si no existe."""
    _validate_table(table_name)
    _validate_row_id(row_id)

    target = _path_for(root, table_name, row_id)
    if not target.is_file():
        return None
    pair = _read_row_hash_and_payload(target)
    if pair is None:
        return None
    _, payload_bytes = pair
    # ``json.loads`` está tipado como ``Any``; sabemos por construcción
    # (escritura via :func:`append_row`) que el payload es JsonValue.
    return json.loads(payload_bytes.decode("utf-8"))  # type: ignore[no-any-return]


def iter_rows(root: Path, table_name: str) -> Iterator[JsonValue]:
    """Itera todas las filas de una tabla. Orden por nombre de fichero."""
    _validate_table(table_name)
    table_dir = root / TABLES_DIRNAME / table_name
    if not table_dir.is_dir():
        return
    for entry in sorted(table_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.suffix != _PARQUET_SUFFIX:
            continue
        pair = _read_row_hash_and_payload(entry)
        if pair is None:
            continue
        yield json.loads(pair[1].decode("utf-8"))


def list_row_hashes(root: Path, table_name: str) -> list[str]:
    """Lista de ``row_hash`` de la tabla, ordenada por hash.

    Útil para el cálculo del ``TableManifest.partition_hashes`` lógico.
    """
    _validate_table(table_name)
    table_dir = root / TABLES_DIRNAME / table_name
    if not table_dir.is_dir():
        return []
    hashes: list[str] = []
    for entry in table_dir.iterdir():
        if not entry.is_file() or entry.suffix != _PARQUET_SUFFIX:
            continue
        pair = _read_row_hash_and_payload(entry)
        if pair is None:
            continue
        hashes.append(pair[0])
    hashes.sort()
    return hashes


def count_rows(root: Path, table_name: str) -> int:
    """Número de filas en la tabla."""
    return len(list_row_hashes(root, table_name))


# --------------------------------------------------------------------- low-level


def _read_row_hash_and_payload(path: Path) -> tuple[str, bytes] | None:
    """Devuelve ``(row_hash, payload_jcs)`` o ``None`` si el fichero no
    cumple el esquema esperado."""
    try:
        table = pq.read_table(path)
    except Exception:  # pyarrow lanza ArrowInvalid u otros; capturamos amplio
        return None
    if table.num_rows != 1:
        return None
    try:
        row_hash = table.column("row_hash")[0].as_py()
        payload_bytes = table.column("payload_jcs")[0].as_py()
    except (KeyError, IndexError):
        return None
    if not isinstance(row_hash, str) or not isinstance(payload_bytes, (bytes, bytearray)):
        return None
    return row_hash, bytes(payload_bytes)


# --------------------------------------------------------------------- assertion


def verify_row_integrity(path: Path) -> bool:
    """Verifica que ``row_hash`` del fichero coincida con ``sha256(payload_jcs)``.

    Defensa frente a tampering del payload sin actualizar el hash declarado.
    """
    pair = _read_row_hash_and_payload(path)
    if pair is None:
        return False
    row_hash, payload_bytes = pair
    return sha256_hex(payload_bytes) == row_hash


def verify_row_canonicalization(path: Path) -> bool:
    """Verifica que el ``payload_jcs`` esté efectivamente canonicalizado.

    Recanonicaliza el payload re-deserializado y compara byte a byte. Si
    el caller escribió un JSON no-canónico (e.g., claves desordenadas), la
    verificación falla.
    """
    pair = _read_row_hash_and_payload(path)
    if pair is None:
        return False
    _, payload_bytes = pair
    try:
        decoded = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return False
    return jcs_canonicalize(decoded) == payload_bytes


# --------------------------------------------------------------------- manifest helper

# Compatibilidad con ``compute_manifest``: cuando ``storage.manifest`` quiera
# usar el contenido lógico (no los bytes Parquet) para ``partition_hashes``,
# delega aquí.


def logical_partition_hashes(root: Path, table_name: str) -> list[str]:
    """``partition_hashes`` lógicos para el manifest: lista ordenada de
    ``row_hash`` de la tabla. Estable independientemente del writer Parquet
    (ADR-0024 §formato canónico vs. motor)."""
    return list_row_hashes(root, table_name)


def logical_row_count(root: Path, table_name: str) -> int:
    """``row_count`` lógico para el manifest."""
    return count_rows(root, table_name)


def logical_blobs_root(blob_hashes: list[str]) -> str:
    """``blobs_root`` lógico para el manifest: hash sobre lista de hashes
    ordenada. Reexpuesto aquí para que ``storage.manifest`` pueda derivarlo
    sin acoplar a layout."""
    return hash_object(sorted(blob_hashes))
