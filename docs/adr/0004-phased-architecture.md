# ADR-0004: Arquitectura por fases

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0003

---

## Contexto

El alcance latente de AIP es enorme: archivo histórico desde la antigüedad, ingestión de fuentes modernas, modelo de evidencia formal, grafo de conocimiento, motor temporal y geoespacial, OSINT, búsqueda, API, UI, ética, gobernanza. Si se afronta como un único bloque, el riesgo es:

- Diseñar capacidades cuya utilidad real no se conoce hasta que las anteriores existen.
- Atar decisiones de Fase 5 a supuestos que la Fase 1 desmiente.
- Producir un sistema parcial donde nada funciona de extremo a extremo.

La práctica establecida en proyectos de horizonte largo (incluyendo `orbital-sentinel`) es declarar fases funcionales y demostrables, cada una con un entregable mínimo coherente. Esa disciplina obliga a que cada fase produzca algo defendible aislado, y a que los aprendizajes de cada una alimenten las siguientes antes de comprometer arquitectura.

## Decisión

El proyecto se desarrolla en seis fases secuenciales. Cada fase es **funcional y demostrable** —su entregable es un sistema que hace algo verificable de extremo a extremo, no un fragmento de andamiaje—. Una fase no puede declararse cerrada hasta que su demo es ejecutable por un investigador externo siguiendo solo la documentación pública.

| Fase | Nombre                                  | Entregable de cierre                                                                                          |
|------|------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| F1   | Modelo de evidencia y fuentes            | Ingestar un PDF desclasificado público y reproducir su cadena de evidencia bit a bit desde el hash crudo      |
| F2   | Catálogo de casos                        | Cargar un archivo histórico (ej. Project Blue Book selección) como casos sobre el modelo de evidencia          |
| F3   | Hipótesis y confianza                    | Evaluar un caso conocido con al menos 3 hipótesis competidoras y exponer su distribución de confianza         |
| F4   | Motores temporal y geoespacial           | Reconstruir la línea de tiempo de un caso multi-fuente y mapear sus geometrías con incertidumbre              |
| F5   | Grafo de conocimiento                    | Cruzar entidades (testigos, lugares, organizaciones) entre ≥10 casos históricos y exponer relaciones          |
| F6   | Workflows de investigación reproducible  | Un revisor externo reproduce un análisis publicado desde un snapshot citable, sin asistencia del autor        |

El orden es estricto. F2 no comienza hasta que F1 cierra. La razón se explica más abajo.

## Justificación

### Orden por dependencia, no por atractivo

El orden no refleja qué fase es más interesante; refleja qué fase es prerrequisito de las siguientes. F1 (evidencia y fuentes) es la base de todo lo demás: sin un modelo formal de evidencia con procedencia, cualquier caso ingestado en F2 hereda los defectos del campo (mezcla narrativa, falta de cadena de custodia). Sin casos en F2, no hay material sobre el que evaluar hipótesis en F3. Sin hipótesis en F3, los motores temporal y geoespacial de F4 no tienen consumidor lógico que les dé sentido. Y así sucesivamente.

### Demostrabilidad como filtro

Cada fase termina con una demo ejecutable por un externo. No por marketing: por filtro. Si la demo no se puede preparar, la fase tiene un defecto real (documentación insuficiente, dependencia oculta, supuesto no operacionalizado). El cierre formal de una fase es la ejecución exitosa de su demo por alguien que no participó en su desarrollo.

### Aprendizaje retroalimentado

Cada fase produce dos tipos de output: el entregable funcional y una **revisión de fase** (`docs/reviews/phase-N-review.md`) que documenta qué supuestos se confirmaron, cuáles se rompieron, y qué decisiones arquitectónicas requieren ADR de enmienda antes de comenzar la siguiente.

### Sin fases paralelas

No se trabajan dos fases en paralelo. La razón es que F1→F6 se diseñan asumiendo retroalimentación secuencial. Si F3 comienza antes de cerrar F2, las decisiones de F3 se toman sobre un modelo de casos que aún se está validando, y eso introduce supuestos ocultos que es caro retractar después.

Excepción explícita: documentación, ética y gobernanza son ejes transversales que evolucionan en todas las fases.

## Descripción detallada de las fases

### Fase 1 — Modelo de evidencia y fuentes

**Objetivo.** Esquemas formales y código que ingesten un artefacto crudo (PDF, imagen, audio, transcripción), lo direccionen por hash, registren su procedencia, y permitan recuperar la cadena bit a bit.

**Incluye.**
- Implementación de ADR-0005 (fuente y procedencia).
- Implementación de ADR-0006 (modelo de evidencia formal).
- Implementación de ADR-0015 (storage) y ADR-0016 (versionado content-addressed).
- CLI mínima para ingestar y consultar.

**No incluye.**
- Modelo de caso completo. F1 ingesta evidencia, no casos.
- Hipótesis ni conclusiones.
- Grafo de conocimiento.

**Demo de cierre.** Un investigador externo:
1. Clona el repositorio.
2. Descarga un PDF desclasificado público especificado en la doc.
3. Ejecuta `aip evidence ingest <pdf>`.
4. Recupera con `aip evidence show <hash>` la procedencia completa.
5. Verifica que el hash coincide con el publicado en la doc de la demo.

### Fase 2 — Catálogo de casos

**Objetivo.** Modelo de caso como vista versionada sobre evidencia, con afirmaciones e interpretaciones explícitas. Cargar un archivo histórico no trivial.

**Incluye.**
- Implementación de ADR-0007 (claims).
- Implementación parcial de ADR-0010 (lifecycle de caso) — al menos los estados `draft`, `published`, `revised`.
- Importadores específicos para al menos un archivo público (Blue Book, GEIPAN público, o equivalente).

