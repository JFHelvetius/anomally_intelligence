"""Reproducibility tests para la cadena del audit log (ADR-0031 T3).

Pinned values sobre una cadena audit canónica de dos entradas: bootstrap +
una ingest evidence con timestamp y actor fijos. Si los hashes cambian, ha
cambiado:

- la canonicalización JCS,
- el formato de timestamp del audit log,
- el conjunto de campos hasheados, o
- el algoritmo SHA-256.

Cualquiera de los cuatro es bug arquitectónico crítico que requiere PR
explícito justificándolo.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from aip.audit import log, verify

pytestmark = pytest.mark.reproducibility

UTC = dt.UTC

CANONICAL_BOOTSTRAP_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
CANONICAL_INGEST_TS = dt.datetime(2026, 6, 4, 0, 1, 0, tzinfo=UTC)
CANONICAL_ACTOR = "@jfhelvetius"
CANONICAL_SCHEMA_VERSION = "0.1.0"
SAMPLE_EVIDENCE_HASH = "1f4a9c0a" + "0" * 56
CANONICAL_INGEST_PARAMS = {"size_bytes": "356721"}

EXPECTED_BOOTSTRAP_HASH = (
    "041072ccda527e0994ce81ef83fe9212a269cfa3bc7ca5b96982313050123be0"
)
EXPECTED_INGEST_HASH = (
    "506bbd1b04511540898e74af8cf8c8e808708aaf4184bbf2721777000f6b4ff8"
)


def _fixed_clock(ts: dt.datetime):
    return lambda: ts


def test_canonical_audit_chain_hashes_are_pinned(archive_root: Path) -> None:
    boot = log.bootstrap(
        archive_root,
        actor=CANONICAL_ACTOR,
        clock=_fixed_clock(CANONICAL_BOOTSTRAP_TS),
        schema_version=CANONICAL_SCHEMA_VERSION,
    )
    assert boot is not None
    assert boot.entry_hash == EXPECTED_BOOTSTRAP_HASH, (
        "Bootstrap entry_hash drifted. Si el cambio es intencional, "
        "documentar la causa en PR y actualizar todos los manifest hashes "
        "dependientes."
    )

    ingest = log.append_entry(
        archive_root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target=f"aip:evidence/sha256:{SAMPLE_EVIDENCE_HASH}",
        actor=CANONICAL_ACTOR,
        parameters=CANONICAL_INGEST_PARAMS,
        result=log.ResultKind.SUCCESS,
        schema_version=CANONICAL_SCHEMA_VERSION,
        clock=_fixed_clock(CANONICAL_INGEST_TS),
    )
    assert ingest.entry_hash == EXPECTED_INGEST_HASH
    assert ingest.prev_hash == EXPECTED_BOOTSTRAP_HASH


def test_canonical_chain_verifies(archive_root: Path) -> None:
    log.bootstrap(
        archive_root,
        actor=CANONICAL_ACTOR,
        clock=_fixed_clock(CANONICAL_BOOTSTRAP_TS),
        schema_version=CANONICAL_SCHEMA_VERSION,
    )
    log.append_entry(
        archive_root,
        action=log.ActionKind.INGEST_EVIDENCE,
        target=f"aip:evidence/sha256:{SAMPLE_EVIDENCE_HASH}",
        actor=CANONICAL_ACTOR,
        parameters=CANONICAL_INGEST_PARAMS,
        result=log.ResultKind.SUCCESS,
        schema_version=CANONICAL_SCHEMA_VERSION,
        clock=_fixed_clock(CANONICAL_INGEST_TS),
    )

    result = verify.verify_chain(archive_root)
    assert result.ok is True
    assert result.total_entries == 2
