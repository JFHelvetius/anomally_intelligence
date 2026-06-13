"""Subgrupo CLI ``aip diff`` (ADR-0039 §CLI + ADR-0040 §CLI).

Also hosts ``aip diff archives`` (cross-archive divergence detection).
That subcommand is per-archive content comparison, not snapshot
set-difference like the other two; it lives in the same group because
"compare two of X" is the user-facing mental model.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import IO

from aip.archive_compare import compare_archives
from aip.diff import compute_diff, decode_diff, encode_diff
from aip.errors import AIPError
from aip.justification import (
    compute_justification_diff,
    decode_justification,
    decode_justification_diff,
    encode_justification_diff,
)
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


def diff_justifications_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    a_path: Path = args.justification_a
    b_path: Path = args.justification_b
    if not a_path.is_file():
        raise AIPError(f"justification file not found: {a_path}")
    if not b_path.is_file():
        raise AIPError(f"justification file not found: {b_path}")
    j_a = decode_justification(a_path.read_text(encoding="utf-8"))
    j_b = decode_justification(b_path.read_text(encoding="utf-8"))
    if j_a.schema_version != j_b.schema_version:
        raise AIPError(
            f"schema_version mismatch: {j_a.schema_version!r} vs "
            f"{j_b.schema_version!r}."
        )
    diff = compute_justification_diff(j_a, j_b)
    payload = encode_justification_diff(diff)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    decode_justification_diff(payload)
    stdout.write(payload)
    return 0


def diff_archives_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Compare two archives and emit the cross-archive divergence report.

    Exit code 0 when no shared artifact disagrees, 1 when at least one does.
    Always emits JSON to stdout, regardless of ``--quiet`` (the report IS
    the output; suppressing it defeats the purpose).
    """
    a_root: Path = args.archive_a
    b_root: Path = args.archive_b
    if not a_root.is_dir():
        raise AIPError(f"archive root not found: {a_root}")
    if not b_root.is_dir():
        raise AIPError(f"archive root not found: {b_root}")

    report = compare_archives(
        a_root, b_root, label_a=args.label_a, label_b=args.label_b
    )

    payload: dict[str, object] = {
        "ok": not report.has_divergence,
        "action": "diff_archives",
        "archive_a_label": report.archive_a_label,
        "archive_b_label": report.archive_b_label,
        "shared_evidence_count": report.shared_count,
        "shared_evidence": [
            {
                **asdict(e),
                "diverging_param_fields": list(e.diverging_param_fields),
            }
            for e in report.shared_evidence
        ],
        "a_only_evidence_hashes": list(report.a_only_evidence_hashes),
        "b_only_evidence_hashes": list(report.b_only_evidence_hashes),
        "shared_proofs": [
            {**asdict(p), "matches": p.matches} for p in report.shared_proofs
        ],
        "a_only_proof_ids": list(report.a_only_proof_ids),
        "b_only_proof_ids": list(report.b_only_proof_ids),
        "has_divergence": report.has_divergence,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 1 if report.has_divergence else 0


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

    justifications = sub.add_parser(
        "justifications",
        help=(
            "Compare two justification.json files. Reports added/"
            "removed/unchanged chain entries plus diff_hash."
        ),
    )
    justifications.add_argument("justification_a", type=Path)
    justifications.add_argument("justification_b", type=Path)
    justifications.add_argument("--output", type=Path, default=None)
    justifications.set_defaults(_cmd=diff_justifications_command)

    archives = sub.add_parser(
        "archives",
        help=(
            "Cross-archive divergence: compare two archives and report "
            "shared evidence / proofs that disagree byte-for-byte. "
            "rc=0 if no disagreement on shared artifacts, 1 if any."
        ),
    )
    archives.add_argument(
        "archive_a", type=Path, help="Path to the first archive root."
    )
    archives.add_argument(
        "archive_b", type=Path, help="Path to the second archive root."
    )
    archives.add_argument(
        "--label-a",
        default=None,
        help="Optional human label for archive A in the output (default: dir name).",
    )
    archives.add_argument(
        "--label-b",
        default=None,
        help="Optional human label for archive B in the output (default: dir name).",
    )
    archives.set_defaults(_cmd=diff_archives_command)
