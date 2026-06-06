# ADR-0021: No-fabricación por LLMs

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0006, ADR-0007, ADR-0009, ADR-0018

---

## Contexto

Los modelos de lenguaje grandes (LLMs) son herramientas potentes para tareas auxiliares de un sistema documental: extracción de entidades, sugerencia de clasificación, traducción aproximada, sumarización, transformación de formatos, extracción de campos estructurados desde prosa.

Y son herramientas peligrosas para un sistema epistémicamente disciplinado. Modos de fallo característicos:

- **Alucinación**: inventar contenido no presente en la fuente con apariencia de hecho.
- **Paráfrasis erosiva**: cambiar el sentido al reescribir.
- **Atribución incorrecta**: atribuir afirmaciones a actores que no las hicieron.
- **Confianza falsa**: producir output con tono asertivo sin base.
- **Sesgo de entrenamiento**: priorizar interpretaciones contemporáneas dominantes.
- **No reproducibilidad**: modelos cambian; el mismo prompt produce salidas distintas.

P10 del ADR-0000 establece: el sistema no genera afirmaciones que no estén ancladas en evidencia ingestada. Cualquier uso de LLM debe respetar P10 estructuralmente, no por convención.

## Decisión

El sistema admite LLMs **exclusivamente como herramientas auxiliares con tres restricciones arquitectónicas inviolables**:

1. **Ningún output de LLM entra directamente al modelo de evidencia como `Fact`, `Claim`, `Hypothesis` o `Conclusion`.** Cualquier output de LLM produce un **artefacto intermedio explícito** que un humano debe revisar, atribuir y promover.

2. **Todo uso de LLM se declara en procedencia.** El modelo concreto, su versión, los parámetros usados, el prompt exacto y el output bruto se almacenan junto al artefacto derivado. Trazabilidad bit a bit.

3. **Los LLMs no producen confianza por sí mismos.** Cualquier campo `KentLevel` o probabilidad cuantitativa **debe ser asignada por un actor humano**. Un LLM puede proponer ("a sugerencia mía esto sería `likely`"), pero la asignación oficial es acto humano explícito.

Estas tres restricciones son ADR-level y no se relajan sin superseder este ADR.

## Especificación

### Categorías de uso permitido

| Uso | Permitido | Restricciones |
|-----|-----------|---------------|
| Extracción de entidades nombradas | Sí | Como sugerencia; revisión humana antes de insertar en el grafo |
| Sugerencia de clasificación de Claim/Hypothesis | Sí | Sugerencia; no auto-insertable |
| Traducción aproximada | Sí | Marcada como traducción asistida por LLM; idioma original preservado |
| Sumarización de prosa larga | Sí | Sumario etiquetado como derivado; original siempre accesible |
| Transcripción asistida de audio | Sí | Transcripción etiquetada como asistida; audio original preservado |
| Búsqueda semántica auxiliar | Sí | ADR-0018, no autoritativa |
| Sugerencia de hipótesis candidatas | Sí | Sugerencias visibles como tales; nada se inserta sin curador |
| Razonamiento sobre evidencia | **No** | Conclusiones deben ser actos humanos |
| Generación de Conclusion completa | **No** | Violación directa de P10 |
| Inferencia de entidades nuevas no presentes | **No** | Fabricación |
| Asignación automática de KentLevel | **No** | Confianza es acto humano |
| Síntesis de prosa narrativa para README de caso | Excepcional | Solo con revisión y firma humana del autor responsable |

### Artefactos intermedios

Cualquier uso de LLM produce un objeto `LlmAssist` que vive en una tabla separada hasta ser promovido o descartado:

```
LlmAssist {
  id: LlmAssistId
  task_kind: LlmTaskKind                # ner | translation | summary | suggestion | ...
  input_refs: [EvidenceRef | ClaimRef]
  model: ModelIdentifier                # nombre + versión + hash si local
  parameters: dict                      # temperature, top_p, etc.
  prompt_template_hash: ContentHash     # hash del template usado
  prompt_rendered: str                  # prompt exacto enviado al modelo
  output_raw: str                       # output bruto, sin parsear
  output_parsed: dict?                  # parseo estructurado si aplica
  produced_at: timestamp
  produced_by: ActorId                  # actor humano que invocó el LLM
  cost_estimate: dict?                  # tokens, tiempo, etc.
  promotion: PromotionRecord?           # qué humano lo promovió y cuándo
  schema_version: SemVer
}
```

`PromotionRecord`:

```
PromotionRecord {
  promoted_to: aip_uri                  # objeto creado en el modelo principal
  promoted_by: ActorId                  # humano responsable
  promoted_at: timestamp
  modifications: [str]                  # cambios introducidos por el humano respecto al output del LLM
  rationale: markdown                   # por qué se promueve y qué se modifica
}
```

Un `LlmAssist` sin `PromotionRecord` **no tiene efecto** en el modelo principal. Es información archivada para auditoría, no contenido operativo.

### Reproducibilidad

Cualquier output de LLM debería poder regenerarse para auditoría. En la práctica esto exige:

- Modelo identificado por nombre, versión y, si local, hash.
- Prompt exacto preservado.
- Parámetros preservados (incluso seeds donde el modelo lo soporte).
- Versión del runtime de inferencia.

Para modelos remotos cuya versión cambia sin notificación, el sistema **registra el output** y advierte en el manifiesto que la reproducibilidad estricta no se puede garantizar. La preferencia operativa es modelos locales con hash declarado.

### Preferencia por modelos locales

ADR-0003 (local-first) y P6 obligan a preferir modelos locales reproducibles. Modelos pequeños compatibles con CPU moderna (Llama 3.x compactos, modelos de embeddings sBERT, transformers de extracción de entidades) cubren la mayoría de las necesidades auxiliares.

