"""Subgrupo CLI ``aip capture`` (Phase 2).

Tres subcomandos:

- ``aip capture sign`` — hashea un fichero, firma con la clave del operador,
  emite un :class:`CaptureCertificate` JSON.
- ``aip capture verify`` — verifica un certificate offline, opcionalmente
  contra la clave pública y opcionalmente contra el fichero original.
- ``aip capture show`` — pretty-print de un certificate persistido.

Output: JSON canónico (``sort_keys=True``, ``indent=2``). Sin scoring,
sin interpretación.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.attestation.signer import load_private_key, load_public_key
from aip.capture import (
    decode_certificate,
    encode_certificate,
    hash_file,
    sign_capture,
    verify_capture,
)
from aip.errors import AIPError, UsageError

# --------------------------------------------------------------------- helpers


def _parse_iso_utc(value: str) -> str:
    """Valida y normaliza ISO-8601 UTC a ``YYYY-MM-DDTHH:MM:SSZ``."""
    try:
        if value.endswith("Z"):
            parsed = dt.datetime.fromisoformat(value[:-1]).replace(tzinfo=dt.UTC)
        else:
            parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise UsageError(
            f"invalid --captured-at {value!r}: {exc}. "
            "Expected ISO-8601 UTC, e.g. 2026-06-09T14:30:00Z."
        ) from exc
    if parsed.tzinfo is None:
        raise UsageError(f"--captured-at {value!r} must be timezone-aware (UTC).")
    return (
        parsed.astimezone(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _coerce_optional(value: str | None) -> str | None:
    """Normaliza string vacío a ``None``. Necesario porque argparse default es None
    pero un ``--device-id ""`` produciría empty string que el modelo rechaza."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


# --------------------------------------------------------------------- sign


def capture_sign_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    evidence_file: Path = args.evidence_file
    if not evidence_file.is_file():
        raise AIPError(f"evidence file not found: {evidence_file}")
    private_key_path: Path = args.private_key
    if not private_key_path.is_file():
        raise AIPError(f"private key not found: {private_key_path}")

    captured_at = _parse_iso_utc(args.captured_at)
    private_key = load_private_key(private_key_path)
    evidence_sha256 = hash_file(evidence_file)

    certificate = sign_capture(
        evidence_sha256=evidence_sha256,
        operator_id=args.operator_id,
        captured_at=captured_at,
        private_key=private_key,
        device_id=_coerce_optional(args.device_id),
        location=_coerce_optional(args.location),
        notes=_coerce_optional(args.notes),
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encode_certificate(certificate), encoding="utf-8")

    if args.quiet:
        return 0

    if args.json:
        payload = {
            "ok": True,
            "action": "capture_sign",
            "evidence_file": str(evidence_file),
            "evidence_sha256": certificate.evidence_sha256,
            "operator_id": certificate.operator_id,
            "captured_at": certificate.captured_at,
            "device_id": certificate.device_id,
            "location": certificate.location,
            "notes": certificate.notes,
            "public_key_fingerprint": certificate.public_key_fingerprint,
            "certificate_hash": certificate.certificate_hash,
            "output": str(args.output) if args.output is not None else None,
        }
        stdout.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        stdout.write(encode_certificate(certificate))
    return 0


# --------------------------------------------------------------------- verify


def capture_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    cert_path: Path = args.certificate_file
    if not cert_path.is_file():
        raise AIPError(f"certificate file not found: {cert_path}")
    certificate = decode_certificate(cert_path.read_text(encoding="utf-8"))

    public_key = None
    if args.public_key is not None:
        if not args.public_key.is_file():
            raise AIPError(f"public key not found: {args.public_key}")
        public_key = load_public_key(args.public_key)

    evidence_file: Path | None = args.evidence_file
    if evidence_file is not None and not evidence_file.is_file():
        raise AIPError(f"evidence file not found: {evidence_file}")

    ok = verify_capture(
        certificate,
        public_key=public_key,
        evidence_file=evidence_file,
    )

    # For UX, also report the recomputed evidence hash if user provided the file —
    # makes mismatches loud and inspectable.
    recomputed_evidence_hash = (
        hash_file(evidence_file) if evidence_file is not None else None
    )

    payload: dict[str, object] = {
        "ok": ok,
        "action": "capture_verify",
        "certificate_file": str(cert_path),
        "evidence_sha256": certificate.evidence_sha256,
        "operator_id": certificate.operator_id,
        "captured_at": certificate.captured_at,
        "device_id": certificate.device_id,
        "location": certificate.location,
        "notes": certificate.notes,
        "public_key_fingerprint": certificate.public_key_fingerprint,
        "certificate_hash": certificate.certificate_hash,
        "crypto_verified": public_key is not None and ok,
        "evidence_bytes_verified": evidence_file is not None and ok,
        "structural_only": public_key is None and evidence_file is None,
    }
    if recomputed_evidence_hash is not None:
        payload["recomputed_evidence_sha256"] = recomputed_evidence_hash
        payload["evidence_hash_match"] = (
            recomputed_evidence_hash == certificate.evidence_sha256
        )
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if ok else 1


