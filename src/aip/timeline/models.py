"""Modelos del Timeline Engine (ADR-0037 §modelo)."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Final

TIMELINE_SCHEMA_VERSION: Final[str] = "1"

_TIMELINE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._\-]+$"
)
_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, order=True)
class TimelineEvent:
    """Evento ordenado en la timeline (ADR-0037 §modelo).

    Orden canónico natural: ``(observed_at, artifact_hash)``. El
    ``artifact_hash`` actúa como tie-break determinista cuando dos
    eventos comparten ``observed_at`` exacto.
    """

    observed_at: dt.datetime
    artifact_hash: str
    artifact_type: str
    artifact_identifier: str
    source_reference: str

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError(
                "TimelineEvent.observed_at must be timezone-aware."
            )
        if self.observed_at.microsecond != 0:
            raise ValueError(
                "TimelineEvent.observed_at must have microsecond=0."
            )
        if not self.artifact_hash:
            raise ValueError("artifact_hash must be non-empty.")
        if not self.artifact_type:
            raise ValueError("artifact_type must be non-empty.")
        if not self.artifact_identifier:
            raise ValueError("artifact_identifier must be non-empty.")
        if not self.source_reference:
            raise ValueError("source_reference must be non-empty.")


@dataclass(frozen=True)
class InvestigationTimeline:
    """Timeline canónica de eventos (ADR-0037 §modelo)."""

    timeline_id: str
    workspace_hash: str
    ordered_events: tuple[TimelineEvent, ...]
    first_timestamp: dt.datetime | None
    last_timestamp: dt.datetime | None
    event_count: int
    timeline_hash: str
    schema_version: str = TIMELINE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.timeline_id:
            raise ValueError("timeline_id must be non-empty.")
        if not _TIMELINE_ID_PATTERN.match(self.timeline_id):
            raise ValueError(
                f"timeline_id {self.timeline_id!r} contains characters "
                "outside [A-Za-z0-9._-]."
            )
        if not _SHA256_HEX_PATTERN.match(self.workspace_hash):
            raise ValueError("workspace_hash must be SHA-256 hex lowercase.")
        if not _SHA256_HEX_PATTERN.match(self.timeline_hash):
            raise ValueError("timeline_hash must be SHA-256 hex lowercase.")
        if self.event_count != len(self.ordered_events):
            raise ValueError(
                f"event_count {self.event_count} != len(ordered_events) "
                f"{len(self.ordered_events)}."
            )
        # Orden canónico.
        sorted_events = tuple(sorted(self.ordered_events))
        if self.ordered_events != sorted_events:
            raise ValueError(
                "ordered_events must be canonically sorted by "
                "(observed_at, artifact_hash)."
            )
        # Consistencia de boundaries.
        if self.ordered_events:
            if self.first_timestamp != self.ordered_events[0].observed_at:
                raise ValueError(
                    "first_timestamp must equal ordered_events[0].observed_at."
                )
            if self.last_timestamp != self.ordered_events[-1].observed_at:
                raise ValueError(
                    "last_timestamp must equal ordered_events[-1].observed_at."
                )
        else:
            if self.first_timestamp is not None:
                raise ValueError(
                    "first_timestamp must be None when ordered_events is empty."
                )
            if self.last_timestamp is not None:
                raise ValueError(
                    "last_timestamp must be None when ordered_events is empty."
                )
