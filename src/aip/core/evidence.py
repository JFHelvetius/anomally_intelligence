"""Modelo formal de :class:`Evidence` (ADR-0006, subset V1).

V1 implementa el núcleo comprometido en ADR-0023 §V1.3:

- ``hash`` (SHA-256 hex lowercase 64).
- ``kind`` (``EvidenceKind``).
- ``content_uri`` (path POSIX relativo a la raíz del archive, ADR-0031 R3).
- ``size_bytes`` (entero no negativo).
- ``mime_type``.
- ``source_id``.
- ``status`` (``EvidenceStatus``).
- ``authentication`` (``AuthenticationAssessment``).
- ``ingested_at`` (datetime tz-aware UTC obligatorio).
- ``ingested_by`` (ActorId textual).
- ``schema_version`` (SemVer del esquema, ADR-0016).
- ``notes`` (opcional).
- ``intrinsic_metadata`` (``dict[str, str]`` opcional).

Campos del ADR-0006 deliberadamente **fuera** de V1: ``provenance`` y
``source`` se almacenan como entidades distintas y se referencian; las
estructuras :class:`Provenance`, :class:`Source`, ``TemporalAnchor`` y
``SpatialAnchor`` no se embeben en :class:`Evidence`. Esa decisión es
coherente con el modelo evidence-first (ADR-0002) y con el recorte de V1.

Inmutabilidad (``frozen=True``) y rechazo de campos desconocidos
(``extra="forbid"``) son requisitos arquitectónicos, no estilo.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------- enums


class EvidenceKind(StrEnum):
    """Tipos intrínsecos de evidencia (ADR-0006). Cerrado; ampliación por ADR."""

    DOCUMENT_TEXT = "document_text"
    DOCUMENT_SCAN = "document_scan"
    STILL_IMAGE = "still_image"
    MOVING_IMAGE = "moving_image"
    AUDIO_RECORDING = "audio_recording"
    SENSOR_LOG = "sensor_log"
    DATASET_TABLE = "dataset_table"
    SPATIAL_DATA = "spatial_data"
    CODE_OR_MODEL = "code_or_model"
    CORRESPONDENCE = "correspondence"
    INTERVIEW_TRANSCRIPT = "interview_transcript"
    PHYSICAL_SPECIMEN_REPORT = "physical_specimen_report"
    COMPOSITE = "composite"


class EvidenceStatus(StrEnum):
    """Salud operativa de la evidencia (ADR-0006). Ortogonal a la credibilidad."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    RETRACTED = "retracted"
    QUARANTINED = "quarantined"


class AuthStatus(StrEnum):
    """Estado de autenticación (ADR-0006). Default operacional al ingestar:
    :attr:`UNVERIFIED`."""

    AUTHENTIC = "authentic"
    PROVISIONALLY_AUTHENTIC = "provisionally_authentic"
    UNVERIFIED = "unverified"
    INCONCLUSIVE = "inconclusive"
    PROVISIONALLY_INAUTHENTIC = "provisionally_inauthentic"
    INAUTHENTIC = "inauthentic"


# --------------------------------------------------------------------- field types

# SHA-256 hex lowercase, longitud exacta 64 (ADR-0016).
_SHA256_HEX_PATTERN: Final[str] = r"^[a-f0-9]{64}$"

Sha256Hex = Annotated[
    str,
    Field(
        pattern=_SHA256_HEX_PATTERN,
        min_length=64,
        max_length=64,
        description="SHA-256 hex lowercase, ADR-0016.",
    ),
]


# --------------------------------------------------------------------- models


class AuthenticationAssessment(BaseModel):
    """Evaluación estructurada de autenticidad (ADR-0006 §AuthenticationAssessment).

    En V1 se almacena el subset operativo: ``status``, ``assessor``,
    ``assessed_at``, ``method``, ``notes``. Los campos ``evidence_for``,
    ``evidence_against`` y ``open_questions`` del ADR completo se difieren
    a una fase posterior (no hay segundo objeto Evidence que referenciar
    en V1 más allá del fixture canónico).

    Default conservador: ``status=UNVERIFIED`` sin assessor. Es lo que se
    asigna a una evidencia recién ingestada que aún no ha pasado peritaje.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AuthStatus = AuthStatus.UNVERIFIED
    assessor: str | None = None
    assessed_at: dt.datetime | None = None
    method: str | None = None
    notes: str | None = None

    @field_validator("assessed_at")
    @classmethod
    def _assessed_at_must_be_tz_aware(
        cls, value: dt.datetime | None
    ) -> dt.datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "assessed_at must be timezone-aware (use UTC). "
                "ADR-0031 R1: wall-clock timestamps without tz are non-reproducible."
            )
        return value


class Evidence(BaseModel):
    """Artefacto ingestado al archive (ADR-0006, subset V1).

    Inmutable por construcción. La identidad del objeto es ``hash`` (SHA-256
    sobre los bytes crudos del artefacto, ADR-0016). El ``content_uri`` es la
    ruta POSIX relativa al archive root (ADR-0031 R3) — usa ``/`` siempre,
    independientemente del SO host.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    hash: Sha256Hex
    kind: EvidenceKind
    content_uri: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    mime_type: str = Field(min_length=1)

    source_id: str = Field(min_length=1)

    status: EvidenceStatus = EvidenceStatus.ACTIVE
    authentication: AuthenticationAssessment = Field(
        default_factory=AuthenticationAssessment
    )

    ingested_at: dt.datetime
    ingested_by: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)

    notes: str | None = None
    intrinsic_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("ingested_at")
    @classmethod
    def _ingested_at_must_be_tz_aware(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError(
                "ingested_at must be timezone-aware (use UTC). "
                "ADR-0031 R1: wall-clock timestamps without tz are non-reproducible."
            )
        return value

    @field_validator("content_uri")
    @classmethod
    def _content_uri_must_be_posix(cls, value: str) -> str:
        if "\\" in value:
            raise ValueError(
                "content_uri must use POSIX-style separators ('/'), not '\\\\'. "
                "ADR-0031 R3: archive-internal paths are POSIX independent of host OS."
            )
        return value

    def aip_uri(self) -> str:
        """URI estable del artefacto conforme a ADR-0016 §URI scheme ``aip:``.

        Forma canónica: ``aip:evidence/sha256:<hash>``.
        """
        return f"aip:evidence/sha256:{self.hash}"
