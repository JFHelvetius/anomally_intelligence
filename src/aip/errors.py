"""Excepciones tipadas del paquete `aip`.

La jerarquía mapea a códigos de salida de la CLI declarados en
`docs/phase-1/command-specification.md` §G5. Toda excepción levantada por la
API pública deriva de :class:`AIPError`.

La política operativa es:

- Sin captura silenciosa: la API Python propaga; la CLI captura solo en el
  borde y mapea a (exit code, mensaje).
- Sin códigos numéricos crípticos: el código entero vive como atributo de la
  excepción para que la CLI no duplique constantes.
"""

from __future__ import annotations


class AIPError(Exception):
    """Base abstracta de todas las excepciones del proyecto.

    Mapea a exit code 1 salvo que una subclase declare otro valor.
    """

    cli_exit_code: int = 1


class UsageError(AIPError):
    """Uso inválido de la CLI (argumentos contradictorios, falta de obligatorios).

    Mapea a exit code 64 (``sysexits.h`` ``EX_USAGE``).
    """

    cli_exit_code = 64


class ArchiveNotFoundError(AIPError):
    """La raíz del archive no existe o no es un archive AIP válido."""

    cli_exit_code = 1


class EvidenceNotFoundError(AIPError):
    """No existe evidencia con el hash solicitado en este archive."""

    cli_exit_code = 1


class InvalidSourceMetadataError(AIPError):
    """Los metadatos de :class:`Source` son incompletos o inconsistentes con la
    fuente ya registrada con el mismo ``source_id``."""

    cli_exit_code = 1


class IntegrityError(AIPError):
    """Un blob no coincide con el hash que lo identifica.

    Es error crítico: la región afectada del archive no puede usarse hasta
    diagnóstico. Mapea a exit code 3.
    """

    cli_exit_code = 3


class AuditChainError(AIPError):
    """La cadena de hashes del audit log es inconsistente.

    Causas plausibles: tampering, corrupción de disco, escritura concurrente
    no protegida. Mapea a exit code 2.
    """

    cli_exit_code = 2


class ManifestError(AIPError):
    """El ``ArchiveManifest`` es inconsistente con el estado real de tablas o blobs."""

    cli_exit_code = 4
