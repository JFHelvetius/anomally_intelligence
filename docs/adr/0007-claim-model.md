# ADR-0007: Modelo de afirmación (claim)

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0005, ADR-0006, ADR-0008, ADR-0009

---

## Contexto

ADR-0001 estableció que **afirmación** (`Claim`) es una categoría epistémica distinta de hecho, interpretación, hipótesis y conclusión. Una afirmación es un enunciado atribuido a una fuente identificada, no necesariamente verificado.

En el campo del estudio de fenómenos anómalos, las afirmaciones son la mayoría del material disponible. La mayor parte de los archivos están construidos sobre testimonios, declaraciones de testigos, manifestaciones de oficiales militares, recogidas de prensa, declaraciones en programas de televisión, reportes redactados por organizaciones civiles. Tratar todo eso como hecho es la patología característica. Tratarlo como ruido es el extremo opuesto, igualmente erróneo.

El modelo de `Claim` debe permitir:

1. Atribuir cada afirmación a su fuente con trazabilidad estricta.
2. Distinguir entre lo que la afirmación dice del mundo y lo que dice sobre quien afirma.
3. Soportar afirmaciones contradictorias sin colapsarlas.
4. Permitir verificación posterior sin alterar el registro original de la afirmación.
5. Capturar incertidumbre del propio acto de afirmar (testigo titubeante, declaración bajo presión, traducción dudosa).

## Decisión

`Claim` es un tipo del modelo de datos con:

- Identidad estable.
- Atribución obligatoria a un actor (`attributed_to`).
- Anclaje a evidencia que materializa el acto de la afirmación.
- Contenido estructurado: el qué se afirma, distinguido del cómo se afirma.
- Verificación opcional, posterior, independiente.
- Capacidad de mantener afirmaciones contradictorias sobre el mismo evento sin fusionarlas.

Una afirmación nunca se promueve automáticamente a hecho. La verificación es un proceso explícito con autoría y evidencia, no una transición silenciosa.

## Modelo

```
Claim {
  id: ClaimId                      # ULID estable
  attributed_to: ActorId           # ADR-0005, obligatorio
  attributed_via: EvidenceRef      # evidencia que materializa la afirmación (declaración, transcripción, etc.)
  attributed_at: TemporalAnchor?   # cuándo fue afirmado (no cuándo ocurrió lo afirmado)

  predicate: ClaimPredicate        # estructura de qué se afirma
  about: [EntityRef]               # entidades sobre las que la afirmación versa
  scope: ClaimScope                # ver enumeración

  modality: ClaimModality          # certeza declarada por el afirmante
  context: ClaimContext            # condiciones del acto de afirmar
  language: BCP47                  # idioma del enunciado original

  verifications: [Verification]    # evaluaciones independientes posteriores
  contradicts: [ClaimRef]          # afirmaciones que contradice explícitamente
  supports: [ClaimRef]             # afirmaciones que refuerza explícitamente

  ingested_at: timestamp
  ingested_by: ActorId
  schema_version: SemVer
  notes: markdown?
}
```

### ClaimPredicate

El **qué** se afirma. Estructurado como un predicado tipado, no como texto libre. Tres formas soportadas:

1. **Predicado natural** (`natural_language`) — el enunciado original tal cual lo emitió el afirmante, sin parafrasear. Idioma original preservado.
2. **Predicado estructurado** (`structured`) — descomposición opcional sujeto-predicado-objeto con tipos referenciados al grafo de conocimiento. Útil para búsqueda. Es **derivado** del predicado natural, no lo reemplaza.
3. **Predicado eventual** (`event`) — para afirmaciones sobre eventos discretos: qué, cuándo, dónde, quién, con incertidumbre por componente.

Las tres formas pueden coexistir en el mismo `Claim`. El predicado natural es **obligatorio**; los demás son extracciones opcionales que requieren atribución de quien las extrajo y, si se generaron con asistencia de LLM, declaración explícita (ADR-0021).

### ClaimScope

Qué tipo de cosa afirma.

| Scope | Ejemplo |
|-------|---------|
| `factual` | "Vi un objeto a las 23:14 sobre el río." |
| `experiential` | "Sentí una vibración en el pecho cuando estaba cerca." |
| `interpretive` | "Pensé que era un avión militar por su forma." |
| `attributive` | "Mi compañero de tripulación también lo vio." |
| `denial` | "Niego haber dicho lo que reporta el periódico X." |
| `recollection_under_uncertainty` | "Creo recordar que ocurrió en marzo, pero podría ser abril." |
| `corrected` | "Lo que dije antes era erróneo; en realidad fue así." |

Esta clasificación **no juzga la veracidad** del contenido. Clasifica la naturaleza del acto de afirmar.

### ClaimModality

Cómo de seguro afirma el afirmante. Cinco niveles:

| Modality | Significado |
|----------|------------|
| `asserted_with_certainty` | El afirmante presenta el enunciado como seguro. |
| `asserted_with_qualification` | El afirmante introduce qualifiers ("creo que", "estoy bastante seguro"). |
| `tentative` | El afirmante presenta como suposición o conjetura propia. |
| `reported_speech` | El afirmante reporta lo que otro dijo, sin asumir. |
| `denied` | El afirmante explícitamente niega o se retracta. |

La modalidad se captura tal como aparece en el material fuente, sin normalizar.

### ClaimContext

Estructura sobre las condiciones bajo las que se hizo la afirmación. No es un retrato psicológico; son hechos circunstanciales del acto.

