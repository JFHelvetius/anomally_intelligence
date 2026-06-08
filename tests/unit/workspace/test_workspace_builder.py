"""Tests del builder + persistence + hashes del Workspace (ADR-0036)."""

from __future__ import annotations

import ast
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.storage import layout
from aip.workspace import (
    InvestigationWorkspace,
    WorkspaceNotFoundError,
    WorkspaceReference,
    compute_artifact_hash,
    compute_workspace_hash,
    create_workspace,
    decode_workspace,
    encode_workspace,
    load_workspace,
    persist_workspace,
    verify_workspace_hash,
    workspace_path,
)

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _ingest(archive_root: Path, blob: Path) -> str:
    archive = Archive.open(archive_root)
    ev = archive.ingest_evidence(
        blob,
        source_id="blue-book-nara",
        source_name="Project Blue Book records",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@jfhelvetius",
        clock=_fixed_clock(CANONICAL_TS),
    )
    return ev.hash


def _write_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _references_input() -> list[tuple[str, str]]:
    return [
        ("evidence", "E001"),
        ("evidence", "E005"),
        ("assessment", "A002"),
        ("impact_analysis", "I003"),
        ("context_bundle", "C001"),
    ]


# ---------------------------------------------------------------- create


def test_create_workspace_constructs_valid_model(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="fraud-chain-01",
        title="Fraud Investigation",
        references_input=_references_input(),
    )
    assert w.workspace_id == "fraud-chain-01"
    assert w.title == "Fraud Investigation"
    assert len(w.references) == 5
    # Sorted canonically.
    keys = [(r.reference_type, r.identifier) for r in w.references]
    assert keys == sorted(keys)


def test_create_raises_when_archive_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_workspace(
            archive_root=tmp_path / "ghost",
            workspace_id="x",
            title="t",
            references_input=[],
        )


def test_create_raises_on_duplicate_references(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(ValueError, match="duplicate"):
        create_workspace(
            archive_root=archive_root,
            workspace_id="x",
            title="t",
            references_input=[("evidence", "E1"), ("evidence", "E1")],
        )


def test_create_raises_on_invalid_reference_type(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(ValueError, match="invalid reference_type"):
        create_workspace(
            archive_root=archive_root,
            workspace_id="x",
            title="t",
            references_input=[("hypothesis", "H1")],
        )


# ---------------------------------------------------------------- determinism


def test_workspace_hash_is_deterministic_across_runs(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w1 = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    w2 = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    assert w1 == w2
    assert w1.workspace_hash == w2.workspace_hash


def test_workspace_hash_changes_with_input_order_is_canonical(
    tmp_path: Path, archive_root: Path
) -> None:
    """Cambiar el orden de input no cambia el workspace_hash (canonical)."""
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    forward = _references_input()
    reverse = list(reversed(forward))
    w1 = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=forward,
    )
    w2 = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=reverse,
    )
    assert w1.workspace_hash == w2.workspace_hash


# ---------------------------------------------------------------- verify


def test_verify_workspace_hash_success(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    assert verify_workspace_hash(w) is True


def test_verify_workspace_hash_failure_on_tampering() -> None:
    """Workspace construido a mano con hash incorrecto → verify False."""
    refs = (
        WorkspaceReference(
            reference_type="evidence",
            identifier="E001",
            artifact_hash=compute_artifact_hash("evidence", "E001"),
        ),
    )
    bad = InvestigationWorkspace(
        workspace_id="x",
        title="t",
        references=refs,
        source_manifest_hash="f" * 64,
        workspace_hash="b" * 64,  # incorrecto
    )
    assert verify_workspace_hash(bad) is False


def test_compute_workspace_hash_matches_verify_round(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    assert compute_workspace_hash(w) == w.workspace_hash


# ---------------------------------------------------------------- encoding


def test_encode_workspace_produces_canonical_json(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    payload = encode_workspace(w)
    parsed = json.loads(payload)
    canonical = json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert payload == canonical


def test_roundtrip_decode_encode_preserves_identity(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    payload = encode_workspace(w)
    decoded = decode_workspace(payload)
    assert decoded == w
    assert decoded.workspace_hash == w.workspace_hash


# ---------------------------------------------------------------- persistence


def test_persist_workspace_writes_canonical_location(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="fraud-chain-01",
        title="t",
        references_input=_references_input(),
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    canonical = workspace_path(archive_root, "fraud-chain-01")
    assert canonical.is_file()
    assert canonical.parent.name == "workspaces"


def test_persist_workspace_also_writes_extra_output(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    extra = tmp_path / "external" / "workspace.json"
    persist_workspace(
        w,
        archive_root=archive_root,
        extra_output=extra,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    canonical = workspace_path(archive_root, "x")
    assert extra.read_bytes() == canonical.read_bytes()


def test_load_workspace_reads_canonical_location(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="x",
        title="t",
        references_input=_references_input(),
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    loaded = load_workspace(archive_root=archive_root, workspace_id="x")
    assert loaded == w


def test_load_workspace_raises_when_missing(tmp_path: Path, archive_root: Path) -> None:
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    with pytest.raises(WorkspaceNotFoundError):
        load_workspace(archive_root=archive_root, workspace_id="ghost")


# ---------------------------------------------------------------- removability


def test_workspace_persistence_does_not_modify_archive_manifest(
    tmp_path: Path, archive_root: Path
) -> None:
    """G2 + G5: persistir un workspace no toca el manifest del archive.

    El directorio ``<archive>/workspaces/`` no entra en ``V1_TABLES``
    ni en ``compute_manifest``, por tanto ``archive_manifest_hash`` es
    invariante bit a bit ante operaciones de workspace.
    """
    blob = _write_blob(tmp_path, "doc.pdf", b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    pre_hash = archive.verify(full=True).archive_manifest_hash
    manifest_bytes_pre = (archive_root / layout.MANIFEST_FILENAME).read_bytes()

    w = create_workspace(
        archive_root=archive_root,
        workspace_id="fraud-chain-01",
        title="t",
        references_input=_references_input(),
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )

    post_hash = archive.verify(full=True).archive_manifest_hash
    manifest_bytes_post = (archive_root / layout.MANIFEST_FILENAME).read_bytes()

    assert pre_hash == post_hash
    assert manifest_bytes_pre == manifest_bytes_post


# ---------------------------------------------------------------- G3 (no engines)


def test_workspace_imports_no_engines() -> None:
    """ADR-0036 §G3: ningún módulo de ``aip.workspace`` importa de las
    capas analíticas derivadas (``analysis``, ``graph``, ``impact``,
    ``context``). Verificación estática vía AST.
    """
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "workspace"
    forbidden_subpaquetes = {"analysis", "graph", "impact", "context"}
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "aip" and parts[1] in forbidden_subpaquetes:
                    offenders.append((module_path.name, node.module))
            elif isinstance(node, ast.Import):
                for n in node.names:
                    parts = n.name.split(".")
                    if len(parts) >= 2 and parts[0] == "aip" and parts[1] in forbidden_subpaquetes:
                        offenders.append((module_path.name, n.name))
    assert offenders == [], f"workspace/ imports forbidden analytical engines: {offenders}"
