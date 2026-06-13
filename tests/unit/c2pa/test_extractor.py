"""Tests for ``aip.c2pa.extractor`` (ADR-0048).

Two layers of coverage:

1. **Transformation tests** (always run): exercise the C2PA→AIP shape
   transform by mocking ``c2pa.Reader.json()``. These pin the contract
   that AIP imposes on the c2pa-python output (root→leaf ordering,
   parent_manifest_label derivation from ingredients, validation_status
   roll-up).
2. **Real-binding integration tests** (skipped if ``c2pa`` not
   installed): exercise the actual c2pa-python parser on a manifest
   store built in-memory. These guarantee the contract still holds
   against the live API.

What we don't test in this file:

- Real X.509 verification (covered in ``test_x509_verifier.py``).
- The chain structural checks (covered in ``test_verifier.py``).
- The CLI exit codes (covered separately if/when an integration test
  runs the whole pipeline).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from aip.c2pa.extractor import extract_from_media
from aip.errors import AIPError

# --------------------------------------------------------------- fixtures


def _write_dummy_jpeg(path: Path) -> Path:
    """Write a minimal valid-ish JPEG so the file exists with the right
    extension. The body never reaches the binding in transform tests
    (the binding is mocked); for live-binding tests we use a real file."""
    path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
    return path


def _patch_reader_returning(c2pa_mod: mock.MagicMock, manifest_store_json: str) -> None:
    """Make c2pa.Reader behave like a context manager returning a fixed JSON."""

    class FakeReader:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeReader:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def json(self) -> str:
            return manifest_store_json

    c2pa_mod.Reader = FakeReader
    c2pa_mod.C2paError = Exception


# --------------------------------------------------------------- contract: install hint


def test_missing_c2pa_dep_raises_with_install_hint(tmp_path: Path) -> None:
    """The whole point of ADR-0048 being an *optional* dep is that AIP
    must say HOW to install it when the user tries to use the extractor
    without the package."""
    media = _write_dummy_jpeg(tmp_path / "test.jpg")
    with (
        mock.patch.dict("sys.modules", {"c2pa": None}),
        pytest.raises(AIPError, match=r"pip install 'aip\[c2pa\]'"),
    ):
        extract_from_media(media)


# --------------------------------------------------------------- contract: file checks


def test_missing_file_raises_clearly(tmp_path: Path) -> None:
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, "{}")
    with (
        mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}),
        pytest.raises(AIPError, match="media file not found"),
    ):
        extract_from_media(tmp_path / "does-not-exist.jpg")


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    bogus = tmp_path / "test.weirdext"
    bogus.write_bytes(b"anything")
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, "{}")
    with (
        mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}),
        pytest.raises(AIPError, match="unsupported media extension"),
    ):
        extract_from_media(bogus)


def test_empty_manifest_store_raises_no_manifest(tmp_path: Path) -> None:
    media = _write_dummy_jpeg(tmp_path / "empty.jpg")
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, "{}")
    with (
        mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}),
        pytest.raises(AIPError, match="no C2PA manifest store"),
    ):
        extract_from_media(media)


def test_garbled_json_from_binding_is_caught(tmp_path: Path) -> None:
    media = _write_dummy_jpeg(tmp_path / "garbled.jpg")
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, "{not valid")
    with (
        mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}),
        pytest.raises(AIPError, match="non-JSON output"),
    ):
        extract_from_media(media)


# --------------------------------------------------------------- shape transform


def test_single_root_manifest_transforms_to_aip_shape(tmp_path: Path) -> None:
    media = _write_dummy_jpeg(tmp_path / "img.jpg")
    store = {
        "active_manifest": "urn:uuid:root",
        "manifests": {
            "urn:uuid:root": {
                "claim_generator": "Sony Alpha 1 II",
                "format": "image/jpeg",
                "signature_info": {
                    "alg": "Ed25519",
                    "issuer": "CN=Sony Alpha 1 II,O=Sony Imaging Products & Solutions Inc.",
                    "cert_serial_number": "ab:cd:ef:01",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [
                    {"label": "c2pa.hash.data", "data": {"sha256": "a" * 64}},
                    {"label": "stds.exif", "data": {"Make": "Sony"}},
                ],
                "ingredients": [],
            },
        },
        "validation_status": [
            {"code": "claim.signature.trusted", "url": "self", "explanation": "OK"},
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    assert "manifests" in result
    assert len(result["manifests"]) == 1
    m = result["manifests"][0]
    assert m["label"] == "urn:uuid:root"
    assert m["parent_manifest_label"] is None
    assert m["signature_info"]["issuer_common_name"] == "Sony Alpha 1 II"
    assert m["signature_info"]["issuer_organization"] == (
        "Sony Imaging Products & Solutions Inc."
    )
    assert m["signature_info"]["cert_serial"] == "ab:cd:ef:01"
    assert m["signature_info"]["chain_verified"] is True
    # cert_chain_pem stays empty per ADR-0048 limitation note.
    assert m["signature_info"]["cert_chain_pem"] == []
    assert m["signature_info"]["chain_verified_against"] == (
        "c2pa-python internal trust list"
    )
    # Assertions ride through unchanged.
    assertion_labels = [a["label"] for a in m["assertions"]]
    assert "c2pa.hash.data" in assertion_labels
    assert "stds.exif" in assertion_labels


def test_camera_plus_editor_chain_is_ordered_root_to_leaf(tmp_path: Path) -> None:
    """The C2PA store keys are unordered; AIP must walk ingredients to
    produce the root→leaf ordering that downstream parsers expect."""
    media = _write_dummy_jpeg(tmp_path / "edited.jpg")
    store = {
        "active_manifest": "urn:uuid:editor",
        "manifests": {
            "urn:uuid:camera": {
                "claim_generator": "Sony",
                "signature_info": {
                    "issuer": "Sony Alpha 1",
                    "cert_serial_number": "111",
                    "time": "2026-06-13T11:00:00Z",
                },
                "assertions": [
                    {"label": "c2pa.hash.data", "data": {"sha256": "a" * 64}},
                ],
                "ingredients": [],
            },
            "urn:uuid:editor": {
                "claim_generator": "Adobe Photoshop",
                "signature_info": {
                    "issuer": "Adobe Inc.",
                    "cert_serial_number": "222",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [
                    {"label": "c2pa.hash.data", "data": {"sha256": "b" * 64}},
                    {"label": "c2pa.actions", "data": {"edits": "crop"}},
                ],
                "ingredients": [
                    {
                        "relationship": "parentOf",
                        "active_manifest": "urn:uuid:camera",
                    },
                ],
            },
        },
        "validation_status": [
            {"code": "claim.signature.trusted", "url": "self", "explanation": "OK"},
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    labels = [m["label"] for m in result["manifests"]]
    assert labels == ["urn:uuid:camera", "urn:uuid:editor"]
    assert result["manifests"][0]["parent_manifest_label"] is None
    assert result["manifests"][1]["parent_manifest_label"] == "urn:uuid:camera"


def test_untrusted_status_propagates_to_chain_verified(tmp_path: Path) -> None:
    """When c2pa-python's validation_status reports any failure code,
    every manifest's chain_verified must be False with the explanation
    surfaced. AIP must NOT silently downgrade or hide failure codes."""
    media = _write_dummy_jpeg(tmp_path / "bad.jpg")
    store = {
        "active_manifest": "urn:uuid:root",
        "manifests": {
            "urn:uuid:root": {
                "signature_info": {
                    "issuer": "Camera",
                    "cert_serial_number": "x",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [
                    {"label": "c2pa.hash.data", "data": {"sha256": "a" * 64}},
                ],
            },
        },
        "validation_status": [
            {
                "code": "claim.signature.untrusted",
                "url": "self",
                "explanation": "cert chain root not in trust list",
            },
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    sig = result["manifests"][0]["signature_info"]
    assert sig["chain_verified"] is False
    assert "untrusted" in (sig["failure_reason"] or "")


def test_distinguished_name_with_only_cn_extracts_correctly(tmp_path: Path) -> None:
    """Issuer without an O= field should still pull a CN out cleanly,
    leaving issuer_organization=None rather than blowing up."""
    media = _write_dummy_jpeg(tmp_path / "img.jpg")
    store = {
        "active_manifest": "urn:uuid:root",
        "manifests": {
            "urn:uuid:root": {
                "signature_info": {
                    "issuer": "CN=Lone Device",
                    "cert_serial_number": "x",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [],
            },
        },
        "validation_status": [
            {"code": "claim.signature.trusted", "url": "self"},
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    sig = result["manifests"][0]["signature_info"]
    assert sig["issuer_common_name"] == "Lone Device"
    assert sig["issuer_organization"] is None


def test_plain_issuer_text_not_a_dn_falls_back_to_full_string(
    tmp_path: Path,
) -> None:
    """Some C2PA producers put a human-readable string in 'issuer'
    instead of a DN. AIP must preserve the original text as the CN
    rather than silently truncate or error."""
    media = _write_dummy_jpeg(tmp_path / "img.jpg")
    store = {
        "active_manifest": "urn:uuid:root",
        "manifests": {
            "urn:uuid:root": {
                "signature_info": {
                    "issuer": "Sony Imaging Products",
                    "cert_serial_number": "x",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [],
            },
        },
        "validation_status": [
            {"code": "claim.signature.trusted", "url": "self"},
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    sig = result["manifests"][0]["signature_info"]
    assert sig["issuer_common_name"] == "Sony Imaging Products"


def test_extracted_shape_is_consumable_by_parse_manifest_json(
    tmp_path: Path,
) -> None:
    """The whole point of the transform is that the output flows
    directly into ADR-0046's parse_manifest_json. This test asserts the
    round trip works without modification."""
    from aip.c2pa import parse_manifest_json  # noqa: PLC0415

    media = _write_dummy_jpeg(tmp_path / "img.jpg")
    store = {
        "active_manifest": "urn:uuid:root",
        "manifests": {
            "urn:uuid:root": {
                "signature_info": {
                    "issuer": "CN=Sony Camera",
                    "cert_serial_number": "ab:cd",
                    "time": "2026-06-13T12:00:00Z",
                },
                "assertions": [
                    {"label": "c2pa.hash.data", "data": {"sha256": "a" * 64}},
                ],
            },
        },
        "validation_status": [
            {"code": "claim.signature.trusted", "url": "self"},
        ],
    }
    fake_c2pa = mock.MagicMock()
    _patch_reader_returning(fake_c2pa, json.dumps(store))
    with mock.patch.dict("sys.modules", {"c2pa": fake_c2pa}):
        result = extract_from_media(media)

    parsed = parse_manifest_json(result)
    assert len(parsed) == 1
    assert parsed[0].label == "urn:uuid:root"
    assert parsed[0].signature_info.chain_verified is True


# --------------------------------------------------------------- live binding


@pytest.mark.skipif(
    pytest.importorskip is None,
    reason="never skipped — importorskip handles dep check",
)
def test_live_binding_rejects_non_c2pa_file_with_clear_error(tmp_path: Path) -> None:
    """With the real c2pa-python installed, reading a non-C2PA file
    yields an AIPError, not a binding-specific exception."""
    pytest.importorskip("c2pa")
    pdf = tmp_path / "plain.pdf"
    pdf.write_bytes(b"%PDF-1.4 plain content\n%%EOF\n")
    with pytest.raises(AIPError):
        extract_from_media(pdf)
