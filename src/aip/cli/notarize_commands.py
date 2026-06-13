"""Subgrupo CLI ``aip notarize`` — OpenTimestamps + Bitcoin anchor.

Cuatro subcomandos:

- ``aip notarize submit <file> [--out PATH]`` — calcula SHA-256, manda a
  calendarios OTS, escribe ``.ots`` con pending attestations.
- ``aip notarize upgrade <ots>`` — pide upgrade a calendarios para que el
  proof apunte a un bloque Bitcoin concreto (típicamente ~1h después de submit).
- ``aip notarize verify <file> <ots>`` — walk offline del proof, reporta
  bitcoin claims (height + expected merkle root) y pending claims.
- ``aip notarize show <ots>`` — pretty-print del proof tree para inspección.

Output: JSON canónico. Sin scoring, sin interpretación.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import IO, Any

from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    PendingAttestation,
)

from aip.errors import AIPError
from aip.notarize import (
    DEFAULT_CALENDARS,
    DEFAULT_SOURCES,
    build_detached,
    decode_dtf_from_bytes,
    encode_dtf_to_bytes,
    fetch_consensus,
    submit_to_calendars,
    upgrade_proof,
    verify_proof,
)


def _sha256_of_file(path: Path) -> bytes:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.digest()


def _default_ots_path(file_path: Path) -> Path:
    return file_path.with_suffix(file_path.suffix + ".ots")


# --------------------------------------------------------------------- submit


def notarize_submit_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    file_path: Path = args.file
    if not file_path.is_file():
        raise AIPError(f"file not found: {file_path}")

    leaf = _sha256_of_file(file_path)
    dtf = build_detached(leaf)
    result = submit_to_calendars(
        dtf,
        calendars=tuple(args.calendars) if args.calendars else DEFAULT_CALENDARS,
        timeout=args.timeout,
    )

    if not result.succeeded:
        # Total failure: no calendar accepted our submission. Don't write
        # an empty .ots file — that would lie about having a proof.
        raise AIPError(
            "submit failed: no calendar accepted the request. "
            f"Errors: {result.failed}"
        )

    out_path: Path = args.out if args.out is not None else _default_ots_path(file_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(encode_dtf_to_bytes(dtf))

    if args.quiet:
        return 0

    payload = {
        "ok": True,
        "action": "notarize_submit",
        "file": str(file_path),
        "leaf_sha256": leaf.hex(),
        "ots_file": str(out_path),
        "calendars_succeeded": result.succeeded,
        "calendars_failed": [
            {"url": u, "reason": r} for u, r in result.failed
        ],
        "note": (
            "Pending attestations only. Run 'aip notarize upgrade' ~1h after "
            "submit to anchor to a Bitcoin block."
        ),
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0


# --------------------------------------------------------------------- upgrade


def notarize_upgrade_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    ots_path: Path = args.ots_file
    if not ots_path.is_file():
        raise AIPError(f"ots file not found: {ots_path}")
    dtf = decode_dtf_from_bytes(ots_path.read_bytes())

    stats = upgrade_proof(dtf, timeout=args.timeout)
    ots_path.write_bytes(encode_dtf_to_bytes(dtf))

    if args.quiet:
        return 0

    payload = {
        "ok": True,
        "action": "notarize_upgrade",
        "ots_file": str(ots_path),
        "upgraded": stats["upgraded"],
        "still_pending": stats["still_pending"],
        "failed": stats["failed"],
        "note": (
            "If still_pending > 0, Bitcoin has not yet processed the batch. "
            "Try again later (~1h after the original submit)."
        ),
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0


# --------------------------------------------------------------------- verify


def notarize_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    file_path: Path = args.file
    ots_path: Path = args.ots_file
    if not file_path.is_file():
        raise AIPError(f"file not found: {file_path}")
    if not ots_path.is_file():
        raise AIPError(f"ots file not found: {ots_path}")

    expected = _sha256_of_file(file_path)
    dtf = decode_dtf_from_bytes(ots_path.read_bytes())
    result = verify_proof(dtf, expected_sha256=expected)

    payload: dict[str, object] = {
        "ok": result.ok,
        "action": "notarize_verify",
        "file": str(file_path),
        "ots_file": str(ots_path),
        "expected_sha256": expected.hex(),
        "proof_leaf_sha256": dtf.file_digest.hex(),
        "file_hash_matches": result.file_hash_matches,
        "bitcoin_claims": [
            {
                "height": c.height,
                "expected_merkle_root_le_hex": c.expected_merkle_root_le.hex(),
            }
            for c in result.bitcoin_claims
        ],
        "pending_claims": [
            {"calendar_uri": p.calendar_uri} for p in result.pending_claims
        ],
        "note": (
            "Bitcoin claims are unverified by this tool — compare each "
            "expected_merkle_root_le_hex against the merkle_root of the "
            "Bitcoin block at the claimed height (block explorer or "
            "bitcoin-cli getblockheader)."
        ),
    }
    if result.reason:
        payload["reason"] = result.reason
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if result.ok else 1


# --------------------------------------------------------------------- fetch-header


def notarize_fetch_header_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Fetch the 80-byte Bitcoin block header at HEIGHT from public explorers.

    Multi-source consensus by default; if --verify-against is provided, the
    extracted merkle root is cross-checked against the OTS proof's claim at
    the same height — refuses to emit a header that contradicts the proof.
    """
    height: int = args.height
    sources = tuple(args.source) if args.source else DEFAULT_SOURCES
    min_agreement = args.min_agreement
    result = fetch_consensus(
        height,
        sources=sources,
        timeout=args.timeout,
        min_agreement=min_agreement,
    )

    payload: dict[str, object] = {
        "ok": True,
        "action": "notarize_fetch_header",
        "height": height,
        "block_hash_hex": result.block_hash_hex,
        "header_hex": result.header_hex,
        "merkle_root_le_hex": result.merkle_root_le_hex,
        "sources_agreed": result.agreed,
        "sources_queried": [fh.source for fh in result.per_source],
        "sources_failed": [
            {"source": s, "reason": r} for s, r in result.errors
        ],
        "ready_to_paste": f"--bitcoin-header {height}:{result.header_hex}",
    }

    # Optional sanity check vs an OTS proof. The verification chain is:
    # OTS proof carries a Bitcoin claim (height, expected_merkle_root_le_hex).
    # The fetched header's merkle_root_le (bytes 36..68) must equal the claim.
    if args.verify_against is not None:
        ots_path: Path = args.verify_against
        if not ots_path.is_file():
            raise AIPError(f"--verify-against: ots file not found: {ots_path}")
        dtf = decode_dtf_from_bytes(ots_path.read_bytes())
        # We don't need the file hash here — only the Bitcoin claims walked
        # from the proof tree. Pass the dtf's own leaf as expected_sha256
        # so verify_proof doesn't reject on file mismatch grounds.
        vresult = verify_proof(dtf, expected_sha256=dtf.file_digest)
        matching = [
            c for c in vresult.bitcoin_claims if c.height == height
        ]
        if not matching:
            payload["verify_against"] = {
                "ots_file": str(ots_path),
                "match": False,
                "reason": (
                    f"OTS proof has no Bitcoin claim at height {height}. "
                    f"Available heights: "
                    f"{sorted({c.height for c in vresult.bitcoin_claims})}"
                ),
            }
            stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            )
            return 1
        # Every claim at that height must match (OTS proof can have
        # duplicate claims from multiple calendars batching into the same
        # block — all must agree on the merkle root).
        mismatches = [
            c for c in matching
            if c.expected_merkle_root_le.hex() != result.merkle_root_le_hex
        ]
        if mismatches:
            payload["verify_against"] = {
                "ots_file": str(ots_path),
                "match": False,
                "reason": (
                    f"Fetched header merkle_root {result.merkle_root_le_hex} "
                    f"does NOT match OTS claim at height {height} "
                    f"(expected {mismatches[0].expected_merkle_root_le.hex()}). "
                    "Either the explorer returned a tampered header, the OTS "
                    "proof is corrupt, or the height is wrong."
                ),
            }
            payload["ok"] = False
            stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            )
            return 1
        payload["verify_against"] = {
            "ots_file": str(ots_path),
            "match": True,
            "claims_matched": len(matching),
        }

    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0


