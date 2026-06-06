# Pre-F1.D — Command Specification

**Fecha:** 2026-06-04
**Estado:** Especificación pre-implementación
**Relacionado con:** ADR-0017 (API design), ADR-0023 (Scope Reduction), ADR-0005, ADR-0006, ADR-0015, ADR-0016, ADR-0019, ADR-0030, ADR-0031

---

## Propósito

Definir la sintaxis, inputs, outputs, errores y comportamiento esperado de los tres comandos de V1:

- `aip evidence ingest`
- `aip evidence show`
- `aip archive verify`

Esta especificación es **el contrato** que la implementación debe satisfacer. Los tests de integración (ADR-0031 T2) y los tests de reproducibilidad (T3) se construyen contra este documento.

Cualquier desviación de la especificación durante la implementación se gestiona como:

- **Inconsistencia menor (formato de output, mensaje exacto)**: actualizar este documento por PR antes de implementar.
- **Inconsistencia mayor (semántica, contrato, alineación con ADRs)**: la implementación se detiene; se enmenda este documento o se cuestiona la especificación con ADR si toca decisión arquitectónica.

Este documento **no** es un ADR. Es la especificación operativa de los artefactos comprometidos por ADR-0023.

---

## Principios generales aplicables a los tres comandos

### G1. Cada comando es invocable como subcomando de `aip`

```
aip <namespace> <verb> [args] [options]
```

- `aip evidence ingest ...`
- `aip evidence show ...`
- `aip archive verify`

La CLI también soporta `python -m aip <namespace> <verb> ...` por convención del ADR-0030 (existencia de `__main__.py`).

### G2. Cada comando es delgado sobre la API Python

Cada comando es un wrapper que llama a una función pública de la API Python. La CLI no implementa lógica de dominio.

API Python equivalente (firmas tentativas, se concretan al implementar):

```python
from aip import Archive

archive = Archive.open("/path/to/archive")           # abre o crea
evidence = archive.ingest_evidence(...)              # equivalente a `aip evidence ingest`
evidence_view = archive.show_evidence(hash="...")    # equivalente a `aip evidence show`
result = archive.verify()                            # equivalente a `aip archive verify`
```

Las firmas exactas se concretan al escribir el código, pero la equivalencia 1:1 es invariante.

### G3. Cada comando opera sobre un archive raíz declarado

Todos los comandos aceptan la opción `--archive-root <path>`:

- Si se pasa, es la ruta al directorio raíz del archive AIP.
- Si se omite, se busca:
  1. La variable de entorno `AIP_ARCHIVE_ROOT`.
  2. Si no existe, `~/.aip/` (default declarado por ADR-0015).

Si el path no existe ni puede crearse (caso de `ingest` con archive nuevo), el comando produce error `ArchiveNotFoundError`.

### G4. Cada comando produce output estructurado por defecto

El formato de output por defecto es **human-readable plain text** legible en terminal. Opciones de output adicionales:

- `--json` para output JSON-encoded en stdout. Útil para scripting y para inputs de los tests.
- `--quiet` para suprimir output excepto errores.

`--json` es ortogonal a `--quiet`: `--json --quiet` es contradictorio y produce error.

### G5. Códigos de salida estándar

| Exit code | Significado |
|---|---|
| `0` | Éxito |
| `1` | Error de entrada del usuario (path no existe, argumento inválido) |
| `2` | Error de estado del archive (corrupción detectada, cadena de audit rota) |
| `3` | Error de integridad de un blob (hash no coincide) |
| `4` | Error de configuración (manifiesto inconsistente, schema_version desconocida) |
| `64` | Error de argumentos de línea de comandos (sysexits.h EX_USAGE) |
| `>127` | Reservado para señales del sistema (no usado por el código) |

Cada error específico mapea a uno de estos códigos. Errores con causa específica reportan código + mensaje detallado.

### G6. Todos los errores son tipados

Errores derivan de excepciones tipadas en `aip.errors` (ADR-0030). La CLI captura excepciones y mapea a (exit code, mensaje). La API Python las propaga sin captura.

Catálogo mínimo de errores (V1):

- `AIPError` (base abstracta).
- `UsageError` → exit 64.
- `ArchiveNotFoundError` → exit 1.
- `EvidenceNotFoundError` → exit 1.
- `InvalidSourceMetadataError` → exit 1.
- `IntegrityError` → exit 3.
- `AuditChainError` → exit 2.
- `ManifestError` → exit 4.

