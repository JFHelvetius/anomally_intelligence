"""Subgrupo CLI ``aip timeline`` (ADR-0037 §CLI)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.errors import AIPError
from aip.timeline import (
    build_timeline,
    decode_timeline,
    encode_timeline,
    load_timeline,
    persist_timeline,
    verify_timeline_hash,
)
from aip.workspace import load_workspace


def timeline_build_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    workspace = load_workspace(
        archive_root=args.archive, workspace_id=args.workspace_id
    )
    timeline = build_timeline(
        archive_root=args.archive,
        workspace=workspace,
        timeline_id=args.timeline_id,
    )
    persist_timeline(
        timeline,
        archive_root=args.archive,
        actor=args.actor,
        clock=lambda: dt.datetime.now(dt.UTC),
        extra_output=args.output,
    )
    stdout.write(encode_timeline(timeline))
    return 0


def timeline_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    timeline = load_timeline(
        archive_root=args.archive, timeline_id=args.timeline_id
    )
    stdout.write(encode_timeline(timeline))
    return 0


def timeline_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    path: Path = args.timeline_file
    if not path.is_file():
        raise AIPError(f"timeline file not found: {path}")
    timeline = decode_timeline(path.read_text(encoding="utf-8"))
    ok = verify_timeline_hash(timeline)
    payload = {
        "ok": ok,
        "action": "timeline_verify",
        "timeline_file": str(path),
        "timeline_id": timeline.timeline_id,
        "timeline_hash": timeline.timeline_hash,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0 if ok else 1


def add_timeline_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "timeline",
        help=(
            "Investigation Timeline (ADR-0037). Chronologically ordered "
            "view over workspace references. Read-only — does not "
            "execute analytical engines."
        ),
    )
    sub = grp.add_subparsers(dest="timeline_action", required=True)

    build = sub.add_parser(
        "build", help="Build a timeline from a workspace."
    )
    build.add_argument("--workspace-id", required=True)
    build.add_argument("--timeline-id", required=True)
    build.add_argument("--archive", required=True, type=Path)
    build.add_argument("--output", type=Path, default=None)
    build.add_argument(
        "--actor",
        required=True,
        help=(
            "ActorId that builds the timeline. Recorded in the audit "
            "log (ADR-0019 §enmienda E1, ActionKind.BUILD_TIMELINE)."
        ),
    )
    build.set_defaults(_cmd=timeline_build_command)

    show = sub.add_parser(
        "show", help="Read a persisted timeline."
    )
    show.add_argument("timeline_id")
    show.add_argument("--archive", required=True, type=Path)
    show.set_defaults(_cmd=timeline_show_command)

    verify = sub.add_parser(
        "verify",
        help=(
            "Offline verification of timeline_hash. No archive access "
            "needed. rc=0 if valid, 1 if mismatch."
        ),
    )
    verify.add_argument("timeline_file", type=Path)
    verify.set_defaults(_cmd=timeline_verify_command)
