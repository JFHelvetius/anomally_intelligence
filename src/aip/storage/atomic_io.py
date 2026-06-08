"""Primitivas de escritura atómica para artefactos derivados.

Defensa mínima contra ficheros parcialmente escritos por crashes
mid-write. Coherente con el patrón ya usado por
:func:`aip.storage.manifest.write_manifest_atomic` y por la ingesta de
blobs CAOS en :meth:`aip.archive.Archive.ingest_evidence`.

Estrategia: write-to-tmp + ``os.replace``. ``os.replace`` es atómico
tanto en POSIX como en Windows cuando origen y destino están en el
mismo filesystem (que es nuestro caso: el ``.tmp`` se crea en el
mismo directorio del target).
"""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(
    target: Path,
    payload: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Escribe ``payload`` en ``target`` de forma atómica.

    El directorio padre se crea si no existe. La escritura va primero a
    ``<target>.tmp`` y luego ``os.replace`` lo mueve al destino final.
    Si el proceso muere mid-write, el ``.tmp`` puede quedar huérfano
    pero el destino canónico nunca queda parcialmente escrito.

    Args:
        target: Path absoluto del fichero destino.
        payload: Texto completo a escribir.
        encoding: Codificación del texto. Default ``utf-8``.

    Notas operativas:

    - El caller es responsable de garantizar que ``target`` y el
      ``.tmp`` estén en el mismo filesystem (lo asegura el sufijo
      ``.tmp`` en el mismo directorio).
    - Tras un crash, los ``.tmp`` huérfanos no son tóxicos (no
      contaminan el self-hash ni la enumeración de artefactos
      derivados — los colectores filtran por ``*.json``).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload, encoding=encoding)
    os.replace(tmp, target)