**No incluye.**
- Hipótesis competidoras formalizadas (eso es F3).
- Conclusiones cuantitativas.

**Demo de cierre.** Externo carga selección de Blue Book, navega casos, verifica que cada afirmación tiene fuente trazable.

### Fase 3 — Hipótesis y confianza

**Objetivo.** Sistema explícito de hipótesis competidoras y cuantificación de incertidumbre.

**Incluye.**
- Implementación de ADR-0008 (hipótesis competidoras).
- Implementación de ADR-0009 (incertidumbre y confianza).
- Implementación de ADR-0021 (no fabricación por LLM) si se usan modelos auxiliares.

**No incluye.**
- Grafo de conocimiento cross-case.
- Motores temporal/geoespacial avanzados.

**Demo de cierre.** Externo selecciona un caso F2 con varias hipótesis típicas (identificación errónea, fenómeno atmosférico, error de observador, no caracterizado), las evalúa con la evidencia del caso, y obtiene una distribución de confianza con evidencia favorable y contradictoria explícita por hipótesis.

### Fase 4 — Motores temporal y geoespacial

**Objetivo.** Reconstrucción de líneas de tiempo multi-fuente y proyección geoespacial de testimonios con incertidumbre.

**Incluye.**
- ADR-0012 (timeline engine).
- ADR-0013 (geospatial engine).
- Visualización con incertidumbre explícita (no líneas finas mentirosas — ver P3 ADR-0000).

**No incluye.**
- Grafo de conocimiento.
- API pública.

**Demo de cierre.** Externo reconstruye la cronología de un caso multi-testigo y obtiene un mapa con regiones de incertidumbre.

### Fase 5 — Grafo de conocimiento

**Objetivo.** Cruzar entidades (personas, organizaciones, lugares, eventos, documentos, hipótesis) entre casos.

**Incluye.**
- ADR-0011 (knowledge graph).
- ADR-0018 (búsqueda).
- Implementación de exportadores citables del grafo.

**Demo de cierre.** Externo identifica relaciones no obvias entre ≥10 casos históricos: testigos comunes, lugares recurrentes, organizaciones que aparecen en investigaciones independientes.

### Fase 6 — Workflows de investigación reproducible

**Objetivo.** Cualquier conclusión publicada por un usuario debe ser reproducible por un revisor externo desde un snapshot citable.

**Incluye.**
- ADR-0017 (API) completada para acceso programático.
- Workflows de exportación de snapshots citables (Zenodo, IPFS opcional, disco).
- Documentación de revisión por pares.

**Demo de cierre.** Un revisor externo reproduce un análisis publicado por otro usuario desde un snapshot citable, sin asistencia, en menos de 60 minutos. Si el resultado coincide bit a bit, F6 cierra y el sistema entra en estado de mantenimiento maduro.

## Consecuencias

**Positivas**
- Cada fase entrega algo útil aislado. El proyecto sobrevive si se interrumpe en cualquier fase tras F1.
- Aprendizaje retroalimentado evita comprometer arquitectura sobre supuestos no validados.
- Demo de cierre es un test brutalmente honesto sobre si la fase está realmente lista.
- Fácil de comunicar a colaboradores externos: "¿en qué fase estás?".

**Negativas**
- Las fases tardías (grafo, API, workflows) parecen muy lejanas. Riesgo de impaciencia interna.
- No hay paralelización: el calendario es secuencial y largo.
- Casos legacy interesantes esperan hasta F2. Hasta entonces solo se ingesta evidencia suelta.

**Neutras**
- El orden es modificable solo por ADR de enmienda explícita. No se reordena por gusto.

## Alternativas consideradas

### A. Vertical slices por caso completo
**Descripción:** Implementar un caso de extremo a extremo (con su evidencia, hipótesis, conclusión, geo, timeline, grafo) antes de generalizar.
**Razón de rechazo:** Tienta a sobre-ajustar el modelo a un caso particular. Reproduce el modo de fallo de muchos archivos del campo: estructuras hechas para un caso famoso que no generalizan.

### B. Capacidades en paralelo
**Descripción:** Equipos distintos trabajan timeline, grafo y modelo simultáneamente.
**Razón de rechazo:** No hay equipos. Y aunque los hubiera, las decisiones de capa N+1 dependen estructuralmente de N. El paralelismo crearía contradicciones que cuesta más resolver que ganar.

### C. MVP minimalista total
**Descripción:** Un único MVP que toque todo a profundidad mínima.
**Razón de rechazo:** Modelos de evidencia mal hechos son irreversibles. Si la F1 queda débil para alcanzar F6 rápido, todo lo demás hereda esa debilidad.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P8, P9.

**Cómo se alinean:**
- P2 (trazabilidad) y P5 (reproducibilidad): la demo de cierre de cada fase es una prueba directa de ambas.
- P8 (documentación al mismo nivel que el código): una fase no cierra si su documentación no permite a un externo ejecutarla.
- P9 (fuentes públicas como primarias): cada demo de cierre usa fuentes públicas para que un externo pueda replicar sin acceso privilegiado.

**Tensión:** Linealidad estricta vs. flexibilidad. Aceptada: el coste de retractar decisiones de fase posterior tomadas sobre supuestos no validados es mayor que el coste de avanzar lento.

## Referencias

- Brooks, F. P. (1995). *The Mythical Man-Month.* (Sobre por qué paralelizar no escala linealmente.)
- Christensen, C. M. (1997). *The Innovator's Dilemma.* (Sobre por qué entregar algo útil aislado en cada fase importa.)
- `orbital-sentinel` ADRs sobre fases, como prior art en el estilo de este proyecto.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
