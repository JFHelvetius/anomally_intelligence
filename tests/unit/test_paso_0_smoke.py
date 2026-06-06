"""Smoke tests del Paso 0 — esqueleto del paquete.

Verifican que el andamiaje mínimo está en pie:

- El paquete ``aip`` importa.
- ``__version__`` se expone.
- La jerarquía de excepciones existe con los códigos de salida canónicos
  declarados en ``docs/phase-1/command-specification.md`` §G5.
"""

from __future__ import annotations

import aip


def test_version_is_semver_shaped() -> None:
    assert isinstance(aip.__version__, str)
    assert aip.__version__.count(".") >= 2


def test_error_hierarchy_root() -> None:
    assert issubclass(aip.UsageError, aip.AIPError)
    assert issubclass(aip.ArchiveNotFoundError, aip.AIPError)
    assert issubclass(aip.EvidenceNotFoundError, aip.AIPError)
    assert issubclass(aip.InvalidSourceMetadataError, aip.AIPError)
    assert issubclass(aip.IntegrityError, aip.AIPError)
    assert issubclass(aip.AuditChainError, aip.AIPError)
    assert issubclass(aip.ManifestError, aip.AIPError)


def test_cli_exit_codes_match_spec() -> None:
    # docs/phase-1/command-specification.md §G5.
    assert aip.UsageError().cli_exit_code == 64
    assert aip.ArchiveNotFoundError().cli_exit_code == 1
    assert aip.EvidenceNotFoundError().cli_exit_code == 1
    assert aip.InvalidSourceMetadataError().cli_exit_code == 1
    assert aip.AuditChainError().cli_exit_code == 2
    assert aip.IntegrityError().cli_exit_code == 3
    assert aip.ManifestError().cli_exit_code == 4


def test_aipbase_default_exit_code() -> None:
    assert aip.AIPError().cli_exit_code == 1
