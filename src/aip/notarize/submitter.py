"""Submit y upgrade de OpenTimestamps proofs.

Submit: envía el hash a calendarios públicos OTS, recibe pending attestations
inmediatas. Upgrade: pide a esos calendarios la prueba completa una vez que
el batch quedó confirmado en Bitcoin (latencia típica ~1h).

Los calendarios OTS son operados por terceros independientes; usamos varios
en paralelo para tolerar fallos individuales — basta con que UNO publique
para tener prueba útil. Lista por defecto incluye los dos del proyecto OTS
oficial + uno de Eternity Wall.
"""

from __future__ import annotations

import urllib.error
from typing import Final

from opentimestamps.calendar import CommitmentNotFoundError, RemoteCalendar
from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

DEFAULT_CALENDARS: Final[tuple[str, ...]] = (
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
)
"""Tres calendarios públicos, operados por entidades independientes. Sólo
hace falta UNO confirmando en Bitcoin para tener proof útil — los otros son
redundancia ante caídas/censura."""

DEFAULT_TIMEOUT_SECONDS: Final[int] = 30


class CalendarSubmitResult:
    """Resultado de submitir el mismo hash a múltiples calendarios."""

    def __init__(self) -> None:
        self.succeeded: list[str] = []
        self.failed: list[tuple[str, str]] = []  # (url, reason)


def submit_to_calendars(
    dtf: DetachedTimestampFile,
    *,
    calendars: tuple[str, ...] = DEFAULT_CALENDARS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> CalendarSubmitResult:
    """Submit el ``dtf`` a cada calendario y mergea las pending attestations.

    Muta ``dtf`` in-place: el ``Timestamp`` interno acumula attestations
    nuevas por cada calendario que responda. Devuelve un resumen de éxitos
    y fallos para que el caller decida si abortar o continuar.

    En V1 toleramos fallos individuales: con que UN calendario suba el hash,
    eventualmente quedará anchorado en Bitcoin. Sólo fallamos duro si NINGUNO
    responde.
    """
    result = CalendarSubmitResult()
    leaf_msg: bytes = dtf.timestamp.msg
    for url in calendars:
        try:
            calendar = RemoteCalendar(url)
            sub_timestamp = calendar.submit(leaf_msg, timeout=timeout)
            dtf.timestamp.merge(sub_timestamp)
            result.succeeded.append(url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            result.failed.append((url, str(exc)))
    return result


def _walk_pending(
    timestamp: Timestamp,
) -> list[tuple[bytes, PendingAttestation, Timestamp]]:
    """Recoge ``(message_at_node, attestation, owning_timestamp)`` para cada
    ``PendingAttestation`` del árbol. Útil para pedir upgrades."""
    out: list[tuple[bytes, PendingAttestation, Timestamp]] = []

    def walk(ts: Timestamp, msg: bytes) -> None:
        for att in ts.attestations:
            if isinstance(att, PendingAttestation):
                out.append((msg, att, ts))
        for op, child in ts.ops.items():
            walk(child, op(msg))

    walk(timestamp, timestamp.msg)
    return out


def upgrade_proof(
    dtf: DetachedTimestampFile,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, int]:
    """Pide upgrades a cada calendario referenciado por una PendingAttestation.

    Devuelve estadísticas: ``{"upgraded": N, "still_pending": M, "failed": K}``.

    El upgrade es idempotente: si una pending attestation ya estaba upgradeada
    en una pasada anterior, vuelve a ser un no-op aquí. Si Bitcoin todavía
    no procesó el batch (~1h desde submit), seguirá pending — sin error.
    """
    pendings = _walk_pending(dtf.timestamp)
    stats = {"upgraded": 0, "still_pending": 0, "failed": 0}

    for msg, pending_att, owning_ts in pendings:
        url = str(pending_att.uri)
        try:
            calendar = RemoteCalendar(url)
            upgraded = calendar.get_timestamp(msg, timeout=timeout)
        except CommitmentNotFoundError:
            # Calendar acknowledges our commitment but Bitcoin batch isn't
            # confirmed yet. Normal state during the ~1h post-submit window.
            stats["still_pending"] += 1
            continue
        except (urllib.error.URLError, OSError, ValueError):
            stats["failed"] += 1
            continue
        # ``upgraded`` is a Timestamp; merge it into the parent so the proof
        # tree gains a path that ends at BitcoinBlockHeaderAttestation.
        owning_ts.merge(upgraded)
        # If the upgraded ts still only carries pending, count as still_pending.
        # The merged tree may contain Bitcoin attestations now — we re-walk
        # to decide.
        if _has_bitcoin_attestation(upgraded):
            stats["upgraded"] += 1
        else:
            stats["still_pending"] += 1
    return stats


def _has_bitcoin_attestation(timestamp: Timestamp) -> bool:
    """Helper: True si hay al menos una ``BitcoinBlockHeaderAttestation`` en el árbol."""

    def walk(ts: Timestamp) -> bool:
        for att in ts.attestations:
            if isinstance(att, BitcoinBlockHeaderAttestation):
                return True
        return any(walk(child) for child in ts.ops.values())

    return walk(timestamp)
