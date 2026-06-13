"""Entry point ``aip-web`` — arranca el servidor uvicorn."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="aip-web",
        description="AIP HTTP server (FastAPI + uvicorn). Read-only Phase 1.",
    )
    parser.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path to the AIP archive directory.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev).")
    args = parser.parse_args(argv)

    archive_path = args.archive.resolve()
    if not archive_path.is_dir():
        print(f"error: archive path does not exist: {archive_path}", file=sys.stderr)
        sys.exit(1)

    os.environ["AIP_ARCHIVE_PATH"] = str(archive_path)

    try:
        import uvicorn
    except ImportError:
        print(
            "error: uvicorn not installed. Run: pip install 'aip[web]'",
            file=sys.stderr,
        )
        sys.exit(1)

    uvicorn.run(
        "aip.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