```
ClaimContext {
  setting: SettingKind?              # ver enumeración
  elapsed_since_event: Duration?     # cuánto tiempo pasó entre evento y afirmación
  prior_exposure: [EvidenceRef]      # qué material el afirmante había visto antes (si se sabe)
  duress_indicators: [str]           # coerción, hipnosis, presión legal, etc.
  language_of_record: BCP47          # idioma del registro
  translated_from: BCP47?            # si se afirmó originalmente en otro idioma
  translator: ActorId?
  notes: markdown?
}
```

`SettingKind` cubre `formal_testimony`, `media_interview`, `private_correspondence`, `informal_conversation`, `hypnotic_regression`, `court_deposition`, `psychiatric_evaluation`, etc.

`prior_exposure` es un campo crucial y subestimado en el campo. Una afirmación hecha después de ver durante años imágenes de un tipo concreto de fenómeno está estructuralmente sesgada en formas que el receptor debe poder evaluar.

### Verification

Evaluación independiente posterior. No mutila el `Claim`; lo acompaña.

```
Verification {
  verifier: ActorId
  verified_at: timestamp
  method: VerificationMethod
  evidence_used: [EvidenceRef]
  outcome: VerificationOutcome  # corroborated | contradicted | inconclusive | partial
  details: markdown
  open_questions: [str]
}
```

Múltiples `Verification` pueden coexistir, incluso con outcomes opuestos. Es información, no contradicción a resolver.

### Contradicciones y soportes

`contradicts` y `supports` son relaciones explícitas. El sistema **no fusiona** afirmaciones contradictorias en una "versión consensual". Las preserva como nodos distintos con la relación.

## Justificación

### Por qué predicado natural obligatorio

Cualquier extracción estructurada es lossy. Preservar el enunciado original en su idioma evita el modo de fallo de "el sistema dice que X afirmó Y" cuando lo que X afirmó realmente fue una cosa más matizada en su idioma original.

### Por qué `modality` y `context` separados

Confundir certeza declarada con condiciones del acto colapsa información valiosa. Una afirmación "con certeza" hecha bajo regresión hipnótica es muy distinta de una hecha en testimonio juramentado. Ambos hechos deben estar disponibles al lector.

### Por qué `prior_exposure` explícito

El modo de fallo "el testigo describe exactamente lo que ya había visto en TV" es endémico en el campo. Hacer este campo de primera clase obliga a que su ausencia sea visible, no asumida.

### Por qué no hay un `truth_value` global

Una afirmación no tiene valor de verdad propio; tiene relación con evidencia. El sistema rechaza el campo `is_true: bool` por la misma razón que rechaza `authenticity_score: float` en evidencia (ADR-0006).

### Por qué `contradicts` y `supports` son relaciones, no resoluciones

Las contradicciones entre testigos son datos. Resolverlas a priori (eligiendo el "más creíble") es una conclusión disfrazada de ingestión. La resolución vive en el plano de hipótesis y conclusiones (ADR-0008, ADR-0009).

## Consecuencias

**Positivas**
- Material de testimonio se preserva sin colapsar.
- Comparación entre afirmaciones contradictorias se vuelve operativa, no editorial.
- La estructura permite búsquedas sutiles: "afirmaciones tentativas sobre fenómenos lumínicos en USA en los 50".
- Soporta investigación de patrones de contexto (ej. afirmaciones bajo coerción legal vs. testimonio voluntario).

**Negativas**
- Ingestar una afirmación requiere más esfuerzo que un campo de texto.
- Riesgo de "ingestión perezosa": rellenar mínimo y dejar contexto vacío.
- Algunos colaboradores resistirán la obligatoriedad del predicado natural en idioma original.

**Neutras**
- Los campos opcionales son muchos; el lector debe entender que "vacío" significa "no documentado", no "no existió".

## Alternativas consideradas

### A. Claim como string
**Descripción:** Un campo de texto libre con atribución.
**Razón de rechazo:** Patología del campo.

### B. Claim con `truth_value`
**Descripción:** Atribuir verdad/falsedad como propiedad de la afirmación.
**Razón de rechazo:** Confunde planos. La verdad de una afirmación es relación con evidencia, no propiedad.

### C. Resolver contradicciones al ingestar
**Descripción:** Cuando dos afirmaciones contradicen, elegir la "más creíble" y descartar la otra.
**Razón de rechazo:** Es una conclusión disfrazada. Viola P1 y P4.

### D. Sin distinguir `scope` ni `modality`
**Descripción:** Modelo plano.
**Razón de rechazo:** Pierde la información más operativa del campo.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P3, P4, P10, P12.

**Cómo se alinean:**
- P1: este ADR define operacionalmente la categoría `Claim`.
- P3: `modality`, `context`, `verifications` cuantifican la incertidumbre del acto de afirmar.
- P4: contradicciones se preservan, no se resuelven editorialmente.
- P10: el predicado natural en idioma original previene fabricación por paráfrasis.
- P12: `duress_indicators` y trazabilidad del afirmante permiten gestionar testigos con respeto.

**Tensión:** Riqueza estructural vs. fricción de ingestión. Aceptada: la riqueza es necesaria para el caso de uso real.

## Referencias

- Toulmin, S. (1958). *The Uses of Argument.* (Esquema claim, data, warrant.)
- Loftus, E. F. (1979). *Eyewitness Testimony.* (Sesgos de testigo presencial.)
- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.*
- Walton, D. (1996). *Argumentation Schemes for Presumptive Reasoning.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
