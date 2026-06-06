# Schema migrations

**Estado:** Aceptado · directorio inicializado vacío al cierre de `v0.1.0`.
**Fecha de creación:** 2026-06-06.
**ADRs que lo exigen:**
- [`ADR-0016 §"Esquema versionado"`](../adr/0016-content-addressed-versioning.md): "Migraciones documentadas y bidireccionales cuando posible" + "Migraciones mayores deben ser **bidireccionales documentadas** salvo casos donde la pérdida de información es inevitable" + ubicación canónica en `docs/schema-migrations/`.

---

## 1. Qué vive aquí

Este directorio contiene **un fichero markdown por migración** del esquema de datos lógico de AIP. La numeración es estricta y sin huecos: `0001-<slug>.md`, `0002-<slug>.md`, etc., siguiendo la misma convención que `docs/adr/`.

A fecha de `v0.1.0`, **no existen migraciones**. La versión inicial del esquema (`SCHEMA_VERSION = "0.1.0"` declarado en [`src/aip/_version.py`](../../src/aip/_version.py)) es el punto de partida sin migración previa.

Este README **no es una migración**. Es la plantilla y las reglas para escribir las que vengan.

## 2. Cuándo se escribe una migración

Una migración se escribe **exclusivamente cuando** `SCHEMA_VERSION` sube en sus componentes **mayor** o **menor** del SemVer (`X.Y.0` → `X.Y+1.0` o `X.Y.Z` → `X+1.0.0`).

Cambios de **parche** (`X.Y.Z` → `X.Y.Z+1`) **NO requieren migración** porque por definición no alteran la forma estructural del esquema. Son correcciones de documentación, mejoras de validador sin cambio de payload, o equivalentes ([`ADR-0016`](../adr/0016-content-addressed-versioning.md) §"Política SemVer").

Lo que **sí** dispara una migración:

- Añadir un campo a `Evidence`, `Source`, `Provenance`, `ProvenanceStep`, `AuthenticationAssessment`, o `AuditEntry`.
- Eliminar un campo (mayor, casi siempre).
- Cambiar el tipo o el formato de un campo existente (e.g., timestamp de ISO con segundos a ISO con milisegundos).
- Cambiar la canonicalización JCS de alguna estructura hasheada (mayor obligatoria — rompe pinned values).
- Cambiar el conjunto `V1_TABLES` de [`src/aip/storage/layout.py`](../../src/aip/storage/layout.py) (mayor — rompe `archive_manifest_hash`).
- Cambiar el conjunto de `EvidenceKind`, `EvidenceStatus`, `SourceKind`, `AuthorityLevel`, `StepKind`, `ActionKind`, `ResultKind` o `ActorKind` (menor si solo añade; mayor si renombra o elimina).
- Cambiar el algoritmo de hash canónico o el separador del CAOS.

Cualquier de estos disparadores requiere **también** ADR correspondiente al ADR fundacional que define el modelo afectado (ADR-0006 para evidencia, ADR-0005 para fuente/procedencia, etc.). Esta migración es el documento operativo del cambio; el ADR es el documento decisional. **Ambos** son obligatorios; este directorio no exime del ADR.

## 3. Formato canónico de un fichero de migración

Cada fichero tiene exactamente tres bloques: frontmatter YAML, narrativa, y procedimiento. La numeración del fichero es el orden lógico cronológico de la migración, no el calendario.

### 3.1 Frontmatter (obligatorio)

```yaml
---
migration_id: <NNNN-slug>           # mismo que el nombre del fichero sin .md
schema_version_from: <SemVer>       # SCHEMA_VERSION antes de la migración
schema_version_to: <SemVer>         # SCHEMA_VERSION después
semver_level: major | minor         # nunca patch
date: <YYYY-MM-DD>                  # fecha de aceptación
author: <handle>                    # mantenedor responsable (MAINTAINERS.md)
related_adr: <ADR-XXXX>             # ADR fundacional o de enmienda asociado
related_enmienda_adr: <ADR-YYYY>?   # opcional, si la migración la dispara una enmienda
reversibility: bidirectional | one_way
reversibility_rationale: <texto>    # obligatorio si one_way
affected_pinned_values:             # lista de pinned values que cambian
  - EXPECTED_DEMO_MANIFEST_HASH     # ejemplos; lista lo que aplique
  - EXPECTED_BOOTSTRAP_HASH
  - schema_hashes (todos)
affects_archive_manifest_hash: true | false
breaks_v0_1_0_reproducibility: true | false   # si es true, debe justificarse en §narrativa
---
```

