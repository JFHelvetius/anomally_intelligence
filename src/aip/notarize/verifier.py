"""Verificación offline de OpenTimestamps proofs.

Reporta atestaciones encontradas en el árbol del proof; el caller decide qué
hacer con cada una:

- :class:`PendingAttestation` (clase de OTS) — el calendarista dice "subí esto",
  todavía sin anchorar a Bitcoin. No prueba timestamp absoluto.
- :class:`BitcoinAnchorClaim` — el proof afirma que el bytes-en-cierto-nodo
  coincide con el merkle root del bloque Bitcoin de altura N. Es una **afirmación
  no verificada por sí sola**: requiere comparar contra el merkle root real del
  bloque (vía Bitcoin node, block explorer público o block header almacenado).

La verificación offline-completa requiere block headers de Bitcoin. Lo que
hacemos aquí es 100% offline: walk del árbol y match del hash del fichero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

from aip.notarize.store import SHA256_DIGEST_LENGTH


@dataclass(frozen=True)
class BitcoinAnchorClaim:
    """Afirmación de anclaje a un bloque Bitcoin concreto, sin verificar aún.

    Para verificarla completamente se necesita el ``merkle_root`` del bloque
    de altura ``height`` (32 bytes, little-endian-internal). Si coincide con
    ``expected_merkle_root_le``, el proof es válido para ese bloque.
    """

    height: int
    expected_merkle_root_le: bytes


@dataclass(frozen=True)
class PendingClaim:
    """Afirmación de submit pendiente a un calendario, sin anclar aún a Bitcoin."""

    calendar_uri: str


@dataclass(frozen=True)
class VerifyResult:
    """Resultado del walk del proof tree."""

    ok: bool
    """``True`` si la cabeza del proof coincide con el hash esperado del fichero
    Y hay al menos una atestación reconocida. Pending solo cuenta como ok=True
    pero el caller debe entender que no es prueba absoluta de tiempo."""

    file_hash_matches: bool
    """``True`` si el ``leaf`` del proof coincide con el ``expected_sha256``
    provisto. Si es ``False``, el proof es para OTRO fichero."""

    bitcoin_claims: list[BitcoinAnchorClaim] = field(default_factory=list)
    pending_claims: list[PendingClaim] = field(default_factory=list)
    reason: str | None = None


def _walk(
    timestamp: Timestamp,
    msg: bytes,
    bitcoin_out: list[BitcoinAnchorClaim],
    pending_out: list[PendingClaim],
) -> None:
    for att in timestamp.attestations:
        if isinstance(att, BitcoinBlockHeaderAttestation):
            bitcoin_out.append(
                BitcoinAnchorClaim(
                    height=att.height,
                    expected_merkle_root_le=msg,
                )
            )
        elif isinstance(att, PendingAttestation):
            pending_out.append(PendingClaim(calendar_uri=str(att.uri)))
    for op, child in timestamp.ops.items():
        _walk(child, op(msg), bitcoin_out, pending_out)


def verify_proof(
    dtf: DetachedTimestampFile,
    *,
    expected_sha256: bytes,
) -> VerifyResult:
    """Verifica offline el proof tree.

    Checks aplicados:

    1. ``dtf.file_digest`` (el leaf hash que el proof afirma haber notarizado)
       debe coincidir con ``expected_sha256`` — esto demuestra "este proof es
       para ESTOS bytes".
    2. Walk del árbol recolectando todas las atestaciones (pending + bitcoin).

    Devuelve un :class:`VerifyResult` con todas las afirmaciones encontradas.
    Validar el match contra block headers reales de Bitcoin es trabajo
    separado (depende de tener un Bitcoin node o un block header confiable).
    """
    if len(expected_sha256) != SHA256_DIGEST_LENGTH:
        return VerifyResult(
            ok=False,
            file_hash_matches=False,
            reason=(
                f"expected_sha256 must be {SHA256_DIGEST_LENGTH} bytes; "
                f"got {len(expected_sha256)}."
            ),
        )

    file_hash_matches = dtf.file_digest == expected_sha256

    bitcoin_claims: list[BitcoinAnchorClaim] = []
    pending_claims: list[PendingClaim] = []
    _walk(dtf.timestamp, dtf.timestamp.msg, bitcoin_claims, pending_claims)

    if not file_hash_matches:
        return VerifyResult(
            ok=False,
            file_hash_matches=False,
            bitcoin_claims=bitcoin_claims,
            pending_claims=pending_claims,
            reason=(
                f"file hash mismatch: proof is for "
                f"sha256:{dtf.file_digest.hex()}, expected sha256:{expected_sha256.hex()}."
            ),
        )

    if not bitcoin_claims and not pending_claims:
        return VerifyResult(
            ok=False,
            file_hash_matches=True,
            reason="proof has no attestations (neither pending nor bitcoin).",
        )

    return VerifyResult(
        ok=True,
        file_hash_matches=True,
        bitcoin_claims=bitcoin_claims,
        pending_claims=pending_claims,
    )
