# PROJECT_STATUS — Anomaly Intelligence Platform

**Última actualización:** 2026-06-06 (cierre de Fase 1 + tracks de mantenimiento C/B/A + auditoría post-release + ADR-0032 aceptado y entregado)
**Estado del proyecto:** **Fase 1 cerrada · release `v0.1.0` publicado · drift documental post-audit cerrado · motor derivado de autenticidad (ADR-0032) operativo**
**Bus factor declarado:** 1 (ver ADR-0026 · próxima revisión semestral 2026-12-04)

---

## Para el lector con prisa

- **¿Qué es AIP hoy?** Un cuerpo de **33 ADRs aceptados** y un V1 ejecutable que ingesta evidencia, la direcciona por hash, registra procedencia, verifica integridad bit a bit, y deriva evaluaciones de autenticidad sin ML ni scoring probabilístico. Demo cerrada con el Twining Memo (1947).
- **¿Qué hace V1?** `aip evidence ingest <pdf> --source-id … --ingested-by …` → `aip evidence show <hash>` → `aip archive verify` → cadena reproducible. Más, post-v0.1.0: `aip assess-authentication --archive … --evidence-id …` produce un artefacto derivado clasificando la evidencia en {UNVERIFIED, PARTIALLY_SUPPORTED, SUPPORTED, CONTRADICTED} según reglas booleanas explícitas.
- **¿Qué NO hace V1?** Claims, hipótesis, conclusiones, grafo, timeline, geospatial, OSINT, búsqueda, HTTP API, LLM, enclave. Todos diferidos por ADR-0023 (recorte deliberado de alcance). ADR-0032 es el primer levantamiento puntual: sólo para `authentication_assessments`, sin abrir nuevos dominios.
- **¿Quality gates?** ruff (0 errores) + mypy strict (0 errores) + **342 tests** pasando (incluye 16 property-based de Hypothesis sobre JCS y audit chain + **14 reproducibility con valores canónicos pinned, ahora incluyendo el manifest post-assessment**) + **96.25% cobertura global**. CI Ubuntu × Python 3.11/3.12 (bloqueante) + macOS-latest + Windows-latest (best-effort) con `uv sync --frozen` desde `uv.lock`.
- **¿Próxima fase?** Ninguna comprometida. Mantenimiento de V1 con criterios D1/D2 del MAINTAINERS.md. Cualquier ampliación de alcance requiere ADR explícito de levantamiento de ADR-0023; el motor de autenticidad ya es ese precedente, acotado a una sola tabla.

---

## Estado de los documentos

### Aprobado y vivo en disco

```
anomaly-intelligence-platform/
├── PROJECT_STATUS.md                              (este documento)
├── README.md                                       (resumen público)
├── LICENSE                                         (Apache 2.0)
├── MAINTAINERS.md                                  (artefacto obligatorio ADR-0026 C1)
├── pyproject.toml                                  (PEP 621 + ruff + mypy + pytest config)
├── uv.lock                                         (lockfile reproducible, ADR-0029 §M2)
├── .python-version                                 (3.11 mínimo declarado)
├── .gitignore .gitattributes                       (convenciones repo)
├── .github/
│   ├── workflows/ci.yml                            (ruff + mypy + pytest --cov, matrix Py 3.11/3.12 sobre Ubuntu + smoke macOS/Windows)
│   ├── dependabot.yml                              (security-only)
│   ├── pull_request_template.md                    (checklist de las 4 garantías)
│   └── ISSUE_TEMPLATE/                             (bug, provenance-concern, config)
├── docs/
│   ├── adr/                                        (33 ADRs + README + template)
│   │   ├── 0000–0022                               (23 fundacionales)
│   │   ├── 0023–0028                               (6 enmiendas post-Red Team)
│   │   ├── 0029–0031                               (3 operativos Pre-F1)
│   │   └── 0032                                    (Authentication Assessment Engine v1)
│   ├── phase-1/
│   │   ├── demo-evidence-selection.md              (Pre-F1.C con pinned values)
│   │   └── command-specification.md                (Pre-F1.D contrato CLI)
│   ├── ethics-procedures/
│   │   └── classified-material.md                  (procedimiento operacional honesto con capacidades V1)
│   ├── legal-compliance.md                         (responsabilidad operador, asunción material público)
│   ├── schema-migrations/
│   │   └── README.md                               (plantilla canónica; cero migraciones a v0.1.0)
│   └── reviews/
│       ├── adr_red_team_review.md                  (crítica hostil 2026-06-03, intacta)
│       ├── red_team_response.md                    (informe formal de cierre)
│       └── phase-1-review.md                       (cierre formal de F1)
├── src/aip/                                        (paquete distribuible)
│   ├── __init__.py __main__.py _version.py archive.py errors.py py.typed
│   ├── analysis/   (authentication — capa derivada ADR-0032)
│   ├── audit/      (log, verify)
│   ├── cli/        (main, evidence_commands, archive_commands, assessment_commands)
│   ├── core/       (hashing, evidence, source, provenance)
│   └── storage/    (layout, manifest, tables)
├── tests/
│   ├── conftest.py
│   ├── data/
│   │   ├── README.md
│   │   └── twining-memo-1947-09-23.pdf             (250 022 bytes, SHA-256 65539d95…)
│   ├── integration/test_demo_pipeline.py
│   ├── reproducibility/   (test_jcs, test_audit_chain, test_manifest_hash — 14 pinned)
│   └── unit/
│       ├── analysis/      (test_authentication, test_assess_authentication_archive)
│       ├── audit/         (test_log, test_verify)
│       ├── cli/           (test_main, test_assessment_commands)
│       ├── core/          (test_hashing, test_evidence, test_source, test_provenance)
│       ├── properties/    (test_hashing_properties, test_audit_properties — Hypothesis)
│       ├── storage/       (test_layout, test_manifest, test_tables, test_tables_corrupt)
│       ├── test_archive.py
│       ├── test_main_module.py
│       └── test_paso_0_smoke.py
└── scripts/                                        (utilidades auxiliares, no producción)
    ├── README.md
    └── fetch_demo_fixture.py                       (helper Pre-F1.C, stdlib-only)
```

