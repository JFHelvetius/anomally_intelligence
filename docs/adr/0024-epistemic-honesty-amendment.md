# ADR-0024: Epistemic Honesty Amendment — límites operativos de las promesas epistémicas

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0002, ADR-0006, ADR-0009, ADR-0010, ADR-0015, ADR-0016

---

## Contexto

El Red Team Review documentó que varias promesas epistémicas del cuerpo de ADRs son **performativas** o **selectivas**: enuncian un ideal sin operacionalizar sus límites. Específicamente:

- **§1.2** Honestidad epistémica es selectiva: ciertas incertidumbres (de marco, lingüísticas, de identidad de actor) no caben en el modelo y por tanto el sistema afirma cuantificar incertidumbre cuando solo cuantifica una parte.
- **§1.3** La pregunta central asume hipótesis independientes; el modelo `HypothesisSet` no soporta dependencia probabilística entre hipótesis ni composición de causas.
- **§2.1** Las propiedades irrenunciables son mutuamente incompatibles en escenarios reales (P9⊥P12, P3⊥P5, P6⊥P9, P10⊥P11). Los ADRs aceptan las tensiones con disclaimer pero no las resuelven.
- **§2.2** P2 (trazabilidad bit a bit) no se sostiene cuando depende de servicios externos cuyo estado cambia (LLMs remotos, fuentes web dinámicas).
- **§3.1** La frontera Fact/Claim es borrosa; un log de instrumento es Fact según una lectura y Claim del operador del instrumento según otra.
- **§3.3** `KentLevel` se presenta como alternativa al score escalar y opera como score escalar con etiquetas verbales.
- **§3.5** La inmutabilidad de evidencia produce explosión de versiones derivadas que erosiona la usabilidad operativa.
- **§4.3** La cita académica por `head` anula reproducibilidad en la práctica aunque el sistema soporte cita por hash.
- **§6.1, §6.2** Dependencias críticas (DuckDB, Parquet) son puntos únicos de falla cuya migración futura no está garantizada.

Este ADR no relaja las propiedades P1–P12 ni los modelos. Lo que hace es **acotar honestamente** qué prometen esas propiedades, qué no prometen, y bajo qué condiciones operativas su garantía se sostiene.

## Decisión

Se introducen **siete límites operativos declarados** que acompañan a las propiedades y modelos correspondientes. Estos límites son obligatorios en la documentación de usuario y en cualquier comunicación pública del proyecto.

### Límite L1. Incertidumbre cuantificada es incertidumbre de primer orden y solo de objetos modelados

P3 (incertidumbre como ciudadano de primera clase) **cubre**:

- Confianza relativa entre hipótesis declaradas en un `HypothesisSet` con curador identificado.
- Distribución cualitativa Kent sobre esas hipótesis.
- Evidencia favorable y contradictoria por hipótesis.
- Supuestos y preguntas abiertas listados.

P3 **no cubre**, y el sistema **no afirma cubrir**:

- Incertidumbre de marco: si el `HypothesisSet` está bien formulado, si faltan hipótesis razonables que el curador no contempló, si la taxonomía aplicada al caso es la correcta.
- Incertidumbre lingüística: ambigüedad del enunciado original del afirmante.
- Incertidumbre de identidad: si dos `Actor` en el sistema representan la misma persona real.
- Incertidumbre de calibración del afirmante: cómo de fiable es el juicio del curador que asigna Kent.

Estas incertidumbres existen. El sistema las nombra pero no las modela. Cualquier conclusión publicada por el sistema viaja con este límite explícito.

### Límite L2. P2 (trazabilidad bit a bit) cubre solo material ingestado al archivo local

P2 **cubre**:

- Cualquier `Evidence` ingestada: hash, procedencia, transformaciones derivadas explícitas.
- Cualquier `Conclusion`, `EvidenceLink`, `CaseRevision`: hash JCS, autoría, supersedencia.
- Cualquier consulta SQL o léxica sobre el archivo local: misma entrada → misma salida.

P2 **no cubre**:

- Re-derivación de un artefacto cuando su fuente externa ha cambiado o desaparecido. El WARC mitiga pero no elimina el riesgo.
- Reproducción de outputs de LLM remoto cuando el modelo remoto ha cambiado.
- Reproducción de resultados de búsqueda semántica cuando el modelo de embeddings se ha actualizado.

