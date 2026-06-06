# ADR-0018: Estrategia de búsqueda

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0011, ADR-0015, ADR-0017, ADR-0021

---

## Contexto

La búsqueda es la operación más visible del sistema para un investigador. "Quiero encontrar todos los casos cerca del lago Erie entre 1947 y 1955 con afirmaciones sobre objetos lumínicos" es un ejemplo realista de query que combina texto, geometría, tiempo y vocabulario controlado.

El campo del estudio de fenómenos anómalos tiene además una idiosincrasia: lo que se busca rara vez aparece literalmente con el término usado por quien busca. Un testigo en 1953 escribe "extraña luz pulsante en el cielo"; un curador moderno la etiquetaría como "fenómeno luminoso aéreo no identificado". La búsqueda solo léxica pierde la correspondencia.

Las opciones modernas (búsqueda semántica con embeddings, modelos vectoriales) son tentadoras pero introducen problemas serios:

- Modelos cambian: la búsqueda de hoy no es la búsqueda de mañana. Viola reproducibilidad.
- Modelos son opacos: el usuario no sabe por qué un resultado entró.
- Modelos sesgan: priorizan vocabulario contemporáneo sobre histórico.
- Modelos consumen recursos: chocan con P6/P7.

El sistema necesita un compromiso operativo entre potencia y rigor.

## Decisión

El sistema mantiene **tres modos de búsqueda** con jerarquía explícita:

1. **Búsqueda estructurada** (canónica) — SQL sobre las tablas Parquet/DuckDB. Reproducible bit a bit. Es la búsqueda **autoritativa** del sistema.

2. **Búsqueda léxica/full-text** (canónica) — sobre índices FTS5 (SQLite) o Tantivy (a evaluar en Fase 5). Reproducible bit a bit dado el mismo índice. Resultados auditables.

3. **Búsqueda semántica/vectorial** (opcional) — sobre embeddings con modelo declarado. **Auxiliar, no autoritativa**. Sus resultados son sugerencias para exploración, nunca cita de evidencia per se.

Los tres modos son combinables, pero solo los dos primeros producen resultados citables. Una conclusión publicada nunca cita "este caso lo encontré con búsqueda semántica"; cita la query estructurada o léxica reproducible que devuelve el caso.

## Especificación

### Búsqueda estructurada

Forma canónica. Es SQL ejecutado sobre las tablas Parquet vía DuckDB, posiblemente con extensiones espaciales y recursivas.

```sql
SELECT c.id, c.title
FROM cases c
JOIN case_revisions cr ON cr.case_id = c.id AND cr.hash = c.current_revision
JOIN spatial_anchors sa ON sa.id = ANY(cr.geographic_anchor_ids)
JOIN temporal_anchors ta ON ta.id = ANY(cr.temporal_anchor_ids)
WHERE
  ST_DWithin(sa.geometry, ST_Point(-79.0, 42.5), 50000)  -- 50 km del Lago Erie
  AND ta.lower_bound >= '1947-01-01' AND ta.upper_bound <= '1955-12-31'
  AND cr.status IN ('published', 'revised')
```

Toda búsqueda autoritativa del sistema se puede expresar así. Las búsquedas léxicas y semánticas terminan, en última instancia, aportando candidatos que se filtran/refinan con SQL.

### Búsqueda léxica/full-text

Índice FTS sobre los campos textuales relevantes:
- `Claim.predicate.natural_language` (idioma original preservado).
- `Hypothesis.statement` y `Hypothesis.short_label`.
- `Conclusion.rationale`.
- `CaseRevision.abstract` y `CaseRevision.title`.
- `Source.name`, `Source.notes`.

Características:
- Multilingüe: índices separados por idioma cuando aplique, con normalización por idioma (stemming, stopwords).
- Soporte de fuzzy matching opcional.
- BM25 como ranker por defecto.
- Sin "magia" de relevancia oculta: parámetros configurables y documentados.

Cada query léxica devuelve **scoring transparente**: BM25 score, tokens matched, longitud del documento. Auditable.

### Búsqueda semántica/vectorial

**Opcional. Auxiliar. No autoritativa.**

Si activada, el sistema admite embeddings de:
- Claims (predicado natural).
- Resúmenes de casos.
- Hipótesis.

El modelo de embeddings es **declarado explícitamente** en el manifiesto reproducible (`ArchiveManifest.embedding_model`):

```
embedding_model: {
  name: "...",
  version: "...",
  hash: "...",            # del modelo en disco, si local
  dimensions: 384,        # por ejemplo
  is_local: true
}
```

Resultados de búsqueda vectorial son **etiquetados como auxiliares**. La UI y la CLI marcan claramente "resultado de búsqueda semántica con modelo X versión Y". El sistema rechaza usarlos como cita en una `Conclusion`.

Si el modelo se actualiza, los embeddings antiguos siguen siendo válidos para sus snapshots históricos. Una snapshot citable lleva el modelo de embeddings exacto que usó.

### Combinación de modos

Los modos se combinan operacionalmente:

```python
results = (
    aip.search.semantic("objeto pulsante en el cielo", top_k=200)
    .filter_lexical("luz OR luminoso OR pulsante")
    .filter_structured(
        spatial_within=("EPSG:4326", -79.0, 42.5, 50_000),
        temporal_between=("1947-01-01", "1955-12-31"),
        case_status_in=["published", "revised"],
    )
    .with_audit()
)
```

