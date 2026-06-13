"""Subgrupo CLI ``aip transparency`` (Phase 1A).

Tres subcomandos:

- ``aip transparency publish`` — recolecta estado del archive, firma con la
  clave del operador, persiste como ``manifest-NNNNNN.json`` y actualiza
  ``latest.json``.
- ``aip transparency verify`` — verifica estructura + (opcional) firma de
  un manifest individual, o verifica la cadena completa con ``--chain``.
- ``aip transparency status`` — muestra estado del transparency log (último
  sequence, head hash, gaps detectados).

Output: JSON canónico (``sort_keys=True``, ``indent=2``). Sin scoring, sin
interpretación.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO, TYPE_CHECKING

from aip.attestation.signer import load_private_key, load_public_key
from aip.transparency.footprint_verifier import (
    DEFAULT_TIMEOUT_SECONDS as FOOTPRINT_DEFAULT_TIMEOUT,
)
from aip.transparency.footprint_verifier import (
    verify_declaration as verify_footprint_declaration,
)
from aip.transparency.key_declaration import (
    TargetSelector,
    WitnessSeed,
    add_external_reference,
    check_consistency,
    declaration_path,
    fingerprint_of_pem_file,
    init_declaration,
    load_declaration,
    save_declaration,
    witness_keys_dir,
)

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aip.errors import AIPError, UsageError
from aip.notarize import (
    build_detached,
    encode_dtf_to_bytes,
    submit_to_calendars,
)
from aip.transparency import (
    ZERO_HASH,
    collect_archive_state,
    detect_gaps,
    encode_manifest,
    list_sequences,
    load_chain,
    load_latest,
    load_manifest,
    persist_manifest,
    sign_manifest,
    verify_chain,
    verify_manifest,
)
from aip.transparency.exporter import export_bundle
from aip.transparency.store import decode_manifest
from aip.transparency.witness import (
    decode_witness,
    encode_witness,
    list_all_witnesses,
    list_witnesses_for_manifest,
    persist_witness,
    sign_witness,
    verify_witness,
)

# --------------------------------------------------------------------- helpers


def _parse_iso_utc(value: str) -> str:
    """Valida y normaliza un ISO-8601 UTC string a ``YYYY-MM-DDTHH:MM:SSZ``."""
    try:
        if value.endswith("Z"):
            parsed = dt.datetime.fromisoformat(value[:-1]).replace(tzinfo=dt.UTC)
        else:
            parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise UsageError(
            f"invalid --signed-at {value!r}: {exc}. "
            "Expected ISO-8601 UTC, e.g. 2026-06-09T14:30:00Z."
        ) from exc
    if parsed.tzinfo is None:
        raise UsageError(f"--signed-at {value!r} must be timezone-aware (UTC).")
    return (
        parsed.astimezone(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _now_utc_iso() -> str:
    return (
        dt.datetime.now(dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# --------------------------------------------------------------------- publish


def transparency_publish_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    archive_root: Path = args.archive_root
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")

    private_key_path: Path = args.private_key
    if not private_key_path.is_file():
        raise AIPError(f"private key not found: {private_key_path}")

    signed_at = (
        _parse_iso_utc(args.signed_at) if args.signed_at else _now_utc_iso()
    )

    # Compute next sequence from disk. If there's a chain, link to its head.
    existing = list_sequences(archive_root)
    if existing:
        previous = load_manifest(archive_root, existing[-1])
        sequence = previous.sequence + 1
        previous_manifest_hash = previous.manifest_hash
    else:
        sequence = 0
        previous_manifest_hash = ZERO_HASH

    state = collect_archive_state(archive_root)
    private_key = load_private_key(private_key_path)

    manifest = sign_manifest(
        sequence=sequence,
        signed_at=signed_at,
        operator_id=args.operator_id,
        private_key=private_key,
        archive_manifest_hash=state.archive_manifest_hash,
        audit_chain_head_hash=state.audit_chain_head_hash,
        audit_entry_count=state.audit_entry_count,
        evidence_count=state.evidence_count,
        attestation_count=state.attestation_count,
        workspace_count=state.workspace_count,
        timeline_count=state.timeline_count,
        snapshot_count=state.snapshot_count,
        justification_count=state.justification_count,
        previous_manifest_hash=previous_manifest_hash,
    )

    target = persist_manifest(manifest, archive_root=archive_root)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encode_manifest(manifest), encoding="utf-8")

    # Optional: external notarization via OpenTimestamps (Phase 4 integration).
    notarization_info: dict[str, object] | None = None
    if args.notarize:
        import hashlib  # noqa: PLC0415 — kept local to avoid hard import when unused

        manifest_bytes = target.read_bytes()
        leaf = hashlib.sha256(manifest_bytes).digest()
        dtf = build_detached(leaf)
        submit_result = submit_to_calendars(dtf)
        if not submit_result.succeeded:
            raise AIPError(
                "notarization submit failed: no calendar accepted. "
                f"Errors: {submit_result.failed}"
            )
        ots_path = target.with_suffix(target.suffix + ".ots")
        ots_path.write_bytes(encode_dtf_to_bytes(dtf))
        notarization_info = {
            "leaf_sha256": leaf.hex(),
            "ots_file": str(ots_path),
            "calendars_succeeded": submit_result.succeeded,
            "calendars_failed": [
                {"url": u, "reason": r} for u, r in submit_result.failed
            ],
            "note": (
                "Pending only. Run 'aip notarize upgrade <ots>' ~1h after "
                "to anchor to Bitcoin."
            ),
        }

    if args.quiet:
        return 0

    if args.json:
        payload = {
            "ok": True,
            "action": "transparency_publish",
            "sequence": manifest.sequence,
            "manifest_hash": manifest.manifest_hash,
            "previous_manifest_hash": manifest.previous_manifest_hash,
            "audit_chain_head_hash": manifest.audit_chain_head_hash,
            "audit_entry_count": manifest.audit_entry_count,
            "archive_manifest_hash": manifest.archive_manifest_hash,
            "signer": {
                "operator_id": manifest.operator_id,
                "public_key_fingerprint": manifest.public_key_fingerprint,
            },
            "signed_at": manifest.signed_at,
            "output": str(target),
            "notarization": notarization_info,
        }
        stdout.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        stdout.write(encode_manifest(manifest))
    return 0


# --------------------------------------------------------------------- verify


def _load_public_key_if_given(args: argparse.Namespace) -> Ed25519PublicKey | None:
    if args.public_key is None:
        return None
    if not args.public_key.is_file():
        raise AIPError(f"public key not found: {args.public_key}")
    return load_public_key(args.public_key)


def _verify_chain_mode(
    args: argparse.Namespace,
    public_key: Ed25519PublicKey | None,
    *,
    stdout: IO[str],
) -> int:
    archive_root: Path = args.archive_root
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")
    manifests = load_chain(archive_root)
    if not manifests:
        stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "action": "transparency_verify",
                    "mode": "chain",
                    "reason": "no manifests found",
                    "manifests_checked": 0,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 1

    ok, reason = verify_chain(manifests)
    if ok and public_key is not None:
        failures = [
            m.sequence
            for m in manifests
            if not verify_manifest(m, public_key=public_key)
        ]
        if failures:
            ok = False
            reason = f"crypto verification failed at sequence(s) {failures}"

    payload: dict[str, object] = {
        "ok": ok,
        "action": "transparency_verify",
        "mode": "chain",
        "manifests_checked": len(manifests),
        "first_sequence": manifests[0].sequence,
        "last_sequence": manifests[-1].sequence,
        "head_manifest_hash": manifests[-1].manifest_hash,
        "crypto_verified": public_key is not None and ok,
        "structural_only": public_key is None,
    }
    if not ok:
        payload["reason"] = reason
    stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if ok else 1


def _verify_single_mode(
    args: argparse.Namespace,
    public_key: Ed25519PublicKey | None,
    *,
    stdout: IO[str],
) -> int:
    manifest_file: Path = args.manifest_file
    if not manifest_file.is_file():
        raise AIPError(f"manifest file not found: {manifest_file}")
    manifest = decode_manifest(manifest_file.read_text(encoding="utf-8"))
    ok = verify_manifest(manifest, public_key=public_key)
    payload = {
        "ok": ok,
        "action": "transparency_verify",
        "mode": "single",
        "sequence": manifest.sequence,
        "manifest_hash": manifest.manifest_hash,
        "previous_manifest_hash": manifest.previous_manifest_hash,
        "audit_chain_head_hash": manifest.audit_chain_head_hash,
        "operator_id": manifest.operator_id,
        "public_key_fingerprint": manifest.public_key_fingerprint,
        "signed_at": manifest.signed_at,
        "crypto_verified": public_key is not None and ok,
        "structural_only": public_key is None,
    }
    stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if ok else 1


def transparency_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    if not args.chain and args.manifest_file is None:
        raise UsageError(
            "transparency verify requires either a manifest file path or --chain."
        )
    if args.chain and args.manifest_file is not None:
        raise UsageError(
            "transparency verify: --chain is exclusive with a positional manifest file."
        )
    public_key = _load_public_key_if_given(args)
    if args.chain:
        return _verify_chain_mode(args, public_key, stdout=stdout)
    return _verify_single_mode(args, public_key, stdout=stdout)


# --------------------------------------------------------------------- status


# --------------------------------------------------------------------- witness


def witness_sign_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    manifest_path: Path = args.manifest_file
    if not manifest_path.is_file():
        raise AIPError(f"manifest file not found: {manifest_path}")
    private_key_path: Path = args.private_key
    if not private_key_path.is_file():
        raise AIPError(f"private key not found: {private_key_path}")

    manifest = decode_manifest(manifest_path.read_text(encoding="utf-8"))
    private_key = load_private_key(private_key_path)
    witnessed_at = (
        _parse_iso_utc(args.witnessed_at) if args.witnessed_at else _now_utc_iso()
    )

    attestation = sign_witness(
        target_manifest=manifest,
        witness_operator_id=args.witness_operator_id,
        witnessed_at=witnessed_at,
        private_key=private_key,
        statement=args.statement,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encode_witness(attestation), encoding="utf-8")

    persisted_to: Path | None = None
    pubkey_persisted_to: Path | None = None
    if args.archive_root_for_witness is not None:
        persisted_to = persist_witness(
            attestation, archive_root=args.archive_root_for_witness
        )
        # Optionally copy the witness's public key into the keystore so
        # the target operator can verify ed25519 signatures (including the
        # standalone HTML report).
        if args.witness_pubkey is not None:
            if not args.witness_pubkey.is_file():
                raise AIPError(
                    f"witness public key not found: {args.witness_pubkey}"
                )
            keystore_dir = (
                args.archive_root_for_witness
                / "transparency"
                / "witness-keys"
            )
            keystore_dir.mkdir(parents=True, exist_ok=True)
            pubkey_persisted_to = (
                keystore_dir
                / f"{attestation.witness_public_key_fingerprint}.pem"
            )
            pubkey_persisted_to.write_bytes(args.witness_pubkey.read_bytes())

    if args.quiet:
        return 0

    if args.json:
        payload = {
            "ok": True,
            "action": "transparency_witness_sign",
            "attestation_hash": attestation.attestation_hash,
            "witness_operator_id": attestation.witness_operator_id,
            "witness_public_key_fingerprint": attestation.witness_public_key_fingerprint,
            "target_manifest_hash": attestation.target_manifest_hash,
            "target_manifest_sequence": attestation.target_manifest_sequence,
            "target_operator_id": attestation.target_operator_id,
            "witnessed_at": attestation.witnessed_at,
            "statement": attestation.statement,
            "output": str(args.output) if args.output is not None else None,
            "persisted_to": str(persisted_to) if persisted_to is not None else None,
            "pubkey_persisted_to": (
                str(pubkey_persisted_to) if pubkey_persisted_to is not None else None
            ),
        }
        stdout.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        stdout.write(encode_witness(attestation))
    return 0


def witness_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    att_path: Path = args.attestation_file
    if not att_path.is_file():
        raise AIPError(f"witness attestation file not found: {att_path}")
    attestation = decode_witness(att_path.read_text(encoding="utf-8"))

    public_key = None
    if args.public_key is not None:
        if not args.public_key.is_file():
            raise AIPError(f"public key not found: {args.public_key}")
        public_key = load_public_key(args.public_key)

    target_manifest = None
    if args.target_manifest is not None:
        if not args.target_manifest.is_file():
            raise AIPError(f"target manifest not found: {args.target_manifest}")
        target_manifest = decode_manifest(
            args.target_manifest.read_text(encoding="utf-8")
        )

    ok = verify_witness(
        attestation,
        public_key=public_key,
        target_manifest=target_manifest,
    )

    payload: dict[str, object] = {
        "ok": ok,
        "action": "transparency_witness_verify",
        "attestation_file": str(att_path),
        "attestation_hash": attestation.attestation_hash,
        "witness_operator_id": attestation.witness_operator_id,
        "witness_public_key_fingerprint": attestation.witness_public_key_fingerprint,
        "target_manifest_hash": attestation.target_manifest_hash,
        "target_manifest_sequence": attestation.target_manifest_sequence,
        "target_operator_id": attestation.target_operator_id,
        "witnessed_at": attestation.witnessed_at,
        "crypto_verified": public_key is not None and ok,
        "target_matched": target_manifest is not None and ok,
        "structural_only": public_key is None and target_manifest is None,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if ok else 1


def witness_list_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    archive_root: Path = args.archive_root
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")

    if args.sequence is not None:
        ws = list_witnesses_for_manifest(archive_root, args.sequence)
        summaries = {args.sequence: ws}
    else:
        summaries = list_all_witnesses(archive_root)

    payload = {
        "ok": True,
        "action": "transparency_witness_list",
        "archive_root": str(archive_root),
        "witnesses_by_manifest": {
            str(seq): [
                {
                    "attestation_hash": a.attestation_hash,
                    "witness_operator_id": a.witness_operator_id,
                    "witness_public_key_fingerprint": a.witness_public_key_fingerprint,
                    "witnessed_at": a.witnessed_at,
                    "statement": a.statement,
                }
                for a in ws
            ]
            for seq, ws in summaries.items()
        },
        "total_manifests_with_witnesses": len(summaries),
        "total_witnesses": sum(len(ws) for ws in summaries.values()),
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0


# --------------------------------------------------------------------- export


def transparency_export_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    archive_root: Path = args.archive_root
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")
    out_dir: Path = args.out
    summary = export_bundle(
        archive_root,
        out_dir,
        exported_at=dt.datetime.now(dt.UTC),
    )
    if not args.quiet:
        stdout.write(
            json.dumps(
                {"action": "transparency_export", **summary},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return 0


def transparency_status_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    archive_root: Path = args.archive_root
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")

    sequences = list_sequences(archive_root)
    latest = load_latest(archive_root)
    gaps = detect_gaps(sequences)

    payload: dict[str, object] = {
        "ok": len(gaps) == 0,
        "action": "transparency_status",
        "archive_root": str(archive_root),
        "manifest_count": len(sequences),
        "gaps": gaps,
    }
    if latest is not None:
        payload["head"] = {
            "sequence": latest.sequence,
            "manifest_hash": latest.manifest_hash,
            "audit_chain_head_hash": latest.audit_chain_head_hash,
            "audit_entry_count": latest.audit_entry_count,
            "signed_at": latest.signed_at,
            "operator_id": latest.operator_id,
        }
    else:
        payload["head"] = None
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0 if not gaps else 1


# --------------------------------------------------------------------- subparser


# ─────────────────────────────────────────────────────────────────────
# declare-key subcommands (ADR-0043)
# ─────────────────────────────────────────────────────────────────────


def _resolve_archive_root(args: argparse.Namespace) -> Path:
    root = getattr(args, "archive_root", None)
    if root is None:
        raise UsageError("--archive-root is required.")
    return Path(root)


def declare_key_init_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Create a fresh ``key-declaration.json`` seeded from on-disk pubkeys.

    Refuses to overwrite an existing declaration unless ``--force`` is set.
    Witness entries are auto-seeded for every PEM under
    ``transparency/witness-keys/``; the operator can later attach external
    references to each.
    """
    archive_root = _resolve_archive_root(args)
    target = declaration_path(archive_root)
    if target.exists() and not args.force:
        raise AIPError(
            f"declaration already exists at {target}. Pass --force to overwrite."
        )

    # Auto-seed witnesses from on-disk PEMs unless explicitly suppressed.
    seeds: list[WitnessSeed] = []
    if not args.no_seed_witnesses:
        wdir = witness_keys_dir(archive_root)
        if wdir.is_dir():
            for p in sorted(wdir.iterdir(), key=lambda x: x.name):
                if not p.is_file() or p.suffix != ".pem":
                    continue
                try:
                    fp = fingerprint_of_pem_file(p)
                except (ValueError, OSError) as exc:
                    raise AIPError(
                        f"witness key {p.name} could not be loaded: {exc}"
                    ) from exc
                # Default witness_operator_id to the fingerprint stem until
                # the operator renames it via --witness-id at add-reference time.
                seeds.append(
                    WitnessSeed(witness_operator_id=fp[:16], public_key_fingerprint=fp)
                )

    data = init_declaration(
        archive_root,
        operator_id=args.operator_id,
        first_published_at=args.first_published_at,
        witnesses=tuple(seeds),
    )
    save_declaration(archive_root, data)

    if args.quiet:
        return 0
    payload = {
        "ok": True,
        "action": "declare_key_init",
        "path": str(target),
        "operator_id": args.operator_id,
        "operator_fingerprint": data["operator"]["public_key_fingerprint"],
        "witnesses_seeded": len(seeds),
        "note": (
            "Add external references with 'aip transparency declare-key "
            "add-reference --kind <K> --uri <U>'. The declaration is "
            "operator-supplied; AIP does not verify the references."
        ),
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


def declare_key_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Print the current declaration and a consistency report.

    Exits 0 if the declaration is consistent with the archive's on-disk
    keys, 1 otherwise. ``--json`` (global) emits the full report;
    otherwise still emits JSON since that is the CLI convention.
    """
    archive_root = _resolve_archive_root(args)
    decl = load_declaration(archive_root)
    consistency = check_consistency(archive_root)

    payload: dict[str, object] = {
        "ok": consistency.ok,
        "action": "declare_key_show",
        "declaration": decl,
        "consistency": {
            "declaration_present": consistency.declaration_present,
            "operator_fingerprint_declared": consistency.operator_fingerprint_declared,
            "operator_fingerprint_actual": consistency.operator_fingerprint_actual,
            "operator_matches": consistency.operator_matches,
            "witnesses_declared": consistency.witnesses_declared,
            "witnesses_in_archive": consistency.witnesses_in_archive,
            "declared_witnesses_without_pem": consistency.declared_witnesses_without_pem,
            "extra_witness_pems_not_declared": consistency.extra_witness_pems_not_declared,
        },
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0 if consistency.ok else 1


def declare_key_add_reference_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Append an external reference to the operator block or a witness.

    Default target is the operator; pass ``--witness-fingerprint`` or
    ``--witness-id`` to target a specific witness. The two flags are
    mutually exclusive.
    """
    archive_root = _resolve_archive_root(args)
    decl = load_declaration(archive_root)
    if decl is None:
        raise AIPError(
            "no declaration in this archive. Run 'aip transparency declare-key "
            "init --operator-id <ID>' first."
        )

    if args.witness_fingerprint is not None and args.witness_id is not None:
        raise UsageError(
            "--witness-fingerprint and --witness-id are mutually exclusive."
        )

    target = TargetSelector(
        witness_fingerprint=args.witness_fingerprint,
        witness_operator_id=args.witness_id,
    )
    decl = add_external_reference(
        decl,
        kind=args.kind,
        uri=args.uri,
        note=args.note,
        target=target,
    )
    save_declaration(archive_root, decl)

    if args.quiet:
        return 0
    payload = {
        "ok": True,
        "action": "declare_key_add_reference",
        "added": {
            "kind": args.kind,
            "uri": args.uri,
            "note": args.note,
            "target": (
                "operator"
                if target.is_operator()
                else (
                    f"witness:fingerprint:{args.witness_fingerprint}"
                    if args.witness_fingerprint
                    else f"witness:id:{args.witness_id}"
                )
            ),
        },
    }
    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


def declare_key_verify_footprint_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Cross-verify the operator's external references (ADR-0045).

    Fetches each supported reference, parses the public key from the
    channel's native format, computes its fingerprint, and compares with
    the declared one. Reports per-reference verdict.

    Exit code:

    - ``0`` if every supported + reachable reference verifies.
    - ``1`` if any reachable reference reports a mismatch (potential
      tampering or stale declaration).
    - ``2`` if every supported reference is unreachable (network /
      misconfiguration; not a verdict).
    """
    archive_root = _resolve_archive_root(args)
    decl = load_declaration(archive_root)
    if decl is None:
        raise AIPError(
            "no declaration in this archive. Run 'aip transparency declare-key "
            "init --operator-id <ID>' first."
        )

    report = verify_footprint_declaration(decl, timeout=args.timeout)

    references_payload = [
        {
            "kind": r.kind,
            "uri": r.uri,
            "status": r.status,
            "fetched_fingerprint": r.fetched_fingerprint,
            "declared_fingerprint": r.declared_fingerprint,
            "reason": r.reason,
        }
        for r in report.references
    ]

    payload: dict[str, object] = {
        "action": "declare_key_verify_footprint",
        "operator_id": report.operator_id,
        "declared_fingerprint": report.declared_fingerprint,
        "references": references_payload,
        "summary": {
            "total": len(report.references),
            "verified": report.verified_count,
            "mismatch": report.mismatch_count,
            "reachable": report.reachable_count,
            "supported": report.supported_count,
        },
    }

    if report.mismatch_count > 0:
        payload["ok"] = False
        exit_code = 1
    elif report.supported_count > 0 and report.reachable_count == 0:
        payload["ok"] = False
        exit_code = 2
    else:
        payload["ok"] = True
        exit_code = 0

    stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return exit_code


# ─────────────────────────────────────────────────────────────────────


def add_transparency_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "transparency",
        help=(
            "Transparency log (Phase 1A). Publish signed manifests of the "
            "archive state to a public append-only chain so any third party "
            "can verify integrity offline without trusting the operator."
        ),
    )
    sub = grp.add_subparsers(dest="transparency_action", required=True)

    # ── publish ──────────────────────────────────────────────────────
    pub = sub.add_parser(
        "publish",
        parents=parents,
        help=(
            "Collect current archive state, sign with operator's ed25519 "
            "key, persist under <archive>/transparency/ and update latest.json."
        ),
    )
    pub.add_argument(
        "--private-key",
        required=True,
        type=Path,
        help="Path to the PEM PKCS#8 ed25519 private key.",
    )
    pub.add_argument(
        "--operator-id",
        required=True,
        help="Operator identifier (e.g. 'jmm-evergreen').",
    )
    pub.add_argument(
        "--signed-at",
        default=None,
        help=(
            "Optional ISO-8601 UTC timestamp. Defaults to 'now' (UTC, "
            "second precision). Operator-supplied — no TSA in V1."
        ),
    )
    pub.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional extra output path for the manifest JSON.",
    )
    pub.add_argument(
        "--notarize",
        action="store_true",
        help=(
            "Submit the manifest's SHA-256 to public OpenTimestamps calendars "
            "right after publishing. Writes a .ots sidecar next to the manifest. "
            "Bitcoin anchoring is finalized ~1h later via 'aip notarize upgrade'."
        ),
    )
    pub.set_defaults(_cmd=transparency_publish_command)

    # ── verify ───────────────────────────────────────────────────────
    ver = sub.add_parser(
        "verify",
        parents=parents,
        help=(
            "Offline verification. Single manifest mode: pass a file path. "
            "Chain mode: pass --chain to verify the entire chain in the "
            "archive. With --public-key, cryptographic signature is verified."
        ),
    )
    ver.add_argument(
        "manifest_file",
        nargs="?",
        type=Path,
        default=None,
        help="Path to a manifest JSON file (single-manifest mode).",
    )
    ver.add_argument(
        "--chain",
        action="store_true",
        help=(
            "Verify the full chain under <archive>/transparency/ instead of "
            "a single file. Uses --archive-root."
        ),
    )
    ver.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help=(
            "Optional PEM SubjectPublicKeyInfo ed25519 public key. When "
            "provided, signatures are cryptographically verified."
        ),
    )
    ver.set_defaults(_cmd=transparency_verify_command)

    # ── status ───────────────────────────────────────────────────────
    sta = sub.add_parser(
        "status",
        parents=parents,
        help=(
            "Show transparency log status: manifest count, head, detected gaps. "
            "rc=0 if no gaps, 1 if any gap detected."
        ),
    )
    sta.set_defaults(_cmd=transparency_status_command)

    # ── export ───────────────────────────────────────────────────────
    exp = sub.add_parser(
        "export",
        parents=parents,
        help=(
            "Export the transparency log as a portable static bundle. "
            "The bundle can be served by any static host (GitHub Pages, S3, "
            "local http server) and verified by the portal without the "
            "operator's backend running."
        ),
    )
    exp.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory for the bundle. Created if missing.",
    )
    exp.set_defaults(_cmd=transparency_export_command)

    # ── witness (Door #3, cross-operator multi-sig) ──────────────────
    wit = sub.add_parser(
        "witness",
        help=(
            "Cross-operator multi-signature witness attestations. Allows "
            "operators DIFFERENT from the manifest publisher to co-sign "
            "transparency manifests they have seen. Accumulating witnesses "
            "raises the cost of forging the chain."
        ),
    )
    wit_sub = wit.add_subparsers(dest="witness_action", required=True)

    # witness sign
    ws = wit_sub.add_parser(
        "sign",
        parents=parents,
        help=(
            "Sign a witness attestation over an existing TransparencyManifest "
            "with the witness's ed25519 key. By default emits JSON to stdout; "
            "with --output writes to a file; with --archive-root-for-witness "
            "persists as a sidecar under <archive>/transparency/witnesses/."
        ),
    )
    ws.add_argument(
        "manifest_file",
        type=Path,
        help="Path to the TransparencyManifest JSON to witness.",
    )
    ws.add_argument(
        "--private-key",
        required=True,
        type=Path,
        help="Path to the witness's ed25519 PEM PKCS#8 private key.",
    )
    ws.add_argument(
        "--witness-operator-id",
        required=True,
        help="Identifier of the witness operator (operator-supplied, no PKI).",
    )
    ws.add_argument(
        "--witnessed-at",
        default=None,
        help="Optional ISO-8601 UTC timestamp. Defaults to now (UTC, second precision).",
    )
    ws.add_argument(
        "--statement",
        default=None,
        help=(
            "Optional free-form statement (e.g. 'saw this state on "
            "github.com/op/log@<commit>'). Operator-supplied."
        ),
    )
    ws.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output file path for the witness attestation JSON.",
    )
    ws.add_argument(
        "--archive-root-for-witness",
        type=Path,
        default=None,
        help=(
            "Optional path to an archive to persist the witness under "
            "<archive>/transparency/witnesses/manifest-NNNNNN/. Typically only "
            "used when the witness IS the manifest owner (rare) or for testing."
        ),
    )
    ws.add_argument(
        "--witness-pubkey",
        type=Path,
        default=None,
        help=(
            "Optional path to the witness's PEM SPKI public key. When provided "
            "together with --archive-root-for-witness, the key is copied to "
            "<archive>/transparency/witness-keys/<fingerprint>.pem so the "
            "standalone HTML report can verify the ed25519 signature client-side."
        ),
    )
    ws.set_defaults(_cmd=witness_sign_command)

    # witness verify
    wv = wit_sub.add_parser(
        "verify",
        parents=parents,
        help=(
            "Verify a witness attestation offline. Without --public-key and "
            "--target-manifest: structural only. With --public-key: ed25519 "
            "signature verification. With --target-manifest: also verifies that "
            "the attestation's target_* fields match the provided manifest."
        ),
    )
    wv.add_argument(
        "attestation_file",
        type=Path,
        help="Path to the WitnessAttestation JSON to verify.",
    )
    wv.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help="Optional PEM SubjectPublicKeyInfo ed25519 public key of the WITNESS.",
    )
    wv.add_argument(
        "--target-manifest",
        type=Path,
        default=None,
        help=(
            "Optional path to the TransparencyManifest the attestation claims "
            "to witness. When provided, target_manifest_hash + sequence + "
            "operator_id must match exactly."
        ),
    )
    wv.set_defaults(_cmd=witness_verify_command)

    # witness list
    wl = wit_sub.add_parser(
        "list",
        parents=parents,
        help=(
            "List witness attestations persisted in an archive. Without "
            "--sequence: list all manifests with witnesses. With --sequence: "
            "list witnesses of that specific manifest."
        ),
    )
    wl.add_argument(
        "--sequence",
        type=int,
        default=None,
        help="Optional manifest sequence to filter by.",
    )
    wl.set_defaults(_cmd=witness_list_command)

    # ── declare-key (ADR-0043) ──────────────────────────────────────
    dk = sub.add_parser(
        "declare-key",
        help=(
            "Manage the operator's key declaration (ADR-0043): a list of "
            "external publications of each public key so receptors can "
            "cross-check identity instead of trusting embedded keys blindly."
        ),
    )
    dk_sub = dk.add_subparsers(dest="declare_key_action", required=True)

    dk_init = dk_sub.add_parser(
        "init",
        parents=parents,
        help=(
            "Create a fresh key-declaration.json from the operator pubkey "
            "and (by default) seed an entry per witness key found in "
            "transparency/witness-keys/."
        ),
    )
    dk_init.add_argument(
        "--operator-id",
        required=True,
        help="Operator identifier (e.g. 'jmm-evergreen').",
    )
    dk_init.add_argument(
        "--first-published-at",
        default=None,
        help="Optional ISO-8601 UTC timestamp of first external publication.",
    )
    dk_init.add_argument(
        "--no-seed-witnesses",
        action="store_true",
        help=(
            "Skip auto-seeding witnesses from transparency/witness-keys/. "
            "Useful if witness keys are added later."
        ),
    )
    dk_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing key-declaration.json.",
    )
    dk_init.set_defaults(_cmd=declare_key_init_command)

    dk_show = dk_sub.add_parser(
        "show",
        parents=parents,
        help=(
            "Print the current declaration + consistency report against "
            "on-disk pubkeys. rc=0 if consistent, 1 otherwise."
        ),
    )
    dk_show.set_defaults(_cmd=declare_key_show_command)

    dk_add = dk_sub.add_parser(
        "add-reference",
        parents=parents,
        help=(
            "Append an external reference (e.g. github_user_keys, "
            "https_pem, dns_txt) to the operator or a witness."
        ),
    )
    dk_add.add_argument(
        "--kind",
        required=True,
        help=(
            "Reference kind. Common: github_user_keys, https_pem, dns_txt, "
            "git_signing_key, verbal_in_person. Custom kinds pass through."
        ),
    )
    dk_add.add_argument(
        "--uri",
        required=True,
        help="URI/locator for the reference (URL, DNS name, etc.).",
    )
    dk_add.add_argument(
        "--note",
        default=None,
        help="Optional human-readable note (e.g. verification instructions).",
    )
    dk_add.add_argument(
        "--witness-fingerprint",
        default=None,
        help="Target a witness by SHA-256 hex fingerprint instead of operator.",
    )
    dk_add.add_argument(
        "--witness-id",
        default=None,
        help="Target a witness by witness_operator_id instead of operator.",
    )
    dk_add.set_defaults(_cmd=declare_key_add_reference_command)

    dk_vfp = dk_sub.add_parser(
        "verify-footprint",
        parents=parents,
        help=(
            "Cross-verify the operator's external references (ADR-0045): "
            "fetch each supported reference, compute its fingerprint and "
            "compare with the declared one. AIP does NOT replace your own "
            "manual cross-check — it surfaces the same result faster. "
            "rc=0 if all reachable references verify, 1 on any mismatch, "
            "2 if all supported references are unreachable."
        ),
    )
    dk_vfp.add_argument(
        "--timeout",
        type=int,
        default=FOOTPRINT_DEFAULT_TIMEOUT,
        help=f"HTTPS timeout per reference (seconds). Default: {FOOTPRINT_DEFAULT_TIMEOUT}.",
    )
    dk_vfp.set_defaults(_cmd=declare_key_verify_footprint_command)


__all__ = [
    "add_transparency_subparser",
    "declare_key_add_reference_command",
    "declare_key_init_command",
    "declare_key_show_command",
    "declare_key_verify_footprint_command",
    "transparency_export_command",
    "transparency_publish_command",
    "transparency_status_command",
    "transparency_verify_command",
    "witness_list_command",
    "witness_sign_command",
    "witness_verify_command",
]
