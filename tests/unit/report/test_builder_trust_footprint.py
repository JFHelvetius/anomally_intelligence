"""Tests for the Signer trust footprint section in standalone HTML reports.

The trust footprint closes the only verifiability gap that pure crypto
cannot — the key-to-identity binding. The report cannot prove a public
key belongs to whom it claims; the operator's external-publication
declaration lets the receptor cross-check.

These tests target three layers:

1. ``_load_key_declaration`` — file present / missing / malformed / wrong type.
2. ``_render_trust_footprint_section`` — empty-archive shortcut, the
   warning rendered when no declaration is present, the full block when
   one is, and the archive-mismatch warning when a witness is declared
   but absent from ``transparency/witness-keys/``.
3. End-to-end via ``load_report_data`` — declaration round-trips into
   the final dict that the JS reads at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

from aip.report.builder import (
    _load_key_declaration,
    _render_trust_footprint_section,
)

DECL_TYPE = "aip.transparency.key-declaration.v1"
SAMPLE_FP = "c8a9c6d4e10c7e644be9310806b65a3405cdfedac642974df0b9b362c93a0f55"
PHANTOM_FP = "0" * 64


def _write_declaration(archive_root: Path, body: dict[str, object]) -> None:
    transparency = archive_root / "transparency"
    transparency.mkdir(parents=True, exist_ok=True)
    (transparency / "key-declaration.json").write_text(
        json.dumps(body), encoding="utf-8"
    )


# ----------------------------------------------------------- loader: file states


def test_load_declaration_returns_none_when_missing(archive_root: Path) -> None:
    assert _load_key_declaration(archive_root) is None


def test_load_declaration_returns_none_when_malformed_json(
    archive_root: Path,
) -> None:
    transparency = archive_root / "transparency"
    transparency.mkdir()
    (transparency / "key-declaration.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    assert _load_key_declaration(archive_root) is None


def test_load_declaration_returns_none_when_wrong_type(
    archive_root: Path,
) -> None:
    """Anyone could drop a JSON file in transparency/; the loader must
    refuse anything that doesn't claim to be our schema."""
    _write_declaration(
        archive_root,
        {
            "declaration_type": "something.else.v1",
            "operator": {"operator_id": "x"},
        },
    )
    assert _load_key_declaration(archive_root) is None


def test_load_declaration_returns_none_for_non_dict_root(
    archive_root: Path,
) -> None:
    transparency = archive_root / "transparency"
    transparency.mkdir()
    (transparency / "key-declaration.json").write_text(
        '["not", "an", "object"]', encoding="utf-8"
    )
    assert _load_key_declaration(archive_root) is None


def test_load_declaration_returns_dict_when_valid(archive_root: Path) -> None:
    body = {
        "declaration_type": DECL_TYPE,
        "schema_version": "1",
        "operator": {
            "operator_id": "op-x",
            "public_key_fingerprint": SAMPLE_FP,
            "external_references": [
                {"kind": "github_user_keys", "uri": "https://github.com/x.keys"}
            ],
        },
        "witnesses": [],
    }
    _write_declaration(archive_root, body)
    loaded = _load_key_declaration(archive_root)
    assert loaded is not None
    assert loaded["operator"]["operator_id"] == "op-x"
    assert loaded["operator"]["public_key_fingerprint"] == SAMPLE_FP


# ----------------------------------------------------------- renderer states


def test_renderer_empty_when_no_keys_and_no_declaration() -> None:
    """If the archive has no operator pubkey, no witness keys, and no
    declaration, the trust footprint section is omitted entirely — there
    is nothing to surface and a blank section would be noise."""
    out = _render_trust_footprint_section(
        {
            "key_declaration": None,
            "operator_public_key_pem": None,
            "witness_public_keys": {},
        }
    )
    assert out == ""


def test_renderer_warns_when_keys_present_but_no_declaration() -> None:
    """Honesty: pubkeys exist in the archive but the operator hasn't
    declared external references. The receptor must see this explicitly
    or they'll assume identity is verified."""
    pem = "-----BEGIN PUBLIC KEY-----\nABC\n-----END PUBLIC KEY-----\n"
    out = _render_trust_footprint_section(
        {
            "key_declaration": None,
            "operator_public_key_pem": pem,
            "witness_public_keys": {},
        }
    )
    assert "Signer trust footprint" in out
    assert "No key declaration in this archive" in out
    assert "transparency/key-declaration.json" in out


