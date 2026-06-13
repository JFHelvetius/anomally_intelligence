"""Tests for ``aip.notarize.header_fetcher``.

The fetcher is a pure-stdlib HTTP helper that pulls 80-byte Bitcoin block
headers from public esplora-style explorers and exposes a consensus mode
that requires multiple sources to return identical bytes.

We never make real HTTP calls in tests — every test patches
``urllib.request.urlopen`` so the fetcher's logic is exercised in
isolation. Determinism is critical because this code path will surface in
operator workflows that paste hex straight into downstream verifiers.
"""

from __future__ import annotations

import contextlib
import io
import urllib.error
from collections.abc import Generator
from typing import Any
from unittest import mock

import pytest

from aip.errors import AIPError
from aip.notarize import header_fetcher

# Real block 953027 header (confirmed via mempool.space + blockstream.info,
# 2026-06-09). Merkle root LE: c2e668…6b564a.
REAL_HEADER_953027 = (
    "00003b27d1e832fd2e346319ad000e274725a639e7ee012c393300000000000000000000"
    "c2e668837a85409d4b5bcc80976ebbc592f71249ed8289905ff033c4666b564a"
    "a898286a8f0602171d2fa80e"
)
REAL_BLOCK_HASH_953027 = (
    "000000000000000000017a1024f79cd8ce949b61a66c9c837010ab1e451e8827"
)
REAL_MERKLE_LE_953027 = (
    "c2e668837a85409d4b5bcc80976ebbc592f71249ed8289905ff033c4666b564a"
)


def _fake_response(body: str) -> contextlib.AbstractContextManager[Any]:
    """Mimic the context-manager API of ``urlopen``: ``.read()`` returns bytes."""

    @contextlib.contextmanager
    def cm() -> Generator[Any]:
        fake = mock.Mock()
        fake.read.return_value = body.encode("ascii")
        yield fake

    return cm()


def _make_urlopen(responses_by_url: dict[str, str | Exception]):
    """Build a fake ``urlopen`` that dispatches on the requested URL."""

    def fake_urlopen(req: Any, timeout: int) -> Any:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        match = responses_by_url.get(url)
        if isinstance(match, Exception):
            raise match
        if match is None:
            raise AssertionError(f"unexpected URL in test: {url}")
        return _fake_response(match)

    return fake_urlopen


# ----------------------------------------------------------- fetch_from_source


def test_fetch_from_source_happy_path() -> None:
    src = "https://example.com/api"
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": REAL_BLOCK_HASH_953027,
            f"{src}/block/{REAL_BLOCK_HASH_953027}/header": REAL_HEADER_953027,
        }
    )
    with mock.patch("urllib.request.urlopen", fake):
        result = header_fetcher.fetch_from_source(src, 953027)

    assert result.source == src
    assert result.height == 953027
    assert result.block_hash_hex == REAL_BLOCK_HASH_953027
    assert result.header_hex == REAL_HEADER_953027
    assert result.merkle_root_le_hex == REAL_MERKLE_LE_953027


def test_fetch_from_source_uppercase_hash_normalized() -> None:
    src = "https://example.com/api"
    upper_hash = REAL_BLOCK_HASH_953027.upper()
    upper_header = REAL_HEADER_953027.upper()
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": upper_hash,
            # The implementation builds the header URL with the as-received
            # hash, so the mocked URL must use the same casing.
            f"{src}/block/{upper_hash}/header": upper_header,
        }
    )
    with mock.patch("urllib.request.urlopen", fake):
        result = header_fetcher.fetch_from_source(src, 953027)

    assert result.block_hash_hex == REAL_BLOCK_HASH_953027  # lowercased
    assert result.header_hex == REAL_HEADER_953027


def test_fetch_from_source_rejects_short_hash() -> None:
    src = "https://example.com/api"
    fake = _make_urlopen({f"{src}/block-height/953027": "deadbeef"})
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="non-hash response"):
            header_fetcher.fetch_from_source(src, 953027)


def test_fetch_from_source_rejects_non_hex_hash() -> None:
    src = "https://example.com/api"
    not_hex = "Z" * 64
    fake = _make_urlopen({f"{src}/block-height/953027": not_hex})
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="non-hex hash"):
            header_fetcher.fetch_from_source(src, 953027)


def test_fetch_from_source_rejects_short_header() -> None:
    src = "https://example.com/api"
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": REAL_BLOCK_HASH_953027,
            f"{src}/block/{REAL_BLOCK_HASH_953027}/header": "ab" * 70,  # 140 chars
        }
    )
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="expected 160"):
            header_fetcher.fetch_from_source(src, 953027)


def test_fetch_from_source_rejects_non_hex_header() -> None:
    src = "https://example.com/api"
    bad_header = "z" * 160
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": REAL_BLOCK_HASH_953027,
            f"{src}/block/{REAL_BLOCK_HASH_953027}/header": bad_header,
        }
    )
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="non-hex"):
            header_fetcher.fetch_from_source(src, 953027)


def test_fetch_from_source_http_error_wrapped_as_aiperror() -> None:
    src = "https://example.com/api"
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": urllib.error.HTTPError(
                url=f"{src}/block-height/953027",
                code=404,
                msg="Not Found",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(b""),
            )
        }
    )
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="HTTP 404"):
            header_fetcher.fetch_from_source(src, 953027)