### G7. Sin red, sin LLM, sin servicios externos

Conforme a ADR-0023 y ADR-0031, **ningún** comando accede a red. La ingesta opera sobre un fichero local. La verificación opera sobre el archive local. No hay descargas, no hay APIs externas.

### G8. Logging

Todos los comandos emiten logs estructurados a stderr cuando se pasa `--verbose`. Sin esa opción, stderr permanece silencioso excepto por mensajes de error. Los logs **nunca** van a stdout (preserva limpieza para scripting).

---

## Comando 1: `aip evidence ingest`

### Propósito

Ingestar un fichero local al archive como una nueva `Evidence`. Computa el hash, almacena el blob en CAOS, registra metadatos en las tablas, anota la entrada correspondiente en el audit log.

### Sintaxis

```
aip evidence ingest <PATH>
    --source-id <ID>
    --source-name <NAME>
    [--source-kind <KIND>]
    [--source-authority <LEVEL>]
    [--source-jurisdiction <ISO3166>]
    [--source-license <LICENSE>]
    [--kind <EVIDENCE_KIND>]
    [--ingested-by <ACTOR_ID>]
    [--archive-root <PATH>]
    [--notes <MARKDOWN>]
    [--dry-run]
    [--json]
    [--verbose]
```

### Inputs

| Argumento / opción | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `<PATH>` | path | sí | Ruta al fichero a ingestar. Debe existir y ser legible. |
| `--source-id <ID>` | str | sí | Identificador de la `Source` ya conocida o a crear. |
| `--source-name <NAME>` | str | sí (si `--source-id` no existe) | Nombre humano de la `Source`. Obligatorio cuando se crea fuente nueva. |
| `--source-kind <KIND>` | enum | recomendado | Uno de los valores de `SourceKind` (ADR-0005). Default: `unknown` con warning. |
| `--source-authority <LEVEL>` | enum | recomendado | Uno de los valores de `AuthorityLevel`. Default: `unattributable` con warning. |
| `--source-jurisdiction <ISO3166>` | str | opcional | Código ISO 3166-1 alpha-2 o alpha-3. |
| `--source-license <LICENSE>` | str | opcional | Identificador de licencia (SPDX preferido) o cadena descriptiva. |
| `--kind <EVIDENCE_KIND>` | enum | opcional | Uno de los valores de `EvidenceKind` (ADR-0006). Si se omite, se infiere por extensión y MIME (`.pdf` → `document_scan` por defecto). |
| `--ingested-by <ACTOR_ID>` | str | opcional | ActorId del responsable de la ingesta. Default: actor declarado en `MAINTAINERS.md` actual o el handle del usuario del sistema. |
| `--archive-root <PATH>` | path | opcional | Ruta al archive. Default: ver G3. |
| `--notes <MARKDOWN>` | str | opcional | Notas en markdown asociadas a la `Evidence`. |
| `--dry-run` | flag | opcional | Computa el hash y valida metadatos sin escribir nada al archive. |
| `--json` | flag | opcional | Output en JSON. |
| `--verbose` | flag | opcional | Logging a stderr. |

### Comportamiento esperado (camino feliz)

1. Validar argumentos. Si `<PATH>` no existe → `UsageError`. Si `--source-id` no está acompañado de `--source-name` y la fuente no existe → `InvalidSourceMetadataError`.
2. Abrir el archive en `--archive-root`. Si no existe, **crearlo** con el layout canónico del ADR-0030 (CAOS vacío, tablas vacías, manifiesto inicial, audit log con entrada bootstrap).
3. Computar SHA-256 del fichero en streaming (no carga completa en memoria).
4. Verificar si la evidencia ya existe en CAOS:
   - Si existe: **idempotencia**. No se duplica. Se reporta evidencia existente y se sale con exit code 0 y mensaje "already ingested".
   - Si no existe: continúa.
5. Si `--source-id` apunta a una `Source` existente, validar consistencia con los args. Si los args contradicen la fuente existente → `InvalidSourceMetadataError`. Si son consistentes, usar la `Source` existente.
6. Si `--source-id` no existe, crear nueva `Source` con los atributos provistos. `--source-name` obligatorio en este caso.
7. Construir `Provenance` mínima con:
   - `origin_source_id` = source_id resuelto en el paso 5/6.
   - `steps` = un único paso `original_capture` cuando no se proporciona información adicional.
   - `is_complete` = `false`.
   - `gaps` = lista con un único gap declarado: "ingestión inicial sin reconstrucción de cadena previa al artefacto".
