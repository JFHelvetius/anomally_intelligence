# ADR-0017: Diseño de API

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0003, ADR-0010, ADR-0016, ADR-0019

---

## Contexto

El sistema necesita exponer su funcionalidad por al menos tres canales:

1. **CLI** — uso interactivo y scripting local.
2. **API Python** — uso embebido en notebooks, pipelines de investigación, código derivado.
3. **HTTP** — acceso remoto opcional para escenarios multi-usuario o integración con herramientas externas.

Diseñar APIs es elegir, una y otra vez, entre comodidad inmediata y costes posteriores. Una API mal diseñada se vuelve un pasivo que cualquier cambio en el modelo arrastra. ADR-0000 exige reproducibilidad y trazabilidad bit a bit; cualquier API debe preservarlas en su interfaz, no romperlas.

## Decisión

El sistema expone tres superficies API alineadas en semántica:

1. **API Python** (`aip` package) — es la **fuente de verdad** semántica. Toda funcionalidad del sistema vive aquí.
2. **CLI** (`aip` comando) — wrapper directo sobre la API Python, con la misma estructura de comandos.
3. **HTTP API** — capa **opcional**, no es prerrequisito de uso del sistema. Cuando se activa, expone un subconjunto de la API Python sobre HTTP siguiendo principios REST + cita estable de recursos.

Las tres superficies comparten:

- Mismos identificadores (`aip:` URIs, ADR-0016).
- Misma representación canónica de objetos.
- Misma semántica de versiones y snapshots.
- Mismas reglas de inmutabilidad y append-only.

Cuando hay conflicto entre comodidad y consistencia con el modelo, la consistencia gana.

## Especificación

### API Python: principios

```python
import aip

# Toda operación devuelve objetos tipados, nunca dicts opacos.
ev = aip.evidence.ingest("/path/to/document.pdf", source_id="src_blue_book")
print(ev.hash)        # ContentHash
print(ev.source.name) # str
print(ev.provenance)  # Provenance | None

# Los identificadores aip: son ciudadanos de primera clase.
case = aip.resolve("aip:case/01HZ4...@a3f9...")

# Consultas devuelven cursores/iteradores lazy sobre Parquet.
for claim in aip.claims.where(attributed_to="actor_jh1", scope="factual"):
    print(claim.predicate.natural_language)

# Mutaciones siempre son explícitas y trazables.
revision = case.revise(
    title="Updated abstract",
    transition_reason="editorial_only",
    authorized_by="actor_mod",
    rationale="Corrected typo in title.",
)
```

**Principios:**

- **Tipado fuerte**: `Evidence`, `Claim`, `Hypothesis`, etc. son tipos (dataclasses o equivalente) con validación al construir.
- **Sin global mutable**: el cliente toma un `Archive` handle. No hay singleton oculto. Tests y casos multi-archivo conviven sin colisión.
- **Iteradores lazy sobre datasets grandes**: queries devuelven cursores que se materializan a demanda.
- **Identificadores explícitos**: cualquier mutación lleva `authorized_by` obligatorio y opcionalmente `rationale`.

### CLI: principios

El CLI es delgado: cada comando llama a la API Python equivalente.

```
aip evidence ingest <path> --source-id <id> [--provenance <yaml>]
aip evidence show <hash>
aip evidence list [--source-id <id>] [--kind <kind>]

aip claim add --attributed-to <actor> --evidence <hash> --natural-language <text> ...
aip hypothesis-set create --case <case_id> --exhaustiveness representative
aip hypothesis add --set <set_id> --short-label "..." --family ...

aip case create --curator <actor> --title "..."
aip case revise <case_id> --transition <reason> --authorized-by <actor>

aip query "SELECT ..."        # DuckDB SQL directo sobre tables/
aip search text "..." [--kind ...]
aip search semantic "..."     # solo si vectorial está activado

aip snapshot create --tag <name>
aip snapshot export <id> --to <path>

aip archive verify             # comprueba todos los hashes
aip archive manifest            # imprime archive_manifest_hash
```

Todos los comandos aceptan `--archive-root <path>` para operar sobre un archivo distinto al default.

### HTTP API (opcional)

Estilo REST con dos características no negociables:

1. **Recursos identificados por URIs `aip:`** mapeados a paths HTTP con resolución estable.
2. **Cabecera `AIP-Archive-Manifest` obligatoria en respuestas**: el cliente sabe contra qué estado del archivo se construyó la respuesta.

```
GET  /v1/evidence/{hash}                  → 200 Evidence
GET  /v1/cases/{case_id}                  → 200 CaseRevision (latest published)
GET  /v1/cases/{case_id}/revisions/{hash} → 200 CaseRevision (specific)
GET  /v1/hypothesis-sets/{set_id}         → 200 HypothesisSet
GET  /v1/search?q=...&kind=...            → 200 SearchResults

POST /v1/evidence                         → 201 Evidence  (ingest local file via upload)
POST /v1/claims                           → 201 Claim
POST /v1/cases                            → 201 Case
POST /v1/cases/{id}/revisions             → 201 CaseRevision  (revise)

GET  /v1/archive/manifest                 → 200 ArchiveManifest
GET  /v1/health                           → 200 health info
```

Sin batch endpoints en V1: si necesitas cargar 1000 evidencias, usa la API Python o el CLI con scripting.

**Sin gRPC**, sin GraphQL en V1. Estas opciones quedan abiertas a ADR posterior si demanda real lo justifica.

### Versionado de API

`v1` en el path. Cambios incompatibles abren `v2` sin retirar `v1` durante un período documentado. Cambios compatibles (campos opcionales nuevos) viven en `v1`.

