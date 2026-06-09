# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
El proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.1] — 2026-06-08

Patch UX descubierto durante el primer uso real del flujo de atestación
sobre `archive_snapshot` (ADR-0042).

### Fixed

- **`aip attestation sign` auto-detect para `archive_snapshot`**. En
  v0.2.0 el kind `archive_snapshot` se añadió a
  `ALLOWED_ARTIFACT_KINDS` y al verificador universal (`aip verify`),
  pero el detector local de `attestation_commands.py` se olvidó de
  incluirlo. Síntoma: `aip attestation sign snap.json ...` fallaba con
  `could not auto-detect artifact_kind` aunque el archivo era un
  ArchiveSnapshot válido. Workaround en v0.2.0: `--artifact-kind
  archive_snapshot` explícito.

### Added

- Regression test `test_sign_autodetects_archive_snapshot` en
  `tests/unit/cli/test_attestation_commands.py`.

### Metrics

- 911 tests (era 910).
- 17/17 pins reproducibility intactos.
- 2/2 pins audit-chain base intactos.

---

## [0.2.0] — 2026-06-08

Cierre arquitectónico de V1. Capa de atestación criptográfica ed25519,
cadena de audit extendida a 6 dominios derivados, reconciliación
disco↔log, snapshot archive-wide atestable, y siete motores de derivación
adicionales sobre el archive base de v0.1.0.

26 commits desde v0.1.0. 42 ADRs aceptados + 3 enmiendas estructurales
(E1 a ADR-0019, E15/E16 a ADR-0030).

**Resumen ejecutivo**:

- **5 nuevos ADRs mayores** introducen capas derivadas que respetan
  ADR-0023 (Scope Reduction): cada una opt-in, removible bit-a-bit,
  sin tocar la integridad del archive base.
- **2 nuevos ADRs introducen verificación exógena**: ADR-0041
  (atestación ed25519 por artefacto) + ADR-0042 (snapshot archive-wide
  atestable). La pregunta central — *"¿qué evidencia existe y cómo
  demostramos que no fue alterada?"* — pasa de verificación
  endógena (auto-consistente) a exógena (verificable contra una clave
  externa, sin acceso al archive).
- **3 enmiendas estructurales** cierran ciclos incompletos sin nuevos
  subpaquetes ni dependencias.

### Added

#### Motores derivados (capa V1+, opt-in, removible)

- **ADR-0032** — Authentication Assessment Engine: motor determinista
  de evaluación de autenticidad sobre el grafo de procedencia. Cinco
  status booleanos. Sin ML, sin scoring probabilístico. Removible sin
  tocar la evidencia.
- **ADR-0033** — Evidence Graph V1: grafo de procedencia derivado,
  read-only, removible. Vista estructural sobre `evidence`, `sources`,
  `provenance_steps` y assessments.
- **ADR-0034** — Impact Analysis Engine: reverse-dependency
  reachability sólo. "¿Qué se queda sin respaldo si esto desaparece?"
- **ADR-0035** — Context Assembly Layer: agregación pura de salidas
  canónicas de los motores anteriores en un `ContextBundle` con
  self-hash. Cero información nueva.
- **ADR-0036** — Investigation Workspace V1: índice reproducible de
  referencias a artefactos derivados.
- **ADR-0037** — Investigation Timeline Engine: vista cronológica
  ordenada.
- **ADR-0038** — Investigation Snapshot Engine: congelación
  reference-only de pares (workspace, timeline).
- **ADR-0039** — Investigation Diff Engine: set-difference puro entre
  snapshots/justifications.
- **ADR-0040** — Investigation Justification Engine: cadena deductiva
  categorizada por rol con anclaje a una conclusión.

#### Verificación exógena

- **ADR-0041** — Operator Attestation Engine V1: firma ed25519 sobre
  artefactos verificables. Cualquier tercero con la clave pública
  verifica offline, sin acceso al archive. Nueva dependencia:
  `cryptography>=42,<46` (ADR-0029 §E1 justifica). Seis kinds firmables
  iniciales: workspace, timeline, snapshot, justification,
  context_bundle, manifest.
- **ADR-0042** — Archive State Snapshot V1: combina `manifest_hash`
  (estado de tablas+blobs) y `audit_log_head_hash` (historia
  encadenada) en un único valor JCS-canónico atestable. Séptimo kind
  firmable (`archive_snapshot`). Read-only por construcción.
  Cierra el vector "reescritura silenciosa de historia con
  manifest_hash invariante".

#### Enmiendas estructurales (cierre de ciclos incompletos)

- **ADR-0019 §E1** — Audit chain archive-wide. La cadena hash-encadenada
  pasa de 2 acciones (bootstrap + ingest) a 8 (añade `ASSESS_AUTHENTICATION`,
  `BUILD_WORKSPACE`, `BUILD_TIMELINE`, `BUILD_SNAPSHOT`,
  `BUILD_JUSTIFICATION`, `SIGN_ATTESTATION`). Cada persistencia
  derivada emite exactamente una entry. `audit_log_head_hash` se
  vuelve archive-state fingerprint real.
- **ADR-0030 §E15** — `attestation/` como 12º subpaquete con S-rule
  S16 (dependencias permitidas: `core/`, `storage/` lectura del
  manifest, `errors/` + librería externa `cryptography`).
