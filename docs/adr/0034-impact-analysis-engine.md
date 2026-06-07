# ADR-0034: Impact Analysis Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0023, ADR-0030, ADR-0031, ADR-0032, ADR-0033

---

## Contexto

ADR-0033 entregó un grafo de procedencia derivado capaz de responder preguntas estructurales: qué evidencia respalda un assessment, qué assessments dependen de una evidencia, etc. Lo que sigue faltando es una pregunta operativa concreta:

> "Si esta evidencia deja de estar disponible, ¿qué conclusiones derivadas se ven afectadas?"

Sin levantar ADR-0021 (asistencia LLM), sin introducir scoring, sin probabilidades, sin reasoning bayesiano, sin recomendaciones automatizadas.

La respuesta es matemáticamente sencilla: **cierre transitivo de reverse-dependencies en el grafo**. Es exactamente la primitiva que `aip.graph.query.get_reverse_dependencies` ya ofrece. ADR-0034 envuelve esa primitiva con un reporte estructurado, métricas observables (no interpretativas) y dos comandos CLI dedicados.

## Decisión

Introducir `src/aip/impact/`, un subpaquete derivado de **una sola operación**: análisis de reachability inversa desde un nodo raíz. Sin AI, sin scoring, sin severidad, sin probabilidad, sin recomendaciones. Cinco métricas observables; ninguna interpretación.

El motor responde **exclusivamente** cuatro preguntas declaradas en el spec:

1. ¿Qué assessments se vuelven sin respaldo? — campo `affected_assessments`.
2. ¿Qué evidencia derivada queda inalcanzable? — campo `affected_evidence`.
3. ¿Cuán profunda es la propagación? — campo `dependency_depth_max`.
4. ¿Cuántos nodos están afectados? — campo `total_affected_nodes`.

Nada más. No declara severidad, riesgo, criticidad, probabilidad ni recomendaciones.

## Modelo

### `ImpactNode`

```python
@dataclass(frozen=True, order=True)
class ImpactNode:
    node_id: str
    node_type: str         # "evidence" | "source" | "assessment"
    distance_from_root: int
```

Unidad de traversal. Frozen + ordenable canónicamente por `(distance_from_root, node_type, node_id)`. El `node_type` se materializa como la cadena del `NodeKind.value` correspondiente (no como el enum) para que el modelo sea autónomo de `aip.graph` cuando se serializa.

### `ImpactReport`

```python
@dataclass(frozen=True)
class ImpactReport:
    root_node_id: str
    affected_assessments: list[str]    # canónicamente sorted
    affected_evidence: list[str]       # canónicamente sorted
    dependency_depth_max: int
    total_affected_nodes: int
    analysis_engine_version: str       # IMPACT_ENGINE_VERSION
    schema_version: str                # SCHEMA_VERSION del proyecto
    analysis_method_name: str = "dependency_reachability_v1"
```

Honesty fields (`analysis_engine_version`, `schema_version`, `analysis_method_name`) hacen explícito **qué tipo de respuesta** está dando el motor. No hay otros campos interpretativos.

`affected_assessments` y `affected_evidence` son sólo las IDs como cadenas. Los detalles estructurales (distance, etc.) viven en una vista paralela vía `report_to_nodes(report)` para consumidores que necesitan más, sin contaminar el contrato mínimo.

## Función núcleo

```python
def analyze_removal_impact(
    graph: EvidenceGraph,
    root_node: GraphNode,
) -> ImpactReport:
    """Calcula el cierre transitivo de reverse-dependencies de ``root_node``.

    Determinista. Sin reloj, sin aleatoriedad, sin estado global.
    El root_node debe existir en ``graph.nodes``; en caso contrario
    lanza ImpactRootNotInGraphError.
    """
```

Algoritmo: BFS sobre aristas `dst == current_frontier`, expandiendo hacia `src`. Cada nodo recibe su distancia mínima desde la raíz (la primera vez que se descubre). El nodo raíz **se excluye** del conjunto resultante por convención (un nodo no es dependiente de sí mismo).

## Garantías arquitectónicas

| # | Garantía | Verificación |
|---|----------|--------------|
| G1 | Determinismo bit a bit | Mismo grafo + mismo root → mismo `ImpactReport`. BFS sobre tupla canónicamente ordenada de aristas. |
| G2 | Reproducibilidad cross-platform | Cero filesystem, cero reloj, cero entorno. |
| G3 | Removibilidad sin huella | `aip.impact` no escribe al archive. `archive verify` antes/después es bit-idéntico. |
| G4 | Solo reachability | El reporte tiene cinco enteros/cadenas más dos listas; cero floats, cero enums de severidad, cero campos derivados de modelos probabilísticos. |
| G5 | No rompe compatibilidad | `schema_version` invariante. Comandos existentes producen salida idéntica. |

## Componentes excluidos (verificable en código)

