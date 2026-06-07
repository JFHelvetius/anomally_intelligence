"""Subgrupo CLI ``aip workspace`` (ADR-0036 §CLI).

Tres subcomandos:

- ``aip workspace create`` — construye y persiste un workspace.
- ``aip workspace show`` — lee un workspace persistido.
- ``aip workspace verify`` — verifica auto-consistencia offline.

JSON canónico (``sort_keys=True``). Sin ejecución de motores analíticos
(ADR-0036 §G3): el CLI sólo orquesta lectura/escritura de strings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import IO

from aip.errors import AIPError
from aip.workspace import (
    DuplicateReferenceError,
    InvalidReferenceTypeError,
    InvestigationWorkspace,
    ReferenceType,
    create_workspace,
    decode_workspace,
    encode_workspace,
    load_workspace,
    persist_workspace,
    verify_workspace_hash,
)

# --------------------------------------------------------------------- create


def workspace_create_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Construye un workspace + persiste en archive + opcional output."""
    references_input: list[tuple[str, str]] = []
    for ev in args.evidence or []:
        references_input.append((ReferenceType.EVIDENCE.value, ev))
    for asm in args.assessment or []:
        references_input.append((ReferenceType.ASSESSMENT.value, asm))
    for imp in args.impact or []:
        references_input.append((ReferenceType.IMPACT_ANALYSIS.value, imp))
    for ctx in args.context or []:
        references_input.append((ReferenceType.CONTEXT_BUNDLE.value, ctx))

    try:
        workspace = create_workspace(
            archive_root=args.archive,
            workspace_id=args.workspace_id,
            title=args.title,
            references_input=references_input,
        )
    except (
        InvalidReferenceTypeError,
        DuplicateReferenceError,
        ValueError,
    ) as exc:
        raise AIPError(str(exc)) from exc

    persist_workspace(
        workspace,
        archive_root=args.archive,
        extra_output=args.output,
    )
    stdout.write(encode_workspace(workspace))
    return 0


# --------------------------------------------------------------------- show


def workspace_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Lee y emite un workspace persistido."""
    workspace = load_workspace(
        archive_root=args.archive, workspace_id=args.workspace_id
    )
    stdout.write(encode_workspace(workspace))
    return 0


# --------------------------------------------------------------------- verify


def workspace_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Verifica ``workspace_hash`` offline. rc=0 si válido, 1 si inválido."""
    path: Path = args.workspace_file
    if not path.is_file():
        raise AIPError(f"workspace file not found: {path}")
    workspace = decode_workspace(path.read_text(encoding="utf-8"))
    ok = verify_workspace_hash(workspace)
    stdout.write(_verify_payload(path, workspace, ok))
    return 0 if ok else 1


def _verify_payload(
    path: Path, workspace: InvestigationWorkspace, ok: bool
) -> str:
    payload = {
        "ok": ok,
        "action": "workspace_verify",
        "workspace_file": str(path),
        "workspace_id": workspace.workspace_id,
        "workspace_hash": workspace.workspace_hash,
    }
    return (
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )


# --------------------------------------------------------------------- subparser


def add_workspace_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el grupo ``workspace`` al dispatcher principal."""
    grp = subparsers.add_parser(
        "workspace",
        help=(
            "Investigation Workspace (ADR-0036). Reproducible references "
            "to existing derived artifacts. Read-only — does not execute "
            "analytical engines."
        ),
    )
    sub = grp.add_subparsers(dest="workspace_action", required=True)

    create = sub.add_parser(
        "create",
        help=(
            "Create a new workspace anchored to the current archive state."
        ),
    )
    create.add_argument(
        "--workspace-id",
        required=True,
        help="ASCII-safe identifier for the workspace.",
    )
    create.add_argument(
        "--title", required=True, help="Human-readable title."
    )
    create.add_argument(
        "--evidence",
        action="append",
        default=None,
        metavar="ID",
        help="Reference to an evidence (repeatable).",
    )
    create.add_argument(
        "--assessment",
        action="append",
        default=None,
        metavar="ID",
        help="Reference to an assessment (repeatable).",
    )
    create.add_argument(
        "--impact",
        action="append",
        default=None,
        metavar="ID",
        help="Reference to an impact_analysis (repeatable).",
    )
    create.add_argument(
        "--context",
        action="append",
        default=None,
        metavar="ID",
        help="Reference to a context_bundle (repeatable).",
    )
    create.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path to the AIP archive.",
    )
    create.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional extra output path. The workspace is always also "
            "persisted to <archive>/workspaces/<id>.json."
        ),
    )
    create.set_defaults(_cmd=workspace_create_command)

    show = sub.add_parser(
        "show",
        help="Read a persisted workspace from the archive.",
    )
    show.add_argument(
        "workspace_id", help="Workspace identifier."
    )
    show.add_argument(
        "--archive", required=True, type=Path, help="Path to the AIP archive."
    )
    show.set_defaults(_cmd=workspace_show_command)

    verify = sub.add_parser(
        "verify",
        help=(
            "Offline verification of workspace_hash. No archive access "
            "needed. rc=0 if valid, 1 if hash mismatch."
        ),
    )
    verify.add_argument(
        "workspace_file",
        type=Path,
        help="Path to the workspace.json to verify.",
    )
    verify.set_defaults(_cmd=workspace_verify_command)