### Total ADRs aprobados: 33

- **23 fundacionales** (0000–0022).
- **6 enmiendas** (0023–0028) en respuesta al Red Team Review.
- **3 operativos Pre-F1** (0029–0031).
- **1 capa derivada post-v0.1.0** (0032 — Authentication Assessment Engine).

### Documentos referenciados por ADRs

| Documento | ADR que lo exige | Estado |
|---|---|---|
| `MAINTAINERS.md` | ADR-0026 C1 | **Creado 2026-06-04** (extendido 2026-06-06 con quality gates + branch protection plan) |
| `docs/phase-1/demo-evidence-selection.md` | Pre-F1.C | **Creado 2026-06-04** (pinned values completados 2026-06-06) |
| `docs/phase-1/command-specification.md` | Pre-F1.D | **Creado 2026-06-04** |
| `docs/ethics-procedures/classified-material.md` | ADR-0026 C4 + RTR §8.3 | **Creado 2026-06-06** (track A de mantenimiento) |
| `docs/legal-compliance.md` | ADR-0019 | **Creado 2026-06-06** (track A) |
| `docs/schema-migrations/README.md` | ADR-0016 | **Creado 2026-06-06** (track A; directorio inicial sin migraciones) |
| `docs/reviews/phase-1-review.md` | ADR-0004 §F1 cierre | **Creado 2026-06-06** |
| `docs/osint-code-of-practice.md` | ADR-0014 | Diferido (fuera de V1; entra cuando se levante ADR-0023 sobre `aip.osint`) |
| `docs/vocabulary/` | ADR-0011, ADR-0025 | Diferido (fuera de V1) |
| `docs/visualization-guidelines.md` | ADR-0012, ADR-0013 | Diferido (fuera de V1) |

Para V1 strictu sensu, **todos los documentos comprometidos por ADRs aceptados están creados**. Los diferidos son obligaciones de fases que aún no se han abierto y no las tiene que cumplir V1.

---

## Resumen ejecutivo de la fundación

### Visión (ADR-0000)

Construir la plataforma open source más rigurosa posible para **medir, organizar, trazar, comparar y cuantificar la incertidumbre** que rodea a los reportes de fenómenos anómalos, sin asumir ninguna conclusión sustantiva.

La pregunta central no es *"¿qué es esto?"* sino *"¿qué nivel de confianza podemos asignar, con honestidad epistémica, a cada hipótesis competidora?"*

### Doce propiedades irrenunciables (ADR-0000)