| Excluido | Materialización |
|---|---|
| Confidence scoring | Cero floats en `ImpactReport`/`ImpactNode`. Cero `Decimal`. |
| Severity scoring | Cero campos `severity`/`risk`/`criticality`. |
| Probabilidad / likelihood | Cero `probability`/`likelihood`/`p_*`. |
| Bayesian reasoning | Cero `prior`/`posterior`/`evidence_weight`. |
| Recomendaciones | Cero `recommend_*`/`suggested_*`/`action_*`. |
| Causal inference | Cero `cause`/`effect_size`. |
| Automated decision support | Cero ramificaciones que recomienden acción. |
| Lenguaje cargado | Cero ocurrencias de "critical", "dangerous", "important", "high-risk", "likely" en `src/aip/impact/*.py`. Test explícito lo verifica. |

## CLI

Dos subcomandos bajo el grupo `aip impact`:

```sh
aip impact evidence   <evidence-id>   --archive PATH
aip impact assessment <assessment-id> --archive PATH
```

Salida JSON canónica (`sort_keys=True`, `ensure_ascii=False`, `indent=2`):

```json
{
  "ok": true,
  "action": "impact_evidence",
  "archive_root": "...",
  "evidence_id": "...",
  "exists": true,
  "report": {
    "root_node_id": "...",
    "affected_assessments": ["..."],
    "affected_evidence": [],
    "dependency_depth_max": 1,
    "total_affected_nodes": 1,
    "analysis_engine_version": "1.0.0",
    "schema_version": "0.1.0",
    "analysis_method_name": "dependency_reachability_v1"
  }
}
```

Cuando el root no existe en el grafo:

```json
{
  "ok": false,
  "action": "impact_evidence",
  "archive_root": "...",
  "evidence_id": "...",
  "exists": false,
  "report": null
}
```

Exit code 1 en ese caso (consistente con `aip evidence show` no encontrado).

`aip impact source <source-id>` se omite **deliberadamente** del CLI público. Las sources son inputs, no derivadas; preguntar por su impacto downstream es operativo válido pero se puede hacer vía la API Python directa o vía `aip graph explain-evidence` para cada evidencia. Si en el futuro hay demanda externa documentada, se añade vía enmienda. Por ahora, el spec del usuario es explícito sobre dos comandos.

## Reproducibilidad

Mismo archive + mismo grafo + mismo root ⇒ mismo `ImpactReport`. Como el grafo subyacente es determinista (ADR-0033 §G3), el impacto también lo es por composición.

`IMPACT_ENGINE_VERSION` se versiona SemVer (inicial: `"1.0.0"`). Un cambio en este string es señal explícita de que la regla puede haber evolucionado; cualquier pinning futuro de `ImpactReport` debe revisarse en la misma PR que cambie esta constante.

No se pinea un `EXPECTED_IMPACT_REPORT_HASH` canónico en V1 por una razón pragmática: el reporte incluye `analysis_engine_version`, y pinear obligaría a actualizar el hash cada vez que la constante cambie, sin valor añadido. La determinabilidad bit a bit se verifica vía `test_impact_report_is_deterministic_across_runs`.

## Consecuencias

**Positivas**
- El archive puede responder "¿qué se vuelve sin respaldo si esto desaparece?" sin abrir la puerta a scoring.
- Materializa la honestidad epistémica de ADR-0000 §P3 (incertidumbre como first-class): el reporte no inventa severidad cuando sólo tiene reachability.
- Test explícito de ausencia de lenguaje prohibido convierte una promesa documental en una promesa de gate.

**Negativas**
- `aip impact assessment` casi siempre devuelve reporte vacío en V1 (nada depende de assessments). Aceptado: la simetría del comando se justificará cuando `aip.claim` (ADR-0007 diferido) entre en alcance.
- Sin scoring, un operador externo puede leer "1 assessment afectado" como "trivial". El motor declara explícitamente vía `analysis_method_name` que sólo está midiendo reachability, no importancia.

**Neutras**
- No cambia `schema_version`. No cambia ningún hash pinned. No añade tablas. No añade entradas al audit log.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P3, P5, P8, P11.

| Propiedad | Cómo se alinea |
|---|---|
| P1 (categorías separadas) | El motor opera sobre nodos tipados; nunca colapsa evidencia y assessment en una categoría compuesta |
| P3 (incertidumbre explícita) | El reporte se queda donde puede ser honesto: reachability. Lo que no puede medir (importancia subjetiva), no lo finge |
| P5 (reproducibilidad) | Mismo grafo + mismo root → mismo reporte byte a byte |
| P8 (documentación) | Este ADR + `analysis_method_name` en cada reporte hacen explícito qué tipo de respuesta se está dando |
| P11 (inmutabilidad) | El motor sólo lee; el archive es invariante |

## Trigger de revisión

Este ADR se revisa si:

- Se solicita explícitamente algún tipo de scoring (entonces el spec habría que negociar contra G4 y ADR-0000 §P3).
- Aparece un nuevo `NodeKind` (e.g., al levantar ADR-0007 Claim) — el motor lo absorbe automáticamente vía el grafo, pero el CLI puede necesitar un nuevo subcomando.
- `aip impact source` se justifica con un caso de uso externo documentado.

## Referencias

- ADR-0033 (Evidence Graph V1 — sustrato).
- ADR-0024 §formato canónico (determinismo bit a bit).
- ADR-0031 §estrategia de testing (T3 reproducibility, T1 unit).
- `tests/unit/impact/` — verificación operativa de G1–G5 y de ausencia de componentes prohibidos.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
