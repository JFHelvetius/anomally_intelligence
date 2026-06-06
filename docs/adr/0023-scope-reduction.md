# ADR-0023: Scope Reduction — recorte deliberado del alcance de V1

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0004, todos los ADR de modelo y motor

---

## Contexto

El Red Team Review del 2026-06-03 identificó como modo de fracaso dominante el **vaporware perpetuo**: un proyecto con 23 ADRs cuidadosamente razonados, un único mantenedor part-time, y un alcance declarado (seis fases, motor temporal, motor geoespacial, grafo, OSINT, ética, búsqueda multi-modo, API triple) que excede capacidad realista en cualquier horizonte razonable.

Los hallazgos concretos del review que disparan esta enmienda:

- **§9.1**: alcance excede capacidad de mantenedor único part-time; F1 sola requiere 6–12 meses full-time según estimación del propio review.
- **§10.1**: ecosistema presupuesto que adopte AIP no es claro que llegue antes de tener entregable.
- **§10.2**: citabilidad académica requiere validación que no ocurre sin software entregado.
- **§7.1, §7.2, §7.3**: superficies de API múltiples y búsqueda multi-modo añaden trabajo no requerido por la demo de cierre F1.
- **§5.1, §5.2, §5.3**: estrategia OSINT completa es trabajo de fases futuras.
- **§6.3**: CAOS basado en filesystem escala bien para archivos modestos; archivos masivos requieren capas adicionales.
- **§2.3**: P7 (portátil moderno) ya prefiere V1 modesta.

El ADR-0004 estableció seis fases en orden estricto y declaró que F1 no progresa hasta cerrar su demo. Este ADR-0023 **no supersede a ADR-0004**: lo refuerza con un compromiso adicional. Hace explícito que **solo F1 está comprometida** y que las ADRs posteriores describen diseño aceptado **sin compromiso de calendario de implementación**.

## Decisión

El alcance de V1 (primer release ejecutable del software) se reduce **deliberadamente y explícitamente** al subconjunto mínimo que sostiene la demo de cierre de Fase 1.

**V1 entrega:**

1. CLI `aip` con tres comandos: `evidence ingest`, `evidence show`, `archive verify`.
2. API Python equivalente para esos tres comandos.
3. Modelo de evidencia formal (ADR-0006) implementado en su núcleo: hash, kind, content_uri, source_id, status, ingested_at/by, schema_version.
4. Modelo de fuente y procedencia (ADR-0005) implementado a nivel suficiente para registrar una `Source` y una `Provenance` mínima por evidencia.
5. CAOS en filesystem (ADR-0015) con verificación de integridad por hash.
6. Almacenamiento Parquet de metadatos (ADR-0015) con esquema versionado.
7. Versionado del archivo (ADR-0016) con `ArchiveManifest` y URI scheme `aip:` para `evidence`.
8. Audit log append-only con hash chain (ADR-0019) para las acciones de los tres comandos.

**V1 NO entrega y NO promete entregar en horizonte definido:**

- Modelo de `Claim` (ADR-0007). Diseñado, no implementado.
- Modelo de `Hypothesis` ni `HypothesisSet` (ADR-0008). Diseñado, no implementado.
- Marco de incertidumbre y `Conclusion` (ADR-0009). Diseñado, no implementado.
- Ciclo de vida de `Case` (ADR-0010). Diseñado, no implementado.
- Grafo de conocimiento (ADR-0011). Diseñado, no implementado.
- Motor temporal (ADR-0012). Diseñado, no implementado.
- Motor geoespacial (ADR-0013). Diseñado, no implementado.
- Adquisidores OSINT (ADR-0014). Diseñado, no implementado.
- HTTP API (ADR-0017). Diseñado, no implementado.
- Búsqueda léxica o semántica (ADR-0018). Diseñado, no implementado.
- Enclave de material sensible (ADR-0019). Diseñado, no implementado.
- Mecanismo de takedown operativo (ADR-0020). Diseñado, no implementado.
- Asistencia LLM (ADR-0021). Diseñado, no implementado.

Estos ADRs **permanecen aceptados como diseño**. La distinción es explícita: un ADR aceptado define cómo se implementaría si y cuando se implemente; no compromete a implementarlo en plazo alguno.

## Justificación

### Por qué congelar el alcance es el acto más valioso ahora

El Red Team Review identifica con claridad el patrón de fracaso: un autor que disfruta diseñando produce volumen documental que termina por no validarse contra realidad. La única defensa estructural contra ese patrón es comprometerse públicamente con un entregable mínimo y rechazar estructuralmente el crecimiento de alcance hasta cerrarlo.

### Por qué tres comandos y no cinco

`evidence ingest`, `evidence show`, `archive verify` es el mínimo viable para la demo de cierre F1. Añadir `claim add`, `case create` u otros comandos sería ampliar alcance hacia F2 antes de cerrar F1, exactamente el modo que ADR-0004 prohíbe.

### Por qué solo CLI + API Python, sin HTTP

