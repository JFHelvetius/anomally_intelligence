"""AIP External Notarization via OpenTimestamps (post-Phase 2).

Cierra el último gap del modelo: hasta ahora todos los timestamps eran
operator-supplied. Con notarización OTS, el hash del manifest queda anclado
a la blockchain de Bitcoin — un operador hostil no puede backdatar sin
re-minar Bitcoin desde la altura de bloque anclada.

Flujo:

1. ``aip notarize submit <manifest.json>`` — calcula SHA-256, manda a 3
   calendarios públicos OTS, escribe el ``.ots`` con pending attestations.
2. (~1h después) ``aip notarize upgrade <manifest.ots>`` — pide a los
   calendarios el upgrade ahora que el batch quedó en un bloque Bitcoin.
3. ``aip notarize verify <manifest.json> <manifest.ots>`` — walk offline
   del proof tree; reporta atestaciones Bitcoin (altura de bloque + merkle
   root esperado). La verificación contra block headers reales queda fuera
   de scope V1 — el usuario consulta block explorer o Bitcoin node.

Limitaciones honestas:

- Bitcoin como anchor — descentralizado pero requiere block header al verify.
- ~1h latencia entre submit y proof finalizado (ventana de batching de OTS).
- Submit + upgrade requieren red. Verify es 100% offline.
"""

from __future__ import annotations

from aip.notarize.header_fetcher import (
    DEFAULT_SOURCES,
    FetchConsensusResult,
    FetchedHeader,
    fetch_consensus,
    fetch_from_source,
)
from aip.notarize.store import (
    OTS_EXTENSION,
    build_detached,
    decode_dtf_from_bytes,
    encode_dtf_to_bytes,
    ots_path_for_manifest,
)
from aip.notarize.submitter import (
    DEFAULT_CALENDARS,
    DEFAULT_TIMEOUT_SECONDS,
    CalendarSubmitResult,
    submit_to_calendars,
    upgrade_proof,
)
from aip.notarize.verifier import (
    BitcoinAnchorClaim,
    PendingClaim,
    VerifyResult,
    verify_proof,
)

__all__ = [
    "DEFAULT_CALENDARS",
    "DEFAULT_SOURCES",
    "DEFAULT_TIMEOUT_SECONDS",
    "OTS_EXTENSION",
    "BitcoinAnchorClaim",
    "CalendarSubmitResult",
    "FetchConsensusResult",
    "FetchedHeader",
    "PendingClaim",
    "VerifyResult",
    "build_detached",
    "decode_dtf_from_bytes",
    "encode_dtf_to_bytes",
    "fetch_consensus",
    "fetch_from_source",
    "ots_path_for_manifest",
    "submit_to_calendars",
    "upgrade_proof",
    "verify_proof",
]
