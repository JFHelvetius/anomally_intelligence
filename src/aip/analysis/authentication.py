"""Motor derivado de evaluación de autenticidad (ADR-0032).

Este módulo **no** decide si una evidencia es auténtica. Convierte el estado
actual del archive (Evidence + Source + Provenance) en un artefacto estructurado
y reproducible que clasifica la evidencia en una de cinco categorías
deterministas, junto con la racionalización textual de por qué se llegó a esa
clasificación y la lista de fuentes que la respaldan.

Garantías arquitectónicas (ADR-0032):

1. **No es verdad.** Es interpretación derivada del estado del archive.
2. **No es inferencia probabilística.** Las reglas son booleanas, no hay
   scoring continuo.
3. **No sustituye investigación humana.** Es un punto de partida documentado,
   no un veredicto.
4. **Es removible.** Eliminar cualquier ``AuthenticationAssessment`` jamás
   altera la Evidence original, su Source, su Provenance ni su audit chain.

El modelo persiste en la tabla ``authentication_assessments`` reservada por
ADR-0015 — sin layout nuevo, sin schema_version nuevo, sin migración. Los
``schema_hashes`` pinned del manifest (ADR-0024 §formato canónico) son agnósticos
del payload: la canonicalización es por contenido JCS, no por columnas Parquet.

Convivencia con :class:`aip.core.evidence.AuthenticationAssessment`:

- La de ``core/evidence`` es el **slot embebido** en Evidence — un campo
  estructural histórico nunca poblado en V1 (default ``UNVERIFIED``,
  inmutable junto con Evidence).
- La de ``analysis/authentication`` (este módulo) es el **artefacto derivado**
  que vive en la tabla. Misma denominación, ámbitos disjuntos: una identifica
  la evidencia ingresada, la otra interpreta el estado del archive en un
  instante dado.

El ADR-0032 §convivencia documenta la dualidad y por qué no se renombran:
romper el nombre embebido tocaría la canonicalización de Evidence y por tanto
``EXPECTED_DEMO_MANIFEST_HASH``.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aip._version import SCHEMA_VERSION

# --------------------------------------------------------------------- enums


class AssessmentStatus(StrEnum):
    """Categoría discreta del veredicto derivado (ADR-0032 §2).

    Cerrada por ADR. Cada valor mapea a una regla determinista en
    :func:`_classify`. No es escala ordinal: ``CONTRADICTED`` y ``UNVERIFIED``
    no son comparables como "más / menos auténtico"; son estados cualitativos.
    """

    UNKNOWN = "unknown"
    """Estado de inicialización; reservado para futuros métodos que aún no
    aplican reglas. No emitido por las reglas V1."""

    UNVERIFIED = "unverified"
    """El archive no documenta ninguna fuente para esta evidencia."""

    PARTIALLY_SUPPORTED = "partially_supported"
    """Hay al menos una fuente conocida pero ningún paso de procedencia
    declarado: la cadena de custodia está vacía."""

    SUPPORTED = "supported"
    """Hay fuentes + pasos de procedencia + todas las referencias resuelven."""

    CONTRADICTED = "contradicted"
    """El archive tiene una referencia rota: la Source referenciada por la
    Evidence no existe, o la Provenance referencia un ``origin_source_id``
    que no aparece en la tabla ``sources``."""


class AssessmentMethod(StrEnum):
    """Método aplicado para producir el assessment (ADR-0032 §2).

    Cerrada por ADR. No describe el algoritmo interno; describe **qué tipo de
    pregunta** se respondió. Los tres valores V1 son ortogonales al cuerpo de
    la regla aplicada — la implementación V1 es uniforme; los métodos sirven
    como etiqueta semántica para distinguir assessments creados con propósitos
    distintos sobre la misma Evidence.
    """

    MANUAL_RESEARCH = "manual_research"
    """Marcador de assessment producido para acompañar revisión humana. La
    regla determinista se aplica igualmente; el método aclara la intención."""

    PROVENANCE_REVIEW = "provenance_review"
    """Revisión centrada en la cadena de procedencia. Método por defecto del
    CLI ``aip assess-authentication``."""

    CHAIN_OF_CUSTODY_REVIEW = "chain_of_custody_review"
    """Revisión centrada en la integridad de la cadena de custodia entre
    Source y Evidence."""


# --------------------------------------------------------------------- model


class AuthenticationAssessment(BaseModel):
    """Artefacto derivado e inmutable que registra una evaluación de
    autenticidad sobre una Evidence concreta (ADR-0032 §1).

    Frozen + ``extra="forbid"`` para conservar las garantías arquitectónicas
    de los demás modelos hasheables del proyecto (ADR-0006 §inmutabilidad).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9._\-]+$",
        description=(
            "Identidad determinista del assessment. Por construcción "
            "``{evidence_id}__{method.value}``, ASCII safe para servir de "
            "row_id de la tabla."
        ),
    )
    evidence_id: str = Field(
        min_length=1,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hex de la Evidence evaluada (= Evidence.hash).",
    )
    created_at: dt.datetime = Field(
        description=(
            "Instante UTC tz-aware al que se atribuye este assessment. "
            "``microsecond=0`` obligatorio para reproducibilidad bit a bit "
            "(ADR-0024 L2)."
        ),
    )
    method: AssessmentMethod
    status: AssessmentStatus
    rationale: str = Field(
        min_length=1,
        description=(
            "Texto fijo derivado de la rama de regla aplicada — no es prosa "
            "libre del operador. Las cinco cadenas posibles viven en "
            ":data:`RATIONALES`."
        ),
    )
    supporting_source_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Lista ordenada de ``Source.id`` que respaldan la evidencia. "
            "Vacía si ninguna fuente del archive cubre esta Evidence."
        ),
    )
    schema_version: str = Field(
        min_length=1,
        description=(
            "SemVer del esquema de datos del proyecto al construir este "
            "assessment. Distinto de ``assessment_schema_version`` futuro "
            "si ADR-0032 §evolución se reabre."
        ),
    )

    @field_validator("created_at")
    @classmethod
    def _created_at_canonical(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError(
                "AuthenticationAssessment.created_at must be timezone-aware "
                "(use UTC). ADR-0031 R1."
            )
        if value.microsecond != 0:
            raise ValueError(
                "AuthenticationAssessment.created_at must have "
                "microsecond=0 for canonical reproducibility (ADR-0024 L2)."
            )
        return value

    @field_validator("supporting_source_ids")
    @classmethod
    def _source_ids_ordered_and_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError(
                "supporting_source_ids must not contain duplicates."
            )
        if value != sorted(value):
            raise ValueError(
                "supporting_source_ids must be sorted lexicographically for "
                "canonical reproducibility."
            )
        return value


# --------------------------------------------------------------------- rationales

RATIONALES: Final[dict[AssessmentStatus, str]] = {
    AssessmentStatus.UNVERIFIED: (
        "No hay fuentes documentadas en el archive para esta evidencia."
    ),
    AssessmentStatus.PARTIALLY_SUPPORTED: (
        "Hay al menos una fuente documentada, pero la cadena de procedencia "
        "no declara pasos: la cadena de custodia está vacía."
    ),
    AssessmentStatus.SUPPORTED: (
        "Hay fuentes documentadas y pasos de procedencia; todas las "
        "referencias del archive se resuelven."
    ),
    AssessmentStatus.CONTRADICTED: (
        "El archive tiene al menos una referencia rota: Source o "
        "origin_source_id referenciados no existen en este archive."
    ),
    AssessmentStatus.UNKNOWN: (
        "Estado de inicialización; ninguna regla V1 emite UNKNOWN."
    ),
}
"""Texto canónico por estado. La rationale forma parte del payload hasheable;
cambiarla romperá los row_hashes de assessments previos — los rationales se
versionan implícitamente vía ``schema_version`` cuando se decida abrirlo."""


# --------------------------------------------------------------------- build helpers


def make_assessment_id(evidence_id: str, method: AssessmentMethod) -> str:
    """Identidad determinista del assessment.

    Forma canónica: ``"{evidence_id}__{method.value}"``. Determinista por
    construcción: mismo (evidence_id, method) ⇒ mismo assessment_id.

    No es opaco: un humano puede leer qué Evidence y qué método representa
    a simple vista. Es ASCII safe para servir directamente como ``row_id``
    en :func:`aip.storage.tables.append_row` (validado contra
    ``[A-Za-z0-9._-]+``).
    """
    return f"{evidence_id}__{method.value}"


def classify(
    *,
    source_exists: bool,
    has_provenance_steps: bool,
    provenance_reference_intact: bool,
) -> tuple[AssessmentStatus, list[str]]:
    """Aplica la regla determinista (ADR-0032 §2).

    Inputs booleanos puros — sin contexto del archive, sin I/O, sin
    aleatoriedad. La lógica entera vive aquí; el resto del módulo solo
    extrae estos tres booleans del estado y construye el modelo.

    Returns:
        Tuple ``(status, supporting_source_ids_filler)``. El segundo
        elemento siempre es ``[]`` — el caller añade las IDs reales
        después de validar :data:`source_exists`. Estructura prevista para
        que la regla pueda evolucionar sin reescribir el caller.
    """
    if not provenance_reference_intact:
        # Una referencia rota es siempre evidencia de contradicción
        # estructural; gana sobre cualquier otro criterio.
        return AssessmentStatus.CONTRADICTED, []
    if not source_exists:
        # Sin fuente conocida no hay base documental que evaluar.
        return AssessmentStatus.UNVERIFIED, []
    if not has_provenance_steps:
        # Source presente pero cadena vacía: respaldo parcial.
        return AssessmentStatus.PARTIALLY_SUPPORTED, []
    # Source presente + ≥1 paso + referencias intactas: respaldo pleno
    # según el estado actual del archive (no es veredicto sustantivo).
    return AssessmentStatus.SUPPORTED, []


# --------------------------------------------------------------------- public API


def build_authentication_assessment(
    *,
    evidence_id: str,
    source_exists: bool,
    has_provenance_steps: bool,
    provenance_reference_intact: bool,
    supporting_source_ids: list[str],
    method: AssessmentMethod,
    created_at: dt.datetime,
) -> AuthenticationAssessment:
    """Construye un :class:`AuthenticationAssessment` aplicando la regla V1.

    Funcionalmente puro: dado un mismo tuple de inputs, devuelve el mismo
    assessment bit a bit. Es la **fase 3** de ADR-0032: ningún I/O, ningún
    reloj de pared, ningún recurso externo.

    El caller (``aip.archive.Archive.assess_authentication``) es quien lee
    el archive, deriva los booleanos y la lista de IDs, e inyecta el reloj.
    Esa separación de responsabilidades hace trivial probar la regla en
    aislamiento con cualquier combinación de inputs.

    Args:
        evidence_id: SHA-256 hex de la Evidence objetivo.
        source_exists: ¿la Source referenciada existe en la tabla ``sources``?
        has_provenance_steps: ¿la Provenance tiene ≥1 paso declarado?
        provenance_reference_intact: ¿la ``origin_source_id`` de la
            Provenance, si existe, está presente en ``sources``? Si no hay
            Provenance, ``True``.
        supporting_source_ids: IDs de Source que respaldan; el caller las
            ordena y deduplica vía el validador del modelo.
        method: Método del assessment.
        created_at: Instante UTC tz-aware sin microsegundos (inyectado).

    Returns:
        El :class:`AuthenticationAssessment` correspondiente.
    """
    status, _ = classify(
        source_exists=source_exists,
        has_provenance_steps=has_provenance_steps,
        provenance_reference_intact=provenance_reference_intact,
    )
    # Si la rama no es SUPPORTED/PARTIALLY_SUPPORTED, no acreditamos
    # fuentes: aunque ``source_exists`` sea True, una referencia rota
    # invalida el respaldo.
    canonical_supporting = (
        sorted(set(supporting_source_ids))
        if status
        in {AssessmentStatus.PARTIALLY_SUPPORTED, AssessmentStatus.SUPPORTED}
        else []
    )
    return AuthenticationAssessment(
        assessment_id=make_assessment_id(evidence_id, method),
        evidence_id=evidence_id,
        created_at=created_at,
        method=method,
        status=status,
        rationale=RATIONALES[status],
        supporting_source_ids=canonical_supporting,
        schema_version=SCHEMA_VERSION,
    )
