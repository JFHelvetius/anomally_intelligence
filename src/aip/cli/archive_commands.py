"""Subcomando ``aip archive verify`` (Pre-F1.D §3)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import IO

from aip.archive import Archive, VerificationReport
from aip.errors import UsageError


def verify_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    if args.quick and args.full:
        raise UsageError("--quick and --full are mutually exclusive.")

    full = not args.quick  # default --full

    archive = Archive.open(args.archive_root)
    report = archive.verify(full=full)

    if args.quiet:
        return 0 if report.ok else 3  # IntegrityError code

    if args.json:
        _print_verify_json(report, stdout=stdout, archive=archive, full=full)
    else:
        _print_verify_human(report, stdout=stdout, archive=archive, full=full)

    return 0 if report.ok else 3


# --------------------------------------------------------------------- formatters


def _print_verify_human(
    report: VerificationReport,
    *,
    stdout: IO[str],
    archive: Archive,
    full: bool,
) -> None:
    stdout.write(f"Verifying archive at {archive.root} ...\n\n")
    for check in report.checks:
        status = "OK  " if check.ok else "FAIL"
        stdout.write(f"  {check.name:<20s} {status}  {check.detail}\n")
    stdout.write("\n")
    if report.ok:
        stdout.write("Archive integrity verified.\n")
    else:
        stdout.write("Archive integrity FAILED. See errors above.\n")
    stdout.write(f"  Evidences:        {report.counts.get('evidences', 0)}\n")
    stdout.write(f"  Sources:          {report.counts.get('sources', 0)}\n")
    stdout.write(
        f"  Provenance steps: {report.counts.get('provenance_steps', 0)}\n"
    )
    stdout.write(f"  Audit entries:    {report.counts.get('audit_entries', 0)}\n")
    stdout.write(f"  Archive manifest: {report.archive_manifest_hash}\n")


def _print_verify_json(
    report: VerificationReport,
    *,
    stdout: IO[str],
    archive: Archive,
    full: bool,
) -> None:
    payload = {
        "ok": report.ok,
        "archive_root": str(archive.root),
        "mode": "full" if full else "quick",
        "checks": {
            c.name: {"ok": c.ok, "detail": c.detail} for c in report.checks
        },
        "summary": {
            **report.counts,
            "archive_manifest_hash": report.archive_manifest_hash,
        },
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------- argparse


def add_archive_subparser(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> None:
    parents = parents or []
    archive = subparsers.add_parser(
        "archive",
        help="Operations on the archive (verify).",
    )
    sub = archive.add_subparsers(dest="archive_action", required=True)

    verify = sub.add_parser(
        "verify",
        help="Verify archive integrity.",
        parents=parents,
    )
    g = verify.add_mutually_exclusive_group()
    g.add_argument(
        "--full",
        action="store_true",
        help="Full mode: include blob rehashing (default).",
    )
    g.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: skip blob rehashing.",
    )
    verify.set_defaults(_cmd=verify_command)
