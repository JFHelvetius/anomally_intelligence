"""Subgrupo CLI ``aip diff`` (ADR-0039 §CLI)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import IO

from aip.diff import compute_diff, decode_diff, encode_diff
from aip.errors import AIPError
from aip.snapshot import decode_snapshot


def diff_snapshots_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    a_path: Path = args.snapshot_a
    b_path: Path = args.snapshot_b
    if not a_path.is_file():
        raise AIPError(f"snapshot file not found: {a_path}")
    if not b_path.is_file():
        raise AIPError(f"snapshot file not found: {b_path}")
    snapshot_a = decode_snapshot(a_path.read_text(encoding="utf-8"))
    snapshot_b = decode_snapshot(b_path.read_text(encoding="utf-8"))
    diff = compute_diff(snapshot_a, snapshot_b)
    payload = encode_diff(diff)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    # Discard return of decode_diff round-trip (defensive: confirma
    # auto-consistencia del payload generado).
    decode_diff(payload)
    stdout.write(payload)
    return 0


def add_diff_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "diff",
        help=(
            "Investigation Diff (ADR-0039). Pure set-difference "
            "comparison between two snapshots."
        ),
    )
    sub = grp.add_subparsers(dest="diff_action", required=True)

    snapshots = sub.add_parser(
        "snapshots",
        help=(
            "Compare two snapshot.json files. Reports added/removed/"
            "unchanged artifacts plus diff_hash."
        ),
    )
    snapshots.add_argument("snapshot_a", type=Path)
    snapshots.add_argument("snapshot_b", type=Path)
    snapshots.add_argument("--output", type=Path, default=None)
    snapshots.set_defaults(_cmd=diff_snapshots_command)
