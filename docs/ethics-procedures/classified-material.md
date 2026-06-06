# Procedimiento para material que aparenta ser clasificado

**Estado:** Aceptado
**Fecha:** 2026-06-06
**ADRs que lo exigen:**
- [`ADR-0026 §C4`](../adr/0026-sustainable-stewardship.md) — "Decisiones éticas ancladas a procedimiento".
- [`ADR-0020`](../adr/0020-ethics-framework.md) — Marco ético general.
- Mitigación de [`docs/reviews/adr_red_team_review.md`](../reviews/adr_red_team_review.md) §8.3 ("Política sobre material clasificado es inestable") — cerrada en [`red_team_response.md`](../reviews/red_team_response.md) condicional a este documento.

---

## 1. Propósito

Define **el procedimiento operacional** que aplica cuando material que va a ser ingestado en un archive AIP **aparenta** ser clasificado por una autoridad estatal.

El procedimiento existe para:

- Proteger al proyecto de convertirse en canal de filtración (no-objetivo declarado del [`ADR-0000`](../adr/0000-long-term-vision.md)).
- Proteger al operador de exposición legal en su jurisdicción.
- Preservar la cadena de evidencia de cualquier material **público** ya ingestado sin contaminarla con material de estatus dudoso.
- Hacer la decisión sobre cada caso **trazable**: misma situación documentada produce misma decisión.

## 2. Alcance

Este procedimiento **define**:

- Qué cuenta como "material que aparenta clasificado" desde el punto de vista del adquisidor y del curador (heurística operacional).
- Qué pasa con la ingestión cuando ese trigger se activa.
- Qué se documenta y dónde queda registrado.
- Qué se hace con material previamente ingestado que se descubre después con estatus dudoso.

Este procedimiento **NO define**:

- Si un documento concreto **es** legalmente clasificado en alguna jurisdicción. El proyecto no es autoridad legal.
- Juicios de autenticidad sobre el material (eso es `AuthenticationAssessment` en el modelo de evidencia, separado).
- Conclusiones sobre la legitimidad de la clasificación original (eso es debate político fuera del alcance del proyecto).
- Quién puede usar AIP. El sistema no filtra al usuario; filtra ingestión.
- Asesoría legal para el operador. El operador es responsable de su propia jurisdicción.

## 3. Definición operativa de "material que aparenta clasificado"

Indicadores heurísticos. Cualquiera de ellos basta para activar el procedimiento. Ninguno es declaración legal.

### 3.1 Marcas visibles sobre el propio artefacto

- Sellos, carimbos o marcas con palabras como (no exhaustivo): "CLASSIFIED", "SECRET", "TOP SECRET", "CONFIDENTIAL", "RESTRICTED", "RESERVADO", "CONFIDENCIAL", "SECRETO" o equivalentes en cualquier idioma.
- Numeración de control (e.g., "Copy 3 of 12"), advertencias de manejo, restricciones de distribución ("NOFORN", "ORCON", "EYES ONLY").
- Banderas o cabeceras de cabecera/pie ("FOR OFFICIAL USE ONLY", "OFFICIAL", "OFICIAL", "EMBARGO HASTA").

### 3.2 Contexto de procedencia declarado

- La `Source` que aporta el material declara `kind = military_report` o `government_archive` y el `name` o `notes` mencionan filtración, leak, whistleblower, o equivalentes.
- El `Provenance.steps` incluye actores anónimos sin justificación documentada.
- El material está enlazado desde un repositorio explícitamente dedicado a filtraciones no autorizadas.

### 3.3 Trigger del propio operador o adquisidor

- El operador, al revisar el material previo a ingestar, identifica subjetivamente cualquier característica anterior aunque no esté en la lista.
- Un adquisidor automatizado lo marca por regex de palabras clave.

**Nota:** la presencia de cualquier indicador es **trigger para procedimiento**, no veredicto. El procedimiento permite que material con marcas visibles sea ingestado **si y solo si** la verificación del paso 2 confirma que ya está desclasificado.

