"""Tests del modelo de Timeline (ADR-0037 §modelo)."""

from __future__ import annotations

import datetime as dt
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aip.timeline import (
    TIMELINE_SCHEMA_VERSION,
    InvestigationTimeline,
    TimelineEvent,
)

UTC = dt.UTC
TS_A = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
TS_B = dt.datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)


def _evt(
    observed_at: dt.datetime = TS_A,
    artifact_hash: str = "a" * 64,
    artifact_type: str = "evidence",
    artifact_identifier: str = "E001",
    source_reference: str = "evidence.ingested_at",
) -> TimelineEvent:
    return TimelineEvent(
        observed_at=observed_at,
        artifact_hash=artifact_hash,
        artifact_type=artifact_type,
        artifact_identifier=artifact_identifier,
        source_reference=source_reference,
    )


def test_schema_version_pinned() -> None:
    assert TIMELINE_SCHEMA_VERSION == "1"


# ---------------------------------------------------------------- TimelineEvent


def test_event_constructs() -> None:
    e = _evt()
    assert e.artifact_type == "evidence"


def test_event_frozen() -> None:
    e = _evt()
    with pytest.raises(FrozenInstanceError):
        e.artifact_type = "x"  # type: ignore[misc]


def test_event_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _evt(observed_at=dt.datetime(2026, 1, 1, 0, 0, 0))


def test_event_rejects_microsecond() -> None:
    with pytest.raises(ValueError, match="microsecond"):
        _evt(
            observed_at=dt.datetime(
                2026, 1, 1, 0, 0, 0, 123, tzinfo=UTC
            )
        )


def test_event_rejects_empty_artifact_hash() -> None:
    with pytest.raises(ValueError):
        _evt(artifact_hash="")


def test_event_orders_by_observed_at_then_hash() -> None:
    a = _evt(observed_at=TS_A, artifact_hash="a" * 64)
    b = _evt(observed_at=TS_B, artifact_hash="a" * 64)
    assert a < b
    c = _evt(observed_at=TS_A, artifact_hash="b" * 64)
    assert a < c  # same time, "a" < "b"


# ---------------------------------------------------------------- Timeline


def _valid_timeline(**overrides) -> InvestigationTimeline:
    e = _evt()
    base: dict[str, object] = {
        "timeline_id": "tl-01",
        "workspace_hash": "f" * 64,
        "ordered_events": (e,),
        "first_timestamp": e.observed_at,
        "last_timestamp": e.observed_at,
        "event_count": 1,
        "timeline_hash": "0" * 64,
    }
    base.update(overrides)
    return InvestigationTimeline(**base)  # type: ignore[arg-type]


def test_timeline_constructs() -> None:
    t = _valid_timeline()
    assert t.timeline_id == "tl-01"
    assert t.schema_version == "1"


def test_timeline_frozen() -> None:
    t = _valid_timeline()
    with pytest.raises(FrozenInstanceError):
        t.timeline_id = "x"  # type: ignore[misc]


def test_timeline_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _valid_timeline(timeline_id="")


def test_timeline_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="outside"):
        _valid_timeline(timeline_id="a/b")


def test_timeline_rejects_event_count_mismatch() -> None:
    with pytest.raises(ValueError, match="event_count"):
        _valid_timeline(event_count=5)


def test_timeline_rejects_unsorted_events() -> None:
    e1 = _evt(observed_at=TS_B, artifact_hash="a" * 64)
    e2 = _evt(observed_at=TS_A, artifact_hash="b" * 64)
    with pytest.raises(ValueError, match="canonically sorted"):
        _valid_timeline(
            ordered_events=(e1, e2),
            first_timestamp=TS_B,
            last_timestamp=TS_A,
            event_count=2,
        )


def test_timeline_rejects_inconsistent_first_timestamp() -> None:
    e = _evt(observed_at=TS_A)
    with pytest.raises(ValueError, match="first_timestamp"):
        _valid_timeline(
            ordered_events=(e,),
            first_timestamp=TS_B,
            last_timestamp=TS_A,
            event_count=1,
        )


def test_timeline_rejects_inconsistent_last_timestamp() -> None:
    e = _evt(observed_at=TS_A)
    with pytest.raises(ValueError, match="last_timestamp"):
        _valid_timeline(
            ordered_events=(e,),
            first_timestamp=TS_A,
            last_timestamp=TS_B,
            event_count=1,
        )


def test_timeline_empty_must_have_none_boundaries() -> None:
    with pytest.raises(ValueError, match="first_timestamp"):
        InvestigationTimeline(
            timeline_id="tl",
            workspace_hash="f" * 64,
            ordered_events=(),
            first_timestamp=TS_A,
            last_timestamp=None,
            event_count=0,
            timeline_hash="0" * 64,
        )


def test_timeline_accepts_empty_with_none_boundaries() -> None:
    t = InvestigationTimeline(
        timeline_id="tl",
        workspace_hash="f" * 64,
        ordered_events=(),
        first_timestamp=None,
        last_timestamp=None,
        event_count=0,
        timeline_hash="0" * 64,
    )
    assert t.event_count == 0


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
    "hypothesis",
    "infer_",
)


def _timeline_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "timeline"
    cli_module = repo / "src" / "aip" / "cli" / "timeline_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_timeline_module() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _timeline_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], (
        f"Forbidden tokens in timeline (ADR-0037 §componentes excluidos): "
        f"{offenders}"
    )
