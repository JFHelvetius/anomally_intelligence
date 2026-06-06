# ADR-0025: Neutrality Clarification — qué tipo de neutralidad ofrece el sistema

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0008, ADR-0011

---

## Contexto

P4 del ADR-0000 enuncia "neutralidad de hipótesis" como propiedad irrenunciable: "el sistema no privilegia arquitectónicamente ninguna hipótesis sustantiva sobre el origen de los fenómenos". El Red Team Review desmonta esta promesa en tres ejes:

- **§1.1** La taxonomía de familias de hipótesis (`misidentification_natural`, `observer_error`, `non_human_intelligence`, etc.) refleja categorías occidentales analíticas contemporáneas. Tradiciones cosmológicas distintas no encuentran hogar limpio en `other` sin pérdida.
- **§1.3** El modelo `HypothesisSet` presupone hipótesis competidoras independientes; composiciones causales y entrelazamientos lógicos no caben.
- **§3.2** La exigencia de `FalsifiabilityClause` operativa privilegia estructuralmente hipótesis con asociación a evidencia accesible —que son, no por casualidad, las hipótesis ordinarias (globos, errores). La neutralidad "estructural" produce sesgo "estructural" hacia lo prosaico.

El ADR-0008 admitía la familia `non_human_intelligence` simétricamente a las demás. El Red Team Review observa correctamente que la simetría taxonómica no es lo mismo que neutralidad: la operacionalización (qué cuenta como falsable, qué evidencia se considera relevante, qué vocabulario se usa) introduce sesgos sustantivos antes de que el curador llegue.

Este ADR **no debilita P4**. Reformula qué tipo de no-favoritismo ofrece el sistema, declara los sesgos que persisten, y elimina el lenguaje de "neutralidad pura" del vocabulario del proyecto.

## Decisión

Se reemplaza el término "neutralidad" por **"no-favoritismo estructural"** en toda comunicación del proyecto, con declaración explícita de cuatro sesgos remanentes que el sistema **admite operar pero no resolver**.

P4 queda reformulada operativamente:

> **P4 (reformulada).** El sistema no provee mecanismos arquitectónicos que privilegien una hipótesis sustantiva sobre otra: no hay rankings editoriales, ni pesos por defecto sobre familias, ni flags semánticamente cargados. El sistema **sí** introduce sesgos epistémicos derivados de su marco analítico declarado. Esos sesgos se nombran explícitamente y permanecen como limitación reconocida.

El cambio es de **superficie semántica**, no de mecanismo. Los mecanismos del ADR-0008 se conservan. Lo que se elimina es la pretensión de objetividad pura.

## Los cuatro sesgos reconocidos

### Sesgo S1. Marco analítico occidental contemporáneo

Las cinco categorías epistémicas (Fact, Claim, Interpretation, Hypothesis, Conclusion) son herramientas de la tradición intelectual eurocéntrica post-Ilustración. Aplicarlas a relatos de tradiciones que no las separan es una imposición.

**Operativamente:**

- Reportes provenientes de tradiciones cosmológicas distintas (animistas, shamánicas, religiosas, mitológicas) **pueden ingestarse** como `Claim` con preservación íntegra del enunciado original y su contexto cultural en `Claim.context`.
- La categorización epistémica del enunciado nunca sustituye al enunciado mismo. El predicado natural en idioma original (ADR-0007) protege contra esa pérdida.
- El campo `Claim.context.cultural_frame` se introduce como subcampo opcional para registrar el marco cosmológico declarado por el afirmante o por el curador. Ese campo es **descriptivo**, no clasificatorio: no afecta la evaluación de hipótesis.

**Limitación declarada.** El sistema no produce un equivalente funcional al marco analítico desde otras tradiciones. Investigadores que operen desde marcos distintos pueden encontrar pérdidas que el sistema reconoce no resolver.

### Sesgo S2. Sesgo de falsabilidad operativa

