"""Operator-supplied key declaration for the trust footprint (ADR-0043).

The declaration lives at ``<archive>/transparency/key-declaration.json`` and
maps each public key (operator + witnesses) to a list of external
references where the operator independently publishes the same key. The
standalone HTML report surfaces this so the receptor can cross-check the
embedded pubkeys against an external source instead of trusting them
blindly.

This module owns the schema constants, load/save logic, and pure mutation
helpers. The CLI (``aip transparency declare-key``) is a thin wrapper that
parses arguments and calls these functions. All I/O is JSON; no network,
no crypto operations beyond computing fingerprints from existing PEM files
(via :mod:`aip.attestation.signer`).

Design properties:

- **Opt-in**: if the file is absent, the report shows an honest warning.
- **Operator-supplied**: nothing here is verified by AIP — the declaration
  is a manifest of *claims* about where the operator says the keys live.
- **Forward-compatible**: unknown reference ``kind`` values pass through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from aip.attestation.signer import (
    compute_public_key_fingerprint,
    load_public_key,
)
from aip.errors import AIPError
from aip.transparency.store import TRANSPARENCY_DIRNAME

KEY_DECLARATION_FILENAME: Final[str] = "key-declaration.json"
KEY_DECLARATION_TYPE: Final[str] = "aip.transparency.key-declaration.v1"
KEY_DECLARATION_SCHEMA_VERSION: Final[str] = "1"

_PUBLIC_KEY_FILENAME: Final[str] = "public-key.pem"
_WITNESS_KEYS_DIRNAME: Final[str] = "witness-keys"


# --------------------------------------------------------------------- paths


def declaration_path(archive_root: Path) -> Path:
    """Canonical path of the declaration file within an archive."""
    return archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME


def operator_public_key_path(archive_root: Path) -> Path:
    return archive_root / TRANSPARENCY_DIRNAME / _PUBLIC_KEY_FILENAME


def witness_keys_dir(archive_root: Path) -> Path:
    return archive_root / TRANSPARENCY_DIRNAME / _WITNESS_KEYS_DIRNAME


# --------------------------------------------------------------------- helpers


def fingerprint_of_pem_file(pem_path: Path) -> str:
    """SHA-256 hex of the DER SPKI of an ed25519 PEM public key."""
    key = load_public_key(pem_path)
    return compute_public_key_fingerprint(key)


def _list_witness_pem_fingerprints(archive_root: Path) -> dict[str, Path]:
    """Map ``fingerprint -> .pem path`` for each well-formed witness key file.

    The on-disk convention is ``<archive>/transparency/witness-keys/<fp>.pem``
    where ``<fp>`` equals the SHA-256 DER SPKI fingerprint. We verify by
    recomputing rather than trusting the filename — a mismatch indicates the
    archive is inconsistent and should be flagged separately.
    """
    d = witness_keys_dir(archive_root)
    out: dict[str, Path] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir(), key=lambda x: x.name):
        if not p.is_file() or p.suffix != ".pem":
            continue
        try:
            out[fingerprint_of_pem_file(p)] = p
        except (ValueError, OSError):
            continue
    return out


# --------------------------------------------------------------------- load/save


def load_declaration(archive_root: Path) -> dict[str, Any] | None:
    """Return the declaration dict if present and well-typed, else ``None``."""
    target = declaration_path(archive_root)
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("declaration_type") != KEY_DECLARATION_TYPE:
        return None
    return data


def save_declaration(archive_root: Path, data: dict[str, Any]) -> Path:
    """Write the declaration JSON sorted+indented for diffability."""
    target = declaration_path(archive_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


# --------------------------------------------------------------------- builders


@dataclass(frozen=True)
class WitnessSeed:
    """Initial witness entry for :func:`init_declaration`."""

    witness_operator_id: str
    public_key_fingerprint: str


def init_declaration(
    archive_root: Path,
    *,
    operator_id: str,
    first_published_at: str | None = None,
    witnesses: tuple[WitnessSeed, ...] = (),
) -> dict[str, Any]:
    """Build a fresh declaration from the operator's pubkey on disk.

    Reads ``transparency/public-key.pem`` and computes its fingerprint —
    refuses to fabricate one. The declaration starts with empty
    ``external_references``; the operator adds them via subsequent calls
    to :func:`add_external_reference`.

    Witness seeds are inserted as-is. The CLI is responsible for verifying
    that each declared fingerprint corresponds to a witness key already in
    ``transparency/witness-keys/`` (the consistency check rendered by the
    HTML report relies on that invariant).
    """
    pk_path = operator_public_key_path(archive_root)
    if not pk_path.is_file():
        raise AIPError(
            f"cannot init declaration: operator public key not found at {pk_path}. "
            "Generate one with 'aip attestation generate-key' first."
        )
    fp = fingerprint_of_pem_file(pk_path)

    operator: dict[str, Any] = {
        "operator_id": operator_id,
        "public_key_fingerprint": fp,
        "external_references": [],
    }
    if first_published_at is not None:
        operator["first_published_at"] = first_published_at

    return {
        "declaration_type": KEY_DECLARATION_TYPE,
        "schema_version": KEY_DECLARATION_SCHEMA_VERSION,
        "operator": operator,
        "witnesses": [
            {
                "witness_operator_id": w.witness_operator_id,
                "public_key_fingerprint": w.public_key_fingerprint,
                "external_references": [],
            }
            for w in witnesses
        ],
    }


# --------------------------------------------------------------------- mutate


@dataclass(frozen=True)
class TargetSelector:
    """How to locate the entry that receives a new reference.

    Exactly one of ``witness_fingerprint`` or ``witness_operator_id`` may be
    non-None to target a witness; both ``None`` targets the operator block.
    """

    witness_fingerprint: str | None = None
    witness_operator_id: str | None = None

    def is_operator(self) -> bool:
        return self.witness_fingerprint is None and self.witness_operator_id is None


def add_external_reference(
    declaration: dict[str, Any],
    *,
    kind: str,
    uri: str,
    note: str | None = None,
    target: TargetSelector | None = None,
) -> dict[str, Any]:
    """Append an external reference. Returns the mutated declaration.

    Mutates a copy of the input dict's relevant list (preserves the caller's
    references where reasonable but does not deep-copy the whole tree —
    callers should treat the return as the source of truth and discard the
    input).

    Raises ``AIPError`` if the target witness cannot be located.
    """
    if not kind:
        raise AIPError("external reference 'kind' must be non-empty.")
    if not uri:
        raise AIPError("external reference 'uri' must be non-empty.")

    entry: dict[str, str] = {"kind": kind, "uri": uri}
    if note is not None:
        entry["note"] = note

    if target is None:
        target = TargetSelector()

    if target.is_operator():
        op = declaration.setdefault("operator", {})
        refs = op.setdefault("external_references", [])
        refs.append(entry)
        return declaration

    if target.witness_fingerprint is not None and target.witness_operator_id is not None:
        raise AIPError(
            "TargetSelector: provide at most one of witness_fingerprint / "
            "witness_operator_id."
        )

    witnesses = declaration.setdefault("witnesses", [])
    for w in witnesses:
        if (
            target.witness_fingerprint is not None
            and w.get("public_key_fingerprint") == target.witness_fingerprint
        ) or (
            target.witness_operator_id is not None
            and w.get("witness_operator_id") == target.witness_operator_id
        ):
            refs = w.setdefault("external_references", [])
            refs.append(entry)
            return declaration

    sel = (
        f"fingerprint={target.witness_fingerprint!r}"
        if target.witness_fingerprint is not None
        else f"operator_id={target.witness_operator_id!r}"
    )
    raise AIPError(
        f"no witness matching {sel} in declaration. Add it via init / a future "
        "'add-witness' helper before attaching references."
    )


# --------------------------------------------------------------------- inspect


@dataclass(frozen=True)
class ConsistencyReport:
    """Result of comparing the declaration against the archive contents."""

    declaration_present: bool
    operator_fingerprint_declared: str | None
    operator_fingerprint_actual: str | None
    operator_matches: bool
    witnesses_declared: int
    witnesses_in_archive: int
    declared_witnesses_without_pem: list[dict[str, str]]
    extra_witness_pems_not_declared: list[str]  # list of fingerprints

    @property
    def ok(self) -> bool:
        if not self.declaration_present:
            return False
        if not self.operator_matches:
            return False
        return not self.declared_witnesses_without_pem


def check_consistency(archive_root: Path) -> ConsistencyReport:
    """Compare on-disk archive state against the declared keys.

    Useful as a pre-publish sanity check and as the data source for the CLI
    ``show`` / ``verify`` subcommands. Does not modify anything.
    """
    decl = load_declaration(archive_root)
    pk_path = operator_public_key_path(archive_root)
    actual_op_fp: str | None = None
    if pk_path.is_file():
        try:
            actual_op_fp = fingerprint_of_pem_file(pk_path)
        except (ValueError, OSError):
            actual_op_fp = None

    if decl is None:
        return ConsistencyReport(
            declaration_present=False,
            operator_fingerprint_declared=None,
            operator_fingerprint_actual=actual_op_fp,
            operator_matches=False,
            witnesses_declared=0,
            witnesses_in_archive=len(_list_witness_pem_fingerprints(archive_root)),
            declared_witnesses_without_pem=[],
            extra_witness_pems_not_declared=[],
        )

    declared_op_fp = (decl.get("operator") or {}).get("public_key_fingerprint")
    op_matches = (
        declared_op_fp is not None
        and actual_op_fp is not None
        and declared_op_fp == actual_op_fp
    )

    witness_pems = _list_witness_pem_fingerprints(archive_root)
    declared_witnesses = decl.get("witnesses") or []
    missing: list[dict[str, str]] = []
    declared_fps: set[str] = set()
    for w in declared_witnesses:
        fp = w.get("public_key_fingerprint") or ""
        wid = w.get("witness_operator_id") or "?"
        if fp:
            declared_fps.add(fp)
        if fp and fp not in witness_pems:
            missing.append({"witness_operator_id": wid, "public_key_fingerprint": fp})
    extra = sorted(fp for fp in witness_pems if fp not in declared_fps)

    return ConsistencyReport(
        declaration_present=True,
        operator_fingerprint_declared=declared_op_fp,
        operator_fingerprint_actual=actual_op_fp,
        operator_matches=op_matches,
        witnesses_declared=len(declared_witnesses),
        witnesses_in_archive=len(witness_pems),
        declared_witnesses_without_pem=missing,
        extra_witness_pems_not_declared=extra,
    )


__all__ = [
    "KEY_DECLARATION_FILENAME",
    "KEY_DECLARATION_SCHEMA_VERSION",
    "KEY_DECLARATION_TYPE",
    "ConsistencyReport",
    "TargetSelector",
    "WitnessSeed",
    "add_external_reference",
    "check_consistency",
    "declaration_path",
    "fingerprint_of_pem_file",
    "init_declaration",
    "load_declaration",
    "operator_public_key_path",
    "save_declaration",
    "witness_keys_dir",
]
