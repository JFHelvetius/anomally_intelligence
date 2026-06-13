"""Subgrupo CLI ``aip justification`` (ADR-0040 §CLI)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.errors import AIPError
from aip.justification import (
    build_justification,
    decode_justification,
    encode_justification,
    load_justification,
    persist_justification,
    verify_justification_hash,
)
from aip.justification.logic import (
    decode_proof,
    verify_proof_hash,
    verify_structural,
)


def justification_build_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    j = build_justification(
        archive_root=args.archive,
        conclusion_anchor_type=args.conclusion_anchor_type,
        conclusion_anchor_id=args.conclusion_anchor_id,
        justification_id=args.justification_id,
        workspace_id=args.workspace_id,
    )
    persist_justification(
        j,
        archive_root=args.archive,
        actor=args.actor,
        clock=lambda: dt.datetime.now(dt.UTC),
        extra_output=args.output,
    )
    stdout.write(encode_justification(j))
    return 0


def justification_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    j = load_justification(
        archive_root=args.archive,
        justification_id=args.justification_id,
    )
    stdout.write(encode_justification(j))
    return 0


def justification_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    path: Path = args.justification_file
    if not path.is_file():
        raise AIPError(f"justification file not found: {path}")
    j = decode_justification(path.read_text(encoding="utf-8"))
    ok = verify_justification_hash(j)
    payload = {
        "ok": ok,
        "action": "justification_verify",
        "justification_file": str(path),
        "justification_id": j.justification_id,
        "justification_hash": j.justification_hash,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0 if ok else 1


def justification_verify_logic_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Verifica estructura de un :class:`InferenceProof` (Phase epistémica).

    Devuelve rc=0 si la DAG es estructuralmente válida (sin importar si las
    premisas son ciertas — eso es del analista). rc=1 si hay errores
    estructurales (ciclos, refs rotas, rules desconocidas, etc.).
    """
    proof_path_arg: Path = args.proof_file
    if not proof_path_arg.is_file():
        raise AIPError(f"inference proof file not found: {proof_path_arg}")
    proof = decode_proof(proof_path_arg.read_text(encoding="utf-8"))

    # First: proof_hash structural self-check. If it fails, the proof is
    # tampered with — reject before doing DAG analysis.
    hash_ok = verify_proof_hash(proof)
    if not hash_ok:
        payload = {
            "ok": False,
            "action": "justification_verify_logic",
            "proof_file": str(proof_path_arg),
            "proof_id": proof.proof_id,
            "errors": ["proof_hash mismatch — the proof has been tampered with."],
        }
        stdout.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )
        return 1

    # Optional: bind to a specific target justification if provided.
    target_match: bool | None = None
    if args.target_justification is not None:
        if not args.target_justification.is_file():
            raise AIPError(
                f"target justification file not found: {args.target_justification}"
            )
        target_j = decode_justification(
            args.target_justification.read_text(encoding="utf-8")
        )
        target_match = (
            target_j.justification_hash == proof.target_justification_hash
            and target_j.justification_id == proof.target_justification_id
        )

    result = verify_structural(proof)

    payload: dict[str, object] = {
        "ok": result.ok and (target_match is not False),
        "action": "justification_verify_logic",
        "proof_file": str(proof_path_arg),
        "proof_id": proof.proof_id,
        "proof_hash": proof.proof_hash,
        "target_justification_id": proof.target_justification_id,
        "target_justification_hash": proof.target_justification_hash,
        "conclusion_claim_id": proof.conclusion_claim_id,
        "structure": result.structure,
        "weak_inferences": [
            {
                "inference_id": w.inference_id,
                "rule": w.rule,
                "output_claim_id": w.output_claim_id,
            }
            for w in result.weak_inferences
        ],
        "errors": list(result.errors),
    }
    if target_match is not None:
        payload["target_match"] = target_match
        if not target_match:
            payload["errors"] = [
                *payload["errors"],
                "target_justification provided does not match the proof's "
                "target_justification_id and/or target_justification_hash.",
            ]

    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if payload["ok"] else 1


def add_justification_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "justification",
        help=(
            "Investigation Justification (ADR-0040). Deductive chain "
            "anchored on a conclusion. Read-only — categorized lookup, "
            "no inference."
        ),
    )
    sub = grp.add_subparsers(
        dest="justification_action", required=True
    )

    build = sub.add_parser(
        "build",
        help=(
            "Build a justification from a conclusion anchor (V1: "
            "assessment)."
        ),
    )
    build.add_argument(
        "--conclusion-anchor-type",
        required=True,
        choices=["assessment"],
    )
    build.add_argument("--conclusion-anchor-id", required=True)
    build.add_argument("--justification-id", required=True)
    build.add_argument("--workspace-id", default=None)
    build.add_argument("--archive", required=True, type=Path)
    build.add_argument("--output", type=Path, default=None)
    build.add_argument(
        "--actor",
        required=True,
        help=(
            "ActorId that builds the justification. Recorded in the "
            "audit log (ADR-0019 §enmienda E1, "
            "ActionKind.BUILD_JUSTIFICATION)."
        ),
    )
    build.set_defaults(_cmd=justification_build_command)

    show = sub.add_parser(
        "show", help="Read a persisted justification."
    )
    show.add_argument("justification_id")
    show.add_argument("--archive", required=True, type=Path)
    show.set_defaults(_cmd=justification_show_command)

    verify = sub.add_parser(
        "verify",
        help=(
            "Offline verification of justification_hash. No archive "
            "access. rc=0 if valid, 1 if mismatch."
        ),
    )
    verify.add_argument("justification_file", type=Path)
    verify.set_defaults(_cmd=justification_verify_command)

    verify_logic = sub.add_parser(
        "verify-logic",
        help=(
            "Structural verification of an InferenceProof (machine-checkable "
            "reasoning layer). Checks: rule vocabulary, arity, refs exist, "
            "DAG acyclic, conclusion reachable from premises. Flags weak "
            "(non-deductive) inferences. Does NOT verify truth of premises."
        ),
    )
    verify_logic.add_argument("proof_file", type=Path)
    verify_logic.add_argument(
        "--target-justification",
        type=Path,
        default=None,
        help=(
            "Optional path to the InvestigationJustification this proof "
            "targets. When provided, verifies that the proof's "
            "target_justification_id and target_justification_hash match."
        ),
    )
    verify_logic.set_defaults(_cmd=justification_verify_logic_command)
