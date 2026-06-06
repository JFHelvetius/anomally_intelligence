"""Audit log append-only con cadena de hashes (ADR-0019, ADR-0030 S3).

Dos módulos:

- :mod:`aip.audit.log` — escritura y lectura de entradas, cadena de hashes,
  bootstrap del archive.
- :mod:`aip.audit.verify` — recorrido y comprobación de integridad de la cadena.

Restricción de dependencias (ADR-0030 S3): ``audit`` importa desde ``core`` y
``storage``, nunca desde ``cli``.
"""
