"""Capa derivada de análisis de impacto (ADR-0034).

``aip.impact`` es la **tercera** capa derivada del archive (después de
``aip.analysis`` de ADR-0032 y ``aip.graph`` de ADR-0033). Responde a
una sola pregunta operativa concreta:

> "Si este nodo deja de estar disponible, ¿qué conclusiones derivadas
> se ven afectadas?"

Sin AI. Sin scoring. Sin severidad. Sin probabilidad. Sin recomendaciones.
**Sólo reachability inversa sobre el grafo derivado.**

El cumplimiento de las prohibiciones de ADR-0034 §componentes excluidos
se verifica explícitamente en ``tests/unit/impact/test_models.py::
test_no_prohibited_tokens_in_impact_module``.
"""

from __future__ import annotations

from aip.impact.analyzer import ImpactRootNotInGraphError, analyze_removal_impact
from aip.impact.models import (
    ANALYSIS_METHOD_NAME,
    IMPACT_ENGINE_VERSION,
    ImpactNode,
    ImpactReport,
)

__all__ = [
    "ANALYSIS_METHOD_NAME",
    "IMPACT_ENGINE_VERSION",
    "ImpactNode",
    "ImpactReport",
    "ImpactRootNotInGraphError",
    "analyze_removal_impact",
]
