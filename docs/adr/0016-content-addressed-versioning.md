# ADR-0016: Versionado y direccionamiento por contenido

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0006, ADR-0010, ADR-0015

---

## Contexto

Múltiples ADRs anteriores referencian identidades por hash de contenido (`ContentHash` para evidencia, `RevisionHash` para revisiones de caso, manifiestos reproducibles, snapshots citables). Hace falta un ADR único que defina:

- Qué algoritmo de hash se usa, por qué, y cómo se prepara para migración.
- Cómo se canonicalizan estructuras antes de hashear.
- Cómo se versiona el esquema del sistema.
- Cómo se versiona el conjunto de datos como un todo.
- Cómo se cita un objeto del sistema en publicaciones académicas.

Sin esta unificación, el sistema acumula inconsistencias: tres formas distintas de hashear, cuatro formas distintas de citar, esquemas evolucionados sin trazabilidad.

## Decisión

El sistema adopta un esquema unificado de **direccionamiento por contenido** y **versionado** con cuatro componentes:

1. **Hash de blobs**: SHA-256 (canónico) + BLAKE3 (suplementario opcional para resistencia futura).
2. **Hash de objetos estructurados**: SHA-256 sobre **canonicalización JSON** determinista (RFC 8785 JCS).
3. **Versionado de esquema**: SemVer estricto sobre el schema-version del modelo. Migraciones documentadas y bidireccionales cuando posible.
4. **Cita estable**: URI con prefijo `aip:` que resuelve a artefacto + versión exacta del esquema + opcional snapshot del archivo.

## Especificación

### Algoritmo de hash para blobs

- **Canónico**: SHA-256, codificado hex minúsculas, longitud 64.
- **Suplementario**: BLAKE3, codificado hex minúsculas, longitud 64. Almacenado en `Evidence.intrinsic_metadata.blake3` si se computa.
- **Migración futura**: si SHA-256 se debilita criptográficamente, se introduce un ADR de migración que añade un tercer algoritmo como canónico. SHA-256 nunca se elimina; permanece como identidad histórica.

### Canonicalización JSON

Para hashear objetos estructurados (`CaseRevision`, manifiestos de snapshot, etc.) se aplica **RFC 8785 (JSON Canonicalization Scheme)** antes de hashear. JCS garantiza:

- Ordenación lexicográfica de claves.
- Normalización de números (sin trailing zeros).
- Codificación UTF-8 sin BOM.
- Escape consistente.

Sin JCS, dos JSON semánticamente idénticos pueden producir hashes distintos. JCS garantiza estabilidad.

### Esquema versionado

Cada tipo del modelo lleva `schema_version: SemVer` en su instancia. Esto permite que el sistema:

- Lea instancias de versiones anteriores sin migración inmediata.
- Documente migraciones explícitas entre versiones (`docs/schema-migrations/`).
- Cite la versión exacta del esquema en cualquier output reproducible.

**Política SemVer**:

- **Mayor**: cambio incompatible (un objeto v1 no puede interpretarse correctamente con código de v2 sin migración).
- **Menor**: adición opcional, hacia atrás compatible (campos nuevos opcionales).
- **Parche**: corrección de documentación, sin cambio de estructura.

Migraciones mayores deben ser **bidireccionales documentadas** salvo casos donde la pérdida de información es inevitable. Cuando es bidireccional, el sistema soporta lecturas de cualquier versión histórica sin pérdida.

### Versionado del archivo como conjunto

El archivo completo (instancia del sistema en un momento dado) se identifica por un **manifest hash** que se computa como hash JCS de:

```
ArchiveManifest {
  schema_version: SemVer
  software_version: SemVer       # versión del código AIP
  software_commit: GitRef        # commit exacto si aplica
  generated_at: timestamp
  tables: {table_name: TableManifest}    # hash de cada tabla Parquet en orden canónico
  blobs_root: ContentHash                # Merkle root de los CAOS blobs
  archives_root: ContentHash             # análogo para WARC y bundles
  notes: markdown?
}

TableManifest {
  partition_hashes: [ContentHash]    # ordenados por nombre de partición
  row_count: int
  schema_hash: ContentHash           # del schema Parquet
}
```

El `archive_manifest_hash` es el identificador estable del archivo en un momento dado. Citaciones académicas pueden anclarse a él.

### Cita estable: URI scheme `aip:`

Forma canónica:

```
aip:<resource_type>/<resource_id>[@<resource_version>][?archive=<archive_manifest_hash>]
```

Ejemplos:

| URI | Resuelve a |
|-----|------------|
| `aip:evidence/sha256:1f4a...` | Una evidencia por su hash |
| `aip:case/01H...` | Última revisión publicada del caso |
| `aip:case/01H...@a3f9...` | Revisión específica del caso |
| `aip:hypothesis/01J...` | Hipótesis por su ULID |
| `aip:conclusion/01K...@v2.1.0` | Conclusión con versión de esquema explícita |
| `aip:archive/<archive_manifest_hash>` | Estado del archivo completo |

