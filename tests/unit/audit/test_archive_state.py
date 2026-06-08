"""Tests del Archive State Snapshot (ADR-0042).

Verifica las garantías estructurales:

- G_42_a — modelo inmutable + regex validators (sha256 hex, ISO UTC).
- G_42_b — ``compute_archive_snapshot`` determinista respecto a
  ``(estado del archive, generated_at)``.
- G_42_c — ``snapshot_hash`` cambia cuando cambian (a) ``manifest_hash``,
  (b) ``audit_log_head_hash``, (c) ``audit_log_total_entries``, o (d)
  ``generated_at``.
- G_42_d — read-only: ``compute_archive_snapshot`` no muta el archive.
- G_42_e — encode/decode roundtrip bit-a-bit.
- G_42_f — integración con ADR-0041: ``archive_snapshot`` es firmable y
  la firma se invalida ante tampering de cualquier dimensión.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.attestation import (
    ALLOWED_ARTIFACT_KINDS,
    generate_keypair,
    sign_artifact,
    verify_attestation,
)
from aip.audit import (
    ARCHIVE_SNAPSHOT_SCHEMA_VERSION,
    ArchiveSnapshot,
    compute_archive_snapshot,
    compute_snapshot_hash,
    decode_archive_snapshot,
    encode_archive_snapshot,
    verify_archive_snapshot_hash,
)
from aip.audit.log import ZERO_HASH, ActionKind, ResultKind, append_entry
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind

UTC = dt.UTC
T0 = dt.datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 6, 7, 13, 0, 0, tzinfo=UTC)

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_TS_OK = "2026-06-07T12:00:00Z"


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _seed_archive(tmp_path: Path, archive_root: Path) -> str:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample bytes")
    arc = Archive.open(archive_root)
    ev = arc.ingest_evidence(
        blob,
        source_id="nara",
        source_name="NARA",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@op",
        clock=_clock(T0),
    )
    return ev.hash


def _valid_snapshot(**overrides: object) -> ArchiveSnapshot:
    base = {
        "manifest_hash": _HASH_A,
        "audit_log_head_hash": _HASH_B,
        "audit_log_total_entries": 2,
        "generated_at": _TS_OK,
        "snapshot_hash": "c" * 64,
    }
    base.update(overrides)
    return ArchiveSnapshot(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- G_42_a (model)


def test_schema_version_pinned() -> None:
    assert ARCHIVE_SNAPSHOT_SCHEMA_VERSION == "1"


def test_archive_snapshot_default_schema_version() -> None:
    snap = _valid_snapshot()
    assert snap.schema_version == "1"


def test_archive_snapshot_is_frozen() -> None:
    snap = _valid_snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.snapshot_hash = "d" * 64  # type: ignore[misc]


def test_rejects_non_sha256_manifest_hash() -> None:
    with pytest.raises(ValueError, match="manifest_hash"):
        _valid_snapshot(manifest_hash="not-hex")
    with pytest.raises(ValueError, match="manifest_hash"):
        _valid_snapshot(manifest_hash="A" * 64)  # uppercase rejected


def test_rejects_non_sha256_head_hash() -> None:
    with pytest.raises(ValueError, match="audit_log_head_hash"):
        _valid_snapshot(audit_log_head_hash="g" * 64)


def test_accepts_zero_hash_head_for_empty_log() -> None:
    snap = _valid_snapshot(audit_log_head_hash=ZERO_HASH, audit_log_total_entries=0)
    assert snap.audit_log_head_hash == ZERO_HASH


def test_rejects_negative_total_entries() -> None:
    with pytest.raises(ValueError, match="audit_log_total_entries"):
        _valid_snapshot(audit_log_total_entries=-1)


def test_rejects_non_iso_utc_generated_at() -> None:
    with pytest.raises(ValueError, match="generated_at"):
        _valid_snapshot(generated_at="2026-06-07T12:00:00+00:00")
    with pytest.raises(ValueError, match="generated_at"):
        _valid_snapshot(generated_at="2026-06-07 12:00:00Z")


def test_rejects_non_sha256_snapshot_hash() -> None:
    with pytest.raises(ValueError, match="snapshot_hash"):
        _valid_snapshot(snapshot_hash="z" * 64)


# ---------------------------------------------------------------- G_42_b (compute determinism)


def test_compute_snapshot_hash_is_jcs_self_hash() -> None:
    """``compute_snapshot_hash`` produce JCS exclude-self sobre todos
    los campos load-bearing. Determinismo verificable independientemente."""
    snap = _valid_snapshot(snapshot_hash="0" * 64)
    h = compute_snapshot_hash(snap)
    # Recomputarlo manualmente con dict exclude-self.
    canonical_obj = {
        "audit_log_head_hash": _HASH_B,
        "audit_log_total_entries": 2,
        "generated_at": _TS_OK,
        "manifest_hash": _HASH_A,
        "schema_version": "1",
    }
    canonical_bytes = json.dumps(
        canonical_obj, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected = hashlib.sha256(canonical_bytes).hexdigest()
    assert h == expected


def test_compute_archive_snapshot_deterministic(
    tmp_path: Path, archive_root: Path
) -> None:
    """Mismo archive + mismo generated_at ⇒ mismo snapshot_hash."""
    _seed_archive(tmp_path, archive_root)
    snap1 = compute_archive_snapshot(archive_root, generated_at=T1)
    snap2 = compute_archive_snapshot(archive_root, generated_at=T1)
    assert snap1 == snap2
    assert snap1.snapshot_hash == snap2.snapshot_hash


def test_compute_strips_microseconds(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    when = dt.datetime(2026, 6, 7, 13, 0, 0, 999999, tzinfo=UTC)
    snap = compute_archive_snapshot(archive_root, generated_at=when)
    assert snap.generated_at == "2026-06-07T13:00:00Z"


def test_compute_requires_tz_aware_generated_at(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_archive_snapshot(
            archive_root, generated_at=dt.datetime(2026, 6, 7)
        )


def test_compute_requires_manifest(tmp_path: Path) -> None:
    """Sin manifest no se puede snapshot — devuelve FileNotFoundError."""
    empty_archive = tmp_path / "empty"
    empty_archive.mkdir()
    with pytest.raises(FileNotFoundError, match="manifest"):
        compute_archive_snapshot(empty_archive, generated_at=T1)


# ---------------------------------------------------------------- G_42_c (sensitivity)


def test_snapshot_hash_changes_when_audit_log_grows(
    tmp_path: Path, archive_root: Path
) -> None:
    """Añadir una entry al audit log cambia head_hash + total → snapshot_hash."""
    _seed_archive(tmp_path, archive_root)
    snap_before = compute_archive_snapshot(archive_root, generated_at=T1)
    append_entry(
        archive_root,
        action=ActionKind.BUILD_WORKSPACE,
        target="aip:workspace/w-x",
        actor="@op",
        parameters={"self_hash": _HASH_A},
        result=ResultKind.SUCCESS,
        schema_version="0.1.0",
        clock=_clock(T1),
    )
    snap_after = compute_archive_snapshot(archive_root, generated_at=T1)
    assert snap_after.audit_log_head_hash != snap_before.audit_log_head_hash
    assert (
        snap_after.audit_log_total_entries
        == snap_before.audit_log_total_entries + 1
    )
    assert snap_after.snapshot_hash != snap_before.snapshot_hash


def test_snapshot_hash_changes_when_generated_at_changes(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    snap_t0 = compute_archive_snapshot(archive_root, generated_at=T0)
    snap_t1 = compute_archive_snapshot(archive_root, generated_at=T1)
    assert snap_t0.snapshot_hash != snap_t1.snapshot_hash
    # Pero los otros campos son idénticos: archive no cambió.
    assert snap_t0.manifest_hash == snap_t1.manifest_hash
    assert snap_t0.audit_log_head_hash == snap_t1.audit_log_head_hash
    assert (
        snap_t0.audit_log_total_entries == snap_t1.audit_log_total_entries
    )


def test_snapshot_boundary_with_chain_tampering(
    tmp_path: Path, archive_root: Path
) -> None:
    """Boundary explícito de ``compute_archive_snapshot``: lee el
    ``entry_hash`` declarado en la última entry tal cual; no recomputa.

    Tampering del **payload** de una entry (cambiar ``actor`` pero
    dejar ``entry_hash`` intacto en el JSONL) **no** cambia el
    ``audit_log_head_hash`` que devuelve compute. Esa detección
    es responsabilidad de :func:`aip.audit.verify.verify_chain`, que
    recomputa el hash y compara — esa capa ya existe y se encadena con
    el snapshot via ``Archive.verify`` (audit_chain check) antes del
    sign para que la firma sólo se emita sobre un archive cuya cadena
    está sana.

    Tampering del ``entry_hash`` mismo en la entry sí cambia
    ``audit_log_head_hash`` → snapshot_hash. Eso lo cubrimos aquí.
    """
    _seed_archive(tmp_path, archive_root)
    snap_before = compute_archive_snapshot(archive_root, generated_at=T1)

    # Tampering del ``entry_hash`` declarado en la última entry.
    log_path = archive_root / "audit.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    last_obj = json.loads(lines[-1])
    last_obj["entry_hash"] = "f" * 64
    lines[-1] = json.dumps(last_obj, ensure_ascii=False)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    snap_after = compute_archive_snapshot(archive_root, generated_at=T1)
    assert snap_after.audit_log_head_hash == "f" * 64
    assert snap_after.audit_log_head_hash != snap_before.audit_log_head_hash
    assert snap_after.snapshot_hash != snap_before.snapshot_hash


# ---------------------------------------------------------------- G_42_d (read-only)


def test_compute_is_read_only_archive_bit_identical(
    tmp_path: Path, archive_root: Path
) -> None:
    """Computar un snapshot no muta NINGÚN byte del archive."""
    _seed_archive(tmp_path, archive_root)

    def fingerprint() -> dict[str, bytes]:
        fp: dict[str, bytes] = {}
        for p in sorted(archive_root.rglob("*")):
            if p.is_file():
                fp[str(p.relative_to(archive_root))] = p.read_bytes()
        return fp

    before = fingerprint()
    compute_archive_snapshot(archive_root, generated_at=T1)
    after = fingerprint()
    assert before == after, (
        "compute_archive_snapshot must not mutate the archive."
    )


# ---------------------------------------------------------------- G_42_e (encode/decode)


def test_encode_decode_roundtrip(tmp_path: Path, archive_root: Path) -> None:
    _seed_archive(tmp_path, archive_root)
    snap = compute_archive_snapshot(archive_root, generated_at=T1)
    payload = encode_archive_snapshot(snap)
    decoded = decode_archive_snapshot(payload)
    assert decoded == snap


def test_encoded_json_is_canonical_sorted(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    snap = compute_archive_snapshot(archive_root, generated_at=T1)
    payload = encode_archive_snapshot(snap)
    parsed = json.loads(payload)
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert payload.endswith("\n")


def test_verify_self_hash_consistency(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    snap = compute_archive_snapshot(archive_root, generated_at=T1)
    assert verify_archive_snapshot_hash(snap) is True


def test_verify_detects_tampered_snapshot_hash(
    tmp_path: Path, archive_root: Path
) -> None:
    _seed_archive(tmp_path, archive_root)
    snap = compute_archive_snapshot(archive_root, generated_at=T1)
    tampered = dataclasses.replace(snap, snapshot_hash="d" * 64)
    assert verify_archive_snapshot_hash(tampered) is False


# ---------------------------------------------------------------- G_42_f (ADR-0041 integration)


def test_archive_snapshot_is_in_allowed_artifact_kinds() -> None:
    """ADR-0042 amplía la taxonomía de ADR-0041 con un séptimo kind."""
    assert "archive_snapshot" in ALLOWED_ARTIFACT_KINDS


def test_archive_snapshot_is_signable_via_attestation_engine(
    tmp_path: Path, archive_root: Path
) -> None:
    """Pipeline integrado: snapshot → sign → verify pasa para clean archive."""
    _seed_archive(tmp_path, archive_root)
    snap = compute_archive_snapshot(archive_root, generated_at=T1)
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(encode_archive_snapshot(snap), encoding="utf-8")

    priv, pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="archive_snapshot",
        artifact_path=snap_path,
        private_key=priv,
        signer_id="@op",
        signed_at=T1,
    )
    assert verify_attestation(att, public_key=pub) is True
    # La firma se ancla al snapshot_hash del snapshot — el artifact_hash
    # de la atestación es exactamente snapshot.snapshot_hash.
    assert att.artifact_hash == snap.snapshot_hash


def test_attestation_invalidates_when_archive_state_changes(
    tmp_path: Path, archive_root: Path
) -> None:
    """Tras firmar un snapshot, mutar el archive (nueva entry) produce un
    snapshot distinto cuya firma ya no es válida bajo la atestación
    original. Cierra el hueco "reescritura silenciosa de historia"."""
    _seed_archive(tmp_path, archive_root)
    snap_before = compute_archive_snapshot(archive_root, generated_at=T1)
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(
        encode_archive_snapshot(snap_before), encoding="utf-8"
    )

    priv, _pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="archive_snapshot",
        artifact_path=snap_path,
        private_key=priv,
        signer_id="@op",
        signed_at=T1,
    )

    # Mutar el archive — añadir una entry al log.
    append_entry(
        archive_root,
        action=ActionKind.BUILD_WORKSPACE,
        target="aip:workspace/w-x",
        actor="@op",
        parameters={"self_hash": _HASH_A},
        result=ResultKind.SUCCESS,
        schema_version="0.1.0",
        clock=_clock(T1),
    )
    snap_after = compute_archive_snapshot(archive_root, generated_at=T1)
    assert snap_after.snapshot_hash != snap_before.snapshot_hash
    # La atestación sigue firmando snap_before.snapshot_hash; no podría
    # firmar snap_after.snapshot_hash sin re-firmar.
    assert att.artifact_hash == snap_before.snapshot_hash
    assert att.artifact_hash != snap_after.snapshot_hash
