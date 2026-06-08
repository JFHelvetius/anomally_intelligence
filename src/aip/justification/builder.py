"""Constructor, persistencia y verificación de Justifications (ADR-0040).

**Build:** lectura pura del archive + traversal del grafo. Sin reloj,
sin aleatoriedad, sin ejecución de motores productores (ADR-0040 §G3).

**Persist:** además de escribir el JSON canónico, emite una entry
``BUILD_JUSTIFICATION`` en el audit log (ADR-0019 §enmienda E1). El
reloj y el actor son operator-supplied: el contrato de inmutabilidad del
artefacto no cambia, sólo se añade una entry hash-chained que registra
el acto de persistir.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import (
    AuthenticationAssessment as DerivedAuthenticationAssessment,
)
from aip.audit import log as audit_log
from aip.core.evidence import Evidence
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.core.provenance import Provenance
from aip.errors import AIPError
from aip.graph import build_graph
from aip.graph.models import GraphNode, NodeKind
from aip.graph.query import get_dependency_chain
from aip.justification.models import (
    JUSTIFICATION_ENGINE_VERSION,
    JUSTIFICATION_METHOD_NAME,
    ChainEntry,
    InvestigationJustification,
)
from aip.storage import layout, tables
from aip.storage.manifest import ArchiveManifest
from aip.workspace import load_workspace

JUSTIFICATIONS_DIRNAME: str = "justifications"


class JustificationAnchorNotFoundError(AIPError):
    """El anchor (assessment) declarado no existe en el archive."""

    cli_exit_code = 1


class JustificationNotFoundError(AIPError):
    """Justificación solicitada no existe bajo ``<archive>/justifications/``."""

    cli_exit_code = 1


# --------------------------------------------------------------------- hashing


def compute_chain_entry_hash(role: str, identifier: str) -> str:
    """SHA-256 hex de ``f"{role}:{identifier}"``.

    Pura función de strings. Cero acceso al archive, cero motores.
    """
    if not role:
        raise ValueError("role must be non-empty.")
    if not identifier:
        raise ValueError("identifier must be non-empty.")
    return sha256_hex(f"{role}:{identifier}".encode())


def compute_justification_hash(j: InvestigationJustification) -> str:
    """SHA-256 hex JCS del modelo **excluyendo** ``justification_hash``."""
    data = _justification_to_canonical_dict(j)
    data.pop("justification_hash", None)
    normalized = cast(JsonValue, data)
    return sha256_hex(jcs_canonicalize(normalized))


def verify_justification_hash(j: InvestigationJustification) -> bool:
    """Verifica ``justification_hash`` offline (ADR-0040 §G4)."""
    return compute_justification_hash(j) == j.justification_hash


# --------------------------------------------------------------------- build


def build_justification(
    *,
    archive_root: Path,
    conclusion_anchor_type: str,
    conclusion_anchor_id: str,
    justification_id: str,
    workspace_id: str | None = None,
) -> InvestigationJustification:
    """Construye una :class:`InvestigationJustification` determinista.

    Lectura pura. Sin reloj. Sin aleatoriedad. Sin ejecución de motores
    productores. Mismo archive + mismo anchor + mismo workspace ⇒ mismo
    output bit a bit (ADR-0040 §G1).
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise FileNotFoundError(
            f"archive not found or invalid at {archive_root}."
        )

    if conclusion_anchor_type != "assessment":
        raise ValueError(
            f"V1 only supports 'assessment' anchor type; "
            f"got {conclusion_anchor_type!r}."
        )

    manifest_path = archive_root / layout.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"manifest.json missing at {manifest_path}; required for "
            "source_manifest_hash."
        )
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored_manifest = ArchiveManifest.model_validate(stored)
    source_manifest_hash = stored_manifest.manifest_hash()

    # Optional workspace scope.
    workspace_hash: str | None = None
    if workspace_id is not None:
        workspace = load_workspace(
            archive_root=archive_root, workspace_id=workspace_id
        )
        workspace_hash = workspace.workspace_hash

    # Resolve anchor (V1: assessment).
    assessment_row = tables.read_row(
        archive_root, "authentication_assessments", conclusion_anchor_id
    )
    if assessment_row is None:
        raise JustificationAnchorNotFoundError(
            f"assessment {conclusion_anchor_id!r} not found in archive."
        )
    assessment = DerivedAuthenticationAssessment.model_validate(
        assessment_row
    )
    conclusion_anchor_hash = compute_chain_entry_hash(
        "assessment", assessment.assessment_id
    )

    # Build chain categories.
    minimal_evidence: list[ChainEntry] = []
    supporting_assessments: list[ChainEntry] = [
        _make_entry("assessment", assessment.assessment_id)
    ]
    graph_nodes_used: list[ChainEntry] = []
    intermediate_artifacts: list[ChainEntry] = []
    provenance_chain: list[ChainEntry] = []

    # Evidence + source + provenance.
    evidence_row = tables.read_row(
        archive_root, "evidence", assessment.evidence_id
    )
    if evidence_row is not None:
        evidence = Evidence.model_validate(evidence_row)
        minimal_evidence.append(_make_entry("evidence", evidence.hash))
        provenance_row = tables.read_row(
            archive_root, "provenance", evidence.hash
        )
        if provenance_row is not None:
            provenance = Provenance.model_validate(provenance_row)
            for step in provenance.steps:
                step_identifier = (
                    f"{evidence.hash}__step{step.step_id:05d}"
                )
                provenance_chain.append(
                    _make_entry("provenance_step", step_identifier)
                )

    # Supporting sources from the assessment.
    for source_id in assessment.supporting_source_ids:
        minimal_evidence.append(_make_entry("source", source_id))

    # Graph traversal: dependency chain (outgoing) from anchor.
    graph = build_graph(archive_root)
    anchor_node = GraphNode(
        kind=NodeKind.ASSESSMENT, id=assessment.assessment_id
    )
    if anchor_node in graph.node_set():
        chain_nodes = get_dependency_chain(graph, anchor_node)
        for node in chain_nodes:
            graph_node_identifier = f"{node.kind.value}:{node.id}"
            graph_nodes_used.append(
                _make_entry("graph_node", graph_node_identifier)
            )

    # Canonical sort each category and dedupe by (role, identifier).
    sorted_categories = {
        "minimal_evidence": _sort_and_dedupe(minimal_evidence),
        "supporting_assessments": _sort_and_dedupe(supporting_assessments),
        "graph_nodes_used": _sort_and_dedupe(graph_nodes_used),
        "intermediate_artifacts": _sort_and_dedupe(intermediate_artifacts),
        "provenance_chain": _sort_and_dedupe(provenance_chain),
    }

    partial = InvestigationJustification(
        justification_id=justification_id,
        conclusion_anchor_type=conclusion_anchor_type,
        conclusion_anchor_id=conclusion_anchor_id,
        conclusion_anchor_hash=conclusion_anchor_hash,
        minimal_evidence=sorted_categories["minimal_evidence"],
        supporting_assessments=sorted_categories["supporting_assessments"],
        graph_nodes_used=sorted_categories["graph_nodes_used"],
        intermediate_artifacts=sorted_categories["intermediate_artifacts"],
        provenance_chain=sorted_categories["provenance_chain"],
        workspace_hash=workspace_hash,
        source_manifest_hash=source_manifest_hash,
        justification_engine_version=JUSTIFICATION_ENGINE_VERSION,
        justification_method_name=JUSTIFICATION_METHOD_NAME,
        justification_hash="0" * 64,
    )
    final_hash = compute_justification_hash(partial)
    return dataclasses.replace(partial, justification_hash=final_hash)


