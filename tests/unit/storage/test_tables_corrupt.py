"""Tests adicionales sobre paths defensivos de ``aip.storage.tables``.

Cubren los modos de fallo que ``test_tables.py`` no ejercita: ficheros
Parquet corruptos, schemas inesperados, tamper de bytes, y los helpers
``verify_row_integrity`` / ``verify_row_canonicalization`` en caminos de
error explícitos.
"""

from __future__ import annotations

import hashlib as _h
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from aip.storage import layout, tables

SAMPLE_HASH = "1f4a9c0a" + "0" * 56


def _ensure(root: Path) -> Path:
    layout.ensure_archive_layout(root)
    return root


# ---------------------------------------------------------------- corrupt Parquet


def test_read_row_returns_none_when_parquet_corrupt(archive_root: Path) -> None:
    _ensure(archive_root)
    bad = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not a parquet file")

    # iter_rows y list_row_hashes ignoran ficheros ilegibles silenciosamente.
    assert list(tables.iter_rows(archive_root, "evidence")) == []
    assert tables.list_row_hashes(archive_root, "evidence") == []
    # read_row devuelve None sin crashear.
    assert tables.read_row(archive_root, "evidence", SAMPLE_HASH) is None


def test_read_row_returns_none_when_parquet_has_wrong_schema(
    archive_root: Path,
) -> None:
    _ensure(archive_root)
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Parquet legal pero sin columnas row_hash / payload_jcs.
    table = pa.table({"foo": ["bar"], "qux": [42]})
    pq.write_table(table, target)

    assert tables.read_row(archive_root, "evidence", SAMPLE_HASH) is None
    assert tables.list_row_hashes(archive_root, "evidence") == []


def test_read_row_returns_none_when_parquet_has_multiple_rows(
    archive_root: Path,
) -> None:
    _ensure(archive_root)
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "row_hash": ["a" * 64, "b" * 64],
            "payload_jcs": [b"{}", b"[]"],
        },
        schema=tables.ROW_ARROW_SCHEMA,
    )
    pq.write_table(table, target)

    assert tables.read_row(archive_root, "evidence", SAMPLE_HASH) is None


def test_iter_rows_ignores_non_parquet_files(archive_root: Path) -> None:
    _ensure(archive_root)
    # Plantamos basura junto a una fila válida; debe verse solo la válida.
    tables.append_row(archive_root, "sources", "src-1", {"id": "src-1"})
    junk = archive_root / "tables" / "sources" / "junk.txt"
    junk.write_text("not parquet")

    rows = list(tables.iter_rows(archive_root, "sources"))
    assert rows == [{"id": "src-1"}]


def test_iter_rows_handles_missing_table_dir(tmp_path: Path) -> None:
    # Archive sin layout: table_dir no existe → iterador vacío sin error.
    rows = list(tables.iter_rows(tmp_path, "evidence"))
    assert rows == []


def test_list_row_hashes_ignores_non_parquet(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "sources", "src-1", {"id": "src-1"})
    junk = archive_root / "tables" / "sources" / "leftover.tmp"
    junk.write_text("x")

    hashes = tables.list_row_hashes(archive_root, "sources")
    assert len(hashes) == 1


# ---------------------------------------------------------------- verify_row_*


def test_verify_row_integrity_false_on_corrupt_parquet(archive_root: Path) -> None:
    _ensure(archive_root)
    bad = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"definitely not parquet")
    assert tables.verify_row_integrity(bad) is False


def test_verify_row_integrity_detects_tampered_payload(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "evidence", SAMPLE_HASH, {"a": 1})
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"

    # Tampering: sobreescribimos el payload pero conservamos el row_hash declarado.
    tampered = pa.table(
        {
            "row_hash": [tables.list_row_hashes(archive_root, "evidence")[0]],
            "payload_jcs": [b'{"a":999}'],  # contenido distinto
        },
        schema=tables.ROW_ARROW_SCHEMA,
    )
    pq.write_table(tampered, target)
    assert tables.verify_row_integrity(target) is False


def test_verify_row_canonicalization_false_on_corrupt(archive_root: Path) -> None:
    _ensure(archive_root)
    bad = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"")
    assert tables.verify_row_canonicalization(bad) is False


def test_verify_row_canonicalization_false_on_non_canonical_payload(
    archive_root: Path,
) -> None:
    _ensure(archive_root)
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Payload con claves desordenadas y espacios — no canónico.
    payload = b'{ "b": 1, "a": 2 }'
    fake_hash = _h.sha256(payload).hexdigest()
    table = pa.table(
        {"row_hash": [fake_hash], "payload_jcs": [payload]},
        schema=tables.ROW_ARROW_SCHEMA,
    )
    pq.write_table(table, target)
    # row_hash coincide con sha256 del payload (integridad pasa),
    # pero el payload no es JCS-canónico.
    assert tables.verify_row_integrity(target) is True
    assert tables.verify_row_canonicalization(target) is False


def test_verify_row_canonicalization_false_on_invalid_json(
    archive_root: Path,
) -> None:
    _ensure(archive_root)
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = b"not valid json at all"
    fake_hash = _h.sha256(payload).hexdigest()
    table = pa.table(
        {"row_hash": [fake_hash], "payload_jcs": [payload]},
        schema=tables.ROW_ARROW_SCHEMA,
    )
    pq.write_table(table, target)
    assert tables.verify_row_canonicalization(target) is False


# ---------------------------------------------------------------- logical helpers


def test_logical_partition_hashes_matches_list_row_hashes(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "sources", "a", {"x": 1})
    tables.append_row(archive_root, "sources", "b", {"x": 2})
    assert tables.logical_partition_hashes(
        archive_root, "sources"
    ) == tables.list_row_hashes(archive_root, "sources")


def test_logical_row_count_matches_count_rows(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "sources", "a", {"x": 1})
    assert tables.logical_row_count(
        archive_root, "sources"
    ) == tables.count_rows(archive_root, "sources")
