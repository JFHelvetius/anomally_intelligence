"""Subgrupo CLI ``aip justification`` (ADR-0040 §CLI)."""

from __future__ import annotations

import argparse
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
        j, archive_root=args.archive, extra_output=args.output
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
