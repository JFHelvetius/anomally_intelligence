"""Versión del paquete `aip` y del esquema de datos (ADR-0016, ADR-0030)."""

__version__ = "0.0.1"
"""SemVer del paquete. Cambia por release."""

SCHEMA_VERSION = "0.1.0"
"""SemVer del esquema de datos. Cambia solo cuando la forma canónica de
``Evidence``, ``Source``, ``Provenance``, ``ProvenanceStep`` o ``AuditEntry``
cambia. Migración entre versiones requiere ADR específico (ADR-0016)."""
