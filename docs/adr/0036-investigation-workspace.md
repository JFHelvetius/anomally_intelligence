# ADR-0036: Investigation Workspace V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0017, ADR-0019, ADR-0023, ADR-0024, ADR-0030, ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035

---

## Contexto

El repositorio sabe **producir** resultados:

- ADR-0032 — assessments derivados.
- ADR-0033 — grafo de procedencia.
- ADR-0034 — análisis de impacto.
- ADR-0035 — context assembly.

Lo que no sabe es **representar la investigación reproducible** sobre esos resultados. Un operador que estudia una evidencia concreta hoy debe recordar mentalmente qué evidencias miró, qué assessments revisó, qué bundles consultó y en qué orden. La plataforma conserva los artefactos analíticos; no conserva el trabajo analítico realizado sobre ellos.

La pregunta operativa nueva:

> "¿Qué conjunto exacto de artefactos utilizó un investigador para estudiar una evidencia determinada y puedo reconstruir exactamente el mismo espacio de trabajo meses después?"

## Decisión

Introducir `src/aip/workspace/`, un **artefacto reproducible de investigación** que agrupa referencias verificables a artefactos existentes en un único JSON canónico, persistible y verificable offline.

**Propiedad central (ADR-0036 §propiedad central):**

> Investigation Workspace **agrega referencias** a artefactos existentes.
> **No ejecuta análisis nuevos.** **No modifica** a ADR-0032, ADR-0033, ADR-0034 ni ADR-0035. **No interpreta** resultados. **No genera** conclusiones.

El workspace es índice reproducible. **No copia datos**: toda información sigue viviendo en los artefactos originales.

## Modelo

### Constantes

```python
WORKSPACE_SCHEMA_VERSION: Final[str] = "1"
```

Versión del esquema del workspace. **Distinta** del `SCHEMA_VERSION` del proyecto (ADR-0016) porque su ciclo de vida es independiente: el workspace puede evolucionar sin tocar la canonicalización de evidencia.

### Taxonomía cerrada de tipos de referencia

```python
class ReferenceType(StrEnum):
    EVIDENCE = "evidence"
    ASSESSMENT = "assessment"
    IMPACT_ANALYSIS = "impact_analysis"
    CONTEXT_BUNDLE = "context_bundle"
```

Cuatro valores. **Cualquier otro valor en construcción lanza `ValueError`**.

### `WorkspaceReference`

```python
@dataclass(frozen=True, order=True)
class WorkspaceReference:
    reference_type: str
    identifier: str
    artifact_hash: str
```

Identidad: `(reference_type, identifier)`. **Nunca contiene payload** — sólo referencias.

`artifact_hash` es la huella canónica de la referencia: `SHA-256 hex(f"{reference_type}:{identifier}")`. Derivada **exclusivamente** de los strings de la referencia — **cero ejecución de motores analíticos**, cero acceso al archive. Esta es la condición que hace G3 (no ejecuta motores) verificable estructuralmente.

### `InvestigationWorkspace`

```python
@dataclass(frozen=True)
class InvestigationWorkspace:
    workspace_id: str
    title: str
    references: tuple[WorkspaceReference, ...]
    source_manifest_hash: str
    workspace_hash: str
    schema_version: str = WORKSPACE_SCHEMA_VERSION
```

`references` se mantiene **ordenada canónicamente** por `(reference_type, identifier)` y libre de duplicados. Construir un workspace con dos referencias `(reference_type, identifier)` idénticas lanza `ValueError` (G7 — sin duplicación de resultados).

## Hashes encadenados

Siguen el patrón ya establecido en ADR-0019 (`AuditEntry.entry_hash`) y ADR-0035 (`ContextBundle.context_bundle_hash`):

### `source_manifest_hash`

Hash del `ArchiveManifest` actualmente almacenado en `<archive>/manifest.json` al momento de la creación del workspace. Permite a un consumidor verificar que el estado del archive no ha cambiado desde que se creó el workspace.

### `workspace_hash`

