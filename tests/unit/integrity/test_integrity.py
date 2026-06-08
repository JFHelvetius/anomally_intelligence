"""Tests del checker de integridad referencial cruzada."""

from __future__ import annotations

import ast
import datetime as dt
import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.analysis.authentication import AssessmentMethod
from aip.cli import main as cli_main
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.integrity import (
    INTEGRITY_ENGINE_VERSION,
    INTEGRITY_METHOD_NAME,
    DerivedIntegrityIssue,
    DerivedIntegrityReport,
    IntegrityIssueKind,
    verify_derived_integrity,
)
from aip.justification import build_justification, persist_justification
from aip.snapshot import create_snapshot, persist_snapshot
from aip.timeline import build_timeline, persist_timeline
from aip.workspace import create_workspace, persist_workspace

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)


def _clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
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
        clock=_clock(CANONICAL_TS),
    )
    return ev.hash


def _assess(archive_root: Path, ev_hash: str) -> str:
    archive = Archive.open(archive_root)
    a = archive.assess_authentication(
        evidence_id=ev_hash,
        method=AssessmentMethod.PROVENANCE_REVIEW,
        clock=_clock(CANONICAL_TS),
        actor="@test",
    )
    return a.assessment_id


def _bootstrap_full_pipeline(
    tmp_path: Path, archive_root: Path
) -> tuple[str, str, str, str, str, str]:
    """Crea pipeline canónico: evidence, assessment, workspace, timeline,
    snapshot, justification. Devuelve (ev_hash, a_id, w_id, tl_id, s_id, j_id).
    """
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    ev_hash = _ingest(archive_root, blob)
    a_id = _assess(archive_root, ev_hash)
    w = create_workspace(
        archive_root=archive_root,
        workspace_id="w-01",
        title="t",
        references_input=[("evidence", ev_hash), ("assessment", a_id)],
    )
    persist_workspace(
        w,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    t = build_timeline(
        archive_root=archive_root,
        workspace=w,
        timeline_id="tl-01",
    )
    persist_timeline(
        t,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    s = create_snapshot(snapshot_id="s-01", workspace=w, timeline=t)
    persist_snapshot(
        s,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    j = build_justification(
        archive_root=archive_root,
        conclusion_anchor_type="assessment",
        conclusion_anchor_id=a_id,
        justification_id="j-01",
        workspace_id="w-01",
    )
    persist_justification(
        j,
        archive_root=archive_root,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    return ev_hash, a_id, "w-01", "tl-01", "s-01", "j-01"


# ---------------------------------------------------------------- constants


def test_engine_version_is_semver() -> None:
    parts = INTEGRITY_ENGINE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_method_name_pinned() -> None:
    assert INTEGRITY_METHOD_NAME == "structural_referential_v1"


def test_issue_kind_taxonomy_closed() -> None:
    assert {k.value for k in IntegrityIssueKind} == {
        "hash_mismatch",
        "manifest_drift",
        "workspace_link_broken",
        "timeline_link_broken",
        "evidence_reference_dangling",
        "source_reference_dangling",
        "assessment_reference_dangling",
        "provenance_step_dangling",
        "decode_error",
    }


# ---------------------------------------------------------------- error paths


def test_verify_raises_when_archive_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_derived_integrity(tmp_path / "ghost")


def test_verify_raises_when_not_an_archive(archive_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_derived_integrity(archive_root)


# ---------------------------------------------------------------- happy path


def test_verify_clean_archive_no_issues(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    report = verify_derived_integrity(archive_root)
    assert report.ok is True
    assert report.issues == ()
    assert report.workspaces_checked == 1
    assert report.timelines_checked == 1
    assert report.snapshots_checked == 1
    assert report.justifications_checked == 1
    assert report.total_checked == 4


def test_verify_no_derived_artifacts_returns_empty_report(
    tmp_path: Path, archive_root: Path
) -> None:
    blob = tmp_path / "doc.pdf"
    blob.write_bytes(b"%PDF-1.4 sample")
    _ingest(archive_root, blob)
    report = verify_derived_integrity(archive_root)
    assert report.ok is True
    assert report.workspaces_checked == 0
    assert report.timelines_checked == 0
    assert report.snapshots_checked == 0
    assert report.justifications_checked == 0


# ---------------------------------------------------------------- workspace tampering


def test_detects_workspace_hash_mismatch(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    # Tamper workspace.
    wp = archive_root / "workspaces" / "w-01.json"
    data = json.loads(wp.read_text(encoding="utf-8"))
    data["title"] = "tampered"
    wp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = verify_derived_integrity(archive_root)
    assert report.ok is False
    hash_mismatches = [
        i
        for i in report.issues
        if i.issue_kind == IntegrityIssueKind.HASH_MISMATCH.value and i.artifact_kind == "workspace"
    ]
    assert len(hash_mismatches) == 1


def test_detects_workspace_evidence_dangling(tmp_path: Path, archive_root: Path) -> None:
    """Borrar la fila de evidence deja el workspace con referencia rota."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    # Borrar el row de evidence (rompe referencia).
    evidence_files = list((archive_root / "tables" / "evidence").glob("*.parquet"))
    assert len(evidence_files) == 1
    evidence_files[0].unlink()
    report = verify_derived_integrity(archive_root)
    assert report.ok is False
    dangling = [
        i
        for i in report.issues
        if i.issue_kind == IntegrityIssueKind.EVIDENCE_REFERENCE_DANGLING.value
    ]
    # Esperamos múltiples (workspace + timeline + snapshot + justification).
    assert len(dangling) >= 1


def test_detects_workspace_decode_error(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    wp = archive_root / "workspaces" / "w-01.json"
    wp.write_text("not valid json {", encoding="utf-8")
    report = verify_derived_integrity(archive_root)
    decode_errors = [
        i
        for i in report.issues
        if i.issue_kind == IntegrityIssueKind.DECODE_ERROR.value and i.artifact_kind == "workspace"
    ]
    assert len(decode_errors) == 1


# ---------------------------------------------------------------- timeline tampering


def test_detects_timeline_hash_mismatch(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    tp = archive_root / "timelines" / "tl-01.json"
    data = json.loads(tp.read_text(encoding="utf-8"))
    data["timeline_id"] = "tampered"
    tp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = verify_derived_integrity(archive_root)
    mismatches = [
        i
        for i in report.issues
        if i.artifact_kind == "timeline" and i.issue_kind == IntegrityIssueKind.HASH_MISMATCH.value
    ]
    assert len(mismatches) == 1


def test_detects_timeline_workspace_link_broken(tmp_path: Path, archive_root: Path) -> None:
    """Si borramos el workspace pero el timeline lo referenciaba, link broken."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    (archive_root / "workspaces" / "w-01.json").unlink()
    report = verify_derived_integrity(archive_root)
    broken = [
        i
        for i in report.issues
        if i.artifact_kind == "timeline"
        and i.issue_kind == IntegrityIssueKind.WORKSPACE_LINK_BROKEN.value
    ]
    assert len(broken) == 1


# ---------------------------------------------------------------- snapshot tampering


def test_detects_snapshot_timeline_link_broken(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    (archive_root / "timelines" / "tl-01.json").unlink()
    report = verify_derived_integrity(archive_root)
    broken = [
        i
        for i in report.issues
        if i.artifact_kind == "snapshot"
        and i.issue_kind == IntegrityIssueKind.TIMELINE_LINK_BROKEN.value
    ]
    assert len(broken) == 1


# ---------------------------------------------------------------- justification


def test_detects_justification_manifest_drift(tmp_path: Path, archive_root: Path) -> None:
    """Crear segundo assessment hace que el manifest cambie; la
    justificación previa queda con source_manifest_hash desactualizado."""
    ev_hash, _a_id, _, _, _, _ = _bootstrap_full_pipeline(tmp_path, archive_root)
    # Crear OTRO assessment con método distinto → manifest cambia.
    archive = Archive.open(archive_root)
    archive.assess_authentication(
        evidence_id=ev_hash,
        method=AssessmentMethod.MANUAL_RESEARCH,
        clock=_clock(CANONICAL_TS),
        actor="@test",
    )
    report = verify_derived_integrity(archive_root)
    drifts = [i for i in report.issues if i.issue_kind == IntegrityIssueKind.MANIFEST_DRIFT.value]
    assert len(drifts) == 1


def test_detects_justification_assessment_anchor_dangling(
    tmp_path: Path, archive_root: Path
) -> None:
    """Borrar el assessment anchor de la justificación."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    # Borrar el row del assessment.
    assess_files = list((archive_root / "tables" / "authentication_assessments").glob("*.parquet"))
    assert len(assess_files) == 1
    assess_files[0].unlink()
    report = verify_derived_integrity(archive_root)
    dangling = [
        i
        for i in report.issues
        if i.artifact_kind == "justification"
        and i.issue_kind == IntegrityIssueKind.ASSESSMENT_REFERENCE_DANGLING.value
    ]
    assert len(dangling) >= 1


# ---------------------------------------------------------------- read-only


def test_verify_does_not_modify_archive(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)

    def snapshot() -> dict[str, bytes]:
        snap: dict[str, bytes] = {}
        for d in (
            "tables",
            "workspaces",
            "timelines",
            "snapshots",
            "justifications",
            "objects",
        ):
            dp = archive_root / d
            if dp.is_dir():
                for p in sorted(dp.rglob("*")):
                    if p.is_file():
                        snap[str(p.relative_to(archive_root))] = p.read_bytes()
        snap["audit.log"] = (archive_root / "audit.log").read_bytes()
        snap["manifest.json"] = (archive_root / "manifest.json").read_bytes()
        return snap

    pre = snapshot()
    verify_derived_integrity(archive_root)
    post = snapshot()
    assert pre == post


# ---------------------------------------------------------------- canonical ordering


def test_issues_are_canonically_sorted(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    # Tamper múltiples artefactos.
    for filename in (
        "workspaces/w-01.json",
        "timelines/tl-01.json",
        "snapshots/s-01.json",
        "justifications/j-01.json",
    ):
        p = archive_root / filename
        data = json.loads(p.read_text(encoding="utf-8"))
        # Cambiar campo no-hash (preserva decode pero rompe hash).
        if "title" in data:
            data["title"] = "x"
        elif "timeline_id" in data:
            data["timeline_id"] = "tampered-tl"
        elif "snapshot_id" in data:
            data["snapshot_id"] = "tampered-s"
        elif "justification_id" in data:
            data["justification_id"] = "tampered-j"
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    report = verify_derived_integrity(archive_root)
    keys = [(i.artifact_kind, i.artifact_id, i.issue_kind, i.detail) for i in report.issues]
    assert keys == sorted(keys)


# ---------------------------------------------------------------- AST guard


def test_integrity_imports_no_forbidden_modules() -> None:
    """integrity/ debe leer pero NO ejecutar motores productores ni
    importar libs ML/red. Imports permitidos: capas derivadas + storage
    + analysis (lectura modelo)."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "integrity"
    forbidden_external = {
        "numpy",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "openai",
        "anthropic",
        "requests",
        "urllib",
        "urllib3",
        "httpx",
    }
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    mods.append(n.name)
            for mod in mods:
                if mod.split(".")[0] in forbidden_external:
                    offenders.append((module_path.name, mod))
    assert offenders == [], f"integrity/ imports forbidden modules: {offenders}"


# ---------------------------------------------------------------- forbidden tokens

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "danger",
    "likelihood",
    "probability",
    "bayesian",
    "confidence_score",
    "recommend_action",
    "recommendation",
    "ranking",
    "embedding",
    "clustering",
    "causal_inference",
    "summary_text",
    "explanation",
    "better",
    "worse",
    "important_",
    "relevant_",
)


def test_no_prohibited_tokens_in_integrity_module() -> None:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "integrity"
    offenders: list[tuple[str, str]] = []
    for path in pkg.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == []


# ---------------------------------------------------------------- CLI


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    rc = cli_main.main(argv, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def test_cli_archive_verify_without_derived_unchanged(tmp_path: Path, archive_root: Path) -> None:
    """Sin --derived el comportamiento es idéntico al pre-P2."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    rc, out, _ = _run(["archive", "verify", "--archive-root", str(archive_root), "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert "derived_integrity" not in payload["checks"]
    assert "derived_integrity_issues" not in payload


def test_cli_archive_verify_with_derived_clean(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    rc, out, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
            "--derived",
        ]
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["checks"]["derived_integrity"]["ok"] is True
    assert payload["derived_integrity_issues"] == []
    assert payload["summary"]["workspaces_checked"] == 1
    assert payload["summary"]["timelines_checked"] == 1
    assert payload["summary"]["snapshots_checked"] == 1
    assert payload["summary"]["justifications_checked"] == 1


def test_cli_archive_verify_with_derived_detects_tampering(
    tmp_path: Path, archive_root: Path
) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    wp = archive_root / "workspaces" / "w-01.json"
    data = json.loads(wp.read_text(encoding="utf-8"))
    data["title"] = "tampered"
    wp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rc, out, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--json",
            "--derived",
        ]
    )
    assert rc == 3
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["checks"]["derived_integrity"]["ok"] is False
    assert len(payload["derived_integrity_issues"]) >= 1


def test_cli_archive_verify_human_with_derived(tmp_path: Path, archive_root: Path) -> None:
    _bootstrap_full_pipeline(tmp_path, archive_root)
    rc, out, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--derived",
        ]
    )
    assert rc == 0
    assert "derived_integrity" in out
    assert "Workspaces:" in out
    assert "Justifications:" in out


# ---------------------------------------------------------------- backwards compat


def test_removing_integrity_module_does_not_break_existing(
    tmp_path: Path, archive_root: Path
) -> None:
    """G5: el comportamiento default de archive verify no depende del módulo."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    # Verify sin --derived debe pasar igual.
    rc, _, _ = _run(["archive", "verify", "--archive-root", str(archive_root)])
    assert rc == 0


def test_removability_after_full_pipeline(tmp_path: Path, archive_root: Path) -> None:
    """Borrar todos los artefactos derivados no rompe archive verify base."""
    _bootstrap_full_pipeline(tmp_path, archive_root)
    for d in ("workspaces", "timelines", "snapshots", "justifications"):
        target = archive_root / d
        if target.is_dir():
            shutil.rmtree(target)
    rc, _, _ = _run(["archive", "verify", "--archive-root", str(archive_root)])
    assert rc == 0
    # También --derived (sin artefactos) debe pasar.
    rc, _, _ = _run(
        [
            "archive",
            "verify",
            "--archive-root",
            str(archive_root),
            "--derived",
        ]
    )
    assert rc == 0


# ---------------------------------------------------------------- report model


def test_report_model_immutable() -> None:
    r = DerivedIntegrityReport(
        workspaces_checked=0,
        timelines_checked=0,
        snapshots_checked=0,
        justifications_checked=0,
        issues=(),
        integrity_engine_version=INTEGRITY_ENGINE_VERSION,
        integrity_method_name=INTEGRITY_METHOD_NAME,
    )
    assert r.ok is True
    assert r.total_checked == 0


def test_issue_model_immutable() -> None:
    i1 = DerivedIntegrityIssue(
        artifact_kind="workspace",
        artifact_id="w-01",
        issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
        detail="x",
    )
    i2 = DerivedIntegrityIssue(
        artifact_kind="workspace",
        artifact_id="w-01",
        issue_kind=IntegrityIssueKind.HASH_MISMATCH.value,
        detail="x",
    )
    assert i1 == i2