| ID | Propiedad | Estado post-enmiendas |
|----|-----------|---------|
| P1 | Separación estricta de categorías epistémicas | Preservada |
| P2 | Trazabilidad bit a bit | **Acotada honestamente** por ADR-0024 L2 |
| P3 | Incertidumbre cuantificada como first-class | **Acotada honestamente** por ADR-0024 L1 |
| P4 | Neutralidad de hipótesis | **Reformulada operativamente** por ADR-0025 (no-favoritismo estructural + S1–S4) |
| P5 | Reproducibilidad | **Acotada honestamente** por ADR-0024 L2 |
| P6 | Local-first | Preservada (reforzada por V1) |
| P7 | Coste cercano a cero | Preservada (reforzada por V1) |
| P8 | Documentación al nivel del código | Preservada (reforzada por las 6 enmiendas) |
| P9 | Fuentes públicas como primarias | Preservada (acotada por ADR-0024 L3) |
| P10 | No fabricación | Preservada |
| P11 | Inmutabilidad de evidencia cruda | Preservada (acotada por ADR-0024 L6 vista operativa) |
| P12 | Do-no-harm | **Operacionalizada** por ADR-0026 |

### Cinco sesgos declarados (ADR-0025)

- **S1** Marco analítico occidental contemporáneo.
- **S2** Sesgo de falsabilidad operativa hacia hipótesis ordinarias.
- **S3** Independencia entre hipótesis (no captura composición causal ni entrelazamiento).
- **S4** Vocabulario controlado refleja a sus curadores.

### Siete límites operativos declarados (ADR-0024)

- **L1** Incertidumbre cuantificada es de primer orden y solo de objetos modelados.
- **L2** P2 cubre material ingestado local; preservación distinta de regeneración.
- **L3** Cuatro tensiones inter-propiedad (P9⊥P12, P3⊥P5, P6⊥P9, P10⊥P11) gestionadas caso por caso.
- **L4** Frontera Fact/Claim es decisión del curador, no propiedad universal.
- **L5** KentLevel es score ordinal con etiquetas verbales, declarado como tal.
- **L6** Inmutabilidad opera bajo política de compactación con vista `evidence_current`.
- **L7** Cita académica obligatoria por hash en tooling oficial.

### Cinco riesgos de mantenedor único (ADR-0026)

- Discontinuación.
- Calidad inconsistente.
- Sesgo personal.
- Captura emocional.
- Obsolescencia técnica.

Los cinco son **inherentes al modelo** y no se prometen eliminar.

### Ocho triggers de archivo digno (ADR-0027)

- T1 Inviabilidad epistémica.
- T2 Colapso de fuentes.
- T3 Doce meses sin commit / sin actualización / sin comunicación pública.
- T4 Captura por intereses incompatibles.
- T5 Daño documentado a testigos por defecto de diseño.
- T6 Dormancia declarada > 24 meses.
- T7 Vacío de mantenimiento sin sucesión en 3 meses.
- T8 Inviabilidad técnica de dependencias críticas.

---

## Decisión arquitectónica núcleo

El sistema se construye sobre **tres invariantes**:

1. **Evidencia inmutable direccionada por hash** (ADR-0002, ADR-0006, ADR-0011 ADR-0015).
2. **Cinco categorías epistémicas distinguibles por tipo** (ADR-0001).
3. **Hipótesis competidoras con falsabilidad operativa, evaluadas con evidencia favorable y contradictoria explícitas** (ADR-0008, ADR-0009).

Sobre estos tres invariantes se levantan el lifecycle de caso, el grafo de conocimiento, los motores temporal y geoespacial, y la búsqueda. **Solo el primero se implementa en V1.**

---

## Alcance de V1 (ADR-0023)

### V1 entrega

1. **CLI `aip`** con tres comandos: `evidence ingest`, `evidence show`, `archive verify`.
2. **API Python** `aip` equivalente para esos tres comandos.
3. **Modelo de evidencia** (ADR-0006) núcleo: hash SHA-256, kind, content_uri, source_id, status, ingested_at/by, schema_version.
4. **Modelo de fuente y procedencia** (ADR-0005) suficiente: una `Source` y una `Provenance` mínima.
5. **CAOS en filesystem** (ADR-0015) con verificación de integridad por hash.
6. **Almacenamiento Parquet** de metadatos (ADR-0015) con esquema versionado.
7. **Versionado de archivo** (ADR-0016) con `ArchiveManifest` y URI scheme `aip:` para `evidence`.
8. **Audit log** append-only con hash chain (ADR-0019).
9. **`MAINTAINERS.md`** (ADR-0026 C1).

### V1 explícitamente NO entrega

- Modelo de `Claim`, `Hypothesis`, `HypothesisSet`, `Conclusion`, `Case`.
- Grafo de conocimiento, motor temporal, motor geoespacial.
- Adquisidores OSINT, HTTP API, búsqueda léxica/semántica, enclave de material sensible, asistencia LLM.