ADR-0008 exige que toda `Hypothesis` declare `FalsifiabilityClause` con cláusula `in_practice` operativa. Hipótesis sin falsabilidad operativa quedan como `Conjecture`, categoría auxiliar fuera del sistema competitivo.

El Red Team Review identifica correctamente que este filtro **sesga hacia hipótesis con asociación a evidencia accesible**. Esas hipótesis son, mayoritariamente, las que el campo llama "prosaicas": identificación errónea, fenómeno atmosférico, error del observador, fabricación deliberada. Hipótesis sustantivas más exóticas suelen ser difíciles de formular con falsabilidad operativa rigurosa.

**Operativamente:**

- La categoría `Conjecture` se mantiene como **categoría legítima**, no como descalificación. Una `Conjecture` se preserva en el sistema con su autoría, su enunciado, y su razón por la que no admite falsabilidad operativa actual.
- Una `Conjecture` puede ser citada por una `Conclusion` como "hipótesis no evaluada en este conjunto por falta de falsabilidad operativa actual". Esta cita preserva la existencia de la conjetura sin admitirla al sistema competitivo.
- El sistema **no afirma** que una hipótesis sin falsabilidad sea menos verdadera. Afirma que el sistema **no sabe evaluarla** con sus mecanismos actuales.

**Limitación declarada.** El sistema no es neutral sobre qué cuenta como hipótesis evaluable. Su criterio de evaluabilidad (falsabilidad operativa) excluye a candidatas que otras tradiciones epistemológicas legitimarían.

### Sesgo S3. Sesgo de independencia entre hipótesis

ADR-0008 modela hipótesis dentro de `HypothesisSet` como competidoras. El modelo formal no captura:

- **Composición causal**: el evento puede deberse a la conjunción de dos causas (un globo más una percepción sesgada por exposición previa). ADR-0008 reconoce `composite` como familia pero el motor de confianza ADR-0009 no soporta evaluación probabilística sobre composiciones.
- **Entrelazamiento lógico**: hipótesis no mutuamente excluyentes que comparten supuestos.
- **Jerarquías de hipótesis**: una hipótesis general (`fenómeno atmosférico raro`) puede tener sub-hipótesis específicas (`rayo en bola`, `halo óptico`) cuya evaluación independiente es teóricamente posible pero operativamente compleja.

**Operativamente:**

- En V1 (ADR-0023) ni `HypothesisSet` ni `Conclusion` se implementan. La limitación es **teórica** hoy.
- Cuando se implementen, el modelo se documenta como "hipótesis tratadas como competidoras independientes". Cualquier composición o entrelazamiento se modela como **hipótesis compuesta nueva**, no como combinación dinámica de hipótesis simples.
- La distribución de confianza Kent se asigna sobre el conjunto cerrado de hipótesis listadas. No hay regla de inferencia que componga confianzas de hipótesis simples para inducir confianza de hipótesis compuesta.

**Limitación declarada.** Investigadores que requieran modelado bayesiano con dependencias estructurales encontrarán el motor de confianza insuficiente. El sistema soporta sus análisis como `QuantitativeAssessment` opcional (ADR-0009 nivel 3) pero no como ciudadano del modelo central.

### Sesgo S4. Sesgo de vocabulario controlado

ADR-0011 mantiene vocabulario controlado para `Concept` con jerarquía SKOS. Cualquier vocabulario controlado refleja a quien lo cura. Términos privilegiados se vuelven sondas de búsqueda; términos ausentes se vuelven invisibles.

**Operativamente:**

- El vocabulario controlado se versiona y queda público. Sus omisiones son auditables.
- Se mantiene un **registro de términos rechazados o aplazados** (`docs/vocabulary/rejected.md`) con razón de rechazo y autor. Esto convierte la decisión en visible.
- Términos de tradiciones no occidentales se incluyen cuando la documentación de la tradición lo permite, con atribución explícita y enlace a la documentación primaria.

