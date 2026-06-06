"""Modelo de dominio puro (sin I/O, sin filesystem).

Esta capa define los tipos del proyecto (Evidence, Source, Provenance, etc.)
y las primitivas independientes de almacenamiento (hashing, identificadores).
No puede importar desde ``aip.storage``, ``aip.audit`` ni ``aip.cli``
(restricción S1 del ADR-0030).
"""
