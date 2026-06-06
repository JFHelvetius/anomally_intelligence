# ADR-0026: Sustainable Stewardship — gobernanza honesta de un proyecto de un solo mantenedor

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0020, ADR-0027

---

## Contexto

El Red Team Review identifica el modelo de sostenibilidad como riesgo arquitectónico de primer orden:

- **§8.4** La revisión ética anual presupone continuidad de carácter del mantenedor. Un sucesor con ética distinta hereda la arquitectura y la usa diferente. El proyecto no tiene defensa estructural contra captura por sucesión.
- **§9.1** Mantenedor único part-time + alcance declarado producen vaporware perpetuo con alta probabilidad.
- **§12 (Verdict 6)** Recomienda documentar la fragilidad del modelo de un mantenedor como propiedad del proyecto, no como pie de página.

El ADR-0000 sección "Modelo de sostenibilidad" declaró tres estados (inicial, intermedio, consolidado) y aceptó la fragilidad. No operacionalizó:

- Qué exige al mantenedor único actual.
- Qué garantiza al usuario externo bajo ese modelo.
- Cómo se gestiona la sucesión (no solo desaparición, sino transición ordenada).
- Cómo se protege la integridad ética contra captura por sucesor.

Este ADR cubre el espacio operativo entre "tenemos un mantenedor" y "hemos archivado dignamente" (ADR-0027).

## Decisión

El proyecto adopta cinco compromisos operativos sobre stewardship, cada uno con artefacto verificable:

1. **MAINTAINERS.md** como artefacto obligatorio del repositorio.
2. **Declaración pública de bus factor** y su revisión semestral.
3. **Protocolo de sucesión** con restricciones que protegen las propiedades irrenunciables.
4. **Decisiones éticas anclas a procedimiento**, no a discreción personal.
5. **Política explícita de no-SLA** y comunicación honesta de cadencia.

Estos compromisos son operativos: cada uno tiene artefacto auditable y revisión documentada. Su incumplimiento es bug, no estilo.

## Especificación

### Compromiso C1. MAINTAINERS.md

El repositorio mantiene en su raíz un fichero `MAINTAINERS.md` con:

- Lista actual de mantenedores con su rol (`founder`, `co-maintainer`, `area-maintainer`, `emeritus`).
- Para cada mantenedor: nombre o handle público, fecha de incorporación, áreas de responsabilidad, contacto público.
- Histórico completo de cambios en la lista, con fecha y motivo.
- Estado actual del **bus factor** del proyecto: número entero, declarado, revisado semestralmente.

Plantilla inicial:

```markdown
# Mantenedores AIP

## Activos

- **<handle>** — fundador. Incorporado 2026-06-03. Responsable: todas las áreas. Contacto: <medio público>.

## Bus factor declarado: 1

Última revisión: 2026-06-04. Próxima revisión: 2026-12-04.

## Histórico

- 2026-06-03 — Fundación. Mantenedor único: <handle>.
```

Cualquier cambio en la lista de mantenedores se hace por **PR con consenso de mantenedores activos**. Si solo hay un mantenedor activo, su propia decisión basta —pero el cambio debe ser visible y comunicable.

### Compromiso C2. Bus factor declarado

**Bus factor** = número mínimo de mantenedores cuya desaparición simultánea dejaría el proyecto sin capacidad de respuesta sostenida.

Estado actual: **1**. El proyecto reconoce públicamente este número.

Implicaciones operativas declaradas al usuario:

- Cualquier release puede ser la última si el mantenedor único deja el proyecto.
- Tiempos de respuesta a issues no tienen compromiso.
- Decisiones arquitectónicas son sostenidas por una persona y, por tanto, vulnerables a su sesgo individual.

Revisión semestral del bus factor obligatoria. Cuando suba (por incorporación de co-mantenedor sostenido), se actualiza con celebración. Cuando baje (mantenedor que se retira), se actualiza con honestidad y se evalúa si aplica ADR-0027.

### Compromiso C3. Protocolo de sucesión

Cuando un nuevo mantenedor se incorpora con rol de co-mantenedor o sucesor:

**Requisitos previos del incorporando:**

