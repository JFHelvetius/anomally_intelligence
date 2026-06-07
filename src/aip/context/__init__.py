"""Capa de Context Assembly (ADR-0035).

``aip.context`` es la **cuarta** capa derivada del archive (después de
``aip.analysis``, ``aip.graph`` y ``aip.impact``). Su única función es
**agregar** los outputs canónicos de ADR-0032/0033/0034 en un único
artefacto consumible y verificable.

**Propiedad central (ADR-0035 §decisión):**

> Context Assembly **agrega resultados existentes**; **no ejecuta
> análisis nuevos** ni **reemplaza** a ADR-0032, ADR-0033 ni ADR-0034.

Cualquier funcionalidad futura que requiera computar información no
derivable de la composición de los outputs canónicos anteriores requiere
ADR de enmienda explícita. Esa restricción es lo que mantiene esta capa
removible sin huella (G2) y agregación pura (G3).
"""

from __future__ import annotations

from aip.context.assembler import (
    ContextAnchorNotFoundError,
    ContextAssemblyError,
    assemble_context,
    compute_context_bundle_hash,
    verify_bundle_hash,
)
from aip.context.models import (
    ASSEMBLY_ENGINE_VERSION,
    ASSEMBLY_METHOD_NAME,
    ContextBundle,
    ContextNode,
    GraphNeighborhood,
)

__all__ = [
    "ASSEMBLY_ENGINE_VERSION",
    "ASSEMBLY_METHOD_NAME",
    "ContextAnchorNotFoundError",
    "ContextAssemblyError",
    "ContextBundle",
    "ContextNode",
    "GraphNeighborhood",
    "assemble_context",
    "compute_context_bundle_hash",
    "verify_bundle_hash",
]
