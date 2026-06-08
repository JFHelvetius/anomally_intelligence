"""Tests unitarios de ``aip.storage.tables``."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from aip.core.hashing import hash_object, sha256_hex
from aip.storage import layout, tables
from aip.storage.manifest import compute_manifest

SAMPLE_HASH = "1f4a9c0a" + "0" * 56


def _ensure(root: Path) -> Path:
    layout.ensure_archive_layout(root)
    return root


# ---------------------------------------------------------------- schemas


def test_get_schemas_returns_all_v1_tables() -> None:
    schemas = tables.get_schemas()
    assert set(schemas.keys()) == set(layout.V1_TABLES)


def test_get_schemas_canonical_bytes_per_table() -> None:
    schemas = tables.get_schemas()
    for name in layout.V1_TABLES:
        assert schemas[name] == f"schema:{name}".encode()


def test_get_schemas_returns_copy() -> None:
    a = tables.get_schemas()
    b = tables.get_schemas()
    a["evidence"] = b"tampered"
    assert b["evidence"] == b"schema:evidence"


# ---------------------------------------------------------------- append_row


def test_append_row_writes_file(archive_root: Path) -> None:
    _ensure(archive_root)
    payload = {"hash": SAMPLE_HASH, "kind": "document_scan"}
    row_hash = tables.append_row(archive_root, "evidence", SAMPLE_HASH, payload)

    expected_hash = sha256_hex(b'{"hash":"' + SAMPLE_HASH.encode() + b'","kind":"document_scan"}')
    assert row_hash == expected_hash

    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    assert target.is_file()


def test_append_row_idempotent_same_payload(archive_root: Path) -> None:
    _ensure(archive_root)
    payload = {"id": "blue-book-nara", "kind": "government_archive"}
    h1 = tables.append_row(archive_root, "sources", "blue-book-nara", payload)
    h2 = tables.append_row(archive_root, "sources", "blue-book-nara", payload)
    assert h1 == h2


def test_append_row_overwrites_when_payload_changes(archive_root: Path) -> None:
    _ensure(archive_root)
    h1 = tables.append_row(
        archive_root, "sources", "blue-book-nara", {"id": "blue-book-nara", "v": 1}
    )
    h2 = tables.append_row(
        archive_root, "sources", "blue-book-nara", {"id": "blue-book-nara", "v": 2}
    )
    assert h1 != h2

    # Lectura devuelve la versión más reciente.
    data = tables.read_row(archive_root, "sources", "blue-book-nara")
    assert data == {"id": "blue-book-nara", "v": 2}


def test_append_row_rejects_unknown_table(archive_root: Path) -> None:
    _ensure(archive_root)
    with pytest.raises(ValueError, match="unknown V1 table"):
        tables.append_row(archive_root, "claims", "x", {"x": 1})


def test_append_row_rejects_empty_row_id(archive_root: Path) -> None:
    _ensure(archive_root)
    with pytest.raises(ValueError):
        tables.append_row(archive_root, "evidence", "", {})


def test_append_row_rejects_bad_filename_chars(archive_root: Path) -> None:
    _ensure(archive_root)
    with pytest.raises(ValueError):
        tables.append_row(archive_root, "evidence", "../escape", {})
    with pytest.raises(ValueError):
        tables.append_row(archive_root, "evidence", "spaces here", {})


def test_append_row_rejects_float_payload(archive_root: Path) -> None:
    _ensure(archive_root)
    with pytest.raises(TypeError):
        tables.append_row(archive_root, "evidence", SAMPLE_HASH, {"x": 3.14})


def test_append_row_no_tmp_left_behind(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "evidence", SAMPLE_HASH, {"a": 1})
    table_dir = archive_root / "tables" / "evidence"
    assert not any(p.suffix.endswith(".tmp") for p in table_dir.iterdir())


# ---------------------------------------------------------------- read_row


def test_read_row_roundtrip(archive_root: Path) -> None:
    _ensure(archive_root)
    payload = {"hash": SAMPLE_HASH, "size_bytes": 123, "kind": "document_scan"}
    tables.append_row(archive_root, "evidence", SAMPLE_HASH, payload)
    got = tables.read_row(archive_root, "evidence", SAMPLE_HASH)
    assert got == payload


def test_read_row_returns_none_when_missing(archive_root: Path) -> None:
    _ensure(archive_root)
    assert tables.read_row(archive_root, "evidence", SAMPLE_HASH) is None


def test_read_row_returns_none_when_table_dir_missing(archive_root: Path) -> None:
    # `archive_root` exists but no ensure_archive_layout — table dir absent.
    assert tables.read_row(archive_root, "evidence", SAMPLE_HASH) is None


# ---------------------------------------------------------------- iter_rows


def test_iter_rows_empty_table(archive_root: Path) -> None:
    _ensure(archive_root)
    assert list(tables.iter_rows(archive_root, "evidence")) == []


def test_iter_rows_returns_all_rows_in_sorted_filename_order(
    archive_root: Path,
) -> None:
    _ensure(archive_root)
    payloads = [
        ("aaa-source", {"id": "aaa-source", "kind": "government_archive"}),
        ("zzz-source", {"id": "zzz-source", "kind": "civilian_organization"}),
        ("mmm-source", {"id": "mmm-source", "kind": "news_outlet"}),
    ]
    for rid, payload in payloads:
        tables.append_row(archive_root, "sources", rid, payload)

    got_ids = [row["id"] for row in tables.iter_rows(archive_root, "sources")]
    assert got_ids == ["aaa-source", "mmm-source", "zzz-source"]


# ---------------------------------------------------------------- list_row_hashes & count


def test_list_row_hashes_empty(archive_root: Path) -> None:
    _ensure(archive_root)
    assert tables.list_row_hashes(archive_root, "evidence") == []


def test_list_row_hashes_returns_sorted_unique(archive_root: Path) -> None:
    _ensure(archive_root)
    payloads = [
        ("hash-a", {"a": 1}),
        ("hash-b", {"b": 2}),
        ("hash-c", {"c": 3}),
    ]
    expected_hashes = []
    for rid, p in payloads:
        h = tables.append_row(archive_root, "sources", rid, p)
        expected_hashes.append(h)

    listed = tables.list_row_hashes(archive_root, "sources")
    assert listed == sorted(expected_hashes)


def test_count_rows_matches_appended(archive_root: Path) -> None:
    _ensure(archive_root)
    assert tables.count_rows(archive_root, "sources") == 0
    tables.append_row(archive_root, "sources", "src-1", {"id": "src-1"})
    assert tables.count_rows(archive_root, "sources") == 1
    tables.append_row(archive_root, "sources", "src-2", {"id": "src-2"})
    assert tables.count_rows(archive_root, "sources") == 2


# ---------------------------------------------------------------- integrity


def test_verify_row_integrity_ok(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "evidence", SAMPLE_HASH, {"a": 1})
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    assert tables.verify_row_integrity(target) is True


def test_verify_row_canonicalization_ok(archive_root: Path) -> None:
    _ensure(archive_root)
    tables.append_row(archive_root, "evidence", SAMPLE_HASH, {"b": 1, "a": 2})
    target = archive_root / "tables" / "evidence" / f"{SAMPLE_HASH}.parquet"
    assert tables.verify_row_canonicalization(target) is True


# ---------------------------------------------------------------- logical helpers


def test_logical_blobs_root_empty_list() -> None:
    # Mismo valor pinned que en test_manifest_hash.
    assert tables.logical_blobs_root([]) == hash_object([])


def test_logical_blobs_root_independent_of_input_order() -> None:
    h1 = tables.logical_blobs_root(["a" * 64, "b" * 64, "c" * 64])
    h2 = tables.logical_blobs_root(["c" * 64, "a" * 64, "b" * 64])
    assert h1 == h2


# ---------------------------------------------------------------- integración con manifest


def test_manifest_hash_changes_when_row_appended(archive_root: Path) -> None:
    # Confirma que añadir una fila a una tabla altera el manifest hash
    # (validación end-to-end de Paso 6 + Paso 7).
    layout.ensure_archive_layout(archive_root)
    generated_at = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.UTC)

    m_empty = compute_manifest(
        archive_root,
        schemas=tables.get_schemas(),
        generated_at=generated_at,
        software_version="0.0.1",
        schema_version="0.1.0",
    )

    tables.append_row(archive_root, "sources", "blue-book-nara", {"id": "blue-book-nara"})

    m_one = compute_manifest(
        archive_root,
        schemas=tables.get_schemas(),
        generated_at=generated_at,
        software_version="0.0.1",
        schema_version="0.1.0",
    )

    assert m_empty.manifest_hash() != m_one.manifest_hash()
    assert m_one.tables["sources"].row_count == 1
    assert len(m_one.tables["sources"].partition_hashes) == 1