ADR-0017 declaró HTTP como opcional. Este ADR refuerza esa opcionalidad: HTTP **no se construye en V1**. Construirlo añade superficie API, autenticación, sandboxing de bind, tres áreas de trabajo sustancial sin contribuir a la demo de cierre F1.

### Por qué sin búsqueda

ADR-0018 mandata SQL/DuckDB como fuente autoritativa. La demo de cierre F1 no requiere FTS5 ni embeddings ni diccionario de sinónimos. Esos son trabajo de F5 y posteriores. Construirlos prematuramente repite el modo del Red Team Review: complejidad sin demanda demostrada.

### Por qué sin LLM auxiliar

ADR-0021 establece `LlmAssist` como categoría auxiliar con sistema de promoción. Esa infraestructura cuesta trabajo y no es prerrequisito de la demo F1. La ingestión inicial es manual: el usuario provee `source_id` y `provenance` literal.

### Por qué sin enclave de material sensible

ADR-0019 establece enclave para material no público. La demo de cierre F1 usa un PDF desclasificado público. Material sensible no aparece en F1. El enclave se construye cuando aparece el caso de uso.

### Por qué se aceptan los hallazgos §10.1 y §10.2 conscientemente

La adopción y la citabilidad académica son resultados, no inputs. Construirlos persiguiendo adoptantes que aún no existen es marketing antes de tener producto. El recorte de V1 acepta que no habrá adopción significativa hasta que la demo F1 esté ejecutable.

## Consecuencias

**Positivas**
- Probabilidad real de que F1 cierre con software ejecutable, no con más documentación.
- Defensa estructural contra el modo "vaporware perpetuo".
- El lector externo entiende qué hay implementado vs. qué es diseño aceptado.
- Las ADRs posteriores quedan como activo intelectual, no como deuda de implementación.

**Negativas**
- El alcance de V1 puede parecer poco ambicioso comparado con la documentación previa.
- Potenciales colaboradores motivados por funcionalidades de F2+ pueden desinteresarse.
- Casos de uso interesantes (cargar Project Blue Book como casos, evaluar hipótesis, mapear timeline) quedan **explícitamente fuera de V1**.

**Neutras**
- El diseño completo permanece. La transición a F2 cuando ocurra no requerirá rediseño.

## Declaración de limitaciones de V1

V1 **no es** una "plataforma de inteligencia anómala" en el sentido completo del nombre del proyecto. V1 es una **infraestructura de evidencia auditada**: ingesta un artefacto, lo direcciona por hash, registra procedencia, y permite verificar integridad.

Esa modestia es deliberada. La aspiración del proyecto sigue siendo la del ADR-0000; el camino para llegar es construir cimiento sólido antes de superestructura ambiciosa.

## Declaración de riesgo de mantenedor único

Este ADR es la primera defensa estructural contra el riesgo más serio identificado por el Red Team Review: un único mantenedor part-time intentando entregar alcance excesivo y terminando por entregar nada.

Aceptar el recorte de V1 reconoce públicamente que:

- El mantenedor único actual **no puede** entregar las seis fases del ADR-0004 en un horizonte razonable solo.
- El alcance de F2 en adelante depende de que el proyecto atraiga co-mantenedores o que el mantenedor cambie su disponibilidad.
- Ninguna de las dos condiciones se asume.

Ver ADR-0026 (Sustainable Stewardship) para operacionalización completa del riesgo.

## Alineación con ADR-0000

**Propiedades afectadas:** todas las P1–P12 conservadas. Ninguna debilitada.

**Cómo se alinea:**
- P5 (reproducibilidad), P11 (inmutabilidad), P2 (trazabilidad): V1 las implementa íntegramente para evidencia.
- P3 (incertidumbre), P4 (neutralidad de hipótesis), P10 (no fabricación): no son aplicables en V1 porque hipótesis no se implementan en V1; se preservan como diseño para fases futuras.
- P6 (local-first), P7 (coste cero): V1 las cumple trivialmente por su minimalismo.
- P8 (documentación): este ADR es la documentación honesta del recorte.
- P9 (fuentes públicas): la demo F1 usa una fuente pública.
- P12 (do-no-harm): V1 no toca material sensible.

**Tensión:** la modestia de V1 vs. la ambición del ADR-0000. Aceptada: la ambición es horizonte; V1 es paso ejecutable.

## Trigger de revisión

Este ADR se revisa cuando ocurra **alguno** de:

1. La demo de cierre F1 se ejecuta exitosamente por un externo. En ese momento, F2 entra en planificación con ADR de transición.
2. Aparece co-mantenedor sostenido. En ese momento se replantea el balance entre F1 y exploración paralela de F2 según capacidad real.
3. El mantenedor único declara abandono. En ese momento aplica ADR-0026 (Stewardship) y ADR-0027 (Graceful Archive).

Antes de cualquiera de esos tres eventos, el alcance no se amplía.

## Referencias

- `docs/reviews/adr_red_team_review.md`, secciones §2.3, §5.x, §6.3, §7.x, §9.1, §10.x, §12.
- Brooks, F. P. (1995). *The Mythical Man-Month.*
- ADR-0004 (arquitectura por fases): este ADR-0023 lo refuerza, no lo supersede.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
