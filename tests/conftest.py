"""Configuración y fixtures compartidos del suite de tests de AIP.

Convenciones (ADR-0031):

- Todo I/O de tests vive bajo ``tmp_path`` de pytest. Ningún test toca el
  filesystem del usuario fuera de su ``tmp_path``.
- Sin red, sin servicios remotos, sin secrets, sin reloj de pared real en
  hashes (los relojes se inyectan).
- Determinismo absoluto: misma entrada → misma salida.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def archive_root(tmp_path: Path) -> Path:
    """Devuelve un path limpio que los tests usan como raíz de archive.

    El directorio existe y está vacío. Los tests invocan helpers de
    ``aip.storage.layout`` para poblar la estructura canónica.
    """
    root = tmp_path / "archive"
    root.mkdir()
    return root