# --------------------------------------------------------------------- show


def capture_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    cert_path: Path = args.certificate_file
    if not cert_path.is_file():
        raise AIPError(f"certificate file not found: {cert_path}")
    certificate = decode_certificate(cert_path.read_text(encoding="utf-8"))
    stdout.write(encode_certificate(certificate))
    return 0


# --------------------------------------------------------------------- subparser


def add_capture_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser],
) -> None:
    grp = subparsers.add_parser(
        "capture",
        help=(
            "Capture-at-Source (Phase 2). Sign the SHA-256 of an evidence file "
            "at the moment of acquisition with an operator ed25519 key. Extends "
            "the provenance chain backwards in time before ingest."
        ),
    )
    sub = grp.add_subparsers(dest="capture_action", required=True)

    # ── sign ──────────────────────────────────────────────────────────
    sign = sub.add_parser(
        "sign",
        parents=parents,
        help=(
            "Hash an evidence file, sign with the operator's ed25519 key, "
            "and emit a CaptureCertificate JSON."
        ),
    )
    sign.add_argument(
        "evidence_file",
        type=Path,
        help="Path to the evidence file to capture (will be hashed in streaming).",
    )
    sign.add_argument(
        "--private-key",
        required=True,
        type=Path,
        help="Path to the PEM PKCS#8 ed25519 private key.",
    )
    sign.add_argument(
        "--operator-id",
        required=True,
        help="Operator identifier (operator-supplied, no PKI in V1).",
    )
    sign.add_argument(
        "--captured-at",
        required=True,
        help=(
            "ISO-8601 UTC capture timestamp, e.g. 2026-06-09T14:30:00Z. "
            "Operator-supplied — no TSA in V1."
        ),
    )
    sign.add_argument(
        "--device-id",
        default=None,
        help="Optional device identifier (free-form, operator-supplied).",
    )
    sign.add_argument(
        "--location",
        default=None,
        help="Optional location string, free-form (e.g. 'MX-19.43,-99.13').",
    )
    sign.add_argument(
        "--notes",
        default=None,
        help="Optional capture context notes.",
    )
    sign.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the certificate JSON. Defaults to stdout.",
    )
    sign.set_defaults(_cmd=capture_sign_command)

    # ── verify ───────────────────────────────────────────────────────
    ver = sub.add_parser(
        "verify",
        parents=parents,
        help=(
            "Offline verify a capture certificate. Without --public-key and "
            "--evidence-file: structural only. With --public-key: ed25519 "
            "signature. With --evidence-file: also verifies the file's bytes "
            "match the certificate's claim. rc=0 if all checks pass, 1 if not."
        ),
    )
    ver.add_argument(
        "certificate_file",
        type=Path,
        help="Path to the CaptureCertificate JSON to verify.",
    )
    ver.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help=(
            "Optional PEM SubjectPublicKeyInfo ed25519 public key. When "
            "provided, the signature is cryptographically verified."
        ),
    )
    ver.add_argument(
        "--evidence-file",
        type=Path,
        default=None,
        help=(
            "Optional path to the evidence file. When provided, its actual "
            "SHA-256 is recomputed and compared to the certificate's claim."
        ),
    )
    ver.set_defaults(_cmd=capture_verify_command)

    # ── show ─────────────────────────────────────────────────────────
    show = sub.add_parser(
        "show",
        parents=parents,
        help="Pretty-print a persisted capture certificate.",
    )
    show.add_argument(
        "certificate_file",
        type=Path,
        help="Path to the CaptureCertificate JSON.",
    )
    show.set_defaults(_cmd=capture_show_command)


__all__ = [
    "add_capture_subparser",
    "capture_show_command",
    "capture_sign_command",
    "capture_verify_command",
]