- **ADR-0030 §E16** — `integrity/` audita atestaciones + reconcilia
  artefactos persistidos contra entries del audit log. Cuatro nuevos
  `IntegrityIssueKind`: `ATTESTATION_HASH_MISMATCH`,
  `MISSING_AUDIT_ENTRY`, `MISSING_PERSISTED_ARTIFACT`,
  `AUDIT_LOG_HASH_MISMATCH`. `aip archive verify --derived` se
  convierte en single-pass full-archive integrity audit.

#### Nuevos comandos CLI

```sh
# ADR-0032 (assessment)
aip assess-authentication --archive PATH --evidence-id ID --actor @op
aip list-assessments --archive PATH [--evidence-id ID]

# ADR-0033 (graph)
aip graph build|show|neighbors

# ADR-0034 (impact)
aip impact analyze|show

# ADR-0035 (context)
aip context assemble|show|verify

# ADR-0036–0040 (workspace, timeline, snapshot, diff, justification)
aip workspace create|show|verify
aip timeline build|show|verify
aip snapshot create|show|verify
aip diff snapshots|justifications
aip justification build|show|verify

# ADR-0041 (attestation, ed25519)
aip attestation keygen|sign|verify|show

# ADR-0042 (archive snapshot)
aip archive snapshot [--generated-at TS] [--output FILE]

# Hardening (universal artifact verifier auto-detect)
aip verify <artifact.json>            # auto-detecta 7 kinds + delega
aip archive verify --derived          # incluye reconciliación disco↔log
```

#### Reproducibility pins

- `EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH` (ADR-0032 §pin)
- `EXPECTED_DEMO_CONTEXT_BUNDLE_HASH` (ADR-0035 §pin)
- `EXPECTED_DEMO_JUSTIFICATION_HASH` (ADR-0040 §pin)
- `EXPECTED_DEMO_ARCHIVE_SNAPSHOT_HASH` (ADR-0042 §pin)
- 17 pins canónicos totales (era 13 en v0.1.0).

#### Tests

- 910 tests (era 469 en v0.1.0).
- Property tests (Hypothesis) sobre JCS canonicalization y audit chain.
- AST guards de import boundaries por subpaquete (ADR-0030 S-rules
  verificadas estructuralmente).
- Forbidden-tokens guards: cada motor derivado prohíbe ~30 tokens de
  interpretación (severity, recommendation, probability, etc.).

### Changed

- **Polish v1 — escritura atómica**: las 5 funciones `persist_*`
  derivadas (workspace, timeline, snapshot, justification,
  attestation) migran de `write_text` directo a `atomic_write_text`
  (write-to-tmp + `os.replace`). Defensa mínima contra ficheros
  parcialmente escritos por crashes mid-write. Patrón coherente con
  `write_manifest_atomic` y la ingesta CAOS.
- **Reproducibility pins desacoplados de `__version__`**: corrección
  de un latente que acoplaba pins canónicos a la versión live del
  paquete. Los pins ahora usan `CANONICAL_SOFTWARE_VERSION="0.0.1"`
  consistentemente — versión bumps no invalidan pins de modelo.
- **CI hardening**: cross-platform smoke (Linux/macOS/Windows),
  Dependabot security-only, templates de PR/issue.

### Fixed

- Lotes de auditoría F3/F5 cerrados (drift docs, classified-material
  honesto, CI a uv).
- Coverage gaps post-F3/F5 (lotes C, D).

### Architecture

- 12 nuevos subpaquetes operativos: `analysis`, `graph`, `impact`,
  `context`, `workspace`, `timeline`, `snapshot`, `diff`,
  `justification`, `integrity`, `attestation`, + `audit/archive_state`.
- 42 ADRs aceptados (era 31 en v0.1.0). Todas las extensiones respetan
  ADR-0023 §congelación: cada motor es derivado, opt-in, removible.

### Dependencies

- **Nueva** (V1+): `cryptography>=42,<46` — ed25519 sign/verify
  (justificación en ADR-0029 §E1).
- Sin otras dependencias nuevas. Lock pineado en `uv.lock`.

---

## [0.1.0] — 2026-06-06

Primer release ejecutable.

### Added

- 31 ADRs cubren la fundación arquitectónica (ADR-0000 a ADR-0031).
- Modelo de evidencia y procedencia: `Evidence`, `Source`,
  `Provenance`, `ProvenanceStep`.
- CAOS (Content-Addressed Object Store) con verificación bit-a-bit.
- `ArchiveManifest` JCS-canónico con `manifest_hash`.
- Audit log append-only con hash chain (ADR-0019, 2 acciones V1:
  `ARCHIVE_BOOTSTRAP`, `INGEST_EVIDENCE`).
- CLI: `aip evidence ingest`, `aip evidence show`, `aip archive verify`.
- Demo pipeline reproducible bit-a-bit sobre el Twining Memo (1947).
- 13 pins canónicos de reproducibility.
- 469 tests.

Ver release notes históricas del tag `v0.1.0`.

---

[0.2.1]: https://github.com/JFHelvetius/anomally_intelligence/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/JFHelvetius/anomally_intelligence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/JFHelvetius/anomally_intelligence/releases/tag/v0.1.0