def test_fetch_from_source_network_error_wrapped_as_aiperror() -> None:
    src = "https://example.com/api"
    fake = _make_urlopen(
        {
            f"{src}/block-height/953027": urllib.error.URLError(
                "name resolution failed"
            )
        }
    )
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="network error"):
            header_fetcher.fetch_from_source(src, 953027)


# --------------------------------------------------------------- fetch_consensus


def _both_sources_return(header_hex: str) -> dict[str, str]:
    sources = ["https://mempool.space/api", "https://blockstream.info/api"]
    out: dict[str, str] = {}
    for s in sources:
        out[f"{s}/block-height/953027"] = REAL_BLOCK_HASH_953027
        out[f"{s}/block/{REAL_BLOCK_HASH_953027}/header"] = header_hex
    return out


def test_fetch_consensus_two_sources_agree() -> None:
    fake = _make_urlopen(_both_sources_return(REAL_HEADER_953027))
    with mock.patch("urllib.request.urlopen", fake):
        result = header_fetcher.fetch_consensus(953027)

    assert result.agreed is True
    assert result.header_hex == REAL_HEADER_953027
    assert len(result.per_source) == 2
    assert result.errors == []


def test_fetch_consensus_sources_disagree_raises() -> None:
    sources = ["https://mempool.space/api", "https://blockstream.info/api"]
    different_header = REAL_HEADER_953027[:-2] + "ff"  # flip a byte
    mapping: dict[str, Any] = {
        f"{sources[0]}/block-height/953027": REAL_BLOCK_HASH_953027,
        f"{sources[0]}/block/{REAL_BLOCK_HASH_953027}/header": REAL_HEADER_953027,
        f"{sources[1]}/block-height/953027": REAL_BLOCK_HASH_953027,
        f"{sources[1]}/block/{REAL_BLOCK_HASH_953027}/header": different_header,
    }
    fake = _make_urlopen(mapping)
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="sources disagree"):
            header_fetcher.fetch_consensus(953027)


def test_fetch_consensus_one_source_fails_other_succeeds_below_quorum() -> None:
    """If only 1/2 sources answer and min_agreement=2, fetch must fail.

    This is the load-bearing safety property: an operator who configured
    two sources to cross-check should NOT silently accept one answer just
    because the other timed out.
    """
    sources = ["https://mempool.space/api", "https://blockstream.info/api"]
    mapping: dict[str, Any] = {
        f"{sources[0]}/block-height/953027": REAL_BLOCK_HASH_953027,
        f"{sources[0]}/block/{REAL_BLOCK_HASH_953027}/header": REAL_HEADER_953027,
        f"{sources[1]}/block-height/953027": urllib.error.URLError("down"),
    }
    fake = _make_urlopen(mapping)
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="only 1 source"):
            header_fetcher.fetch_consensus(953027)


def test_fetch_consensus_single_source_mode_allows_quorum_of_one() -> None:
    """Opt-in: ``min_agreement=1`` accepts a single source. Documented escape
    hatch for when one explorer is offline."""
    sources = ["https://mempool.space/api", "https://blockstream.info/api"]
    mapping: dict[str, Any] = {
        f"{sources[0]}/block-height/953027": REAL_BLOCK_HASH_953027,
        f"{sources[0]}/block/{REAL_BLOCK_HASH_953027}/header": REAL_HEADER_953027,
        f"{sources[1]}/block-height/953027": urllib.error.URLError("down"),
    }
    fake = _make_urlopen(mapping)
    with mock.patch("urllib.request.urlopen", fake):
        result = header_fetcher.fetch_consensus(953027, min_agreement=1)

    assert result.header_hex == REAL_HEADER_953027
    assert len(result.per_source) == 1
    assert result.errors  # the second source's failure is recorded


def test_fetch_consensus_all_sources_fail_raises() -> None:
    sources = ["https://mempool.space/api", "https://blockstream.info/api"]
    mapping: dict[str, Any] = {
        f"{sources[0]}/block-height/953027": urllib.error.URLError("a-down"),
        f"{sources[1]}/block-height/953027": urllib.error.URLError("b-down"),
    }
    fake = _make_urlopen(mapping)
    with mock.patch("urllib.request.urlopen", fake):  # noqa: SIM117
        with pytest.raises(AIPError, match="all sources failed"):
            header_fetcher.fetch_consensus(953027)


def test_fetch_consensus_empty_sources_raises() -> None:
    with pytest.raises(AIPError, match="sources tuple is empty"):
        header_fetcher.fetch_consensus(953027, sources=())


def test_fetch_consensus_invalid_min_agreement_raises() -> None:
    with pytest.raises(AIPError, match="min_agreement must be >= 1"):
        header_fetcher.fetch_consensus(953027, min_agreement=0)


def test_merkle_root_extraction_offset_is_72_to_136() -> None:
    """Regression guard for the Bitcoin block-header layout.

    A subtle bug here (e.g., flipping bytes 4..36 with 36..68) would silently
    accept tampered headers downstream. This test pins the offsets explicitly.
    """
    fake = _make_urlopen(_both_sources_return(REAL_HEADER_953027))
    with mock.patch("urllib.request.urlopen", fake):
        result = header_fetcher.fetch_consensus(953027)

    assert result.merkle_root_le_hex == REAL_HEADER_953027[72:136]
    assert result.merkle_root_le_hex == REAL_MERKLE_LE_953027
