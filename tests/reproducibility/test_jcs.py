"""Reproducibility tests para canonicalización JCS (ADR-0031 T3).

Estos valores son **canonical pinned**: forman parte del contrato de
reproducibilidad bit a bit. Si cambian, ha cambiado la canonicalización
JCS o el algoritmo SHA-256 del proyecto. Eso es bug arquitectónico
crítico — no se actualizan sin PR explícito que documente la causa.
"""

from __future__ import annotations

import pytest

from aip.core import hashing

pytestmark = pytest.mark.reproducibility


# Corpus canónico: (objeto, bytes JCS esperados, SHA-256 hex del JCS esperado).
CANONICAL_CASES: list[tuple[hashing.JsonValue, bytes, str]] = [
    (
        {"b": 1, "a": 2},
        b'{"a":2,"b":1}',
        "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772",
    ),
    (
        {"name": "AIP", "version": "0.0.1", "stable": False},
        b'{"name":"AIP","stable":false,"version":"0.0.1"}',
        "9c29c4b4943c3dd62f9346c8b160753f6afd38daf0272233d6f56511a9fd352a",
    ),
    (
        {"nested": {"b": [1, 2, 3], "a": "x"}, "top": True},
        b'{"nested":{"a":"x","b":[1,2,3]},"top":true}',
        "c714449c010e88d0140bccf8164eb6820e343dd66df8f5a9a48a61f7f8689f4a",
    ),
    (
        [1, 2, 3, "four", None],
        b'[1,2,3,"four",null]',
        "1a75ce26e7a5740391899968fa5afa5e42f60e2b39290b22ac0b10a6ad75c7be",
    ),
    (
        {},
        b"{}",
        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    ),
    (
        [],
        b"[]",
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    ),
]


@pytest.mark.parametrize(
    ("obj", "expected_canon", "expected_sha256"),
    CANONICAL_CASES,
    ids=[
        "dict_two_keys_reordered",
        "aip_metadata_flat",
        "nested_dict_and_list",
        "list_with_mixed_scalars",
        "empty_dict",
        "empty_list",
    ],
)
def test_canonical_jcs_bytes_and_hash(
    obj: hashing.JsonValue,
    expected_canon: bytes,
    expected_sha256: str,
) -> None:
    canon = hashing.jcs_canonicalize(obj)
    assert canon == expected_canon, (
        f"JCS canonical bytes drifted for {obj!r}.\n"
        f"  expected: {expected_canon!r}\n"
        f"  got:      {canon!r}\n"
        "Si el cambio es intencional, justifícalo en PR y actualiza tanto este "
        "fichero como cualquier ArchiveManifest dependiente."
    )
    assert hashing.sha256_hex(canon) == expected_sha256
    assert hashing.hash_object(obj) == expected_sha256


def test_canonical_jcs_corpus_no_collisions() -> None:
    # Sanidad: cada caso del corpus produce un hash distinto.
    hashes = {sha256 for _, _, sha256 in CANONICAL_CASES}
    assert len(hashes) == len(CANONICAL_CASES)
