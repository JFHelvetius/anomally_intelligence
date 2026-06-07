"""Dispatcher principal de la CLI ``aip`` (Pre-F1.D, ADR-0017).

Construye el parser argparse, ejecuta el subcomando, captura :class:`AIPError`
y mapea a códigos de salida conforme a ``docs/phase-1/command-specification.md``
§G5.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import IO

from aip._version import __version__ as SOFTWARE_VERSION
from aip.cli.archive_commands import add_archive_subparser
from aip.cli.assessment_commands import (
    add_assessment_subparser,
    add_list_assessments_subparser,
)
from aip.cli.evidence_commands import add_evidence_subparser
from aip.errors import AIPError, UsageError

DEFAULT_ARCHIVE_ROOT_ENV: str = "AIP_ARCHIVE_ROOT"
DEFAULT_ARCHIVE_ROOT: Path = Path.home() / ".aip"


def _resolve_archive_root(value: str | None) -> Path:
    if value is not None:
        return Path(value)
    env = os.environ.get(DEFAULT_ARCHIVE_ROOT_ENV)
    if env:
        return Path(env)
    return DEFAULT_ARCHIVE_ROOT


def _build_common_parent() -> argparse.ArgumentParser:
    """Padre con las opciones globales para que sean válidas tanto antes
    como después del subcomando (e.g., ``aip --json verify`` y
    ``aip verify --json``)."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--archive-root",
        default=None,
        help="Path al archive AIP. Default: $AIP_ARCHIVE_ROOT, o ~/.aip.",
    )
    parent.add_argument(
        "--json",
        action="store_true",
        help="Output JSON en stdout.",
    )
    parent.add_argument(
        "--quiet",
        action="store_true",
        help="Suprime output salvo errores.",
    )
    parent.add_argument(
        "--verbose",
        action="store_true",
        help="Logging adicional a stderr.",
    )
    return parent


def build_parser() -> argparse.ArgumentParser:
    """Top-level parser.

    Estilo CLI: las opciones globales (--archive-root, --json, --quiet,
    --verbose) viven en los **subcomandos** vía ``parents=[common]``.
    Ejemplo: ``aip archive verify --archive-root /tmp/x --json``. El
    top-level solo expone ``--version`` y ``--help``.
    """
    common = _build_common_parent()
    parser = argparse.ArgumentParser(
        prog="aip",
        description=(
            "Anomaly Intelligence Platform — evidence-first archive. "
            "V1 entrega ingest/show/verify. Ver docs/phase-1/."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"aip {SOFTWARE_VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    add_evidence_subparser(subparsers, parents=[common])
    add_archive_subparser(subparsers, parents=[common])
    # ``assess-authentication`` no comparte el padre común: su contrato
    # (ADR-0032 §5) lista exactamente ``--archive`` y ``--evidence-id`` y
    # emite siempre JSON. Sin ``--archive-root``, ``--quiet``, etc.
    add_assessment_subparser(subparsers)
    # ``list-assessments`` es la simetría de lectura: enumera assessments
    # persistidos sin modificar el archive. Mismo estilo flat.
    add_list_assessments_subparser(subparsers)

    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
) -> int:
    """Punto de entrada de la CLI.

    Args:
        argv: argumentos (sin el nombre del programa). Si ``None``, usa
            ``sys.argv[1:]``.
        stdout: stream de output canónico. Si ``None``, ``sys.stdout``.
        stderr: stream de errores. Si ``None``, ``sys.stderr``.

    Returns:
        Exit code (entero).
    """
    if stdout is None:
        stdout = sys.stdout
    if stderr is None:
        stderr = sys.stderr

    parser = build_parser()
    args = parser.parse_args(argv)

    # Reglas de globals: --json + --quiet son contradictorios. Solo aplican
    # a subcomandos que las exponen (assess-authentication no las tiene).
    if getattr(args, "json", False) and getattr(args, "quiet", False):
        stderr.write("aip: --json and --quiet are mutually exclusive.\n")
        return UsageError.cli_exit_code

    if hasattr(args, "archive_root"):
        args.archive_root = _resolve_archive_root(args.archive_root)

    cmd = getattr(args, "_cmd", None)
    if cmd is None:
        parser.print_help(stderr)
        return UsageError.cli_exit_code

    try:
        return int(cmd(args, stdout=stdout))
    except AIPError as exc:
        stderr.write(f"aip: {type(exc).__name__}: {exc}\n")
        return exc.cli_exit_code
    except FileNotFoundError as exc:
        stderr.write(f"aip: file not found: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
