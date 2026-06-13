"""Fetch Bitcoin block headers from public block explorers.

Helper para reducir fricción al embeber headers en reportes HTML standalone.
El operador necesita pasar 80 bytes de header (160 hex chars) a
``aip evidence report --bitcoin-header HEIGHT:HEX`` para que el navegador
verifique client-side el merkle root reclamado por el OTS proof. Tipearlo a
mano desde un block explorer es propenso a error.

Diseño:

- **Stdlib-only**: urllib, sin requests, sin httpx — minimiza supply chain.
- **Sin confianza en el explorer**: la fuente sólo provee los 80 bytes; el
  receptor sigue verificando vs el OTS claim (que viene de Bitcoin merkle
  computation, no del explorer). Si el explorer mintió, el verify dará
  MISMATCH — exactamente como queremos.
- **Multi-fuente con consenso**: por defecto se consulta a >=2 explorers
  independientes y se exige que devuelvan el mismo header. Si discrepan,
  fallo ruidoso — un explorer comprometido no puede inyectar un header
  malicioso silenciosamente.

Default sources: mempool.space + blockstream.info (operadores diferentes,
infra diferente, ambos REST públicos sin auth).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

from aip.errors import AIPError

DEFAULT_SOURCES: Final[tuple[str, ...]] = (
    "https://mempool.space/api",
    "https://blockstream.info/api",
)
"""Public explorer REST bases. Both follow the esplora-style API:

- ``GET /block-height/<height>`` → block hash (64-hex text)
- ``GET /block/<hash>/header``   → 80-byte block header (160-hex text)
"""

DEFAULT_TIMEOUT_SECONDS: Final[int] = 30

_HEADER_HEX_LEN: Final[int] = 160
_BLOCK_HASH_HEX_LEN: Final[int] = 64
_USER_AGENT: Final[str] = "aip-notarize-fetch-header/1"


@dataclass(frozen=True, slots=True)
class FetchedHeader:
    """Result of fetching one block header from one source."""

    source: str
    height: int
    block_hash_hex: str
    header_hex: str
    merkle_root_le_hex: str


def _http_get_text(url: str, *, timeout: int) -> str:
    """Minimal stdlib GET that returns body as stripped text."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body: bytes = resp.read()
            return body.decode("ascii", errors="strict").strip()
    except urllib.error.HTTPError as exc:
        raise AIPError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise AIPError(f"network error fetching {url}: {exc.reason}") from exc


def _extract_merkle_root_le(header_hex: str) -> str:
    """Extract merkle_root (LE internal byte order) from an 80-byte header.

    Layout: version[0..4) prev_hash[4..36) merkle_root[36..68)
            timestamp[68..72) bits[72..76) nonce[76..80)
    So in hex chars: merkle_root at [72..136).
    """
    return header_hex[72:136].lower()


def fetch_from_source(
    source: str, height: int, *, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> FetchedHeader:
    """Fetch a block header from a single esplora-style explorer.

    Raises ``AIPError`` if the response is malformed (not 160 hex chars).
    """
    base = source.rstrip("/")
    block_hash = _http_get_text(f"{base}/block-height/{height}", timeout=timeout)
    if len(block_hash) != _BLOCK_HASH_HEX_LEN:
        raise AIPError(
            f"{source}: block-height/{height} returned non-hash response "
            f"({len(block_hash)} chars): {block_hash[:80]!r}"
        )
    if any(c not in "0123456789abcdef" for c in block_hash.lower()):
        raise AIPError(
            f"{source}: block-height/{height} returned non-hex hash: {block_hash[:80]!r}"
        )

    header = _http_get_text(
        f"{base}/block/{block_hash}/header", timeout=timeout
    )
    header_lc = header.lower()
    if len(header_lc) != _HEADER_HEX_LEN:
        raise AIPError(
            f"{source}: block/{block_hash}/header returned {len(header_lc)} chars; "
            f"expected {_HEADER_HEX_LEN}"
        )
    if any(c not in "0123456789abcdef" for c in header_lc):
        raise AIPError(
            f"{source}: block/{block_hash}/header returned non-hex: {header_lc[:80]!r}"
        )

    return FetchedHeader(
        source=source,
        height=height,
        block_hash_hex=block_hash.lower(),
        header_hex=header_lc,
        merkle_root_le_hex=_extract_merkle_root_le(header_lc),
    )


@dataclass(frozen=True, slots=True)
class FetchConsensusResult:
    """Multi-source fetch result.

    - ``agreed``: all queried sources returned the same header_hex.
    - ``per_source``: each source that returned a header successfully.
    - ``errors``: list of (source, reason) for sources that failed.
    """

    height: int
    agreed: bool
    header_hex: str
    block_hash_hex: str
    merkle_root_le_hex: str
    per_source: list[FetchedHeader]
    errors: list[tuple[str, str]]


def fetch_consensus(
    height: int,
    *,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    min_agreement: int = 2,
) -> FetchConsensusResult:
    """Query >=2 explorers and require they agree on the header bytes.

    A single compromised explorer cannot inject a malicious header — the
    verifier downstream would catch the merkle mismatch, but here we catch
    it earlier and refuse to even emit a hex string the operator might
    paste blindly.

    ``min_agreement`` of 1 disables the cross-check (single-source mode);
    callers that want speed over paranoia can opt in.
    """
    if not sources:
        raise AIPError("fetch_consensus: sources tuple is empty")
    if min_agreement < 1:
        raise AIPError("fetch_consensus: min_agreement must be >= 1")

    per_source: list[FetchedHeader] = []
    errors: list[tuple[str, str]] = []
    for src in sources:
        try:
            per_source.append(
                fetch_from_source(src, height, timeout=timeout)
            )
        except AIPError as exc:
            errors.append((src, str(exc)))

    if not per_source:
        joined = "; ".join(f"{s}: {r}" for s, r in errors)
        raise AIPError(f"all sources failed for height {height}: {joined}")

    # Group by header_hex.
    headers_seen = {fh.header_hex for fh in per_source}
    agreed = len(headers_seen) == 1 and len(per_source) >= min_agreement

    if len(headers_seen) > 1:
        details = ", ".join(
            f"{fh.source}={fh.header_hex[:16]}…" for fh in per_source
        )
        raise AIPError(
            f"sources disagree on block {height} header: {details}. "
            "Refusing to emit a header that is not cross-validated."
        )

    # All agree on a single header (or we have only 1 result and min_agreement==1).
    if len(per_source) < min_agreement:
        sources_returned = [fh.source for fh in per_source]
        raise AIPError(
            f"only {len(per_source)} source(s) returned a header for block "
            f"{height} ({sources_returned}); min_agreement={min_agreement}. "
            f"Errors: {errors}"
        )

    first = per_source[0]
    return FetchConsensusResult(
        height=height,
        agreed=agreed,
        header_hex=first.header_hex,
        block_hash_hex=first.block_hash_hex,
        merkle_root_le_hex=first.merkle_root_le_hex,
        per_source=per_source,
        errors=errors,
    )


__all__ = [
    "DEFAULT_SOURCES",
    "DEFAULT_TIMEOUT_SECONDS",
    "FetchConsensusResult",
    "FetchedHeader",
    "fetch_consensus",
    "fetch_from_source",
]
