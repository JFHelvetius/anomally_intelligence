# ADR-0040: Investigation Justification Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0019, ADR-0023, ADR-0030, ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035, ADR-0036, ADR-0037, ADR-0038, ADR-0039

---

## Contexto

El estado actual produce **información derivada** pero **no produce derivaciones explícitas**. La cadena de artefactos que sostiene una conclusión existe estructuralmente en la composición tablas + grafo + assessments, pero no como artefacto verificable. ADR-0040 materializa esa cadena como objeto de primer nivel.

## Decisión

Introducir `src/aip/justification/`, capa derivada que produce un `InvestigationJustification`: cadena deductiva categorizada por rol, anclada a una conclusión existente (V1: assessment), construida **exclusivamente** mediante **lectura** de artefactos ya existentes y **traversal canónico** del grafo de ADR-0033.

**Propiedad central:**

> Investigation Justification **enumera estructuralmente** la cadena que existe en el archive entre una conclusión y sus dependencias. **No infiere. No clasifica. No pondera. No genera lenguaje libre.** Es lookup estructurado categorizado por rol epistémico.

## Modelo

```python
JUSTIFICATION_SCHEMA_VERSION: Final[str] = "1"
JUSTIFICATION_ENGINE_VERSION: Final[str] = "1.0.0"
JUSTIFICATION_METHOD_NAME: Final[str] = "deductive_chain_v1"

ALLOWED_ENTRY_ROLES: frozenset[str] = frozenset({
    "evidence", "source", "assessment", "provenance_step", "graph_node",
})
ALLOWED_ANCHOR_TYPES: frozenset[str] = frozenset({"assessment"})

@dataclass(frozen=True, order=True)
class ChainEntry:
    entry_role: str
    entry_identifier: str
    entry_hash: str          # SHA-256(f"{role}:{identifier}")

@dataclass(frozen=True)
class InvestigationJustification:
    justification_id: str
    conclusion_anchor_type: str
    conclusion_anchor_id: str
    conclusion_anchor_hash: str
    minimal_evidence: tuple[ChainEntry, ...]
    supporting_assessments: tuple[ChainEntry, ...]
    graph_nodes_used: tuple[ChainEntry, ...]
    intermediate_artifacts: tuple[ChainEntry, ...]
    provenance_chain: tuple[ChainEntry, ...]
    workspace_hash: str | None
    source_manifest_hash: str
    justification_engine_version: str
    justification_method_name: str
    justification_hash: str
    schema_version: str = JUSTIFICATION_SCHEMA_VERSION

@dataclass(frozen=True)
class JustificationDiff:
    justification_a_hash: str
    justification_b_hash: str
    added_entries: tuple[ChainEntry, ...]
    removed_entries: tuple[ChainEntry, ...]
    unchanged_entries: tuple[ChainEntry, ...]
    diff_hash: str
    schema_version: str = JUSTIFICATION_SCHEMA_VERSION
```

## Hashes encadenados

- `conclusion_anchor_hash`: SHA-256 del par `(anchor_type, anchor_id)`.
- `entry_hash`: SHA-256 de `f"{role}:{identifier}"`.
- `source_manifest_hash`: hash del `manifest.json` actual (mismo patrón ADR-0035/0036).
- `workspace_hash`: hash del workspace persistido si se proporciona scope.
- `justification_hash`: SHA-256 JCS del modelo excluyendo el propio campo.
- `diff_hash`: SHA-256 JCS del diff excluyendo el propio campo.

`verify_justification_hash(j)` y `verify_justification_diff(d)` son verificadores **offline**.

## Persistencia

`<archive>/justifications/<id>.json`. No entra en `V1_TABLES`, `compute_manifest`, ni `is_archive`. `archive_manifest_hash` invariante.

## CLI

```sh
aip justification build  --conclusion-anchor-type ASSESSMENT \
                          --conclusion-anchor-id ID \
                          --justification-id ID \
                          [--workspace-id ID] \
                          --archive PATH [--output PATH]

aip justification show   <justification_id> --archive PATH

aip justification verify <justification_file>

aip diff justifications  <a.json> <b.json> [--output PATH]
```

JSON canónico (`sort_keys=True`).

## Algoritmo del builder (sin nuevos motores)

1. Validar archive y leer `manifest.json` → `source_manifest_hash`.
2. Cargar workspace opcional → `workspace_hash`.
3. Leer fila del assessment anchor → `evidence_id`, `supporting_source_ids`.
4. Computar `conclusion_anchor_hash` = SHA-256(`f"assessment:{anchor_id}"`).
5. Leer fila del Evidence → `source_id`, `provenance` opcional.
6. Leer fila de Source y de Provenance + steps.
7. Construir grafo (ADR-0033) y resolver `get_dependency_chain` desde el nodo assessment.
8. Categorizar cada hallazgo en una de las 5 listas por `entry_role`.
9. Ordenar canónicamente cada lista.
10. Construir partial con `justification_hash="0"*64`, computar hash JCS exclude-self, devolver final.

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo bit-identical | mismo archive + mismo anchor + mismo workspace ⇒ misma justificación |
| G2 | Removibilidad sin huella | `archive/justifications/` periférico |
| G3 | No ejecuta motores productores | AST inspect rechaza imports a impact/context/timeline/snapshot/diff/ML/red |
| G4 | Verify offline | `verify_justification_hash` sin archive |
| G5 | Compatibilidad total | sin modificar ningún modelo previo; `schema_version` invariante |
| G6 | Sin interpretación | token guard sobre 30+ palabras prohibidas |
| G7 | Sin duplicación | sólo referencias por hash; cero payload |

## Componentes excluidos

Cero IA, LLM, NLP, embeddings, ML, clasificación automática, scoring probabilístico, confidence intervals, recomendaciones, heurísticas opacas, APIs externas, UI, dashboards, exportadores, alertas, observabilidad, telemetría. Cero floats, `Decimal`, `bytes`. Cero campos `severity`, `confidence`, `criticality`, `likelihood`, `probability`, `ranking`, `recommendation`, `suggested_action`, `causal_inference`, `important_*`, `relevant_*`, `dangerous`, `regression`, `improvement`, `better`, `worse`, `summary_text`, `report_text`.

## Alineación ADR-0000

P1 (categorización), P2 (provenance), P3 (incertidumbre explícita — el motor se niega a expresar confianza), P5 (reproducibilidad), P8 (documentación), P11 (inmutabilidad).

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
