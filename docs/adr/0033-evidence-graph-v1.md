# ADR-0033: Evidence Graph V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0005, ADR-0006, ADR-0011, ADR-0015, ADR-0017, ADR-0023, ADR-0024, ADR-0030, ADR-0031, ADR-0032

---

## Contexto

Con ADR-0032 el archive ya puede:

1. Ingestar evidencia inmutable direccionada por hash.
2. Persistir la `Source` de origen y la `Provenance` mínima.
3. Producir `AuthenticationAssessment` derivados con reglas booleanas explícitas.
4. Listar y mostrar tanto el slot embebido como los assessments derivados.

Lo que **no** puede aún es responder preguntas estructurales sobre la relación entre estos artefactos:

- ¿Qué evidencias respaldan una conclusión?
- ¿Qué conclusiones se derivaron de una evidencia concreta?
- ¿Qué cadena completa de procedencia existe detrás de un assessment?
- ¿Qué se rompería si se retirara una `Source`?

Estas preguntas son **inherentes al alcance epistémico de ADR-0000** (P1, P9, P11) y a la separación de categorías de ADR-0001. Hoy el operador puede deducir las respuestas leyendo manualmente las tablas; el archive debería poder responderlas directamente.

ADR-0011 (Knowledge Graph) reservó un dominio completo de grafo para fases posteriores con `aip.graph` como subpaquete. Ese ADR sigue diferido por ADR-0023. **Este ADR-0033 NO lo levanta**. ADR-0033 introduce una capa **deliberadamente más pobre**: un grafo de procedencia **derivado, sin persistencia propia, sin nuevas entidades, sin librerías externas**, construido únicamente a partir de los datos que el archive ya tiene.

Cualquier ampliación hacia el grafo de conocimiento "real" (entidades de personas, organizaciones, eventos, relaciones tipadas más allá de procedencia) sigue requiriendo levantamiento explícito de ADR-0011 vía ADR de enmienda. Este ADR-0033 cubre **estrictamente** procedencia entre tres tipos de nodo: `evidence`, `source`, `assessment`.

## Decisión

Introducir un **grafo de procedencia derivado** en `src/aip/graph/` que:

1. Se reconstruye **íntegramente** desde los contenidos del archive en cada invocación.
2. No introduce nuevas tablas, archivos, formatos ni `schema_version`.
3. No depende de librerías externas de grafo (networkx, igraph, neo4j, etc.).
4. Permite responder preguntas estructurales mediante una API Python y comandos CLI read-only.
5. Su salida es JSON canónico bit a bit reproducible.
6. Eliminar la salida (stdout) **nunca** modifica el archive — no hay nada que persistir.

El motor cumple **cinco garantías arquitectónicas declaradas** en el código y testeadas explícitamente:

| # | Garantía | Verificación |
|---|----------|--------------|
| G1 | No es una nueva fuente de verdad | El grafo es función pura del estado del archive |
| G2 | Es removible sin huella | No escribe ningún byte al archive (verify pre/post idéntico) |
| G3 | Es reproducible bit a bit | Mismo archive → mismo JSON, ordenamiento canónico explícito |
| G4 | No introduce dependencias externas | Sin networkx, sin grafos en disco, sin red, sin LLM |
| G5 | No rompe compatibilidad hacia atrás | `schema_version` invariante, comandos existentes intactos |

## Modelo del grafo

### Tipos de nodo (`NodeKind`)

| Valor | Origen | ID |
|---|---|---|
| `evidence` | fila en `tables/evidence/` | `Evidence.hash` (SHA-256 hex) |
| `source` | fila en `tables/sources/` | `Source.id` (cadena estable) |
| `assessment` | fila en `tables/authentication_assessments/` | `AuthenticationAssessment.assessment_id` |

Los nodos son `frozen=True` `dataclass` con campos `(kind, id)`. Comparables y hasheables — necesario para `set` y ordenamiento determinista.

**Regla:** un nodo aparece en el grafo si y sólo si existe la fila correspondiente. Nodos referenciados por aristas pero sin fila de respaldo (rotura de referencia) **no aparecen como nodo**; la arista persiste con destino "colgante" y el validador de integridad reporta el incidente. Esto preserva una propiedad clave: `len(graph.nodes) == count_rows(evidence) + count_rows(sources) + count_rows(authentication_assessments)`.

