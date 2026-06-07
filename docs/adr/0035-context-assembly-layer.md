# ADR-0035: Context Assembly Layer V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0017, ADR-0023, ADR-0030, ADR-0031, ADR-0032, ADR-0033, ADR-0034

---

## Contexto

Con ADR-0032/0033/0034 el archive expone cinco superficies derivadas:

1. El slot embebido `Evidence.authentication` (estructural).
2. La tabla `authentication_assessments` con resultados de ADR-0032.
3. El grafo de procedencia de ADR-0033 (`build_graph`, `get_dependency_chain`, `get_reverse_dependencies`, `get_assessments_for_evidence`, `get_evidence_for_assessment`, `validate_graph_integrity`).
4. El motor de impacto de ADR-0034 (`analyze_removal_impact`).
5. Los comandos read-only que exponen los anteriores: `evidence show`, `archive verify`, `assess-authentication`, `list-assessments`, `graph show/explain-*`, `impact evidence/assessment`.

Cada consumidor externo (humano, API client, futuro agente explicativo) que necesite responder una pregunta operativa sobre una pieza de evidencia está hoy obligado a orquestar **al menos cuatro llamadas distintas** y reconciliar sus JSONs por su cuenta. Esa duplicación:

- Replica lógica de composición en cada cliente.
- Convierte cada actualización del modelo en N actualizaciones de cliente.
- Introduce ventanas de inconsistencia cuando los clientes capturan el estado en momentos distintos.

La pieza que falta para cerrar el ciclo de trazabilidad es una **capa de composición estable, determinista y removible** que entregue toda la información derivada en un único artefacto consumible.

## Decisión

Introducir `src/aip/context/`, un subpaquete derivado que **agrega** los resultados existentes de ADR-0032/0033/0034 en un único `ContextBundle` deterministra y removible.

**Esta es la propiedad arquitectónica central de ADR-0035:**

> **Context Assembly agrega resultados existentes; no ejecuta análisis nuevos ni reemplaza a ADR-0032, ADR-0033 ni ADR-0034.**

Si en algún momento futuro la capa de contexto necesitara producir información que no se pueda derivar componiendo los outputs canónicos de las capas anteriores, eso sería **bug arquitectónico** o **levantamiento implícito** de scope — ambos requieren ADR de enmienda explícita.

## Modelo

### Constantes

```python
ASSEMBLY_ENGINE_VERSION: Final[str] = "1.0.0"
ASSEMBLY_METHOD_NAME: Final[str] = "evidence_centric_v1"
```

### `ContextNode`

```python
@dataclass(frozen=True, order=True)
class ContextNode:
    distance_from_anchor: int
    node_type: str           # "evidence" | "source" | "assessment"
    node_id: str
```

Unidad de neighborhood. Misma forma estructural que `ImpactNode` de ADR-0034 (la BFS produce el mismo tipo de tuple), pero con etiqueta semántica distinta (`distance_from_anchor` vs. `distance_from_root`). Deliberadamente **no se reutiliza** `ImpactNode`: el bundle debe quedar legible sin importar nombres de la capa de impacto.

### `GraphNeighborhood`

```python
@dataclass(frozen=True)
class GraphNeighborhood:
    upstream: tuple[ContextNode, ...]    # outgoing closure (dependencies of anchor)
    downstream: tuple[ContextNode, ...]  # incoming closure (dependents of anchor)
```

Vista canónicamente ordenada del barrio del grafo alrededor del anchor. Reproduce los outputs de `get_dependency_chain` y `get_reverse_dependencies` de ADR-0033 con distancia añadida — sin re-ejecutar análisis, sólo recorriendo el grafo ya construido.

### `ContextBundle`

```python
@dataclass(frozen=True)
class ContextBundle:
    # Identidad del anchor
    anchor_node_kind: str            # NodeKind.value
    anchor_node_id: str

    # Datos del archive (referencias resueltas — agregación de ADR-0032 +
    # tablas de core)
    evidence: dict | None
    source: dict | None
    provenance: dict | None
    derived_assessments: tuple[dict, ...]

    # Proyección del grafo (agregación de ADR-0033)
    graph_neighborhood: GraphNeighborhood

    # Análisis de impacto (agregación de ADR-0034 sin re-ejecutar)
    impact_report: dict

    # Honesty fields (ADR-0035 §honesty)
    assembly_engine_version: str
    assembly_method_name: str
    schema_version: str

    # Hashes encadenados (recomendación explícita del usuario en aprobación)
    source_manifest_hash: str
    context_bundle_hash: str
```

`derived_assessments` se serializa con `model_dump(mode="json")` para que su contenido sea el mismo que produce `list-assessments` — agregación literal.