8. Construir `AuthenticationAssessment` por defecto con `status = unverified`.
9. Construir `Evidence` con todos los campos canónicos.
10. Si `--dry-run`: emitir el output con el hash computado y los metadatos que **se hubieran escrito**, sin tocar disco. Salir con exit code 0.
11. Si no es dry-run:
    - Mover/copiar el blob a `objects/sha256/<2>/<rest>` en el archive (atómico: escribir en tmp + rename).
    - Verificar que el hash del blob almacenado coincide con el computado en paso 3.
    - Insertar entrada en la tabla `evidence` con esquema versionado.
    - Insertar/actualizar entrada en la tabla `sources` si aplica.
    - Insertar `Provenance` y `ProvenanceStep`s en sus tablas.
    - Insertar `AuthenticationAssessment`.
    - Anotar entrada en el audit log con `action: ingest_evidence`, `target: aip:evidence/sha256:<hash>`, parámetros, exit.
    - Actualizar el `ArchiveManifest` (recomputar hashes de tablas afectadas, recomputar root).
12. Emitir output canónico.

### Output (texto humano)

```
Ingested evidence:
  Hash:        sha256:1f4a9c0a...
  Kind:        document_scan
  Size:        356721 bytes
  Source:      blue-book-nara — Project Blue Book records (government_archive, secondary)
  Provenance:  1 step declared (original_capture); 1 gap noted
  Auth:        unverified
  Ingested by: @jfhelvetius
  Archive:     /home/user/.aip
  URI:         aip:evidence/sha256:1f4a9c0a...
```

### Output (`--json`)

```json
{
  "ok": true,
  "action": "ingest_evidence",
  "evidence": {
    "uri": "aip:evidence/sha256:1f4a9c0a...",
    "hash": "1f4a9c0a...",
    "kind": "document_scan",
    "size_bytes": 356721,
    "mime_type": "application/pdf",
    "source_id": "blue-book-nara",
    "ingested_at": "2026-06-04T15:30:12Z",
    "ingested_by": "@jfhelvetius",
    "schema_version": "0.1.0"
  },
  "source": {
    "id": "blue-book-nara",
    "name": "Project Blue Book records",
    "kind": "government_archive",
    "authority": "secondary"
  },
  "provenance": {
    "is_complete": false,
    "step_count": 1,
    "gap_count": 1
  },
  "archive_root": "/home/user/.aip",
  "archive_manifest_hash": "fedcba98..."
}
```

### Errores

| Error | Exit | Mensaje canónico |
|---|---|---|
| `UsageError` | 64 | "missing required argument: ..." |
| `UsageError` (path) | 1 | "file not found: <path>" |
| `InvalidSourceMetadataError` | 1 | "source-id 'X' does not exist; --source-name is required" |
| `IntegrityError` | 3 | "post-write hash mismatch; ingestion aborted" |
| `ManifestError` | 4 | "manifest inconsistent after ingestion; archive may need repair" |

### Idempotencia y dry-run

- **Idempotencia:** ingestar dos veces el mismo fichero produce el mismo hash y la segunda invocación no duplica. Reporta "already ingested" y sale 0. Esto refleja la inmutabilidad de evidencia (P11).
- **Dry-run:** no toca disco. Solo computa hash y valida metadatos. Útil para CI y para validación de input antes de operación real.

### Ejemplo de uso

```
$ aip evidence ingest twining-memo.pdf \
    --source-id blue-book-nara \
    --source-name "Project Blue Book records" \
    --source-kind government_archive \
    --source-authority secondary \
    --source-jurisdiction USA \
    --source-license public_domain \
    --kind document_scan \
    --ingested-by @jfhelvetius \
    --notes "Demo fixture for Phase 1 closure."
```

---

## Comando 2: `aip evidence show`

### Propósito

Recuperar y mostrar la `Evidence` completa identificada por su hash. Incluye su `Source`, su `Provenance`, su `AuthenticationAssessment`, y los metadatos de ingestión.

Operación de **solo lectura**.

