"""Tests for the C2PA capture attestation verifier (ADR-0046).

The verifier accepts an operator-supplied JSON manifest chain and reports
honestly on three things: parse integrity, chain linkage, and binding to
the declared evidence. Each failure path gets its own ``failure_reason``
string — the receptor reads it directly in the report HTML, so the
phrasing is load-bearing.

Tests intentionally do NOT exercise X.509 signature verification: v1
trusts the operator-supplied ``chain_verified`` boolean inside
``signature_info``. ADR-0047 (deferred) covers in-process X.509 checks.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from aip.c2pa import (
    C2PA_REPORT_TYPE,
    DEFAULT_TRUST_LIST_NAME,
    parse_manifest_json,
    persist_report,
    verify_manifest_chain,
)
from aip.c2pa.verifier import C2PA_ATTESTATIONS_DIRNAME
from aip.errors import AIPError

EVIDENCE_HASH = "a" * 64
FROZEN_NOW = dt.datetime(2026, 6, 11, 12, 0, 0, tzinfo=dt.UTC)


# --------------------------------------------------------------- fixtures


def _root_manifest(
    label: str = "camera-001",
    *,
    binding_sha: str = EVIDENCE_HASH,
    chain_verified: bool = True,
    failure_reason: str | None = None,
    issuer_cn: str = "Sony Alpha 1 Camera",
    issuer_org: str = "Sony Imaging Products & Solutions Inc.",
) -> dict[str, object]:
    return {
        "label": label,
        "parent_manifest_label": None,
        "signature_info": {
            "issuer_common_name": issuer_cn,
            "issuer_organization": issuer_org,
            "cert_serial": "ab:cd:ef:01",
            "not_before": "2025-01-01T00:00:00Z",
            "not_after": "2030-01-01T00:00:00Z",
            "chain_verified_against": "c2pa-default-trust-list-v1",
            "chain_verified": chain_verified,
            "failure_reason": failure_reason,
        },
        "assertions": [
            {"label": "c2pa.hash.data", "data": {"sha256": binding_sha}},
            {"label": "stds.exif", "data": {"camera": "Alpha 1"}},
        ],
    }


def _editor_manifest(
    label: str = "photoshop-edit-001",
    parent: str = "camera-001",
    *,
    binding_sha: str = EVIDENCE_HASH,
) -> dict[str, object]:
    return {
        "label": label,
        "parent_manifest_label": parent,
        "signature_info": {
            "issuer_common_name": "Adobe Photoshop 25.4",
            "issuer_organization": "Adobe Inc.",
            "cert_serial": "11:22:33:44",
            "not_before": "2025-01-01T00:00:00Z",
            "not_after": "2030-01-01T00:00:00Z",
            "chain_verified_against": "c2pa-default-trust-list-v1",
            "chain_verified": True,
            "failure_reason": None,
        },
        "assertions": [
            {"label": "c2pa.hash.data", "data": {"sha256": binding_sha}},
            {"label": "c2pa.actions", "data": {"edits": "crop, color-balance"}},
        ],
    }


# --------------------------------------------------------------- parse


def test_parse_rejects_missing_manifests_field() -> None:
    with pytest.raises(AIPError, match="non-empty 'manifests'"):
        parse_manifest_json({"foo": "bar"})


def test_parse_rejects_empty_manifests_list() -> None:
    with pytest.raises(AIPError, match="non-empty 'manifests'"):
        parse_manifest_json({"manifests": []})


def test_parse_rejects_manifest_without_label() -> None:
    payload = {"manifests": [{"signature_info": {}, "assertions": []}]}
    with pytest.raises(AIPError, match="missing non-empty 'label'"):
        parse_manifest_json(payload)


def test_parse_rejects_signature_with_non_boolean_chain_verified() -> None:
    bad = _root_manifest()
    bad["signature_info"]["chain_verified"] = "yes"  # type: ignore[index]
    with pytest.raises(AIPError, match="chain_verified must be a boolean"):
        parse_manifest_json({"manifests": [bad]})


def test_parse_round_trips_simple_camera_manifest() -> None:
    manifests = parse_manifest_json({"manifests": [_root_manifest()]})
    assert len(manifests) == 1
    m = manifests[0]
    assert m.label == "camera-001"
    assert m.parent_manifest_label is None
    assert m.signature_info.issuer_organization == (
        "Sony Imaging Products & Solutions Inc."
    )
    assert any(a.label == "c2pa.hash.data" for a in m.assertions)


def test_parse_round_trips_camera_plus_editor_chain() -> None:
    manifests = parse_manifest_json(
        {"manifests": [_root_manifest(), _editor_manifest()]}
    )
    assert [m.label for m in manifests] == ["camera-001", "photoshop-edit-001"]
    assert manifests[1].parent_manifest_label == "camera-001"


# --------------------------------------------------------------- verify (happy)


def test_verify_single_camera_manifest_binds_to_evidence() -> None:
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is True
    assert report.failure_reason is None
    assert report.evidence_sha256 == EVIDENCE_HASH
    assert report.trust_list_name == DEFAULT_TRUST_LIST_NAME
    assert report.verified_at == "2026-06-11T12:00:00Z"
    assert report.report_type == C2PA_REPORT_TYPE
    assert report.report_hash and len(report.report_hash) == 64


def test_verify_two_link_chain_uses_leaf_for_hash_binding() -> None:
    """Leaf manifest carries the binding to the FINAL file bytes; the
    root manifest's binding is to the ORIGINAL camera bytes before
    editing. The verifier must check the leaf, not the root."""
    chain = parse_manifest_json(
        {"manifests": [_root_manifest(binding_sha="b" * 64), _editor_manifest()]}
    )
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is True


# --------------------------------------------------------------- verify (fail)


def test_verify_rejects_evidence_hash_with_wrong_length() -> None:
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    with pytest.raises(AIPError, match="64 lowercase hex"):
        verify_manifest_chain(chain, evidence_sha256="short")


def test_verify_rejects_evidence_hash_with_non_hex_chars() -> None:
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    with pytest.raises(AIPError, match="64 lowercase hex"):
        verify_manifest_chain(chain, evidence_sha256="z" * 64)


def test_verify_rejects_empty_chain() -> None:
    with pytest.raises(AIPError, match="empty manifest chain"):
        verify_manifest_chain((), evidence_sha256=EVIDENCE_HASH)


def test_verify_detects_unverified_signature() -> None:
    bad_root = _root_manifest(
        chain_verified=False,
        failure_reason="leaf certificate expired 2020-01-01",
    )
    chain = parse_manifest_json({"manifests": [bad_root]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "signature did not verify" in (report.failure_reason or "")
    assert "leaf certificate expired" in (report.failure_reason or "")


def test_verify_detects_hash_mismatch() -> None:
    chain = parse_manifest_json(
        {"manifests": [_root_manifest(binding_sha="b" * 64)]}
    )
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "does not match" in (report.failure_reason or "")


def test_verify_detects_missing_hash_assertion() -> None:
    """A camera manifest without c2pa.hash.data cannot bind to evidence —
    the receptor needs an explicit failure reason rather than silent OK."""
    no_hash = _root_manifest()
    no_hash["assertions"] = [
        {"label": "stds.exif", "data": {"camera": "Alpha 1"}}
    ]
    chain = parse_manifest_json({"manifests": [no_hash]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "no c2pa.hash.data" in (report.failure_reason or "")


def test_verify_detects_orphan_parent_reference() -> None:
    orphan = _editor_manifest(parent="ghost-manifest")
    chain = parse_manifest_json({"manifests": [_root_manifest(), orphan]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "unknown parent" in (report.failure_reason or "")


def test_verify_detects_multiple_roots() -> None:
    """V1 handles linear chains only. Two parent=null manifests means
    either two independent assets bundled wrongly, or a tampered chain."""
    a = _root_manifest(label="cam-a")
    b = _root_manifest(label="cam-b")
    chain = parse_manifest_json({"manifests": [a, b]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "exactly one root" in (report.failure_reason or "")


def test_verify_detects_duplicate_labels() -> None:
    a = _root_manifest(label="dup")
    # Duplicate of `a`'s label, but with a parent so the multi-root check
    # doesn't fire first.
    b = _editor_manifest(label="dup", parent="dup")
    chain = parse_manifest_json({"manifests": [a, b]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "duplicate manifest labels" in (report.failure_reason or "")


def test_verify_detects_multiple_leaves() -> None:
    """A C2PA chain forks if two editors based off the same camera both
    have no children — undefined which version is the final bytes."""
    root = _root_manifest()
    edit1 = _editor_manifest(label="edit-a", parent="camera-001")
    edit2 = _editor_manifest(label="edit-b", parent="camera-001")
    chain = parse_manifest_json({"manifests": [root, edit1, edit2]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert report.chain_verified is False
    assert "exactly one leaf" in (report.failure_reason or "")


# --------------------------------------------------------------- persistence


def test_persist_writes_sorted_indented_json_at_canonical_path(
    archive_root: Path,
) -> None:
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    report = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    persist_report(archive_root, report)

    target = archive_root / C2PA_ATTESTATIONS_DIRNAME / f"{EVIDENCE_HASH}.json"
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    # Sorted: chain_verified < evidence_sha256 < failure_reason < manifests…
    assert text.index('"chain_verified"') < text.index('"evidence_sha256"')
    assert text.index('"evidence_sha256"') < text.index('"manifests"')
    # Indented, not minified.
    assert "\n  " in text


def test_persist_overwrites_previous_report_for_same_evidence(
    archive_root: Path,
) -> None:
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    r1 = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    persist_report(archive_root, r1)

    later = FROZEN_NOW + dt.timedelta(hours=1)
    r2 = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=later
    )
    persist_report(archive_root, r2)

    target = archive_root / C2PA_ATTESTATIONS_DIRNAME / f"{EVIDENCE_HASH}.json"
    persisted = json.loads(target.read_text(encoding="utf-8"))
    assert persisted["verified_at"] == "2026-06-11T13:00:00Z"


# --------------------------------------------------------------- contract


def test_report_hash_is_stable_for_identical_inputs() -> None:
    """The report hash must be deterministic so two operators verifying
    the same manifest under the same trust list compute the same hash."""
    chain = parse_manifest_json({"manifests": [_root_manifest()]})
    r1 = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    r2 = verify_manifest_chain(
        chain, evidence_sha256=EVIDENCE_HASH, now=FROZEN_NOW
    )
    assert r1.report_hash == r2.report_hash