Para los tres casos no cubiertos, el sistema preserva el output histórico **como artefacto inmutable**. Lo que no garantiza es que ese output se pueda **regenerar** desde la fuente original en el futuro. La distinción entre "preservación" y "regeneración" es operativa y se documenta.

### Límite L3. Las propiedades P1–P12 tienen tensiones operativas reconocidas

Las cuatro tensiones identificadas por el Red Team Review:

- **P9 (fuentes públicas) ↔ P12 (do-no-harm)**: el material público con testigos vivos puede requerir tratamiento conservador en el enclave, reduciendo la fracción de "fuente pública" efectivamente disponible en el archivo abierto. Esta tensión se gestiona caso por caso por el curador, con preferencia hacia P12 cuando el daño es concreto y previsible.

- **P3 (incertidumbre cuantificada) ↔ P5 (reproducibilidad)**: cualquier cuantificación involucra elecciones (priors bayesianos, calibración de Kent, ponderación de evidencias). La elección es **reproducible si se documenta**, pero no es **objetivamente correcta**. El sistema reproduce la cuantificación documentada; no reproduce un consenso epistémico.

- **P6 (local-first) ↔ P9 (fuentes públicas)**: archivos públicos masivos no caben en portátil moderno. El sistema acepta operar sobre **subconjuntos**; el subconjunto efectivo de cada instancia se documenta en el `ArchiveManifest`. Una conclusión publicada cita el subconjunto del que dependía.

- **P10 (no fabricación) ↔ P11 (inmutabilidad de evidencia)**: metadatos derivados por LLM o procesos automáticos pueden enriquecer la comprensión de la evidencia. El sistema los aloja como `LlmAssist` y artefactos derivados (ADR-0021), nunca como mutación de la evidencia raw.

Las cuatro tensiones quedan registradas como tensiones permanentes del diseño, no como bugs por resolver.

### Límite L4. La frontera Fact/Claim es decisión del curador, no propiedad universal

ADR-0001 distingue cinco categorías epistémicas como tipos del modelo. La asignación de un enunciado a categoría es **acto del curador**, no clasificación automática del sistema. En zonas grises (log de instrumento como Fact vs. Claim del operador; testimonio bajo regresión hipnótica como Claim vs. Interpretation; etc.) la decisión:

- Lleva autoría y fecha.
- Lleva justificación en `notes`.
- Es revisable: un curador posterior puede registrar una segunda categorización con evidencia para el cambio, sin sobreescribir la primera.

El sistema **no afirma** que su categorización refleje una división objetiva del mundo. Afirma que la división registrada es **auditable y revisable**.

### Límite L5. KentLevel es score ordinal con etiquetas verbales y se declara como tal

ADR-0009 introdujo `KentLevel` con rangos sugeridos y justificó "las palabras llevan menos pretensión de precisión que los números". El Red Team Review observa correctamente que la información operativa extraída de `likely` y de `0.7` es la misma. Aceptado.

`KentLevel` se documenta de aquí en adelante como:

- **Score ordinal de siete niveles** con anclajes verbales y rangos cuantitativos sugeridos.
- Su ventaja sobre el escalar puro: **resiste pretensión de precisión espuria** (`likely` no invita a debatir si era 0.72 o 0.73; `0.7` sí).
- Su limitación operativa: codifica la misma información que un score escalar; cualquier transformación matemática sobre Kent equivale a transformación sobre escalar.

Esta franqueza protege al usuario de la ilusión de que Kent es metodológicamente superior cuando solo es **operacionalmente más sobrio**.

### Límite L6. La inmutabilidad opera bajo política de compactación documentada

ADR-0006 declara inmutabilidad. El Red Team Review observa que la explosión de versiones derivadas erosiona la usabilidad. Este ADR introduce un **principio de compactación documentada** sin violar inmutabilidad:

- Cualquier `Evidence` con `status: superseded` permanece en el archivo histórico.
- Una vista materializada `evidence_current` expone solo las versiones activas para uso operativo diario.
- Comandos del sistema operan por defecto sobre `evidence_current`; consultas explícitamente históricas operan sobre el conjunto completo.
- Esta separación es **vista**, no eliminación. El histórico completo sigue accesible para auditoría y reproducción.