# --------------------------------------------------------------------- show


def notarize_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    ots_path: Path = args.ots_file
    if not ots_path.is_file():
        raise AIPError(f"ots file not found: {ots_path}")
    dtf = decode_dtf_from_bytes(ots_path.read_bytes())

    bitcoin: list[dict[str, object]] = []
    pending: list[dict[str, str]] = []

    def walk(ts: Any, msg: bytes) -> None:
        for att in ts.attestations:
            if isinstance(att, BitcoinBlockHeaderAttestation):
                bitcoin.append({
                    "height": att.height,
                    "expected_merkle_root_le_hex": msg.hex(),
                })
            elif isinstance(att, PendingAttestation):
                pending.append({"calendar_uri": str(att.uri)})
        for op, child in ts.ops.items():
            walk(child, op(msg))

    walk(dtf.timestamp, dtf.timestamp.msg)

    payload = {
        "ok": True,
        "action": "notarize_show",
        "ots_file": str(ots_path),
        "leaf_sha256": dtf.file_digest.hex(),
        "bitcoin_attestations": bitcoin,
        "pending_attestations": pending,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0


# --------------------------------------------------------------------- subparser


def add_notarize_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "notarize",
        help=(
            "External notarization via OpenTimestamps. Anchors hashes to the "
            "Bitcoin blockchain so even the operator can't backdate. Submit + "
            "upgrade require network; verify is 100%% offline."
        ),
    )
    sub = grp.add_subparsers(dest="notarize_action", required=True)

    # submit
    sub_sub = sub.add_parser(
        "submit",
        parents=parents,
        help=(
            "Hash a file, submit its SHA-256 to public OTS calendars, write a "
            ".ots file with pending attestations. Anchoring to a Bitcoin block "
            "happens on the calendar side (~1h)."
        ),
    )
    sub_sub.add_argument(
        "file",
        type=Path,
        help="Path to the file to notarize (typically a manifest-NNNNNN.json).",
    )
    sub_sub.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the .ots proof. Default: <file>.ots.",
    )
    sub_sub.add_argument(
        "--calendars",
        nargs="*",
        default=None,
        help="Override the default OTS calendars (3 public). Provide >=1 URL.",
    )
    sub_sub.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout per calendar request (seconds).",
    )
    sub_sub.set_defaults(_cmd=notarize_submit_command)

    # upgrade
    up = sub.add_parser(
        "upgrade",
        parents=parents,
        help=(
            "Ask each pending calendar for an upgraded proof now that the "
            "batch should be in a Bitcoin block. Run ~1h after submit. "
            "Idempotent: safe to run repeatedly."
        ),
    )
    up.add_argument("ots_file", type=Path, help="Path to the .ots file.")
    up.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout per calendar request (seconds).",
    )
    up.set_defaults(_cmd=notarize_upgrade_command)

    # verify
    ver = sub.add_parser(
        "verify",
        parents=parents,
        help=(
            "Offline-verify a .ots proof against a file. Reports Bitcoin claims "
            "(height + expected merkle root, unverified) and pending claims. "
            "rc=0 if structure ok, 1 if file hash mismatch or no attestations."
        ),
    )
    ver.add_argument("file", type=Path, help="Path to the original notarized file.")
    ver.add_argument("ots_file", type=Path, help="Path to the .ots proof.")
    ver.set_defaults(_cmd=notarize_verify_command)

    # show
    show = sub.add_parser(
        "show",
        parents=parents,
        help="Pretty-print of a .ots proof tree (attestations only, no merkle ops).",
    )
    show.add_argument("ots_file", type=Path, help="Path to the .ots proof.")
    show.set_defaults(_cmd=notarize_show_command)

    # fetch-header
    fh = sub.add_parser(
        "fetch-header",
        parents=parents,
        help=(
            "Fetch the 80-byte Bitcoin block header at HEIGHT from public "
            "explorers (mempool.space + blockstream.info by default). "
            "Cross-checks the sources against each other and optionally "
            "against an OTS proof. Output is ready to paste into "
            "'aip evidence report --bitcoin-header'."
        ),
    )
    fh.add_argument(
        "height", type=int, help="Bitcoin block height to fetch."
    )
    fh.add_argument(
        "--source",
        action="append",
        default=None,
        help=(
            "Esplora-style explorer REST base (may repeat). Default: "
            "mempool.space + blockstream.info."
        ),
    )
    fh.add_argument(
        "--min-agreement",
        type=int,
        default=2,
        help=(
            "Minimum number of sources that must return the same header for "
            "the fetch to succeed. Default 2. Set to 1 to allow single-source."
        ),
    )
    fh.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout per source (seconds).",
    )
    fh.add_argument(
        "--verify-against",
        type=Path,
        default=None,
        help=(
            "Optional .ots proof to cross-check against. The fetched header's "
            "merkle_root must equal the OTS Bitcoin claim at the same height. "
            "If they disagree, the command exits 1 with match=false."
        ),
    )
    fh.set_defaults(_cmd=notarize_fetch_header_command)


__all__ = [
    "add_notarize_subparser",
    "notarize_fetch_header_command",
    "notarize_show_command",
    "notarize_submit_command",
    "notarize_upgrade_command",
    "notarize_verify_command",
]