Modelos remotos (Claude, OpenAI, etc.) son **permitidos como opción** pero:

- Su uso queda explícito en el manifiesto.
- Sus outputs pasan por el mismo flujo `LlmAssist` → promoción humana.
- El sistema documenta que sus resultados son menos reproducibles.

### Prompts versionados

Los prompt templates viven en `prompts/` del repositorio, versionados y hasheados. Un `LlmAssist` referencia su template por hash, no por contenido inline. Modificar un template produce un nuevo hash, lo cual segmenta los resultados correctamente.

### Política sobre hipótesis sugeridas

LLMs pueden sugerir hipótesis competidoras candidatas para un caso ("la familia `misidentification_natural` con `globo de gran altitud` es candidata para este caso por X y Y razones"). Esas sugerencias:

- Viven como `LlmAssist` con `task_kind: hypothesis_suggestion`.
- Se presentan al curador como lista de candidatos.
- El curador decide aceptar, rechazar o reformular cada uno.
- Las aceptadas se promueven a `Hypothesis` con `proponent` declarando humano + LLM auxiliar.

Esta política previene tanto pasividad (LLM dicta hipótesis) como desperdicio (LLM no aporta).

### Política sobre asistencia de redacción

Cuando un humano usa LLM para asistir redacción de un `Conclusion.rationale` o un `Case.abstract`, el output del LLM **es solo punto de partida**. La versión que se publica es la versión revisada y firmada por el humano. El `LlmAssist` queda en la tabla auxiliar como rastro de procedencia.

### Política sobre extracción a partir de prosa histórica

Caso típico: PDF de reporte histórico de 1956 que necesita extracción de campos estructurados (testigo, fecha, lugar, descripción). El flujo:

1. LLM produce extracción candidata → `LlmAssist`.
2. Humano revisa cada campo extraído contra el texto original.
3. Campos aprobados se insertan como `Claim`/`Evidence` con procedencia que incluye el `LlmAssist` y la revisión humana.
4. Campos rechazados o modificados quedan registrados en el `PromotionRecord.modifications`.

### Detección de alucinación

Cuando es posible (claims sobre entidades, ubicaciones, fechas), el sistema implementa **chequeos de soporte**:

- Si el LLM extrae "el testigo era oficial de la USAF", ¿ese texto aparece en el documento? Se verifica.
- Si el LLM produce coordenadas, ¿están consistentes con topónimos extraíbles del texto?

Chequeos automáticos no son sustituto de revisión humana, pero filtran outputs evidentemente fabricados.

### No LLMs en el camino crítico del sistema base

Sin LLM, el sistema funciona plenamente: ingesta, almacena, busca (estructurada + léxica), expone hipótesis (formuladas por humanos), evalúa confianza (asignada por humanos). LLMs son aceleradores, nunca prerrequisitos.

## Justificación

### Por qué no auto-promoción

La auto-promoción de outputs de LLM al modelo principal es el modo de fallo dominante de sistemas modernos. Para un proyecto que prioriza rigor epistémico, ese modo es inaceptable.

### Por qué prompts versionados

Sin versionado, no hay forma de explicar por qué un LLM hoy produce X cuando ayer producía Y. Hash de template segmenta el espacio de resultados de forma auditable.

### Por qué preferencia local

P5, P6, P7. Reproducibilidad y autonomía.

### Por qué chequeos automáticos de soporte

No son perfectos pero filtran fabricaciones evidentes. Coste bajo, beneficio alto.

### Por qué declarar todo en procedencia

Sin declaración, un usuario externo no puede distinguir contenido producido por humano vs. asistido por LLM. Esa distinción es información que el lector merece.

## Consecuencias

**Positivas**
- LLMs aceleran tareas tediosas sin contaminar el modelo principal.
- Procedencia clara distingue lo asistido por LLM de lo no asistido.
- Reproducibilidad maximizada bajo restricciones realistas.
- Filtro contra fabricaciones obvias.

**Negativas**
- Más overhead operativo que "deja que el LLM lo haga".
- Curador debe revisar siempre; sin atajos.
- Modelos remotos quedan en posición de segunda clase.

**Neutras**
- Conforme mejoran modelos, el flujo `LlmAssist` permite incorporarlos sin cambiar la arquitectura.

## Alternativas consideradas

### A. LLM auto-promovible bajo umbral de confianza
**Descripción:** Si el modelo declara alta confianza, su output entra directamente.
**Razón de rechazo:** La confianza declarada por LLM no es confiable. Violación de P10.

### B. Prohibición total de LLMs
**Descripción:** Eliminar todo uso de LLM.
**Razón de rechazo:** Excesivo. LLMs como asistentes auditados son valor real.

### C. Sin trazabilidad de prompts
**Descripción:** Aceptar outputs sin almacenar prompts.
**Razón de rechazo:** Imposibilita auditoría.

### D. Solo modelos remotos
**Descripción:** No mantener tooling para modelos locales.
**Razón de rechazo:** Viola P6.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P6, P10.

**Cómo se alinean:**
- P10 (no fabricación): operacionalización primaria.
- P1: outputs de LLM nunca son `Fact`/`Claim`/`Hypothesis`/`Conclusion` sin acto humano.
- P2/P5 (trazabilidad/reproducibilidad): prompts, modelos y parámetros preservados.
- P6: preferencia local explícita.

**Tensión:** Overhead operativo vs. seguridad epistémica. Aceptada: el overhead es prerrequisito.

## Referencias

- Bender, E., Gebru, T., et al. (2021). *On the Dangers of Stochastic Parrots.*
- Ji, Z., et al. (2023). *Survey of Hallucination in Natural Language Generation.*
- Sigstore project. Prior art en transparency de artefactos.
- BPMN-style human-in-the-loop patterns.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
