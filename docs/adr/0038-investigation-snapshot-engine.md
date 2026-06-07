# ADR-0038: Investigation Snapshot Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0023, ADR-0030, ADR-0036, ADR-0037

---

## Contexto

ADR-0036 produjo workspaces. ADR-0037 produjo timelines.

Falta una pieza: **congelar un estado exacto de una investigación** (workspace + timeline) en un artefacto único, portable y verificable offline.

## Decisión

Introducir `src/aip/snapshot/`, capa que **agrupa por referencia** un workspace y su timeline en un `InvestigationSnapshot`. Cero payload de artefactos; sólo hashes y referencias.

**Propiedad central:**

> Investigation Snapshot **congela referencias** existentes. **No copia payloads. No duplica resultados. No infiere. No interpreta.**

## Modelo

```python
SNAPSHOT_SCHEMA_VERSION: Final[str] = "1"

@dataclass(frozen=True, order=True)
class SnapshotReference:
    reference_type: str
    identifier: str
    artifact_hash: str

@dataclass(frozen=True)
class InvestigationSnapshot:
    snapshot_id: str
    workspace_hash: str
    timeline_hash: str
    referenced_artifacts: tuple[SnapshotReference, ...]
    snapshot_hash: str
    schema_version: str = SNAPSHOT_SCHEMA_VERSION
```

`referenced_artifacts` espeja las referencias del workspace en orden canónico — sin payload.

## Hashes

`snapshot_hash`: SHA-256 hex de la canonicalización JCS del snapshot **excluyendo** el propio campo.

`verify_snapshot(snapshot)` recomputa offline.

## Persistencia

`<archive>/snapshots/<snapshot_id>.json`. No entra en V1_TABLES. Manifest del archive invariante.

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo bit-identical | mismo (workspace, timeline) ⇒ mismo snapshot |
| G2 | Removibilidad sin huella | `archive/snapshots/` periférico |
| G3 | No ejecuta motores | AST inspect — sólo importa de workspace+timeline+core |
| G4 | Verify offline | `verify_snapshot(s)` sin archive |
| G5 | Compatibilidad total | `schema_version` invariante |
| G6 | Sin interpretación | Tokens prohibidos absent |
| G7 | Sin duplicación | Sólo referencias, cero payload |

## CLI

```sh
aip snapshot create --snapshot-id ID --workspace-id ID --timeline-id ID --archive PATH [--output PATH]
aip snapshot show   <snapshot_id> --archive PATH
aip snapshot verify <snapshot.json>
```

## Componentes excluidos

ML, NLP, LLM, embeddings, clustering, scoring, ranking, recomendaciones, agrupación, resumen, interpretación. Cero floats.

## Alineación ADR-0000

P1, P2, P5, P8, P11.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
