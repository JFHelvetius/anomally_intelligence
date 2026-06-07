"""Subcomando ``aip assess-authentication`` (ADR-0032 §5).

Ortogonal a ``evidence`` y ``archive``: vive como subcomando top-level porque
es un artefacto derivado distinto del ciclo de vida de la evidencia. Argumentos
mínimos por contrato (ADR-0032 §5): ``--archive PATH`` + ``--evidence-id ID``.
Salida JSON canónica; sin formato humano por contrato (el assessment se piensa
para ser consumido por herramientas externas o como entrada de la siguiente
fase, no para ser leído al vuelo).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.analysis.authentication import AssessmentMethod
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


# --------------------------------------------------------------------- helpers


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