`impact_report` se serializa con `dataclasses.asdict(ImpactReport)` — exactamente el mismo payload que devuelve `aip impact evidence/assessment`.

`evidence`/`source`/`provenance` son los `model_dump(mode="json")` de las tablas correspondientes. No se reinterpretan; el bundle los expone como aparecen en el archive.

## Hashes encadenados

Los dos hashes nuevos forman una **cadena de trazabilidad** verificable sin reconstruir el bundle:

### `source_manifest_hash`

Hash del `ArchiveManifest` actualmente almacenado en `<root>/manifest.json` al momento del ensamble.

**Lectura:** parse `manifest.json` → `ArchiveManifest.model_validate(...)` → `.manifest_hash()`.

**Propiedad:** un consumidor que cacheó un bundle puede preguntar "¿el archive sigue en el mismo estado que cuando me dieron este bundle?" comparando `bundle.source_manifest_hash` con el manifest actual.

Como consecuencia directa de la decisión arquitectónica: para la demo canónica del Twining Memo + assessment con clocks canónicos, **`source_manifest_hash` coincide bit a bit con `EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH`** pinned en ADR-0032. Test reproducibility verifica esta invariante cross-ADR.

### `context_bundle_hash`

SHA-256 hex sobre la canonicalización JCS del bundle **excluyendo `context_bundle_hash`** (mismo patrón que `AuditEntry.entry_hash` en ADR-0019).

**Propiedad:** identidad bit-by-bit del bundle. Dos bundles producidos sobre el mismo archive tienen el mismo `context_bundle_hash`; modificar cualquier byte cambia el hash.

Función pública `verify_bundle_hash(bundle)` permite a cualquier consumidor recomputar y validar sin acceso al archive original.

## Función núcleo

```python
def assemble_context(
    archive_root: Path,
    anchor: GraphNode,
) -> ContextBundle:
    """Construye un ContextBundle determinista para `anchor`.

    Función pura del estado del archive. Sin reloj, sin aleatoriedad,
    sin estado global. Mismo archive + mismo anchor ⇒ mismo bundle
    bit a bit (incluido context_bundle_hash).
    """
```

Algoritmo (esqueleto):

1. Validar que `archive_root` es archive AIP válido.
2. Construir grafo (`build_graph`).
3. Validar que `anchor in graph.node_set()`.
4. Resolver evidencia relacionada al anchor (puede ser el mismo anchor, o derivarse vía aristas para anchors de tipo assessment / source).
5. Leer `evidence`, `source`, `provenance` de las tablas (sin recomputar nada — sólo lectura).
6. Listar assessments derivados que tocan al anchor (sin ejecutar `assess_authentication` — sólo lectura de la tabla ya persistida).
7. Computar `graph_neighborhood` vía BFS sobre `graph.edges` con tracking de distancia (la primitiva de BFS es similar a la de ADR-0034 §analyzer pero se aísla en `context/assembler.py` para no acoplar capas).
8. Computar `impact_report` con `analyze_removal_impact(graph, anchor)` (literalmente la función pública de ADR-0034 — agregación, no re-implementación).
9. Leer `manifest.json` y derivar `source_manifest_hash`.
10. Construir bundle parcial con `context_bundle_hash=""`.
11. Computar `context_bundle_hash` sobre la canonicalización JCS del bundle parcial (excluyendo el campo `context_bundle_hash`).
12. Devolver bundle final con el hash inyectado.

## Garantías arquitectónicas

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo bit a bit | `test_bundle_is_deterministic_across_runs` — same archive → identical bundle including `context_bundle_hash` |
| G2 | Removibilidad sin huella | `test_assembly_does_not_modify_archive` — pre/post snapshot bit a bit |
| G3 | **Agregación pura — no ejecuta análisis nuevos** | El assembler llama exclusivamente a funciones públicas de ADR-0032/0033/0034 + lecturas de tablas. Verificado por `test_assembler_only_uses_existing_engines` (inspecciona las dependencies del módulo) |
| G4 | Cadena de hashes verificable | `verify_bundle_hash(bundle)` + comparación con `source_manifest_hash` en el archive |
| G5 | No rompe compatibilidad | `schema_version` invariante. Comandos previos producen JSON byte-idéntico antes/después |
| G6 | Sin interpretación | Cero floats, cero scoring, cero narrativa. Test de tokens prohibidos análogo al de ADR-0034 |

## Componentes excluidos

| Excluido | Materialización |
|---|---|
| Ranking de evidencias o assessments | El bundle no ordena por "relevancia" — sólo canónicamente por id |
| Resumen ejecutivo / narrativa generada | El bundle expone datos crudos; no produce prosa |
| Recomendación de acciones | Cero campos `recommend_*` o `suggested_*` |
| Scoring de severidad | Mismos tokens prohibidos que ADR-0034 |
| Re-ejecución de análisis | El assembler **no** construye nuevos assessments ni nuevas aristas — sólo agrega outputs canónicos |
| Caché persistente del bundle | El bundle no se escribe a disco; cada llamada lo recomputa (G2) |
| Sincronización con servicios externos | Cero red, cero APIs externas |

