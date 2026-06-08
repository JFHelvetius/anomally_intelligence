"""Tests unitarios de ``aip.audit.log``."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from aip.audit import log

UTC = dt.UTC


def _clock(*timestamps: dt.datetime) -> Iterator[dt.datetime]:
    """Cola de timestamps para inyectar como reloj inmutable."""
    return iter(timestamps)


def _wrap_clock(*timestamps: dt.datetime):
    seq = iter(timestamps)
    return lambda: next(seq)


# ---------------------------------------------------------------- enums


def test_action_kind_complete_set() -> None:
    """Pinea las 8 acciones registrables (ADR-0019 §enmienda E1).

    Los valores string son estables forever — modificarlos invalidaría
    cadenas históricas. Añadir un nuevo valor es seguro; renombrar /
    eliminar uno existente NO lo es.
    """
    assert {a.value for a in log.ActionKind} == {
        # Capa base (V1 original).
        "archive_bootstrap",
        "ingest_evidence",
        # Capa derivada (ADR-0019 §enmienda E1, 2026-06-07).
        "assess_authentication",
        "build_workspace",
        "build_timeline",
        "build_snapshot",
        "build_justification",
        "sign_attestation",
    }


def test_result_kind_v1_values() -> None:
    assert {r.value for r in log.ResultKind} == {"success", "failure"}


# ---------------------------------------------------------------- AuditEntry


def _make_entry(**overrides: object) -> log.AuditEntry:
    base = {
        "seq": 0,
        "prev_hash": log.ZERO_HASH,
        "timestamp": dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC),
        "actor": "@jfhelvetius",
        "action": log.ActionKind.ARCHIVE_BOOTSTRAP,
        "target": log.BOOTSTRAP_TARGET,
        "parameters": {},
        "result": log.ResultKind.SUCCESS,
        "schema_version": "0.1.0",
        "entry_hash": "a" * 64,
    }
    base.update(overrides)
    return log.AuditEntry(**base)  # type: ignore[arg-type]


def test_audit_entry_constructs() -> None:
    e = _make_entry()
    assert e.seq == 0
    assert e.action == log.ActionKind.ARCHIVE_BOOTSTRAP


def test_audit_entry_is_frozen() -> None:
    e = _make_entry()
    with pytest.raises(ValidationError):
        e.seq = 1  # type: ignore[misc]


def test_audit_entry_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _make_entry(timestamp=dt.datetime(2026, 6, 4, 0, 0, 0))


def test_audit_entry_rejects_subsecond_timestamp() -> None:
    with pytest.raises(ValidationError, match="microsecond"):
        _make_entry(timestamp=dt.datetime(2026, 6, 4, 0, 0, 0, 500, tzinfo=UTC))


def test_audit_entry_rejects_bad_prev_hash() -> None:
    with pytest.raises(ValidationError):
        _make_entry(prev_hash="abc")


def test_audit_entry_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _make_entry(extra="x")


# ---------------------------------------------------------------- compute_entry_hash


def test_compute_entry_hash_is_deterministic() -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    h1 = log.compute_entry_hash(
        seq=0,
        prev_hash=log.ZERO_HASH,
        timestamp=ts,
        actor="@jfhelvetius",
        action=log.ActionKind.ARCHIVE_BOOTSTRAP,
        target=log.BOOTSTRAP_TARGET,
        parameters={},
        result=log.ResultKind.SUCCESS,
        schema_version="0.1.0",
    )
    h2 = log.compute_entry_hash(
        seq=0,
        prev_hash=log.ZERO_HASH,
        timestamp=ts,
        actor="@jfhelvetius",
        action=log.ActionKind.ARCHIVE_BOOTSTRAP,
        target=log.BOOTSTRAP_TARGET,
        parameters={},
        result=log.ResultKind.SUCCESS,
        schema_version="0.1.0",
    )
    assert h1 == h2


def test_compute_entry_hash_changes_with_seq() -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    args = dict(
        prev_hash=log.ZERO_HASH,
        timestamp=ts,
        actor="@x",
        action=log.ActionKind.ARCHIVE_BOOTSTRAP,
        target=log.BOOTSTRAP_TARGET,
        parameters={},
        result=log.ResultKind.SUCCESS,
        schema_version="0.1.0",
    )
    h0 = log.compute_entry_hash(seq=0, **args)  # type: ignore[arg-type]
    h1 = log.compute_entry_hash(seq=1, **args)  # type: ignore[arg-type]
    assert h0 != h1


# ---------------------------------------------------------------- bootstrap


def test_bootstrap_writes_first_entry_on_empty_archive(archive_root: Path) -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    entry = log.bootstrap(
        archive_root,
        actor="@jfhelvetius",
        clock=_wrap_clock(ts),
        schema_version="0.1.0",
    )
    assert entry is not None
    assert entry.seq == 0
    assert entry.prev_hash == log.ZERO_HASH
    assert entry.action == log.ActionKind.ARCHIVE_BOOTSTRAP


def test_bootstrap_is_idempotent(archive_root: Path) -> None:
    ts1 = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    ts2 = dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)
    log.bootstrap(
        archive_root,
        actor="@jfhelvetius",
        clock=_wrap_clock(ts1),
        schema_version="0.1.0",
    )
    # Second call must NOT add an entry.
    second = log.bootstrap(
        archive_root,
        actor="@jfhelvetius",
        clock=_wrap_clock(ts2),
        schema_version="0.1.0",
    )
    assert second is None
    assert log.count_entries(archive_root) == 1


# ---------------------------------------------------------------- append_entry


def test_append_entry_chains_prev_hash(archive_root: Path) -> None:
    ts1 = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    ts2 = dt.datetime(2026, 6, 4, 0, 1, 0, tzinfo=UTC)

    boot = log.bootstrap(
        archive_root,
        actor="@jfhelvetius",
        clock=_wrap_clock(ts1),
        schema_version="0.1.0",
    )
    assert boot is not None

    second = log.append_entry(
        archive_root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target=f"aip:evidence/sha256:{'1' * 64}",
        actor="@jfhelvetius",
        parameters={"size_bytes": "356721"},
        result=log.ResultKind.SUCCESS,
        schema_version="0.1.0",
        clock=_wrap_clock(ts2),
    )
    assert second.seq == 1
    assert second.prev_hash == boot.entry_hash


def test_append_entry_strips_microseconds(archive_root: Path) -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, 999999, tzinfo=UTC)
    entry = log.bootstrap(
        archive_root,
        actor="@x",
        clock=_wrap_clock(ts),
        schema_version="0.1.0",
    )
    assert entry is not None
    assert entry.timestamp.microsecond == 0


def test_append_entry_rejects_naive_clock(archive_root: Path) -> None:
    def naive_clock() -> dt.datetime:
        # Intencionalmente naive: el test verifica que el validador la rechaza.
        return dt.datetime(2026, 6, 4, 0, 0, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        log.append_entry(
            archive_root,
            action=log.ActionKind.INGEST_EVIDENCE,
            target="aip:evidence/sha256:" + "0" * 64,
            actor="@x",
            schema_version="0.1.0",
            clock=naive_clock,
        )


def test_append_entry_converts_non_utc_to_utc(archive_root: Path) -> None:
    # Reloj que entrega un timestamp con offset +05:00; debe almacenarse en UTC.
    plus5 = dt.timezone(dt.timedelta(hours=5))
    ts_plus5 = dt.datetime(2026, 6, 4, 5, 0, 0, tzinfo=plus5)
    entry = log.bootstrap(
        archive_root,
        actor="@x",
        clock=_wrap_clock(ts_plus5),
        schema_version="0.1.0",
    )
    assert entry is not None
    # 05:00+05:00 → 00:00 UTC.
    expected_utc = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    assert entry.timestamp == expected_utc


# ---------------------------------------------------------------- iter & count


def test_iter_entries_on_empty_archive(archive_root: Path) -> None:
    assert list(log.iter_entries(archive_root)) == []
    assert log.count_entries(archive_root) == 0
    assert log.last_entry(archive_root) is None


def test_iter_entries_in_order(archive_root: Path) -> None:
    times = [
        dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC),
        dt.datetime(2026, 6, 4, 0, 1, 0, tzinfo=UTC),
        dt.datetime(2026, 6, 4, 0, 2, 0, tzinfo=UTC),
    ]
    log.bootstrap(
        archive_root,
        actor="@x",
        clock=_wrap_clock(times[0]),
        schema_version="0.1.0",
    )
    log.append_entry(
        archive_root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target="aip:evidence/sha256:" + "a" * 64,
        actor="@x",
        schema_version="0.1.0",
        clock=_wrap_clock(times[1]),
    )
    log.append_entry(
        archive_root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target="aip:evidence/sha256:" + "b" * 64,
        actor="@x",
        schema_version="0.1.0",
        clock=_wrap_clock(times[2]),
    )
    entries = list(log.iter_entries(archive_root))
    assert [e.seq for e in entries] == [0, 1, 2]
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[2].prev_hash == entries[1].entry_hash


# ---------------------------------------------------------------- physical format


def test_log_file_is_jsonl(archive_root: Path) -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    log.bootstrap(
        archive_root,
        actor="@x",
        clock=_wrap_clock(ts),
        schema_version="0.1.0",
    )
    log_path = archive_root / "audit.log"
    text = log_path.read_text(encoding="utf-8")
    lines = [line for line in text.split("\n") if line]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["seq"] == 0
    assert parsed["timestamp"] == "2026-06-04T00:00:00Z"
    assert parsed["target"] == log.BOOTSTRAP_TARGET
