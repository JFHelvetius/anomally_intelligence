"""Modelos del motor de impacto (ADR-0034 §modelo).

Cinco constantes / dos dataclasses frozen, todas declarativas. Sin floats,
sin enums de severidad, sin campos derivados de modelos probabilísticos.

Honesty fields (ADR-0034 §honesty):

- :data:`IMPACT_ENGINE_VERSION` — SemVer del motor de impacto. Cambia
  cuando la regla evoluciona; cualquier consumidor que pinea reportes
  debe revisar esta constante.
- :data:`ANALYSIS_METHOD_NAME` — etiqueta fija del método aplicado.
  V1 sólo conoce ``"dependency_reachability_v1"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

IMPACT_ENGINE_VERSION: Final[str] = "1.0.0"
"""SemVer del motor de análisis de impacto (ADR-0034)."""

ANALYSIS_METHOD_NAME: Final[str] = "dependency_reachability_v1"
"""Etiqueta cerrada del método aplicado en V1.

Cualquier sustitución por otro método (e.g., un futuro
``dependency_reachability_v2`` que cambie cómo se manejan ciclos)
requiere ADR de enmienda + actualización pública de los consumidores
que pinea reportes.
"""


@dataclass(frozen=True, order=True)
class ImpactNode:
    """Unidad de traversal del análisis de impacto (ADR-0034 §modelo).

    El campo ``distance_from_root`` está primero para que el orden
    canónico natural ``(distance, node_type, node_id)`` coincida con el
    layout BFS — los más cercanos al root aparecen antes.
    """

    distance_from_root: int
    node_type: str
    node_id: str


@dataclass(frozen=True)
class ImpactReport:
    """Reporte declarativo del impacto downstream de un nodo (ADR-0034).

    Contrato mínimo intencionalmente austero. Las únicas métricas
    publicadas son **observables del grafo**: listas de IDs, profundidad
    de propagación, conteo total. No hay severidad, ranking ni
    interpretación.

    Los honesty fields (``analysis_engine_version``, ``schema_version``,
    ``analysis_method_name``) declaran explícitamente **qué tipo de
    respuesta** está dando el motor. Su presencia es el contrato:
    cualquier consumidor que recibe un ImpactReport sabe que está
    leyendo reachability bruta, no un veredicto.
    """

    root_node_id: str
    affected_assessments: list[str]
    affected_evidence: list[str]
    dependency_depth_max: int
    total_affected_nodes: int
    analysis_engine_version: str
    schema_version: str
    analysis_method_name: str = ANALYSIS_METHOD_NAME

    def __post_init__(self) -> None:
        # Defensa estructural: las listas deben venir ya canónicamente
        # ordenadas y sin duplicados. El analyzer es el único productor
        # legítimo y respeta esta invariante; verificarla aquí evita
        # que reportes construidos a mano en tests reintroduzcan
        # no-determinismo silencioso.
        if list(self.affected_assessments) != sorted(set(self.affected_assessments)):
            raise ValueError(
                "ImpactReport.affected_assessments must be a sorted list "
                "of unique IDs (ADR-0034 §determinismo)."
            )
        if list(self.affected_evidence) != sorted(set(self.affected_evidence)):
            raise ValueError(
                "ImpactReport.affected_evidence must be a sorted list of "
                "unique IDs (ADR-0034 §determinismo)."
            )
        if self.dependency_depth_max < 0:
            raise ValueError(
                "ImpactReport.dependency_depth_max must be non-negative."
            )
        if self.total_affected_nodes < 0:
            raise ValueError(
                "ImpactReport.total_affected_nodes must be non-negative."
            )
