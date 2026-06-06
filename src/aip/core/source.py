"""Modelo de :class:`Source` (ADR-0005, subset V1).

V1 implementa el subset comprometido por ADR-0023 §V1.4:

- ``id``, ``kind``, ``name``, ``authority`` (obligatorios para registrar fuente).
- ``jurisdiction``, ``license``, ``first_seen`` (opcionales).
- ``notes`` (markdown opcional).

El campo ``contact_info`` del ADR-0005 completo se difiere; los actores
(:class:`Actor`) se modelan como wrapper textual mínimo para que las fases
posteriores puedan extenderlo sin romper V1.

Restricciones:

- ``id`` es identificador estable elegido por el curador (no hash). Cadena
  no vacía sin espacios al borde, recomendación kebab-case (no impuesta).
- ``jurisdiction`` se almacena como código ISO 3166-1 alpha-2 (mayúsculas).
  No se valida contra catálogo oficial en V1 — solo forma.
- ``first_seen`` es ``datetime.date`` (no datetime) porque el día basta para
  procedencia de fuente.

Inmutabilidad y rechazo de campos desconocidos: idénticos a :class:`Evidence`.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import Enum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------- enums


class SourceKind(str, Enum):
    """Categoría intrínseca de la fuente (ADR-0005). Cerrada por ADR."""

    GOVERNMENT_ARCHIVE = "government_archive"
    MILITARY_REPORT = "military_report"
    ACADEMIC_PUBLICATION = "academic_publication"
    CIVILIAN_ORGANIZATION = "civilian_organization"
    NEWS_OUTLET = "news_outlet"
    WITNESS_TESTIMONY = "witness_testimony"
    PERSONAL_ARCHIVE = "personal_archive"
    PHYSICAL_ARTIFACT = "physical_artifact"
    INSTRUMENT_READING = "instrument_reading"
    AUDIOVISUAL_RECORDING = "audiovisual_recording"
    ONLINE_AGGREGATOR = "online_aggregator"
    SOCIAL_MEDIA = "social_media"
    UNKNOWN = "unknown"


class AuthorityLevel(str, Enum):
    """Nivel de autoridad de la fuente (ADR-0005).

    No mide credibilidad: mide proximidad a la fuente reconstruible primaria.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNATTRIBUTABLE = "unattributable"


class ActorKind(str, Enum):
    """Tipo de actor (ADR-0005). Forward-compatible para fases posteriores."""

    PERSON = "person"
    ORGANIZATION = "organization"
    SYSTEM = "system"
    ANONYMOUS = "anonymous"


# --------------------------------------------------------------------- field types

# ISO 3166-1 alpha-2: dos letras mayúsculas.
_ISO3166_ALPHA2_PATTERN: Final[str] = r"^[A-Z]{2}$"

Iso3166Alpha2 = Annotated[
    str,
    Field(
        pattern=_ISO3166_ALPHA2_PATTERN,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (uppercase).",
    ),
]

# ID textual estable. Caracteres ASCII imprimibles sin espacios externos.
_SOURCE_ID_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._\-]*$"
_SOURCE_ID_RE: Final[re.Pattern[str]] = re.compile(_SOURCE_ID_PATTERN)


# --------------------------------------------------------------------- models


class Actor(BaseModel):
    """Identidad textual mínima de un actor (ADR-0005).

    En V1 el sistema almacena ActorId como cadena en :class:`Evidence` y otros
    sitios; este tipo existe como wrapper forward-compatible para fases
    posteriores donde Persona / Organización / Sistema se distingan
    estructuralmente.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    kind: ActorKind = ActorKind.ANONYMOUS
    display_name: str | None = None


class Source(BaseModel):
    """Origen reconstruible de un artefacto ingestado (ADR-0005, subset V1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    kind: SourceKind
    name: str = Field(min_length=1)
    authority: AuthorityLevel

    jurisdiction: Iso3166Alpha2 | None = None
    license: str | None = None
    first_seen: dt.date | None = None
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def _id_must_be_well_formed(cls, value: str) -> str:
        if not _SOURCE_ID_RE.match(value):
            raise ValueError(
                "Source.id must start with [A-Za-z0-9] and contain only "
                "[A-Za-z0-9._-] (no whitespace, no leading separator)."
            )
        return value
