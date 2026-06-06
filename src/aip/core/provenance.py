"""Cadena de procedencia (ADR-0005, subset V1).

V1 implementa:

- :class:`StepKind` — enum cerrada con los 12 tipos del ADR-0005.
- :class:`ProvenanceStep` — paso individual con autor, instante, inputs, outputs.
- :class:`GapDescription` — hueco declarado en la cadena.
- :class:`Provenance` — cadena completa anclada a un hash de evidencia y a una
  fuente de origen.

Campos del ADR-0005 deliberadamente diferidos:

- ``signature`` — firma criptográfica de la procedencia atestiguada. No aplica
  en V1 sin PKI.

Reglas validadas en V1:

- ``step_id`` único dentro de una procedencia.
- Cualquier ``timestamp`` que se almacene en estructura hasheada debe ser
  tz-aware (ADR-0031 R1).
- Hashes en ``inputs`` / ``outputs`` deben ser SHA-256 hex lowercase 64.
- ``parameters`` es ``dict[str, str]`` para preservar canonicalización JCS
  (ADR-0024 L2). Tipos no-str se rechazan estructuralmente.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------- enums


class StepKind(StrEnum):
    """Tipos de paso en una cadena de procedencia (ADR-0005). Cerrado por ADR."""

    ORIGINAL_CAPTURE = "original_capture"
    ANALOG_TO_DIGITAL = "analog_to_digital"
    FORMAT_CONVERSION = "format_conversion"
    OCR = "ocr"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"
    REDACTION = "redaction"
    CROP_OR_EXCERPT = "crop_or_excerpt"
    ENHANCEMENT = "enhancement"
    ATTRIBUTION_CHANGE = "attribution_change"
    REPUBLICATION = "republication"
    UNKNOWN_STEP = "unknown_step"


# --------------------------------------------------------------------- field types

_SHA256_HEX_PATTERN: Final[str] = r"^[a-f0-9]{64}$"

Sha256Hex = Annotated[
    str,
    Field(
        pattern=_SHA256_HEX_PATTERN,
        min_length=64,
        max_length=64,
    ),
]


# --------------------------------------------------------------------- models


class GapDescription(BaseModel):
    """Hueco conocido en la cadena de procedencia (ADR-0005).

    Hacer los huecos explícitos es información honesta; un hueco silencioso es
    deshonestidad estructural (ADR-0005 §huecos explícitos).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = Field(min_length=1)


class ProvenanceStep(BaseModel):
    """Paso individual de una cadena de procedencia (ADR-0005)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: int = Field(ge=1, description="Posición lógica del paso (1-based).")
    kind: StepKind
    actor: str | None = Field(default=None, min_length=1)
    timestamp: dt.datetime | None = None
    inputs: list[Sha256Hex] = Field(default_factory=list)
    outputs: list[Sha256Hex] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_tz_aware(
        cls, value: dt.datetime | None
    ) -> dt.datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "ProvenanceStep.timestamp must be timezone-aware (use UTC)."
            )
        return value


class Provenance(BaseModel):
    """Cadena de procedencia completa de un artefacto (ADR-0005, subset V1).

    Atestiguada por un actor identificado en un instante dado. La cadena puede
    ser incompleta (``is_complete=False``) siempre que los huecos se declaren
    explícitamente en :attr:`gaps`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_hash: Sha256Hex
    origin_source_id: str = Field(min_length=1)
    steps: list[ProvenanceStep] = Field(default_factory=list)
    is_complete: bool = False
    gaps: list[GapDescription] = Field(default_factory=list)
    attestor: str = Field(min_length=1)
    attested_at: dt.datetime

    @field_validator("attested_at")
    @classmethod
    def _attested_at_must_be_tz_aware(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Provenance.attested_at must be timezone-aware (use UTC)."
            )
        return value

    @model_validator(mode="after")
    def _step_ids_must_be_unique(self) -> Provenance:
        seen: set[int] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(
                    f"duplicate step_id={step.step_id} in Provenance "
                    f"for evidence {self.evidence_hash[:8]}…"
                )
            seen.add(step.step_id)
        return self

    @model_validator(mode="after")
    def _complete_chain_has_no_gaps(self) -> Provenance:
        if self.is_complete and self.gaps:
            raise ValueError(
                "Provenance.is_complete=True conflicts with declared gaps. "
                "A chain claimed as complete cannot list gaps; either remove "
                "gaps or set is_complete=False (the honest default)."
            )
        return self