### Sintaxis

```
aip evidence show <HASH | URI>
    [--archive-root <PATH>]
    [--json]
    [--verbose]
```

### Inputs

| Argumento / opción | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `<HASH | URI>` | str | sí | SHA-256 en hex (con o sin prefijo `sha256:`) o URI `aip:evidence/sha256:<hash>`. |
| `--archive-root <PATH>` | path | opcional | Ver G3. |
| `--json` | flag | opcional | Output en JSON. |
| `--verbose` | flag | opcional | Logging a stderr. |

### Comportamiento esperado

1. Validar argumento. Aceptar las tres formas:
   - `sha256:1f4a9c0a...`
   - `1f4a9c0a...` (sin prefijo)
   - `aip:evidence/sha256:1f4a9c0a...`
2. Abrir archive en `--archive-root`. Si no existe → `ArchiveNotFoundError`.
3. Resolver hash a `Evidence` en tabla `evidence`. Si no existe → `EvidenceNotFoundError`.
4. Recuperar `Source` referenciada por `source_id`.
5. Recuperar `Provenance` (`steps` y `gaps`) si existe.
6. Recuperar `AuthenticationAssessment`.
7. Verificar que el blob en CAOS existe y su hash coincide. Si no coincide → `IntegrityError` (decisión: el comando reporta y falla, no oculta el problema).
8. Componer output canónico.

### Output (texto humano)

```
Evidence: aip:evidence/sha256:1f4a9c0a...

  Hash:           sha256:1f4a9c0a...
  Kind:           document_scan
  MIME:           application/pdf
  Size:           356721 bytes
  Status:         active
  Schema version: 0.1.0

  Ingested at:    2026-06-04T15:30:12Z
  Ingested by:    @jfhelvetius

Source:
  ID:           blue-book-nara
  Name:         Project Blue Book records
  Kind:         government_archive
  Authority:    secondary
  Jurisdiction: USA
  License:      public_domain

Provenance:
  Is complete:  false
  Step 1:       original_capture (actor: unknown)
  Gap 1:        ingestión inicial sin reconstrucción de cadena previa al artefacto

Authentication:
  Status:    unverified
  Assessor:  —
  Method:    —

Intrinsic metadata:
  (none recorded)

Notes:
  Demo fixture for Phase 1 closure.
```

### Output (`--json`)

```json
{
  "ok": true,
  "evidence": {
    "uri": "aip:evidence/sha256:1f4a9c0a...",
    "hash": "1f4a9c0a...",
    "kind": "document_scan",
    "mime_type": "application/pdf",
    "size_bytes": 356721,
    "status": "active",
    "schema_version": "0.1.0",
    "ingested_at": "2026-06-04T15:30:12Z",
    "ingested_by": "@jfhelvetius",
    "intrinsic_metadata": {},
    "notes": "Demo fixture for Phase 1 closure."
  },
  "source": {
    "id": "blue-book-nara",
    "name": "Project Blue Book records",
    "kind": "government_archive",
    "authority": "secondary",
    "jurisdiction": "USA",
    "license": "public_domain"
  },
  "provenance": {
    "is_complete": false,
    "steps": [
      { "step_id": 1, "kind": "original_capture", "actor": "unknown" }
    ],
    "gaps": [
      { "description": "ingestión inicial sin reconstrucción de cadena previa al artefacto" }
    ]
  },
  "authentication": {
    "status": "unverified",
    "assessor": null,
    "method": null
  }
}
```

### Errores

| Error | Exit | Mensaje canónico |
|---|---|---|
| `UsageError` | 64 | "invalid hash or URI: ..." |
| `ArchiveNotFoundError` | 1 | "archive not found at <path>" |
| `EvidenceNotFoundError` | 1 | "no evidence with hash sha256:<X> in this archive" |
| `IntegrityError` | 3 | "blob hash mismatch for evidence sha256:<X>" |

### Ejemplo de uso

```
$ aip evidence show sha256:1f4a9c0a...

$ aip evidence show 1f4a9c0a... --archive-root ./local-archive --json | jq '.evidence.size_bytes'

$ aip evidence show aip:evidence/sha256:1f4a9c0a...
```

---

## Comando 3: `aip archive verify`

### Propósito

Verificar la integridad completa del archive:

