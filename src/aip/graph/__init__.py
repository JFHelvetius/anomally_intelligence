"""Capa derivada de grafo de procedencia (ADR-0033).

``aip.graph`` es la **segunda** capa derivada del archive (la primera es
``aip.analysis``, ADR-0032). Reconstruye un grafo dirigido de procedencia
sobre Evidence, Source y AuthenticationAssessment **sin persistencia
propia, sin librerías externas y sin nuevas entidades**.

Sus garantías arquitectónicas (ADR-0033 §G1-G5):

- G1: no es nueva fuente de verdad; función pura del estado del archive.
- G2: removible sin huella; no escribe al archive.
- G3: reproducible bit a bit; orden canónico explícito.
- G4: sin dependencias externas (networkx, etc.).
- G5: no rompe compatibilidad hacia atrás.

NO es ADR-0011 (Knowledge Graph): no introduce nodos para personas,
organizaciones, eventos, claims, hipótesis. ADR-0011 sigue diferido por
ADR-0023; ampliar este grafo requiere ADR específico.
"""

from __future__ import annotations

from aip.graph.builder import build_graph
from aip.graph.models import (
    EdgeKind,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    NodeKind,
)
from aip.graph.query import (
    GraphIntegrityIssue,
    get_assessments_for_evidence,
    get_dependency_chain,
    get_evidence_for_assessment,
    get_reverse_dependencies,
    validate_graph_integrity,
)

__all__ = [
    "EdgeKind",
    "EvidenceGraph",
    "GraphEdge",
    "GraphIntegrityIssue",
    "GraphNode",
    "NodeKind",
    "build_graph",
    "get_assessments_for_evidence",
    "get_dependency_chain",
    "get_evidence_for_assessment",
    "get_reverse_dependencies",
    "validate_graph_integrity",
]