### 3.2 Narrativa (obligatoria)

Cinco subsecciones, en este orden:

1. **Motivación.** Por qué la migración. Cita explícita al ADR que la dispara y la sección concreta del ADR.
2. **Cambio estructural.** Diff lógico del esquema antes vs. después. Tipos, defaults, validadores.
3. **Razón de reversibilidad declarada.** Si es `one_way`, qué información se pierde y por qué la pérdida es necesaria.
4. **Impacto sobre las cuatro garantías.** Provenance, evidence integrity, reproducibility, hash stability. Esta sección **no es opcional**; cada garantía tiene su línea explícita, marcada como `intacta`, `acotada`, o `rota` con explicación.
5. **Compatibilidad con archives `v0.1.0`.** Qué pasa cuando un mantenedor con un archive en el esquema viejo intenta operar con código del esquema nuevo. Default obligatorio: el código nuevo debe **leer** el archive viejo (sin migrar in-place) hasta que el operador ejecute la migración explícitamente.

### 3.3 Procedimiento (obligatorio)

Cuatro subsecciones:

1. **Pre-migración.** Qué debe verificar el operador antes de migrar (e.g., `aip archive verify` debe pasar; backup del archive recomendado).
2. **Migración en sí.** Comandos o pasos concretos. Si requiere un script auxiliar, vive en `scripts/migrate_<NNNN>.py` y se referencia desde aquí.
3. **Post-migración.** Cómo verificar que la migración fue exitosa. Habitualmente: `aip archive verify` post-migración, comprobación de que el nuevo `archive_manifest_hash` coincide con el valor declarado en `tests/reproducibility/`.
4. **Rollback** (si bidireccional). Comandos para revertir. Si la migración es one_way, esta subsección dice literal "No aplica: migración declarada one_way en frontmatter; rollback requiere restaurar backup pre-migración".

## 4. Metadatos obligatorios (resumen)

| Campo | Obligatorio | Validación de PR |
|---|---|---|
| `migration_id` | sí | coincide con nombre de fichero |
| `schema_version_from` / `schema_version_to` | sí | SemVer válido; `to` > `from`; el delta corresponde a `semver_level` |
| `semver_level` | sí | uno de `major` / `minor` |
| `date` | sí | ISO 8601 fecha |
| `author` | sí | handle activo en `MAINTAINERS.md` al momento del merge |
| `related_adr` | sí | apunta a ADR existente |
| `reversibility` | sí | `bidirectional` o `one_way` |
| `reversibility_rationale` | obligatorio si `one_way` | texto no vacío |
| `affected_pinned_values` | sí | lista (puede ser vacía si la migración no toca pinned) |
| `affects_archive_manifest_hash` | sí | booleano |
| `breaks_v0_1_0_reproducibility` | sí | booleano; si `true`, narrativa §4 lo justifica |

## 5. Expectativas de reproducibilidad

Las tres expectativas que un PR de migración debe satisfacer **simultáneamente**:

### 5.1 Bidireccionalidad cuando posible

Una migración bidireccional aplicada y luego revertida produce un archive **bit a bit idéntico** al original. Esto significa: mismo `archive_manifest_hash`, mismos hashes de blob, misma cadena de audit log. Cualquier desviación se trata como bug de la migración.

Una migración one_way debe demostrar en §narrativa que la pérdida es **inherente al cambio** (e.g., consolidación de dos campos en uno por una decisión de ADR), no consecuencia de descuido.

### 5.2 Pinned values actualizados en el mismo commit

Si la migración cambia cualquier valor en `tests/reproducibility/` (`EXPECTED_*`, `EXPECTED_DEMO_MANIFEST_HASH`, `EXPECTED_*_HASHES`, schema_hashes calculados), el commit que introduce la migración **también** actualiza los pinned values. No se permiten commits intermedios donde los pinned values y el código diverjan.

### 5.3 Test de migración obligatorio