Esos ADRs permanecen **aceptados como diseño** sin compromiso de plazo.

### Demo de cierre de Fase 1

Un investigador externo:

1. Clona el repositorio.
2. Descarga un PDF desclasificado público especificado en la documentación de la demo (candidato: un memo individual de Project Blue Book disponible en NARA).
3. Ejecuta `aip evidence ingest <pdf> --source-id blue-book-nara --source-name "Project Blue Book — NARA"`.
4. Recupera con `aip evidence show <hash>` la procedencia completa, incluyendo `Source`, `Provenance` mínima con un solo paso `original_capture`, `AuthenticationAssessment` con `unverified`, `ingested_at`, `ingested_by`, `schema_version`.
5. Ejecuta `aip archive verify` y obtiene "OK: 1 evidencia, 1 fuente, hash verificado, audit log encadenado válido".
6. Verifica que el hash SHA-256 reportado coincide bit a bit con el publicado en la documentación de la demo.

Si los seis pasos se ejecutan en máquina del investigador sin asistencia del autor, la demo cierra.

### Pipeline conceptual de la demo

```
PDF (disco local)
    │
    ▼
┌──────────────────────┐
│ aip evidence ingest  │
│  - compute SHA-256   │
│  - JCS canonicalize  │
│  - store in CAOS     │
│  - append to Parquet │
│  - emit AuditEntry   │
└──────────┬───────────┘
           │
           ▼
   archive/objects/sha256/<2>/<rest>
   archive/tables/evidence/...
   archive/audit.log

           │
           ▼
┌──────────────────────┐
│ aip evidence show    │
│  - read by hash      │
│  - join provenance   │
│  - join source       │
│  - render structured │
└──────────────────────┘

           │
           ▼
┌──────────────────────┐
│ aip archive verify   │
│  - rehash all blobs  │
│  - check audit chain │
│  - check manifest    │
└──────────────────────┘
```

Ningún paso anterior depende de red, LLM, base de datos remota, servicio externo, ni de funcionalidad fuera de V1.

---

## Hoja de trabajo para Fase 1 (orden recomendado)

**Sin escribir código todavía.** Esta es la hoja de pre-implementación que debe cerrarse antes de la primera línea.

### Pre-F1.A — Documentación bloqueante

- [x] **`MAINTAINERS.md`** con bus factor declarado = 1. **Cerrado 2026-06-04.**
- [ ] `docs/ethics-procedures/classified-material.md`. **Aplazado**: no es bloqueante para la demo F1 con fixture público en dominio público; obligatorio antes de ingestar cualquier otra cosa que no sea el fixture.
- [ ] `docs/legal-compliance.md`. **Aplazado**: mismo criterio.

### Pre-F1.B — Elecciones técnicas explícitas formalizadas

- [x] **ADR-0029 Runtime Language Decision** — Python 3.11+ + uv + ruff + pytest + mypy/pyright. **Cerrado 2026-06-04.**
- [x] **ADR-0030 Repository Layout** — src layout, 4 subpaquetes (`cli/`, `core/`, `storage/`, `audit/`), 3 categorías de tests. **Cerrado 2026-06-04.**
- [x] **ADR-0031 Testing Strategy** — unit/integration/reproducibility, cobertura diferenciada (95/95/90/80), prohibición absoluta de red en tests. **Cerrado 2026-06-04.**

### Pre-F1.C — Selección del PDF de la demo

- [x] Criterios de selección S1–S7 definidos en `docs/phase-1/demo-evidence-selection.md`. **Cerrado 2026-06-04.**
- [x] Candidato primario identificado: **Twining Memo (1947-09-23)**. **Cerrado 2026-06-04.**
- [x] Tres fallbacks identificados (Special Report 14, Robertson Panel Report, memo individual de Blue Book). **Cerrado 2026-06-04.**
- [x] Procedimientos P1–P5 (publicación) y V1–V3 (verificación independiente) definidos. **Cerrado 2026-06-04.**
- [ ] **Pinned values rellenados** (URL, fecha de descarga, tamaño, SHA-256 hexadecimal). **Acción operativa puntual del mantenedor pendiente** — requiere descarga del PDF desde NARA. No es funcionalidad del proyecto, es acto operativo de selección.

### Pre-F1.D — Especificación detallada del API/CLI mínimo

