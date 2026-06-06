"""Verificación de integridad del audit log (ADR-0019).

La verificación recorre el log entrada a entrada y comprueba:

1. ``seq`` empieza en 0 y crece en exactamente +1 por entrada.
2. ``prev_hash`` de la entrada N coincide con ``entry_hash`` de N-1 (o con
   :data:`aip.audit.log.ZERO_HASH` cuando N=0).
3. El ``entry_hash`` almacenado coincide con el recomputado desde los campos
   canónicos (defensa contra tampering del payload sin recompute).

Si cualquiera de los tres falla, devolvemos un :class:`ChainVerificationResult`
con ``ok=False`` y la causa concreta en la entrada N donde la cadena se rompe.
La verificación no se aborta al primer fallo: se reporta el primero pero
seguimos contando entradas para diagnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aip.audit.log import (
    ZERO_HASH,
    compute_entry_hash,
    iter_entries,
)


@dataclass(frozen=True)
class ChainVerificationResult:
    """Resultado de :func:`verify_chain`."""

    ok: bool
    total_entries: int
    first_failure_seq: int | None = None
    first_failure_reason: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def verify_chain(root: Path) -> ChainVerificationResult:
    """Verifica la cadena de hashes del audit log.

    Si el log no existe (o está vacío), se considera **válido** con cero
    entradas — la ausencia de log no es bug por sí misma. Los comandos
    aguas arriba pueden requerir presencia de bootstrap por separado.
    """
    total = 0
    expected_prev_hash = ZERO_HASH
    expected_seq = 0
    first_failure_seq: int | None = None
    first_failure_reason: str | None = None

    for entry in iter_entries(root):
        total += 1
        # Las propiedades de cadena se chequean en orden. Si una falla,
        # registramos la primera causa pero seguimos iterando para contar.

        if first_failure_reason is None and entry.seq != expected_seq:
            first_failure_seq = entry.seq
            first_failure_reason = (
                f"seq mismatch at entry {entry.seq}: expected seq={expected_seq}."
            )

        if first_failure_reason is None and entry.prev_hash != expected_prev_hash:
            first_failure_seq = entry.seq
            first_failure_reason = (
                f"prev_hash mismatch at seq={entry.seq}: expected "
                f"{expected_prev_hash[:8]}…, found {entry.prev_hash[:8]}…."
            )

        if first_failure_reason is None:
            recomputed = compute_entry_hash(
                seq=entry.seq,
                prev_hash=entry.prev_hash,
                timestamp=entry.timestamp,
                actor=entry.actor,
                action=entry.action,
                target=entry.target,
                parameters=entry.parameters,
                result=entry.result,
                schema_version=entry.schema_version,
            )
            if recomputed != entry.entry_hash:
                first_failure_seq = entry.seq
                first_failure_reason = (
                    f"entry_hash mismatch at seq={entry.seq}: stored "
                    f"{entry.entry_hash[:8]}…, recomputed {recomputed[:8]}…."
                )

        # Avanzamos los esperados para la siguiente iteración usando los
        # valores REALES de la entrada (no los esperados). Así, tras detectar
        # la primera ruptura, seguimos midiendo contra la cadena tal cual
        # quedó escrita, no contra una cadena ideal.
        expected_seq = entry.seq + 1
        expected_prev_hash = entry.entry_hash

    return ChainVerificationResult(
        ok=first_failure_reason is None,
        total_entries=total,
        first_failure_seq=first_failure_seq,
        first_failure_reason=first_failure_reason,
    )
