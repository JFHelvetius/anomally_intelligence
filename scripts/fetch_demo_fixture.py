#!/usr/bin/env python3
"""Helper para Pre-F1.C — descarga el PDF fixture de la demo y emite Pinned values.

Uso:

    python scripts/fetch_demo_fixture.py \
        --url <URL exacta de la fuente pública estable> \
        --target tests/data/twining-memo-1947-09-23.pdf \
        --actor @jfhelvetius

El script:

1. Descarga la URL en streaming (sin cargar el blob entero en memoria).
2. Computa SHA-256 sobre los bytes crudos (canónico, hex lowercase, longitud 64).
3. Copia el binario al target indicado.
4. Anota el tamaño en bytes y el timestamp UTC de la descarga.
5. Imprime un bloque Markdown listo para pegar en la sección "Pinned values"
   de docs/phase-1/demo-evidence-selection.md.

No es código de producción. No vive en src/aip/. No tiene tests bajo ADR-0031.
Es una utilidad auxiliar que el mantenedor ejecuta una vez para cerrar la
acción operativa Pre-F1.C.

Restricciones de diseño:

- Solo stdlib (urllib + hashlib + pathlib + argparse + datetime). Sin pip install.
- Sin red salvo la URL explícita pasada por argumento.
- Sin fabricación: si la descarga falla, el script falla; nunca emite valores
  inventados.
- Sin escritura de los pinned values en el documento; solo los imprime. La
  inserción en el documento es acto humano (commit explícito).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

CHUNK_SIZE = 64 * 1024


def fetch(url: str, dest: Path) -> tuple[str, int]:
    """Descarga la URL a dest computando SHA-256 en streaming.

    Returns:
        (sha256_hex_lowercase, size_bytes)
    """
    hasher = hashlib.sha256()
    size = 0
    dest.parent.mkdir(parents=True, exist_ok=True)

    # User-Agent honesto: identificarse como el helper del proyecto.
    request = Request(
        url,
        headers={
            "User-Agent": "anomaly-intelligence-platform/pre-f1-fixture-fetch",
        },
    )

    with tempfile.NamedTemporaryFile(
        prefix=dest.name + ".",
        suffix=".part",
        dir=dest.parent,
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        try:
            with urlopen(request) as response:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
            tmp.flush()
        except BaseException:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise

    shutil.move(str(tmp_path), str(dest))
    return hasher.hexdigest(), size


def verify_post_move(dest: Path, expected_sha256: str, expected_size: int) -> None:
    """Relee el fichero final y verifica que coincide con lo descargado."""
    hasher = hashlib.sha256()
    size = 0
    with dest.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
            size += len(chunk)
    if hasher.hexdigest() != expected_sha256:
        raise RuntimeError(
            f"post-move SHA-256 mismatch: expected {expected_sha256}, "
            f"got {hasher.hexdigest()}"
        )
    if size != expected_size:
        raise RuntimeError(
            f"post-move size mismatch: expected {expected_size}, got {size}"
        )


def emit_pinned_block(
    *,
    url: str,
    target: Path,
    sha256_hex: str,
    size_bytes: int,
    actor: str,
    now_utc: dt.datetime,
) -> str:
    """Produce el bloque Markdown listo para pegar."""
    date_str = now_utc.strftime("%Y-%m-%d")
    return (
        "### Demo fixture (primary candidate)\n"
        "\n"
        '- **Document:** Twining Memo (AMC Opinion Concerning "Flying Discs"), 1947-09-23\n'
        f"- **Source URL:** {url}\n"
        f"- **Download date:** {date_str}\n"
        f"- **File size (bytes):** {size_bytes}\n"
        f"- **SHA-256 (hex, lowercase):** {sha256_hex}\n"
        "- **MIME type:** application/pdf\n"
        f"- **Local fixture path:** {target.as_posix()}\n"
        f"- **Selected by:** {actor}\n"
        f"- **Selected at:** {date_str}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga el PDF fixture de la demo y emite el bloque de Pinned values "
            "para Pre-F1.C. No edita demo-evidence-selection.md automáticamente."
        ),
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL exacta de la fuente pública estable del Twining Memo (1947-09-23).",
    )
    parser.add_argument(
        "--target",
        default="tests/data/twining-memo-1947-09-23.pdf",
        help="Ruta destino del binario versionado (default: tests/data/twining-memo-1947-09-23.pdf).",
    )
    parser.add_argument(
        "--actor",
        required=True,
        help="ActorId del mantenedor que ejecuta la selección (e.g., @jfhelvetius).",
    )
    args = parser.parse_args()

    target = Path(args.target)
    now_utc = dt.datetime.now(dt.timezone.utc)

    print(f"[fetch] downloading {args.url}", file=sys.stderr)
    try:
        sha256_hex, size_bytes = fetch(args.url, target)
    except Exception as exc:
        print(f"[fetch] FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        f"[fetch] wrote {size_bytes} bytes to {target} (sha256={sha256_hex})",
        file=sys.stderr,
    )

    try:
        verify_post_move(target, sha256_hex, size_bytes)
    except Exception as exc:
        print(f"[verify] FAILED: {exc}", file=sys.stderr)
        return 2

    print("[verify] OK: bytes-on-disk match streamed hash", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "[output] Paste the following block into "
        "docs/phase-1/demo-evidence-selection.md under 'Pinned values':",
        file=sys.stderr,
    )
    print("", file=sys.stderr)

    print(
        emit_pinned_block(
            url=args.url,
            target=target,
            sha256_hex=sha256_hex,
            size_bytes=size_bytes,
            actor=args.actor,
            now_utc=now_utc,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
