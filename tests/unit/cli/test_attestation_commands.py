"""Tests del CLI ``aip attestation`` (ADR-0041 §CLI)."""

from __future__ import annotations

import io
import json
from pathlib import Path

from aip.attestation import decode_attestation
from aip.cli import main as cli_main


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _write_workspace(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "workspace_id": "w-1",
                "workspace_hash": "a" * 64,
                "references": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _keygen(tmp_path: Path) -> tuple[Path, Path]:
    priv = tmp_path / "keys" / "priv.pem"
    pub = tmp_path / "keys" / "pub.pem"
    rc, _, err = _run(
        [
            "attestation",
            "keygen",
            "--output-private",
            str(priv),
            "--output-public",
            str(pub),
        ]
    )
    assert rc == 0, err
    return priv, pub


# ---------------------------------------------------------------- discoverability


def test_attestation_subgroup_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "attestation" in names


def test_attestation_help_lists_four_actions() -> None:
    parser = cli_main.build_parser()
    # walk into the attestation subparser
    attestation_action = None
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and "attestation" in choices:
            attestation_action = choices["attestation"]
            break
    assert attestation_action is not None
    sub_names: set[str] = set()
    for action in attestation_action._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            sub_names.update(str(k) for k in choices)
    assert sub_names == {"keygen", "sign", "verify", "show"}


# ---------------------------------------------------------------- keygen


def test_keygen_happy_path(tmp_path: Path) -> None:
    priv, pub = _keygen(tmp_path)
    assert priv.is_file()
    assert pub.is_file()
    assert priv.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
    assert pub.read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")


# ---------------------------------------------------------------- sign


def test_sign_happy_path_without_archive(tmp_path: Path) -> None:
    priv, _pub = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    out_sig = tmp_path / "sig.json"
    rc, out, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(out_sig),
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["signer_id"] == "@op"
    assert payload["artifact_kind"] == "workspace"
    assert payload["signature_algorithm"] == "ed25519-v1"
    assert out_sig.is_file()


def test_sign_persists_under_archive(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    archive = tmp_path / "archive"
    rc, _, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--archive",
            str(archive),
            "--attestation-id",
            "att-1",
        ]
    )
    assert rc == 0, err
    target = archive / "attestations" / "att-1.json"
    assert target.is_file()
    att = decode_attestation(target.read_text(encoding="utf-8"))
    assert att.signer_id == "@op"
    assert att.artifact_kind == "workspace"


def test_sign_requires_attestation_id_when_archive_given(
    tmp_path: Path,
) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    rc, _, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--archive",
            str(tmp_path / "archive"),
        ]
    )
    assert rc == 64
    assert "attestation-id" in err


def test_sign_rejects_invalid_signed_at(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    rc, _, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "not-a-timestamp",
            "--output",
            str(tmp_path / "sig.json"),
        ]
    )
    assert rc == 64
    assert "signed-at" in err


def test_sign_explicit_artifact_kind_override(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    rc, out, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--artifact-kind",
            "workspace",
            "--output",
            str(tmp_path / "sig.json"),
        ]
    )
    assert rc == 0, err
    assert json.loads(out)["artifact_kind"] == "workspace"


def test_sign_autodetect_fails_for_unknown_shape(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = tmp_path / "weird.json"
    artifact.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    rc, _, err = _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(tmp_path / "sig.json"),
        ]
    )
    assert rc == 1
    assert "auto-detect" in err


# ---------------------------------------------------------------- verify


def test_verify_structural_only(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    sig_path = tmp_path / "sig.json"
    _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(sig_path),
        ]
    )
    rc, out, err = _run(["attestation", "verify", str(sig_path)])
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["structural_only"] is True
    assert payload["crypto_verified"] is False


def test_verify_with_public_key_full_crypto(tmp_path: Path) -> None:
    priv, pub = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    sig_path = tmp_path / "sig.json"
    _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(sig_path),
        ]
    )
    rc, out, err = _run(
        [
            "attestation",
            "verify",
            str(sig_path),
            "--public-key",
            str(pub),
        ]
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["crypto_verified"] is True
    assert payload["structural_only"] is False


def test_verify_with_wrong_public_key_rc1(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    _, wrong_pub_path = _keygen(tmp_path / "other")
    artifact = _write_workspace(tmp_path / "ws.json")
    sig_path = tmp_path / "sig.json"
    _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(sig_path),
        ]
    )
    rc, out, _ = _run(
        [
            "attestation",
            "verify",
            str(sig_path),
            "--public-key",
            str(wrong_pub_path),
        ]
    )
    assert rc == 1
    assert json.loads(out)["ok"] is False


def test_verify_missing_file_rc1(tmp_path: Path) -> None:
    rc, _, err = _run(["attestation", "verify", str(tmp_path / "absent.json")])
    assert rc == 1
    assert "not found" in err


# ---------------------------------------------------------------- show


def test_show_loads_persisted_attestation(tmp_path: Path) -> None:
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    archive = tmp_path / "archive"
    _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--archive",
            str(archive),
            "--attestation-id",
            "att-1",
        ]
    )
    rc, out, err = _run(["attestation", "show", "att-1", "--archive", str(archive)])
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["signer_id"] == "@op"


def test_show_missing_id_rc1(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    rc, _, err = _run(["attestation", "show", "absent", "--archive", str(archive)])
    assert rc == 1
    assert "absent" in err


# ---------------------------------------------------------------- universal verify integration


def test_universal_verify_autodetects_attestation(tmp_path: Path) -> None:
    """``aip verify`` debe detectar attestations y delegar."""
    priv, _ = _keygen(tmp_path)
    artifact = _write_workspace(tmp_path / "ws.json")
    sig_path = tmp_path / "sig.json"
    _run(
        [
            "attestation",
            "sign",
            str(artifact),
            "--private-key",
            str(priv),
            "--signer-id",
            "@op",
            "--signed-at",
            "2026-06-07T12:00:00Z",
            "--output",
            str(sig_path),
        ]
    )
    rc, out, err = _run(["verify", str(sig_path)])
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["artifact_kind"] == "attestation"
    assert payload["ok"] is True
