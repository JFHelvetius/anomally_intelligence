<!--
Este template encuadra la revisión sobre las cuatro garantías del framing
v0.1.0 (evidence first). NO es burocracia: las cuatro casillas existen
porque cualquier cambio en alguna de ellas convierte un PR de mantenimiento
en cambio arquitectónico que necesita ADR.
-->

## Resumen

<!-- Una o dos frases sobre qué cambia el PR y por qué. -->

## Tipo de cambio

Marca lo que aplique:

- [ ] Bugfix (D2 del MAINTAINERS.md)
- [ ] Mejora de rendimiento sin cambio de semántica (D2)
- [ ] Documentación / refactor interno (D2)
- [ ] Tests adicionales (D2)
- [ ] Cambio que afecta a un ADR vigente — **requiere ADR de enmienda mergeado primero** (D1)
- [ ] Ampliación de alcance respecto a ADR-0023 — **requiere ADR de levantamiento** (D1)

## Las cuatro garantías

Para cada una, indica si el cambio afecta o no. Si afecta a cualquiera,
explica cómo y enlaza el ADR que lo justifica.

- [ ] **Provenance:** la cadena fuente → evidencia se mantiene intacta.
- [ ] **Integridad de evidencia:** los hashes ingestados siguen coincidiendo con los bytes en CAOS.
- [ ] **Reproducibilidad:** dos ejecuciones del pipeline con el mismo input producen el mismo `archive_manifest_hash`.
- [ ] **Hash stability:** ningún `EXPECTED_*` en `tests/reproducibility/` cambia.

Si alguna casilla NO se marca, explicar por qué el cambio es legítimo:

<!-- Justificación + enlace al ADR pertinente. -->

## Quality gates

Comprobado localmente antes de abrir el PR:

- [ ] `ruff check src tests` → 0 errores
- [ ] `mypy` (strict) → 0 errores
- [ ] `pytest --cov-fail-under=90` → 0 fallos, cobertura por encima del umbral

## Notas para el revisor

<!-- Cualquier contexto que ayude: incidencia que motiva el PR, casos límite
verificados, decisiones de diseño que no son obvias del diff. -->
