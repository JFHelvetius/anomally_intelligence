"""Integration test del pipeline completo de la demo de Fase 1.

Este test es el contrato testeable derivado de
``docs/phase-1/command-specification.md`` §resumen ejecutivo. Si pasa en
máquina limpia (Linux x86_64 referencia) con el fixture canónico de
Pre-F1.C, **F1 está operativamente cerrada**.

Estado actual: marcado :pytest:`requires_fixture` y :pytest:`integration`.
Skip automático hasta que ``tests/data/twining-memo-1947-09-23.pdf`` exista
con su SHA-256 pinned en ``docs/phase-1/demo-evidence-selection.md``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from aip.cli import main as cli_main

# ---------------------------------------------------------------- canonical inputs

FIXTURE_NAME = "twining-memo-1947-09-23.pdf"

# Una vez rellenado el paso operativo P1-P5 de Pre-F1.C, sustituir el valor
# siguiente por el SHA-256 hex pinned (lowercase, len 64). Hasta entonces,
# permanece como sentinela vacío y el test queda en skip.
EXPECTED_PDF_SHA256: str = ""

# Constantes canónicas de la demo (Pre-F1.D + demo-evidence-selection.md).
DEMO_SOURCE_ID = "blue-book-nara"
DEMO_SOURCE_NAME = "Project Blue Book records"
DEMO_SOURCE_KIND = "government_archive"
DEMO_SOURCE_AUTHORITY = "secondary"
DEMO_SOURCE_JURISDICTION = "US"
DEMO_SOURCE_LICENSE = "public_domain"
DEMO_INGESTED_BY = "@jfhelvetius"


# ---------------------------------------------------------------- test


pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_fixture,
]


def _fixture_path() -> Path:
    return Path(__file__).parent.parent / "data" / FIXTURE_NAME


def _skip_if_no_fixture() -> None:
    if not EXPECTED_PDF_SHA256:
        pytest.skip(
            "awaiting Pre-F1.C pinned values; see "
            "docs/phase-1/demo-evidence-selection.md"
        )
    fx = _fixture_path()
    if not fx.is_file():
        pytest.skip(
            f"fixture {fx} not present; run scripts/fetch_demo_fixture.py "
            "to download and pin SHA-256."
        )


def test_demo_pipeline_pdf_ingest_show_verify(tmp_path: Path) -> None:
    """PDF → ingest → show → verify, todo end-to-end por CLI.

    Reproduce paso a paso el contrato del Pre-F1.D §resumen ejecutivo. Las
    cuatro fases (ingest, show, verify, hash) ejecutan en orden y verifican
    que el archive resultante es consistente con los valores pinned del
    fixture canónico.
    """
    _skip_if_no_fixture()

    fixture = _fixture_path()
    archive_root = tmp_path / "demo_archive"

    # ----- ingest -----------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "evidence",
            "ingest",
            str(fixture),
            "--archive-root",
            str(archive_root),
            "--source-id",
            DEMO_SOURCE_ID,
            "--source-name",
            DEMO_SOURCE_NAME,
            "--source-kind",
            DEMO_SOURCE_KIND,
            "--source-authority",
            DEMO_SOURCE_AUTHORITY,
            "--source-jurisdiction",
            DEMO_SOURCE_JURISDICTION,
            "--source-license",
            DEMO_SOURCE_LICENSE,
            "--ingested-by",
            DEMO_INGESTED_BY,
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    ingest_payload = json.loads(out.getvalue())
    assert ingest_payload["evidence"]["hash"] == EXPECTED_PDF_SHA256, (
        "Reported hash differs from the Pre-F1.C pinned SHA-256. "
        "Either the fixture binary changed or core/hashing drifted."
    )

    # ----- show -------------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "evidence",
            "show",
            f"sha256:{EXPECTED_PDF_SHA256}",
            "--archive-root",
            str(archive_root),
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    show_payload = json.loads(out.getvalue())
    assert show_payload["evidence"]["hash"] == EXPECTED_PDF_SHA256
    assert show_payload["source"]["id"] == DEMO_SOURCE_ID
    assert show_payload["source"]["authority"] == DEMO_SOURCE_AUTHORITY
    assert show_payload["provenance"]["is_complete"] is False
    assert len(show_payload["provenance"]["steps"]) == 1
    assert show_payload["authentication"]["status"] == "unverified"

    # ----- verify -----------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    verify_payload = json.loads(out.getvalue())
    assert verify_payload["ok"] is True
    assert verify_payload["checks"]["audit_chain"]["ok"] is True
    assert verify_payload["checks"]["references"]["ok"] is True
    assert verify_payload["checks"]["blobs"]["ok"] is True
    assert verify_payload["checks"]["manifest"]["ok"] is True
    assert verify_payload["summary"]["evidences"] == 1
    assert verify_payload["summary"]["sources"] == 1
    assert verify_payload["summary"]["audit_entries"] == 2  # bootstrap + ingest

    # ----- idempotencia de ingest -----------------------------------------
    # Re-ingest del mismo PDF debe devolver el mismo hash sin duplicar audit.
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "evidence",
            "ingest",
            str(fixture),
            "--archive-root",
            str(archive_root),
            "--source-id",
            DEMO_SOURCE_ID,
            "--source-name",
            DEMO_SOURCE_NAME,
            "--source-kind",
            DEMO_SOURCE_KIND,
            "--source-authority",
            DEMO_SOURCE_AUTHORITY,
            "--source-jurisdiction",
            DEMO_SOURCE_JURISDICTION,
            "--source-license",
            DEMO_SOURCE_LICENSE,
            "--ingested-by",
            DEMO_INGESTED_BY,
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    re_ingest = json.loads(out.getvalue())
    assert re_ingest["evidence"]["hash"] == EXPECTED_PDF_SHA256

    # Confirmamos que el archive sigue verificando OK tras la re-ingesta.
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0
    second_verify = json.loads(out.getvalue())
    assert second_verify["ok"] is True
    # Audit no debe haber crecido (idempotencia).
    assert second_verify["summary"]["audit_entries"] == 2