## CLI

Subgrupo `aip context` con un único subcomando `show` que despacha por kind:

```sh
aip context show evidence   <evidence-id>    --archive PATH
aip context show assessment <assessment-id>  --archive PATH
```

`aip context show source` se omite del CLI público por simetría con `aip impact`. La API Python (`assemble_context(archive_root, GraphNode(kind=SOURCE, id=...))`) lo soporta sin cambios.

Salida JSON canónica (`sort_keys=True`, `ensure_ascii=False`, `indent=2`). Exit code 1 si el anchor no existe.

## Reproducibilidad

`tests/reproducibility/test_manifest_hash.py` pina un nuevo valor:

```python
EXPECTED_DEMO_CONTEXT_BUNDLE_HASH = "<sha256 hex>"
```

Producido por:

- Demo del Twining Memo ingestada con clock canónico.
- Assessment derivado con clock canónico, método `provenance_review`.
- Anchor = evidencia (= `EXPECTED_PDF_SHA256`).

Si este pin cambia, ha cambiado alguno de:

- La canonicalización JCS,
- El layout del bundle (campos, orden, tipos),
- El cuerpo de los modelos derivados de ADR-0032/0033/0034,
- O el contenido del fixture.

Cualquiera es bug arquitectónico crítico — PR explícito requerido.

Como invariante adicional, el test cross-ADR verifica:

```python
assert bundle.source_manifest_hash == EXPECTED_DEMO_ASSESSMENT_MANIFEST_HASH
```

— atando ADR-0035 directamente al pin de ADR-0032.

## Consecuencias

**Positivas**
- Clientes externos consumen un único artefacto canónico en lugar de orquestar 4+ calls.
- La cadena de hashes (`source_manifest_hash` + `context_bundle_hash`) elimina ambigüedades temporales: "¿este bundle es de qué estado del archive?" tiene respuesta verificable.
- Cierra coherentemente el ciclo "derive → expose" iniciado por ADR-0032: a partir de aquí el siguiente salto natural ya no es interno (exportadores, agentes opcionales).
- El principio "agregación pura, no re-ejecución" hace explícito que ADR-0032/0033/0034 siguen siendo las fuentes de verdad derivadas.

**Negativas**
- El bundle puede ser grande para archives grandes. V1 acepta el coste (los V1 son archives modestos por construcción); compactación o paginación se evaluarían en V2 si surge dolor real.
- Dos formas de leer la mayoría de los datos (vía comandos individuales o vía bundle) crean superficie redundante. Mitigado: el bundle reusa literalmente los outputs canónicos, así que no hay drift.

**Neutras**
- Sin cambios en `schema_version`. Sin tablas nuevas. Sin entradas nuevas al audit log. Sin nuevos pinned hashes para los manifests del archive.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P5, P8, P11.

| Propiedad | Cómo se alinea |
|---|---|
| P1 (separación) | El bundle preserva las cinco categorías; nunca colapsa una en otra |
| P2 (trazabilidad) | `source_manifest_hash` ata el bundle al estado verificable del archive |
| P5 (reproducibilidad) | Bundle byte-idéntico mismo archive ⇒ mismo bundle |
| P8 (documentación) | Honesty fields hacen explícito qué tipo de respuesta da el bundle |
| P11 (inmutabilidad) | Cero escrituras al archive; verify pre/post bit-idéntico |

**Tensión nueva:** ninguna. ADR-0023 §congelación V1 cubre el alcance; ADR-0035 es continuación lógica de la línea ADR-0032/0033/0034.

## Trigger de revisión

Este ADR se revisa si:

- Aparece necesidad documentada de incluir un nuevo campo en el bundle que **no** sea agregación de outputs canónicos existentes. Eso sería levantamiento de scope y requiere ADR específico.
- Surge presión por persistir bundles (caché en disco). Negocia G2 vs. coste.
- El bundle crece a un tamaño donde la paginación/streaming es necesaria.

## Referencias

- ADR-0032 (motor de assessments — proveedor).
- ADR-0033 (grafo derivado — proveedor).
- ADR-0034 (motor de impacto — proveedor).
- ADR-0019 (audit chain — pattern de `entry_hash` aplicado a `context_bundle_hash`).
- ADR-0024 §formato canónico (determinismo bit a bit).
- `tests/unit/context/` — verificación operativa de G1–G6.
- `tests/reproducibility/test_manifest_hash.py::test_demo_context_bundle_hash_is_canonical_pinned`.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
