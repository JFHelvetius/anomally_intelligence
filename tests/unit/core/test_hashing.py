"""Tests unitarios de ``aip.core.hashing``.

Cualquier valor pinned en este fichero forma parte del contrato de
reproducibilidad bit a bit (ADR-0024 L2, ADR-0031 R4). Si cambia, ha
cambiado la canonicalización o el algoritmo; eso es bug arquitectónico,
no estilo.
"""

from __future__ import annotations

import io

import pytest

from aip.core import hashing

# ---------------------------------------------------------------- SHA-256 directo


def test_sha256_empty_bytes() -> None:
    # Constante criptográfica universalmente conocida (RFC 6234 vector trivial).
    assert hashing.sha256_hex(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_known_string_aip() -> None:
    assert hashing.sha256_hex(b"AIP") == (
        "b24a868593dba8e7c828376c93d080c16ff7a29831af3377fbab149270e330d3"
    )


def test_sha256_known_string_hello_world() -> None:
    assert hashing.sha256_hex(b"hello world") == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_sha256_hex_lowercase_length_64() -> None:
    digest = hashing.sha256_hex(b"anything")
    assert len(digest) == 64
    assert digest == digest.lower()


# ---------------------------------------------------------------- SHA-256 streaming


def test_sha256_stream_matches_direct() -> None:
    payload = b"the quick brown fox jumps over the lazy dog" * 1000
    assert hashing.sha256_hex_stream(io.BytesIO(payload)) == hashing.sha256_hex(payload)


def test_sha256_stream_empty() -> None:
    assert hashing.sha256_hex_stream(io.BytesIO(b"")) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_stream_handles_chunk_boundary() -> None:
    # Tamaño deliberadamente > CHUNK_SIZE para forzar múltiples reads.
    payload = b"x" * (hashing.CHUNK_SIZE * 3 + 17)
    assert hashing.sha256_hex_stream(io.BytesIO(payload)) == hashing.sha256_hex(payload)


# ---------------------------------------------------------------- JCS — estructura


def test_jcs_orders_keys_lexicographically() -> None:
    assert hashing.jcs_canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_jcs_nested_dict_keys_ordered_recursively() -> None:
    obj = {"nested": {"b": [1, 2, 3], "a": "x"}, "top": True}
    assert hashing.jcs_canonicalize(obj) == b'{"nested":{"a":"x","b":[1,2,3]},"top":true}'


def test_jcs_empty_dict() -> None:
    assert hashing.jcs_canonicalize({}) == b"{}"


def test_jcs_empty_list() -> None:
    assert hashing.jcs_canonicalize([]) == b"[]"


def test_jcs_list_preserves_order() -> None:
    # Listas NO se ordenan: el orden de los elementos es semántico.
    assert hashing.jcs_canonicalize([1, 2, 3, "four", None]) == b'[1,2,3,"four",null]'


# ---------------------------------------------------------------- JCS — escalares


def test_jcs_null() -> None:
    assert hashing.jcs_canonicalize(None) == b"null"


def test_jcs_true_false() -> None:
    assert hashing.jcs_canonicalize(True) == b"true"
    assert hashing.jcs_canonicalize(False) == b"false"


def test_jcs_int_decimal_representation() -> None:
    assert hashing.jcs_canonicalize(0) == b"0"
    assert hashing.jcs_canonicalize(-1) == b"-1"
    assert hashing.jcs_canonicalize(1234567890) == b"1234567890"
    # Enteros grandes: Python soporta arbitraria precisión.
    assert hashing.jcs_canonicalize(2**64) == b"18446744073709551616"


def test_jcs_string_basic_ascii() -> None:
    assert hashing.jcs_canonicalize("hello") == b'"hello"'


def test_jcs_string_required_escapes() -> None:
    # RFC 8785: solo escapes obligatorios (control chars, ", \\).
    assert hashing.jcs_canonicalize('a"b') == b'"a\\"b"'
    assert hashing.jcs_canonicalize("a\\b") == b'"a\\\\b"'
    assert hashing.jcs_canonicalize("a\nb") == b'"a\\nb"'
    assert hashing.jcs_canonicalize("a\tb") == b'"a\\tb"'
    assert hashing.jcs_canonicalize("a\rb") == b'"a\\rb"'
    assert hashing.jcs_canonicalize("a\bb") == b'"a\\bb"'
    assert hashing.jcs_canonicalize("a\fb") == b'"a\\fb"'


def test_jcs_string_utf8_preserved_without_escapes() -> None:
    # Caracteres no-ASCII se emiten tal cual en UTF-8 (no \uXXXX).
    assert hashing.jcs_canonicalize("café") == b'"caf\xc3\xa9"'


def test_jcs_string_other_control_chars_use_unicode_escape() -> None:
    # 0x01 (Start of Heading) sin short-escape → .
    assert hashing.jcs_canonicalize("\x01") == b'"\\u0001"'


# ---------------------------------------------------------------- JCS — rechazos


def test_jcs_rejects_float() -> None:
    with pytest.raises(TypeError, match="float"):
        hashing.jcs_canonicalize(3.14)  # type: ignore[arg-type]


def test_jcs_rejects_tuple() -> None:
    with pytest.raises(TypeError):
        hashing.jcs_canonicalize((1, 2, 3))  # type: ignore[arg-type]


def test_jcs_rejects_bytes() -> None:
    with pytest.raises(TypeError):
        hashing.jcs_canonicalize(b"hi")  # type: ignore[arg-type]


def test_jcs_rejects_set() -> None:
    with pytest.raises(TypeError):
        hashing.jcs_canonicalize({1, 2, 3})  # type: ignore[arg-type]


def test_jcs_rejects_non_str_dict_key() -> None:
    with pytest.raises(TypeError, match="dict keys"):
        hashing.jcs_canonicalize({1: "x"})  # type: ignore[dict-item]


# ---------------------------------------------------------------- hash_object


def test_hash_object_combines_jcs_and_sha256() -> None:
    obj = {"b": 1, "a": 2}
    canon = hashing.jcs_canonicalize(obj)
    assert hashing.hash_object(obj) == hashing.sha256_hex(canon)


def test_hash_object_known_pinned_value_simple_dict() -> None:
    assert hashing.hash_object({"b": 1, "a": 2}) == (
        "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )


def test_hash_object_known_pinned_value_aip_metadata() -> None:
    obj = {"name": "AIP", "version": "0.0.1", "stable": False}
    assert hashing.hash_object(obj) == (
        "9c29c4b4943c3dd62f9346c8b160753f6afd38daf0272233d6f56511a9fd352a"
    )