### Tipos de arista (`EdgeKind`)

| Valor | Dirección | Significado |
|---|---|---|
| `sourced_from` | `evidence → source` | La evidencia declara su fuente de origen vía `Evidence.source_id` |
| `assessed_from` | `assessment → evidence` | El assessment se construyó sobre esta evidencia (`AuthenticationAssessment.evidence_id`) |
| `derived_from` | `assessment → source` | El assessment cita esta fuente como respaldo (`AuthenticationAssessment.supporting_source_ids[*]`) |

Las aristas son `frozen=True` `dataclass` con campos `(kind, src, dst)`. La dirección es semánticamente "depende de": ir hacia adelante (outgoing) sigue dependencias; ir hacia atrás (incoming) sigue reverse-dependencies.

### Estructura agregada

```python
@dataclass(frozen=True)
class EvidenceGraph:
    nodes: tuple[GraphNode, ...]   # ordenado por (kind.value, id)
    edges: tuple[GraphEdge, ...]   # ordenado por (kind.value, src..., dst...)
```

Ambos campos son tuplas inmutables. El ordenamiento es canónico explícito, no dependiente del filesystem ni del orden de inserción.

## Determinismo

| Fuente potencial de no-determinismo | Decisión arquitectónica |
|---|---|
| Orden de filesystem (`iterdir`) | Builder usa `sorted()` sobre cada nivel; lectura ya determinista vía `tables.iter_rows` |
| Orden de inserción en `set` | Conversión a tupla siempre vía `sorted(..., key=canonical_key)` |
| Diccionarios al serializar JSON | `json.dumps(..., sort_keys=True)` en CLI |
| Reloj de pared | **No se usa**: el grafo no incluye timestamps |
| Aleatoriedad | **No se usa** |
| Estado global mutable | **No se usa**: el builder es función pura sobre `archive_root` |

Reproducibilidad bit a bit garantizada: dos invocaciones consecutivas sobre el mismo archive producen el mismo `EvidenceGraph` y el mismo JSON.

## Garantía de removibilidad (G2)

El grafo **no se persiste**. No hay `tables/graph/`, no hay `graph.json` en disco, no hay caché. Cada `aip graph show` recomputa.

Eso significa:

- Borrar la salida JSON (stdout, pipe, fichero externo) es matemáticamente equivalente a no haber corrido el comando.
- No hay manifest a actualizar ni audit entries que añadir — coherente con la decisión de ADR-0032 §rationale.
- Verificable empíricamente: `verify` antes del `graph show` y `verify` después son bit-idénticos, incluyendo el `manifest_hash`.

## Componentes excluidos explícitamente

| Excluido | Razón |
|---|---|
| Librerías externas de grafo (networkx, igraph, graphviz, etc.) | Dependencia + superficie de ataque + complejidad innecesaria para V1 |
| Persistencia del grafo (tabla nueva, snapshot, caché) | Convertiría al grafo en una nueva fuente de verdad, violando G1 |
| Base de datos de grafo (neo4j, dgraph, etc.) | Idem + violación de ADR-0003 (local-first) y ADR-0007 (coste cercano a cero) |
| Red (consultas a servicios externos) | ADR-0003, ADR-0014 (OSINT diferido) |
| Inferencia con IA o ML | ADR-0021 + ADR-0032 §exclusiones aplicables aquí también |
| Nuevos `NodeKind` (persona, organización, evento, claim, hipótesis) | ADR-0011 diferido por ADR-0023; cualquier expansión requiere su ADR específico |
| Aristas con peso o probabilidad | ADR-0032 §G2 (no scoring continuo) — la procedencia se declara o no se declara |

## API Python

### Construcción

```python
from aip.graph import build_graph
from pathlib import Path

graph = build_graph(Path("/path/to/archive"))
# graph.nodes — tupla ordenada canónicamente
# graph.edges — tupla ordenada canónicamente
```

### Queries

```python
from aip.graph.query import (
    get_assessments_for_evidence,    # evidence_id → tuple[GraphNode (assessment), ...]
    get_evidence_for_assessment,      # assessment_id → GraphNode | None
    get_dependency_chain,             # node → tuple (outgoing transitive closure)
    get_reverse_dependencies,         # node → tuple (incoming transitive closure)
    validate_graph_integrity,         # graph → tuple[GraphIntegrityIssue, ...]
)
```

