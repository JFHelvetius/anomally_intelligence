"""Cobertura del shim ``python -m aip`` (ADR-0017, ADR-0030 §E2).

El módulo ``src/aip/__main__.py`` delega a ``aip.cli.main:main`` y existe para
soportar la invocación ``python -m aip`` en entornos donde el console_script
``aip`` no está en ``PATH``. Tres tipos de cobertura aquí:

1. Importación directa del módulo (tres statements: future, ``import sys``,
   ``from aip.cli.main import main``). El bloque ``if __name__ == "__main__":``
   está marcado ``# pragma: no cover`` porque solo se ejecuta cuando se
   invoca como módulo desde la línea de comandos.

2. Smoke end-to-end vía subprocess: confirma que ``python -m aip --version``
   imprime la versión real del paquete y retorna 0. No contribuye a la
   métrica de coverage (subprocess no instrumentado) pero verifica el
   contrato observable: el usuario que hace ``python -m aip`` obtiene la
   misma respuesta que con el console_script.
"""

from __future__ import annotations

import subprocess
import sys

import aip.__main__ as shim
from aip._version import __version__ as SOFTWARE_VERSION
from aip.cli.main import main as dispatch_main


def test_main_module_imports_cleanly() -> None:
    """Importar el shim ejecuta los statements de nivel módulo.

    El bloque ``if __name__ == "__main__":`` queda excluido por pragma.
    """
    # El shim re-exporta ``main`` desde el dispatcher de la CLI. Verificamos
    # vía ``vars()`` para no depender de ``__all__`` explícito (mypy strict)
    # ni infringir ruff B009 (constant getattr).
    assert vars(shim)["main"] is dispatch_main


def test_python_dash_m_aip_version_smoke() -> None:
    """``python -m aip --version`` retorna 0 e imprime la versión canónica."""
    result = subprocess.run(
        [sys.executable, "-m", "aip", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert SOFTWARE_VERSION in combined
    assert "aip" in combined.lower()
