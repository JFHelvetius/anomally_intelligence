"""Subgrupo CLI ``aip snapshot`` (ADR-0038 §CLI)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.errors import AIPError
from aip.snapshot import (
    create_snapshot,
    decode_snapshot,
    encode_snapshot,
    load_snapshot,
    persist_snapshot,
    verify_snapshot,
)
from aip.timeline import load_timeline
from aip.workspace import load_workspace


def snapshot_create_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    workspace = load_workspace(
        archive_root=args.archive, workspace_id=args.workspace_id
    )
    timeline = load_timeline(
        archive_root=args.archive, timeline_id=args.timeline_id
    )
    snapshot = create_snapshot(
        snapshot_id=args.snapshot_id,
        workspace=workspace,
        timeline=timeline,
    )
    persist_snapshot(
        snapshot,
        archive_root=args.archive,
        actor=args.actor,
        clock=lambda: dt.datetime.now(dt.UTC),
        extra_output=args.output,
    )
    stdout.write(encode_snapshot(snapshot))
    return 0


def snapshot_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    snapshot = load_snapshot(
        archive_root=args.archive, snapshot_id=args.snapshot_id
    )
    stdout.write(encode_snapshot(snapshot))
    return 0


def snapshot_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    path: Path = args.snapshot_file
    if not path.is_file():
        raise AIPError(f"snapshot file not found: {path}")
    snapshot = decode_snapshot(path.read_text(encoding="utf-8"))
    ok = verify_snapshot(snapshot)
    payload = {
        "ok": ok,
        "action": "snapshot_verify",
        "snapshot_file": str(path),
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": snapshot.snapshot_hash,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0 if ok else 1


def add_snapshot_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "snapshot",
        help=(
            "Investigation Snapshot (ADR-0038). Freezes a (workspace, "
            "timeline) pair as a verifiable reference-only artifact."
        ),
    )
    sub = grp.add_subparsers(dest="snapshot_action", required=True)

    create = sub.add_parser(
        "create", help="Create a snapshot from a workspace + timeline pair."
    )
    create.add_argument("--snapshot-id", required=True)
    create.add_argument("--workspace-id", required=True)
    create.add_argument("--timeline-id", required=True)
    create.add_argument("--archive", required=True, type=Path)
    create.add_argument("--output", type=Path, default=None)
    create.add_argument(
        "--actor",
        required=True,
        help=(
            "ActorId that creates the snapshot. Recorded in the audit "
            "log (ADR-0019 §enmienda E1, ActionKind.BUILD_SNAPSHOT)."
        ),
    )
    create.set_defaults(_cmd=snapshot_create_command)

    show = sub.add_parser(
        "show", help="Read a persisted snapshot."
    )
    show.add_argument("snapshot_id")
    show.add_argument("--archive", required=True, type=Path)
    show.set_defaults(_cmd=snapshot_show_command)

    verify = sub.add_parser(
        "verify",
        help=(
            "Offline verification of snapshot_hash. No archive access "
            "needed. rc=0 if valid, 1 if mismatch."
        ),
    )
    verify.add_argument("snapshot_file", type=Path)
    verify.set_defaults(_cmd=snapshot_verify_command)
