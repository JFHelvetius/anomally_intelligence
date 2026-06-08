"""Tests del helper ``atomic_write_text`` (storage/atomic_io.py).

Verifica las dos propiedades operativas:

- write-to-tmp + os.replace deja el destino canónico bit-correcto.
- Tras un write exitoso, no quedan ``.tmp`` residuales en el directorio.

La propiedad de atomicidad estricta bajo crash mid-write se hereda de
``os.replace`` (atómico en POSIX y Windows). No la testamos directamente
— testamos que el patrón se aplica.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from aip import Archive
from aip.attestation import (
    generate_keypair,
    persist_attestation,
    sign_artifact,
)
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.justification import build_justification, persist_justification
from aip.snapshot import create_snapshot, persist_snapshot
from aip.storage.atomic_io import atomic_write_text
from aip.timeline import build_timeline, persist_timeline
from aip.workspace import create_workspace, persist_workspace

UTC = dt.UTC
T0 = dt.datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime):
    return lambda: ts


# ---------------------------------------------------------------- primitive


def test_atomic_write_text_writes_canonical(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    atomic_write_text(target, '{"k": 1}\n')
    assert target.read_text(encoding="utf-8") == '{"k": 1}\n'


def test_atomic_write_text_creates_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "out.json"
    atomic_write_text(target, "payload")
    assert target.is_file()


def test_atomic_write_text_no_tmp_residual(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    atomic_write_text(target, "payload")
    residuals = list(tmp_path.glob("*.tmp"))
    assert residuals == []


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


# ---------------------------------------------------------------- persist_* propagation


def _seed_evidence(tmp_path: Path, archive_root: Path) -> str:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    arc = Archive.open(archive_root)
    ev = arc.ingest_evidence(
        blob,
        source_id="src",
        source_name="NARA",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by="@op",
        clock=_clock(T0),
    )
    return ev.hash


@pytest.mark.parametrize("artifact_dir", [
    "workspaces",
    "timelines",
    "snapshots",
    "justifications",
    "attestations",
])
def test_persist_leaves_no_tmp_residuals(
    tmp_path: Path, archive_root: Path, artifact_dir: str
) -> None:
    """Tras un pipeline completo, ningún directorio derivado debe
    contener ficheros ``.tmp`` huérfanos del helper atómico.
    """
    ev_hash = _seed_evidence(tmp_path, archive_root)

    archive = Archive.open(archive_root)
    a = archive.assess_authentication(
        evidence_id=ev_hash, actor="@r", clock=_clock(T0)
    )
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash), ("assessment", a.assessment_id)],
    )
    persist_workspace(
        w, archive_root=archive_root, actor="@op", clock=_clock(T0)
    )
    t = build_timeline(
        archive_root=archive_root, workspace=w, timeline_id="tl-01"
    )
    persist_timeline(
        t, archive_root=archive_root, actor="@op", clock=_clock(T0)
    )
    s = create_snapshot(snapshot_id="s-01", workspace=w, timeline=t)
    persist_snapshot(
        s, archive_root=archive_root, actor="@op", clock=_clock(T0)
    )
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a.assessment_id,
        justification_id="j-01",
        workspace_id=w.workspace_id,
    )
    persist_justification(
        j, archive_root=archive_root, actor="@op", clock=_clock(T0)
    )
    priv, _pub = generate_keypair()
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=archive_root / "workspaces" / "w-01.json",
        private_key=priv,
        signer_id="@op",
        signed_at=T0,
    )
    persist_attestation(
        att,
        archive_root=archive_root,
        attestation_id="att-01",
        actor="@op",
        clock=_clock(T0),
    )

    d = archive_root / artifact_dir
    if d.is_dir():
        residuals = list(d.glob("*.tmp"))
        assert residuals == [], (
            f"{artifact_dir}/ contains stray .tmp residuals: {residuals}"
        )


def test_persist_workspace_extra_output_is_atomic(
    tmp_path: Path, archive_root: Path
) -> None:
    """``extra_output`` también pasa por atomic_write_text."""
    ev_hash = _seed_evidence(tmp_path, archive_root)
    extra = tmp_path / "shared" / "ws-extra.json"
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash)],
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@op",
        clock=_clock(T0),
        extra_output=extra,
    )
    assert extra.is_file()
    assert not (tmp_path / "shared" / "ws-extra.json.tmp").exists()
