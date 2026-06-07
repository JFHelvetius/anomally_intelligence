# ADR-0039: Investigation Diff Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0030, ADR-0036, ADR-0037, ADR-0038

---

## Contexto

ADR-0038 produjo snapshots de investigación. Sigue faltando una operación: **comparar dos snapshots** y reportar diferencias estructurales puras.

## Decisión

Introducir `src/aip/diff/`, capa que **compara dos snapshots** por set-difference sobre sus `referenced_artifacts`. Sin ranking, sin interpretación, sin lenguaje cargado.

**Propiedad central:**

> Investigation Diff **reporta diferencias estructurales** entre dos
> snapshots. **No declara cuál es mejor, peor, más importante ni más
> relevante.** No infiere. No interpreta. Sólo diferencias de set.

## Modelo

```python
DIFF_SCHEMA_VERSION: Final[str] = "1"

@dataclass(frozen=True, order=True)
class DiffEntry:
    reference_type: str
    identifier: str
    artifact_hash: str

@dataclass(frozen=True)
class InvestigationDiff:
    snapshot_a_hash: str
    snapshot_b_hash: str
    added_artifacts: tuple[DiffEntry, ...]      # en b, no en a
    removed_artifacts: tuple[DiffEntry, ...]    # en a, no en b
    unchanged_artifacts: tuple[DiffEntry, ...]  # en ambos
    diff_hash: str
    schema_version: str = DIFF_SCHEMA_VERSION
```

Las tres tuplas están canónicamente ordenadas. Cero campos de "mejora", "regresión", "importancia". Sólo presencia/ausencia.

## Hashes

`diff_hash`: SHA-256 hex de la canonicalización JCS del diff **excluyendo** el propio campo.

`verify_diff(diff)` recomputa offline.

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo | mismo par (a, b) ⇒ mismo diff |
| G2 | Removibilidad | diff no se persiste por defecto |
| G3 | No ejecuta motores | AST inspect — sólo importa de snapshot+core |
| G4 | Verify offline | `verify_diff(d)` sin archive |
| G5 | Compatibilidad total | invariante schema_version |
| G6 | Sin interpretación | Tokens prohibidos absent + lenguaje neutral por construcción |
| G7 | Sin duplicación | Sólo referencias (type, id, hash), cero payload |

## CLI

```sh
aip diff snapshots <a.json> <b.json> [--output PATH]
```

JSON canónico a stdout. Opcional `--output` para persistir.

## Componentes excluidos

| Excluido | Materialización |
|---|---|
| Ranking de importancia | Tres campos: added/removed/unchanged. Ninguno declara importancia |
| Lenguaje cargado ("mejor", "peor", "regresión") | Test de tokens prohibidos verifica ausencia |
| Inferencia causal | Diff no relaciona causas; sólo reporta presencia |
| Sugerencias | Cero campos `recommend_*` |
| ML / NLP / LLM | Cero deps |

## Alineación ADR-0000

P1, P2, P5, P8, P11.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