El query string `archive=<archive_manifest_hash>` ancla la resolución al estado exacto del archivo, prerrequisito de reproducibilidad académica.

### ULIDs como identidad humana

Para entidades no derivadas de contenido (un `Hypothesis` es un acto creativo de un curador, no un hash de un blob), se usan **ULID** como identificadores estables:

- Ordenables temporalmente.
- 128 bits, colisión prácticamente imposible.
- Más legibles que UUID v4.

Los ULID se generan localmente sin coordinación central. Conflictos imposibles para todos los efectos prácticos.

### Validación de hashes al cargar

Cada lectura de blob valida el hash contra el nombre del fichero en CAOS. Si discrepa, el sistema rechaza la lectura con error explícito (no silencia ni intenta recuperar). Esto detecta corrupción de disco temprano.

### Snapshots citables

Un snapshot es:

1. Un directorio completo del archivo en un momento dado.
2. Con su `archive_manifest_hash` calculado y firmado opcionalmente.
3. Empaquetado en formato OCFL o BagIt para preservación.

Snapshots se exportan a almacenamiento de largo plazo (Zenodo, IPFS opcional, archivo nacional) con identidad `aip:archive/<hash>`.

### Migración de hash si se debilita SHA-256

Plan documentado:

1. Cuando comunidad criptográfica declare SHA-256 obsoleto para integridad, se lanza ADR de migración.
2. Sistema introduce algoritmo sucesor (BLAKE3, SHA-3-256, lo que aplique) como canónico nuevo.
3. SHA-256 permanece registrado como identidad histórica en cada objeto.
4. Nuevas ingestiones usan el algoritmo nuevo.
5. Históricos no se rehashean masivamente; se computa hash sucesor sobre los blobs y se almacena junto al SHA-256 histórico.

Esta política minimiza la disrupción y preserva la trazabilidad histórica.

## Justificación

### Por qué SHA-256

Estándar de facto, ampliamente soportado, todavía considerado seguro para integridad. La adopción universal es ventaja: cualquier herramienta verifica.

### Por qué BLAKE3 suplementario

BLAKE3 es más rápido y resistente a futuras debilidades. Almacenarlo desde el principio como opcional permite migración suave si se necesita.

### Por qué JCS (RFC 8785)

Es la forma estándar y testeable de canonicalización JSON. Existen implementaciones reference. Evita reinventar canonicalización (origen clásico de bugs).

### Por qué ULID

Mejor que UUIDv4 (ordenable). Mejor que IDs secuenciales (sin coordinación). Mejor que IDs derivados del contenido (no aplica a actos creativos).

### Por qué cita con scheme `aip:`

Un scheme propio permite resolución unificada en herramientas del proyecto y deja claro que la cita es a un objeto del sistema. No interfiere con URLs HTTP cuando se quiere también publicar la resolución HTTP.

## Consecuencias

**Positivas**
- Cualquier objeto del sistema es citable, reproducible, verificable.
- El esquema evoluciona sin romper material histórico.
- Snapshots permiten preservar el estado de razonamiento en un momento dado.
- Detección temprana de corrupción.

**Negativas**
- Canonicalización JCS añade coste computacional al hashear estructuras.
- ULIDs son menos legibles que IDs secuenciales humanos.
- Cualquier campo no canonicalizable (binarios embebidos no estándar) requiere manejo especial.

**Neutras**
- El scheme `aip:` necesita resolver: tooling propio + opcionalmente publicación HTTP.

## Alternativas consideradas

### A. Solo SHA-1
**Descripción:** Adopción de Git-like.
**Razón de rechazo:** SHA-1 ya está roto criptográficamente.

### B. Solo BLAKE3
**Descripción:** Más rápido.
**Razón de rechazo:** Soporte ecosistémico todavía menor que SHA-256. Aceptable como suplementario, no como canónico hoy.

### C. UUIDv4 para todo
**Descripción:** Estándar universal.
**Razón de rechazo:** No ordenable temporalmente, menos legible que ULID.

### D. Versionado solo del software, no del esquema
**Descripción:** Asumir que el esquema cambia con el software.
**Razón de rechazo:** Hace imposible leer histórico cuando el software cambia.

### E. Sin canonicalización JCS, hash directo
**Descripción:** Hashear el JSON tal como se serializa.
**Razón de rechazo:** Dos serializadores producen hashes distintos. Inviable.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P11.

**Cómo se alinean:**
- P2 (trazabilidad bit a bit): hash canónico de cada objeto.
- P5 (reproducibilidad): JCS + esquema versionado garantizan identidad bit a bit.
- P11 (inmutabilidad evidencia cruda): hash CAOS hace explícita la inmutabilidad.

**Tensión:** Migración de algoritmo de hash en horizonte de décadas. Plan documentado preventivamente.

## Referencias

- RFC 8785 (JSON Canonicalization Scheme).
- NIST FIPS 180-4 (SHA-256).
- BLAKE3 specification.
- ULID specification. https://github.com/ulid/spec
- OCFL specification.
- BagIt File Packaging Format (RFC 8493).
- Multihash specification (IPFS prior art).

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
