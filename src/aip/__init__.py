"""Anomaly Intelligence Platform — archive con evidencia como ciudadano de primera clase.

La superficie pública de V1 es deliberadamente mínima conforme a ADR-0023
(Scope Reduction). Lo que se expone aquí es lo único que se compromete como
estable en el primer release; el resto del repositorio es trabajo en curso.

Documentos canónicos para entender el alcance:

- ``docs/adr/0000-long-term-vision.md`` — la brújula.
- ``docs/adr/0023-scope-reduction.md`` — qué entra y qué no en V1.
- ``docs/phase-1/command-specification.md`` — contrato de la CLI.

Componentes implementados en V1:

- Modelo de evidencia, fuente y procedencia (subpaquete ``core``).
- Almacenamiento CAOS + Parquet + manifiesto (subpaquete ``storage``).
- Audit log append-only con cadena de hashes (subpaquete ``audit``).
- CLI (subpaquete ``cli``).

Componentes diseñados pero **NO** implementados en V1 (diferidos por ADR-0023):

- Claims, hipótesis competidoras, conclusiones, ciclo de vida de casos.
- Grafo de conocimiento, motor temporal, motor geoespacial.
- Adquisidores OSINT, HTTP API, búsqueda léxica/semántica.
- Asistencia LLM, enclave de material sensible.
"""

from __future__ import annotations

from aip._version import SCHEMA_VERSION, __version__
from aip.archive import (
    Archive,
    CheckResult,
    EvidenceView,
    VerificationReport,
)
from aip.errors import (
    AIPError,
    ArchiveNotFoundError,
    AuditChainError,
    EvidenceNotFoundError,
    IntegrityError,
    InvalidSourceMetadataError,
    ManifestError,
    UsageError,
)

__all__ = [
    "SCHEMA_VERSION",
    "AIPError",
    "Archive",
    "ArchiveNotFoundError",
    "AuditChainError",
    "CheckResult",
    "EvidenceNotFoundError",
    "EvidenceView",
    "IntegrityError",
    "InvalidSourceMetadataError",
    "ManifestError",
    "UsageError",
    "VerificationReport",
    "__version__",
]
