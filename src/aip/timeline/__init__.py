"""Investigation Timeline Engine (ADR-0037).

Capa derivada que ordena cronológicamente los artefactos referenciados
por un :class:`InvestigationWorkspace`. Sólo entran artefactos con
timestamp nativo en el archive (evidence + assessment); impact_analysis
y context_bundle se omiten silenciosamente — la timeline es honesta
sobre lo que sabe (ADR-0037 §alcance).

**No infiere causalidad. No agrupa. No clasifica. No resume. No puntúa.**
Es únicamente una vista ordenada.
"""

from __future__ import annotations

from aip.timeline.builder import (
    TimelineNotFoundError,
    build_timeline,
    compute_timeline_hash,
    decode_timeline,
    encode_timeline,
    load_timeline,
    persist_timeline,
    timeline_path,
    verify_timeline_hash,
)
from aip.timeline.models import (
    TIMELINE_SCHEMA_VERSION,
    InvestigationTimeline,
    TimelineEvent,
)

__all__ = [
    "TIMELINE_SCHEMA_VERSION",
    "InvestigationTimeline",
    "TimelineEvent",
    "TimelineNotFoundError",
    "build_timeline",
    "compute_timeline_hash",
    "decode_timeline",
    "encode_timeline",
    "load_timeline",
    "persist_timeline",
    "timeline_path",
    "verify_timeline_hash",
]
