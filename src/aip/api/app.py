"""FastAPI application factory para AIP (Phase 1 — read-only)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aip._version import __version__
from aip.api.routes import (
    analyze,
    archive,
    attestations,
    audit,
    cases,
    derived,
    evidence,
    inference_proofs,
    transparency,
)

_STATIC_DIR = Path(__file__).parent.parent.parent.parent / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Anomaly Intelligence Platform",
        version=__version__,
        description="Evidence-first archive — read-only HTTP API (Phase 1).",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(archive.router, prefix="/api")
    app.include_router(analyze.router, prefix="/api")
    app.include_router(evidence.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(attestations.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(derived.router, prefix="/api")
    app.include_router(transparency.router, prefix="/api")
    app.include_router(inference_proofs.router, prefix="/api")

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

    return app


app = create_app()
