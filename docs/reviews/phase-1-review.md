# Phase 1 — Cierre formal y revisión

**Fecha:** 2026-06-06
**Release asociado:** `v0.1.0`
**Estado:** **Fase 1 cerrada.**
**Próxima fase planificada:** ninguna comprometida (ADR-0023 mantiene el alcance V1 congelado; F2+ requieren ADR de enmienda explícito).

---

## 1. Qué exigía cerrar F1

ADR-0004 §F1 y `docs/phase-1/command-specification.md` §resumen ejecutivo definieron el contrato de cierre:

> Un investigador externo:
> 1. Clona el repositorio.
> 2. Descarga el PDF desclasificado público especificado en la doc de la demo.
> 3. Ejecuta `aip evidence ingest <pdf> --source-id … --ingested-by …`.
> 4. Recupera con `aip evidence show <hash>` la procedencia completa.
> 5. Ejecuta `aip archive verify` y obtiene "Archive integrity verified".
> 6. Verifica que el hash SHA-256 reportado coincide bit a bit con el publicado en la doc.

## 2. Qué se entregó

Estado del proyecto en el commit `v0.1.0`:

### 2.1. Documentación

- **32 ADRs aceptados (0000–0031)** sin reescrituras ni superseder pendientes.
- **MAINTAINERS.md** con bus factor = 1 declarado.
- **Red Team Review + informe de cierre** (9 hallazgos cerrados, 13 mitigados, 12 aceptados conscientemente; 0 abiertos).
- **Pre-F1.C** con fixture canónico pinned (Twining Memo, SHA-256 `65539d95…`).
- **Pre-F1.D** con contrato testeable de los tres comandos.

### 2.2. Implementación V1

`src/aip/` con cuatro subpaquetes:

| Subpaquete | Función | Stmts | Coverage |
|---|---|---|---|
| `aip.core` | Modelo de evidencia, fuente, procedencia, hashing/JCS | 287 | 100% |
| `aip.audit` | Append-only log con cadena de hashes + verificación | 127 | 99–100% |
| `aip.storage` | CAOS + Parquet append-only + manifest canónico | 237 | 94–100% |
| `aip.cli` | Wrapper delgado sobre `Archive` (ingest/show/verify) | 211 | 86–96% |
| `aip.archive` | Fachada API Python pública | 223 | 82% |

CLI funcional: `aip evidence ingest`, `aip evidence show`, `aip archive verify` con output texto humano y `--json`, exit codes mapeados a errores tipados.

### 2.3. Tests y reproducibilidad

| Categoría | Tests | Cobertura |
|---|---|---|
| Unit (`tests/unit/`) | 233 | Por capa según ADR-0031 §umbrales |
| Reproducibility (`tests/reproducibility/`) | 14 | JCS canónico, manifest hash empty, manifest hash con fixture, audit chain |
| Integration (`tests/integration/`) | 1 | Pipeline end-to-end PDF → ingest → show → verify |

**Totales:** 248 tests, 0 skipped, 93.57% coverage, 0 fallos.

### 2.4. Quality gates en CI

`.github/workflows/ci.yml` matriz Python 3.11 + 3.12 sobre Ubuntu:

- `ruff check src tests` → 0 errores.
- `mypy --strict` (src + tests) → 0 errores.
- `pytest --cov=aip --cov-fail-under=90` → 248 passed, 93.57% coverage.

## 3. Verificación de la demo de cierre

Ejecutado el 2026-06-06 contra `tests/data/twining-memo-1947-09-23.pdf` (SHA-256 pinned `65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1`):

| Paso del contrato Pre-F1.D | Comando | Resultado |
|---|---|---|
| 1. PDF → ingest | `aip evidence ingest twining-memo-1947-09-23.pdf …` | exit 0, hash `65539d95…` == pinned ✓ |
| 2. Recuperación | `aip evidence show sha256:65539d95…` | exit 0, view estructurada con source + provenance + auth (unverified default) ✓ |
| 3. Verificación full | `aip archive verify` | exit 0, `Archive integrity verified` ✓ |
| 4. Reproducibilidad bit a bit | `manifest_hash` con clock canónico fijo | `364b23977466ad44c6f7a544a2b99987dc8ed9cabc82d227fc8a670942fda7bc` pinned ✓ |
| 5. Idempotencia | re-ingest del mismo PDF | mismo hash, audit_entries no crece (2 entradas: bootstrap + ingest) ✓ |

`tests/integration/test_demo_pipeline.py` ejecuta esta cadena automatizadamente bajo `pytest.mark.integration`. Verde en máquina del mantenedor sobre Windows 11 + Python 3.11.9 (plataforma host) y previsto verde sobre Ubuntu (CI matriz).

