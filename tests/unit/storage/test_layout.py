"""Tests unitarios de ``aip.storage.layout``."""

from __future__ import annotations

from pathlib import Path

import pytest

from aip.storage import layout

SAMPLE_HASH = "1f4a9c0a" + "0" * 56  # 64 chars hex


# ---------------------------------------------------------------- caos_path_for


def test_caos_path_for_canonical_layout(archive_root: Path) -> None:
    p = layout.caos_path_for(archive_root, SAMPLE_HASH)
    expected = (
        archive_root / "objects" / "sha256" / SAMPLE_HASH[:2] / SAMPLE_HASH[2:]
    )
    assert p == expected


def test_caos_path_for_distinct_hashes_distinct_paths(archive_root: Path) -> None:
    a = layout.caos_path_for(archive_root, "a" * 64)
    b = layout.caos_path_for(archive_root, "b" * 64)
    assert a != b


def test_caos_path_for_rejects_short_hash(archive_root: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        layout.caos_path_for(archive_root, "abc")


def test_caos_path_for_rejects_uppercase_hash(archive_root: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        layout.caos_path_for(archive_root, SAMPLE_HASH.upper())


def test_caos_path_for_rejects_non_hex(archive_root: Path) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        layout.caos_path_for(archive_root, "z" * 64)


# ---------------------------------------------------------------- caos_relative_uri_for


def test_caos_relative_uri_for_canonical_form() -> None:
    uri = layout.caos_relative_uri_for(SAMPLE_HASH)
    assert uri == f"objects/sha256/{SAMPLE_HASH[:2]}/{SAMPLE_HASH[2:]}"


def test_caos_relative_uri_for_uses_posix_separator_only() -> None:
    # Reproducibilidad cross-platform (ADR-0031 R3): siempre `/`.
    uri = layout.caos_relative_uri_for(SAMPLE_HASH)
    assert "\\" not in uri
    assert uri.count("/") == 3


def test_caos_relative_uri_for_rejects_bad_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        layout.caos_relative_uri_for("not-a-hash")


# ---------------------------------------------------------------- ensure_archive_layout


def test_ensure_creates_full_layout(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    assert (archive_root / "objects" / "sha256").is_dir()
    assert (archive_root / "tables").is_dir()
    for table in layout.V1_TABLES:
        assert (archive_root / "tables" / table).is_dir(), table


def test_ensure_is_idempotent(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    layout.ensure_archive_layout(archive_root)  # debe ser no-op
    layout.ensure_archive_layout(archive_root)
    assert (archive_root / "objects" / "sha256").is_dir()


def test_ensure_creates_root_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / "does" / "not" / "exist" / "yet"
    assert not nested.exists()
    layout.ensure_archive_layout(nested)
    assert nested.is_dir()
    assert (nested / "objects" / "sha256").is_dir()


def test_ensure_does_not_create_manifest_or_audit(archive_root: Path) -> None:
    # Los ficheros transaccionales los emite el bootstrap del primer ingest,
    # no `ensure_archive_layout`. Mantener la separación es defensa contra
    # archives "parcialmente creados pero ya con manifiesto vacío engañoso".
    layout.ensure_archive_layout(archive_root)
    assert not (archive_root / "manifest.json").exists()
    assert not (archive_root / "audit.log").exists()


def test_v1_tables_count_matches_committed_subset() -> None:
    # ADR-0023 §V1.3 + V1.4 + ADR-0030 §V1 tables.
    # Si esto cambia, requiere actualizar también la documentación.
    assert layout.V1_TABLES == (
        "evidence",
        "sources",
        "provenance",
        "provenance_steps",
        "authentication_assessments",
    )


# ---------------------------------------------------------------- is_archive


def test_is_archive_false_on_empty_dir(archive_root: Path) -> None:
    assert layout.is_archive(archive_root) is False


def test_is_archive_false_on_missing_root(tmp_path: Path) -> None:
    nonexistent = tmp_path / "ghost"
    assert layout.is_archive(nonexistent) is False


def test_is_archive_false_when_only_objects_dir(archive_root: Path) -> None:
    (archive_root / "objects" / "sha256").mkdir(parents=True)
    assert layout.is_archive(archive_root) is False


def test_is_archive_true_with_layout_and_audit_log(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    (archive_root / "audit.log").touch()
    assert layout.is_archive(archive_root) is True


def test_is_archive_true_with_layout_and_manifest(archive_root: Path) -> None:
    layout.ensure_archive_layout(archive_root)
    (archive_root / "manifest.json").touch()
    assert layout.is_archive(archive_root) is True


def test_is_archive_false_when_layout_dirs_missing(archive_root: Path) -> None:
    # Manifiesto presente pero falta tables/ — no es archive válido.
    (archive_root / "manifest.json").touch()
    assert layout.is_archive(archive_root) is False


def test_is_archive_false_on_file_path(tmp_path: Path) -> None:
    f = tmp_path / "not-a-dir"
    f.write_text("hello")
    assert layout.is_archive(f) is False
