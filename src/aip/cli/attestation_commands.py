"""Subgrupo CLI ``aip attestation`` (ADR-0041 §CLI).

Cuatro subcomandos:

- ``aip attestation keygen`` — genera un par ed25519 (PEM PKCS#8 + SPKI).
- ``aip attestation sign``   — firma un artefacto y persiste la atestación.
- ``aip attestation verify`` — verifica una atestación offline (con o sin
  clave pública).
- ``aip attestation show``   — lee una atestación persistida en el archive.

JSON canónico (``sort_keys=True``). Sin scoring, sin interpretación.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import IO

from aip.attestation import (
    decode_attestation,
    encode_attestation,
    generate_keypair,
    load_attestation,
    load_private_key,
    load_public_key,
    persist_attestation,
    serialize_private_key_pem,
    serialize_public_key_pem,
    sign_artifact,
    verify_attestation,
)
from aip.attestation.models import ALLOWED_ARTIFACT_KINDS
from aip.errors import AIPError, UsageError

# --------------------------------------------------------------------- detect


_KIND_SIGNATURES: tuple[tuple[str, frozenset[str]], ...] = (
    ("workspace", frozenset({"workspace_id", "workspace_hash", "references"})),
    ("timeline", frozenset({"timeline_id", "timeline_hash", "ordered_events"})),
    ("snapshot", frozenset({"snapshot_id", "snapshot_hash", "referenced_artifacts"})),
    (
        "justification",
        frozenset(
            {"justification_id", "justification_hash", "conclusion_anchor_type"}
        ),
    ),
    (
        "context_bundle",
        frozenset(
            {"context_bundle_hash", "assembly_method_name", "graph_neighborhood"}
        ),
    ),
    (
        "manifest",
        frozenset({"tables", "blobs_root", "schema_version", "generated_at"}),
    ),
)
"""Firma estructural (subconjunto de claves obligatorias) por
``artifact_kind``. Cubre los seis kinds firmables de ADR-0041."""


def _detect_artifact_kind_from_json(
    data: dict[str, object],
) -> str | None:
    """Detecta ``artifact_kind`` inspeccionando claves estructurales.

    Devuelve ``None`` si la forma no coincide con ningún kind conocido.
    """
    keys = data.keys()
    for kind, required in _KIND_SIGNATURES:
        if required <= keys:
            return kind
    return None


def _resolve_artifact_kind(
    artifact_path: Path, override: str | None
) -> str:
    """Resuelve ``artifact_kind`` con override explícito o auto-detección."""
    if override is not None:
        if override not in ALLOWED_ARTIFACT_KINDS:
            raise UsageError(
                f"invalid --artifact-kind {override!r}; "
                f"must be one of {sorted(ALLOWED_ARTIFACT_KINDS)}."
            )
        return override
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AIPError(
            f"artifact file not valid JSON: {artifact_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise AIPError(
            f"artifact file root must be a JSON object: {artifact_path}"
        )
    detected = _detect_artifact_kind_from_json(data)
    if detected is None:
        raise AIPError(
            "could not auto-detect artifact_kind; pass --artifact-kind. "
            f"Allowed: {sorted(ALLOWED_ARTIFACT_KINDS)}."
        )
    return detected


# --------------------------------------------------------------------- keygen


def attestation_keygen_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Genera un par ed25519 y lo persiste en PEM."""
    private, public = generate_keypair()
    out_priv: Path = args.output_private
    out_pub: Path = args.output_public
    out_priv.parent.mkdir(parents=True, exist_ok=True)
    out_pub.parent.mkdir(parents=True, exist_ok=True)
    out_priv.write_bytes(serialize_private_key_pem(private))
    out_pub.write_bytes(serialize_public_key_pem(public))
    payload = {
        "ok": True,
        "action": "attestation_keygen",
        "output_private": str(out_priv),
        "output_public": str(out_pub),
        "signature_algorithm": "ed25519-v1",
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0


# --------------------------------------------------------------------- sign


def _parse_signed_at(value: str) -> dt.datetime:
    """Parsea ISO-8601 UTC con ``Z`` suffix."""
    try:
        if value.endswith("Z"):
            naive = value[:-1]
            parsed = dt.datetime.fromisoformat(naive).replace(tzinfo=dt.UTC)
        else:
            parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise UsageError(
            f"invalid --signed-at {value!r}: {exc}. "
            "Expected ISO-8601 UTC, e.g. 2026-06-07T12:00:00Z."
        ) from exc
    if parsed.tzinfo is None:
        raise UsageError(
            f"--signed-at {value!r} must be timezone-aware (UTC)."
        )
    return parsed


def attestation_sign_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Firma un artefacto y persiste la atestación."""
    artifact_path: Path = args.artifact_file
    if not artifact_path.is_file():
        raise AIPError(f"artifact file not found: {artifact_path}")
    private_key_path: Path = args.private_key
    if not private_key_path.is_file():
        raise AIPError(f"private key not found: {private_key_path}")

    artifact_kind = _resolve_artifact_kind(
        artifact_path, args.artifact_kind
    )
    private_key = load_private_key(private_key_path)
    signed_at = _parse_signed_at(args.signed_at)

    attestation = sign_artifact(
        artifact_kind=artifact_kind,
        artifact_path=artifact_path,
        private_key=private_key,
        signer_id=args.signer_id,
        signed_at=signed_at,
    )

    extra_output: Path | None = args.output
    if args.archive is not None:
        if args.attestation_id is None:
            raise UsageError(
                "--archive requires --attestation-id."
            )
        persist_attestation(
            attestation,
            archive_root=args.archive,
            attestation_id=args.attestation_id,
            actor=args.signer_id,
            clock=lambda: dt.datetime.now(dt.UTC),
            extra_output=extra_output,
        )
    elif extra_output is not None:
        extra_output.parent.mkdir(parents=True, exist_ok=True)
        extra_output.write_text(
            encode_attestation(attestation), encoding="utf-8"
        )
    elif args.attestation_id is not None:
        raise UsageError(
            "--attestation-id requires --archive (persistence target)."
        )

    stdout.write(encode_attestation(attestation))
    return 0


# --------------------------------------------------------------------- verify


def attestation_verify_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Verifica una atestación offline. rc=0 si válida, 1 si no."""
    path: Path = args.attestation_file
    if not path.is_file():
        raise AIPError(f"attestation file not found: {path}")
    attestation = decode_attestation(path.read_text(encoding="utf-8"))

    public_key = None
    if args.public_key is not None:
        if not args.public_key.is_file():
            raise AIPError(
                f"public key not found: {args.public_key}"
            )
        public_key = load_public_key(args.public_key)

    ok = verify_attestation(attestation, public_key=public_key)
    payload: dict[str, object] = {
        "ok": ok,
        "action": "attestation_verify",
        "attestation_file": str(path),
        "artifact_kind": attestation.artifact_kind,
        "artifact_hash": attestation.artifact_hash,
        "signer_id": attestation.signer_id,
        "public_key_fingerprint": attestation.public_key_fingerprint,
        "signed_at": attestation.signed_at,
        "attestation_hash": attestation.attestation_hash,
        "crypto_verified": public_key is not None and ok,
        "structural_only": public_key is None,
    }
    stdout.write(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    return 0 if ok else 1


# --------------------------------------------------------------------- show


def attestation_show_command(
    args: argparse.Namespace, *, stdout: IO[str]
) -> int:
    """Lee una atestación persistida en ``<archive>/attestations/``."""
    attestation = load_attestation(
        archive_root=args.archive,
        attestation_id=args.attestation_id,
    )
    stdout.write(encode_attestation(attestation))
    return 0


# --------------------------------------------------------------------- subparser


def add_attestation_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Añade el grupo ``attestation`` al dispatcher principal."""
    grp = subparsers.add_parser(
        "attestation",
        help=(
            "Operator Attestation (ADR-0041). Cryptographically bind an "
            "artifact to an ed25519 keypair controlled by an operator. "
            "Offline-verifiable. No PKI, no TSA, no interpretation."
        ),
    )
    sub = grp.add_subparsers(dest="attestation_action", required=True)

    keygen = sub.add_parser(
        "keygen",
        help=(
            "Generate an ed25519 keypair (PEM PKCS#8 private + "
            "SubjectPublicKeyInfo public). Convenience helper — equivalent "
            "to openssl ed25519 keygen."
        ),
    )
    keygen.add_argument(
        "--output-private",
        required=True,
        type=Path,
        help="Output path for the PEM PKCS#8 private key (no passphrase).",
    )
    keygen.add_argument(
        "--output-public",
        required=True,
        type=Path,
        help="Output path for the PEM SubjectPublicKeyInfo public key.",
    )
    keygen.set_defaults(_cmd=attestation_keygen_command)

    sign = sub.add_parser(
        "sign",
        help=(
            "Sign an artifact. Extracts its self-hash, builds a JCS "
            "canonical payload, and produces an OperatorAttestation JSON. "
            "Optional persistence under <archive>/attestations/."
        ),
    )
    sign.add_argument(
        "artifact_file",
        type=Path,
        help="Path to the artifact JSON to sign.",
    )
    sign.add_argument(
        "--private-key",
        required=True,
        type=Path,
        help="Path to the PEM PKCS#8 ed25519 private key.",
    )
    sign.add_argument(
        "--signer-id",
        required=True,
        help=(
            "Operator-supplied signer identifier (e.g. '@operator'). "
            "Not authenticated by itself — PKI is out of scope V1."
        ),
    )
    sign.add_argument(
        "--signed-at",
        required=True,
        help=(
            "ISO-8601 UTC timestamp, e.g. 2026-06-07T12:00:00Z. "
            "Operator-supplied — no TSA in V1."
        ),
    )
    sign.add_argument(
        "--artifact-kind",
        default=None,
        choices=sorted(ALLOWED_ARTIFACT_KINDS),
        help=(
            "Optional explicit artifact kind. Default: auto-detect from "
            "the artifact JSON structure."
        ),
    )
    sign.add_argument(
        "--archive",
        type=Path,
        default=None,
        help=(
            "Optional archive path. When provided with --attestation-id, "
            "the attestation is persisted under <archive>/attestations/."
        ),
    )
    sign.add_argument(
        "--attestation-id",
        default=None,
        help=(
            "Identifier used as filename under <archive>/attestations/. "
            "Required when --archive is provided."
        ),
    )
    sign.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional extra output path for the attestation JSON.",
    )
    sign.set_defaults(_cmd=attestation_sign_command)

    verify = sub.add_parser(
        "verify",
        help=(
            "Offline verification of an attestation. Without --public-key: "
            "structural verification only (attestation_hash). With "
            "--public-key: full ed25519 cryptographic verification. "
            "rc=0 if valid, 1 if not."
        ),
    )
    verify.add_argument(
        "attestation_file",
        type=Path,
        help="Path to the OperatorAttestation JSON to verify.",
    )
    verify.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help=(
            "Optional path to a PEM SubjectPublicKeyInfo ed25519 public "
            "key. When provided, the signature is cryptographically "
            "verified and the fingerprint match is enforced."
        ),
    )
    verify.set_defaults(_cmd=attestation_verify_command)

    show = sub.add_parser(
        "show",
        help="Read a persisted attestation from <archive>/attestations/.",
    )
    show.add_argument(
        "attestation_id", help="Attestation identifier."
    )
    show.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path to the AIP archive.",
    )
    show.set_defaults(_cmd=attestation_show_command)
