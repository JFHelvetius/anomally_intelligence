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

# Pinned por Pre-F1.C cerrada el 2026-06-06.
# Fuente: archive.org/details/twinning-memo (slug con typo histórico del item).
# Verificado en `tests/data/twining-memo-1947-09-23.pdf` (250 022 bytes).
EXPECTED_PDF_SHA256: str = (
    "65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1"
)
EXPECTED_PDF_SIZE_BYTES: int = 250022

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


# ---------------------------------------------------------------- full derived pipeline

# Constantes adicionales para el flujo post-v0.1.0.
DEMO_ASSESSMENT_METHOD = "provenance_review"
DEMO_WORKSPACE_ID = "demo-workspace"
DEMO_TIMELINE_ID = "demo-timeline"
DEMO_SNAPSHOT_ID = "demo-snapshot"
DEMO_JUSTIFICATION_ID = "demo-justification"


def test_demo_pipeline_full_derived_layers(tmp_path: Path) -> None:
    """Pipeline completo end-to-end ejercitando todas las capas derivadas.

    Cubre el ciclo:

        ingest → assess → workspace → timeline → snapshot →
        justification → diff → archive verify --derived

    Cada paso valida:

    - rc=0 del CLI.
    - Estructura mínima del JSON emitido.
    - Persistencia bajo `<archive>/{workspaces,timelines,snapshots,
      justifications}/`.

    El último paso (`archive verify --derived`) confirma integridad
    referencial cruzada sin incidencias. Si cualquier interacción
    inter-capa regresa silenciosamente, este test lo captura.
    """
    _skip_if_no_fixture()

    fixture = _fixture_path()
    archive_root = tmp_path / "demo_archive_full"

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
    ev_hash = json.loads(out.getvalue())["evidence"]["hash"]
    assert ev_hash == EXPECTED_PDF_SHA256

    # ----- assess -----------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "assess-authentication",
            "--archive",
            str(archive_root),
            "--evidence-id",
            ev_hash,
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    assessment_payload = json.loads(out.getvalue())
    assessment_id = assessment_payload["assessment"]["assessment_id"]
    assert assessment_payload["assessment"]["method"] == DEMO_ASSESSMENT_METHOD
    assert assessment_payload["assessment"]["status"] == "supported"

    # ----- workspace --------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "workspace",
            "create",
            "--workspace-id",
            DEMO_WORKSPACE_ID,
            "--title",
            "Demo investigation",
            "--evidence",
            ev_hash,
            "--assessment",
            assessment_id,
            "--archive",
            str(archive_root),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    workspace_payload = json.loads(out.getvalue())
    assert workspace_payload["workspace_id"] == DEMO_WORKSPACE_ID
    assert len(workspace_payload["references"]) == 2
    assert (
        archive_root / "workspaces" / f"{DEMO_WORKSPACE_ID}.json"
    ).is_file()

    # ----- timeline ---------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "timeline",
            "build",
            "--workspace-id",
            DEMO_WORKSPACE_ID,
            "--timeline-id",
            DEMO_TIMELINE_ID,
            "--archive",
            str(archive_root),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    timeline_payload = json.loads(out.getvalue())
    assert timeline_payload["timeline_id"] == DEMO_TIMELINE_ID
    # Evidence + assessment → 2 eventos (ambos con timestamp nativo).
    assert timeline_payload["event_count"] == 2
    assert (
        archive_root / "timelines" / f"{DEMO_TIMELINE_ID}.json"
    ).is_file()

    # ----- snapshot ---------------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "snapshot",
            "create",
            "--snapshot-id",
            DEMO_SNAPSHOT_ID,
            "--workspace-id",
            DEMO_WORKSPACE_ID,
            "--timeline-id",
            DEMO_TIMELINE_ID,
            "--archive",
            str(archive_root),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    snapshot_payload = json.loads(out.getvalue())
    assert snapshot_payload["snapshot_id"] == DEMO_SNAPSHOT_ID
    assert (
        archive_root / "snapshots" / f"{DEMO_SNAPSHOT_ID}.json"
    ).is_file()

    # ----- justification ----------------------------------------------------
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "justification",
            "build",
            "--conclusion-anchor-type",
            "assessment",
            "--conclusion-anchor-id",
            assessment_id,
            "--justification-id",
            DEMO_JUSTIFICATION_ID,
            "--workspace-id",
            DEMO_WORKSPACE_ID,
            "--archive",
            str(archive_root),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    justification_payload = json.loads(out.getvalue())
    assert (
        justification_payload["justification_id"] == DEMO_JUSTIFICATION_ID
    )
    assert justification_payload["conclusion_anchor_id"] == assessment_id
    assert justification_payload["workspace_hash"] is not None
    # La cadena no debe ser vacía: el assessment está respaldado por
    # al menos una evidencia + una source + un provenance step.
    assert len(justification_payload["minimal_evidence"]) >= 1
    assert len(justification_payload["provenance_chain"]) >= 1
    assert (
        archive_root / "justifications" / f"{DEMO_JUSTIFICATION_ID}.json"
    ).is_file()

    # ----- diff snapshots ---------------------------------------------------
    # Crear un segundo snapshot sobre el mismo workspace+timeline para
    # comparar. Como nada cambió, el diff debe ser "todo unchanged".
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "snapshot",
            "create",
            "--snapshot-id",
            "demo-snapshot-b",
            "--workspace-id",
            DEMO_WORKSPACE_ID,
            "--timeline-id",
            DEMO_TIMELINE_ID,
            "--archive",
            str(archive_root),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0

    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "diff",
            "snapshots",
            str(archive_root / "snapshots" / f"{DEMO_SNAPSHOT_ID}.json"),
            str(archive_root / "snapshots" / "demo-snapshot-b.json"),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0
    diff_payload = json.loads(out.getvalue())
    assert diff_payload["added_artifacts"] == []
    assert diff_payload["removed_artifacts"] == []
    assert len(diff_payload["unchanged_artifacts"]) == 2

    # ----- diff justifications ----------------------------------------------
    # Mismo razonamiento: una segunda justificación idéntica.
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "diff",
            "justifications",
            str(
                archive_root
                / "justifications"
                / f"{DEMO_JUSTIFICATION_ID}.json"
            ),
            str(
                archive_root
                / "justifications"
                / f"{DEMO_JUSTIFICATION_ID}.json"
            ),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0
    diff_j_payload = json.loads(out.getvalue())
    assert diff_j_payload["added_entries"] == []
    assert diff_j_payload["removed_entries"] == []
    assert len(diff_j_payload["unchanged_entries"]) >= 1

    # ----- archive verify --derived -----------------------------------------
    # Cierre del pipeline: todos los artefactos derivados deben pasar la
    # auditoría de integridad referencial cruzada sin incidencias.
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--derived",
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
    assert verify_payload["checks"]["derived_integrity"]["ok"] is True
    assert verify_payload["derived_integrity_issues"] == []
    assert verify_payload["summary"]["workspaces_checked"] == 1
    assert verify_payload["summary"]["timelines_checked"] == 1
    assert verify_payload["summary"]["snapshots_checked"] == 2
    assert verify_payload["summary"]["justifications_checked"] == 1

    # ----- removability ----------------------------------------------------
    # Borrar todos los artefactos derivados deja el archive verify base
    # funcional (G2 a nivel de plataforma).
    for d in ("workspaces", "timelines", "snapshots", "justifications"):
        target = archive_root / d
        if target.is_dir():
            for entry in target.iterdir():
                entry.unlink()

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
    final_payload = json.loads(out.getvalue())
    assert final_payload["ok"] is True
    # Las cuatro garantías base preservadas tras borrar TODO lo derivado.
    assert final_payload["checks"]["audit_chain"]["ok"] is True
    assert final_payload["checks"]["references"]["ok"] is True
    assert final_payload["checks"]["blobs"]["ok"] is True
    assert final_payload["checks"]["manifest"]["ok"] is True
    # Evidence canónica preservada.
    assert final_payload["summary"]["evidences"] == 1
