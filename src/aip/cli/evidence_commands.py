"""Subcomandos ``aip evidence ingest`` y ``aip evidence show`` (Pre-F1.D §1 §2)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.archive import Archive, EvidenceView
from aip.core.evidence import Evidence, EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind

# --------------------------------------------------------------------- ingest


def ingest_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    """Implementa ``aip evidence ingest``.

    Devuelve exit code conforme a Pre-F1.D §G5.
    """
    archive = Archive.open(args.archive_root)
    evidence = archive.ingest_evidence(
        path=args.path,
        source_id=args.source_id,
        source_name=args.source_name,
        source_kind=args.source_kind,
        source_authority=args.source_authority,
        source_jurisdiction=args.source_jurisdiction,
        source_license=args.source_license,
        evidence_kind=args.kind,
        mime_type=args.mime_type,
        ingested_by=args.ingested_by,
        notes=args.notes,
        dry_run=args.dry_run,
    )

    if args.quiet:
        return 0

    if args.json:
        _print_ingest_json(evidence, stdout=stdout, archive=archive, dry_run=args.dry_run)
    else:
        _print_ingest_human(evidence, stdout=stdout, archive=archive, dry_run=args.dry_run)
    return 0


def _print_ingest_human(
    evidence: Evidence,
    *,
    stdout: IO[str],
    archive: Archive,
    dry_run: bool,
) -> None:
    label = "Would ingest evidence (dry-run):" if dry_run else "Ingested evidence:"
    stdout.write(f"{label}\n")
    stdout.write(f"  Hash:        sha256:{evidence.hash}\n")
    stdout.write(f"  Kind:        {evidence.kind.value}\n")
    stdout.write(f"  Size:        {evidence.size_bytes} bytes\n")
    stdout.write(f"  MIME:        {evidence.mime_type}\n")
    stdout.write(f"  Source:      {evidence.source_id}\n")
    stdout.write(f"  Ingested by: {evidence.ingested_by}\n")
    stdout.write(f"  Ingested at: {_iso_utc(evidence.ingested_at)}\n")
    stdout.write(f"  Archive:     {archive.root}\n")
    stdout.write(f"  URI:         {evidence.aip_uri()}\n")


def _print_ingest_json(
    evidence: Evidence,
    *,
    stdout: IO[str],
    archive: Archive,
    dry_run: bool,
) -> None:
    payload = {
        "ok": True,
        "action": "ingest_evidence" if not dry_run else "ingest_evidence_dry_run",
        "evidence": {
            "uri": evidence.aip_uri(),
            "hash": evidence.hash,
            "kind": evidence.kind.value,
            "size_bytes": evidence.size_bytes,
            "mime_type": evidence.mime_type,
            "source_id": evidence.source_id,
            "ingested_at": _iso_utc(evidence.ingested_at),
            "ingested_by": evidence.ingested_by,
            "schema_version": evidence.schema_version,
        },
        "archive_root": str(archive.root),
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------- show


def show_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    archive = Archive.open(args.archive_root)
    view = archive.show_evidence(args.hash_or_uri)
    if args.quiet:
        return 0
    if args.json:
        _print_show_json(view, stdout=stdout)
    else:
        _print_show_human(view, stdout=stdout)
    return 0


def _print_show_human(view: EvidenceView, *, stdout: IO[str]) -> None:
    e = view.evidence
    stdout.write(f"Evidence: {e.aip_uri()}\n\n")
    stdout.write(f"  Hash:           sha256:{e.hash}\n")
    stdout.write(f"  Kind:           {e.kind.value}\n")
    stdout.write(f"  MIME:           {e.mime_type}\n")
    stdout.write(f"  Size:           {e.size_bytes} bytes\n")
    stdout.write(f"  Status:         {e.status.value}\n")
    stdout.write(f"  Schema version: {e.schema_version}\n\n")
    stdout.write(f"  Ingested at:    {_iso_utc(e.ingested_at)}\n")
    stdout.write(f"  Ingested by:    {e.ingested_by}\n\n")

    s = view.source
    stdout.write("Source:\n")
    stdout.write(f"  ID:           {s.id}\n")
    stdout.write(f"  Name:         {s.name}\n")
    stdout.write(f"  Kind:         {s.kind.value}\n")
    stdout.write(f"  Authority:    {s.authority.value}\n")
    if s.jurisdiction is not None:
        stdout.write(f"  Jurisdiction: {s.jurisdiction}\n")
    if s.license is not None:
        stdout.write(f"  License:      {s.license}\n")
    stdout.write("\n")

    if view.provenance is not None:
        p = view.provenance
        stdout.write("Provenance:\n")
        stdout.write(f"  Is complete:  {str(p.is_complete).lower()}\n")
        for step in p.steps:
            actor = step.actor or "unknown"
            stdout.write(f"  Step {step.step_id}:       {step.kind.value} (actor: {actor})\n")
        for i, gap in enumerate(p.gaps, 1):
            stdout.write(f"  Gap {i}:        {gap.description}\n")
        stdout.write("\n")

    a = e.authentication
    stdout.write("Authentication:\n")
    stdout.write(f"  Status:    {a.status.value}\n")
    stdout.write(f"  Assessor:  {a.assessor or '—'}\n")
    stdout.write(f"  Method:    {a.method or '—'}\n")


def _print_show_json(view: EvidenceView, *, stdout: IO[str]) -> None:
    e = view.evidence
    s = view.source
    payload: dict[str, object] = {
        "ok": True,
        "evidence": {
            "uri": e.aip_uri(),
            "hash": e.hash,
            "kind": e.kind.value,
            "mime_type": e.mime_type,
            "size_bytes": e.size_bytes,
            "status": e.status.value,
            "schema_version": e.schema_version,
            "ingested_at": _iso_utc(e.ingested_at),
            "ingested_by": e.ingested_by,
            "intrinsic_metadata": dict(e.intrinsic_metadata),
            "notes": e.notes,
        },
        "source": {
            "id": s.id,
            "name": s.name,
            "kind": s.kind.value,
            "authority": s.authority.value,
            "jurisdiction": s.jurisdiction,
            "license": s.license,
        },
        "authentication": {
            "status": e.authentication.status.value,
            "assessor": e.authentication.assessor,
            "method": e.authentication.method,
        },
    }
    if view.provenance is not None:
        p = view.provenance
        payload["provenance"] = {
            "is_complete": p.is_complete,
            "steps": [
                {
                    "step_id": step.step_id,
                    "kind": step.kind.value,
                    "actor": step.actor,
                }
                for step in p.steps
            ],
            "gaps": [{"description": g.description} for g in p.gaps],
        }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------- argparse builders


def add_evidence_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> None:
    parents = parents or []
    evidence = subparsers.add_parser(
        "evidence",
        help="Operations on evidence (ingest, show).",
    )
    evidence_sub = evidence.add_subparsers(dest="evidence_action", required=True)

    # --- ingest ---
    ingest = evidence_sub.add_parser(
        "ingest",
        help="Ingest a local file as evidence.",
        parents=parents,
    )
    ingest.add_argument("path", type=Path, help="Path to the file to ingest.")
    ingest.add_argument(
        "--source-id", required=True, help="Identifier of the Source."
    )
    ingest.add_argument(
        "--source-name",
        default=None,
        help="Human name of the Source (required when creating new).",
    )
    ingest.add_argument(
        "--source-kind",
        type=SourceKind,
        choices=list(SourceKind),
        default=None,
        help="One of SourceKind (ADR-0005).",
    )
    ingest.add_argument(
        "--source-authority",
        type=AuthorityLevel,
        choices=list(AuthorityLevel),
        default=None,
        help="One of AuthorityLevel.",
    )
    ingest.add_argument("--source-jurisdiction", default=None)
    ingest.add_argument("--source-license", default=None)
    ingest.add_argument(
        "--kind",
        type=EvidenceKind,
        choices=list(EvidenceKind),
        default=None,
        help="One of EvidenceKind (inferred from extension if omitted).",
    )
    ingest.add_argument("--mime-type", default=None)
    ingest.add_argument(
        "--ingested-by",
        required=True,
        help="ActorId of the ingestor.",
    )
    ingest.add_argument("--notes", default=None)
    ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute hash and validate metadata without writing the archive.",
    )
    ingest.set_defaults(_cmd=ingest_command)

    # --- show ---
    show = evidence_sub.add_parser(
        "show",
        help="Show evidence by hash or URI.",
        parents=parents,
    )
    show.add_argument(
        "hash_or_uri",
        help="SHA-256 hex, sha256:<hex>, or aip:evidence/sha256:<hex>.",
    )
    show.set_defaults(_cmd=show_command)


# --------------------------------------------------------------------- helpers


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
