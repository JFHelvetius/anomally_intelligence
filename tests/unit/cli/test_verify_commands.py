"""Tests del universal artifact verifier (``aip verify``)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
from collections.abc import Callable
from pathlib import Path

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.cli import main as cli_main
from aip.context import assemble_context
from aip.context.assembler import _normalize_for_jcs
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.graph.models import GraphNode, NodeKind
from aip.justification import build_justification, persist_justification
from aip.snapshot import create_snapshot, persist_snapshot
from aip.timeline import build_timeline, persist_timeline
from aip.workspace import create_workspace, persist_workspace

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


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
        clock=_clock(CANONICAL_TS),
    )
    return ev.hash


def _bootstrap(tmp_path: Path, archive_root: Path) -> dict[str, Path]:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    archive = Archive.open(archive_root)
    a = archive.assess_authentication(
        evidence_id=ev_hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_clock(CANONICAL_TS),
        actor="@test",
    )

    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash), ("assessment", a.assessment_id)],
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    tl = build_timeline(archive_root=archive_root, workspace=w, timeline_id="tl-01")
    persist_timeline(
        tl,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    sn = create_snapshot(snapshot_id="s-01", workspace=w, timeline=tl)
    persist_snapshot(
        sn,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a.assessment_id,
        justification_id="j-01",
    )
    persist_justification(
        j,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )

    # Context bundle: assemble + write to disk for test.
    bundle = assemble_context(
        archive_root,
        GraphNode(kind=NodeKind.EVIDENCE, id=ev_hash),
    )
    bundle_dict = dataclasses.asdict(bundle)
    # Normalize tuples → lists for JSON.
    bundle_dict_norm = _normalize_for_jcs(bundle_dict)
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(
        json.dumps(
            bundle_dict_norm,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "workspace": archive_root / "workspaces" / "w-01.json",
        "timeline": archive_root / "timelines" / "tl-01.json",
        "snapshot": archive_root / "snapshots" / "s-01.json",
        "justification": archive_root / "justifications" / "j-01.json",
        "context_bundle": ctx_path,
    }


# ---------------------------------------------------------------- discoverability


def test_verify_command_is_listed() -> None:
    parser = cli_main.build_parser()
    names: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            names.update(str(k) for k in choices)
    assert "verify" in names


# ---------------------------------------------------------------- happy paths


def test_verify_workspace(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(["verify", str(paths["workspace"])])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["artifact_kind"] == "workspace"
    assert payload["artifact_identity"] == "w-01"
    assert payload["self_hash_ok"] is True


def test_verify_timeline(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(["verify", str(paths["timeline"])])
    assert rc == 0
    payload = json.loads(out)
    assert payload["artifact_kind"] == "timeline"
    assert payload["artifact_identity"] == "tl-01"


def test_verify_snapshot(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(["verify", str(paths["snapshot"])])
    assert rc == 0
    payload = json.loads(out)
    assert payload["artifact_kind"] == "snapshot"
    assert payload["artifact_identity"] == "s-01"


def test_verify_justification(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(["verify", str(paths["justification"])])
    assert rc == 0
    payload = json.loads(out)
    assert payload["artifact_kind"] == "justification"
    assert payload["artifact_identity"] == "j-01"


def test_verify_context_bundle(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(["verify", str(paths["context_bundle"])])
    assert rc == 0
    payload = json.loads(out)
    assert payload["artifact_kind"] == "context_bundle"


# ---------------------------------------------------------------- tampering


def test_verify_detects_tampered_workspace(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    p = paths["workspace"]
    data = json.loads(p.read_text(encoding="utf-8"))
    data["title"] = "tampered"
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(["verify", str(p)])
    assert rc == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["self_hash_ok"] is False


def test_verify_detects_tampered_justification(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    p = paths["justification"]
    data = json.loads(p.read_text(encoding="utf-8"))
    data["justification_id"] = "tampered"
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, _, _ = _run(["verify", str(p)])
    assert rc == 1


# ---------------------------------------------------------------- errors


def test_verify_missing_file(tmp_path: Path) -> None:
    rc, _, err = _run(["verify", str(tmp_path / "ghost.json")])
    assert rc != 0
    assert "not found" in err.lower()


def test_verify_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not valid {", encoding="utf-8")
    rc, _, err = _run(["verify", str(p)])
    assert rc != 0
    assert "not valid json" in err.lower()


def test_verify_unrecognized_artifact_type(tmp_path: Path) -> None:
    p = tmp_path / "weird.json"
    p.write_text(
        json.dumps({"foo": "bar", "baz": 42}, indent=2),
        encoding="utf-8",
    )
    rc, _, err = _run(["verify", str(p)])
    assert rc != 0
    assert "could not detect artifact type" in err.lower()


def test_verify_root_not_object(tmp_path: Path) -> None:
    p = tmp_path / "array.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    rc, _, err = _run(["verify", str(p)])
    assert rc != 0
    assert "json object" in err.lower()


# ---------------------------------------------------------------- against-archive


def test_verify_against_archive_clean(tmp_path: Path, archive_root: Path) -> None:
    """Workspace válido + archive sin cambios → no drift."""
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(
        [
            "verify",
            str(paths["workspace"]),
            "--against-archive",
            str(archive_root),
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["archive_drift"]["ok"] is True


def test_verify_against_archive_detects_source_manifest_drift(
    tmp_path: Path, archive_root: Path
) -> None:
    """Tras alterar el archive (nuevo assessment), el justification queda
    con source_manifest_hash desactualizado."""
    paths = _bootstrap(tmp_path, archive_root)
    # Crear OTRO assessment → manifest cambia.
    archive = Archive.open(archive_root)
    ev_hash = next((archive_root / "tables" / "evidence").glob("*.parquet")).stem
    archive.assess_authentication(
        evidence_id=ev_hash,
        method=AssessmentMethod.MANUAL_RESEARCH,
        clock=_clock(CANONICAL_TS),
        actor="@test",
    )
    rc, out, _ = _run(
        [
            "verify",
            str(paths["justification"]),
            "--against-archive",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["self_hash_ok"] is True  # estructura intacta
    assert payload["archive_drift"]["ok"] is False
    assert any(
        "source_manifest_hash drift" in issue for issue in payload["archive_drift"]["issues"]
    )


def test_verify_against_archive_detects_workspace_link_broken(
    tmp_path: Path, archive_root: Path
) -> None:
    """Borrar el workspace y verificar una justification que lo referencia."""
    paths = _bootstrap(tmp_path, archive_root)
    (archive_root / "workspaces" / "w-01.json").unlink()
    # Esta justification no fue construida con workspace_id, así que
    # workspace_hash en su JSON puede ser None. Verificamos con un
    # snapshot que sí tiene workspace_hash.
    rc, out, _ = _run(
        [
            "verify",
            str(paths["snapshot"]),
            "--against-archive",
            str(archive_root),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert any(
        "workspace_hash" in issue and "not\n" not in issue
        for issue in payload["archive_drift"]["issues"]
    ) or any("workspace_hash" in issue for issue in payload["archive_drift"]["issues"])


def test_verify_against_archive_invalid_path(tmp_path: Path, archive_root: Path) -> None:
    paths = _bootstrap(tmp_path, archive_root)
    rc, out, _ = _run(
        [
            "verify",
            str(paths["workspace"]),
            "--against-archive",
            str(tmp_path / "ghost"),
        ]
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["archive_drift"]["ok"] is False


# ---------------------------------------------------------------- backwards compat


def test_existing_verify_subcommands_still_work(tmp_path: Path, archive_root: Path) -> None:
    """Los verify específicos por tipo deben seguir funcionando."""
    paths = _bootstrap(tmp_path, archive_root)
    rc_w, _, _ = _run(["workspace", "verify", str(paths["workspace"])])
    rc_t, _, _ = _run(["timeline", "verify", str(paths["timeline"])])
    rc_s, _, _ = _run(["snapshot", "verify", str(paths["snapshot"])])
    rc_j, _, _ = _run(["justification", "verify", str(paths["justification"])])
    assert rc_w == 0
    assert rc_t == 0
    assert rc_s == 0
    assert rc_j == 0


def test_archive_verify_unaffected_by_new_command(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap(tmp_path, archive_root)
    rc, _, _ = _run(["archive", "verify", "--archive-root", str(archive_root)])
    assert rc == 0
