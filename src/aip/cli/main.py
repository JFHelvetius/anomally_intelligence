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
from aip.cli.attestation_commands import add_attestation_subparser
from aip.cli.capture_commands import add_capture_subparser
from aip.cli.context_commands import add_context_subparser
from aip.cli.diff_commands import add_diff_subparser
from aip.cli.evidence_commands import add_evidence_subparser
from aip.cli.graph_commands import add_graph_subparser
from aip.cli.impact_commands import add_impact_subparser
from aip.cli.justification_commands import add_justification_subparser
from aip.cli.notarize_commands import add_notarize_subparser
from aip.cli.snapshot_commands import add_snapshot_subparser
from aip.cli.timeline_commands import add_timeline_subparser
from aip.cli.transparency_commands import add_transparency_subparser
from aip.cli.verify_commands import add_verify_subparser
from aip.cli.workspace_commands import add_workspace_subparser
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
    # ``graph`` es subgrupo (ADR-0033 §CLI): tres subcomandos comparten
    # dominio "grafo de procedencia derivado". Read-only por contrato.
    add_graph_subparser(subparsers)
    # ``impact`` es subgrupo (ADR-0034 §CLI): dos subcomandos reportan
    # reverse-dependency reachability. Read-only por contrato. Sin
    # scoring, sin severidad, sin probabilidad.
    add_impact_subparser(subparsers)
    # ``context`` es subgrupo (ADR-0035 §CLI): agregación pura de
    # ADR-0032/0033/0034 en un único bundle determinista. Read-only.
    add_context_subparser(subparsers)
    # ``workspace`` es subgrupo (ADR-0036 §CLI): índice reproducible de
    # referencias a artefactos derivados. No ejecuta motores analíticos.
    add_workspace_subparser(subparsers)
    # ``timeline`` es subgrupo (ADR-0037 §CLI): vista cronológica ordenada.
    add_timeline_subparser(subparsers)
    # ``snapshot`` es subgrupo (ADR-0038 §CLI): congelación reference-only.
    add_snapshot_subparser(subparsers)
    # ``diff`` es subgrupo (ADR-0039 §CLI): set-difference puro.
    add_diff_subparser(subparsers)
    # ``justification`` es subgrupo (ADR-0040 §CLI): cadena deductiva
    # categorizada por rol. Read-only — no ejecuta motores productores.
    add_justification_subparser(subparsers)
    # ``verify`` (P5 hardening): universal artifact verifier que
    # auto-detecta el tipo y ejecuta verificación offline. Distinto de
    # ``archive verify`` (audita el archive) — éste audita artefactos.
    add_verify_subparser(subparsers)
    # ``attestation`` es subgrupo (ADR-0041 §CLI): capa de atestación
    # criptográfica ed25519. Vincula artefactos a una clave operada por
    # el firmante; verificación exógena offline.
    add_attestation_subparser(subparsers)
    # ``transparency`` es subgrupo (Phase 1A): publica manifests firmados
    # del estado completo del archive a una cadena append-only para
    # verificación pública sin necesidad de confiar en el operador.
    add_transparency_subparser(subparsers, parents=[common])
    # ``capture`` es subgrupo (Phase 2): firma el SHA-256 de un fichero al
    # momento de adquisición con la clave ed25519 del operador. Extiende
    # la cadena de procedencia hacia atrás en el tiempo, antes del ingest.
    add_capture_subparser(subparsers, parents=[common])
    # ``notarize`` (post-Phase 2): ancla hashes a la blockchain de Bitcoin
    # via OpenTimestamps. Cierra el gap de timestamps operator-supplied —
    # incluso el propio operador no puede backdatar sin reminar Bitcoin.
    add_notarize_subparser(subparsers, parents=[common])

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
