"""Tests for ``GET /api/transparency/key-declaration``.

The endpoint is a thin pass-through over
:func:`aip.transparency.key_declaration.check_consistency` and
:func:`load_declaration`. The underlying functions have their own
exhaustive coverage (see ``tests/unit/transparency/test_key_declaration.py``).
These tests verify the JSON shape the operator dashboard and the public
portal consume — drift in this layer would silently break both UIs.
"""

from __future__ import annotations

import json
from pathlib import Path

from aip import Archive
from aip.api.routes.transparency import get_key_declaration
from aip.attestation import generate_keypair, serialize_public_key_pem
from aip.transparency.key_declaration import (
    KEY_DECLARATION_FILENAME,
    KEY_DECLARATION_TYPE,
    WitnessSeed,
    init_declaration,
    operator_public_key_path,
    save_declaration,
)
from aip.transparency.store import TRANSPARENCY_DIRNAME


def _archive_facade(archive_root: Path) -> Archive:
    """Construct an Archive facade over the test directory.

    The endpoint reads only ``<root>/transparency/...``; no audit log or
    other archive state is needed. We deliberately bypass full archive
    bootstrapping to keep these route tests focused on the JSON contract.
    """
    return Archive.open(archive_root)


def _seed_operator_pubkey(archive_root: Path) -> None:
    """Generate an ed25519 key and drop the PEM where the loader expects."""
    _, pub = generate_keypair()
    pem = serialize_public_key_pem(pub)
    (archive_root / TRANSPARENCY_DIRNAME).mkdir(parents=True, exist_ok=True)
    operator_public_key_path(archive_root).write_bytes(pem)


# --------------------------------------------------------------- absent state


def test_get_key_declaration_returns_null_when_archive_has_none(
    archive_root: Path,
) -> None:
    archive = _archive_facade(archive_root)
    result = get_key_declaration(archive)

    assert result["declaration"] is None
    consistency = result["consistency"]
    assert consistency["declaration_present"] is False
    assert consistency["operator_matches"] is False
    assert consistency["ok"] is False


# --------------------------------------------------------------- happy path


def test_get_key_declaration_returns_consistent_for_well_formed_archive(
    archive_root: Path,
) -> None:
    archive = _archive_facade(archive_root)
    _seed_operator_pubkey(archive_root)
    decl = init_declaration(archive_root, operator_id="op-x")
    save_declaration(archive_root, decl)

    result = get_key_declaration(archive)

    assert result["declaration"] is not None
    assert result["declaration"]["declaration_type"] == KEY_DECLARATION_TYPE
    assert result["declaration"]["operator"]["operator_id"] == "op-x"

    consistency = result["consistency"]
    assert consistency["declaration_present"] is True
    assert consistency["operator_matches"] is True
    assert consistency["ok"] is True
    assert consistency["operator_fingerprint_declared"] == (
        consistency["operator_fingerprint_actual"]
    )


# --------------------------------------------------------------- mismatch


def test_get_key_declaration_flags_operator_fingerprint_mismatch(
    archive_root: Path,
) -> None:
    """A declaration whose operator fingerprint doesn't match the on-disk
    pubkey must produce ok=false. The Dashboard renders this as a red
    warning bar; if this regresses to silently ok the warning never
    fires."""
    archive = _archive_facade(archive_root)
    _seed_operator_pubkey(archive_root)
    decl = init_declaration(archive_root, operator_id="op-x")
    # Tamper with the declared fingerprint.
    decl["operator"]["public_key_fingerprint"] = "f" * 64
    save_declaration(archive_root, decl)

    result = get_key_declaration(archive)

    consistency = result["consistency"]
    assert consistency["operator_matches"] is False
    assert consistency["ok"] is False
    assert consistency["operator_fingerprint_declared"] == "f" * 64
    assert consistency["operator_fingerprint_actual"] != "f" * 64


def test_get_key_declaration_flags_phantom_witness(
    archive_root: Path,
) -> None:
    """A declared witness with no matching ``.pem`` is the canonical
    consistency failure caught by ADR-0043. The endpoint must surface
    it inside ``declared_witnesses_without_pem`` so the Dashboard
    Trust-footprint card can render the mismatch row."""
    archive = _archive_facade(archive_root)
    _seed_operator_pubkey(archive_root)
    decl = init_declaration(
        archive_root,
        operator_id="op-x",
        witnesses=(WitnessSeed("ghost", "0" * 64),),
    )
    save_declaration(archive_root, decl)

    result = get_key_declaration(archive)
    consistency = result["consistency"]
    assert consistency["ok"] is False
    assert consistency["declared_witnesses_without_pem"] == [
        {"witness_operator_id": "ghost", "public_key_fingerprint": "0" * 64}
    ]


# --------------------------------------------------------------- shape


def test_get_key_declaration_response_shape_is_stable(
    archive_root: Path,
) -> None:
    """The Dashboard + Portal TypeScript layer pins specific keys on the
    response (see ``web/src/api/client.ts``). This test pins the contract
    on the Python side so renaming a field surfaces here, not at runtime
    in the browser."""
    archive = _archive_facade(archive_root)
    _seed_operator_pubkey(archive_root)
    save_declaration(
        archive_root, init_declaration(archive_root, operator_id="op-x")
    )

    result = get_key_declaration(archive)

    assert set(result.keys()) == {"declaration", "consistency"}
    expected_consistency_keys = {
        "declaration_present",
        "operator_fingerprint_declared",
        "operator_fingerprint_actual",
        "operator_matches",
        "witnesses_declared",
        "witnesses_in_archive",
        "declared_witnesses_without_pem",
        "extra_witness_pems_not_declared",
        "ok",
    }
    assert set(result["consistency"].keys()) == expected_consistency_keys

    # Defensive: JSON-serialisable end-to-end. FastAPI does this for us
    # at the wire layer, but Pydantic's quiet coercion can mask
    # non-JSON-safe values that would only fail in prod.
    json.dumps(result)


def test_get_key_declaration_handles_malformed_json_in_archive(
    archive_root: Path,
) -> None:
    """A user-edited declaration file that is no longer valid JSON must
    not crash the endpoint — it should degrade to the 'no declaration'
    state, exactly as if the file were absent. Anything else exposes the
    backend to a denial-of-service via a bad file."""
    archive = _archive_facade(archive_root)
    _seed_operator_pubkey(archive_root)
    target = archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not valid json", encoding="utf-8")

    result = get_key_declaration(archive)
    assert result["declaration"] is None
    assert result["consistency"]["declaration_present"] is False