- [x] Sintaxis, inputs, outputs, errores y comportamiento esperado de `aip evidence ingest`. **Cerrado 2026-06-04.**
- [x] Lo mismo para `aip evidence show`. **Cerrado 2026-06-04.**
- [x] Lo mismo para `aip archive verify`. **Cerrado 2026-06-04.**
- [x] Códigos de salida estándar (0/1/2/3/4/64). **Cerrado 2026-06-04.**
- [x] Comportamiento bootstrap (archive nuevo) definido. **Cerrado 2026-06-04.**
- [x] Output canónico texto humano y JSON para los tres comandos. **Cerrado 2026-06-04.**
- [x] Contrato testeable derivable para integration test. **Cerrado 2026-06-04.**

Documento canónico: `docs/phase-1/command-specification.md`.

### F1 — Implementación (sin todavía empezar)

Cuando Pre-F1.A–D estén cerrados:

- [ ] Esqueleto del paquete Python.
- [ ] Implementación de `EvidenceKind`, `EvidenceStatus`, `Source`, `Provenance` mínima, `AuthenticationAssessment` con un solo método de verificación trivial.
- [ ] CAOS y verificación de hash.
- [ ] Append-only Parquet para tablas.
- [ ] Audit log encadenado.
- [ ] CLI delgada sobre API Python.
- [ ] Tests.
- [ ] Documentación de la demo.

### F1 cierre

- [ ] Auto-prueba: el propio autor ejecuta la demo en máquina limpia.
- [ ] Invitación pública a un externo para reproducirla.
- [ ] Si el externo cierra la demo en su máquina sin asistencia: **F1 cerrada**.
- [ ] Publicación de release `v0.1.0` con tag, manifiesto reproducible, y revisión de fase en `docs/reviews/phase-1-review.md`.

---

## Lo que NO se va a hacer ahora

Para preservar la disciplina del recorte de alcance (ADR-0023), las siguientes tentaciones se rechazan explícitamente en esta sesión y en las próximas hasta que F1 cierre:

- ❌ Diseñar nuevas capacidades, modelos o motores.
- ❌ Añadir integraciones con servicios externos.
- ❌ Implementar HTTP API, búsqueda, grafo, timeline, geoespacial.
- ❌ Construir asistencia LLM ni enclave de material sensible.
- ❌ Empezar a cargar archivos legacy (Project Blue Book completo, GEIPAN, etc.) más allá del único PDF de demo.
- ❌ Crear UI (web, desktop, ni siquiera notebook templates) más allá de CLI mínima.
- ❌ Promover, anunciar o reclutar antes de tener entregable funcional.

Cualquier presión por ampliar alcance antes del cierre de F1 se contesta con esta lista.

---

## Riesgos visibles y aceptados

Los riesgos están documentados completos en `docs/reviews/red_team_response.md`. Síntesis para el lector que solo lee este documento:

### Riesgos cerrados (modo de fallo eliminado)

- Tres superficies API divergiendo.
- Búsqueda semántica como autoritativa en uso real.
- Diccionario de sinónimos como trabajo infinito.
- Revisión ética dependiente de carácter del mantenedor.
- Vaporware perpetuo por exceso de alcance.
- Condiciones de archivo circulares.
- Licencia sin razonamiento explícito frente a alternativas.

### Riesgos mitigados (acotados operativamente)

- 13 hallazgos del Red Team Review acotados con límites declarados, procedimientos documentados o triggers explícitos.

### Riesgos aceptados conscientemente

- 12 hallazgos reconocidos como inherentes al alcance, al modelo o al contexto, y declarados sin promesa de eliminación.

### Riesgo dominante no eliminado

**Discontinuación del proyecto por mantenedor único.** Mitigado con bus factor declarado, política de no-SLA, protocolo de sucesión y procedimiento de archivo digno. **No eliminado.** Cualquier adoptante debe internalizar este riesgo.

---

## Estado al cierre de Fase 1 (release v0.1.0, 2026-06-06)

Fase 1 cerrada. La cadena de cierre completa:

```
Pre-F1.A bloqueante         ✓ MAINTAINERS.md publicado
Pre-F1.B ADRs operativos    ✓ ADR-0029/0030/0031
Pre-F1.C fixture canónico   ✓ Twining Memo SHA-256 65539d95…
Pre-F1.D contrato CLI       ✓ comando especificado y testeado
Implementación V1           ✓ 12 pasos completados
Quality gates               ✓ ruff + mypy strict + 93.57% cov
GitHub Actions CI           ✓ matriz Py 3.11/3.12 sobre Ubuntu
Demo F1                     ✓ PDF → ingest → show → verify
Reproducibilidad bit a bit  ✓ manifest hash pinned 364b2397…
Phase-1 review              ✓ docs/reviews/phase-1-review.md
```

