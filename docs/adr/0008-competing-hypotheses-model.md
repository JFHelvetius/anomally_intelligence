# ADR-0008: Modelo de hipótesis competidoras

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0006, ADR-0007, ADR-0009

---

## Contexto

La pregunta central del proyecto (ADR-0000) reformula "¿qué es esto?" como "¿qué nivel de confianza podemos asignar, con honestidad epistémica, a cada hipótesis competidora?". Para que esa reformulación sea operativa y no retórica, el sistema necesita un modelo formal de **hipótesis competidoras**.

El método **Analysis of Competing Hypotheses (ACH)**, desarrollado por Richards Heuer en la CIA y publicado abiertamente, es la referencia operativa más cercana. ACH parte de tres principios:

1. Listar todas las hipótesis razonablemente plausibles **antes** de evaluar evidencia.
2. Evaluar cada evidencia contra **todas** las hipótesis simultáneamente (no solo contra la hipótesis favorita).
3. Trabajar para **refutar** hipótesis, no para confirmar la preferida.

Estos tres principios son exactamente lo que el campo del estudio de fenómenos anómalos sufre por ausencia: la mayoría de los archivos evalúan evidencia contra una hipótesis "interesante" y descartan las "aburridas" implícitamente.

AIP adopta una variante formalizada de ACH como modelo arquitectónico de hipótesis. La variante incluye dos extensiones que ACH original deja informales: incertidumbre cuantificada en la evaluación de evidencia-vs-hipótesis, y trazabilidad bit a bit de cada evaluación.

## Decisión

El sistema modela hipótesis como entidades de primera clase, agrupadas en **conjuntos competidores** (`HypothesisSet`) por caso o por contexto investigador. Cada hipótesis declara:

- Su contenido sustantivo.
- Sus condiciones de falsabilidad.
- Sus supuestos.
- Su distribución de confianza actual (siempre con evidencia favorable y contradictoria explícitas).

Las **conclusiones** (ADR-0009) operan sobre `HypothesisSet`, no sobre hipótesis individuales. Esta restricción arquitectónica fuerza la evaluación competitiva.

Una hipótesis **nunca se elimina** del sistema. Su confianza puede caer arbitrariamente cerca de cero, pero el nodo permanece, citable y reevaluable.

## Modelo

```
Hypothesis {
  id: HypothesisId                 # ULID estable
  set_id: HypothesisSetId          # conjunto competidor al que pertenece
  short_label: str                 # etiqueta corta para UI ("identificación errónea — globo")
  statement: markdown              # enunciado completo en lenguaje natural
  proponent: ActorId?              # quién propuso la hipótesis (puede ser nulo si es estándar)
  proposed_at: timestamp

  falsifiability: FalsifiabilityClause   # qué la falsearía
  required_assumptions: [Assumption]     # qué supuestos necesita
  predicted_evidence: [PredictedEvidence] # qué evidencia esperaríamos si fuese cierta

  status: HypothesisStatus         # ver enumeración
  family: HypothesisFamily         # ver enumeración (etiqueta no excluyente)

  schema_version: SemVer
  notes: markdown?
}

HypothesisSet {
  id: HypothesisSetId
  scope: HypothesisSetScope         # what binds these hypotheses together
  hypotheses: [HypothesisId]
  curator: ActorId
  created_at: timestamp
  exhaustiveness_claim: ExhaustivenessLevel  # ver enumeración
  open_residual: bool               # si el conjunto incluye explícitamente "ninguna de las anteriores"
  notes: markdown?
}
```

### FalsifiabilityClause

Sin condición de falsabilidad explícita, una hipótesis no entra en el sistema como `Hypothesis`. Entra como `Conjecture` (categoría auxiliar fuera del modelo competitivo) y no participa en evaluación de confianza.

```
FalsifiabilityClause {
  in_principle: markdown    # qué tipo de evidencia, hipotética, la falsearía
  in_practice: markdown     # qué evidencia accesible, real o potencialmente recuperable, la favorecería o la desfavorecería
  hard_constraints: [str]   # observaciones que la harían incompatible con el dataset (ej. "fue grabado simultáneamente desde otro ángulo")
}
```

El campo `in_principle` puede ser inalcanzable; el campo `in_practice` debe ser operativo con material plausiblemente accesible.

### Assumption

Supuestos requeridos. Cada uno con su propia evaluación.

