"""Subgrupo CLI ``aip impact`` (ADR-0034 §CLI).

Dos subcomandos read-only que reportan reachability inversa:

- ``aip impact evidence <evidence-id> --archive PATH``
- ``aip impact assessment <assessment-id> --archive PATH``

Ambos emiten JSON canónico con ``sort_keys=True``. Ninguno modifica el
archive. Ambos retornan rc=1 cuando el root no está en el grafo.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import IO

from aip.errors import EvidenceNotFoundError
from aip.graph import build_graph
from aip.graph.models import GraphNode, NodeKind
from aip.impact import analyze_removal_impact


def impact_evidence_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Reporta impacto downstream de una evidencia (ADR-0034 §CLI)."""
    return _run_impact(
        archive=args.archive,
        node_kind=NodeKind.EVIDENCE,
        node_id=args.evidence_id,
        action="impact_evidence",
        id_field="evidence_id",
        stdout=stdout,
    )


def impact_assessment_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Reporta impacto downstream de un assessment (ADR-0034 §CLI)."""
    return _run_impact(
        archive=args.archive,
        node_kind=NodeKind.ASSESSMENT,
        node_id=args.assessment_id,
        action="impact_assessment",
        id_field="assessment_id",
        stdout=stdout,
    )


# --------------------------------------------------------------------- subparser


def add_impact_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el grupo ``impact`` al dispatcher principal.

    Subgroup style (consistente con ``aip graph``) porque agrupa dos
    subcomandos del mismo dominio. ``aip impact source <id>`` está
    deliberadamente fuera del CLI público; los operadores que necesiten
    impacto desde una source usan la API Python directa (ver ADR-0034
    §CLI).
    """
    grp = subparsers.add_parser(
        "impact",
        help=(
            "Downstream impact analysis (ADR-0034). Reverse-dependency "
            "reachability from a root node. Reachability only."
        ),
    )
    sub = grp.add_subparsers(dest="impact_action", required=True)

    ev = sub.add_parser(
        "evidence",
        help=(
            "Report which assessments would lose support if this "
            "evidence becomes unavailable."
        ),
    )
    ev.add_argument(
        "evidence_id",
        help="SHA-256 hex of the Evidence to analyze.",
    )
    ev.add_argument("--archive", required=True, type=Path)
    ev.set_defaults(_cmd=impact_evidence_command)

    asm = sub.add_parser(
        "assessment",
        help=(
            "Report which downstream artifacts depend on this assessment "
            "(typically empty in V1 — assessments are terminal nodes)."
        ),
    )
    asm.add_argument(
        "assessment_id",
        help="Assessment identifier (= '{evidence_id}__{method}').",
    )
    asm.add_argument("--archive", required=True, type=Path)
    asm.set_defaults(_cmd=impact_assessment_command)


# --------------------------------------------------------------------- helpers


def _run_impact(
    *,
    archive: Path,
    node_kind: NodeKind,
    node_id: str,
    action: str,
    id_field: str,
    stdout: IO[str],
) -> int:
    graph = build_graph(archive)
    target = GraphNode(kind=node_kind, id=node_id)

    if target not in graph.node_set():
        payload: dict[str, object] = {
            "ok": False,
            "action": action,
            "archive_root": str(archive),
            id_field: node_id,
            "exists": False,
            "report": None,
        }
        _emit_canonical_json(payload, stdout=stdout)
        return EvidenceNotFoundError.cli_exit_code

    report = analyze_removal_impact(graph, target)
    payload = {
        "ok": True,
        "action": action,
        "archive_root": str(archive),
        id_field: node_id,
        "exists": True,
        "report": dataclasses.asdict(report),
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
