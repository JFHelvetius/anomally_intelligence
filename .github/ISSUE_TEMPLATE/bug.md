---
name: Bug report
about: Algo no funciona como dice la documentación o como deberían operar los pinned values
title: "[bug] "
labels: bug
assignees: []
---

## Resumen

<!-- Una a tres frases sobre qué esperabas que ocurriera y qué pasó. -->

## Comando o llamada que reproduce el problema

```sh
aip <subcomando> ...
```

o el equivalente en API Python:

```python
from aip import Archive
...
```

## Comportamiento esperado

<!-- Cita el ADR, la sección de Pre-F1.D o el test que define el comportamiento esperado. -->

## Comportamiento observado

<!-- Output literal, exit code, stack trace si aplica. -->

## Entorno

- Versión `aip`: <!-- `aip --version` -->
- Python: <!-- `python --version` -->
- Sistema operativo: <!-- p. ej. Ubuntu 24.04, macOS 14 arm64, Windows 11 -->
- Commit / tag en el que ocurre: <!-- p. ej. v0.1.0 o sha7 -->

## Impacto sobre las cuatro garantías

Por favor marca lo que aplique. Si alguna se ve afectada, esto sube a
**bug arquitectónico crítico** y debe priorizarse sobre cualquier otro
trabajo de mantenimiento.

- [ ] **Provenance** — la cadena fuente→evidencia se ve afectada.
- [ ] **Integridad de evidencia** — el hash de un blob ingestado no coincide con su contenido.
- [ ] **Reproducibilidad** — dos ejecuciones con el mismo input producen resultados distintos.
- [ ] **Hash stability** — un pinned value (`EXPECTED_*` en `tests/reproducibility/`) cambia respecto a `v0.1.0`.
- [ ] Ninguna de las anteriores; bug local sin impacto en la cadena.
