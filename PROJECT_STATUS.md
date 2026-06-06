# PROJECT_STATUS — Anomaly Intelligence Platform

**Última actualización:** 2026-06-04 (cierre de Pre-F1)
**Estado del proyecto:** **Pre-F1 cerrada · Listo para implementación de Fase 1** (pendiente acción operativa P1–P3 sobre Pre-F1.C)
**Bus factor declarado:** 1 (ver ADR-0026)

---

## Para el lector con prisa

- **¿Qué es AIP hoy?** Un cuerpo de **32 ADRs aceptados**, un Red Team Review crítico cerrado, especificaciones operativas Pre-F1 completas y un `MAINTAINERS.md` vigente. **Cero código ejecutable.**
- **¿Qué hará en V1?** Ingestar un PDF público, direccionarlo por hash, registrar procedencia, verificar integridad. **Nada más.**
- **¿Cuándo?** Sin compromiso de calendario. Mantenedor único part-time.
- **¿Por qué tan modesto?** Porque el Red Team Review identificó como modo de fallo dominante el "vaporware perpetuo" y el recorte deliberado de alcance (ADR-0023) es la defensa estructural.
- **¿Qué falta para escribir código?** Una sola acción operativa puntual: descargar el PDF de demo y rellenar los pinned values en `docs/phase-1/demo-evidence-selection.md` (procedimiento P1–P3 de ese documento).

---

## Estado de los documentos

### Aprobado y vivo en disco

```
anomaly-intelligence-platform/
├── PROJECT_STATUS.md                       (este documento)
├── README.md                                (resumen público)
├── LICENSE                                  (Apache 2.0)
├── MAINTAINERS.md                           (artefacto obligatorio ADR-0026 C1)
└── docs/
    ├── adr/
    │   ├── README.md                        (índice de ADRs con estado de implementación V1)
    │   ├── template.md                      (plantilla canónica)
    │   ├── 0000-long-term-vision.md         (la brújula; con enmiendas al pie)
    │   ├── 0001 .. 0022                     (bloque fundacional, 23 ADRs)
    │   ├── 0023-scope-reduction.md          (recorte deliberado a V1)
    │   ├── 0024-epistemic-honesty-amendment.md (7 límites operativos)
    │   ├── 0025-neutrality-clarification.md (4 sesgos declarados; reformula P4)
    │   ├── 0026-sustainable-stewardship.md  (5 compromisos operativos)
    │   ├── 0027-graceful-archive-policy.md  (triggers temporales + procedimiento)
    │   ├── 0028-license-reassessment.md     (reafirma Apache + CC BY-SA corpus)
    │   ├── 0029-runtime-language-decision.md (Python 3.11+ + uv formalizado)
    │   ├── 0030-repository-layout.md         (src layout + 4 subpaquetes)
    │   └── 0031-testing-strategy.md          (unit/integration/reproducibility, sin red)
    ├── phase-1/
    │   ├── demo-evidence-selection.md       (Pre-F1.C: PDF canónico, S1–S7, P1–P5, V1–V3)
    │   └── command-specification.md         (Pre-F1.D: contrato testeable de los 3 comandos)
    ├── models/                              (vacío; reservado para fases futuras)
    └── reviews/
        ├── adr_red_team_review.md           (crítica hostil del 2026-06-03, intacta)
        └── red_team_response.md             (informe formal de cierre 2026-06-04)
```

### Total ADRs aprobados: 32

- **23 fundacionales** (0000–0022).
- **6 enmiendas** (0023–0028) en respuesta al Red Team Review.
- **3 operativos Pre-F1** (0029–0031).

### Documentos referenciados por ADRs

| Documento | ADR que lo exige | Estado |
|---|---|---|
| `MAINTAINERS.md` | ADR-0026 C1 | **Creado 2026-06-04** |
| `docs/phase-1/demo-evidence-selection.md` | Pre-F1.C | **Creado 2026-06-04** (pinned values pendientes — acción puntual del mantenedor) |
| `docs/phase-1/command-specification.md` | Pre-F1.D | **Creado 2026-06-04** |
| `docs/ethics-procedures/` | ADR-0026 C4 | Pendiente (no crítico para F1; sí antes de cualquier ingestión que no sea el fixture de demo) |
| `docs/ethics-procedures/classified-material.md` | ADR-0026 §RTR §8.3 | Pendiente (mismo criterio) |
| `docs/legal-compliance.md` | ADR-0019 | Pendiente (mismo criterio) |
| `docs/osint-code-of-practice.md` | ADR-0014 | Diferido (fuera de V1) |
| `docs/vocabulary/` | ADR-0011, ADR-0025 | Diferido (fuera de V1) |
| `docs/visualization-guidelines.md` | ADR-0012, ADR-0013 | Diferido (fuera de V1) |
| `docs/schema-migrations/` | ADR-0016 | Pendiente (vacío al inicio; se llena con cambios reales) |

Para implementación de F1 strictu sensu, los únicos documentos bloqueantes están **creados**. Los pendientes restantes son obligaciones para fases posteriores, no para abrir F1.

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

## Próxima acción

Pre-F1 queda cerrada documentalmente. La única acción operativa pendiente entre "documento listo" y "primer commit de código" es **rellenar los pinned values del fixture de demo** siguiendo P1–P3 de `docs/phase-1/demo-evidence-selection.md`. Esa acción:

1. Es una sesión puntual (no es funcionalidad del proyecto): descargar el Twining Memo desde NARA, anotar URL/fecha/tamaño, computar SHA-256 con `sha256sum`, copiar el binario a `tests/data/`, registrar valores en la sección "Pinned values" del documento Pre-F1.C, y commit con motivo explícito.
2. Requiere red **una sola vez** por parte del mantenedor (acción operativa, no parte del sistema).
3. Desbloquea los tests de reproducibilidad (T3 del ADR-0031), que necesitan `EXPECTED_PDF_SHA256` como constante canónica antes de poder ejecutarse.

Tras esa sesión puntual, la cadena de implementación F1 puede comenzar sin más bloqueos:

```
Pinned values registrados
    │
    ▼
Esqueleto del paquete (pyproject.toml, src/aip/, tests/)
    │
    ▼
core/hashing.py + tests unitarios → ROJO → VERDE
    │
    ▼
core/{evidence, source, provenance, authentication, actor}.py + unit tests
    │
    ▼
storage/{layout, caos, manifest, tables}.py + unit tests
    │
    ▼
audit/{log, verify}.py + unit tests
    │
    ▼
cli/{main, evidence_commands, archive_commands}.py
    │
    ▼
integration/demo_pipeline_test.py → ROJO → VERDE (cierre operativo de F1)
    │
    ▼
reproducibility/{manifest_hash, audit_chain, jcs}_test.py → VERDE
    │
    ▼
Auto-prueba en máquina limpia del mantenedor
    │
    ▼
Invitación pública a externo
    │
    ▼
Externo cierra demo sin asistencia → release v0.1.0 → F1 cerrada
```

No se escribe código antes de fijar los pinned values. No se amplía alcance bajo ningún pretexto antes del release v0.1.0.

---

*El proyecto AIP no garantiza éxito. Garantiza honestidad sobre el riesgo. La aspiración del ADR-0000 sigue siendo la brújula; V1 es el paso ejecutable más pequeño que avanza en su dirección.*