SHA-256 hex sobre la canonicalización JCS del workspace **excluyendo** el propio campo `workspace_hash`. Self-referente y verificable offline:

```python
def verify_workspace_hash(workspace: InvestigationWorkspace) -> bool:
    return compute_workspace_hash(workspace) == workspace.workspace_hash
```

Verificable sin acceso al archive — es propiedad estructural del workspace.

## Persistencia

Los workspaces se persisten en `<archive>/workspaces/<workspace_id>.json` (un directorio nuevo bajo la raíz del archive). **No se introduce ninguna tabla nueva en `V1_TABLES`**, por tanto el `manifest_hash` del archive es invariante ante creaciones de workspaces. Test explícito lo confirma.

Adicionalmente `create` admite `--output PATH` para emitir una copia portable a cualquier ubicación (compartir, archivar, versionar fuera del archive).

`<archive>/workspaces/` no entra en `is_archive`, ni en `compute_manifest`, ni en `archive verify`. Es deliberadamente periférico: borrar el directorio entero **no altera** la integridad del archive (G2).

## Garantías arquitectónicas

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo bit-identical | `test_workspace_hash_is_deterministic_across_runs` |
| G2 | Removibilidad sin huella | `test_workspace_persistence_does_not_modify_archive_manifest` — `archive_manifest_hash` pre/post idéntico |
| G3 | No ejecuta motores analíticos | `test_workspace_imports_no_engines` (AST inspect — cero imports a `aip.graph`, `aip.impact`, `aip.context`, `aip.analysis`) + `artifact_hash` deriva de strings únicamente |
| G4 | Hash verificable offline | `verify_workspace_hash(workspace)` sin acceso al archive |
| G5 | Compatibilidad total | `schema_version` invariante; todos los pinned hashes existentes intactos |
| G6 | Sin interpretación | Test de tokens prohibidos análogo al de ADR-0034/0035 |
| G7 | Sin duplicación de resultados | El workspace contiene solo `(reference_type, identifier, artifact_hash)`; **cero payload de artefactos**. Test verifica que añadir duplicados lanza `ValueError`. |

## Componentes excluidos (verificable en código)

| Excluido | Materialización |
|---|---|
| Dashboards / HTML / PDF / CSV / export visual | Cero generadores de output binario; sólo JSON canónico |
| Timelines / scoring / ranking / recommendations | Cero campos de orden subjetivo; sólo orden léxico canónico |
| Workflow automation / collaboration / comments / annotations | Workspace inmutable post-creación; ningún campo de comentario |
| Labels automáticos / interpretación | `title` es input del operador, no derivado |
| ML / NLP / LLMs / embeddings / clustering / clasificación | Cero deps ML; AST inspect lo confirma |
| Ejecución de motores | Workspace nunca llama `analyze_removal_impact`, `assemble_context`, `build_graph`, etc. AST inspect lo confirma |

## CLI

Subgrupo `aip workspace` con tres subcomandos:

```sh
aip workspace create \
    --workspace-id <id> \
    --title "<title>" \
    [--evidence ID ...] \
    [--assessment ID ...] \
    [--impact ID ...] \
    [--context ID ...] \
    --archive PATH \
    [--output PATH]

aip workspace show <workspace-id> --archive PATH

aip workspace verify <workspace.json>
```

### `create`

- Requiere `--workspace-id`, `--title`, `--archive`.
- `--evidence/--assessment/--impact/--context` son repetibles. Sus identifiers se convierten en `WorkspaceReference`s con `reference_type` correspondiente.
- Persiste siempre en `<archive>/workspaces/<workspace-id>.json` (canónico). Adicionalmente en `--output PATH` si se proporciona.
- Salida a stdout: JSON canónico del workspace.

### `show`

- Requiere `<workspace-id>` posicional y `--archive PATH`.
- Lee de `<archive>/workspaces/<workspace-id>.json`.
- Salida a stdout: JSON canónico del workspace.
- Exit code 1 si el workspace no existe.

