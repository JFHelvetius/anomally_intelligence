# ADR-0011: Diseño del grafo de conocimiento

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0015, ADR-0018

---

## Contexto

Una de las capacidades distintivas del sistema (Fase 5 en ADR-0004) es cruzar entidades entre casos a lo largo de décadas: identificar que un testigo aparece en dos investigaciones independientes, que un mismo oficial militar firmó reportes de tres incidentes distintos, que un mismo lugar concentra observaciones a lo largo de cincuenta años, que dos casos comparten un patrón documental.

Esa capacidad requiere un grafo de conocimiento explícito. El grafo no es la base de datos del sistema; es una **vista** materializada y consultable sobre las entidades y relaciones derivadas del modelo de evidencia, claims, hipótesis y conclusiones.

Los grafos de conocimiento son fáciles de hacer mal: ontologías excesivas, vocabularios sin disciplina, inferencia automática que mezcla observación con conjetura, normalizaciones agresivas que pierden información. El reto es construir un grafo útil sin caer en esos modos.

## Decisión

El sistema mantiene un **grafo de conocimiento dirigido y tipado**, con vocabulario controlado y extensible solo por ADR, materializado sobre el almacenamiento local (ADR-0015) como vista derivada de las entidades primarias del modelo.

Propiedades del grafo:

1. **Sin auto-inferencia**. El grafo solo contiene aristas declaradas explícitamente por un actor identificado o derivadas de relaciones existentes en el modelo de datos. No hay reasoner automático que invente relaciones nuevas.
2. **Aristas con procedencia**. Cada arista lleva su origen (qué evidencia o qué actor la afirmó) y su confianza.
3. **Reconciliación de entidades controlada**. Fusionar dos nodos (afirmar que dos representaciones se refieren a la misma entidad real) es un evento explícito, reversible, con motivación.
4. **No es la verdad ontológica del mundo**. Es la mejor representación tipada del estado actual del archivo, sujeta a revisión.

El grafo se materializa sobre el almacenamiento canónico del sistema (Parquet/DuckDB, ADR-0015). No se adopta una base gráfica externa propietaria. Consultas se expresan en SQL extendido con operaciones de grafo (recursividad) o, opcionalmente, en un wrapper Cypher-like si la fase lo justifica.

## Modelo

### Nodos

Tipos canónicos. Cerrado, extensible solo por ADR.

| NodeType | Procedencia |
|----------|------------|
| `Evidence` | ADR-0006, directamente del modelo primario |
| `Claim` | ADR-0007 |
| `Hypothesis` | ADR-0008 |
| `Conclusion` | ADR-0009 |
| `Case` | ADR-0010 |
| `Source` | ADR-0005 |
| `Person` | Subtype de `Actor` |
| `Organization` | Subtype de `Actor` |
| `System` | Subtype de `Actor` — instrumento, modelo computacional |
| `Place` | Anclaje geoespacial (ADR-0013) |
| `Event` | Evento físico declarado, no asumido |
| `Document` | Subtype de `Evidence` por conveniencia de consulta |
| `Concept` | Términos del vocabulario controlado (ej. "objeto luminoso esférico", "reporte de radar civil") |

`Event` merece comentario aparte. ADR-0002 evita tomar el evento físico como raíz del modelo. Pero el grafo necesita un nodo "evento declarado" para conectar testigos, lugares y tiempos. La distinción operativa: un `Event` en el grafo es **lo que las afirmaciones del caso dicen que ocurrió**, no una asunción del sistema de que ocurrió. Su existencia en el grafo es vista derivada, no compromiso sustantivo.

### Aristas (Edge / Relationship)

```
Edge {
  id: EdgeId
  source: NodeId
  target: NodeId
  type: EdgeType                # ver enumeración
  attributes: dict              # atributos tipados
  declared_by: ActorId
  declared_at: timestamp
  basis: [EvidenceLinkId | ClaimRef | ConclusionId]
  confidence: KentLevel         # ADR-0009
  rationale: markdown
  supersedes: EdgeId?
  status: EdgeStatus            # active | superseded | disputed | retracted
  schema_version: SemVer
}
```

