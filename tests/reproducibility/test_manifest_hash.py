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

from aip import Archive
from aip._version import SCHEMA_VERSION
from aip._version import __version__ as SOFTWARE_VERSION
from aip.core.evidence import EvidenceKind
from aip.core.hashing import sha256_hex, sha256_hex_stream
from aip.core.source import AuthorityLevel, SourceKind
from aip.storage import layout
from aip.storage.manifest import compute_manifest
from aip.storage.tables import get_schemas

pytestmark = pytest.mark.reproducibility


CANONICAL_GENERATED_AT = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.UTC)
CANONICAL_SOFTWARE_VERSION = "0.0.1"
CANONICAL_SCHEMA_VERSION = "0.1.0"


# ----------------------------------------------------------------- canonical hashes


# Esquemas sintéticos por tabla V1. Forman parte del input canónico de los
# pinned values; si cambian, el manifest_hash cambia.
def _synthetic_schemas() -> dict[str, bytes]:
    return {name: f"schema:{name}".encode() for name in layout.V1_TABLES}


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
        actual = sha256_hex(f"schema:{name}".encode())
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


EXPECTED_DEMO_PDF_SHA256 = (
    "65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1"
)
"""SHA-256 del Twining Memo (fixture de Pre-F1.C). Anclado al fichero
``tests/data/twining-memo-1947-09-23.pdf``."""

EXPECTED_DEMO_MANIFEST_HASH = (
    "364b23977466ad44c6f7a544a2b99987dc8ed9cabc82d227fc8a670942fda7bc"
)
"""``manifest_hash`` canónico tras ingestar el fixture con los siguientes
inputs deterministas:

- ``software_version = "0.0.1"``.
- ``schema_version = "0.1.0"``.
- ``generated_at = 2026-06-04T00:00:00Z`` (= clock inyectado en ingest).
- ``source_id = "blue-book-nara"``, kind/authority/jurisdiction/license
  según Pre-F1.D.
- ``ingested_by = "@jfhelvetius"``.

Si este valor cambia, ha cambiado:

- la canonicalización del manifest,
- el conjunto de tablas V1 o su orden,
- el orden de filas en los manifests de tabla,
- el algoritmo de hash, o
- el contenido del fichero fixture (sha256 distinto de
  ``EXPECTED_DEMO_PDF_SHA256``).

Cualquiera es bug arquitectónico crítico que requiere PR explícito."""


@pytest.mark.requires_fixture
def test_archive_with_demo_pdf_manifest_hash_is_canonical_pinned(
    tmp_path: Path,
) -> None:
    """Manifest hash sobre archive con el PDF de demo de Pre-F1.C ingestado.

    Tres garantías de reproducibilidad bit a bit:

    1. El SHA-256 del fixture coincide con el pinned (cadena de procedencia OK).
    2. ``Evidence.hash`` post-ingest coincide con SHA-256 del fixture (CAOS OK).
    3. ``manifest_hash`` con clock canónico coincide con el pinned (manifest OK).
    """
    fixture = (
        Path(__file__).parent.parent / "data" / "twining-memo-1947-09-23.pdf"
    )
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # 1. SHA-256 del fixture coincide con el pinned.
    with fixture.open("rb") as fh:
        fixture_hash = sha256_hex_stream(fh)
    assert fixture_hash == EXPECTED_DEMO_PDF_SHA256, (
        "Fixture binary drifted from Pre-F1.C pinned SHA-256. Either someone "
        "replaced the file or the source URL is serving a different version."
    )

    # 2. Ingesta con clock canónico produce Evidence.hash == fixture SHA-256.
    archive_root = tmp_path / "demo_archive"
    archive = Archive.open(archive_root)
    evidence = archive.ingest_evidence(
        fixture,
        source_id="blue-book-nara",
        source_name="Project Blue Book records",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@jfhelvetius",
        clock=lambda: CANONICAL_GENERATED_AT,
    )
    assert evidence.hash == EXPECTED_DEMO_PDF_SHA256

    # 3. Manifest hash con clock canónico coincide con el pinned.
    manifest = compute_manifest(
        archive_root,
        schemas=get_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version=SOFTWARE_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    assert manifest.manifest_hash() == EXPECTED_DEMO_MANIFEST_HASH
