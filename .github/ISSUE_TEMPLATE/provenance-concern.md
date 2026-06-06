---
name: Provenance concern
about: Sospecha de drift en pinned values, deriva del fixture canónico, o comportamiento de procedencia no esperado
title: "[provenance] "
labels: provenance, critical
assignees: []
---

> Este template tiene prioridad sobre **bug** y **question** porque cualquier deriva real
> en la cadena de evidencia compromete la credibilidad del proyecto entero. Si tu duda no
> toca pinned values ni reproducibilidad, probablemente quieras el template **bug**.

## ¿Qué pinned value, fixture, o garantía está en duda?

<!--
Lista los identificadores concretos. Ejemplos:
- EXPECTED_PDF_SHA256 (Pre-F1.C)
- EXPECTED_DEMO_MANIFEST_HASH (test_manifest_hash.py)
- EXPECTED_BOOTSTRAP_HASH / EXPECTED_INGEST_HASH (test_audit_chain.py)
- archive_manifest_hash devuelto por `aip archive verify`
- Twining Memo SHA-256 en `tests/data/twining-memo-1947-09-23.pdf`
-->

## Valor observado vs. valor pinned

| Origen | Valor pinned (v0.1.0) | Valor observado |
|---|---|---|
| | | |

## Cómo lo reproduces

```sh
# comandos o llamadas que producen el valor observado
```

## ¿Qué crees que ha cambiado?

Marca lo que aplique:

- [ ] El fichero binario en `tests/data/` (corrupción, sustitución).
- [ ] La canonicalización JCS (`aip.core.hashing`).
- [ ] El layout de tablas V1 (`aip.storage.layout.V1_TABLES`).
- [ ] La forma del `ArchiveManifest` (orden, campos, formato datetime).
- [ ] La cadena del audit log (`AuditEntry`, prev_hash, entry_hash).
- [ ] Una dependencia externa (pyarrow, pydantic) ha alterado bytes de salida.
- [ ] No lo sé; necesito ayuda para diagnosticar.

## Plataforma y versión

- Versión `aip` (`aip --version`): 
- Python:
- Sistema operativo:
- Commit en el que reproduces:

## Si la deriva es REAL y no es bug del proyecto

¿Hay alguna razón legítima por la que el pinned debería actualizarse?
(Cambio en el item de Internet Archive, nuevo fixture canónico aprobado
por ADR, etc.). Si la respuesta es "no", esto es bug crítico.