def _make_entry(role: str, identifier: str) -> ChainEntry:
    return ChainEntry(
        entry_role=role,
        entry_identifier=identifier,
        entry_hash=compute_chain_entry_hash(role, identifier),
    )


def _sort_and_dedupe(
    entries: list[ChainEntry],
) -> tuple[ChainEntry, ...]:
    seen: set[tuple[str, str]] = set()
    out: list[ChainEntry] = []
    for e in entries:
        key = (e.entry_role, e.entry_identifier)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return tuple(sorted(out))


# --------------------------------------------------------------------- persistence


def justification_path(
    archive_root: Path, justification_id: str
) -> Path:
    return (
        archive_root / JUSTIFICATIONS_DIRNAME / f"{justification_id}.json"
    )


def persist_justification(
    j: InvestigationJustification,
    *,
    archive_root: Path,
    actor: str,
    clock: Callable[[], dt.datetime],
    extra_output: Path | None = None,
) -> Path:
    target = justification_path(archive_root, j.justification_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = encode_justification(j)
    target.write_text(payload, encoding="utf-8")
    if extra_output is not None:
        extra_output.parent.mkdir(parents=True, exist_ok=True)
        extra_output.write_text(payload, encoding="utf-8")
    audit_log.record_derived_artifact(
        archive_root,
        action=audit_log.ActionKind.BUILD_JUSTIFICATION,
        artifact_kind="justification",
        artifact_id=j.justification_id,
        self_hash=j.justification_hash,
        actor=actor,
        clock=clock,
        schema_version=SCHEMA_VERSION,
    )
    return target


def load_justification(
    *, archive_root: Path, justification_id: str
) -> InvestigationJustification:
    target = justification_path(archive_root, justification_id)
    if not target.is_file():
        raise JustificationNotFoundError(
            f"justification {justification_id!r} not found at {target}."
        )
    return decode_justification(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- encoding


def encode_justification(j: InvestigationJustification) -> str:
    data = _justification_to_canonical_dict(j)
    return (
        json.dumps(
            data, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )


def decode_justification(payload: str) -> InvestigationJustification:
    data = json.loads(payload)
    return InvestigationJustification(
        justification_id=data["justification_id"],
        conclusion_anchor_type=data["conclusion_anchor_type"],
        conclusion_anchor_id=data["conclusion_anchor_id"],
        conclusion_anchor_hash=data["conclusion_anchor_hash"],
        minimal_evidence=_decode_entries(data.get("minimal_evidence", [])),
        supporting_assessments=_decode_entries(
            data.get("supporting_assessments", [])
        ),
        graph_nodes_used=_decode_entries(data.get("graph_nodes_used", [])),
        intermediate_artifacts=_decode_entries(
            data.get("intermediate_artifacts", [])
        ),
        provenance_chain=_decode_entries(data.get("provenance_chain", [])),
        workspace_hash=data.get("workspace_hash"),
        source_manifest_hash=data["source_manifest_hash"],
        justification_engine_version=data["justification_engine_version"],
        justification_method_name=data["justification_method_name"],
        justification_hash=data["justification_hash"],
        schema_version=data.get("schema_version", ""),
    )


def _decode_entries(raw: list[dict[str, str]]) -> tuple[ChainEntry, ...]:
    return tuple(
        ChainEntry(
            entry_role=e["entry_role"],
            entry_identifier=e["entry_identifier"],
            entry_hash=e["entry_hash"],
        )
        for e in raw
    )


def _justification_to_canonical_dict(
    j: InvestigationJustification,
) -> dict[str, object]:
    return {
        "justification_id": j.justification_id,
        "conclusion_anchor_type": j.conclusion_anchor_type,
        "conclusion_anchor_id": j.conclusion_anchor_id,
        "conclusion_anchor_hash": j.conclusion_anchor_hash,
        "minimal_evidence": [_entry_dict(e) for e in j.minimal_evidence],
        "supporting_assessments": [
            _entry_dict(e) for e in j.supporting_assessments
        ],
        "graph_nodes_used": [_entry_dict(e) for e in j.graph_nodes_used],
        "intermediate_artifacts": [
            _entry_dict(e) for e in j.intermediate_artifacts
        ],
        "provenance_chain": [_entry_dict(e) for e in j.provenance_chain],
        "workspace_hash": j.workspace_hash,
        "source_manifest_hash": j.source_manifest_hash,
        "justification_engine_version": j.justification_engine_version,
        "justification_method_name": j.justification_method_name,
        "justification_hash": j.justification_hash,
        "schema_version": j.schema_version,
    }


def _entry_dict(e: ChainEntry) -> dict[str, str]:
    return {
        "entry_role": e.entry_role,
        "entry_identifier": e.entry_identifier,
        "entry_hash": e.entry_hash,
    }
