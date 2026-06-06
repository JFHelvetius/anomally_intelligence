"""Property-based tests sobre ``aip.core.hashing`` (ADR-0031 §opcional).

Estos tests **no** modifican el código de producción; solo verifican
invariantes adicionales con inputs aleatorios deterministas (Hypothesis
con seed por defecto + ``derandomize=True`` en CI). Cubren las cuatro
garantías declaradas en el framing v0.1.0:

1. **Provenance:** la canonicalización JCS es función pura — mismo input,
   mismos bytes, siempre.
2. **Integridad de evidencia:** dos objetos con contenido semánticamente
   distinto producen bytes JCS distintos, por tanto hashes distintos.
3. **Reproducibilidad:** JCS es invariante al orden de claves en dicts y al
   orden en que Python construye internamente sus estructuras.
4. **Hash stability:** ``hash_object`` produce hex lowercase de longitud
   exacta 64; aplicar ``json.loads`` + ``jcs_canonicalize`` es idempotente.

Si alguna de estas propiedades falla, la cadena de evidencia del proyecto
está rota y los manifest hashes pinned dejan de ser garantía.
"""

from __future__ import annotations

import json

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aip.core.hashing import (
    SHA256_HEX_LENGTH,
    hash_object,
    jcs_canonicalize,
    sha256_hex,
)

# --------------------------------------------------------------------- settings

# Perfil ajustado para CI: ejemplos suficientes para confianza, deadline
# generoso para máquinas lentas. Sin shrinking agresivo (no necesitamos
# minimal counterexamples para regressions porque el código de producción
# no cambia en este ciclo).
_PROFILE = settings(
    max_examples=100,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
    derandomize=True,
)


# --------------------------------------------------------------------- strategies


# ``JsonValue`` admisible por JCS: sin floats, sin bytes, sin tuples, sin sets.
# Caracteres surrogate (categoría Cs) excluidos porque no codifican a UTF-8
# y romperían la encodificación final, no la lógica de JCS.
_safe_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        min_codepoint=0,
        max_codepoint=0x10FFFF,
    ),
    max_size=20,
)

_safe_scalar = st.one_of(
    st.none(),
    st.booleans(),
    # Enteros dentro del rango seguro para JSON round-trip.
    st.integers(min_value=-(2**53), max_value=2**53),
    _safe_text,
)

_json_value = st.recursive(
    _safe_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(
            keys=_safe_text.filter(bool),  # claves no vacías para JCS estricto
            values=children,
            max_size=4,
        ),
    ),
    max_leaves=10,
)


# --------------------------------------------------------------------- properties


@given(value=_json_value)
@_PROFILE
def test_jcs_is_pure_function(value: object) -> None:
    """Mismo input ⇒ mismos bytes, siempre. (Provenance §1)"""
    a = jcs_canonicalize(value)  # type: ignore[arg-type]
    b = jcs_canonicalize(value)  # type: ignore[arg-type]
    assert a == b


@given(value=_json_value)
@_PROFILE
def test_hash_object_is_64_lowercase_hex(value: object) -> None:
    """Salida canónica de ``hash_object`` es siempre hex lowercase de 64. (Hash stability §4)"""
    h = hash_object(value)  # type: ignore[arg-type]
    assert len(h) == SHA256_HEX_LENGTH
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


@given(value=_json_value)
@_PROFILE
def test_jcs_round_trip_through_json_loads_is_idempotent(value: object) -> None:
    """``jcs(json.loads(jcs(x))) == jcs(x)``.

    Cualquier valor que pase por JCS y vuelva por json.loads, al re-canonicalizar
    produce los mismos bytes. (Reproducibilidad §3, idempotencia)
    """
    once = jcs_canonicalize(value)  # type: ignore[arg-type]
    reparsed = json.loads(once.decode("utf-8"))
    twice = jcs_canonicalize(reparsed)
    assert once == twice


@given(d=st.dictionaries(keys=_safe_text.filter(bool), values=_safe_scalar, min_size=2, max_size=4))
@_PROFILE
def test_jcs_key_order_invariance(d: dict[str, object]) -> None:
    """JCS sobre el mismo dict en orden de inserción distinto produce los mismos bytes.

    (Reproducibilidad §3, key-order invariance de RFC 8785 §3.2.3)
    """
    items = list(d.items())
    reversed_dict = dict(reversed(items))
    assert jcs_canonicalize(d) == jcs_canonicalize(reversed_dict)  # type: ignore[arg-type]


@given(a=_json_value, b=_json_value)
@_PROFILE
def test_jcs_injectivity_implies_hash_distinguishes(a: object, b: object) -> None:
    """Si los bytes canónicos difieren, los hashes difieren.

    (Integridad de evidencia §2; modulo colisión SHA-256 que es cripto-improbable).
    """
    canon_a = jcs_canonicalize(a)  # type: ignore[arg-type]
    canon_b = jcs_canonicalize(b)  # type: ignore[arg-type]
    if canon_a != canon_b:
        assert hash_object(a) != hash_object(b)  # type: ignore[arg-type]
    else:
        assert hash_object(a) == hash_object(b)  # type: ignore[arg-type]


@given(value=_json_value)
@_PROFILE
def test_hash_object_equals_sha256_of_jcs(value: object) -> None:
    """Identidad estructural: ``hash_object(x) == sha256_hex(jcs(x))``. (Hash stability §4)"""
    assert hash_object(value) == sha256_hex(jcs_canonicalize(value))  # type: ignore[arg-type]


@given(data=st.binary(max_size=4096))
@_PROFILE
def test_sha256_hex_deterministic_and_canonical(data: bytes) -> None:
    """SHA-256 sobre bytes es función pura, hex lowercase, longitud 64."""
    h1 = sha256_hex(data)
    h2 = sha256_hex(data)
    assert h1 == h2
    assert len(h1) == SHA256_HEX_LENGTH
    assert h1 == h1.lower()


# --------------------------------------------------------------------- rejection


@given(
    bad=st.one_of(
        st.floats(allow_nan=False, allow_infinity=False),
        st.tuples(st.integers(), st.integers()),
        st.binary(max_size=16),
        st.sets(st.integers(), max_size=3),
    )
)
@_PROFILE
def test_jcs_rejects_non_json_types(bad: object) -> None:
    """JCS levanta TypeError sobre todo tipo fuera del subset estricto.

    (Defensa contra fabricación silenciosa por canonicalización de tipos
    ambiguos — ADR-0024 §formato canónico.)
    """
    try:
        jcs_canonicalize(bad)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError(f"jcs_canonicalize should have rejected {type(bad).__name__}")
