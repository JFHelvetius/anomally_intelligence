"""Tests for ``aip.transparency.key_declaration`` (ADR-0043).

The declaration is operator-supplied and trust-by-cross-check, so the
module's job is narrow: read/write JSON safely, compute fingerprints from
on-disk PEMs, append references at the right place, and report
inconsistencies between what the operator declared and what the archive
actually contains.

These tests cover the round-trip + every consistency case the rendering
layer relies on (``aip.report.builder._render_trust_footprint_section``
reads the same data and flags the same conditions).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aip.attestation import (
    generate_keypair,
    serialize_public_key_pem,
)
from aip.errors import AIPError
from aip.transparency.key_declaration import (
    KEY_DECLARATION_FILENAME,
    KEY_DECLARATION_TYPE,
    ConsistencyReport,
    TargetSelector,
    WitnessSeed,
    add_external_reference,
    check_consistency,
    declaration_path,
    fingerprint_of_pem_file,
    init_declaration,
    load_declaration,
    save_declaration,
)
from aip.transparency.store import TRANSPARENCY_DIRNAME


def _write_operator_pubkey(archive_root: Path) -> str:
    """Generate an ed25519 keypair, write the public PEM under transparency/,
    return its fingerprint."""
    _, pub = generate_keypair()
    pem = serialize_public_key_pem(pub)
    transparency = archive_root / TRANSPARENCY_DIRNAME
    transparency.mkdir(parents=True, exist_ok=True)
    pem_path = transparency / "public-key.pem"
    pem_path.write_bytes(pem)
    return fingerprint_of_pem_file(pem_path)


def _write_witness_pubkey(archive_root: Path) -> str:
    _, pub = generate_keypair()
    pem = serialize_public_key_pem(pub)
    wdir = archive_root / TRANSPARENCY_DIRNAME / "witness-keys"
    wdir.mkdir(parents=True, exist_ok=True)
    # Temporarily write to a known location to compute its fingerprint, then
    # rename to <fp>.pem per archive convention.
    tmp = wdir / "_tmp.pem"
    tmp.write_bytes(pem)
    fp = fingerprint_of_pem_file(tmp)
    tmp.rename(wdir / f"{fp}.pem")
    return fp


# --------------------------------------------------------------- fingerprint


def test_fingerprint_is_stable_across_reloads(archive_root: Path) -> None:
    """The fingerprint must be a function of DER bytes only — independent of
    PEM whitespace, comments, or filesystem path."""
    fp = _write_operator_pubkey(archive_root)
    again = fingerprint_of_pem_file(
        archive_root / TRANSPARENCY_DIRNAME / "public-key.pem"
    )
    assert fp == again
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


# --------------------------------------------------------------- init


def test_init_creates_declaration_with_operator_fingerprint(
    archive_root: Path,
) -> None:
    expected_fp = _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")

    assert data["declaration_type"] == KEY_DECLARATION_TYPE
    assert data["operator"]["operator_id"] == "op-x"
    assert data["operator"]["public_key_fingerprint"] == expected_fp
    assert data["operator"]["external_references"] == []
    assert data["witnesses"] == []
    assert "first_published_at" not in data["operator"]


def test_init_records_first_published_at_when_provided(
    archive_root: Path,
) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(
        archive_root,
        operator_id="op-x",
        first_published_at="2026-06-01T00:00:00Z",
    )
    assert data["operator"]["first_published_at"] == "2026-06-01T00:00:00Z"


def test_init_seeds_witnesses_when_supplied(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    seeds = (
        WitnessSeed(witness_operator_id="alice", public_key_fingerprint="a" * 64),
        WitnessSeed(witness_operator_id="bob", public_key_fingerprint="b" * 64),
    )
    data = init_declaration(archive_root, operator_id="op-x", witnesses=seeds)
    assert len(data["witnesses"]) == 2
    assert data["witnesses"][0]["witness_operator_id"] == "alice"
    assert data["witnesses"][0]["external_references"] == []
    assert data["witnesses"][1]["public_key_fingerprint"] == "b" * 64


def test_init_refuses_without_operator_pubkey_on_disk(
    archive_root: Path,
) -> None:
    """The fingerprint cannot be fabricated. If the archive has no
    ``public-key.pem``, init refuses — a declaration whose fingerprint
    cannot be verified against on-disk material is worthless."""
    with pytest.raises(AIPError, match="operator public key not found"):
        init_declaration(archive_root, operator_id="op-x")


# --------------------------------------------------------------- save / load


def test_save_and_load_round_trip(archive_root: Path) -> None:
    fp = _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    save_declaration(archive_root, data)

    loaded = load_declaration(archive_root)
    assert loaded is not None
    assert loaded["operator"]["public_key_fingerprint"] == fp
    assert loaded["operator"]["operator_id"] == "op-x"


def test_save_writes_pretty_sorted_json(archive_root: Path) -> None:
    """Diff-friendly: the on-disk file must be sorted by key and
    indented so PRs reviewing declaration changes are readable."""
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    save_declaration(archive_root, data)

    text = (
        archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
    ).read_text(encoding="utf-8")
    # Sorted: declaration_type before operator before schema_version before witnesses.
    assert text.index('"declaration_type"') < text.index('"operator"')
    assert text.index('"operator"') < text.index('"schema_version"')
    assert text.index('"schema_version"') < text.index('"witnesses"')
    assert "\n" in text  # indented, not minified


def test_load_returns_none_when_absent(archive_root: Path) -> None:
    assert load_declaration(archive_root) is None


def test_load_returns_none_on_wrong_declaration_type(archive_root: Path) -> None:
    transparency = archive_root / TRANSPARENCY_DIRNAME
    transparency.mkdir(parents=True)
    (transparency / KEY_DECLARATION_FILENAME).write_text(
        json.dumps({"declaration_type": "fake", "operator": {}}),
        encoding="utf-8",
    )
    assert load_declaration(archive_root) is None


# --------------------------------------------------------------- add_external_reference


def test_add_reference_defaults_to_operator(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    data = add_external_reference(
        data,
        kind="github_user_keys",
        uri="https://github.com/op-x.keys",
        note="ssh-keygen -lf",
    )
    refs = data["operator"]["external_references"]
    assert refs == [
        {
            "kind": "github_user_keys",
            "uri": "https://github.com/op-x.keys",
            "note": "ssh-keygen -lf",
        }
    ]


def test_add_reference_omits_note_when_none(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    data = add_external_reference(data, kind="dns_txt", uri="_aip-key.example.com")
    assert "note" not in data["operator"]["external_references"][0]


def test_add_reference_targets_witness_by_fingerprint(
    archive_root: Path,
) -> None:
    _write_operator_pubkey(archive_root)
    seeds = (
        WitnessSeed(witness_operator_id="alice", public_key_fingerprint="a" * 64),
    )
    data = init_declaration(archive_root, operator_id="op-x", witnesses=seeds)
    data = add_external_reference(
        data,
        kind="https_pem",
        uri="https://alice.example/key.pem",
        target=TargetSelector(witness_fingerprint="a" * 64),
    )
    assert data["operator"]["external_references"] == []
    assert data["witnesses"][0]["external_references"][0]["uri"] == (
        "https://alice.example/key.pem"
    )


def test_add_reference_targets_witness_by_id(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    seeds = (
        WitnessSeed(witness_operator_id="alice", public_key_fingerprint="a" * 64),
    )
    data = init_declaration(archive_root, operator_id="op-x", witnesses=seeds)
    data = add_external_reference(
        data,
        kind="verbal_in_person",
        uri="meeting:2026-06-05",
        target=TargetSelector(witness_operator_id="alice"),
    )
    assert data["witnesses"][0]["external_references"][0]["kind"] == (
        "verbal_in_person"
    )


def test_add_reference_rejects_both_witness_selectors(
    archive_root: Path,
) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    with pytest.raises(AIPError, match="at most one"):
        add_external_reference(
            data,
            kind="x",
            uri="y",
            target=TargetSelector(
                witness_fingerprint="a" * 64, witness_operator_id="alice"
            ),
        )


def test_add_reference_rejects_unknown_witness(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    with pytest.raises(AIPError, match="no witness matching"):
        add_external_reference(
            data,
            kind="x",
            uri="y",
            target=TargetSelector(witness_fingerprint="z" * 64),
        )


def test_add_reference_rejects_empty_kind(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    with pytest.raises(AIPError, match="'kind' must be non-empty"):
        add_external_reference(data, kind="", uri="y")


def test_add_reference_rejects_empty_uri(archive_root: Path) -> None:
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    with pytest.raises(AIPError, match="'uri' must be non-empty"):
        add_external_reference(data, kind="x", uri="")


# --------------------------------------------------------------- check_consistency


def test_consistency_no_declaration_marks_present_false(
    archive_root: Path,
) -> None:
    rep = check_consistency(archive_root)
    assert rep == ConsistencyReport(
        declaration_present=False,
        operator_fingerprint_declared=None,
        operator_fingerprint_actual=None,
        operator_matches=False,
        witnesses_declared=0,
        witnesses_in_archive=0,
        declared_witnesses_without_pem=[],
        extra_witness_pems_not_declared=[],
    )
    assert rep.ok is False


def test_consistency_happy_path(archive_root: Path) -> None:
    op_fp = _write_operator_pubkey(archive_root)
    w_fp = _write_witness_pubkey(archive_root)
    data = init_declaration(
        archive_root,
        operator_id="op-x",
        witnesses=(WitnessSeed("w-alice", w_fp),),
    )
    save_declaration(archive_root, data)

    rep = check_consistency(archive_root)
    assert rep.declaration_present is True
    assert rep.operator_fingerprint_declared == op_fp
    assert rep.operator_fingerprint_actual == op_fp
    assert rep.operator_matches is True
    assert rep.witnesses_declared == 1
    assert rep.witnesses_in_archive == 1
    assert rep.declared_witnesses_without_pem == []
    assert rep.extra_witness_pems_not_declared == []
    assert rep.ok is True


def test_consistency_flags_phantom_witness(archive_root: Path) -> None:
    """A declared witness with no matching .pem must be flagged. This is the
    load-bearing safety property: the report renders this as a visible
    warning."""
    _write_operator_pubkey(archive_root)
    data = init_declaration(
        archive_root,
        operator_id="op-x",
        witnesses=(WitnessSeed("ghost", "0" * 64),),
    )
    save_declaration(archive_root, data)

    rep = check_consistency(archive_root)
    assert rep.ok is False
    assert rep.declared_witnesses_without_pem == [
        {"witness_operator_id": "ghost", "public_key_fingerprint": "0" * 64}
    ]


def test_consistency_flags_extra_witness_pem_not_in_declaration(
    archive_root: Path,
) -> None:
    """Inverse of the phantom case: a .pem on disk that nobody declared.
    Not a security failure per se but worth surfacing so the operator
    knows to declare it before publishing the next report."""
    _write_operator_pubkey(archive_root)
    extra_fp = _write_witness_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")  # no witnesses
    save_declaration(archive_root, data)

    rep = check_consistency(archive_root)
    assert rep.extra_witness_pems_not_declared == [extra_fp]
    # An undeclared extra is not a hard failure (operator may not be ready
    # to publish), so ok stays True if everything else is consistent.
    assert rep.ok is True


def test_consistency_flags_operator_fingerprint_mismatch(
    archive_root: Path,
) -> None:
    """If someone tampers the declaration to claim a different fingerprint,
    the consistency check must refuse to call it OK."""
    _write_operator_pubkey(archive_root)
    data = init_declaration(archive_root, operator_id="op-x")
    # Tamper.
    data["operator"]["public_key_fingerprint"] = "f" * 64
    save_declaration(archive_root, data)

    rep = check_consistency(archive_root)
    assert rep.operator_matches is False
    assert rep.operator_fingerprint_declared == "f" * 64
    assert rep.ok is False


# --------------------------------------------------------------- path helpers


def test_declaration_path_is_under_transparency_dir(archive_root: Path) -> None:
    p = declaration_path(archive_root)
    assert p.parent == archive_root / TRANSPARENCY_DIRNAME
    assert p.name == KEY_DECLARATION_FILENAME
