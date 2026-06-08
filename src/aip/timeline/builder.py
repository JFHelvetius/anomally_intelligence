"""Constructor, persistencia y verificación de Timelines (ADR-0037)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from aip._version import SCHEMA_VERSION
from aip.analysis.authentication import (
    AuthenticationAssessment as DerivedAuthenticationAssessment,
)
from aip.audit import log as audit_log
from aip.core.evidence import Evidence
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.errors import AIPError
from aip.storage import layout, tables
from aip.storage.atomic_io import atomic_write_text
from aip.timeline.models import (
    InvestigationTimeline,
    TimelineEvent,
)
from aip.workspace.models import InvestigationWorkspace

TIMELINES_DIRNAME: str = "timelines"


class TimelineNotFoundError(AIPError):
    """Timeline solicitado no existe bajo ``<archive>/timelines/``."""

    cli_exit_code = 1


# --------------------------------------------------------------------- build


def build_timeline(
    *,
    archive_root: Path,
    workspace: InvestigationWorkspace,
    timeline_id: str,
) -> InvestigationTimeline:
    """Construye un :class:`InvestigationTimeline` determinista.

    Sólo entran eventos para artefactos con timestamp nativo:
    ``evidence.ingested_at`` y ``assessment.created_at``.
    ``impact_analysis`` y ``context_bundle`` se omiten silenciosamente
    (ADR-0037 §alcance).
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise FileNotFoundError(
            f"archive not found or invalid at {archive_root}."
        )

    events: list[TimelineEvent] = []
    for ref in workspace.references:
        ev_evt = _event_for_reference(archive_root, ref.reference_type, ref.identifier)
        if ev_evt is not None:
            events.append(ev_evt)

    events.sort()
    first_ts = events[0].observed_at if events else None
    last_ts = events[-1].observed_at if events else None

    partial = InvestigationTimeline(
        timeline_id=timeline_id,
        workspace_hash=workspace.workspace_hash,
        ordered_events=tuple(events),
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        event_count=len(events),
        timeline_hash="0" * 64,
    )
    final_hash = compute_timeline_hash(partial)
    return dataclasses.replace(partial, timeline_hash=final_hash)


def _event_for_reference(
    archive_root: Path, ref_type: str, identifier: str
) -> TimelineEvent | None:
    if ref_type == "evidence":
        row = tables.read_row(archive_root, "evidence", identifier)
        if row is None:
            return None
        ev = Evidence.model_validate(row)
        return TimelineEvent(
            observed_at=ev.ingested_at,
            artifact_hash=ev.hash,
            artifact_type="evidence",
            artifact_identifier=ev.hash,
            source_reference="evidence.ingested_at",
        )
    if ref_type == "assessment":
        row = tables.read_row(
            archive_root, "authentication_assessments", identifier
        )
        if row is None:
            return None
        a = DerivedAuthenticationAssessment.model_validate(row)
        # artifact_hash para tie-break: SHA-256 de la cadena del assessment_id.
        h = sha256_hex(a.assessment_id.encode("utf-8"))
        return TimelineEvent(
            observed_at=a.created_at,
            artifact_hash=h,
            artifact_type="assessment",
            artifact_identifier=a.assessment_id,
            source_reference="assessment.created_at",
        )
    # impact_analysis y context_bundle: sin timestamp nativo. Omitir.
    return None


# --------------------------------------------------------------------- hashing


def compute_timeline_hash(timeline: InvestigationTimeline) -> str:
    """SHA-256 hex de la canonicalización JCS del timeline **excluyendo**
    el propio campo ``timeline_hash``."""
    data = _timeline_to_canonical_dict(timeline)
    data.pop("timeline_hash", None)
    normalized = cast(JsonValue, data)
    return sha256_hex(jcs_canonicalize(normalized))


