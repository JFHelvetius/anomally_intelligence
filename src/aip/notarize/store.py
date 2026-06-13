"""Serialización y paths para OpenTimestamps proofs (.ots).

Wrapper delgado sobre :mod:`opentimestamps.core.timestamp` y
:mod:`opentimestamps.core.serialize`. Cero rolling-our-own crypto — la
librería ``opentimestamps`` implementa el formato canónico .ots de OTS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import (
    BytesDeserializationContext,
    BytesSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

from aip.transparency.store import TRANSPARENCY_DIRNAME

OTS_EXTENSION: Final[str] = ".ots"
SHA256_DIGEST_LENGTH: Final[int] = 32


def build_detached(leaf_hash: bytes) -> DetachedTimestampFile:
    """Construye un ``DetachedTimestampFile`` desde el SHA-256 de un fichero.

    El argumento ``leaf_hash`` son los **bytes** del hash (32 bytes), no el hex.
    OTS opera siempre sobre bytes — el hex es sólo representación humana.
    """
    if len(leaf_hash) != SHA256_DIGEST_LENGTH:
        raise ValueError(
            f"leaf_hash must be {SHA256_DIGEST_LENGTH} bytes (SHA-256 digest); "
            f"got {len(leaf_hash)}."
        )
    timestamp = Timestamp(leaf_hash)
    return DetachedTimestampFile(OpSHA256(), timestamp)


def encode_dtf_to_bytes(dtf: DetachedTimestampFile) -> bytes:
    """Serializa un ``DetachedTimestampFile`` al formato binario .ots canónico."""
    ctx = BytesSerializationContext()
    dtf.serialize(ctx)
    return ctx.getbytes()


def decode_dtf_from_bytes(data: bytes) -> DetachedTimestampFile:
    """Deserializa bytes .ots a un ``DetachedTimestampFile``.

    Acepta tanto archivos OTS canónicos como bytes producidos por
    :func:`encode_dtf_to_bytes`.
    """
    ctx = BytesDeserializationContext(data)
    return DetachedTimestampFile.deserialize(ctx)


def ots_path_for_manifest(archive_root: Path, sequence: int) -> Path:
    """Path canónico del sidecar .ots junto al manifest correspondiente.

    Convención: ``<archive>/transparency/manifest-NNNNNN.ots`` — al lado del
    fichero ``manifest-NNNNNN.json`` que notariza. El portal y el exporter
    asumen este layout.
    """
    if sequence < 0:
        raise ValueError(f"sequence must be >= 0, got {sequence}.")
    return archive_root / TRANSPARENCY_DIRNAME / f"manifest-{sequence:06d}{OTS_EXTENSION}"