```
Assumption {
  id: AssumptionId
  statement: markdown
  status: AssumptionStatus    # supported | unsupported | disputed | required_but_untested
  supporting_evidence: [EvidenceRef]
  contradicting_evidence: [EvidenceRef]
  notes: markdown?
}
```

Si un supuesto crítico cae, la hipótesis no se elimina pero su confianza se afecta automáticamente. La propagación se computa en el motor de confianza (ADR-0009), no en este ADR.

### PredictedEvidence

Predicciones operativas. Hace explícito qué buscaría un investigador si quisiera testar la hipótesis.

```
PredictedEvidence {
  id: PredictedEvidenceId
  description: markdown
  expected_kind: EvidenceKind?    # ADR-0006
  expected_temporal_window: TemporalWindow?
  expected_spatial_region: SpatialRegion?
  if_present_implies: SupportDirection  # supports | refutes | partial
  search_status: SearchStatus     # searched | partial | not_searched
}
```

### HypothesisStatus

| Status | Significado |
|--------|------------|
| `active` | Forma parte del conjunto competidor actual. |
| `dormant` | No descartada, pero sin evidencia reciente que la mueva. Permanece en el conjunto. |
| `provisionally_excluded` | Datos disponibles la hacen incompatible con el dataset. Permanece visible como histórico. |
| `superseded_by` | Reemplazada por una hipótesis más precisa (referencia obligatoria). |

`provisionally_excluded` **no es** "refutada definitivamente". Mantiene la hipótesis lista para reactivarse si nueva evidencia la favorece.

### HypothesisFamily

Etiqueta no excluyente para agrupación operativa. Una hipótesis puede pertenecer a varias familias. Las familias canónicas, por taxonomía del campo:

| Family | Ejemplo |
|--------|---------|
| `misidentification_natural` | Planeta, satélite Iridium, meteoro, fenómeno atmosférico |
| `misidentification_human_made` | Globo, avión convencional, dron, satélite, ensayo militar |
| `observer_error` | Memoria, percepción, expectativa, ilusión óptica |
| `deliberate_fabrication` | Engaño, broma, fraude |
| `instrument_artifact` | Reflejo de lente, hot pixel, glitch de radar, paralaje |
| `classified_human_technology` | Programa militar/inteligencia no público |
| `uncharacterized_natural` | Fenómeno natural no catalogado |
| `uncharacterized_human_made` | Tecnología humana no catalogada |
| `non_human_intelligence` | Hipótesis NHI / ETH / interdimensional / etc. |
| `composite` | Combinación de causas (ej. "globo identificado como X + memoria sesgada por exposición previa") |
| `data_insufficient` | El dato disponible no permite distinguir; cualquier hipótesis está sub-determinada |
| `other` | Hipótesis sustantiva fuera de las familias anteriores |

**La taxonomía no implica jerarquía de plausibilidad.** El sistema no privilegia arquitectónicamente ninguna familia (P4). La familia es etiqueta de agrupación, no peso.

### ExhaustivenessLevel del conjunto

| Level | Significado |
|-------|------------|
| `exhaustive_with_residual` | El curador afirma que las hipótesis listadas más "ninguna de las anteriores" (residual) cubren todo el espacio. |
| `representative` | Cubre las hipótesis razonables; reconoce que pueden existir más. |
| `partial` | El curador admite que el conjunto es parcial; cita razones. |

El campo `open_residual` obliga a la inclusión explícita de "ninguna de las hipótesis anteriores" como hipótesis residual en conjuntos `exhaustive_with_residual`. Sin residual, no hay exhaustividad real.

## Operaciones permitidas

- **Añadir hipótesis** a un conjunto: evento explícito con autoría y motivación.
- **Promover/demover status**: evento explícito, con evidencia que motiva el cambio.
- **Reemplazar hipótesis con superseded_by**: la antigua permanece; la nueva la referencia.
- **Eliminar hipótesis**: **no permitido**. Una hipótesis mal formulada se marca `superseded_by` apuntando a la versión corregida.

## Justificación

### Por qué `HypothesisSet` y no hipótesis sueltas

Evaluar confianza sobre una sola hipótesis es trivial y engañoso. La pregunta operativa es siempre relativa: P(H_i | evidencia) en un espacio de hipótesis competidoras. El tipo arquitectónico que materializa esa restricción es `HypothesisSet`.

### Por qué falsabilidad obligatoria