El versionado de la API es independiente del versionado del esquema del modelo. La API absorbe ciertos cambios menores del esquema sin saltar versión; cambios mayores del esquema disparan migración de versión de API y se documenta.

### Autenticación y autorización en HTTP

Cubierto por ADR-0019 (seguridad). Resumen:

- Sin auth por defecto en bind local (`127.0.0.1`).
- Auth obligatorio en bind no local: tokens generados con `aip auth issue` para cliente identificado.
- Sin OAuth ni single-sign-on en V1. Esos serían ADR posterior.

### Errores

Respuestas de error con estructura consistente:

```json
{
  "error": {
    "code": "evidence_not_found",
    "message": "No evidence with hash sha256:1f4a... in this archive.",
    "details": { ... }
  },
  "archive_manifest": "..."
}
```

Códigos de error son enumeración cerrada documentada. Sin códigos numéricos crípticos.

### Formato de respuesta

JSON por defecto. Cabecera `Accept: application/x-parquet` para descargas masivas (ej. tabla completa de claims de un caso). Otras codificaciones (CBOR, Arrow IPC) abiertas a ADR posterior.

### Streaming

Para resultados largos (millones de filas), el HTTP soporta streaming en NDJSON o Arrow IPC. La API Python ya es lazy nativamente.

### Idempotencia

Operaciones idempotentes (ingestar el mismo blob dos veces) devuelven el mismo recurso (el hash es la identidad). Sin necesidad de keys de idempotencia explícitas.

Operaciones no idempotentes (crear una `Claim` nueva) llevan opcionalmente un header `Idempotency-Key` que la implementación puede consumir para deduplicación a nivel de cliente.

### Compatibilidad de schema y wire format

La canonicalización JCS del ADR-0016 se aplica en cualquier respuesta HTTP que necesite ser hasheada (e.g., responses que el cliente quiere usar como input de un hash compuesto). Para responses no destinadas a hashearse, se usa JSON estándar.

### Documentación de API

Generada desde el código con OpenAPI 3.x para HTTP y typestubs para Python. Sin documentación manual divergente.

## Justificación

### Por qué API Python como fuente de verdad

La audiencia primaria del proyecto (investigadores académicos, periodistas, archivistas) usa Python para análisis. Hacer la API Python ciudadana de primera clase reduce fricción y previene el modo de fallo "el CLI hace algo y la API Python hace otra cosa distinta".

### Por qué CLI delgado sobre API Python

Si la CLI tiene lógica propia, divergen. Mantenerla delgada hace que un fix en la API arregle automáticamente la CLI.

### Por qué HTTP opcional

Local-first (P6) significa que el flujo principal no requiere HTTP. Forzar HTTP al usuario individual añade complejidad sin valor. Los escenarios multi-usuario son secundarios y son los que usan HTTP.

### Por qué REST y no GraphQL/gRPC

GraphQL y gRPC son atractivos pero introducen costes de tooling y aprendizaje que no se justifican en V1. REST con JSON cubre los flujos reales. Una migración futura es posible si demanda real lo exige.

### Por qué cabecera `AIP-Archive-Manifest`

Sin esto, dos llamadas a la misma URL en momentos distintos pueden devolver respuestas distintas sin pista. Con esto, el cliente puede comparar contra qué estado del archivo se construyó cada respuesta. Es prerrequisito de reproducibilidad sobre HTTP.

### Por qué sin OAuth en V1

OAuth añade complejidad de tooling enorme para escenarios que el proyecto no necesita inicialmente. Cuando lo necesite (federación con archivos institucionales, por ejemplo), un ADR posterior lo introduce.

## Consecuencias

**Positivas**
- API consistente entre superficies.
- Reproducibilidad explícita sobre HTTP gracias al manifest header.
- Sin lock-in de proveedor de API.
- Usuarios pueden ignorar HTTP completamente si no lo necesitan.

**Negativas**
- Mantener tres superficies tiene coste; mitigado por la delgadez del CLI y la opcionalidad del HTTP.
- Sin GraphQL/gRPC, ciertos clientes encuentran fricción para queries específicas.
- Sin batch endpoints HTTP; cargas grandes vía CLI o Python.

**Neutras**
- Documentación OpenAPI auto-generada exige disciplina en anotaciones.

## Alternativas consideradas

### A. GraphQL como única API
**Descripción:** GraphQL para todo.
**Razón de rechazo:** Complejidad alta. La API Python sigue siendo necesaria; GraphQL no la reemplaza. Coste no justificado en V1.

### B. gRPC con protobufs
**Descripción:** Binary protocol moderno.
**Razón de rechazo:** Excesivo para el caso. Sin demanda actual.

### C. Sin CLI, solo Python
**Descripción:** Reducir superficies.
**Razón de rechazo:** Operaciones administrativas (verify, snapshot) son naturalmente CLI.

### D. HTTP como prerrequisito
**Descripción:** Forzar a usuarios a levantar servidor.
**Razón de rechazo:** Choca con local-first single-user.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P3, P5, P6, P8.

**Cómo se alinean:**
- P6 (local-first): HTTP opcional, no obligatorio.
- P5 (reproducibilidad): `AIP-Archive-Manifest` header garantiza reproducibilidad sobre HTTP.
- P8 (documentación): OpenAPI + typestubs auto-generados.
- P2 (trazabilidad): cada mutación de la API exige `authorized_by`.

**Tensión:** Tres superficies vs. mantenimiento. Aceptada con mitigación de delgadez.

## Referencias

- OpenAPI Specification 3.x.
- RFC 7231 (HTTP semantics).
- Fielding, R. (2000). *Architectural Styles and the Design of Network-based Software Architectures.* (Dissertation REST.)
- Datasette (Simon Willison). Prior art en exposición de SQL sobre datasets locales.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