def verify_timeline_hash(timeline: InvestigationTimeline) -> bool:
    """Verifica ``timeline_hash`` offline."""
    return compute_timeline_hash(timeline) == timeline.timeline_hash


def _timeline_to_canonical_dict(
    timeline: InvestigationTimeline,
) -> dict[str, object]:
    return {
        "timeline_id": timeline.timeline_id,
        "workspace_hash": timeline.workspace_hash,
        "ordered_events": [_event_to_dict(e) for e in timeline.ordered_events],
        "first_timestamp": _iso_or_none(timeline.first_timestamp),
        "last_timestamp": _iso_or_none(timeline.last_timestamp),
        "event_count": timeline.event_count,
        "timeline_hash": timeline.timeline_hash,
        "schema_version": timeline.schema_version,
    }


def _event_to_dict(e: TimelineEvent) -> dict[str, object]:
    return {
        "artifact_type": e.artifact_type,
        "artifact_identifier": e.artifact_identifier,
        "artifact_hash": e.artifact_hash,
        "observed_at": _iso_utc(e.observed_at),
        "source_reference": e.source_reference,
    }


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_or_none(value: dt.datetime | None) -> str | None:
    return _iso_utc(value) if value is not None else None


# --------------------------------------------------------------------- persistence


def timeline_path(archive_root: Path, timeline_id: str) -> Path:
    return archive_root / TIMELINES_DIRNAME / f"{timeline_id}.json"


def persist_timeline(
    timeline: InvestigationTimeline,
    *,
    archive_root: Path,
    actor: str,
    clock: Callable[[], dt.datetime],
    extra_output: Path | None = None,
) -> Path:
    """Persiste el timeline y emite ``BUILD_TIMELINE`` al audit log
    (ADR-0019 §enmienda E1).
    """
    target = timeline_path(archive_root, timeline.timeline_id)
    payload = encode_timeline(timeline)
    atomic_write_text(target, payload)
    if extra_output is not None:
        atomic_write_text(extra_output, payload)
    audit_log.record_derived_artifact(
        archive_root,
        action=audit_log.ActionKind.BUILD_TIMELINE,
        artifact_kind="timeline",
        artifact_id=timeline.timeline_id,
        self_hash=timeline.timeline_hash,
        actor=actor,
        clock=clock,
        schema_version=SCHEMA_VERSION,
    )
    return target


def load_timeline(
    *, archive_root: Path, timeline_id: str
) -> InvestigationTimeline:
    target = timeline_path(archive_root, timeline_id)
    if not target.is_file():
        raise TimelineNotFoundError(
            f"timeline {timeline_id!r} not found at {target}."
        )
    return decode_timeline(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- encoding


def encode_timeline(timeline: InvestigationTimeline) -> str:
    data = _timeline_to_canonical_dict(timeline)
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def decode_timeline(payload: str) -> InvestigationTimeline:
    data = json.loads(payload)
    events = tuple(
        TimelineEvent(
            observed_at=_parse_iso(e["observed_at"]),
            artifact_hash=e["artifact_hash"],
            artifact_type=e["artifact_type"],
            artifact_identifier=e["artifact_identifier"],
            source_reference=e["source_reference"],
        )
        for e in data.get("ordered_events", [])
    )
    return InvestigationTimeline(
        timeline_id=data["timeline_id"],
        workspace_hash=data["workspace_hash"],
        ordered_events=events,
        first_timestamp=_parse_iso_or_none(data.get("first_timestamp")),
        last_timestamp=_parse_iso_or_none(data.get("last_timestamp")),
        event_count=data["event_count"],
        timeline_hash=data["timeline_hash"],
        schema_version=data.get("schema_version", ""),
    )


def _parse_iso(value: str) -> dt.datetime:
    # Acepta YYYY-MM-DDTHH:MM:SSZ.
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.UTC
    )


def _parse_iso_or_none(value: str | None) -> dt.datetime | None:
    return _parse_iso(value) if value is not None else None
