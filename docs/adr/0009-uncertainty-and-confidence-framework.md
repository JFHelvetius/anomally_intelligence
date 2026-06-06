# ADR-0009: Marco de incertidumbre y confianza

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0006, ADR-0007, ADR-0008

---

## Contexto

P3 del ADR-0000 establece que la incertidumbre es ciudadano de primera clase del sistema. ADR-0008 establece que las hipótesis viven en conjuntos competidores. Falta un marco operativo que diga **cómo** se cuantifica la confianza relativa entre hipótesis, **cómo** se actualiza al aparecer nueva evidencia, y **cómo** se exhibe sin colapsar en una sola cifra mentirosa.

El campo del estudio de fenómenos anómalos usa históricamente dos extremos:

1. **Confianza binaria** ("caso identificado" / "caso inexplicable"). Pierde toda la estructura.
2. **Scores únicos** (ej. NICAP usaba un sistema de 7 niveles). Esconde el porqué del score.

Ambos modos colapsan información operativa. El sistema necesita un marco que:

- Permita representar distribuciones, no solo puntos.
- Preserve por qué la confianza es la que es: evidencia favorable, contradictoria, supuestos, preguntas abiertas.
- Soporte actualización trazable: cómo cambió la confianza con la nueva evidencia E, en qué fecha, por quién.
- Tolere incertidumbre de segundo orden: no solo "P(H)=0.3" sino "qué confianza tenemos en ese 0.3".

## Decisión

El sistema adopta un marco de incertidumbre con tres niveles:

1. **Soporte evidencial estructurado** — para cada hipótesis del conjunto, la lista versionada de `EvidenceLink`s favorables y contradictorios. Este nivel no produce número; produce estructura legible.

2. **Distribución de confianza cualitativa** — escala ordinal Kent-style con anclajes verbales explícitos. Default del sistema. No requiere modelado probabilístico avanzado.

3. **Distribución de confianza cuantitativa (opcional)** — para usuarios avanzados, distribuciones sobre hipótesis con su propia incertidumbre de segundo orden (intervalos de credibilidad sobre la propia distribución). Optativo, marcado explícitamente como tal.

Los tres niveles **coexisten**: el nivel 1 es siempre obligatorio. El nivel 2 es el default. El nivel 3 es opcional pero, cuando se usa, no reemplaza al 1.

Una conclusión se entrega siempre con los cinco elementos exigidos por P3:
- Confianza (en cualquiera de los tres niveles).
- Evidencia favorable.
- Evidencia contradictoria.
- Supuestos.
- Preguntas abiertas.

Si falta cualquiera de los cinco, no es una conclusión válida del sistema. Es un bug.

## Modelo

### EvidenceLink

Cada vínculo entre evidencia y hipótesis es un objeto explícito, no implícito.

```
EvidenceLink {
  id: EvidenceLinkId
  hypothesis_id: HypothesisId
  evidence_ref: EvidenceRef | ClaimRef
  direction: LinkDirection   # supports | contradicts | inconclusive
  weight_qualitative: KentLevel?  # ver enumeración
  weight_quantitative: float?     # opcional, en [-1, 1] o [0, 1] según convención declarada
  assessor: ActorId
  assessed_at: timestamp
  rationale: markdown        # por qué el assessor cree que esta evidencia soporta/contradice
  supersedes: EvidenceLinkId?  # si reemplaza un link anterior
  schema_version: SemVer
}
```

**Observaciones clave:**

- `rationale` es obligatorio. Sin razón explícita no hay link. Esto frena automáticamente la práctica del campo de "agregar la foto X al caso Y" sin decir por qué la foto soporta o contradice una hipótesis.
- `supersedes` permite encadenar reasignaciones: un assessor previo dijo "supports", uno posterior dijo "inconclusive", la cadena queda visible.
- `inconclusive` es un valor legítimo, no un mero ausencia.

### Escala Kent (nivel 2 cualitativo)

Adopción adaptada de la escala de Sherman Kent (CIA) y refinamientos posteriores. Siete niveles ordinales con anclajes verbales y rangos cuantitativos sugeridos (no obligatorios).

