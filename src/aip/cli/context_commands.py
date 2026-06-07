"""Subgrupo CLI ``aip context`` (ADR-0035 §CLI).

Un único subcomando ``show`` que despacha por tipo de anchor:

- ``aip context show evidence   <evidence-id>   --archive PATH``
- ``aip context show assessment <assessment-id> --archive PATH``

JSON canónico (``sort_keys=True``). Read-only — no modifica el archive.
``aip context show source`` se omite del CLI público por simetría con
``aip impact``. Ver ADR-0035 §CLI.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import IO

from aip.context import (
    ContextAnchorNotFoundError,
    assemble_context,
)
from aip.errors import EvidenceNotFoundError
from aip.graph.models import GraphNode, NodeKind


def context_show_evidence_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Ensambla y emite el ContextBundle anclado en una evidencia."""
    return _run(
        archive=args.archive,
        anchor=GraphNode(kind=NodeKind.EVIDENCE, id=args.evidence_id),
        action="context_show_evidence",
        id_field="evidence_id",
        id_value=args.evidence_id,
        stdout=stdout,
    )


def context_show_assessment_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Ensambla y emite el ContextBundle anclado en un assessment."""
    return _run(
        archive=args.archive,
        anchor=GraphNode(kind=NodeKind.ASSESSMENT, id=args.assessment_id),
        action="context_show_assessment",
        id_field="assessment_id",
        id_value=args.assessment_id,
        stdout=stdout,
    )


# --------------------------------------------------------------------- subparser


def add_context_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el grupo ``context`` al dispatcher principal."""
    grp = subparsers.add_parser(
        "context",
        help=(
            "Context Assembly (ADR-0035). Aggregate all derived layers "
            "for a single anchor into one deterministic JSON bundle. "
            "Read-only — aggregates existing results."
        ),
    )
    sub = grp.add_subparsers(dest="context_action", required=True)

    show = sub.add_parser(
        "show",
        help="Assemble a ContextBundle for an evidence or assessment.",
    )
    show_sub = show.add_subparsers(
        dest="context_show_kind", required=True
    )

    ev = show_sub.add_parser(
        "evidence",
        help="Assemble context anchored on an evidence (by SHA-256 hex).",
    )
    ev.add_argument("evidence_id", help="SHA-256 hex of the Evidence.")
    ev.add_argument("--archive", required=True, type=Path)
    ev.set_defaults(_cmd=context_show_evidence_command)

    asm = show_sub.add_parser(
        "assessment",
        help="Assemble context anchored on an assessment.",
    )
    asm.add_argument(
        "assessment_id",
        help="Assessment identifier (= '{evidence_id}__{method}').",
    )
    asm.add_argument("--archive", required=True, type=Path)
    asm.set_defaults(_cmd=context_show_assessment_command)


# --------------------------------------------------------------------- internals


def _run(
    *,
    archive: Path,
    anchor: GraphNode,
    action: str,
    id_field: str,
    id_value: str,
    stdout: IO[str],
) -> int:
    try:
        bundle = assemble_context(archive, anchor)
    except ContextAnchorNotFoundError:
        payload: dict[str, object] = {
            "ok": False,
            "action": action,
            "archive_root": str(archive),
            id_field: id_value,
            "exists": False,
            "bundle": None,
        }
        _emit_canonical_json(payload, stdout=stdout)
        return EvidenceNotFoundError.cli_exit_code

    payload = {
        "ok": True,
        "action": action,
        "archive_root": str(archive),
        id_field: id_value,
        "exists": True,
        "bundle": dataclasses.asdict(bundle),
    }
    _emit_canonical_json(payload, stdout=stdout)
    return 0


def _emit_canonical_json(
    payload: dict[str, object], *, stdout: IO[str]
) -> None:
    stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