Por cada migración se añade un test bajo `tests/reproducibility/migrations/test_<NNNN>_<slug>.py` que verifica:

- Aplicar la migración sobre un archive sintético en `schema_version_from` produce uno válido en `schema_version_to`.
- Si la migración es bidireccional: la composición forward + reverse produce un archive bit a bit idéntico al original.
- Los pinned values declarados en `affected_pinned_values` son los únicos que cambian.

El test entra en la misma PR que el fichero de migración. CI los ejecuta automáticamente.

## 6. Plantilla anotada (copiar y rellenar)

Crear un fichero nuevo con nombre `NNNN-<slug-kebab>.md` y contenido:

```markdown
---
migration_id: NNNN-<slug-kebab>
schema_version_from: X.Y.Z
schema_version_to: A.B.C
semver_level: minor          # o `major`
date: YYYY-MM-DD
author: @<handle>
related_adr: ADR-XXXX        # ADR fundacional del modelo afectado
related_enmienda_adr: null   # o ADR de enmienda si lo dispara una enmienda
reversibility: bidirectional # o `one_way`
reversibility_rationale:     # obligatorio si one_way; null en bidireccionales
affected_pinned_values: []   # lista de constantes en tests/reproducibility/
affects_archive_manifest_hash: true
breaks_v0_1_0_reproducibility: false
---

# Migración NNNN — <título corto humano>

## Motivación

<una a tres frases sobre por qué la migración existe; cita exacta del ADR
que la dispara, con sección>

## Cambio estructural

<diff lógico del modelo antes vs. después; tipos, defaults, validadores,
cardinalidad de enums>

## Razón de reversibilidad declarada

<si bidirectional: "Reversible sin pérdida porque ...". Si one_way:
"Pérdida inherente: <descripción>. La pérdida es necesaria porque <ADR>">

## Impacto sobre las cuatro garantías

- **Provenance:** intacta | acotada | rota — <una frase>
- **Evidence integrity:** intacta | acotada | rota — <una frase>
- **Reproducibility:** intacta | acotada | rota — <una frase>
- **Hash stability:** intacta | acotada | rota — <una frase>

Si cualquiera es `rota`, esta migración debe ir acompañada de ADR de
enmienda que justifique la ruptura.

## Compatibilidad con archives v0.1.0

<descripción de qué pasa si un archive viejo intenta abrirse con código
nuevo; comportamiento esperado del lector hacia atrás>

## Pre-migración

<lista de comprobaciones del operador>

## Migración

<comandos o pasos concretos; referencia a script si existe>

## Post-migración

<cómo verificar éxito; nuevo manifest hash esperado>

## Rollback

<comandos para revertir, o "No aplica: one_way">
```

## 7. Lo que este README NO hace

- ❌ **No** describe migraciones que aún no existen. A `v0.1.0` este directorio está vacío salvo este README.
- ❌ **No** fija un calendario de cambios de schema. El esquema se mueve cuando un ADR de enmienda lo justifica, no por agenda.
- ❌ **No** exime del ADR cuando la migración toca un modelo de [`ADR-0001`](../adr/0001-epistemic-category-separation.md) a [`ADR-0010`](../adr/0010-case-lifecycle.md). El ADR sigue siendo obligatorio.
- ❌ **No** garantiza retro-compatibilidad de archives a través de migraciones one_way. Una migración one_way bien documentada es **legítima**; el rollback bit a bit no es posible y eso se reconoce explícitamente.
- ❌ **No** sustituye `aip archive verify` como gate de integridad. Las migraciones se verifican con tests dedicados además del verify estándar.

## 8. Alineación con las cuatro garantías (de esta política, no de migraciones futuras)

Este README no toca ningún canonical value. Su impacto sobre las garantías de `v0.1.0`:

| Garantía | Estado |
|---|---|
| **Provenance** | **intacta** |
| **Evidence integrity** | **intacta** |
| **Reproducibility** | **intacta** |
| **Hash stability** | **intacta** |

El propósito del documento es **proteger** las cuatro garantías cuando llegue la primera migración real, no modificarlas hoy.

---

## Historial

| Fecha | Cambio | Schema vigente |
|---|---|---|
| 2026-06-06 | Inicialización del directorio con esta plantilla. Cero migraciones. | `0.1.0` |
