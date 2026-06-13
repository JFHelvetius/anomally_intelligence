"""Dependencias FastAPI compartidas."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException

from aip.archive import Archive
from aip.errors import AIPError


@lru_cache(maxsize=1)
def _archive_path() -> Path:
    raw = os.environ.get("AIP_ARCHIVE_PATH", "")
    if not raw:
        raise RuntimeError(
            "AIP_ARCHIVE_PATH env var not set. "
            "Start the server with: AIP_ARCHIVE_PATH=/path/to/archive aip-web"
        )
    return Path(raw)


def get_archive() -> Archive:
    try:
        return Archive.open(_archive_path())
    except AIPError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


ArchiveDep = Annotated[Archive, Depends(get_archive)]
