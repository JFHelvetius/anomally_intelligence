"""CLI tests for ``aip transparency declare-key`` (ADR-0043).

End-to-end through ``aip.cli.main`` so argparse wiring, exit codes, and
JSON output are exercised together. Every test runs the CLI against a
``tmp_path`` archive — no shared state, no network, no clock dependency.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from aip.attestation import generate_keypair, serialize_public_key_pem
from aip.cli import main as cli_main
from aip.transparency.key_declaration import (
    KEY_DECLARATION_FILENAME,
    fingerprint_of_pem_file,
)
from aip.transparency.store import TRANSPARENCY_DIRNAME


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _seed_operator_key(archive_root: Path) -> str:
    _, pub = generate_keypair()
    transparency = archive_root / TRANSPARENCY_DIRNAME
    transparency.mkdir(parents=True, exist_ok=True)
    pem_path = transparency / "public-key.pem"
    pem_path.write_bytes(serialize_public_key_pem(pub))
    return fingerprint_of_pem_file(pem_path)


def _seed_witness_key(archive_root: Path) -> str:
    _, pub = generate_keypair()
    wdir = archive_root / TRANSPARENCY_DIRNAME / "witness-keys"
    wdir.mkdir(parents=True, exist_ok=True)
    tmp = wdir / "_tmp.pem"
    tmp.write_bytes(serialize_public_key_pem(pub))
    fp = fingerprint_of_pem_file(tmp)
    tmp.rename(wdir / f"{fp}.pem")
    return fp


# --------------------------------------------------------------- init


def test_init_creates_declaration_with_operator_fingerprint(
    archive_root: Path,
) -> None:
    op_fp = _seed_operator_key(archive_root)
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["action"] == "declare_key_init"
    assert payload["operator_fingerprint"] == op_fp
    assert payload["witnesses_seeded"] == 0

    # File exists with the right shape.
    decl = json.loads(
        (
            archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
        ).read_text(encoding="utf-8")
    )
    assert decl["operator"]["public_key_fingerprint"] == op_fp


def test_init_seeds_witnesses_from_disk(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    w_fp = _seed_witness_key(archive_root)
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["witnesses_seeded"] == 1
    decl = json.loads(
        (
            archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
        ).read_text(encoding="utf-8")
    )
    assert decl["witnesses"][0]["public_key_fingerprint"] == w_fp


def test_init_no_seed_witnesses_flag_skips_witnesses(
    archive_root: Path,
) -> None:
    _seed_operator_key(archive_root)
    _seed_witness_key(archive_root)
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
            "--no-seed-witnesses",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["witnesses_seeded"] == 0


def test_init_refuses_overwrite_without_force(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    rc, _out, _err = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    assert rc == 0

    rc2, _out2, err2 = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    assert rc2 != 0
    assert "already exists" in err2


def test_init_force_overwrites(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    rc, _out, _err = _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x2",
            "--force",
        ]
    )
    assert rc == 0
    decl = json.loads(
        (
            archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
        ).read_text(encoding="utf-8")
    )
    assert decl["operator"]["operator_id"] == "op-x2"


# --------------------------------------------------------------- add-reference


def test_add_reference_to_operator(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "add-reference",
            "--archive-root",
            str(archive_root),
            "--kind",
            "github_user_keys",
            "--uri",
            "https://github.com/op-x.keys",
            "--note",
            "ssh-keygen -lf",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["added"]["target"] == "operator"
    decl = json.loads(
        (
            archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
        ).read_text(encoding="utf-8")
    )
    refs = decl["operator"]["external_references"]
    assert len(refs) == 1
    assert refs[0]["uri"] == "https://github.com/op-x.keys"
    assert refs[0]["note"] == "ssh-keygen -lf"


def test_add_reference_to_witness_by_fingerprint(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    w_fp = _seed_witness_key(archive_root)
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "add-reference",
            "--archive-root",
            str(archive_root),
            "--kind",
            "https_pem",
            "--uri",
            "https://w.example/k.pem",
            "--witness-fingerprint",
            w_fp,
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["added"]["target"].startswith("witness:fingerprint:")
    decl = json.loads(
        (
            archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
        ).read_text(encoding="utf-8")
    )
    assert decl["operator"]["external_references"] == []
    assert decl["witnesses"][0]["external_references"][0]["uri"] == (
        "https://w.example/k.pem"
    )


def test_add_reference_fails_without_declaration(archive_root: Path) -> None:
    rc, _out, err = _run(
        [
            "transparency",
            "declare-key",
            "add-reference",
            "--archive-root",
            str(archive_root),
            "--kind",
            "https_pem",
            "--uri",
            "https://example.com",
        ]
    )
    assert rc != 0
    assert "no declaration" in err


def test_add_reference_rejects_both_witness_selectors(
    archive_root: Path,
) -> None:
    _seed_operator_key(archive_root)
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    rc, _out, err = _run(
        [
            "transparency",
            "declare-key",
            "add-reference",
            "--archive-root",
            str(archive_root),
            "--kind",
            "x",
            "--uri",
            "y",
            "--witness-fingerprint",
            "a" * 64,
            "--witness-id",
            "alice",
        ]
    )
    assert rc != 0
    assert "mutually exclusive" in err


# --------------------------------------------------------------- show


def test_show_returns_zero_on_consistent_archive(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "show",
            "--archive-root",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["consistency"]["operator_matches"] is True


def test_show_returns_one_when_no_declaration(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "show",
            "--archive-root",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["consistency"]["declaration_present"] is False
    assert payload["declaration"] is None


def test_show_returns_one_when_phantom_witness(archive_root: Path) -> None:
    _seed_operator_key(archive_root)
    # Init with a witness that doesn't exist on disk.
    _run(
        [
            "transparency",
            "declare-key",
            "init",
            "--archive-root",
            str(archive_root),
            "--operator-id",
            "op-x",
        ]
    )
    # Inject a phantom witness manually by editing the file.
    decl_path = archive_root / TRANSPARENCY_DIRNAME / KEY_DECLARATION_FILENAME
    decl = json.loads(decl_path.read_text(encoding="utf-8"))
    decl["witnesses"].append(
        {
            "witness_operator_id": "ghost",
            "public_key_fingerprint": "0" * 64,
            "external_references": [],
        }
    )
    decl_path.write_text(json.dumps(decl), encoding="utf-8")

    rc, out, _err = _run(
        [
            "transparency",
            "declare-key",
            "show",
            "--archive-root",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    declared_missing = payload["consistency"]["declared_witnesses_without_pem"]
    assert len(declared_missing) == 1
    assert declared_missing[0]["witness_operator_id"] == "ghost"