- Lectura documentada del ADR-0000 completo.
- Lectura documentada de los ADRs 0023–0028 (las enmiendas de honestidad).
- Acuerdo escrito (PR con su firma) que reconoce las propiedades irrenunciables P1–P12 y los sesgos S1–S4 (ADR-0025) como condición de mantenimiento.

**Restricciones sobre el sucesor:**

- No puede superseder el ADR-0000 unilateralmente. La supersesión requiere **revisión externa documentada** en `docs/reviews/` por al menos un revisor sin afiliación al proyecto.
- No puede cambiar la licencia (ADR-0022, ADR-0028) sin revisión externa equivalente.
- No puede archivar el proyecto (ADR-0027) sin cumplir los criterios de archivo digno declarados.
- Hereda las decisiones éticas vigentes (ADR-0020). Cualquier cambio sustantivo requiere actualización formal del ADR-0020 con revisión externa.

**Defensa contra captura sustantiva:**

Un sucesor que quisiera reorientar el proyecto hacia una hipótesis sustantiva específica (afirmar origen extraterrestre, ETH, ETI, NHI, o cualquier alternativa) violaría P4 reformulada por ADR-0025. La defensa estructural:

- El propio mecanismo del sistema (hipótesis competidoras sin pesos por defecto) no permite codificar sesgo sin que el sesgo sea visible.
- Los sesgos S1–S4 ya están declarados; añadir un quinto sesgo sustantivo sería acto público auditable.
- La licencia Apache (ADR-0022) permite a cualquier observador externo forkear el proyecto si el mantenedor en ejercicio lo captura. La defensa última es la posibilidad de fork.

Esta defensa **no es absoluta**. Reconocimiento honesto.

### Compromiso C4. Decisiones éticas ancladas a procedimiento

ADR-0020 establece marco ético. El Red Team Review observa que la revisión ética anual depende del carácter del mantenedor en ejercicio.

Operacionalización:

- Las decisiones éticas concretas (clasificación de sensibilidad de una `Person`, procesamiento de un takedown, política sobre un material en zona gris) **se documentan caso por caso** con autoría, fecha, procedimiento aplicado, y rationale.
- Procedimientos están documentados en `docs/ethics-procedures/`. Decisiones se evalúan contra procedimiento, no contra criterio personal.
- Cualquier desviación del procedimiento es **acto explícito** que se registra como excepción con su justificación.
- Un sucesor con ética distinta puede cambiar los procedimientos por ADR-0020 enmendado, pero las decisiones pasadas se evalúan contra el procedimiento vigente en su momento. No hay reescritura retroactiva.

Esta política transforma "carácter del mantenedor" en "procedimiento del proyecto en su momento" como ancla.

#### Mitigación del sesgo de clase en takedowns (RTR §8.1)

El takedown verificable mantenido en ADR-0020 introduce sesgo de clase: personas con recursos legales completan verificación más fácilmente. Mitigación declarada:

- Se aceptan **vías alternativas de verificación** documentadas: autenticación por verificación de control de un identificador (email asociado a documento público, cuenta institucional, etc.), no solo identificación legal formal.
- El curador en ejercicio puede ejercer **discreción a favor del solicitante** cuando la balance del daño es clara, incluso sin verificación formal completa.
- Casos donde la verificación es imposible pero el daño es plausible se documentan como "takedown sin verificación formal" con razón explícita y aplican anonimización por precaución.

El sesgo de clase no se elimina; se mitiga con discreción documentada.

### Compromiso C5. Política de no-SLA y cadencia honesta

El proyecto **no promete**:

- Tiempos de respuesta a issues.
- Frecuencia de releases.
- Compatibilidad hacia delante o hacia atrás de cualquier API que no esté en V1 (ADR-0023).
- Resolución de PRs externos en horizonte alguno.

El proyecto **sí promete**:

- Que cualquier release lleve manifiesto reproducible (ADR-0016).
- Que las decisiones tomadas se documentan como ADR.
- Que el `ARCHIVED.md` (ADR-0027) se publica si y cuando el proyecto se archiva.
- Que los mantenedores cuyo nombre figura en `MAINTAINERS.md` declaran disposición razonable a recibir comunicación pública sobre el proyecto.

Esta franqueza protege al usuario externo de expectativas falsas y protege al mantenedor de presión que no puede sostener.