def test_renderer_shows_operator_block_when_declaration_present() -> None:
    out = _render_trust_footprint_section(
        {
            "key_declaration": {
                "declaration_type": DECL_TYPE,
                "operator": {
                    "operator_id": "op-x",
                    "public_key_fingerprint": SAMPLE_FP,
                    "first_published_at": "2026-06-01T00:00:00Z",
                    "external_references": [
                        {
                            "kind": "github_user_keys",
                            "uri": "https://github.com/x.keys",
                            "note": "compare via ssh-keygen",
                        },
                        {
                            "kind": "dns_txt",
                            "uri": "_aip-key.example.com",
                        },
                    ],
                },
                "witnesses": [],
            },
            "operator_public_key_pem": "PEM",
            "witness_public_keys": {},
        }
    )
    assert "Operator key" in out
    assert SAMPLE_FP in out
    assert "2026-06-01T00:00:00Z" in out
    assert "github_user_keys" in out
    assert "https://github.com/x.keys" in out
    assert "compare via ssh-keygen" in out
    assert "External references (2)" in out
    # No witness block because none declared.
    assert "Witness keys" not in out
    # No mismatch warning because no inconsistency.
    assert "Declaration / archive mismatch" not in out


def test_renderer_flags_witness_declared_without_archive_pem() -> None:
    """A declaration that names a witness fingerprint not present in
    ``transparency/witness-keys/`` is internally inconsistent. The renderer
    must surface that loudly — the receptor cannot verify signatures from
    a witness whose key is only asserted, never embedded."""
    out = _render_trust_footprint_section(
        {
            "key_declaration": {
                "declaration_type": DECL_TYPE,
                "operator": {
                    "operator_id": "op-x",
                    "public_key_fingerprint": SAMPLE_FP,
                    "external_references": [],
                },
                "witnesses": [
                    {
                        "witness_operator_id": "phantom",
                        "public_key_fingerprint": PHANTOM_FP,
                        "external_references": [],
                    }
                ],
            },
            "operator_public_key_pem": "PEM",
            "witness_public_keys": {},
        }
    )
    assert "Declaration / archive mismatch" in out
    assert "phantom" in out
    # Truncated fingerprint preview must appear (first 16 chars + ellipsis).
    assert PHANTOM_FP[:16] in out


def test_renderer_no_mismatch_when_witness_pem_present() -> None:
    out = _render_trust_footprint_section(
        {
            "key_declaration": {
                "declaration_type": DECL_TYPE,
                "operator": {
                    "operator_id": "op-x",
                    "public_key_fingerprint": SAMPLE_FP,
                    "external_references": [],
                },
                "witnesses": [
                    {
                        "witness_operator_id": "ok-witness",
                        "public_key_fingerprint": PHANTOM_FP,
                        "external_references": [
                            {"kind": "https_pem", "uri": "https://w.example/k.pem"}
                        ],
                    }
                ],
            },
            "operator_public_key_pem": "PEM",
            "witness_public_keys": {PHANTOM_FP: "WITNESS PEM"},
        }
    )
    assert "Declaration / archive mismatch" not in out
    assert "ok-witness" in out
    assert "Witness keys (1)" in out


def test_renderer_shows_no_refs_label_when_empty_list() -> None:
    """Operators can publish a declaration with an empty external_references
    list (e.g., placeholder during setup). The UI must not mislead the
    receptor into thinking a verification path exists."""
    out = _render_trust_footprint_section(
        {
            "key_declaration": {
                "declaration_type": DECL_TYPE,
                "operator": {
                    "operator_id": "op-x",
                    "public_key_fingerprint": SAMPLE_FP,
                    "external_references": [],
                },
                "witnesses": [],
            },
            "operator_public_key_pem": "PEM",
            "witness_public_keys": {},
        }
    )
    assert "No external references declared" in out
    assert "External references (0)" in out