**Limitación declarada.** El vocabulario controlado no es ontología universal. Es el mapa de un mantenedor (o pocos mantenedores) en una época. Su uso impone sesgo de visibilidad.

## Sobre la palabra "neutralidad"

A partir de este ADR, el proyecto **no usa "neutralidad" sin cualificación** en su comunicación pública. Los términos sustitutivos:

- **"No-favoritismo estructural"** para describir lo que el mecanismo arquitectónico provee.
- **"Sesgo declarado"** para nombrar los sesgos S1–S4 explícitamente.
- **"Honestidad sobre marco"** para describir el compromiso operativo.

El ADR-0000 conserva el lenguaje histórico "neutralidad" por estabilidad del documento fundacional, pero su sección de propiedad P4 ahora **referencia este ADR-0025 para la operacionalización vigente**. La actualización al ADR-0000 es por enmienda explícita en su pie, no por reescritura del cuerpo.

## Consecuencias

**Positivas**
- El proyecto deja de prometer lo que no entrega.
- Sesgos se vuelven auditables.
- Operadores de tradiciones distintas saben qué pueden esperar y qué no.
- Crítica externa tiene puntos concretos a los que apelar.

**Negativas**
- El marketing del proyecto pierde la palabra "neutral", que es comercialmente útil.
- Algunos lectores interpretarán la declaración de sesgos como debilidad cuando es solidez.
- Más documentación que mantener.

**Neutras**
- Los mecanismos del sistema no cambian. Lo que cambia es el discurso sobre ellos.

## Declaración de limitaciones

El proyecto **no afirma** que su marco epistémico sea óptimo, universal o libre de sesgo. Afirma que es:

- **Explícito** (los sesgos están nombrados).
- **Auditable** (cualquier observador puede chequear su operación).
- **Revisable** (los sesgos pueden replantearse por ADR posterior si emerge consenso).

Investigadores que requieran neutralidad en sentido fuerte deberían diseñar sistema propio.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único, la elección de qué cuenta como "sesgo declarado" depende del mantenedor mismo. Esto es problemático: el sesgo del mantenedor sobre qué considerar sesgo no se autocorrige.

Mitigación:

- Los sesgos S1–S4 se exponen y se documentan **por escrito**, no por convención.
- Cualquier hallazgo externo de sesgo no documentado se acepta como contribución al ADR-0025 mediante PR de enmienda.
- Las revisiones anuales del ADR-0000 incluyen revisión de S1–S4 con instrucción explícita al revisor de buscar sesgos no documentados.

## Alineación con ADR-0000

**Propiedades afectadas:** P4 (reformulada operativamente), P1 (separación epistémica).

**Cómo se alinea:** este ADR **fortalece** P4 al hacerla operacionalmente honesta. Una propiedad que admite sus sesgos es más robusta que una que los oculta detrás de lenguaje absoluto.

**Tensión:** el ADR-0000 conserva el término "neutralidad" en su redacción original. Esta tensión se resuelve por enmienda al pie del ADR-0000 que referencia ADR-0025 como operacionalización vigente del término.

## Enmienda al ADR-0000

Como parte de la aceptación de este ADR, se añade al historial de enmiendas del ADR-0000 la siguiente entrada:

> *2026-06-04 — AIP autor fundador:* La propiedad P4 ("neutralidad de hipótesis") se interpreta operativamente conforme a ADR-0025 (Neutrality Clarification). El término "neutralidad" se conserva en el cuerpo del ADR-0000 por estabilidad documental, pero su operacionalización en el sistema corresponde a "no-favoritismo estructural" con cuatro sesgos declarados (S1–S4).

## Referencias

- `docs/reviews/adr_red_team_review.md`, secciones §1.1, §1.3, §3.2.
- Smith, L. T. (1999). *Decolonizing Methodologies.*
- Feyerabend, P. (1975). *Against Method.* (Sobre el filtro de falsabilidad como filtro institucional.)
- Lakatos, I. (1970). *Falsification and the Methodology of Scientific Research Programmes.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