Todas las funciones devuelven resultados ordenados canónicamente. `validate_graph_integrity` devuelve los problemas detectados (aristas con extremos que no son nodos del grafo); tupla vacía = grafo íntegro.

## CLI

Tres subcomandos bajo el grupo `aip graph`:

```sh
aip graph show              --archive PATH
aip graph explain-assessment --archive PATH --assessment-id ID
aip graph explain-evidence   --archive PATH --evidence-id ID
```

Todas las invocaciones:

- **Read-only**: no modifican el archive.
- **JSON only**: sin variante humana; el grafo es para consumo programático o auditoría programable.
- **UTF-8 sin BOM**, `sort_keys=True`, `indent=2`, `ensure_ascii=False`.
- **Estables**: mismo archive → mismo output byte a byte.

### `aip graph show`

Devuelve el grafo completo más conteos por tipo y reporte de integridad.

### `aip graph explain-assessment`

Para un `assessment_id` concreto, expone:

- Nodo de assessment.
- Nodo de evidencia referenciada (vía `assessed_from`).
- Cadena de dependencias hacia adelante (transitive closure desde el assessment).
- `exists: false` + `rc != 0` si el assessment no aparece en el grafo.

### `aip graph explain-evidence`

Para un `evidence_id` concreto, expone:

- Nodo de evidencia.
- Cadena hacia adelante (la fuente).
- Reverse-dependencies (qué assessments dependen de esta evidencia).
- `exists: false` + `rc != 0` si la evidencia no aparece en el grafo.

## Consecuencias

**Positivas**
- El archive puede explicar la procedencia detrás de cada conclusión.
- Eliminar una `Source` es **observable** estructuralmente: `validate_graph_integrity` lo reporta inmediatamente.
- Capa nueva 100% testeable: builder es función pura, queries son funciones puras, CLI es adapter delgado.
- Materializa la separación P1/P11 de ADR-0000 sin nuevas piezas de verdad.

**Negativas**
- Coste de recomputo por cada llamada CLI. Aceptable en V1 (tablas pequeñas).
- No es ADR-0011 — el "grafo de conocimiento" real con personas, organizaciones, eventos, etc., sigue diferido. Un lector externo podría confundir uno con otro; mitigado con naming `evidence graph` y este ADR.

**Neutras**
- No cambia ningún hash canónico pinned. No cambia `schema_version`. No cambia comportamiento de comandos existentes.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P8, P11.

| Propiedad | Cómo se alinea |
|---|---|
| P1 (categorías separadas) | El grafo materializa la separación: cada nodo tiene tipo cerrado, cada arista tipo cerrado |
| P2 (trazabilidad bit a bit) | Determinismo garantizado; el grafo es función pura del archive |
| P3 (incertidumbre explícita) | El `EdgeKind.derived_from` documenta qué fuentes respaldan qué assessment sin scoring |
| P5 (reproducibilidad) | Mismo archive → mismo JSON byte a byte |
| P8 (documentación al nivel del código) | Este ADR documenta la decisión completa |
| P11 (inmutabilidad de evidencia) | El grafo nunca modifica evidencia; verify pre/post idéntico |

**Tensión nueva:** ninguna. ADR-0011 (Knowledge Graph) sigue diferido.

## Trigger de revisión

Este ADR se revisa si:

- Se necesita un nuevo `NodeKind` (e.g., al levantar ADR-0007 Claim) — entonces enmienda al pie aquí + ADR del nuevo dominio.
- Se necesita persistencia del grafo (caché por performance) — entonces ADR específico que negocie G2 vs. coste.
- Un colaborador externo plantea que las queries V1 son insuficientes con caso de uso concreto.

## Referencias

- ADR-0011 (Knowledge Graph diferido — este ADR NO lo levanta).
- ADR-0024 §formato canónico vs. motor (determinismo bit a bit).
- ADR-0031 §estrategia de testing (T3 reproducibility, T1 unit).
- ADR-0032 (motor de assessments — este ADR construye encima).
- `tests/unit/graph/` — verificación operativa de G1–G5.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