**Bloqueante para iniciar Fase 2:** ADR explícito de levantamiento de ADR-0023 §recorte. **No comprometido.** Mantenimiento de V1 hasta entonces. ADR-0032 estableció el precedente: levantamientos puntuales por tabla son posibles si la nueva capacidad cumple las cuatro garantías del ADR (derivada, no probabilística, no sustituye humanos, removible).

---

## Post-v0.1.0: motor de autenticidad (ADR-0032, 2026-06-06)

Levantamiento puntual de ADR-0023 §recorte para poblar la tabla `authentication_assessments` previamente reservada vacía. **Nada más**: ningún otro dominio diferido se abre.

### Qué entrega

- **`src/aip/analysis/authentication.py`** — modelo Pydantic frozen `AuthenticationAssessment` + enums cerrados `AssessmentStatus` (5) y `AssessmentMethod` (3) + regla `classify()` booleana pura + builder `build_authentication_assessment()` funcionalmente puro.
- **`src/aip/cli/assessment_commands.py`** — subcomando top-level `aip assess-authentication --archive PATH --evidence-id ID [--method ...]`. Salida JSON canónica siempre.
- **`Archive.assess_authentication()`** + **`Archive.list_authentication_assessments()`** en la API Python.
- **`EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH`** pinned en reproducibility tests: `33530b04c25c3766fb3fc7aa496bd22dffa2848d4bdc71d204ddb4b1141ee9ea` (Twining Memo + assess con clock canónico).

### Qué NO entrega

- Sin ML, sin IA, sin scoring probabilístico, sin red, sin OCR, sin NLP, sin embeddings.
- Sin nuevas tablas, sin nuevo `schema_version`, sin migración.
- Sin nuevas entradas en el audit log: el assessment es derivado y removible sin huella.
- Sin modificación de `Evidence`, `Source`, `Provenance`, ni del audit chain.

### Garantías testeadas

| # | Garantía | Test |
|---|---|---|
| G1 | No es verdad sustantiva | `test_classify_*` — status discreto + rationale fijo |
| G2 | No es inferencia probabilística | regla booleana cubierta por 8 combinaciones de input |
| G3 | No sustituye investigación humana | `--method` documenta intención; cuerpo de la regla auditable |
| G4 | Es derivado y removible | `test_deleting_assessment_does_not_affect_evidence` bit a bit |

### Pinned hashes intactos tras ADR-0032

`EXPECTED_PDF_SHA256`, `EXPECTED_DEMO_MANIFEST_HASH`, `EXPECTED_EMPTY_MANIFEST_HASH`, 5 `EXPECTED_SCHEMA_HASHES`, `EXPECTED_BOOTSTRAP_HASH`, `EXPECTED_INGEST_HASH`, 6 pares JCS canónicos — todos verdes sin cambio.

### Lo que NO se hará sin ADR de levantamiento

Cada subpaquete `aip.X` que aparece como import futuro en cualquier ADR pero no existe en `src/aip/` queda diferido:

- `aip.claim` (ADR-0007)
- `aip.hypothesis` (ADR-0008)
- `aip.conclusion` (ADR-0009)
- `aip.case` (ADR-0010)
- `aip.graph` (ADR-0011)
- `aip.temporal` (ADR-0012)
- `aip.spatial` (ADR-0013)
- `aip.osint` (ADR-0014)
- `aip.http` (ADR-0017 HTTP API opcional)
- `aip.search` (ADR-0018)
- `aip.enclave` (ADR-0019 enclave de material sensible)
- `aip.llm` (ADR-0021 asistencia LLM)

### Próximas acciones del proyecto sin ampliación de alcance

1. **Revisión semestral del bus factor** — 2026-12-04 (MAINTAINERS.md C2).
2. **Revisión anual del ADR-0000** — 2027-06-03.
3. **PRs externos:** se aceptan bajo criterios D1/D2 del MAINTAINERS.md.
4. **Triggers de archivado** (ADR-0027): monitorización pasiva del commit activity (T3 — 12 meses sin commit dispara archivado digno).

---

*El proyecto AIP no garantiza éxito. Garantiza honestidad sobre el riesgo. La aspiración del ADR-0000 sigue siendo la brújula; V1 es el paso ejecutable más pequeño que avanza en su dirección.*
