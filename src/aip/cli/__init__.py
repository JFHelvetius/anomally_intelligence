"""CLI delgada sobre :class:`aip.Archive` (ADR-0017, ADR-0030).

Capa adapter, sin lógica de dominio: cada subcomando construye el
:class:`aip.Archive` y delega. Mapea :class:`aip.errors.AIPError` a códigos
de salida según ``docs/phase-1/command-specification.md`` §G5.
"""