### EdgeType

Vocabulario controlado, ~40 tipos canónicos. Subconjunto representativo:

**Procedencia y derivación**
- `derived_from` (evidencia derivada de otra)
- `cites`
- `transcribes`
- `translates`
- `retracts`

**Afirmación y verificación**
- `attributed_to`
- `verifies`
- `contradicts`
- `corroborates`

**Hipótesis y evaluación**
- `evaluates_hypothesis`
- `supports_hypothesis`
- `refutes_hypothesis`
- `assumes`

**Casos y agregación**
- `included_in_case`
- `referenced_by_case`
- `case_supersedes`
- `case_disputes`

**Entidades del mundo**
- `witnessed_event`
- `recorded_event`
- `occurred_at_place`
- `occurred_at_time`
- `affiliated_with` (persona-organización)
- `present_at`
- `produced` (organización/persona produce documento)

**Reconciliación**
- `same_as_provisional` (dos nodos referidos como la misma entidad real, con confianza)
- `same_as_confirmed` (reconciliación con evidencia material)
- `disambiguates_from` (explícitamente declarar no-identidad entre dos nodos parecidos)

**Estructura conceptual**
- `instance_of` (un evento es instancia de un concepto)
- `broader_than` / `narrower_than` (relaciones jerárquicas entre conceptos)

Cualquier tipo adicional requiere ADR de enmienda.

### Atributos típicos de Edge

Algunas aristas llevan atributos tipados específicos:

- `occurred_at_time` lleva `temporal_anchor: TemporalAnchorId` (ADR-0012).
- `occurred_at_place` lleva `spatial_anchor: SpatialAnchorId` (ADR-0013).
- `same_as_provisional` lleva `reconciliation_method` y `evidence_for_identity`.
- `affiliated_with` lleva `role`, `period_start`, `period_end`.

### Reconciliación de entidades

Reconciliar (fusionar dos nodos como la misma entidad real) es **explícito, reversible y trazable**:

- `same_as_confirmed` se crea con evidencia material (registro civil, documentación oficial, fotografía con identificación cruzada).
- `same_as_provisional` se crea con razonamiento documentado pero sin evidencia material rotunda.
- `disambiguates_from` se crea cuando dos representaciones se afirman como distintas a pesar de parecerse (mismo nombre, mismo lugar, etc.).

El sistema **no fusiona automáticamente** nodos por similitud nominal. Eso es un origen clásico de errores en grafos de conocimiento del campo (dos "John Smith" colapsados en uno, dos lugares con el mismo topónimo confundidos).

### Vocabulario controlado de conceptos

Los `Concept` viven en un vocabulario controlado mantenido como artefacto del repositorio (`docs/vocabulary/`). El vocabulario:

- Es versionado.
- Es bilingüe en su primera fase (español/inglés).
- Distingue jerarquía (`broader_than` / `narrower_than`).
- Es extensible por ADR de vocabulario (más ligero que ADR técnico).
- Exporta a SKOS para interoperabilidad.

### Consulta del grafo

Tres formas:

1. **SQL recursivo sobre las tablas Parquet/DuckDB** — forma canónica.
2. **API de path-queries** — wrapper Pythonic para patrones comunes (vecinos a N saltos, caminos entre nodos, ciclos).
3. **Wrapper Cypher-like opcional** — si una fase posterior demuestra demanda. No es prerrequisito.

Cualquier consulta se ejecuta sobre un **snapshot del grafo en un momento dado**, no sobre la cabeza en evolución. Esto permite reproducibilidad: una query del 2027-04 sobre snapshot del 2027-03 devuelve siempre el mismo resultado.

## Justificación

### Por qué sin auto-inferencia

Los reasoners automáticos (OWL DL, etc.) producen relaciones que nadie afirmó explícitamente y que pueden ser falsas. P10 (no fabricación) lo prohíbe: el sistema no afirma lo que ningún actor afirmó. Las "inferencias" útiles se materializan como queries sobre el grafo, no como aristas nuevas insertadas por un razonador.