### `verify`

- Requiere `<path>` posicional a un workspace.json.
- Verifica `workspace_hash` recomputándolo offline.
- Exit code 0 si válido, 1 si hash inválido.
- **Sin acceso al archive** — verifica auto-consistencia del workspace.

Todas las salidas son JSON canónico (`sort_keys=True`, `ensure_ascii=False`, `indent=2`).

## Reglas de validación

- `workspace_id`: no vacío, ASCII safe `[A-Za-z0-9._-]+` (mismo regex que `assessment_id` en ADR-0032 §make_assessment_id).
- `title`: no vacío.
- `reference_type`: uno de los cuatro valores cerrados; otro valor → `ValueError`.
- `identifier`: no vacío.
- Duplicados `(reference_type, identifier)` en `references`: → `ValueError`.
- `source_manifest_hash`: SHA-256 hex (64 chars lowercase).
- `workspace_hash`: SHA-256 hex (64 chars lowercase).

## Reproducibilidad

Mismo archive + mismas referencias + mismo título + mismo workspace_id ⇒ mismo workspace **bit a bit**, incluyendo `workspace_hash`. Test `test_workspace_hash_is_deterministic_across_runs` lo verifica.

## Consecuencias

**Positivas**
- El operador puede compartir un workspace.json como artefacto independiente, verificable offline, sin filtrar contenido del archive.
- La cadena `source_manifest_hash` + `workspace_hash` da identidad doble: estado del archive cuando se creó + integridad estructural del workspace.
- Cierra el último gap entre "producir resultados" y "documentar investigaciones reproducibles" sin abrir la puerta a interpretación.

**Negativas**
- El workspace no captura el orden temporal de operaciones del investigador. Aceptado: ese sería metadato interpretativo (timestamp = información temporal); preservarlo requiere reloj inyectado y rompe el determinismo state-pure. Se descarta para V1.
- Las referencias son strings opacas — un workspace puede mencionar identifiers que ya no existen en el archive. Mitigado: `source_manifest_hash` actúa como tripwire. Si el operador quiere verificación contra archive, ejecuta `aip archive verify` + revisa `--archive` actual vs. `source_manifest_hash`.

**Neutras**
- Workspace persistence en `<archive>/workspaces/` añade un directorio nuevo sin tocar `V1_TABLES`. Confirmado bit a bit: `EXPECTED_DEMO_MANIFEST_HASH` invariante tras creaciones.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P5, P8, P11.

| Propiedad | Cómo se alinea |
|---|---|
| P1 (categorías separadas) | Taxonomía cerrada de 4 valores; ningún workspace mezcla categorías |
| P2 (trazabilidad) | `source_manifest_hash` ata el workspace al estado del archive |
| P5 (reproducibilidad) | Mismo input ⇒ mismo JSON byte a byte |
| P8 (documentación) | Honesty field `schema_version` + ADR explícito |
| P11 (inmutabilidad) | Workspace nunca modifica artefactos referenciados; archive verify pre/post bit-idéntico |

**Tensión nueva:** ninguna. ADR-0023 §congelación V1 se mantiene; ADR-0036 introduce metadatos investigativos, no nuevos dominios analíticos.

## Trigger de revisión

Este ADR se revisa si:

- Aparece necesidad de un nuevo `reference_type` (e.g., para futuros dominios diferidos como claims/hipótesis al levantar ADR-0007/0008).
- Se solicita que `verify` también valide referencias contra un archive vivo.
- Se solicita versionado de workspaces (workspace_v2 que añada campos), lo que requeriría bump de `WORKSPACE_SCHEMA_VERSION`.

## Referencias

- ADR-0019 (audit chain — `entry_hash` pattern aplicado a `workspace_hash`).
- ADR-0024 §formato canónico (determinismo bit a bit).
- ADR-0031 §estrategia de testing.
- ADR-0035 (Context Assembly — pattern de hashes encadenados y aggregation-only).
- `tests/unit/workspace/` — verificación operativa de G1–G7.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
