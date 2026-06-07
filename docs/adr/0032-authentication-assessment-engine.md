# ADR-0032: Authentication Assessment Engine v1

**Estado:** Aceptado
**Fecha:** 2026-06-06
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0005, ADR-0006, ADR-0015, ADR-0019, ADR-0023, ADR-0024, ADR-0030, ADR-0031

---

## Contexto

Hasta este ADR la tabla `authentication_assessments` existe en `V1_TABLES` (ADR-0015 §V1.3) pero permanece **vacía**: el campo `Evidence.authentication` se llena con un `AuthenticationAssessment` por defecto (`UNVERIFIED`, sin assessor, sin método) y la tabla nunca recibe filas. La consecuencia operativa es que el archive describe **qué se ingestó** pero no ofrece ningún punto de partida estructurado para razonar sobre la **autenticidad** del material — la pregunta sustantiva que ADR-0000 declara central.

Resolver eso sin caer en machine learning, scoring continuo, inferencia probabilística, redes, OCR ni NLP es el contrato de este ADR.

ADR-0023 (Scope Reduction) congeló el alcance V1. Levantar esa congelación normalmente requiere ADR explícito. Este ADR-0032 es ese vehículo, con dos restricciones autoimpuestas: (a) no introduce capas nuevas de persistencia, (b) no toca la canonicalización de Evidence, Source, Provenance ni audit chain, por tanto **ningún `EXPECTED_*_HASH` pinned cambia** como consecuencia de aceptarlo.

## Decisión

Crear un **motor derivado de evaluación de autenticidad** en `src/aip/analysis/authentication.py` que:

1. Define un modelo Pydantic frozen `AuthenticationAssessment` con identidad determinista y rationale textual fijo.
2. Aplica reglas booleanas mínimas — sin scoring, sin probabilidades, sin heurísticas continuas — sobre el estado actual del archive (Evidence + Source + Provenance).
3. Persiste el resultado en la tabla `authentication_assessments` ya prevista, reutilizando el esquema Arrow uniforme (`row_hash`, `payload_jcs`) y el `schema_hash` opaco existente.
4. Exporta una CLI `aip assess-authentication --archive PATH --evidence-id ID` que produce salida JSON canónica.

El motor cumple **cuatro garantías arquitectónicas declaradas** en el código y testeadas explícitamente (`tests/unit/analysis/test_authentication.py`):

| # | Garantía | Verificación |
|---|----------|--------------|
| G1 | No es verdad sustantiva | Status discreto + rationale textual fijo; nunca claims "es auténtico" |
| G2 | No es inferencia probabilística | Reglas booleanas puras; cero floats, cero probabilidades |
| G3 | No sustituye investigación humana | El campo `method` señala intención del operador; el cuerpo de la regla es transparente |
| G4 | Es derivado y removible | Borrar la fila del row.parquet **nunca** modifica Evidence/Source/Provenance/audit; test explícito |

## Justificación

### Por qué reglas booleanas y no scoring continuo

Un scoring continuo (e.g., un número 0.0–1.0 que pretende "nivel de autenticidad") es la puerta de entrada al sensacionalismo blando: lectores no técnicos lo leen como probabilidad bayesiana, y el sistema sería falsamente cuantitativo. Las cinco categorías (`UNKNOWN`, `UNVERIFIED`, `PARTIALLY_SUPPORTED`, `SUPPORTED`, `CONTRADICTED`) son cualitativamente distinguibles, mapean a hechos verificables del archive y son trivialmente reproducibles bit a bit.

### Por qué reutilizar la tabla `authentication_assessments`

La tabla ya está en `V1_TABLES` y entra en el cómputo de `EXPECTED_DEMO_MANIFEST_HASH` con 0 filas. Reutilizarla preserva esa invariante: poblar la tabla en ejecuciones futuras del CLI deriva nuevos manifest_hash (legítimo — el archive cambió) sin contradecir los pinned originales (que describen archives previos al primer assessment). El esquema Arrow es uniforme (`row_hash`, `payload_jcs`) y el `schema_hash` se hashea sobre bytes opacos (`b"schema:authentication_assessments"`), por tanto **el payload puede tener cualquier forma** sin cambiar el `schema_hash` ni romper el manifest hash de archives vacíos.

### Por qué un módulo `analysis/` aparte de `core/`

