"""Entry point ``python -m aip`` (ADR-0017)."""

from __future__ import annotations

import sys

from aip.cli.main import main

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
