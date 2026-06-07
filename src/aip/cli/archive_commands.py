"""Subcomando ``aip archive verify`` (Pre-F1.D §3 + post-ADR-0040 hardening)."""

from __future__ import annotations

import argparse
import json
from typing import IO

from aip.archive import Archive, VerificationReport
from aip.errors import UsageError
from aip.integrity import DerivedIntegrityReport, verify_derived_integrity


def verify_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    if args.quick and args.full:
        raise UsageError("--quick and --full are mutually exclusive.")

    full = not args.quick  # default --full

    archive = Archive.open(args.archive_root)
    report = archive.verify(full=full)

    derived_report: DerivedIntegrityReport | None = None
    if args.derived:
        derived_report = verify_derived_integrity(archive.root)

    overall_ok = report.ok and (
        derived_report is None or derived_report.ok
    )

    if args.quiet:
        return 0 if overall_ok else 3

    if args.json:
        _print_verify_json(
            report,
            stdout=stdout,
            archive=archive,
            full=full,
            derived_report=derived_report,
        )
    else:
        _print_verify_human(
            report,
            stdout=stdout,
            archive=archive,
            full=full,
            derived_report=derived_report,
        )

    return 0 if overall_ok else 3


# --------------------------------------------------------------------- formatters


def _print_verify_human(
    report: VerificationReport,
    *,
    stdout: IO[str],
    archive: Archive,
    full: bool,
    derived_report: DerivedIntegrityReport | None,
) -> None:
    stdout.write(f"Verifying archive at {archive.root} ...\n\n")
    for check in report.checks:
        status = "OK  " if check.ok else "FAIL"
        stdout.write(f"  {check.name:<22s} {status}  {check.detail}\n")
    if derived_report is not None:
        derived_status = "OK  " if derived_report.ok else "FAIL"
        stdout.write(
            f"  {'derived_integrity':<22s} {derived_status}  "
            f"{derived_report.total_checked} derived artifacts, "
            f"{len(derived_report.issues)} issues\n"
        )
    stdout.write("\n")
    overall_ok = report.ok and (
        derived_report is None or derived_report.ok
    )
    if overall_ok:
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
    if derived_report is not None:
        stdout.write(
            f"  Workspaces:       {derived_report.workspaces_checked}\n"
        )
        stdout.write(
            f"  Timelines:        {derived_report.timelines_checked}\n"
        )
        stdout.write(
            f"  Snapshots:        {derived_report.snapshots_checked}\n"
        )
        stdout.write(
            f"  Justifications:   {derived_report.justifications_checked}\n"
        )
        if derived_report.issues:
            stdout.write("\nDerived integrity issues:\n")
            for issue in derived_report.issues:
                stdout.write(
                    f"  - [{issue.artifact_kind}:{issue.artifact_id}] "
                    f"{issue.issue_kind}: {issue.detail}\n"
                )


def _print_verify_json(
    report: VerificationReport,
    *,
    stdout: IO[str],
    archive: Archive,
    full: bool,
    derived_report: DerivedIntegrityReport | None,
) -> None:
    checks_dict: dict[str, dict[str, object]] = {
        c.name: {"ok": c.ok, "detail": c.detail} for c in report.checks
    }
    if derived_report is not None:
        checks_dict["derived_integrity"] = {
            "ok": derived_report.ok,
            "detail": (
                f"{derived_report.total_checked} derived artifacts, "
                f"{len(derived_report.issues)} issues"
            ),
        }
    summary_dict: dict[str, object] = {
        **report.counts,
        "archive_manifest_hash": report.archive_manifest_hash,
    }
    if derived_report is not None:
        summary_dict["workspaces_checked"] = derived_report.workspaces_checked
        summary_dict["timelines_checked"] = derived_report.timelines_checked
        summary_dict["snapshots_checked"] = derived_report.snapshots_checked
        summary_dict["justifications_checked"] = (
            derived_report.justifications_checked
        )
    payload: dict[str, object] = {
        "ok": report.ok and (
            derived_report is None or derived_report.ok
        ),
        "archive_root": str(archive.root),
        "mode": "full" if full else "quick",
        "checks": checks_dict,
        "summary": summary_dict,
    }
    if derived_report is not None:
        payload["derived_integrity_issues"] = [
            {
                "artifact_kind": issue.artifact_kind,
                "artifact_id": issue.artifact_id,
                "issue_kind": issue.issue_kind,
                "detail": issue.detail,
            }
            for issue in derived_report.issues
        ]
        payload["derived_integrity_engine_version"] = (
            derived_report.integrity_engine_version
        )
        payload["derived_integrity_method_name"] = (
            derived_report.integrity_method_name
        )
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------- argparse


def add_archive_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
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
    verify.add_argument(
        "--derived",
        action="store_true",
        help=(
            "Also audit derived artifacts persisted under "
            "<archive>/{workspaces,timelines,snapshots,justifications}/. "
            "Opt-in. Default behavior unchanged."
        ),
    )
    verify.set_defaults(_cmd=verify_command)
