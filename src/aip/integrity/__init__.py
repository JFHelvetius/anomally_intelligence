"""Derived-artifact integrity checker (post-ADR-0040 hardening).

``aip.integrity`` audita la integridad referencial cruzada de los
artefactos derivados persistidos en el archive:
``<archive>/{workspaces,timelines,snapshots,justifications}/``.

Es **opt-in** vía ``aip archive verify --derived``. El comportamiento por
defecto de ``aip archive verify`` permanece **inalterado** (G5 de cada
ADR de capa derivada). Cero modificación de comportamiento default.

**Propiedad central:**

> Integrity checker **enumera incidencias** estructurales — hash
> mismatches, referencias rotas a tablas base, ruptura de la cadena
> workspace → timeline → snapshot. **No infiere. No clasifica. No
> prioriza.** Sólo reporta.
"""

from __future__ import annotations

from aip.integrity.models import (
    INTEGRITY_ENGINE_VERSION,
    INTEGRITY_METHOD_NAME,
    DerivedIntegrityIssue,
    DerivedIntegrityReport,
    IntegrityIssueKind,
)
from aip.integrity.verify import verify_derived_integrity

__all__ = [
    "INTEGRITY_ENGINE_VERSION",
    "INTEGRITY_METHOD_NAME",
    "DerivedIntegrityIssue",
    "DerivedIntegrityReport",
    "IntegrityIssueKind",
    "verify_derived_integrity",
]