`core/` contiene el modelo de **verdad observada**: Evidence, Source, Provenance. Confundir verdad con interpretación derivada es exactamente lo que ADR-0000 prohíbe arquitectónicamente. Un subpaquete propio `analysis/` (ADR-0030 §S2: dependencia legítima sobre `core`+`storage`, nunca al revés) materializa esa separación: un lector del código sabe inmediatamente que un módulo en `analysis/` es derivado y removible, no fuente.

### Por qué `assessment_id = "{evidence_id}__{method}"`

Identidad determinista, legible y ASCII-safe en una sola decisión:
- Reproducibilidad: mismo `(evidence_id, method)` ⇒ mismo `assessment_id` ⇒ mismo `row_id` ⇒ idempotencia trivial en `append_row` (ADR-0031 R6).
- Legibilidad: un humano leyendo `tables/authentication_assessments/` sabe a qué evidencia y método corresponde cada fichero sin abrirlo.
- Pluralidad: la misma Evidence puede tener un assessment por método (`PROVENANCE_REVIEW`, `MANUAL_RESEARCH`, `CHAIN_OF_CUSTODY_REVIEW`) sin colisión.

### Por qué dos `AuthenticationAssessment` (convivencia)

Existen ahora dos clases del mismo nombre en ámbitos disjuntos:

- `aip.core.evidence.AuthenticationAssessment` — slot histórico embebido en `Evidence`. Frozen, default `UNVERIFIED`, jamás poblado activamente en V1. Es parte de la canonicalización de Evidence; renombrarlo cambiaría `EXPECTED_DEMO_MANIFEST_HASH`. Por tanto: **no se toca**.
- `aip.analysis.authentication.AuthenticationAssessment` — artefacto derivado de este ADR. Vive en la tabla.

La dualidad es deliberada. Los re-exports públicos resuelven la ambigüedad:

- `aip.AuthenticationAssessment` queda **no exportado** desde la raíz para evitar confusión.
- `aip.DerivedAuthenticationAssessment` es el alias público del nuevo modelo (con el prefijo `Derived` documentando explícitamente su naturaleza).
- Quien necesite el slot embebido lo importa por path completo (`aip.core.evidence.AuthenticationAssessment`).

### Por qué CLI top-level y no bajo `evidence`

`aip evidence ingest|show` opera sobre la Evidence como entidad ingestada. `aip assess-authentication` opera sobre un artefacto derivado distinto: pertenece a una capa analítica nueva, no a operaciones de evidencia. Subordinarlo a `evidence` sugeriría que el assessment es propiedad de Evidence — falso: es propiedad del archive en un instante dado. El nivel superior refleja la separación.

### Por qué no escribe audit log

ADR-0019 reserva el audit log para operaciones que **modifican estado fuente**: bootstrap, ingest, futuras `revise_evidence`, etc. Un assessment derivado **no modifica estado fuente** — modifica una capa de interpretación que es completamente reconstruible desde el estado fuente actual. Auditarlo introduciría ruido sin valor: la fila del row.parquet ya documenta cuándo (`created_at`) y con qué método. Re-ejecutar el CLI sobre un archive sin cambios produce idempotencia bit a bit en el row, no entradas duplicadas en el audit.

Si en una fase posterior se desea trazabilidad cross-actor (quién corrió el assessment), un ADR específico añadirá `ActionKind.ASSESS_AUTHENTICATION`. Por ahora: fuera de scope.

### Por qué `created_at` es tz-aware sin microsegundos

Idéntica restricción a `ArchiveManifest.generated_at` y `AuditEntry.timestamp` (ADR-0024 L2). Sin esto, el `row_hash` del payload JCS difiere entre máquinas con relojes de distinta precisión. Con esto, la única fuente de no-determinismo es la decisión del operador sobre cuándo lanzar el comando — y el clock es inyectable desde la API Python para tests reproducibles (ADR-0031 R7).

## Reglas

Pseudocódigo canónico (implementación en `aip.analysis.authentication.classify`):

```
si NOT provenance_reference_intact:
    return CONTRADICTED
si NOT source_exists:
    return UNVERIFIED
si NOT has_provenance_steps:
    return PARTIALLY_SUPPORTED
return SUPPORTED
```

Cuatro ramas verificables; `UNKNOWN` reservado para futuros métodos. Cualquier ampliación de las reglas requiere ADR de enmienda.

## Lo que el motor **NO** hace

