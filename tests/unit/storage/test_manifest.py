"""Tests unitarios de ``aip.storage.manifest``."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aip.core.hashing import hash_object, sha256_hex
from aip.storage import layout
from aip.storage.manifest import (
    ArchiveManifest,
    TableManifest,
    _compute_blobs_root,
    _list_blob_hashes,
    compute_manifest,
    write_manifest_atomic,
)

_EMPTY_BLOBS_ROOT_HASH = hash_object([])

CANONICAL_GENERATED_AT = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.UTC)
EMPTY_LIST_HASH = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


def _canonical_schemas() -> dict[str, bytes]:
    """Esquemas sintéticos deterministas por tabla V1.

    Se usan en lugar de los esquemas reales de Parquet (Paso 7) para que el
    manifest hash sea pinnable independientemente de pyarrow.
    """
    return {name: f"schema:{name}".encode() for name in layout.V1_TABLES}


# ---------------------------------------------------------------- TableManifest


def test_table_manifest_constructs_empty() -> None:
    tm = TableManifest(
        partition_hashes=[],
        row_count=0,
        schema_hash=sha256_hex(b"schema:evidence"),
    )
    assert tm.partition_hashes == []
    assert tm.row_count == 0


def test_table_manifest_rejects_negative_row_count() -> None:
    with pytest.raises(ValidationError):
        TableManifest(
            partition_hashes=[],
            row_count=-1,
            schema_hash=sha256_hex(b"x"),
        )


def test_table_manifest_rejects_bad_partition_hash() -> None:
    with pytest.raises(ValidationError):
        TableManifest(
            partition_hashes=["not-a-hash"],
            row_count=0,
            schema_hash=sha256_hex(b"x"),
        )


def test_table_manifest_is_frozen() -> None:
    tm = TableManifest(
        partition_hashes=[],
        row_count=0,
        schema_hash=sha256_hex(b"x"),
    )
    with pytest.raises(ValidationError):
        tm.row_count = 5  # type: ignore[misc]


# ---------------------------------------------------------------- ArchiveManifest


def _make_manifest(**overrides: object) -> ArchiveManifest:
    base = {
        "schema_version": "0.1.0",
        "software_version": "0.0.1",
        "generated_at": CANONICAL_GENERATED_AT,
        "tables": {
            name: TableManifest(
                partition_hashes=[],
                row_count=0,
                schema_hash=sha256_hex(f"schema:{name}".encode()),
            )
            for name in layout.V1_TABLES
        },
        "blobs_root": EMPTY_LIST_HASH,
    }
    base.update(overrides)
    return ArchiveManifest(**base)  # type: ignore[arg-type]


def test_archive_manifest_constructs() -> None:
    m = _make_manifest()
    assert m.schema_version == "0.1.0"
    assert set(m.tables.keys()) == set(layout.V1_TABLES)


def test_archive_manifest_rejects_naive_generated_at() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _make_manifest(generated_at=dt.datetime(2026, 6, 4, 0, 0, 0))


def test_archive_manifest_rejects_subsecond_generated_at() -> None:
    with pytest.raises(ValidationError, match="microsecond"):
        _make_manifest(
            generated_at=dt.datetime(
                2026, 6, 4, 0, 0, 0, 123456, tzinfo=dt.UTC
            )
        )


def test_archive_manifest_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _make_manifest(extra_field="x")


def test_archive_manifest_is_frozen() -> None:
    m = _make_manifest()
    with pytest.raises(ValidationError):
        m.schema_version = "9.9.9"  # type: ignore[misc]


def test_archive_manifest_to_canonical_dict_serializes_datetime_as_z() -> None:
    m = _make_manifest()
    canon = m.to_canonical_dict()
    assert canon["generated_at"] == "2026-06-04T00:00:00Z"


def test_archive_manifest_canonical_dict_is_jcs_hashable() -> None:
    m = _make_manifest()
    # No debe levantar TypeError al canonicalizar (todo es str/int/bool/None/list/dict).
    h = m.manifest_hash()
    assert len(h) == 64


def test_two_identical_manifests_have_same_hash() -> None:
    m1 = _make_manifest()
    m2 = _make_manifest()
    assert m1.manifest_hash() == m2.manifest_hash()


def test_changing_generated_at_changes_hash() -> None:
    m1 = _make_manifest()
    m2 = _make_manifest(
        generated_at=dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=dt.UTC)
    )
    assert m1.manifest_hash() != m2.manifest_hash()


# ---------------------------------------------------------------- compute_manifest


def test_compute_manifest_empty_archive(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    m = compute_manifest(
        archive_root,
        schemas=_canonical_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version="0.0.1",
        schema_version="0.1.0",
    )
    # Empty archive ⇒ no blobs ⇒ blobs_root = hash(empty list).
    assert m.blobs_root == EMPTY_LIST_HASH
    for name in layout.V1_TABLES:
        tm = m.tables[name]
        assert tm.partition_hashes == []
        assert tm.row_count == 0


def test_compute_manifest_picks_up_blob(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    # Plantamos un blob sintético en CAOS.
    blob_content = b"hello blob"
    blob_hash = sha256_hex(blob_content)
    blob_path = layout.caos_path_for(archive_root, blob_hash)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(blob_content)

    m = compute_manifest(
        archive_root,
        schemas=_canonical_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version="0.0.1",
        schema_version="0.1.0",
    )
    assert m.blobs_root == hash_object([blob_hash])


def test_compute_manifest_blobs_root_independent_of_disk_order(
    archive_root: Path,
) -> None:
    layout.ensure_archive_layout(archive_root)
    # Plantamos dos blobs en orden inverso al de hash; el blobs_root debe
    # ser independiente del orden de creación porque ordenamos por hash.
    blobs = [b"alpha", b"beta", b"gamma"]
    hashes = [sha256_hex(b) for b in blobs]
    for blob, h in zip(blobs, hashes, strict=True):
        p = layout.caos_path_for(archive_root, h)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)

    m = compute_manifest(
        archive_root,
        schemas=_canonical_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version="0.0.1",
        schema_version="0.1.0",
    )
    # Recomputa explícitamente la raíz esperada con sort de hashes.
    assert m.blobs_root == hash_object(sorted(hashes))


def test_compute_manifest_requires_all_v1_table_schemas(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    partial = {name: b"x" for name in list(layout.V1_TABLES)[:2]}
    with pytest.raises(ValueError, match="missing"):
        compute_manifest(
            archive_root,
            schemas=partial,
            generated_at=CANONICAL_GENERATED_AT,
            software_version="0.0.1",
            schema_version="0.1.0",
        )


# ---------------------------------------------------------------- write_manifest_atomic


def test_write_manifest_atomic_creates_file(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    m = compute_manifest(
        archive_root,
        schemas=_canonical_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version="0.0.1",
        schema_version="0.1.0",
    )
    target = archive_root / layout.MANIFEST_FILENAME
    write_manifest_atomic(target, m)

    assert target.is_file()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.1.0"
    assert data["generated_at"] == "2026-06-04T00:00:00Z"
    assert set(data["tables"].keys()) == set(layout.V1_TABLES)


def test_write_manifest_atomic_no_tmp_left(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    m = compute_manifest(
        archive_root,
        schemas=_canonical_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version="0.0.1",
        schema_version="0.1.0",
    )
    target = archive_root / layout.MANIFEST_FILENAME
    write_manifest_atomic(target, m)
    # No quedan ficheros .tmp sueltos en el directorio del archive root.
    assert not list(archive_root.glob("*.tmp"))


# ---------------------------------------------------------------- _list_blob_hashes (CAOS corrupto)
# Las ramas defensivas de ``_list_blob_hashes`` (skips silenciosos sobre
# entradas que no encajan con el contrato del CAOS) sólo se ejercen cuando
# el disco está parcialmente corrupto o cuando un agente externo dejó
# residuos. Cubrir cada rama explícitamente blinda la canonicalización del
# ``blobs_root`` (P5 — reproducibilidad bit a bit) ante FS anómalo.


def test_list_blob_hashes_returns_empty_when_objects_dir_missing(
    archive_root: Path,
) -> None:
    # Archive root vacío: no existe `objects/sha256/`.
    assert _list_blob_hashes(archive_root) == []


def test_list_blob_hashes_skips_files_at_prefix_level(archive_root: Path) -> None:
    # Un fichero (no directorio) bajo `objects/sha256/` debe ser ignorado.
    objects_root = archive_root / layout.OBJECTS_DIRNAME / layout.SHA256_ALGO_DIRNAME
    objects_root.mkdir(parents=True, exist_ok=True)
    rogue_file = objects_root / "rogue.txt"
    rogue_file.write_bytes(b"not a prefix dir")

    assert _list_blob_hashes(archive_root) == []


def test_list_blob_hashes_skips_prefix_dirs_with_wrong_length(
    archive_root: Path,
) -> None:
    # Subdirs de longitud != 2 chars deben ignorarse (no son prefijos CAOS).
    objects_root = archive_root / layout.OBJECTS_DIRNAME / layout.SHA256_ALGO_DIRNAME
    objects_root.mkdir(parents=True, exist_ok=True)
    (objects_root / "x").mkdir()
    (objects_root / "xyz").mkdir()
    (objects_root / "xxxx").mkdir()

    assert _list_blob_hashes(archive_root) == []


def test_list_blob_hashes_skips_subdirs_under_prefix(archive_root: Path) -> None:
    # Dentro de `aa/` un subdir (no fichero) debe ignorarse.
    objects_root = archive_root / layout.OBJECTS_DIRNAME / layout.SHA256_ALGO_DIRNAME
    prefix = objects_root / "aa"
    prefix.mkdir(parents=True, exist_ok=True)
    (prefix / "nested-dir").mkdir()

    assert _list_blob_hashes(archive_root) == []


def test_list_blob_hashes_skips_blob_names_with_wrong_length(
    archive_root: Path,
) -> None:
    # Ficheros bajo `aa/` con nombre de longitud != 62 chars no son blobs.
    objects_root = archive_root / layout.OBJECTS_DIRNAME / layout.SHA256_ALGO_DIRNAME
    prefix = objects_root / "aa"
    prefix.mkdir(parents=True, exist_ok=True)
    (prefix / "too-short").write_bytes(b"x")
    (prefix / ("z" * 61)).write_bytes(b"x")
    (prefix / ("z" * 63)).write_bytes(b"x")

    assert _list_blob_hashes(archive_root) == []


def test_list_blob_hashes_picks_only_valid_caos_entries(archive_root: Path) -> None:
    # Mezcla: una entrada válida + residuos varios. Sólo la válida sobrevive.
    objects_root = archive_root / layout.OBJECTS_DIRNAME / layout.SHA256_ALGO_DIRNAME
    valid_prefix = objects_root / "aa"
    valid_prefix.mkdir(parents=True, exist_ok=True)
    valid_blob_name = "b" * 62
    (valid_prefix / valid_blob_name).write_bytes(b"payload")

    # Residuos: prefix wrong length, file at prefix level, subdir bajo prefix
    # válido, fichero bajo prefix válido con nombre wrong length.
    (objects_root / "xyz").mkdir()
    (objects_root / "rogue.txt").write_bytes(b"x")
    (valid_prefix / "nested").mkdir()
    (valid_prefix / ("z" * 60)).write_bytes(b"x")

    assert _list_blob_hashes(archive_root) == ["aa" + valid_blob_name]


def test_compute_blobs_root_on_empty_archive_is_canonical(
    archive_root: Path,
) -> None:
    # ``blobs_root`` de un CAOS inexistente debe ser hash de lista vacía.
    # Esto fija la invariante que entra en ``EXPECTED_EMPTY_MANIFEST_HASH``.
    assert _compute_blobs_root(archive_root) == _EMPTY_BLOBS_ROOT_HASH