### Por qué reconciliación explícita

El modo de fallo característico de grafos del campo: fusionar entidades por nombre. Hace impracticable distinguir personas o lugares homónimos. La política `same_as_confirmed` / `same_as_provisional` con autoría y evidencia previene este modo.

### Por qué materializar sobre Parquet/DuckDB

Una base gráfica propietaria (Neo4j Enterprise, etc.) viola P6 (local-first), P7 (coste cercano a cero) y P5 (reproducibilidad si la base cambia). Una base gráfica embebida open source (Neo4j Community con limitaciones, MemGraph, RedisGraph) puede ser opción futura, pero requiere justificación adicional. DuckDB con SQL recursivo cubre los patrones reales del proyecto sin dependencia adicional.

### Por qué vocabulario controlado y no folksonomy

Una folksonomy crece sin control. Pierde la capacidad de pregunta tipo "todas las afirmaciones sobre fenómenos lumínicos esféricos" porque las etiquetas se atomizan. El control con extensibilidad documentada es el compromiso.

### Por qué `Event` como nodo a pesar de ADR-0002

ADR-0002 evita tomar el evento como **raíz del modelo de datos** (porque exigiría asumir que ocurrió). El grafo permite materializar `Event` como **nodo derivado** sin esa asunción: el `Event` agrega afirmaciones que dicen que algo ocurrió en T y P. Su existencia operativa en el grafo no es compromiso sustantivo del sistema.

## Consecuencias

**Positivas**
- Cruzar entidades entre casos es operativo desde Fase 5.
- Reconciliación trazable evita falsos colapsos.
- El grafo es vista derivada: regenerable desde el modelo primario sin pérdida.
- Sin dependencia de base gráfica propietaria.

**Negativas**
- SQL recursivo es menos ergonómico que Cypher para queries muy ramificadas. Aceptable: las queries habituales son alcanzables.
- Mantener vocabulario controlado requiere disciplina.
- Materializar el grafo tras cambios al modelo primario tiene coste.

**Neutras**
- Exportación a formatos académicos (RDF, JSON-LD) es opcional, no estructural.

## Alternativas consideradas

### A. Base gráfica nativa (Neo4j, MemGraph)
**Descripción:** Adoptar una base gráfica desde Fase 5.
**Razón de rechazo:** Dependencia externa que complica reproducibilidad y local-first. No descartada como evolución; necesita ADR de enmienda.

### B. Grafo RDF + reasoner OWL
**Descripción:** Modelo basado en triples con razonador semántico.
**Razón de rechazo:** Auto-inferencia viola P10. Vocabulario excesivamente burocrático para el caso de uso.

### C. Sin grafo dedicado: solo joins SQL
**Descripción:** Trabajar las relaciones siempre como joins sobre el modelo primario.
**Razón de rechazo:** Posible para queries simples; intratable para patrones de varios saltos. La materialización es necesaria.

### D. Folksonomy con etiquetas libres
**Descripción:** Sin vocabulario controlado.
**Razón de rechazo:** Pierde la consultabilidad meta del archivo.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P4, P5, P6, P7, P10.

**Cómo se alinean:**
- P10 (no fabricación): sin auto-inferencia, sin reasoner que invente.
- P5 (reproducibilidad): el grafo se regenera del modelo primario.
- P6 (local-first) y P7 (coste cercano a cero): materialización sobre storage local sin servicios externos.
- P4 (neutralidad): el vocabulario no privilegia hipótesis.

**Tensión:** Ergonomía de SQL recursivo vs. Cypher. Aceptada: la complejidad típica de las queries del campo es baja-media.

## Referencias

- W3C SKOS Reference. https://www.w3.org/TR/skos-reference/
- W3C PROV-O Recommendation.
- DuckDB documentation, recursive CTEs.
- Heath, T., & Bizer, C. (2011). *Linked Data: Evolving the Web into a Global Data Space.*
- Vrandečić, D., & Krötzsch, M. (2014). *Wikidata: A Free Collaborative Knowledgebase.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