Sin falsabilidad declarada, una "hipótesis" es indistinguible de una afirmación dogmática. Esto incluye tanto a hipótesis NHI sin condiciones operacionales como a hipótesis "ordinarias" descritas tan vagamente que cualquier dato las acomoda. La cláusula `in_practice` filtra ambas.

### Por qué hipótesis nunca se eliminan

Una hipótesis descartada con la evidencia de hoy puede recuperarse con la evidencia de mañana. La eliminación rompe la trazabilidad histórica de cómo evolucionó el razonamiento. La marca `provisionally_excluded` cumple la función operativa de "no la consideres por ahora" sin destruir información.

### Por qué `predicted_evidence` es estructura, no prosa

Hace operativa la hipótesis. Convierte la formulación abstracta en programa de búsqueda. Identifica explícitamente qué buscar y, crucialmente, qué se ha buscado y qué no (search_status). Una hipótesis con todas sus predicciones marcadas `not_searched` es información valiosa sobre el estado de la investigación.

### Por qué la taxonomía de familias no implica jerarquía

P4 (neutralidad de hipótesis) es propiedad arquitectónica del sistema. Cualquier orden, color o peso por defecto que privilegie una familia sobre otra viola esta propiedad. Las familias se usan para agrupar y filtrar, no para evaluar.

## Consecuencias

**Positivas**
- Evaluación competitiva es estructura del modelo, no convención.
- Hipótesis "aburridas" (globos, identificaciones erróneas) reciben el mismo tratamiento estructural que hipótesis "interesantes" (NHI).
- Permite estudio de patrones meta: "¿cuántos casos tienen hipótesis NHI mantenida activa? ¿con qué evidencia?".
- Falsabilidad obligatoria filtra ruido.

**Negativas**
- Formular una hipótesis cuesta más esfuerzo que escribirla en prosa.
- Hipótesis tradicionales del campo a menudo no tienen falsabilidad operativa; estarán en `Conjecture` o requerirán reformulación.
- Curadores de conjuntos pueden manipular vía sesgo de selección.
- Riesgo de "exhaustividad teatral" con conjuntos `exhaustive_with_residual` que no cubren hipótesis razonables.

**Neutras**
- El sistema produce un volumen creciente de hipótesis dormidas y excluidas provisionalmente. La interfaz debe permitir filtrarlas sin ocultarlas.

## Alternativas consideradas

### A. Hipótesis sin conjuntos
**Descripción:** Cada hipótesis se evalúa aislada.
**Razón de rechazo:** Imposibilita evaluación competitiva. Reproduce la patología del campo.

### B. ACH puro de Heuer
**Descripción:** Adoptar ACH sin extensiones.
**Razón de rechazo:** ACH original no formaliza incertidumbre cuantificada ni trazabilidad bit a bit. AIP necesita ambas (P2, P3).

### C. Inferencia bayesiana automatizada
**Descripción:** Modelado bayesiano completo con priors y likelihoods auto-actualizados.
**Razón de rechazo:** Atractivo pero peligroso: oculta supuestos en priors arbitrarios. AIP necesita supuestos explícitos como objetos del sistema. La inferencia bayesiana puede usarse como **opción interna** del motor de confianza (ADR-0009), pero no es la única forma de evaluar.

### D. Eliminación física de hipótesis "refutadas"
**Descripción:** Liberar el espacio de hipótesis activas eliminando las refutadas.
**Razón de rechazo:** Destruye historial. Hace imposible reactivar con nueva evidencia.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P3, P4, P8, P10.

**Cómo se alinean:**
- P1: hipótesis como categoría con tipo propio.
- P3: confianza por hipótesis con evidencia favorable/contradictoria explícitas.
- P4: neutralidad estructural — las familias no llevan peso por defecto, ninguna hipótesis se privilegia.
- P10: las predicciones (`predicted_evidence`) son objetos explícitos, no narrativa generada.

**Tensión:** Falsabilidad obligatoria excluye hipótesis populares en el campo no formuladas con falsabilidad operativa. Aceptable: el sistema invita a reformularlas, no las prohíbe sustantivamente.

## Referencias

- Heuer, R. J. (1999). *Psychology of Intelligence Analysis.* (Capítulo de ACH.)
- Popper, K. (1934/1959). *The Logic of Scientific Discovery.* (Falsabilidad.)
- Tetlock, P. E., & Gardner, D. (2015). *Superforecasting.*
- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
