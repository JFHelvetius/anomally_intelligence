"""Subgrupo CLI ``aip graph`` (ADR-0033 §CLI).

Tres subcomandos read-only que exponen consultas del grafo derivado:

- ``aip graph show`` — grafo completo + conteos + integridad.
- ``aip graph explain-assessment`` — qué hay detrás de un assessment.
- ``aip graph explain-evidence`` — qué depende de una evidencia.

Todos emiten JSON canónico (``sort_keys=True``, ``ensure_ascii=False``,
``indent=2``). Ninguno modifica el archive (verificado por
``test_cli_graph_show_does_not_modify_archive``).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import IO

from aip.errors import EvidenceNotFoundError
from aip.graph import (
    EvidenceGraph,
    GraphNode,
    NodeKind,
    build_graph,
    get_assessments_for_evidence,
    get_dependency_chain,
    get_evidence_for_assessment,
    get_reverse_dependencies,
    validate_graph_integrity,
)
from aip.graph.models import EDGE_KINDS, NODE_KINDS

# --------------------------------------------------------------------- show


def graph_show_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    """Emite el grafo completo en JSON canónico."""
    archive_root: Path = args.archive
    graph = build_graph(archive_root)
    payload = {
        "ok": True,
        "action": "graph_show",
        "archive_root": str(archive_root),
        "graph": _graph_to_payload(graph),
    }
    _emit_canonical_json(payload, stdout=stdout)
    return 0


# --------------------------------------------------------------------- explain-assessment


def graph_explain_assessment_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Explica la procedencia de un assessment (ADR-0033 §CLI)."""
    archive_root: Path = args.archive
    assessment_id: str = args.assessment_id
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.ASSESSMENT, id=assessment_id)

    if target not in graph.node_set():
        payload: dict[str, object] = {
            "ok": False,
            "action": "graph_explain_assessment",
            "archive_root": str(archive_root),
            "assessment_id": assessment_id,
            "exists": False,
        }
        _emit_canonical_json(payload, stdout=stdout)
        # Exit code 1: consistente con `evidence show` no encontrado.
        return EvidenceNotFoundError.cli_exit_code

    evidence_node = get_evidence_for_assessment(graph, assessment_id)
    transitive = get_dependency_chain(graph, target)
    payload = {
        "ok": True,
        "action": "graph_explain_assessment",
        "archive_root": str(archive_root),
        "assessment_id": assessment_id,
        "exists": True,
        "assessment": _node_to_payload(target),
        "evidence": _node_to_payload(evidence_node) if evidence_node else None,
        "transitive_dependencies": [_node_to_payload(n) for n in transitive],
    }
    _emit_canonical_json(payload, stdout=stdout)
    return 0


# --------------------------------------------------------------------- explain-evidence


def graph_explain_evidence_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Explica qué depende de una evidencia (ADR-0033 §CLI)."""
    archive_root: Path = args.archive
    evidence_id: str = args.evidence_id
    graph = build_graph(archive_root)
    target = GraphNode(kind=NodeKind.EVIDENCE, id=evidence_id)

    if target not in graph.node_set():
        payload: dict[str, object] = {
            "ok": False,
            "action": "graph_explain_evidence",
            "archive_root": str(archive_root),
            "evidence_id": evidence_id,
            "exists": False,
        }
        _emit_canonical_json(payload, stdout=stdout)
        return EvidenceNotFoundError.cli_exit_code

    assessments = get_assessments_for_evidence(graph, evidence_id)
    transitive = get_dependency_chain(graph, target)
    reverse = get_reverse_dependencies(graph, target)
    payload = {
        "ok": True,
        "action": "graph_explain_evidence",
        "archive_root": str(archive_root),
        "evidence_id": evidence_id,
        "exists": True,
        "evidence": _node_to_payload(target),
        "transitive_dependencies": [_node_to_payload(n) for n in transitive],
        "assessments": [_node_to_payload(n) for n in assessments],
        "reverse_dependencies": [_node_to_payload(n) for n in reverse],
    }
    _emit_canonical_json(payload, stdout=stdout)
    return 0


# --------------------------------------------------------------------- subparser


def add_graph_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el grupo ``graph`` al dispatcher principal.

    Estilo subgroup (consistente con ``aip archive verify``) porque hay
    tres subcomandos relacionados que comparten el dominio "grafo".
    """
    grp = subparsers.add_parser(
        "graph",
        help=(
            "Derived evidence graph (ADR-0033). Read-only queries over "
            "evidence/source/assessment provenance without persisting "
            "new state."
        ),
    )
    sub = grp.add_subparsers(dest="graph_action", required=True)

    show = sub.add_parser(
        "show",
        help="Emit the full evidence graph (nodes + edges) as canonical JSON.",
    )
    show.add_argument("--archive", required=True, type=Path)
    show.set_defaults(_cmd=graph_show_command)

    explain_a = sub.add_parser(
        "explain-assessment",
        help=(
            "Explain the provenance behind an assessment: the evidence "
            "it was built on plus its transitive sources."
        ),
    )
    explain_a.add_argument("--archive", required=True, type=Path)
    explain_a.add_argument(
        "--assessment-id",
        required=True,
        help="Assessment identifier (= '{evidence_id}__{method}').",
    )
    explain_a.set_defaults(_cmd=graph_explain_assessment_command)

    explain_e = sub.add_parser(
        "explain-evidence",
        help=(
            "Explain the dependencies and reverse dependencies of an "
            "evidence node: its source plus assessments derived from it."
        ),
    )
    explain_e.add_argument("--archive", required=True, type=Path)
    explain_e.add_argument(
        "--evidence-id",
        required=True,
        help="SHA-256 hex of the Evidence.",
    )
    explain_e.set_defaults(_cmd=graph_explain_evidence_command)


# --------------------------------------------------------------------- helpers


def _node_to_payload(node: GraphNode) -> dict[str, str]:
    return {"kind": node.kind.value, "id": node.id}


def _graph_to_payload(graph: EvidenceGraph) -> dict[str, object]:
    nodes_payload = [_node_to_payload(n) for n in graph.nodes]
    edges_payload = [
        {
            "kind": e.kind.value,
            "src": _node_to_payload(e.src),
            "dst": _node_to_payload(e.dst),
        }
        for e in graph.edges
    ]
    integrity_issues = validate_graph_integrity(graph)
    return {
        "nodes": nodes_payload,
        "edges": edges_payload,
        "counts": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "nodes_by_kind": {
                kind.value: sum(1 for n in graph.nodes if n.kind is kind)
                for kind in NODE_KINDS
            },
            "edges_by_kind": {
                kind.value: sum(1 for e in graph.edges if e.kind is kind)
                for kind in EDGE_KINDS
            },
        },
        "integrity": {
            "ok": not integrity_issues,
            "issues": [
                {
                    "kind": issue.kind.value,
                    "edge": {
                        "kind": issue.edge.kind.value,
                        "src": _node_to_payload(issue.edge.src),
                        "dst": _node_to_payload(issue.edge.dst),
                    },
                }
                for issue in integrity_issues
            ],
        },
    }


def _emit_canonical_json(payload: dict[str, object], *, stdout: IO[str]) -> None:
    stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