1. Cada blob en CAOS tiene el hash declarado en su nombre.
2. La cadena del audit log es consistente (hashes encadenados correctos).
3. El `ArchiveManifest` es consistente con las tablas y los blobs.
4. Las tablas son legibles bajo su `schema_version`.
5. Las referencias internas (Evidence → Source, Evidence → Provenance, etc.) son válidas.

Operación de **solo lectura**.

### Sintaxis

```
aip archive verify
    [--archive-root <PATH>]
    [--quick]
    [--full]
    [--json]
    [--verbose]
```

### Inputs

| Opción | Tipo | Default | Descripción |
|---|---|---|---|
| `--archive-root <PATH>` | path | ver G3 | Ver G3. |
| `--quick` | flag | off | Modo rápido: verifica audit chain, manifest, referencias. **No** rehashea todos los blobs (los asume válidos si el manifest lo es). |
| `--full` | flag | **on** | Modo completo: incluye `--quick` + rehasheo de todos los blobs. **Default**. |
| `--json` | flag | opcional | Output en JSON. |
| `--verbose` | flag | opcional | Logging a stderr. |

`--quick` y `--full` son mutuamente excluyentes. Si ambos se pasan → `UsageError`.

### Comportamiento esperado

1. Abrir archive. Si no existe → `ArchiveNotFoundError`.
2. Cargar `ArchiveManifest`. Si corrupto → `ManifestError`.
3. **Verificación de la cadena del audit log:**
   - Para cada entrada en orden:
     - Recomputar `entry_hash` desde los campos.
     - Comparar contra el valor almacenado.
     - Verificar que `prev_hash` coincide con el `entry_hash` de la entrada anterior.
   - Si cualquier desfase → `AuditChainError`. Reportar la primera entrada inconsistente.
4. **Verificación de referencias internas:**
   - Para cada `Evidence`, verificar que su `source_id` existe en tabla `sources`.
   - Para cada `Evidence`, verificar que su `Provenance` (si existe) está consistente.
   - Si alguna referencia rota → `ManifestError` con detalle.
5. **Verificación de blobs** (solo en `--full`):
   - Para cada `Evidence` en tabla `evidence`:
     - Verificar que el blob existe en `objects/sha256/<2>/<rest>`.
     - Rehashear el blob.
     - Comparar con el hash declarado.
   - Si cualquier mismatch → `IntegrityError`. Reportar todos los blobs problemáticos antes de salir (no se aborta al primero).
6. **Verificación del manifest:**
   - Recomputar `archive_manifest_hash` desde el estado actual.
   - Comparar con el valor almacenado.
   - Si discrepa → `ManifestError`.
7. Si todas las verificaciones pasan, reportar resumen y salir 0.

### Output (texto humano, `--full` éxito)

```
Verifying archive at /home/user/.aip ...

Audit log:           OK (1 entries, chain valid)
Internal references: OK (1 evidence → source, 1 provenance step)
Blobs:               OK (1/1 blobs rehashed, all match)
Manifest:            OK (archive_manifest_hash matches)

Archive integrity verified.
  Evidences:          1
  Sources:            1
  Provenance steps:   1
  Audit entries:      1
  Archive manifest:   fedcba98...
```

### Output (`--json`)

```json
{
  "ok": true,
  "archive_root": "/home/user/.aip",
  "mode": "full",
  "checks": {
    "audit_chain": { "ok": true, "entries": 1 },
    "references":  { "ok": true, "evidence_count": 1, "broken": 0 },
    "blobs":       { "ok": true, "rehashed": 1, "mismatches": 0 },
    "manifest":    { "ok": true, "expected": "fedcba98...", "actual": "fedcba98..." }
  },
  "summary": {
    "evidences": 1,
    "sources": 1,
    "provenance_steps": 1,
    "audit_entries": 1,
    "archive_manifest_hash": "fedcba98..."
  }
}
```

### Output en caso de fallo (texto humano)

```
Verifying archive at /home/user/.aip ...

Audit log:           OK (5 entries, chain valid)
Internal references: OK (5 evidences → 2 sources, 5 provenance steps)
Blobs:               FAIL (4/5 OK, 1 mismatch)
  - aip:evidence/sha256:abcd1234... — declared hash != actual

Archive integrity FAILED. See errors above.
```

Exit code: `3` (IntegrityError).

### Errores