El método `.with_audit()` produce un trace estructurado: qué modo trajo cada candidato, qué filtros lo eliminaron o retuvieron, qué score le asignó cada capa. Útil para entender por qué un resultado aparece o no.

### Reproducibilidad

Para que una búsqueda sea reproducible:

- Modo estructurado: SQL + `archive_manifest_hash` es suficiente.
- Modo léxico: SQL + hash del índice FTS + `archive_manifest_hash`.
- Modo semántico: SQL + hash del modelo de embeddings + hash del índice vectorial + `archive_manifest_hash`.

Cualquier query citable incluye estos componentes en su forma canónica.

### Diccionarios y sinónimos

Para mejorar búsqueda léxica sin caer en folksonomy, el sistema mantiene un **diccionario de sinónimos y términos histórico-modernos** como parte del vocabulario controlado (ADR-0011):

- "objeto volador no identificado" ≡ "OVNI" ≡ "UFO" ≡ "UAP" (en el contexto de evolución terminológica del campo).
- "luz pulsante" relacionado con "fenómeno luminoso intermitente".
- Etc.

Las relaciones de sinonimia y relación están versionadas y citables. Una búsqueda léxica con `expand_synonyms=true` documenta qué expansiones aplicó.

### Filtros canónicos

Filtros de primera clase ampliamente usados:

- `evidence_kind`, `evidence_status`, `source_id`, `source_kind`.
- `claim_scope`, `claim_modality`, `attributed_to`.
- `hypothesis_family`, `hypothesis_status`.
- `case_status`, `curator`.
- Temporal: rango, calendario, precisión.
- Espacial: dentro de polígono, dentro de radio, intersección con región nombrada.
- Procedencia: nivel de autoridad (`primary`/`secondary`/etc.).
- Idioma de origen.

### No-features

- **No hay personalización de resultados.** Mismo dataset → mismas queries → mismos resultados. Sin perfilado.
- **No hay sugerencias generativas.** Si el usuario quiere ayuda para formular query, la asistencia LLM (ADR-0021) puede sugerir, pero el output siempre es una query reproducible que el usuario inspecciona y ejecuta.
- **No hay aprendizaje implícito de los clicks del usuario.** El sistema no muta su ranking según uso.

## Justificación

### Por qué tres modos con jerarquía

Reducir a uno solo perdería. El SQL es el suelo autoritativo. El léxico cubre el caso común "buscar palabras". El semántico es heurístico útil para descubrimiento, pero su no reproducibilidad estricta lo descalifica como autoritativo.

### Por qué la búsqueda semántica no es citable

Modelos cambian. Reentrenamiento, fine-tuning, ajuste de tokenizer producen resultados distintos. Aceptar resultados semánticos como cita haría que el archivo histórico cambiara silenciosamente al actualizar modelo. P5 (reproducibilidad) lo prohíbe.

### Por qué modelos locales preferidos

P6 (local-first), P7 (coste cercano a cero). Modelos pequeños (sBERT compacto, multilingüe) caben en disco moderno y se ejecutan en CPU razonablemente. Si el usuario quiere modelos mayores, los activa explícitamente con declaración en manifiesto.

### Por qué sin personalización

Personalización oculta sesgo de ranking detrás del usuario. Investigación rigurosa exige que dos investigadores ejecutando la misma query en el mismo archivo vean lo mismo.

### Por qué diccionario de sinónimos versionado

Es la forma honesta de capturar evolución terminológica sin entrenamiento opaco. Cualquier expansión es auditable y reversible.

## Consecuencias

**Positivas**
- Búsquedas autoritativas son reproducibles bit a bit.
- Combinación de modos cubre flujos reales.
- Trace auditable evita "el ranker dijo que sí".
- Sinónimos versionados capturan evolución del campo.

**Negativas**
- Sin personalización, la UX puede sentirse menos "moderna".
- Mantener diccionario de sinónimos es trabajo curado.
- Búsqueda semántica como auxiliar puede confundir a usuarios que la esperan autoritativa.

**Neutras**
- Implementación inicial con FTS5 + DuckDB; evaluar Tantivy/LanceDB en Fase 5 según necesidad real.

## Alternativas consideradas

### A. Solo búsqueda semántica
**Descripción:** Confiar en embeddings para todo.
**Razón de rechazo:** Viola reproducibilidad. Opacidad.

### B. Solo SQL
**Descripción:** Sin FTS, sin semántica.
**Razón de rechazo:** UX inaceptable para investigadores que quieren buscar palabras.

### C. Búsqueda semántica como ranker primario con SQL como filtro
**Descripción:** Invertir la jerarquía.
**Razón de rechazo:** Misma violación de reproducibilidad. El ranker primario debe ser determinístico.

### D. Personalización basada en uso
**Descripción:** Aprender de clicks.
**Razón de rechazo:** Sesgo opaco.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P3, P4, P5, P6, P7, P10.

**Cómo se alinean:**
- P5 (reproducibilidad): solo búsquedas autoritativas determinísticas son citables.
- P10 (no fabricación): búsqueda semántica como auxiliar, etiquetada explícitamente.
- P4 (neutralidad): sin personalización, sin reranking implícito.
- P6/P7: modelos locales preferidos.

**Tensión:** Modernidad UX vs. rigor. Aceptada.

## Referencias

- Robertson, S., & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond.*
- Apache Lucene / Tantivy documentation.
- SQLite FTS5 documentation.
- Datasette (Simon Willison). Prior art en exposición SQL sobre datasets.
- Reimers, N. (2019+). Sentence-BERT family of models.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