## 4. Cumplimiento de las propiedades irrenunciables (ADR-0000, ADR-0024)

| Propiedad | Estado V1 | Comentario |
|---|---|---|
| P1 Separación epistémica | Parcial (solo `Evidence`) | Diferido para `Claim`/`Hypothesis`/`Conclusion` por ADR-0023. |
| P2 Trazabilidad bit a bit | Cumplida | JCS + SHA-256 sobre todo objeto canónico. Acotada por ADR-0024 L2 (material ingestado local). |
| P3 Incertidumbre cuantificada | N/A en V1 | Sin hipótesis, sin scoring. Diferido. |
| P4 Neutralidad de hipótesis | N/A en V1 | Diferido. |
| P5 Reproducibilidad | Cumplida | Manifest hash + audit chain pinned en tests de reproducibility. |
| P6 Local-first | Cumplida | Cero red en runtime; descarga del fixture aislada en `scripts/`. |
| P7 Coste cercano a cero | Cumplida | Solo deps open source (pydantic, pyarrow). |
| P8 Documentación al nivel del código | Cumplida | 32 ADRs + Pre-F1.C/D + este review. |
| P9 Fuentes públicas | Cumplida | Fixture = dominio público (Twining 1947, USG work). |
| P10 No fabricación | Cumplida | Sin LLM en runtime; helper de descarga es operativo, no productivo. |
| P11 Inmutabilidad evidencia cruda | Cumplida | CAOS content-addressed; tests verifican rehash post-write. |
| P12 Do-no-harm | N/A en V1 | Sin testigos vivos; fixture > 75 años. |

Las cuatro propiedades acotadas por ADR-0024 (L1–L7) lo siguen estando; las cinco sesgos del ADR-0025 (S1–S4) no entran porque V1 no toca hipótesis.

## 5. Hallazgos del Red Team Review aún pendientes (de los 12 aceptados)

Ninguno es bloqueante de F1. Los relevantes para V1 entregado:

- **§6.1** DuckDB como punto único de falla: mitigado por ADR-0024 (formato canónico = Parquet, no DuckDB) + V1 no usa DuckDB todavía (consultas son lookup por hash de fichero).
- **§6.3** CAOS basado en filesystem escala bien para archivos modestos: confirmado en V1 (1 blob). Sin estrés.
- **§9.1** Vaporware perpetuo por mantenedor único: **modo de fallo evitado** — V1 entregable real, no documentación adicional.
- **§10.1** Adopción no garantizada: sigue siendo riesgo aceptado.

## 6. Decisiones tomadas durante la implementación que merecen mención

Ninguna requirió ADR de enmienda, pero conviene registrarlas:

1. **`JsonValue` covariante en contenedores** (`Sequence`/`Mapping` en lugar de `list`/`dict`) para que `dict[str, str]` se acepte en `hash_object` sin cast. Cambio interno; no afecta semántica documentada del JCS.
2. **`StrEnum`** en lugar de `class X(str, Enum)`: idiomático Python 3.11+, equivalente semánticamente para los usos del proyecto (`enum.value` siempre explícito).
3. **Patrón "una fila por fichero Parquet"** en `storage/tables`: el nombre del fichero codifica `row_id` y el payload va JCS-canonicalizado como columna binaria. Trade-off declarado: sin queries columnares reales, pero reproducibilidad bit a bit garantizada independiente del writer Parquet (ADR-0024 §formato canónico vs. motor).
4. **CLI con globals al nivel del subcomando** (estilo git/kubectl), no al top-level. `aip evidence ingest … --json --archive-root <path>`. Cambio respecto al primer borrador donde los globals eran top-level.
5. **`ingested_by` obligatorio en CLI** (no se infiere del usuario del sistema). Coherente con la mitigación R8 propuesta en el plan Pre-F1 y con ADR-0031 R1.

## 7. Limitaciones declaradas de V1

V1 **no entrega** (diferido por ADR-0023, todo permanece como ADR aceptado para fases futuras):

- Modelo de `Claim`, `Hypothesis`, `HypothesisSet`, `Conclusion`, `Case`.
- Grafo de conocimiento (`aip.graph`).
- Motor temporal (`aip.temporal`) ni geoespacial (`aip.spatial`).
- Adquisidores OSINT (`aip.osint`).
- HTTP API (`aip.http`).
- Búsqueda léxica o semántica (`aip.search`).
- Enclave de material sensible (`aip.enclave`).
- Asistencia LLM (`aip.llm`).

Estas ausencias son **deliberadas** y representan el ~90% de lo descrito en los ADRs 0007–0014 y 0017–0021. Su implementación, si ocurre, requiere ADR explícito de levantamiento del recorte de ADR-0023 sobre cada área.

## 8. Métricas comparativas

