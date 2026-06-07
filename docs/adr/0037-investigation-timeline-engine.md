# ADR-0037: Investigation Timeline Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0023, ADR-0030, ADR-0031, ADR-0032, ADR-0036

---

## Contexto

ADR-0036 introdujo el `InvestigationWorkspace`: índice reproducible de referencias a artefactos derivados. Lo que no entrega es la **vista temporal** de esos artefactos.

Pregunta operativa nueva:

> "Dada una colección de artefactos asociada a una investigación, ¿en qué orden cronológico fueron observados los que tienen marca temporal nativa en el archive?"

## Decisión

Introducir `src/aip/timeline/`, capa derivada que reconstruye una **vista cronológica ordenada** sobre los artefactos referenciados por un workspace, leyendo timestamps **exclusivamente** de los campos nativos del archive.

**Propiedad central:**

> Investigation Timeline **ordena artefactos existentes** por su timestamp nativo. **No infiere causalidad. No agrupa. No clasifica. No resume. No puntúa. No interpreta.** Es únicamente una vista ordenada.

## Modelo

```python
TIMELINE_SCHEMA_VERSION: Final[str] = "1"

@dataclass(frozen=True, order=True)
class TimelineEvent:
    observed_at: datetime         # tz-aware UTC, microsecond=0
    artifact_hash: str            # tie-break canónico
    artifact_type: str
    artifact_identifier: str
    source_reference: str         # campo del archive de donde viene observed_at

@dataclass(frozen=True)
class InvestigationTimeline:
    timeline_id: str
    workspace_hash: str
    ordered_events: tuple[TimelineEvent, ...]
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    event_count: int
    timeline_hash: str
    schema_version: str = TIMELINE_SCHEMA_VERSION
```

Orden canónico de `ordered_events`: `(observed_at, artifact_hash)`. Lexicográfico secundario por `artifact_hash` para tie-break determinista.

## Alcance de eventos

Sólo entran en la timeline artefactos con timestamp **nativo en el archive**:

- `evidence` → `Evidence.ingested_at` (campo del row), `source_reference = "evidence.ingested_at"`.
- `assessment` → `AuthenticationAssessment.created_at` (campo del row), `source_reference = "assessment.created_at"`.

Las referencias de tipo `impact_analysis` y `context_bundle` en el workspace **se omiten silenciosamente** porque sus identifiers son opacos y no tienen timestamp persistido. La timeline es honesta sobre lo que sabe.

## Hashes

`timeline_hash`: SHA-256 hex de la canonicalización JCS del timeline **excluyendo** el propio campo. Mismo patrón que `ContextBundle.context_bundle_hash` y `InvestigationWorkspace.workspace_hash`.

`workspace_hash` actúa como ancla: el timeline declara el workspace específico del que se derivó.

Función pública `verify_timeline_hash(timeline)` permite verificación offline.

## Persistencia

`<archive>/timelines/<timeline_id>.json`. **No entra** en `V1_TABLES` ni en `compute_manifest`. `archive_manifest_hash` invariante ante operaciones de timeline.

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo bit-identical | mismo workspace + mismo archive ⇒ mismo timeline |
| G2 | Removibilidad sin huella | `archive/timelines/` periférico |
| G3 | No ejecuta motores analíticos | AST inspect: imports limitados a workspace + core + storage + analysis (lectura de modelo) |
| G4 | Hash verificable offline | `verify_timeline_hash(t)` sin archive |
| G5 | Compatibilidad total | `schema_version` invariante |
| G6 | Sin interpretación | Tokens prohibidos absent (severity, ranking, etc.) |
| G7 | Sin duplicación | Eventos referencian artefactos por hash; cero payload |

## CLI

```sh
aip timeline build  --workspace-id ID --timeline-id ID --archive PATH [--output PATH]
aip timeline show   <timeline_id> --archive PATH
aip timeline verify <timeline.json>
```

JSON canónico (`sort_keys=True`). Subgrupo style.

## Componentes excluidos

ML, NLP, LLM, embeddings, clustering, scoring, ranking, recomendaciones, causalidad, agrupación, resumen, clasificación, hipótesis. Cero floats. Cero campos subjetivos.

## Alineación ADR-0000

P1, P2, P5, P8, P11.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
