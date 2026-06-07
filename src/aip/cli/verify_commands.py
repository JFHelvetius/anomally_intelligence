"""Universal artifact verifier (``aip verify``).

Auto-detecta el tipo de un artefacto JSON persistido (workspace, timeline,
snapshot, justification, context bundle) y ejecuta su verificación offline
sin requerir múltiples comandos.

Optional ``--against-archive PATH``: además de la verificación estructural
offline, compara ``source_manifest_hash``/``workspace_hash``/
``timeline_hash`` declarados en el artefacto contra el estado actual del
archive — detecta drift.

Cero ejecución de motores productores. Sólo decode + verify + comparación
de hashes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import IO, Final

from aip.context import verify_bundle_hash
from aip.context.models import ContextBundle, ContextNode, GraphNeighborhood
from aip.errors import AIPError
from aip.justification import (
    decode_justification,
    verify_justification_hash,
)
from aip.snapshot import decode_snapshot, verify_snapshot
from aip.storage import layout
from aip.storage.manifest import ArchiveManifest
from aip.timeline import decode_timeline, verify_timeline_hash
from aip.workspace import decode_workspace, verify_workspace_hash

ARTIFACT_DETECTOR_PRIORITY: Final[tuple[str, ...]] = (
    "workspace",
    "timeline",
    "snapshot",
    "justification",
    "context_bundle",
)


# --------------------------------------------------------------------- detect


def _detect_artifact_kind(data: dict[str, object]) -> str | None:
    """Detecta el tipo del artefacto inspeccionando llaves estructurales.

    Cada tipo tiene una firma de campos únicos. Devuelve ``None`` si no
    coincide con ninguno conocido.
    """
    # Workspace: workspace_id + workspace_hash + references
    if (
        "workspace_id" in data
        and "workspace_hash" in data
        and "references" in data
    ):
        return "workspace"
    # Timeline
    if (
        "timeline_id" in data
        and "timeline_hash" in data
        and "ordered_events" in data
    ):
        return "timeline"
    # Snapshot
    if (
        "snapshot_id" in data
        and "snapshot_hash" in data
        and "referenced_artifacts" in data
    ):
        return "snapshot"
    # Justification
    if (
        "justification_id" in data
        and "justification_hash" in data
        and "conclusion_anchor_type" in data
    ):
        return "justification"
    # Context bundle
    if (
        "context_bundle_hash" in data
        and "assembly_method_name" in data
        and "graph_neighborhood" in data
    ):
        return "context_bundle"
    return None


# --------------------------------------------------------------------- verify


def verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    path: Path = args.artifact_file
    if not path.is_file():
        raise AIPError(f"artifact file not found: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        raise AIPError(f"artifact file not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise AIPError(
            f"artifact file root must be a JSON object, got {type(data).__name__}."
        )

    kind = _detect_artifact_kind(data)
    if kind is None:
        raise AIPError(
            "could not detect artifact type. Expected one of: "
            f"{list(ARTIFACT_DETECTOR_PRIORITY)}."
        )

    self_ok, identity, declared_self_hash = _verify_self(
        kind=kind, raw_text=raw_text, data=data
    )

    archive_drift: dict[str, object] | None = None
    if args.against_archive is not None:
        archive_drift = _verify_against_archive(
            kind=kind,
            data=data,
            archive_root=args.against_archive,
        )

    overall_ok = self_ok and (
        archive_drift is None or bool(archive_drift.get("ok"))
    )

    payload: dict[str, object] = {
        "ok": overall_ok,
        "action": "verify",
        "artifact_file": str(path),
        "artifact_kind": kind,
        "artifact_identity": identity,
        "self_hash": declared_self_hash,
        "self_hash_ok": self_ok,
    }
    if archive_drift is not None:
        payload["archive_drift"] = archive_drift
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0 if overall_ok else 1


def _verify_self(
    *, kind: str, raw_text: str, data: dict[str, object]
) -> tuple[bool, str, str]:
    """Recomputa el self-hash del artefacto y compara con el declarado.

    Devuelve ``(ok, identity, declared_self_hash)`` donde ``identity`` es
    el ID legible del artefacto y ``declared_self_hash`` es el hash que
    figura en el JSON original.
    """
    if kind == "workspace":
        w = decode_workspace(raw_text)
        return (
            verify_workspace_hash(w),
            w.workspace_id,
            w.workspace_hash,
        )
    if kind == "timeline":
        t = decode_timeline(raw_text)
        return (
            verify_timeline_hash(t),
            t.timeline_id,
            t.timeline_hash,
        )
    if kind == "snapshot":
        s = decode_snapshot(raw_text)
        return (verify_snapshot(s), s.snapshot_id, s.snapshot_hash)
    if kind == "justification":
        j = decode_justification(raw_text)
        return (
            verify_justification_hash(j),
            j.justification_id,
            j.justification_hash,
        )
    if kind == "context_bundle":
        bundle = _decode_context_bundle(data)
        return (
            verify_bundle_hash(bundle),
            f"{bundle.anchor_node_kind}:{bundle.anchor_node_id}",
            bundle.context_bundle_hash,
        )
    raise AIPError(f"unsupported artifact kind: {kind}")


def _decode_context_bundle(data: dict[str, object]) -> ContextBundle:
    """Decode helper para ContextBundle (no expuesto por aip.context).

    Reconstruye la dataclass desde su representación dict — los campos
    son escalares + dicts + tuplas, así que la conversión es directa.
    """
    nb_raw = data.get("graph_neighborhood", {})
    if not isinstance(nb_raw, dict):
        raise AIPError("context_bundle.graph_neighborhood not an object")
    upstream = tuple(
        ContextNode(
            distance_from_anchor=n["distance_from_anchor"],
            node_type=n["node_type"],
            node_id=n["node_id"],
        )
        for n in nb_raw.get("upstream", [])
        if isinstance(n, dict)
    )
    downstream = tuple(
        ContextNode(
            distance_from_anchor=n["distance_from_anchor"],
            node_type=n["node_type"],
            node_id=n["node_id"],
        )
        for n in nb_raw.get("downstream", [])
        if isinstance(n, dict)
    )
    neighborhood = GraphNeighborhood(
        upstream=upstream, downstream=downstream
    )
    derived_raw = data.get("derived_assessments", [])
    if not isinstance(derived_raw, list):
        derived_raw = []
    return ContextBundle(
        anchor_node_kind=str(data["anchor_node_kind"]),
        anchor_node_id=str(data["anchor_node_id"]),
        evidence=data.get("evidence"),  # type: ignore[arg-type]
        source=data.get("source"),  # type: ignore[arg-type]
        provenance=data.get("provenance"),  # type: ignore[arg-type]
        derived_assessments=tuple(derived_raw),
        graph_neighborhood=neighborhood,
        impact_report=data.get("impact_report", {}),  # type: ignore[arg-type]
        assembly_engine_version=str(data["assembly_engine_version"]),
        assembly_method_name=str(data["assembly_method_name"]),
        schema_version=str(data["schema_version"]),
        source_manifest_hash=str(data["source_manifest_hash"]),
        context_bundle_hash=str(data["context_bundle_hash"]),
    )


# --------------------------------------------------------------------- against archive


def _verify_against_archive(
    *,
    kind: str,
    data: dict[str, object],
    archive_root: Path,
) -> dict[str, object]:
    """Compara hashes declarados en el artefacto vs. estado actual del archive."""
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        return {
            "ok": False,
            "detail": f"archive not found or invalid at {archive_root}",
        }
    current_manifest_hash = _current_manifest_hash(archive_root)
    issues: list[str] = []

    declared_source_manifest = data.get("source_manifest_hash")
    if (
        isinstance(declared_source_manifest, str)
        and current_manifest_hash
        and declared_source_manifest != current_manifest_hash
    ):
        issues.append(
            f"source_manifest_hash drift: artifact declares "
            f"{declared_source_manifest[:8]}..., archive currently "
            f"{current_manifest_hash[:8]}..."
        )

    declared_workspace_hash = data.get("workspace_hash")
    if isinstance(
        declared_workspace_hash, str
    ) and not _archive_has_workspace_hash(
        archive_root, declared_workspace_hash
    ):
        issues.append(
            f"workspace_hash {declared_workspace_hash[:8]}... not "
            "present in <archive>/workspaces/"
        )

    declared_timeline_hash = data.get("timeline_hash")
    if isinstance(
        declared_timeline_hash, str
    ) and not _archive_has_timeline_hash(
        archive_root, declared_timeline_hash
    ):
        issues.append(
            f"timeline_hash {declared_timeline_hash[:8]}... not "
            "present in <archive>/timelines/"
        )

    return {
        "ok": len(issues) == 0,
        "archive_root": str(archive_root),
        "current_manifest_hash": current_manifest_hash,
        "issues": issues,
    }


def _current_manifest_hash(archive_root: Path) -> str | None:
    p = archive_root / layout.MANIFEST_FILENAME
    if not p.is_file():
        return None
    try:
        stored = json.loads(p.read_text(encoding="utf-8"))
        return ArchiveManifest.model_validate(stored).manifest_hash()
    except Exception:
        return None


def _archive_has_workspace_hash(
    archive_root: Path, expected_hash: str
) -> bool:
    d = archive_root / "workspaces"
    if not d.is_dir():
        return False
    for p in d.glob("*.json"):
        try:
            w = decode_workspace(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if w.workspace_hash == expected_hash:
            return True
    return False


def _archive_has_timeline_hash(
    archive_root: Path, expected_hash: str
) -> bool:
    d = archive_root / "timelines"
    if not d.is_dir():
        return False
    for p in d.glob("*.json"):
        try:
            t = decode_timeline(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if t.timeline_hash == expected_hash:
            return True
    return False


# --------------------------------------------------------------------- subparser


def add_verify_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el comando top-level ``aip verify`` al dispatcher.

    Estilo flat (no subgrupo): ``aip verify <artifact.json>``. Comando
    distinto de ``aip archive verify`` (que audita la integridad del
    archive), ``aip workspace verify``, etc. (que requieren conocer el
    tipo de antemano). Este comando auto-detecta.
    """
    cmd = subparsers.add_parser(
        "verify",
        help=(
            "Universal artifact verifier. Auto-detects the type of a "
            "persisted JSON artifact (workspace, timeline, snapshot, "
            "justification, context_bundle) and verifies it offline. "
            "Optional --against-archive validates archive-anchored hashes."
        ),
    )
    cmd.add_argument(
        "artifact_file",
        type=Path,
        help="Path to the artifact JSON file.",
    )
    cmd.add_argument(
        "--against-archive",
        type=Path,
        default=None,
        help=(
            "Optional archive path. When provided, additionally verifies "
            "that source_manifest_hash / workspace_hash / timeline_hash "
            "declared in the artifact match the archive's current state."
        ),
    )
    cmd.set_defaults(_cmd=verify_command)
