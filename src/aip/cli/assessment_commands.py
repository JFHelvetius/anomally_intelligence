"""Subcomandos top-level relacionados con assessments derivados (ADR-0032).

- ``aip assess-authentication`` — produce un nuevo assessment para una
  Evidence (contrato ADR-0032 §5).
- ``aip list-assessments`` — enumera assessments persistidos, opcionalmente
  filtrados por ``--evidence-id``. UX adicional sobre la API
  :meth:`aip.archive.Archive.list_all_authentication_assessments`; sin
  cambio de modelo ni de tabla.

Ambos viven como subcomandos top-level porque son artefactos derivados
distintos del ciclo de vida de la evidencia y emiten siempre JSON
canónico (sin formato humano).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.analysis.authentication import AssessmentMethod, AuthenticationAssessment
from aip.archive import Archive


def assess_authentication_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Implementa ``aip assess-authentication`` (ADR-0032 §5).

    El comando es **idempotente sobre estado del archive**: dos invocaciones
    consecutivas sobre el mismo archive (sin cambios entremedias) producen
    el mismo ``assessment_id`` y, salvo por ``created_at``, el mismo payload.
    El ``row_id`` derivado de ``assessment_id`` hace que la segunda escritura
    sea no-op por la idempotencia de :func:`aip.storage.tables.append_row`.
    """
    archive = Archive.open(args.archive)
    assessment = archive.assess_authentication(
        evidence_id=args.evidence_id,
        method=args.method,
    )
    payload = {
        "ok": True,
        "action": "assess_authentication",
        "archive_root": str(archive.root),
        "assessment": {
            "assessment_id": assessment.assessment_id,
            "evidence_id": assessment.evidence_id,
            "created_at": _iso_utc(assessment.created_at),
            "method": assessment.method.value,
            "status": assessment.status.value,
            "rationale": assessment.rationale,
            "supporting_source_ids": list(assessment.supporting_source_ids),
            "schema_version": assessment.schema_version,
        },
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def add_assessment_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el subcomando ``assess-authentication`` al dispatcher principal.

    No usa el ``common`` parent porque su contrato (ADR-0032 §5) lista
    ``--archive PATH`` + ``--evidence-id ID`` y nada más. La salida es JSON
    por contrato, sin variantes ``--json/--quiet/--verbose``.
    """
    cmd = subparsers.add_parser(
        "assess-authentication",
        help=(
            "Derive an AuthenticationAssessment for an Evidence (ADR-0032). "
            "Reads the archive, applies deterministic rules, persists the "
            "result into the authentication_assessments table, refreshes "
            "the manifest, emits JSON."
        ),
    )
    cmd.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path al archive AIP.",
    )
    cmd.add_argument(
        "--evidence-id",
        required=True,
        help="SHA-256 hex de la Evidence (= Evidence.hash, 64 hex lowercase).",
    )
    cmd.add_argument(
        "--method",
        type=AssessmentMethod,
        choices=list(AssessmentMethod),
        default=AssessmentMethod.PROVENANCE_REVIEW,
        help=(
            "Método semántico del assessment. Default: provenance_review. "
            "La regla aplicada es la misma para los tres valores; el método "
            "diferencia assessments creados con propósitos distintos sobre "
            "la misma Evidence (ADR-0032 §2)."
        ),
    )
    cmd.set_defaults(_cmd=assess_authentication_command)


# --------------------------------------------------------------------- list


def list_assessments_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Implementa ``aip list-assessments`` (lectura read-only).

    Lee la tabla ``authentication_assessments``, opcionalmente filtra por
    ``--evidence-id``, y emite la lista entera en JSON. Sin tocar el
    archive: no escribe filas, no actualiza el manifest, no añade audit
    entries. Es la simetría de lectura del comando de escritura
    ``assess-authentication``.
    """
    archive = Archive.open(args.archive)
    if args.evidence_id is not None:
        items: tuple[AuthenticationAssessment, ...] = (
            archive.list_authentication_assessments(args.evidence_id)
        )
        filter_payload: dict[str, str] | None = {
            "evidence_id": args.evidence_id,
        }
    else:
        items = archive.list_all_authentication_assessments()
        filter_payload = None

    payload: dict[str, object] = {
        "ok": True,
        "action": "list_assessments",
        "archive_root": str(archive.root),
        "filter": filter_payload,
        "count": len(items),
        "assessments": [
            {
                "assessment_id": a.assessment_id,
                "evidence_id": a.evidence_id,
                "method": a.method.value,
                "status": a.status.value,
                "rationale": a.rationale,
                "supporting_source_ids": list(a.supporting_source_ids),
                "created_at": _iso_utc(a.created_at),
                "schema_version": a.schema_version,
            }
            for a in items
        ],
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def add_list_assessments_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el subcomando ``list-assessments`` al dispatcher.

    Mismo estilo flat que ``assess-authentication`` (sin ``common`` parent),
    salida JSON por contrato. ``--evidence-id`` opcional: sin él, enumera
    todo el corpus derivado.
    """
    cmd = subparsers.add_parser(
        "list-assessments",
        help=(
            "List AuthenticationAssessments persisted in the archive. "
            "Optional --evidence-id filters to a single Evidence. Read-only: "
            "does not modify the archive nor write audit entries."
        ),
    )
    cmd.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path al archive AIP.",
    )
    cmd.add_argument(
        "--evidence-id",
        default=None,
        help=(
            "Opcional. SHA-256 hex (también acepta ``sha256:<hex>`` o "
            "``aip:evidence/sha256:<hex>``). Si está presente, sólo "
            "devuelve assessments de esa Evidence."
        ),
    )
    cmd.set_defaults(_cmd=list_assessments_command)


# --------------------------------------------------------------------- helpers


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