### Mitigación de RTR §8.3 — Política sobre material clasificado

El Red Team Review identifica la política ADR-0020 sobre material clasificado como "inestable" porque depende de decisión sostenida por una persona bajo presión.

Mitigación: la política se ancla a procedimiento documentado en `docs/ethics-procedures/classified-material.md`:

1. Cualquier material que aparenta ser clasificado vigente activa **suspensión inmediata de ingestión** del propio adquisidor que lo trajo.
2. Verificación del estatus de clasificación se hace **antes** de cualquier decisión sobre el material concreto.
3. Si confirmado clasificado vigente: el material **no se ingesta**, y la decisión se documenta con cita a la confirmación. Si la confirmación no es posible en plazo razonable, default es no ingestar.
4. Si confirmado desclasificado: ingestión normal con procedencia documentada.
5. Casos ambiguos donde la confirmación no es posible y el material es plausiblemente sensible: **default a no ingestar**.

Este procedimiento traslada la responsabilidad de "decisión bajo presión" a "aplicación de procedimiento documentado". Si el procedimiento ha de cambiar, se cambia por ADR explícito, no por decisión silenciosa.

## Consecuencias

**Positivas**
- El usuario externo entiende qué puede esperar.
- El sucesor potencial entiende qué hereda.
- La integridad ética se ancla a procedimiento, no a persona.
- Riesgos del modelo de un solo mantenedor son declarados, no escondidos.

**Negativas**
- La franqueza puede desalentar adopción por organizaciones que requieren SLAs.
- Mantener `MAINTAINERS.md`, procedimientos éticos y bus factor exige disciplina sostenida.
- Protocolo de sucesión añade fricción a la incorporación de co-mantenedores.

**Neutras**
- Los procedimientos evolucionan; este ADR captura la versión inicial.

## Declaración explícita de riesgo de mantenedor único

El proyecto reconoce públicamente:

1. **Riesgo de discontinuación.** El proyecto puede dejar de mantenerse en cualquier momento sin aviso previo significativo. La licencia Apache garantiza que el material existente permanece utilizable bajo sus términos.

2. **Riesgo de calidad inconsistente.** Sin revisión por pares interna sostenida, decisiones de diseño y ética pueden incorporar errores que un equipo habría detectado.

3. **Riesgo de sesgo personal.** Las elecciones del mantenedor único —qué fuentes priorizar, qué casos curar, qué hipótesis enunciar como ejemplos— reflejan su perspectiva individual incluso cuando el mecanismo es no-favoritista (ADR-0025).

4. **Riesgo de captura emocional.** El mantenedor único es vulnerable a presión emocional de comunidades del campo. La defensa es la disciplina de procedimientos y la posibilidad de fork bajo Apache.

5. **Riesgo de obsolescencia técnica.** Sin contribuyentes activos, dependencias críticas (DuckDB, Parquet, librerías Python) pueden envejecer sin que el mantenedor único pueda mantenerlas al día.

Estos cinco riesgos son **inherentes al modelo** y no se prometen eliminar. Se prometen reconocer.

## Alineación con ADR-0000

**Propiedades afectadas:** P8 (documentación al nivel del código), P12 (do-no-harm), modelo de sostenibilidad del ADR-0000.

**Cómo se alinea:** este ADR operacionaliza compromisos que el ADR-0000 enuncia en alto nivel. No introduce propiedad nueva; convierte la disposición declarativa en disciplina operativa.

**Tensión:** la fricción de los compromisos vs. la libertad del mantenedor único. Aceptada: la fricción es defensa estructural contra modos de fracaso identificados.

## Trigger de revisión

Este ADR se revisa cuando:

- Cambia el bus factor declarado.
- Se incorpora primer co-mantenedor (ajuste de procedimiento).
- Se produce sucesión efectiva del mantenedor único.
- Aparece incidente ético no cubierto por procedimiento (gap detectado).

## Referencias

- `docs/reviews/adr_red_team_review.md`, secciones §8.1, §8.3, §8.4, §9.1, §12.
- Eghbal, N. (2020). *Working in Public: The Making and Maintenance of Open Source Software.*
- OpenSSF Scorecard. Maintainer-presence heuristics.
- Tidelift maintainer agreements (prior art en compromisos explícitos del mantenedor).

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
