"""Subcomandos ``aip evidence ingest`` y ``aip evidence show`` (Pre-F1.D §1 §2)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO, Any

from aip.archive import Archive, EvidenceView
from aip.core.evidence import Evidence, EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.errors import AIPError
from aip.report import build_report_html, load_report_data

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
        capture_certificate_path=args.capture_cert,
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


# --------------------------------------------------------------------- report


def _maybe_verify_trust_footprint(
    args: argparse.Namespace, archive_root: Path
) -> dict[str, Any] | None:
    """ADR-0045: optionally cross-verify the operator's external references.

    Runs ``aip.transparency.footprint_verifier.verify_declaration`` when
    ``--verify-trust-footprint`` is set, and returns a JSON-friendly dict
    that the report builder embeds. Returns ``None`` if the flag is unset
    or the archive has no key declaration.
    """
    if not getattr(args, "verify_trust_footprint", False):
        return None

    # Lazy imports: a report build without the flag must not depend on
    # the verifier module loading the network stack.
    from aip.transparency.footprint_verifier import (  # noqa: PLC0415
        verify_declaration as _verify_footprint,
    )
    from aip.transparency.key_declaration import (  # noqa: PLC0415
        load_declaration as _load_decl,
    )

    decl = _load_decl(archive_root)
    if decl is None:
        return None

    try:
        vreport = _verify_footprint(
            decl, timeout=args.verify_trust_footprint_timeout
        )
    except AIPError as exc:
        # Surface a degraded report honestly rather than pretending it
        # succeeded.
        return {"error": str(exc), "references": []}

    return {
        "operator_id": vreport.operator_id,
        "declared_fingerprint": vreport.declared_fingerprint,
        "references": [
            {
                "kind": r.kind,
                "uri": r.uri,
                "status": r.status,
                "fetched_fingerprint": r.fetched_fingerprint,
                "declared_fingerprint": r.declared_fingerprint,
                "reason": r.reason,
            }
            for r in vreport.references
        ],
    }


def report_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    """Genera un HTML auto-contenido con todo el chain de confianza para esta
    evidencia. El receptor lo abre en cualquier navegador y el navegador
    recompute las hashes via SubtleCrypto sin necesidad de backend.
    """
    out_path: Path = args.out
    archive_root: Path = args.archive_root

    # Normalize hash_or_uri to plain hex.
    raw = args.hash_or_uri.strip()
    if raw.startswith("aip:evidence/sha256:"):
        evidence_hash = raw[len("aip:evidence/sha256:"):]
    elif raw.startswith("sha256:"):
        evidence_hash = raw[len("sha256:"):]
    else:
        evidence_hash = raw

    # Parse --bitcoin-header HEIGHT:HEX flags (may repeat).
    # Bitcoin block header is exactly 80 bytes = 160 hex chars.
    btc_headers: dict[int, str] = {}
    btc_header_hex_len = 160
    for spec in (args.bitcoin_header or []):
        if ":" not in spec:
            raise AIPError(
                f"invalid --bitcoin-header {spec!r}; expected HEIGHT:HEX format."
            )
        height_str, hexstr = spec.split(":", 1)
        try:
            height = int(height_str)
        except ValueError as exc:
            raise AIPError(
                f"invalid block height in --bitcoin-header: {height_str!r}"
            ) from exc
        hexstr = hexstr.strip().lower()
        if len(hexstr) != btc_header_hex_len:
            raise AIPError(
                f"--bitcoin-header for height {height}: hex must be 80 bytes "
                f"({btc_header_hex_len} chars); got {len(hexstr)}."
            )
        if any(c not in "0123456789abcdef" for c in hexstr):
            raise AIPError(
                f"--bitcoin-header for height {height}: hex contains non-hex chars."
            )
        btc_headers[height] = hexstr

    footprint_verification = _maybe_verify_trust_footprint(args, archive_root)

    try:
        data = load_report_data(
            archive_root,
            evidence_hash,
            bitcoin_block_headers=btc_headers or None,
            footprint_verification=footprint_verification,
        )
    except Exception as exc:
        raise AIPError(f"failed to load report data: {exc}") from exc

    html = build_report_html(data, title=args.title)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    if args.quiet:
        return 0

    payload = {
        "ok": True,
        "action": "evidence_report",
        "evidence_hash": evidence_hash,
        "out_path": str(out_path),
        "size_bytes": out_path.stat().st_size,
        "sections": {
            "capture_certificate": data["capture_certificate"] is not None,
            "audit_entries": len(data["audit_chain"]),
            "coverage_manifests": len(data["coverage_manifests"]),
            "witnesses": sum(
                len(ws)
                for ws in data["witnesses_by_manifest_sequence"].values()
            ),
            "bitcoin_anchored_manifests": sum(
                1
                for v in data["notarization_by_manifest_sequence"].values()
                if v.get("bitcoin_anchors")
            ),
            "inference_proofs": len(data["inference_proofs"]),
        },
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
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
    stdout.write("Authentication (embedded slot):\n")
    stdout.write(f"  Status:    {a.status.value}\n")
    stdout.write(f"  Assessor:  {a.assessor or '—'}\n")
    stdout.write(f"  Method:    {a.method or '—'}\n\n")

    # Derived assessments (ADR-0032). Lista vacía = estado legítimo, no
    # error; el operador no ha corrido `aip assess-authentication` aún.
    stdout.write("Derived Assessments (ADR-0032):\n")
    if not view.derived_assessments:
        stdout.write(
            "  (none) — run `aip assess-authentication "
            f"--archive {{path}} --evidence-id {e.hash}` to produce one.\n"
        )
    else:
        for d in view.derived_assessments:
            stdout.write(
                f"  - {d.method.value:>26s} → {d.status.value:>20s}  "
                f"(created_at: {_iso_utc(d.created_at)})\n"
            )


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
    # Derived assessments (ADR-0032). Lista siempre presente — vacía si
    # nunca se corrió `aip assess-authentication`. La presencia explícita
    # del campo evita que consumidores externos confundan "no había
    # campo" con "no había assessments".
    payload["derived_assessments"] = [
        {
            "assessment_id": d.assessment_id,
            "evidence_id": d.evidence_id,
            "method": d.method.value,
            "status": d.status.value,
            "rationale": d.rationale,
            "supporting_source_ids": list(d.supporting_source_ids),
            "created_at": _iso_utc(d.created_at),
            "schema_version": d.schema_version,
        }
        for d in view.derived_assessments
    ]
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
        "--capture-cert",
        default=None,
        type=Path,
        help=(
            "Optional path to a signed CaptureCertificate JSON (Phase 2). When "
            "provided, the certificate is validated (self-hash + bytes match) "
            "and persisted as a sidecar under <archive>/capture-certificates/. "
            "The ORIGINAL_CAPTURE provenance step is enriched with the "
            "certificate's operator_id, captured_at, device_id and certificate_hash. "
            "Use 'aip capture sign' to create one."
        ),
    )
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

    # --- report ---
    report = evidence_sub.add_parser(
        "report",
        help=(
            "Generate a standalone, self-contained HTML report for this "
            "evidence. The report includes all data (evidence, capture cert, "
            "audit chain, manifests, witnesses, OTS anchors, inference proofs) "
            "and embedded JS that recomputes SHA-256(JCS) hashes client-side "
            "on load — verifiable by anyone in any modern browser, no backend "
            "needed."
        ),
        parents=parents,
    )
    report.add_argument(
        "hash_or_uri",
        help="SHA-256 hex, sha256:<hex>, or aip:evidence/sha256:<hex>.",
    )
    report.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for the HTML file.",
    )
    report.add_argument(
        "--title",
        default=None,
        help="Optional custom title (default: 'Evidence Report · sha256:<short>…').",
    )
    report.add_argument(
        "--bitcoin-header",
        action="append",
        default=None,
        metavar="HEIGHT:HEX",
        help=(
            "Optional Bitcoin block header for verification. Format: "
            "HEIGHT:80-byte-hex. May be repeated for multiple block heights. "
            "Obtain from a block explorer or 'bitcoin-cli getblockheader <hash> "
            "false'. When provided, the report's JS verifies the OTS-claimed "
            "merkle root matches the merkle root in the embedded header (bytes "
            "36..68, little-endian internal byte order)."
        ),
    )
    report.add_argument(
        "--verify-trust-footprint",
        action="store_true",
        help=(
            "ADR-0045: cross-verify each declared external reference at "
            "report build time and embed the verdicts. AIP fetches https_pem "
            "URLs and github_user_keys, computes fingerprints, and compares. "
            "Verdicts ride next to the declared row in the report HTML so "
            "the receptor sees both. Requires outbound HTTPS at build time."
        ),
    )
    report.add_argument(
        "--verify-trust-footprint-timeout",
        type=int,
        default=15,
        metavar="SECONDS",
        help="HTTPS timeout per reference when --verify-trust-footprint is set. Default: 15.",
    )
    report.set_defaults(_cmd=report_command)

    # ── evidence c2pa-verify ──────────────────────────────────────
    c2pa_cmd = evidence_sub.add_parser(
        "c2pa-verify",
        parents=parents,
        help=(
            "ADR-0046: verify a pre-extracted C2PA manifest JSON and "
            "persist the result as a sidecar attestation inside the "
            "archive. Use 'c2patool extract <file> --json' (or "
            "equivalent) to produce the manifest JSON. AIP does NOT "
            "extract from binary media in v1."
        ),
    )
    c2pa_cmd.add_argument(
        "manifest_json",
        type=Path,
        help="Path to the JSON file produced by your C2PA extractor.",
    )
    c2pa_cmd.add_argument(
        "--evidence-sha256",
        required=True,
        help="SHA-256 hex of the evidence the manifest binds to.",
    )
    c2pa_cmd.add_argument(
        "--trust-list",
        default=None,
        help=(
            "Optional name to record as 'trust_list_name' in the report. "
            "Default: 'c2pa-default-trust-list-v1'."
        ),
    )
    c2pa_cmd.add_argument(
        "--no-persist",
        action="store_true",
        help=(
            "Print the verification report to stdout without writing to "
            "<archive>/c2pa-attestations/. Useful for dry-runs."
        ),
    )
    c2pa_cmd.add_argument(
        "--trust-list-pem",
        type=Path,
        default=None,
        help=(
            "ADR-0047: PEM bundle of trusted root CA certificates. When "
            "provided AND the manifest JSON includes 'cert_chain_pem', AIP "
            "walks each X.509 chain in-process and overrides the operator-"
            "supplied 'chain_verified' boolean. Without this flag, AIP "
            "trusts the operator-supplied value."
        ),
    )
    c2pa_cmd.set_defaults(_cmd=c2pa_verify_command)

    # ── evidence c2pa-extract (ADR-0048) ───────────────────────────
    c2pa_ext = evidence_sub.add_parser(
        "c2pa-extract",
        parents=parents,
        help=(
            "ADR-0048: extract a C2PA manifest store directly from a "
            "JPEG/PNG/MP4/HEIC/AVIF/DNG/PDF file. Output is JSON in the "
            "AIP shape, ready for 'aip evidence c2pa-verify'. Requires "
            "the optional 'c2pa' dependency: pip install 'aip[c2pa]'."
        ),
    )
    c2pa_ext.add_argument(
        "media_file",
        type=Path,
        help="Path to the media file with the embedded C2PA manifest.",
    )
    c2pa_ext.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the JSON to this path instead of stdout.",
    )
    c2pa_ext.set_defaults(_cmd=c2pa_extract_command)


def c2pa_extract_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    """Extract C2PA manifest store from a media file (ADR-0048).

    Exit code:
      0 — extraction successful and manifest non-empty.
      1 — file has no C2PA manifest store (not an error, but no layer to
          surface in the report).
      2 — c2pa-python not installed, file not found, or parse failure.
    """
    from aip.c2pa.extractor import extract_from_media  # noqa: PLC0415

    media_path: Path = args.media_file
    if not media_path.is_file():
        raise AIPError(f"media file not found: {media_path}")

    try:
        aip_shape = extract_from_media(media_path)
    except AIPError as exc:
        # "no manifest" is exit 1; everything else is exit 2.
        # c2pa-python phrases this several ways depending on the file
        # format ("no JUMBF data found", "ManifestNotFound", "no C2PA
        # manifest store"); we widen the heuristic to catch all of them.
        msg = str(exc).lower()
        no_manifest = (
            "no c2pa manifest store" in msg
            or "no jumbf data" in msg
            or "manifestnotfound" in msg
        )
        if no_manifest:
            stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "action": "evidence_c2pa_extract",
                        "media_file": str(media_path),
                        "reason": "no C2PA manifest store in this file.",
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return 1
        raise

    payload = json.dumps(aip_shape, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        stdout.write(
            json.dumps(
                {
                    "ok": True,
                    "action": "evidence_c2pa_extract",
                    "media_file": str(media_path),
                    "out": str(args.out),
                    "manifest_count": len(aip_shape.get("manifests") or []),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    else:
        stdout.write(payload + "\n")
    return 0


def c2pa_verify_command(args: argparse.Namespace, *, stdout: IO[str]) -> int:
    """Verify a pre-extracted C2PA manifest JSON and write the attestation.

    Exit code: 0 if chain verifies AND binds to evidence; 1 if any
    structural / signature failure; 2 on input parse error.
    """
    # Lazy imports — keep the cold path of `aip evidence` light.
    from aip.c2pa import (  # noqa: PLC0415
        DEFAULT_TRUST_LIST_NAME,
        parse_manifest_json,
        persist_report,
        verify_manifest_chain,
    )

    manifest_path: Path = args.manifest_json
    if not manifest_path.is_file():
        raise AIPError(f"manifest JSON not found: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AIPError(f"manifest JSON is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise AIPError("manifest JSON must be an object at the top level.")

    try:
        manifests = parse_manifest_json(payload)
    except AIPError:
        raise
    except Exception as exc:
        raise AIPError(f"failed to parse manifest: {exc}") from exc

    # ADR-0047: load the operator-supplied trust list PEM if provided.
    trust_list_pem: str | None = None
    if getattr(args, "trust_list_pem", None) is not None:
        pem_path: Path = args.trust_list_pem
        if not pem_path.is_file():
            raise AIPError(f"trust list PEM not found: {pem_path}")
        try:
            trust_list_pem = pem_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AIPError(f"failed to read trust list PEM: {exc}") from exc

    report = verify_manifest_chain(
        manifests,
        evidence_sha256=args.evidence_sha256.lower(),
        trust_list_name=args.trust_list or DEFAULT_TRUST_LIST_NAME,
        trust_list_pem=trust_list_pem,
    )

    persisted_path: Path | None = None
    if not args.no_persist:
        archive_root = _resolve_archive_root(args)
        persisted_path = persist_report(archive_root, report)

    payload_out: dict[str, object] = {
        "ok": report.chain_verified,
        "action": "evidence_c2pa_verify",
        "evidence_sha256": report.evidence_sha256,
        "chain_verified": report.chain_verified,
        "failure_reason": report.failure_reason,
        "trust_list_name": report.trust_list_name,
        "verified_at": report.verified_at,
        "report_hash": report.report_hash,
        "manifest_count": len(report.manifests),
        "persisted_path": str(persisted_path) if persisted_path else None,
        # ADR-0047: who verified each manifest's signature, per manifest.
        "verification_modes": [
            {
                "label": m.label,
                "mode": m.signature_info.verification_mode,
                "chain_verified": m.signature_info.chain_verified,
            }
            for m in report.manifests
        ],
    }
    stdout.write(json.dumps(payload_out, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0 if report.chain_verified else 1


def _resolve_archive_root(args: argparse.Namespace) -> Path:
    root = getattr(args, "archive_root", None)
    if root is None:
        raise AIPError("--archive-root is required.")
    return Path(root)


# --------------------------------------------------------------------- helpers


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