## 4. El procedimiento de cinco pasos

Codifica el bloque de mitigación del [`ADR-0026 §C4 §RTR §8.3`](../adr/0026-sustainable-stewardship.md). No añade pasos nuevos; los formaliza con plantilla.

### Paso P1 — Suspensión inmediata del adquisidor

Cuando un adquisidor (manual o automatizado) presenta material con cualquier indicador de §3:

- El propio adquisidor **se suspende** sobre ese ítem hasta resolución.
- El blob no se mueve al CAOS del archive bajo ninguna circunstancia hasta haber pasado P2 y P3.
- Si el adquisidor es manual (operador con CLI), se interrumpe la sesión sin ejecutar `aip evidence ingest`.
- Si el adquisidor es automatizado (cuando aplique en fases futuras), se marca el ítem como `pending_review` y se notifica al curador. Hasta ADR-0014, este caso no aplica en V1.

### Paso P2 — Verificación del estatus de clasificación

Antes de cualquier decisión sobre ingesta:

1. Localizar al menos **una fuente independiente y verificable** que documente el estatus actual del documento. Ejemplos aceptables:
   - Catálogo público de archivo nacional con metadato de "desclasificado el [fecha]".
   - Documentación FOIA con número de release.
   - Aviso oficial de la autoridad clasificadora (military release, executive declassification order, etc.).
   - Cita académica de un trabajo revisado por pares que documente la desclasificación.
2. Anotar la cita exacta del statement de estatus: URL, archivo, fecha, autoridad.
3. Si la verificación no produce evidencia inequívoca de **desclasificación**, se asume estatus dudoso y se pasa al P3c.

### Paso P3a — Confirmado clasificado vigente

Si la verificación produce evidencia de que el documento sigue clasificado en su jurisdicción de origen:

- **El material no se ingesta.** Ni en V1, ni en fases posteriores.
- Se documenta la decisión conforme a §5.
- Si el adquisidor mantenía el blob en un staging, se elimina del staging.
- El operador puede mantener su propia copia para uso personal sujeto a las leyes de su jurisdicción. El proyecto no se mezcla con esa decisión.

### Paso P3b — Confirmado desclasificado

Si la verificación produce evidencia inequívoca de desclasificación:

- Ingesta normal vía `aip evidence ingest`.
- La cita del statement de desclasificación se incluye obligatoriamente en `Source.notes` o en `Provenance.steps[N].notes`.
- El `Evidence.notes` registra "Estatus de clasificación verificado como `released` el [fecha] por [autoridad]; cita en `Source.notes`".
- El `AuthenticationAssessment` permanece con default `unverified` — la confirmación de desclasificación **no** es lo mismo que confirmación de autenticidad. Son ejes ortogonales.

### Paso P3c — Ambiguo: verificación imposible en plazo razonable

Si el operador no consigue evidencia inequívoca en cualquiera de las dos direcciones tras un esfuerzo razonable:

- **Default: no ingesta.** El silencio del registro público no equivale a desclasificación.
- Se documenta la decisión conforme a §5, indicando "Verificación no concluyente; default a no ingesta".
- El ítem queda fuera del archive. El operador puede reintentar la verificación si surge nueva evidencia pública.

## 5. Formato de documentación de la decisión

Cada decisión bajo este procedimiento genera una entrada de registro. En V1 (sin `aip osint` ni HTTP API) la entrada se mantiene en un fichero local del operador. Cuando se levante [`ADR-0014`](../adr/0014-osint-strategy.md), el manifiesto del adquisidor podrá incluir el bloque correspondiente nativamente.

Formato canónico de la entrada:

