"""Primitivas de hash y canonicalización JSON.

Implementa:

- :func:`sha256_hex` y :func:`sha256_hex_stream` — SHA-256 sobre bytes y streams.
- :func:`jcs_canonicalize` — subset estricto de **RFC 8785 JSON Canonicalization
  Scheme**: claves ordenadas por code units UTF-16-BE, sin whitespace
  insignificante, escapes JSON obligatorios, UTF-8 sin BOM.
- :func:`hash_object` — atajo: ``sha256_hex(jcs_canonicalize(obj))``.

Tipos admitidos en la canonicalización (V1):

- ``None`` → ``null``
- ``True`` / ``False`` → ``true`` / ``false``
- ``int`` → representación decimal exacta
- ``str`` → cadena UTF-8 entre comillas con escapes obligatorios
- ``list`` de los anteriores → ``[...]``
- ``dict[str, ...]`` con claves ``str`` → ``{...}`` con claves ordenadas

Tipos **rechazados** explícitamente:

- ``float`` — representación variable entre implementaciones; podría reintroducirse
  con política de ECMA-262 ``Number.prototype.toString`` en un ADR posterior.
- ``Decimal`` — análogo.
- ``bytes`` — sin codificación implícita; el llamador debe decidir base64 u otro.
- ``tuple``, ``set``, ``frozenset`` — fuera del subset JSON.
- Cualquier otro tipo no listado.

La política conservadora protege la propiedad de reproducibilidad bit a bit
(ADR-0024 L2, ADR-0031 R4): no se canonicalizan tipos donde la representación
es ambigua entre implementaciones.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import BinaryIO, Final

CHUNK_SIZE: Final[int] = 64 * 1024
"""Tamaño de bloque para hashing en streaming. 64 KiB es el tradeoff estándar
entre overhead de llamadas y memoria pico."""

SHA256_HEX_LENGTH: Final[int] = 64
"""Longitud canónica de un hash SHA-256 en hex lowercase (ADR-0016)."""

CONTROL_CHAR_THRESHOLD: Final[int] = 0x20
"""Code point a partir del cual los caracteres dejan de ser de control y no
requieren escape JSON obligatorio (RFC 8259 §7, RFC 8785)."""


# ``JsonValue`` admite ``Sequence``/``Mapping`` covariantes en el plano de
# tipos para que ``list[str]`` y ``dict[str, str]`` (invariantes en sus
# parámetros) sean aceptados sin cast. El runtime sigue siendo estricto: solo
# se serializan ``list`` y ``dict`` reales (cualquier otro Sequence/Mapping
# levanta ``TypeError`` en :func:`_serialize`).
JsonScalar = str | int | bool | None
JsonValue = JsonScalar | Sequence["JsonValue"] | Mapping[str, "JsonValue"]


def sha256_hex(data: bytes) -> str:
    """SHA-256 sobre ``data``; devuelve hex lowercase de 64 caracteres."""
    return hashlib.sha256(data).hexdigest()


def sha256_hex_stream(reader: BinaryIO) -> str:
    """SHA-256 sobre un binario en streaming.

    Lee en bloques de :data:`CHUNK_SIZE` sin cargar el contenido completo
    en memoria. Útil para ficheros grandes (PDFs, audios, etc.).
    """
    hasher = hashlib.sha256()
    while True:
        chunk = reader.read(CHUNK_SIZE)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()


def jcs_canonicalize(obj: JsonValue) -> bytes:
    """Canonicaliza ``obj`` conforme a un subset estricto de RFC 8785.

    Levanta :class:`TypeError` para tipos no admitidos.
    """
    parts: list[bytes] = []
    _serialize(obj, parts)
    return b"".join(parts)


def hash_object(obj: JsonValue) -> str:
    """Atajo: ``sha256_hex(jcs_canonicalize(obj))``."""
    return sha256_hex(jcs_canonicalize(obj))


# --------------------------------------------------------------------------- helpers


def _serialize(obj: JsonValue, parts: list[bytes]) -> None:  # noqa: PLR0911, PLR0912
    # `is True` y `is False` interceptan los singletons booleanos antes de
    # caer en isinstance(obj, int). En Python `isinstance(True, int)` es True,
    # por lo que el orden importa.
    if obj is None:
        parts.append(b"null")
        return
    if obj is True:
        parts.append(b"true")
        return
    if obj is False:
        parts.append(b"false")
        return
    if isinstance(obj, float):
        raise TypeError(
            "float values are not supported by jcs_canonicalize in V1; "
            "use int or string representation explicitly."
        )
    if isinstance(obj, int):
        parts.append(str(obj).encode("ascii"))
        return
    if isinstance(obj, str):
        _emit_string(obj, parts)
        return
    if isinstance(obj, list):
        parts.append(b"[")
        first = True
        for item in obj:
            if not first:
                parts.append(b",")
            _serialize(item, parts)
            first = False
        parts.append(b"]")
        return
    if isinstance(obj, dict):
        # Validación previa: todas las claves deben ser str.
        for key in obj:
            if not isinstance(key, str):
                raise TypeError(
                    f"dict keys must be str for JCS, got {type(key).__name__}"
                )
        # Ordenación por code units UTF-16-BE conforme a RFC 8785 §3.2.3.
        # Python compara strings por code point Unicode; para BMP coincide
        # con UTF-16, pero fuera del BMP (supplementary planes) difieren
        # por la presencia de surrogate pairs en UTF-16.
        items = sorted(obj.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        parts.append(b"{")
        first = True
        for key, value in items:
            if not first:
                parts.append(b",")
            _emit_string(key, parts)
            parts.append(b":")
            _serialize(value, parts)
            first = False
        parts.append(b"}")
        return
    raise TypeError(
        f"unsupported type for JCS canonicalization: {type(obj).__name__}"
    )


# Mapa de escapes obligatorios para caracteres de control habituales.
_SHORT_ESCAPES: Final[dict[str, str]] = {
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _emit_string(value: str, parts: list[bytes]) -> None:
    out: list[str] = ['"']
    for ch in value:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif cp < CONTROL_CHAR_THRESHOLD:
            short = _SHORT_ESCAPES.get(ch)
            if short is not None:
                out.append(short)
            else:
                # `\uXXXX` para el resto de caracteres de control.
                out.append(f"\\u{cp:04x}")
        else:
            # Cualquier otro carácter (incluyendo no-ASCII) se emite tal cual
            # en UTF-8. RFC 8785 prohíbe escapes innecesarios.
            out.append(ch)
    out.append('"')
    parts.append("".join(out).encode("utf-8"))
