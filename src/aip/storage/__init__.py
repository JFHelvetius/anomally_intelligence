"""Capa de persistencia local del archive (ADR-0015).

Tres responsabilidades:

- :mod:`aip.storage.layout` — paths canónicos, CAOS y bootstrap del archive.
- :mod:`aip.storage.manifest` — ``ArchiveManifest`` y su hash canónico.
- :mod:`aip.storage.tables` — append-only Parquet sobre las tablas V1.

Restricción de dependencias (ADR-0030 S2): ``storage`` puede importar desde
``core`` pero no desde ``audit`` ni ``cli``.
"""
