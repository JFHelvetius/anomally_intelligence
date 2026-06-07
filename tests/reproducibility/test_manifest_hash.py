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
from aip.analysis.authentication import AssessmentMethod
from aip.context import assemble_context, verify_bundle_hash
from aip.core.evidence import EvidenceKind
from aip.core.hashing import sha256_hex, sha256_hex_stream
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph.models import GraphNode, NodeKind
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


# ----------------------------------------------------------------- ADR-0032

EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH = (
    "33530b04c25c3766fb3fc7aa496bd22dffa2848d4bdc71d204ddb4b1141ee9ea"
)
"""``manifest_hash`` canónico tras ingestar el fixture de demo **y** correr
``Archive.assess_authentication`` con clock canónico y método por defecto
(``PROVENANCE_REVIEW``).

Inputs deterministas (idénticos a EXPECTED_DEMO_MANIFEST_HASH **más**):

- ``method = AssessmentMethod.PROVENANCE_REVIEW``.
- ``created_at = generated_at = 2026-06-04T00:00:00Z`` (mismo clock inyectado).
- ``rationale`` canónico para ``status=SUPPORTED``.
- ``supporting_source_ids = ["blue-book-nara"]``.
- ``assessment_id = "{evidence.hash}__provenance_review"``.

Si este valor cambia, ha cambiado uno de:

- la canonicalización del manifest (mismas causas que en
  ``EXPECTED_DEMO_MANIFEST_HASH``),
- la regla determinista de ``aip.analysis.authentication.classify``,
- el texto de ``RATIONALES[SUPPORTED]``,
- la forma de ``AuthenticationAssessment.model_dump(mode="json")``,
- el algoritmo de ``make_assessment_id``.

Cualquiera es bug arquitectónico crítico que requiere PR explícito + ADR
de enmienda al motor (ADR-0032). El valor se pinea aquí para que cualquier
drift se detecte en CI sin necesidad de re-ejecutar la demo a mano."""


@pytest.mark.requires_fixture
def test_archive_with_demo_pdf_and_assessment_manifest_hash_is_canonical_pinned(
    tmp_path: Path,
) -> None:
    """Manifest hash sobre archive ingest + assess con clocks canónicos.

    Una garantía adicional: la regla determinista del motor de autenticidad
    (ADR-0032) no degrada la reproducibilidad bit a bit del archive. Mismo
    fixture + mismo clock + mismo método ⇒ mismo manifest hash, sesión tras
    sesión, máquina tras máquina.
    """
    fixture = (
        Path(__file__).parent.parent / "data" / "twining-memo-1947-09-23.pdf"
    )
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    archive_root = tmp_path / "demo_archive_assessed"
    archive = Archive.open(archive_root)

    # 1. Ingest canónico (mismo contrato que el test anterior).
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

    # 2. Assess con clock canónico y método por defecto.
    assessment = archive.assess_authentication(
        evidence_id=evidence.hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=lambda: CANONICAL_GENERATED_AT,
    )
    # La regla emite SUPPORTED por construcción (post-ingest tiene Source +
    # Provenance con un paso y referencias intactas). Pinear el status
    # protege contra cambios silenciosos en classify().
    assert assessment.status.value == "supported"
    assert assessment.supporting_source_ids == ["blue-book-nara"]

    # 3. Manifest hash post-assessment coincide con el pinned.
    manifest = compute_manifest(
        archive_root,
        schemas=get_schemas(),
        generated_at=CANONICAL_GENERATED_AT,
        software_version=SOFTWARE_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    assert manifest.manifest_hash() == EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH


# ----------------------------------------------------------------- ADR-0035

EXPECTED_DEMO_CONTEXT_BUNDLE_HASH = (
    "ea257f4019f34e37fdf2601f27a5a00a963f99c6867e64ab7f237aad09624adc"
)
"""``context_bundle_hash`` canónico del :class:`ContextBundle` ensamblado
sobre el demo del Twining Memo con clock canónico y assessment derivado.

Inputs canónicos:

- Mismos clocks + inputs de ``EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH``
  (ingest + assess con clock 2026-06-04T00:00:00Z, método
  ``provenance_review``).
- Anchor del bundle: ``GraphNode(EVIDENCE, evidence.hash)``.

Si este valor cambia, ha cambiado uno de:

- Layout o campos del :class:`ContextBundle` / :class:`ContextNode` /
  :class:`GraphNeighborhood`.
- Forma del payload serializado por ``Evidence/Source/Provenance/
  AuthenticationAssessment.model_dump(mode="json")``.
- Output de ``analyze_removal_impact`` (ADR-0034).
- Forma de la canonicalización JCS / normalización de tuplas.
- ``ASSEMBLY_ENGINE_VERSION`` o ``ASSEMBLY_METHOD_NAME``.

Cualquiera es bug arquitectónico crítico que requiere PR + (posiblemente)
ADR de enmienda explícito.
"""


@pytest.mark.requires_fixture
def test_demo_context_bundle_hash_is_canonical_pinned(tmp_path: Path) -> None:
    """ContextBundle sobre demo + assess + anchor=evidence con clocks
    canónicos coincide con el pinned (ADR-0035 §reproducibilidad).

    Verifica además dos invariantes cross-ADR:

    1. ``bundle.source_manifest_hash`` coincide con
       ``EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH`` (ADR-0032/0035).
    2. ``verify_bundle_hash(bundle)`` es ``True`` (self-consistencia
       del hash declarado vs. recomputo).
    """
    fixture = (
        Path(__file__).parent.parent / "data" / "twining-memo-1947-09-23.pdf"
    )
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    archive_root = tmp_path / "demo_archive_assembled"
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
    archive.assess_authentication(
        evidence_id=evidence.hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=lambda: CANONICAL_GENERATED_AT,
    )

    bundle = assemble_context(
        archive_root,
        GraphNode(kind=NodeKind.EVIDENCE, id=evidence.hash),
    )
    # Invariante cross-ADR-0032/0035.
    assert bundle.source_manifest_hash == EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH
    # Self-consistencia del hash declarado.
    assert verify_bundle_hash(bundle) is True
    # Pin canónico.
    assert bundle.context_bundle_hash == EXPECTED_DEMO_CONTEXT_BUNDLE_HASH