```yaml
---
decision_id: <ulid o slug determinístico>
decision_date: <YYYY-MM-DD>
operator: <ActorId del MAINTAINERS.md o del operador del archive>
material_identity:
  human_description: <una a tres frases>
  candidate_hash: <SHA-256 si fue computado en staging; opcional>
  source_url_or_location: <URL o ruta>
trigger:
  indicator_kind: visible_marking | source_context | operator_judgement | automated_keyword
  indicator_detail: <texto del marcador, regex que disparó, etc.>
verification:
  attempted_at: <YYYY-MM-DD>
  source_citation: <URL/archivo/cita académica>
  citation_excerpt: <texto literal del statement de estatus>
  result: confirmed_classified | confirmed_declassified | inconclusive
decision: P3a_no_ingest | P3b_ingest | P3c_no_ingest_default
rationale: <una o dos frases que conecten verification.result con decision>
followup:
  blob_disposition: not_staged | deleted_from_staging | ingested_as_<hash>
  notes: <opcional>
---
```

La entrada **no es una afirmación legal** sobre el estatus del documento. Es un registro auditable de **qué decidió el operador, con qué evidencia, en qué fecha**.

## 6. Material ya ingestado que aparece sospechoso post-ingesta

Si después de ingerir material V1 (o futuro) emerge evidencia de que el material era clasificado vigente al momento de la ingestión:

1. **No se borra el blob del CAOS.** [`ADR-0006 §P11`](../adr/0006-formal-evidence-model.md) y [`ADR-0024 §L2`](../adr/0024-epistemic-honesty-amendment.md) prohíben mutar evidencia raw. La inmutabilidad protege la cadena.
2. El `EvidenceStatus` del registro afectado pasa a `quarantined` (valor existente en [`aip.core.evidence.EvidenceStatus`](../../src/aip/core/evidence.py)).
3. El cambio de status se registra como entrada del audit log (acción `change_evidence_status` cuando esté implementada; en V1 se anota en `Evidence.notes` con prefijo `[CLASSIFIED_STATUS_REVISION]` hasta que el comando exista).
4. Se documenta una entrada bajo §5 con `decision = P3a_no_ingest`, `followup.blob_disposition = ingested_as_<hash> · quarantined`.
5. Cualquier sucesor que clone el archive recibe el blob con status `quarantined` y debe respetar el quarantine para sus propias decisiones.

El quarantine no es "borrado dignified"; es marcaje honesto. La cadena de evidencia documenta tanto la ingestión original como la decisión posterior.

## 7. Lo que este procedimiento NO hace

- ❌ **No** emite juicios de autenticidad. Eso vive en `AuthenticationAssessment`.
- ❌ **No** emite conclusiones legales. El operador es responsable de su propia jurisdicción.
- ❌ **No** prohíbe que un operador, en su sistema personal y bajo su responsabilidad legal, mantenga material clasificado fuera del archive AIP. El procedimiento solo regula qué entra al archive.
- ❌ **No** sustituye asesoría legal. Si el operador tiene dudas legales reales sobre un caso, debe consultar a un abogado de su jurisdicción antes de actuar.
- ❌ **No** trata de identificar a quien filtró un documento. AIP no es herramienta forense de leaks.
- ❌ **No** garantiza protección legal del operador. Documentar la decisión bajo §5 es honestidad operativa, no defensa jurídica.

## 8. Trigger de revisión

Este procedimiento se revisa **automáticamente** cuando:

- Se apruebe el ADR de levantamiento de [`ADR-0014`](../adr/0014-osint-strategy.md) (adquisidores OSINT activos cambian la superficie del problema).
- Se apruebe el ADR de levantamiento de la sección de enclave de [`ADR-0019`](../adr/0019-security-model.md) (material sensible con flujo de takedown cambia P6).
- Se materialice un caso concreto en producción que el procedimiento no cubra claramente. La excepción se documenta como issue público y produce update de este fichero por PR.

## 9. Alineación con las cuatro garantías

| Garantía | Estado tras este procedimiento |
|---|---|
| **Provenance** | **se refuerza**: §5 obliga a citar la fuente del statement de desclasificación en `Source.notes`. |
| **Evidence integrity** | **se refuerza**: §6 mantiene `quarantined` como mecanismo no destructivo. |
| **Reproducibility** | **intacta**: el procedimiento es operacional, no toca canonicalización. |
| **Hash stability** | **intacta**: ningún pinned value se ve afectado. |