| Error | Exit | Cuándo |
|---|---|---|
| `UsageError` | 64 | `--quick` y `--full` simultáneos. |
| `ArchiveNotFoundError` | 1 | Path inexistente o no es archive AIP. |
| `AuditChainError` | 2 | Cadena de audit log rota. |
| `ManifestError` | 4 | Referencias rotas o manifest inconsistente. |
| `IntegrityError` | 3 | Mismatch de hash en ≥1 blob. |

Cuando se detectan múltiples problemas en `--full`, se reportan **todos** antes de salir. El exit code refleja el problema más severo (jerarquía: 3 > 2 > 4 > 1).

### Ejemplo de uso

```
$ aip archive verify
$ aip archive verify --archive-root ./local-archive --quick
$ aip archive verify --json | jq '.checks.blobs.mismatches'
```

---

## Comportamiento bootstrap (archive nuevo)

Cuando `aip evidence ingest` se invoca sobre un `--archive-root` que **no existe**:

1. Crear el directorio raíz.
2. Crear el layout canónico:
   - `objects/sha256/` (vacío).
   - `tables/` con tablas Parquet vacías y schema declarado.
   - `audit.log` con entrada bootstrap único:
     - `seq = 0`
     - `prev_hash = "0" * 64`
     - `action = "archive_bootstrap"`
     - `actor = <ingested-by>`
     - `timestamp = <now>` (registrado con honestidad; reproducibilidad bit a bit se logra fijando timestamps en tests)
   - `manifest.json` inicial con tablas vacías hashed.
3. Continuar con la ingestión.

`aip evidence show` y `aip archive verify` sobre un archive nuevo (sin entradas) devuelven respectivamente `EvidenceNotFoundError` y "Archive integrity verified" con conteos a cero.

---

## Lo que estos comandos NO hacen

Para preservar la disciplina del recorte de alcance:

- ❌ **No imprimen el contenido del PDF**. `evidence show` no abre el blob, solo metadatos.
- ❌ **No descargan**. No hay red en V1.
- ❌ **No buscan**. No hay search en V1.
- ❌ **No editan metadatos in-place**. Cualquier corrección requiere ingesta de nueva versión derivada (V2+).
- ❌ **No exportan a otros formatos**. Solo texto humano y JSON.
- ❌ **No producen visualizaciones**. Solo CLI textual.
- ❌ **No interactúan con sources externas**. Sources se declaran al ingestar, no se "descubren" de algún servicio.
- ❌ **No ejecutan acciones masivas**. Sin batch ingest, sin glob expansion, sin --recursive. Un fichero por invocación de `ingest`.

Estas exclusiones son **comprometidas por ADR-0023**. Cualquier ampliación requiere ADR de enmienda.

---

## Resumen ejecutivo: contrato testeable

Los tests de integración (`tests/integration/demo_pipeline_test.py`) verifican esta especificación así:

| Paso del pipeline | Comando | Verificación |
|---|---|---|
| PDF → ingest | `aip evidence ingest twining-memo.pdf --source-id blue-book-nara --source-name "..." ...` | Exit 0, hash reportado = `EXPECTED_PDF_SHA256` |
| Recuperación | `aip evidence show sha256:<hash>` | Exit 0, output contiene campos canónicos |
| Verificación | `aip archive verify --full` | Exit 0, output contiene "Archive integrity verified" |
| Reproducibilidad | inspección del `archive_manifest_hash` | `archive_manifest_hash == EXPECTED_MANIFEST_HASH` (pinned en `tests/reproducibility/manifest_hash_test.py`) |

Si los cuatro pasos pasan en máquina limpia (Linux x86_64 referencia) con el fixture canónico, **F1 está cerrada**.

---

## Estado de este documento

- **Sintaxis de los tres comandos definida:** sí.
- **Inputs y outputs canónicos definidos:** sí (formato texto humano y formato JSON).
- **Errores tipados con códigos de salida definidos:** sí.
- **Comportamiento esperado paso a paso definido:** sí.
- **Ejemplos de uso definidos:** sí.
- **Contrato testeable derivable:** sí.

**Bloqueante para inicio de implementación F1:** ninguno. Esta especificación es el contrato.

Cualquier ambigüedad detectada durante la implementación se resuelve por PR contra este documento. Cambios sustantivos al contrato son ADR de enmienda, no edición silenciosa.
