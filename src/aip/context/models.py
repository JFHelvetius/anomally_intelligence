"""Modelos de la capa de Context Assembly (ADR-0035 §modelo).

Tres dataclasses frozen y dos constantes. Cero floats, cero campos
interpretativos. Todos los datos se exponen como aparecen en sus
fuentes canónicas (ADR-0032/0033/0034 + tablas de core).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ASSEMBLY_ENGINE_VERSION: Final[str] = "1.0.0"
"""SemVer del motor de Context Assembly (ADR-0035)."""

ASSEMBLY_METHOD_NAME: Final[str] = "evidence_centric_v1"
"""Etiqueta cerrada del método de ensamble V1.

Anchor por evidencia es el caso primario (de ahí "evidence_centric");
los anchors de tipo assessment / source son soportados como
generalización natural del mismo algoritmo.
"""


@dataclass(frozen=True, order=True)
class ContextNode:
    """Nodo del barrio del grafo proyectado en el bundle.

    Mismo shape estructural que :class:`aip.impact.models.ImpactNode`
    pero con etiqueta semántica distinta: ``distance_from_anchor``
    (no ``distance_from_root``). Deliberadamente no se reutiliza
    ``ImpactNode``: el bundle debe ser legible sin importar nombres
    de la capa de impacto. La duplicación es intencional y minúscula.
    """

    distance_from_anchor: int
    node_type: str
    node_id: str


@dataclass(frozen=True)
class GraphNeighborhood:
    """Vista canónica del barrio del grafo alrededor del anchor.

    ``upstream`` es el cierre transitivo de **dependencias** (aristas
    salientes desde el anchor); ``downstream`` es el cierre transitivo
    de **dependientes** (aristas entrantes al anchor). Ambos
    canónicamente ordenados.
    """

    upstream: tuple[ContextNode, ...]
    downstream: tuple[ContextNode, ...]


@dataclass(frozen=True)
class ContextBundle:
    """Artefacto único y determinista agregando todas las capas derivadas.

    Construido **exclusivamente** por composición de:

    - Lecturas de las tablas ``evidence``, ``sources``, ``provenance``.
    - Outputs de ADR-0032 (``Archive.list_authentication_assessments``).
    - Outputs de ADR-0033 (``build_graph``).
    - Outputs de ADR-0034 (``analyze_removal_impact``).

    Sin reloj, sin aleatoriedad, sin escrituras al archive. La identidad
    del bundle vive en ``context_bundle_hash`` y su anclaje al estado
    del archive en ``source_manifest_hash`` (ADR-0035 §hashes).
    """

    # Identidad del anchor
    anchor_node_kind: str
    anchor_node_id: str

    # Lecturas literales del archive
    evidence: dict[str, object] | None
    source: dict[str, object] | None
    provenance: dict[str, object] | None
    derived_assessments: tuple[dict[str, object], ...]

    # Proyección del grafo
    graph_neighborhood: GraphNeighborhood

    # Reporte de impacto agregado tal cual lo devuelve ADR-0034
    impact_report: dict[str, object]

    # Honesty fields
    assembly_engine_version: str
    assembly_method_name: str
    schema_version: str

    # Hashes encadenados (ADR-0035 §hashes)
    source_manifest_hash: str
    context_bundle_hash: str
