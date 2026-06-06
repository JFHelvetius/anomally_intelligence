"""Tests unitarios de ``aip.audit.verify``."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from aip.audit import log, verify

UTC = dt.UTC


def _clock_factory(*timestamps: dt.datetime):
    it = iter(timestamps)
    return lambda: next(it)


def _seed_chain(root: Path) -> list[log.AuditEntry]:
    """Construye un audit log con tres entradas válidas y devuelve la lista."""
    times = [
        dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC),
        dt.datetime(2026, 6, 4, 0, 1, 0, tzinfo=UTC),
        dt.datetime(2026, 6, 4, 0, 2, 0, tzinfo=UTC),
    ]
    boot = log.bootstrap(
        root,
        actor="@x",
        clock=_clock_factory(times[0]),
        schema_version="0.1.0",
    )
    assert boot is not None
    e1 = log.append_entry(
        root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target="aip:evidence/sha256:" + "a" * 64,
        actor="@x",
        schema_version="0.1.0",
        clock=_clock_factory(times[1]),
    )
    e2 = log.append_entry(
        root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target="aip:evidence/sha256:" + "b" * 64,
        actor="@x",
        schema_version="0.1.0",
        clock=_clock_factory(times[2]),
    )
    return [boot, e1, e2]


# ---------------------------------------------------------------- cadena válida


def test_verify_empty_log_is_ok(archive_root: Path) -> None:
    result = verify.verify_chain(archive_root)
    assert result.ok is True
    assert result.total_entries == 0
    assert result.first_failure_seq is None
    assert result.first_failure_reason is None


def test_verify_single_bootstrap_entry(archive_root: Path) -> None:
    ts = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    log.bootstrap(
        archive_root,
        actor="@x",
        clock=_clock_factory(ts),
        schema_version="0.1.0",
    )
    result = verify.verify_chain(archive_root)
    assert result.ok is True
    assert result.total_entries == 1


def test_verify_three_entry_chain(archive_root: Path) -> None:
    _seed_chain(archive_root)
    result = verify.verify_chain(archive_root)
    assert result.ok is True
    assert result.total_entries == 3


def test_result_truthy_when_ok(archive_root: Path) -> None:
    result = verify.verify_chain(archive_root)
    assert bool(result) is True


# ---------------------------------------------------------------- detecta tampering


def _rewrite_log(root: Path, mutator) -> None:
    """Aplica ``mutator(entries: list[dict]) -> list[dict]`` al fichero."""
    path = root / "audit.log"
    lines = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    new_lines = mutator(lines)
    path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in new_lines) + "\n",
        encoding="utf-8",
    )


def test_verify_detects_tampered_payload(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        # Modificamos `actor` de la segunda entrada SIN actualizar entry_hash.
        entries[1]["actor"] = "@attacker"
        return entries

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    assert result.first_failure_seq == 1
    assert "entry_hash mismatch" in (result.first_failure_reason or "")


def test_verify_detects_tampered_entry_hash(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        entries[1]["entry_hash"] = "f" * 64
        return entries

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    assert result.first_failure_seq == 1
    assert "entry_hash mismatch" in (result.first_failure_reason or "")


def test_verify_detects_broken_prev_hash(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        entries[2]["prev_hash"] = "0" * 64
        return entries

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    assert result.first_failure_seq == 2
    assert "prev_hash mismatch" in (result.first_failure_reason or "")


def test_verify_detects_seq_gap(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        # Saltamos seq=1 directamente a seq=5
        entries[1]["seq"] = 5
        return entries

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    assert result.first_failure_seq == 5  # seq que devuelve la entrada
    assert "seq mismatch" in (result.first_failure_reason or "")


def test_verify_detects_deleted_middle_entry(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        # Borramos la entrada del medio (seq=1).
        return [entries[0], entries[2]]

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    # Al saltar de seq=0 a seq=2, primera causa será seq mismatch.
    assert result.first_failure_seq == 2


def test_verify_counts_total_entries_even_when_failed(archive_root: Path) -> None:
    _seed_chain(archive_root)

    def _tamper(entries):
        entries[1]["actor"] = "@attacker"
        return entries

    _rewrite_log(archive_root, _tamper)
    result = verify.verify_chain(archive_root)
    assert result.ok is False
    assert result.total_entries == 3  # Recorre el log completo aunque falle.