| Métrica | V1 | Comentario |
|---|---|---|
| ADRs escritos | 32 | Todos aceptados, ninguno superseded |
| Tests | 248 | 233 unit + 14 reproducibility + 1 integration |
| Coverage global | 93.57% | Threshold ADR-0031: ≥ 90% |
| Coverage `core/` | 100% | Threshold: ≥ 95% |
| Coverage `audit/` | 99–100% | Threshold: ≥ 95% |
| Coverage `storage/` | 94–100% | Threshold: ≥ 90% |
| Coverage `cli/` | 86–96% | Threshold: ≥ 80% |
| Líneas de código de producción (`src/`) | ~1 120 | Excluye blank/comment |
| Líneas de tests | ~2 800 | Ratio tests/src ≈ 2.5 |
| Ficheros de doc en `docs/` | 41 | Mayoría ADRs + reviews + phase-1 specs |
| Commits hasta v0.1.0 | 3 | foundation, quality-gates, phase-1-close |
| Bus factor declarado | 1 | Sin cambio respecto a fundación |

## 9. Lo que CI valida en cada push

`.github/workflows/ci.yml`:

```
matrix: Python {3.11, 3.12} × Ubuntu
gate 1: ruff check src tests           → must exit 0
gate 2: mypy (strict, files=src+tests) → must exit 0
gate 3: pytest --cov-fail-under=90     → 248 passed, ≥ 90% coverage
```

Estos tres gates son los **mínimos no negociables** para mergear a `main`. Cualquier push directo a main que falle cualquiera de los tres sigue siendo aceptado por GitHub (no hay branch protection todavía), pero el badge del workflow lo expone.

## 10. Decisión: cierre formal

**Fase 1 queda cerrada con la entrega del release `v0.1.0`.** El contrato declarado por ADR-0004 §F1 está cumplido en todas sus dimensiones:

1. Demo de cierre ejecutable por externo: cumplida.
2. Reproducibilidad bit a bit verificable: cumplida y testeada.
3. Cobertura sobre los umbrales de ADR-0031: cumplida.
4. Quality gates automatizados en CI: configurados.

El proyecto entra ahora en **estado de mantenimiento** según el modelo de sostenibilidad del ADR-0000:

- Sin commits de nuevas capacidades hasta que aparezca ADR explícito de levantamiento del recorte.
- Aceptación de PRs de bugfixes y mejoras de rendimiento sin cambio de semántica documentada (D2 del MAINTAINERS.md).
- Revisión semestral del bus factor (próxima: 2026-12-04).
- Revisión anual del ADR-0000 (próxima: 2027-06-03).

## 11. Riesgos aceptados explícitamente al cerrar F1

1. **El proyecto no se anuncia, no se promociona, no se publica en foros del campo.** ADR-0023 lo prohíbe explícitamente. El v0.1.0 vive solo en GitHub y solo para quien lo encuentre orgánicamente.

2. **La adopción puede no llegar.** Aceptado por ADR-0023 §10.1. La existencia del entregable es la única apuesta racional disponible bajo bus factor = 1.

3. **El Twining Memo del Internet Archive puede desaparecer.** El SHA-256 pinned protege contra silenciosa sustitución; el fichero versionado en `tests/data/` es la copia canónica del proyecto. Si la URL muere, el procedimiento V1–V3 de Pre-F1.C aplica.

4. **Cambios en pyarrow o Parquet pueden afectar al `partition_hashes` físico**, pero NO al `manifest_hash` canónico (ADR-0024 §formato canónico vs. motor). Si esto fallara, sería bug arquitectónico crítico, no degradación esperada.

5. **bus factor = 1.** Cinco riesgos del modelo (discontinuación, calidad inconsistente, sesgo personal, captura emocional, obsolescencia técnica) siguen activos. ADR-0026 los reconoce sin pretender eliminarlos.

---

## Apéndice: enlaces canónicos del release

- **Commit tag:** `v0.1.0` (sha7 pendiente del commit final).
- **Demo fixture:** [`tests/data/twining-memo-1947-09-23.pdf`](../../tests/data/twining-memo-1947-09-23.pdf), SHA-256 `65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1`.
- **Canonical manifest hash** (con clock `2026-06-04T00:00:00Z`): `364b23977466ad44c6f7a544a2b99987dc8ed9cabc82d227fc8a670942fda7bc`.
- **Integration test:** [`tests/integration/test_demo_pipeline.py`](../../tests/integration/test_demo_pipeline.py).
- **Reproducibility test (manifest + fixture):** [`tests/reproducibility/test_manifest_hash.py`](../../tests/reproducibility/test_manifest_hash.py).

---

*Phase 1 review firmada por `@jfhelvetius` el 2026-06-06. No requiere co-firma porque el bus factor del proyecto es 1 en este momento.*
