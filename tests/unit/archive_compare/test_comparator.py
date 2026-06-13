"""Tests for ``aip.archive_compare.compare_archives``.

The comparator's job is detecting silent disagreement between two
operators that both claim to hold the same evidence. The tests build
small synthetic archives via ``Archive.ingest_evidence`` and then
optionally tamper one side to confirm each divergence path fires.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aip import Archive
from aip.analysis.authentication import AssessmentMethod  # noqa: F401  (imported for parity)
from aip.archive_compare import compare_archives
from aip.audit import log as audit_log
from aip.core.evidence import EvidenceKind
from aip.core.source import AuthorityLevel, SourceKind
from aip.justification.logic.store import INFERENCE_PROOFS_DIRNAME

UTC = dt.UTC
CANONICAL_TS = dt.datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)


def _fixed_clock(ts: dt.datetime) -> Callable[[], dt.datetime]:
    return lambda: ts


def _make_blob(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _ingest(archive_root: Path, blob: Path, *, ingested_by: str = "@op") -> str:
    archive = Archive.open(archive_root)
    ev = archive.ingest_evidence(
        blob,
        source_id="src-x",
        source_name="Source X",
        source_kind=SourceKind.GOVERNMENT_ARCHIVE,
        source_authority=AuthorityLevel.SECONDARY,
        source_jurisdiction="US",
        source_license="public_domain",
        evidence_kind=EvidenceKind.DOCUMENT_SCAN,
        mime_type="application/pdf",
        ingested_by=ingested_by,
        clock=_fixed_clock(CANONICAL_TS),
    )
    return ev.hash


@pytest.fixture
def two_archives(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "archive-a"
    a.mkdir()
    b = tmp_path / "archive-b"
    b.mkdir()
    return a, b


# --------------------------------------------------------------- basic shape


def test_empty_archives_report_no_divergence(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    rep = compare_archives(a, b)
    assert rep.shared_count == 0
    assert rep.a_only_evidence_hashes == ()
    assert rep.b_only_evidence_hashes == ()
    assert rep.has_divergence is False


def test_compare_archives_raises_on_missing_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compare_archives(tmp_path / "missing", tmp_path / "also-missing")


def test_labels_default_to_directory_names(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    rep = compare_archives(a, b)
    assert rep.archive_a_label == "archive-a"
    assert rep.archive_b_label == "archive-b"


def test_explicit_labels_override(two_archives: tuple[Path, Path]) -> None:
    a, b = two_archives
    rep = compare_archives(a, b, label_a="OP-A", label_b="OP-B")
    assert rep.archive_a_label == "OP-A"
    assert rep.archive_b_label == "OP-B"


# --------------------------------------------------------------- a-only / b-only


def test_a_only_evidence_is_listed_separately(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    a, b = two_archives
    blob = _make_blob(tmp_path, "doc.pdf", b"%PDF-1.4 only-in-a")
    ev_hash = _ingest(a, blob)
    rep = compare_archives(a, b)
    assert rep.shared_count == 0
    assert rep.a_only_evidence_hashes == (ev_hash,)
    assert rep.b_only_evidence_hashes == ()
    assert rep.has_divergence is False  # no SHARED divergence


def test_b_only_evidence_is_listed_separately(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    a, b = two_archives
    blob = _make_blob(tmp_path, "doc.pdf", b"%PDF-1.4 only-in-b")
    ev_hash = _ingest(b, blob)
    rep = compare_archives(a, b)
    assert rep.shared_count == 0
    assert rep.b_only_evidence_hashes == (ev_hash,)


# --------------------------------------------------------------- shared evidence


def test_shared_evidence_with_identical_ingest_matches(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    """Two independent ingests of the same file — different audit chains, but
    the content-derived parameters (size_bytes) must coincide and the
    comparator must report no divergence."""
    a, b = two_archives
    blob_a = _make_blob(tmp_path, "doc-a.pdf", b"%PDF-1.4 shared-evidence")
    blob_b = _make_blob(tmp_path, "doc-b.pdf", b"%PDF-1.4 shared-evidence")
    ev_a = _ingest(a, blob_a, ingested_by="@op-a")
    ev_b = _ingest(b, blob_b, ingested_by="@op-b")
    assert ev_a == ev_b  # same bytes → same SHA-256

    rep = compare_archives(a, b)
    assert rep.shared_count == 1
    div = rep.shared_evidence[0]
    assert div.evidence_hash == ev_a
    assert div.audit_params_match is True
    assert div.diverging_param_fields == ()
    assert rep.has_divergence is False


def test_shared_evidence_with_tampered_size_bytes_flags_divergence(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    """Direct attack: an operator edits their audit log to claim a different
    ``size_bytes`` for the same evidence hash. The comparator must catch
    this as a divergence and exit code 1 from the CLI."""
    a, b = two_archives
    blob_a = _make_blob(tmp_path, "doc-a.pdf", b"%PDF-1.4 shared")
    blob_b = _make_blob(tmp_path, "doc-b.pdf", b"%PDF-1.4 shared")
    _ingest(a, blob_a)
    _ingest(b, blob_b)

    # Tamper B's audit log: rewrite size_bytes in the ingest entry. We do
    # this by reading the JSONL, mutating, and writing it back — we don't
    # need a valid chain hash for the comparator, which only reads
    # ``parameters``. (Other tests guard the chain itself.)
    log_path = a.parent / "archive-b" / "audit.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    for raw in lines:
        entry = json.loads(raw)
        if entry.get("action") == "ingest_evidence":
            entry["parameters"]["size_bytes"] = "999999"
        rewritten.append(json.dumps(entry, sort_keys=True))
    log_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    rep = compare_archives(a, b)
    assert rep.shared_count == 1
    div = rep.shared_evidence[0]
    assert div.audit_params_match is False
    assert "size_bytes" in div.diverging_param_fields
    assert div.has_divergence is True
    assert rep.has_divergence is True


# --------------------------------------------------------------- inference proofs


def _drop_proof(
    archive_root: Path,
    *,
    proof_id: str,
    target_justification_hash: str,
    proof_hash: str,
) -> None:
    """Write a minimal inference-proof JSON file into the archive.

    The comparator only reads ``proof_id``, ``target_justification_hash``,
    and ``proof_hash`` — we skip the full schema to keep the fixture tiny.
    """
    d = archive_root / INFERENCE_PROOFS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{proof_id}.json").write_text(
        json.dumps(
            {
                "proof_id": proof_id,
                "target_justification_hash": target_justification_hash,
                "proof_hash": proof_hash,
            }
        ),
        encoding="utf-8",
    )


def test_shared_proof_with_matching_hashes_reports_match(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    _drop_proof(
        a, proof_id="p-001", target_justification_hash="f" * 64, proof_hash="a" * 64
    )
    _drop_proof(
        b, proof_id="p-001", target_justification_hash="f" * 64, proof_hash="a" * 64
    )
    rep = compare_archives(a, b)
    assert len(rep.shared_proofs) == 1
    p = rep.shared_proofs[0]
    assert p.proof_id == "p-001"
    assert p.matches is True
    assert rep.has_divergence is False


def test_shared_proof_with_diverging_proof_hash_flags_tampering(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    _drop_proof(
        a, proof_id="p-001", target_justification_hash="f" * 64, proof_hash="a" * 64
    )
    _drop_proof(
        b, proof_id="p-001", target_justification_hash="f" * 64, proof_hash="b" * 64
    )
    rep = compare_archives(a, b)
    p = rep.shared_proofs[0]
    assert p.matches is False
    assert p.has_divergence is True
    assert rep.has_divergence is True


def test_a_only_and_b_only_proofs_listed_separately(
    two_archives: tuple[Path, Path],
) -> None:
    a, b = two_archives
    _drop_proof(
        a, proof_id="only-a", target_justification_hash="f" * 64, proof_hash="a" * 64
    )
    _drop_proof(
        b, proof_id="only-b", target_justification_hash="e" * 64, proof_hash="b" * 64
    )
    rep = compare_archives(a, b)
    assert rep.a_only_proof_ids == ("only-a",)
    assert rep.b_only_proof_ids == ("only-b",)
    assert rep.shared_proofs == ()
    assert rep.has_divergence is False  # no shared disagreement


def test_proof_with_different_target_justification_hash_diverges(
    two_archives: tuple[Path, Path],
) -> None:
    """Identical proof_id but different target_justification_hash means the
    proof is attesting different justifications — semantically a different
    proof, structurally a divergence."""
    a, b = two_archives
    _drop_proof(
        a, proof_id="p-001", target_justification_hash="f" * 64, proof_hash="a" * 64
    )
    _drop_proof(
        b, proof_id="p-001", target_justification_hash="e" * 64, proof_hash="a" * 64
    )
    rep = compare_archives(a, b)
    p = rep.shared_proofs[0]
    assert p.matches is False
    assert p.has_divergence is True


# --------------------------------------------------------------- audit log edge cases


def test_re_ingestion_uses_latest_state(
    tmp_path: Path, two_archives: tuple[Path, Path]
) -> None:
    """If an evidence appears twice in the audit log (e.g., re-ingested with
    additional metadata), the comparator uses the last entry. This pins
    the behavior so a future refactor cannot silently change it."""
    a, b = two_archives
    blob = _make_blob(tmp_path, "doc.pdf", b"%PDF-1.4 reingested")
    _ingest(a, blob)
    _ingest(b, blob)

    # Append a duplicate ingest_evidence entry for archive A with mutated
    # size_bytes. The audit-log helper iterates and overwrites, so the
    # second entry wins.
    log_path = a / "audit.log"
    existing = log_path.read_text(encoding="utf-8").rstrip()
    last_entry = json.loads(existing.splitlines()[-1])
    last_entry["parameters"] = {"size_bytes": "999999"}
    last_entry["seq"] = last_entry["seq"] + 1
    log_path.write_text(
        existing + "\n" + json.dumps(last_entry, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rep = compare_archives(a, b)
    div = rep.shared_evidence[0]
    assert div.audit_params_a["size_bytes"] == "999999"
    assert div.audit_params_match is False


def test_iter_entries_pulls_real_entries(tmp_path: Path) -> None:
    """Defensive: prove the comparator's underlying audit-log reader sees the
    ingest entries produced by ``Archive.ingest_evidence``. Catches a
    layout/migration drift that would otherwise turn divergence reports
    into silent no-ops."""
    root = tmp_path / "archive"
    root.mkdir()
    blob = _make_blob(tmp_path, "doc.pdf", b"%PDF-1.4 probe")
    _ingest(root, blob)
    entries = list(audit_log.iter_entries(root))
    actions = [e.action for e in entries]
    assert "ingest_evidence" in actions