| Restricción ADR-0032 | Implementación |
|---|---|
| Sin ML | Cero modelos entrenados, cero pickles, cero pesos |
| Sin IA | Sin LLMs, sin agentes, sin embeddings |
| Sin scoring probabilístico | El status es enum cerrado; cero floats en el modelo |
| Sin APIs externas | `requests`/`httpx` no son dependencia; el motor no abre sockets |
| Sin red | El módulo solo importa stdlib + pydantic + módulos `aip.*` |
| Sin OCR | El motor no procesa bytes del blob; solo lee tablas |
| Sin visión artificial | Idem |
| Sin NLP | El `rationale` es texto fijo por status, no derivado de prosa |
| Sin embeddings | Idem |
| Sin nueva persistencia | Reutiliza tabla existente; sin nuevos directorios |
| Sin alterar hashes existentes | Cero modificaciones a Evidence/Source/Provenance/audit canonicalización |
| Sin alterar `schema_version` | `SCHEMA_VERSION = "0.1.0"` invariante |
| Sin romper reproducibilidad | 13/13 reproducibility tests siguen verdes |

## CLI

```sh
aip assess-authentication --archive PATH --evidence-id ID [--method METHOD]
```

- `--archive PATH` (obligatorio): raíz del archive AIP.
- `--evidence-id ID` (obligatorio): SHA-256 hex de la Evidence.
- `--method METHOD` (opcional, default `provenance_review`): uno de
  `manual_research`, `provenance_review`, `chain_of_custody_review`.

Salida: JSON con la estructura completa del `AuthenticationAssessment` + metadatos del archive root. Sin variante humana — el comando es para consumo programático.

## Persistencia

Tabla: `authentication_assessments` (ya en `V1_TABLES`).
`row_id`: `{evidence_id}__{method.value}` — único, determinista, ASCII safe.
Payload: `assessment.model_dump(mode="json")` ⇒ JCS via `tables.append_row`.

**No hay nuevo schema, no hay nueva tabla, no hay nuevo directorio.** El layout del archive es idéntico antes y después del primer assessment.

## Consecuencias

**Positivas**
- Primera capacidad analítica del archive sin abandonar los principios irrenunciables.
- Reglas auditables: cualquier lector puede revisar `classify()` y reproducir el veredicto a mano.
- Removibilidad demostrada: tests verifican que borrar assessments no cambia hashes de Evidence/Source/Provenance/audit.

**Negativas**
- Naming collision con `aip.core.evidence.AuthenticationAssessment`: requiere atención de lectores nuevos. Mitigado vía re-export `DerivedAuthenticationAssessment` en `aip.__init__`.
- El menú de cinco status puede sentirse insuficiente: deliberado. Si en F2+ se necesita más granularidad, ADR explícito.

**Neutras**
- Tras correr `aip assess-authentication`, el `manifest_hash` del archive cambia (legítimamente — el archive cambió). Los pinned `EXPECTED_*_HASH` de Pre-F1 describen archives **pre-assessment** y siguen siendo válidos para ese estado.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P8.

**Cómo se alinean:**
- **P1 (separación hechos/interpretaciones):** materializada en módulos distintos (`core/` vs. `analysis/`).
- **P2 (evidencia inmutable):** las reglas leen, jamás escriben Evidence.
- **P3 (incertidumbre explícita):** la enum cerrada `AssessmentStatus` documenta el espacio de respuestas; `UNKNOWN`/`UNVERIFIED` son ciudadanos de primera, no estados degenerados.
- **P5 (reproducibilidad):** misma archive + mismo clock ⇒ mismo payload bit a bit.
- **P8 (documentación arquitectónica):** este ADR registra la decisión.

**Tensión nueva:** ninguna. ADR-0023 §congelación V1 se levanta puntualmente para `authentication_assessments` con el alcance descrito; el resto de los dominios diferidos sigue diferido.

## Trigger de revisión

Este ADR se revisa si:

- Aparece necesidad de método cuyo cuerpo no encaje en las reglas V1 (e.g., revisión criptográfica de firmas).
- Surge requerimiento de auditar quién corrió el assessment (entonces `ActionKind.ASSESS_AUTHENTICATION`).
- Un colaborador externo plantea que las cinco categorías son insuficientes con caso de uso concreto.

## Referencias

- ADR-0000 §propiedades irrenunciables P1, P2, P3, P5, P8.
- ADR-0023 §congelación V1 (vehículo de levantamiento puntual).
- ADR-0024 §formato canónico vs. motor (schema_hash opaco).
- ADR-0031 §estrategia de testing (T3 reproducibility, T1 unit).
- `tests/reproducibility/test_manifest_hash.py` — confirmación de invariancia de `EXPECTED_*_HASH`.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