| Etiqueta | Rango sugerido | Significado verbal |
|---|---|---|
| `almost_certainly_not` | 0–5% | Existe evidencia rotunda en contra. |
| `very_unlikely` | 5–20% | Evidencia significativa en contra; alguna a favor. |
| `unlikely` | 20–40% | Más evidencia en contra que a favor. |
| `even_chance` | 40–60% | Evidencia equilibrada o insuficiente para decidir. |
| `likely` | 60–80% | Más evidencia a favor que en contra. |
| `very_likely` | 80–95% | Evidencia significativa a favor. |
| `almost_certain` | 95–100% | Evidencia rotunda a favor. |

Adicionalmente, dos etiquetas no probabilísticas:

| Etiqueta | Significado |
|---|---|
| `insufficient_data` | No hay material suficiente para asignar nivel sin fabricar. |
| `not_evaluated` | Aún no se ha evaluado. |

`insufficient_data` no se traduce a "0.5". Son cosas distintas y el sistema preserva la distinción.

### Distribución cuantitativa (nivel 3 opcional)

Cuando se activa explícitamente, el sistema admite distribuciones discretas sobre hipótesis del conjunto.

```
QuantitativeAssessment {
  set_id: HypothesisSetId
  distribution: {HypothesisId: float}   # suma a 1.0
  second_order_credibility: {HypothesisId: [float, float]}?  # intervalo de credibilidad sobre cada P(H)
  method: AssessmentMethod              # ver enumeración
  evidence_ids_used: [EvidenceLinkId]   # qué evidence links se incorporaron
  assessor: ActorId
  assessed_at: timestamp
  reproducibility: ReproducibilityInfo  # código, parámetros, seed si aplica
  schema_version: SemVer
}
```

`AssessmentMethod` incluye `expert_elicitation`, `bayesian_update`, `dempster_shafer`, `weighted_likelihood`, `ad_hoc`. Cada método declara sus parámetros con suficiente detalle para reproducir el cálculo.

`second_order_credibility` captura confianza en la propia distribución. No es ornamento: una P(H)=0.3 con intervalo [0.05, 0.6] dice algo muy distinto que una P(H)=0.3 con intervalo [0.28, 0.32].

### Conclusion

```
Conclusion {
  id: ConclusionId
  hypothesis_set_id: HypothesisSetId
  assessment_qualitative: {HypothesisId: KentLevel}   # obligatorio
  assessment_quantitative: QuantitativeAssessment?    # opcional
  supporting_evidence: {HypothesisId: [EvidenceLinkId]}
  contradicting_evidence: {HypothesisId: [EvidenceLinkId]}
  assumptions_in_play: [AssumptionId]
  open_questions: [str]
  rationale: markdown
  author: ActorId
  authored_at: timestamp
  supersedes: ConclusionId?
  schema_version: SemVer
}
```

Una `Conclusion` **siempre** referencia un `HypothesisSet`, nunca una sola hipótesis suelta (refuerzo de ADR-0008).

Una `Conclusion` no muta. Si cambia la evidencia, se publica una `Conclusion` nueva con `supersedes` apuntando a la anterior. Ambas siguen citables.

### Propagación al cambiar evidencia

Cuando una `Evidence` cambia de `status` (ADR-0006) — por ejemplo, pasa a `retracted`:

- Cada `EvidenceLink` que la referencia se marca automáticamente como `affected_by_status_change`.
- Cada `Conclusion` que dependía de esos links se marca como `affected`.
- El sistema **no recomputa automáticamente** las conclusiones. Las marca como "afectadas, requiere revisión". La recomputación es un acto humano explícito que produce una `Conclusion` nueva con `supersedes`.

Esta política protege la trazabilidad: ningún recálculo silencioso. El historial muestra cuándo y por qué cambió la confianza.

## Justificación

### Por qué tres niveles en lugar de uno

