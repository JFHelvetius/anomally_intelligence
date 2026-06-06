"""Paths canónicos del archive y operaciones de bootstrap (ADR-0015).

Constantes:

- :data:`MANIFEST_FILENAME` — fichero con :class:`ArchiveManifest`.
- :data:`OBJECTS_DIRNAME` — raíz del Content-Addressed Object Store.
- :data:`SHA256_ALGO_DIRNAME` — subdir del algoritmo canónico (ADR-0016).
- :data:`TABLES_DIRNAME` — raíz de tablas Parquet.
- :data:`AUDIT_LOG_FILENAME` — fichero append-only con hash chain (ADR-0019).
- :data:`V1_TABLES` — lista de tablas activas en V1.

Funciones:

- :func:`caos_path_for` — path absoluto al blob de un hash en CAOS.
- :func:`caos_relative_uri_for` — URI POSIX-relativa al archive root.
- :func:`ensure_archive_layout` — crea la estructura mínima si no existe.
- :func:`is_archive` — heurística de detección no destructiva.

Reglas (ADR-0031 R3): rutas internas del archive son POSIX (``/``) en cualquier
plataforma host. Las rutas absolutas locales sí usan separador nativo, pero
nunca se serializan en estructuras hasheadas.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Final

# --------------------------------------------------------------------- constants

MANIFEST_FILENAME: Final[str] = "manifest.json"
OBJECTS_DIRNAME: Final[str] = "objects"
SHA256_ALGO_DIRNAME: Final[str] = "sha256"
TABLES_DIRNAME: Final[str] = "tables"
AUDIT_LOG_FILENAME: Final[str] = "audit.log"

V1_TABLES: Final[tuple[str, ...]] = (
    "evidence",
    "sources",
    "provenance",
    "provenance_steps",
    # NOTA: ``authentication_assessments`` queda reservada por ADR-0015 pero
    # permanece **vacía** en V1: ``AuthenticationAssessment`` está embebido
    # en :class:`Evidence` (ADR-0023 §V1.3 lo consolida). El directorio se
    # crea de todos modos porque entra en el cómputo de ``blobs_root`` /
    # ``tables_root`` y por tanto contribuye al ``EXPECTED_DEMO_MANIFEST_HASH``
    # pinned. Eliminarlo rompería reproducibilidad bit a bit sin ADR de
    # levantamiento.
    "authentication_assessments",
)
"""Tablas comprometidas por ADR-0023 §V1.3 + V1.4. Diferidas explícitamente:
``claims``, ``hypotheses``, ``hypothesis_sets``, ``conclusions``, ``cases``,
``case_revisions``, ``evidence_links``, ``temporal_anchors``,
``spatial_anchors``, ``graph_nodes``, ``graph_edges``, ``actors``."""


_SHA256_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


# --------------------------------------------------------------------- helpers


def _validate_hash(hash_hex: str) -> None:
    if not _SHA256_HEX_RE.match(hash_hex):
        raise ValueError(
            "expected SHA-256 hex lowercase of length 64, got "
            f"{hash_hex!r} (len={len(hash_hex)})."
        )


def caos_path_for(root: Path, hash_hex: str) -> Path:
    """Path local absoluto del blob identificado por ``hash_hex``.

    Estructura: ``<root>/objects/sha256/<aa>/<rest>`` donde ``aa`` son los
    dos primeros caracteres del hash y ``rest`` los 62 restantes. El uso de
    dos caracteres como prefijo de directorio mantiene cardinalidad de
    inodos por subdir manejable bajo escalas modestas (ADR-0024 §6.3 acepta
    como limitación de V1).
    """
    _validate_hash(hash_hex)
    return root / OBJECTS_DIRNAME / SHA256_ALGO_DIRNAME / hash_hex[:2] / hash_hex[2:]


def caos_relative_uri_for(hash_hex: str) -> str:
    """URI POSIX **relativa** al archive root, sin separador inicial.

    Forma: ``objects/sha256/<aa>/<rest>``. Esta es la cadena que se almacena
    en :attr:`aip.core.evidence.Evidence.content_uri`. POSIX-only para
    cumplir con ADR-0031 R3 (reproducibilidad cross-platform).
    """
    _validate_hash(hash_hex)
    posix = PurePosixPath(OBJECTS_DIRNAME) / SHA256_ALGO_DIRNAME / hash_hex[:2] / hash_hex[2:]
    return str(posix)


def ensure_archive_layout(root: Path) -> None:
    """Crea (o completa) la estructura canónica del archive en ``root``.

    Idempotente. Si la estructura ya existe, no toca nada. Si existe
    parcialmente, completa los directorios faltantes. **No** crea
    ``manifest.json`` ni ``audit.log`` — esos los emite el bootstrap
    transaccional del primer ingest (Pre-F1.D §bootstrap).
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / OBJECTS_DIRNAME / SHA256_ALGO_DIRNAME).mkdir(parents=True, exist_ok=True)
    tables_root = root / TABLES_DIRNAME
    tables_root.mkdir(parents=True, exist_ok=True)
    for table in V1_TABLES:
        (tables_root / table).mkdir(parents=True, exist_ok=True)


def is_archive(root: Path) -> bool:
    """Detecta heurísticamente si ``root`` parece un archive AIP.

    Marcadores requeridos:

    - ``root`` es directorio existente.
    - ``root/objects/sha256/`` existe.
    - ``root/tables/`` existe.
    - ``root/manifest.json`` **o** ``root/audit.log`` existe (al menos uno;
      ambos podrían faltar si el bootstrap quedó interrumpido — en ese caso
      reportar como NO archive es lo más honesto).
    """
    if not root.is_dir():
        return False
    if not (root / OBJECTS_DIRNAME / SHA256_ALGO_DIRNAME).is_dir():
        return False
    if not (root / TABLES_DIRNAME).is_dir():
        return False
    has_manifest = (root / MANIFEST_FILENAME).is_file()
    has_audit = (root / AUDIT_LOG_FILENAME).is_file()
    return has_manifest or has_audit