La inmutabilidad sigue siendo invariante del archivo; la usabilidad operativa se gestiona con vistas.

### Límite L7. Cita académica obligatoria por hash, no por head

ADR-0010 soporta cita por `aip:case/<id>@<revision_hash>` y por `aip:case/<id>` (head). El Red Team Review observa que la práctica académica derivará hacia `head` y anulará la promesa de reproducibilidad.

Política del proyecto:

- La **documentación pública del proyecto**, las plantillas de exportación, y cualquier output destinado a publicación citan obligatoriamente por hash, no por head.
- Citas por head se permiten en UI exploratoria pero llevan marca visual "no-citable, snapshot móvil".
- Las exportaciones académicas (snapshots empaquetados, citas estructuradas en BibTeX/CSL) usan exclusivamente forma con hash.

No se puede impedir que un autor externo cite por head; se elimina la opción de hacerlo desde el tooling oficial.

### Declaración complementaria: punto único de falla en DuckDB y Parquet

El Red Team Review identifica DuckDB y Parquet como dependencias críticas cuyo cambio futuro podría dañar el proyecto. Reconocimiento explícito:

- **El formato canónico del archivo es Parquet con esquema JCS-hashado**, no DuckDB. Si DuckDB desaparece, los datos siguen accesibles con cualquier otro lector Parquet/Arrow.
- DuckDB es **motor de consulta preferido**, no fuente de verdad. Toda funcionalidad implementada con DuckDB es regenerable con cualquier otro motor analítico SQL sobre Arrow.
- Parquet en sí es estándar abierto adoptado por Apache Arrow y mantenido por la Apache Software Foundation. Si su evolución introduce incompatibilidades, el plan es congelar lectura sobre la versión adoptada en el `ArchiveManifest` y migrar derivaciones, no el archivo histórico.

Esta separación entre formato (Parquet) y motor (DuckDB) protege contra el modo de fallo "DuckDB pivotea y nos hundimos".

## Consecuencias

**Positivas**
- El proyecto no afirma más de lo que entrega.
- Los límites declarados son criterios de evaluación útiles para revisores externos.
- Defensa estructural contra modos de fallo identificados sin debilitar los modelos.

**Negativas**
- Lectores que esperan promesas absolutas encontrarán declaraciones cualificadas.
- La documentación se vuelve más extensa con los límites.

**Neutras**
- Ninguno de los modelos cambia; solo se acotan sus garantías.

## Declaración de limitaciones generales

Este ADR es un acto de honestidad sobre lo que el proyecto **no** garantiza incluso en su mejor estado:

- No garantiza captar toda la incertidumbre epistémicamente relevante.
- No garantiza que la categorización epistémica sea universal o correcta.
- No garantiza reproducibilidad cuando depende de servicios o fuentes externas mutables.
- No garantiza adopción ni citabilidad académica por su mera existencia.
- No garantiza compatibilidad de formatos en horizontes de décadas más allá de Parquet stable y SHA-256.

## Declaración de riesgo de mantenedor único

La aplicación de los siete límites requiere disciplina operativa sostenida. Bajo mantenedor único part-time, la disciplina puede erosionarse silenciosamente. El proyecto reconoce este riesgo y se compromete a **revisar trimestralmente** que los límites declarados sigan operacionalizados en el código y la documentación. La revisión queda registrada en `audit.log`.

Si los límites se incumplen silenciosamente, este ADR autoriza explícitamente a cualquier observador externo a reportarlo como bug arquitectónico, no como crítica menor.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P9, P10, P11, P12.

**Cómo se alinean:** este ADR **fortalece** las propiedades acotando lo que prometen. Una propiedad acotada con honestidad es más robusta que una propiedad enunciada en absoluto y susceptible a desmentido operativo.

**Tensión:** ninguna nueva. Las tensiones inter-propiedad ya existían; este ADR las hace visibles.

## Referencias

- `docs/reviews/adr_red_team_review.md`, secciones §1.2, §1.3, §2.1, §2.2, §3.1, §3.3, §3.5, §4.3, §6.1, §6.2.
- Kent, S. (1964). *Words of Estimative Probability.*
- Sigstore project. Prior art en transparencia de artefactos.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