Forzar a todos los casos a nivel 3 (cuantitativo) reproduce el modo de fallo del campo: scores únicos sin estructura. Forzar a todos los casos a nivel 2 (Kent) impide a investigadores avanzados publicar análisis probabilísticos rigurosos. La estratificación es el compromiso: estructura obligatoria, cuantificación opcional.

### Por qué Kent en lugar de números directos

Las palabras llevan menos pretensión de precisión que los números. "very_likely" es honesto sobre su rango; "0.87" no lo es. El campo se beneficia de honestidad de granularidad.

### Por qué `rationale` obligatorio en `EvidenceLink`

Sin esto, el sistema se llena rápidamente de links no auditados ("X soporta H" sin explicar por qué). La obligatoriedad introduce fricción pero garantiza calidad.

### Por qué no recálculo automático

El recálculo automático suena conveniente y es destructivo. Las conclusiones publicadas en momentos anteriores pierden su contexto si se sobrescriben. La marca "afectada" es información honesta; la recomputación silenciosa es deshonestidad.

### Por qué `insufficient_data` distinto de `even_chance`

Confundirlos es el error que más caro se paga en el campo. "No sé" no es lo mismo que "50/50". El sistema preserva la distinción a nivel de tipo.

## Consecuencias

**Positivas**
- Cualquier conclusión del sistema lleva su contexto epistémico completo.
- Diferentes usuarios con expertise distinta pueden contribuir al mismo conjunto (uno aporta nivel 2 cualitativo, otro aporta nivel 3 cuantitativo) sin conflicto.
- La superposición de conclusiones a lo largo del tiempo es legible: el sistema responde "¿qué pensábamos del caso C en 2031?" con la conclusión exacta de entonces.
- Propagación de cambio de status es informativa sin ser destructiva.

**Negativas**
- Curva de aprendizaje para investigadores acostumbrados a "porcentaje único".
- El espacio de datos crece con el historial de `EvidenceLink`s y `Conclusion`s.
- La obligatoriedad de `rationale` filtra contribuciones perezosas. Eso es deseable, pero reduce el flujo bruto.

**Neutras**
- Visualizaciones de incertidumbre son obligatoriamente más ricas (y por lo tanto más densas) que un gauge de un solo número.

## Alternativas consideradas

### A. Solo cuantitativo bayesiano
**Descripción:** Forzar a todos los casos a llevar P(H) con priors y likelihoods.
**Razón de rechazo:** Esconde supuestos en priors. Excluye material histórico donde el modelado probabilístico es artificioso.

### B. Solo cualitativo
**Descripción:** Renunciar a nivel 3.
**Razón de rechazo:** Impide análisis serios que el campo necesita.

### C. Recomputación automática al cambiar evidencia
**Descripción:** Cada cambio de status recalcula confianza.
**Razón de rechazo:** Destruye historial. La trazabilidad bit a bit exige que cada conclusión sea acto explícito de un autor.

### D. Score único con ponderaciones internas
**Descripción:** Una función combinatoria sobre links que produce un número.
**Razón de rechazo:** Esconde la ponderación. Inauditable. Crea ilusión de objetividad.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P4, P5, P10.

**Cómo se alinean:**
- P3 (incertidumbre cuantificada como first-class): operacionalización primaria.
- P2 (trazabilidad) y P5 (reproducibilidad): cada conclusión cita exactamente qué links usó, cada link es citable por hash.
- P4 (neutralidad): la escala Kent no privilegia ninguna hipótesis; la cuantitativa es opcional y simétrica.
- P10 (no fabricación): `insufficient_data` previene el modo de fallo de inventar 0.5 cuando no hay base.

**Tensión:** Friction adicional vs. claridad. Aceptada: el proyecto existe para producir conclusiones defendibles, no rápidas.

## Referencias

- Kent, S. (1964). *Words of Estimative Probability.*
- Heuer, R. J. (1999). *Psychology of Intelligence Analysis.*
- Tetlock, P. E., & Gardner, D. (2015). *Superforecasting.*
- Pearl, J. (2009). *Causality.*
- Dempster, A. P. (1968). *A generalization of Bayesian inference.*
- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
