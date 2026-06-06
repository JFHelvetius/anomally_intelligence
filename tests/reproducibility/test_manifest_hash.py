"""Reproducibility tests para ``ArchiveManifest`` (ADR-0031 T3).

Pinned values en este fichero forman parte del contrato de reproducibilidad
bit a bit. Cubren dos escenarios canónicos:

1. **Archive vacío**: layout creado, sin blobs ni filas, esquemas sintéticos
   (``b"schema:<table_name>"``).
2. **Archive con un PDF de demo**: requiere los pinned values de Pre-F1.C;
   marcado :pytest:`requires_fixture` hasta que el fixture exista.

El primer caso queda fijado hoy. El segundo se desbloquea cuando el helper
``scripts/fetch_demo_fixture.py`` deja el binario y los pinned values en
``docs/phase-1/demo-evidence-selection.md``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from aip.core.hashing import sha256_hex
from aip.storage import layout
from aip.storage.manifest import compute_manifest

pytestmark = pytest.mark.reproducibility


CANONICAL_GENERATED_AT = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.timezone.utc)
CANONICAL_SOFTWARE_VERSION = "0.0.1"
CANONICAL_SCHEMA_VERSION = "0.1.0"


# ----------------------------------------------------------------- canonical hashes


# Esquemas sintéticos por tabla V1. Forman parte del input canónico de los
# pinned values; si cambian, el manifest_hash cambia.
def _synthetic_schemas() -> dict[str, bytes]:
    return {name: f"schema:{name}".encode("utf-8") for name in layout.V1_TABLES}


# Hashes de esquemas sintéticos. Pinned por tabla.
EXPECTED_SCHEMA_HASHES: dict[str, str] = {
    "evidence": "1f9d805d58d29e9e2b8a3bd8dbd81c5430dfba7aec9b336adb702571025bac05",
    "sources": "617381c20880539a9283c112460e310dc7e92be2066e9b7b7d44018f182f4683",
    "provenance": "62e34b42370a7c9a5c7df8aa52e5100bad9f8246f4153758f78288097c8d7c0e",
    "provenance_steps": "d69877b26c7ca994e40f09890eba477f18bda48071f37e78f05419b2162ceaac",
    "authentication_assessments": (
        "2d7384f43a897a2c8ec21fc9669a5835cc61e056c4f780c8cfdcb1c9c3b231df"
    ),
}

# Manifest hash canónico de un archive vacío con los inputs anteriores.
EXPECTED_EMPTY_MANIFEST_HASH = (
    "ef07ea2790e4622bae2fe590cce0898d45015da3c1cbc28ae46f55eaa77a0b82"
)


# ----------------------------------------------------------------- tests


def test_synthetic_schema_hashes_are_stable() -> None:
    """Cada esquema sintético hashea al valor pinned correspondiente."""
    for name, expected in EXPECTED_SCHEMA_HASHES.items():
        actual = sha256_hex(f"schema:{name}".encode("utf-8"))
        assert actual == expected, (
            f"schema hash drifted for table {name!r}: expected {expected}, got {actual}"
        )


def test_empty_archive_manifest_hash_is_canonical_pinned(
    archive_root: Path,
) -> None:
    """Archive vacío con inputs canónicos produce el manifest hash pinned.

    Si este valor cambia, ha cambiado alguna canonicalización del manifest,
    el set V1_TABLES, o el formato de serialización del datetime. Cualquiera
    es bug arquitectónico crítico — no se actualiza sin PR explícito que
    documente la causa.
    """
    layout.ensure_archive_layout(archive_root)
    manifest = compute_manifest(
        archive_root,
        schemas=_synthetic_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version=CANONICAL_SOFTWARE_VERSION,
        schema_version=CANONICAL_SCHEMA_VERSION,
    )
    assert manifest.manifest_hash() == EXPECTED_EMPTY_MANIFEST_HASH


def test_empty_archive_manifest_recomputation_is_stable(archive_root: Path) -> None:
    """Reejecutar compute_manifest sobre el mismo archive ⇒ mismo hash."""
    layout.ensure_archive_layout(archive_root)
    m1 = compute_manifest(
        archive_root,
        schemas=_synthetic_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version=CANONICAL_SOFTWARE_VERSION,
        schema_version=CANONICAL_SCHEMA_VERSION,
    )
    m2 = compute_manifest(
        archive_root,
        schemas=_synthetic_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version=CANONICAL_SOFTWARE_VERSION,
        schema_version=CANONICAL_SCHEMA_VERSION,
    )
    assert m1.manifest_hash() == m2.manifest_hash()


@pytest.mark.requires_fixture
def test_archive_with_demo_pdf_manifest_hash_is_canonical_pinned() -> None:
    """Manifest hash sobre archive con el PDF de demo de Pre-F1.C.

    Skip hasta que ``tests/data/twining-memo-1947-09-23.pdf`` exista y los
    pinned values estén en ``docs/phase-1/demo-evidence-selection.md``.
    Cuando se desbloquee, este test:

    1. Ingesta el PDF (Paso 11) en un archive temporal con clock fijo.
    2. Computa el manifest con ``generated_at`` canónico.
    3. Verifica contra el valor pinned (pendiente).
    """
    pytest.skip(
        "awaiting Pre-F1.C pinned values; see docs/phase-1/demo-evidence-selection.md"
    )
