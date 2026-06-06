# ADR-0020: Marco ético y do-no-harm

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0014, ADR-0019

---

## Contexto

La libertad de investigación no es absoluta. Coexiste con derechos de personas concretas que aparecen en los archivos: testigos identificables, oficiales nombrados, familiares de afectados, propietarios de tierras donde ocurrieron observaciones, periodistas que cubrieron casos, perits que evaluaron material.

Históricamente, el campo del estudio de fenómenos anómalos ha producido daños concretos a personas:

- Periodistas hostigados décadas por aparecer en archivos como "involucrados" en casos famosos.
- Testigos cuyas vidas privadas se reabren cíclicamente con cada documental.
- Oficiales militares cuyo nombre se asocia con interpretaciones sustantivas que ellos no firmaron.
- Familias afectadas por filtraciones de localización de testigos vivos.

Un sistema que **agrega y vuelve consultable** material histórico amplifica esos daños si no se diseña con disciplina. La consultabilidad eficiente, combinada con el grafo de conocimiento (ADR-0011), permite cruces que los archivos físicos dispersos no permitían fácilmente.

P12 del ADR-0000 estableció `do-no-harm` como propiedad irrenunciable. Este ADR la operacionaliza.

## Decisión

El sistema adopta un **marco ético explícito** documentado en `docs/ethics.md` y operacionalizado en cuatro mecanismos:

1. **Categorización de sensibilidad** por entidad nombrada, con políticas de exposición diferenciadas.
2. **Mecanismo de takedown verificable** para testigos identificables u otros afectados.
3. **Revisión humana obligatoria de exportes que crucen umbral de agregación**.
4. **Negativa estructural a deanonymization automatizada** por cruces.

El marco se revisa con cadencia anual o ante incidente documentado. Cualquier ADR técnico que entre en tensión con este marco debe declararla y resolverla, no ignorarla.

## Especificación

### Categorización de sensibilidad por entidad

Cada `Person` y, opcionalmente, otras entidades nombradas, llevan un campo `sensitivity_classification`:

| Class | Significado | Política |
|-------|-------------|----------|
| `public_figure_in_context` | Persona pública en el contexto del fenómeno (oficial firmante de reporte público, científico que ha hablado abiertamente del caso) | Exposición normal. Nombre y rol son referenciables. |
| `private_with_consent_for_use` | Privada pero consintió a uso académico documentado | Exposición conforme al consentimiento; las condiciones se registran. |
| `private_without_explicit_consent` | Aparece en material pero sin consentimiento explícito para uso académico contemporáneo | Por defecto seudonimizada en exportes; nombre solo en enclave. |
| `deceased_with_living_kin` | Fallecida; familiares directos vivos | Caso por caso. Por defecto, conservadora. |
| `minor_at_time_of_event` | Era menor cuando se afirmó la observación | Anonimizada hasta verificación de mayoría legal + consentimiento, salvo material ya extensamente publicado donde el balance es claro. |
| `subject_of_redress_request` | Ha solicitado takedown o limitación; pendiente o resuelto | Bajo política de takedown vigente. |

La clasificación es un **objeto del modelo**, con autoría y fecha. Se modifica con evento explícito. Cualquier elevación de sensibilidad (`public_figure` → `private_without_consent`) se aplica sin penalización al solicitante.

### Mecanismo de takedown verificable

Cualquier persona identificable en el archivo (o representante legal verificado) puede solicitar:

- Anonimización (sustitución de nombre por seudónimo en vistas públicas).
- Limitación de exposición (no aparece en visualizaciones de tipo X).
- Retirada de evidencia atribuida a su persona (con condiciones; ver más abajo).

Procedimiento:

1. Solicitud por canal documentado (email, formulario público).
2. Verificación de identidad por método razonable (documento de identidad, abogado).
3. Evaluación por curador del archivo en plazo documentado.
4. Resolución: anonimización aplicada, denegación con motivación, o derivación a comité si el caso lo requiere.
5. Registro de la decisión en `audit.log` con seudónimo o ID, sin exponer datos personales.

La retirada total de evidencia (no solo de la entidad nombrada) es la opción menos preferida: solo se aplica cuando:
- Hay obligación legal explícita.
- El daño concreto del material en sí es desproporcionado al interés público.
- No hay forma razonable de mantener el material sin la atribución problemática.

### Umbrales de agregación que disparan revisión humana

Cierto tipo de exportes pueden producir daño por agregación aunque cada elemento sea inocuo:

- Mapa de domicilios de testigos vivos.
- Lista cruzada de testigos múltiples de distintos casos.
- Cruce de identidades con redes sociales (no soportado por ADR-0014 política conservadora, pero potencialmente derivable de fuentes incluidas).
- Cualquier exporte que combine `private_without_explicit_consent` con información geográfica precisa.

El sistema implementa **detectores de exporte sensible**:

- Si una query devuelve >N personas privadas sin consentimiento + coordenadas precisas → bloqueado por defecto; requiere autorización explícita con motivación.
- Si un exporte excede umbrales similares → idem.

La autorización deja huella en `audit.log`. La política no impide el exporte; obliga a deliberación.

### Negativa a deanonymization automatizada

El sistema **no provee funcionalidad nativa** para:

- Inferir identidad de testigos anonimizados a partir de cruces.
- Resolver "John Doe" en un caso a una persona real basándose en patrones de hábitos, ubicación, etc.
- Generar perfiles de personas a partir de múltiples afirmaciones cruzadas.

Si un usuario externo construye tales capacidades sobre la API, eso es responsabilidad suya y queda fuera del proyecto. El proyecto no diseña esta funcionalidad y declara públicamente que no la diseñará.

### Política sobre testigos fallecidos

Las personas fallecidas no tienen derechos GDPR (mayoría de jurisdicciones), pero la política del proyecto reconoce derechos de familiares directos vivos y memoria. Por defecto:

- Material extensamente publicado en vida (testimonio formal en hearings, libros propios, entrevistas con consentimiento) → exposición normal.
- Material privado o filtrado en vida sin consentimiento → conserva clasificación restrictiva incluso post-mortem hasta verificación.
- Cualquier menor identificable en momento del evento conserva protección incluso si ahora es adulto, salvo consentimiento explícito o publicación extensa documentada.

### Política sobre material clasificado activo

Si llega al sistema material que aparenta ser clasificado vigente (no desclasificado oficialmente):

- Suspensión inmediata de ingestión.
- Verificación del estatus de clasificación.
- Si confirmado clasificado vigente: no se ingesta. Decisión documentada.
- Si confirmado desclasificado: se ingesta normalmente.
- Si ambiguo: caso por caso, con consulta a marco legal de la jurisdicción del operador.

El sistema **no es un canal de filtración**. La línea entre archivo de material legalmente publicable y vehículo de filtración debe mantenerse inequívoca.

### Política sobre material de menores

Cualquier afirmación atribuida a un menor en el momento del evento se trata como sensible por defecto. La política se documenta separadamente en `docs/minors-policy.md`.

### Política sobre comunidades indígenas y patrimonio inmaterial

Reportes anómalos en contextos indígenas o de patrimonio inmaterial específico requieren atención particular:

- Atribución a tradiciones orales sin consentimiento de la comunidad fuente puede ser ofensivo o legalmente cuestionable.
- Coordenadas precisas de lugares sagrados pueden facilitar daño material.

El sistema admite políticas locales por subset de archivo. Cuando se ingesta material de este tipo, el curador documenta consulta a la comunidad fuente o explica por qué no fue posible.

### Política sobre sensacionalización por terceros

El proyecto no puede prevenir que terceros sensacionalicen sus exportes. Lo que puede:

- Diseñar exportes que llevan **contexto epistémico** obligatorio (confianza, supuestos, contradicciones).
- Documentar guías de uso responsable.
- Rechazar colaboración formal con proyectos derivados que documentadamente violan los principios del marco.

### Revisión ética periódica

Cadencia anual. Cualquier release mayor incluye:

- Conteo de takedown requests procesadas, resueltas, pendientes.
- Conteo de exportes que cruzaron umbral de revisión humana.
- Incidentes éticos reportados.
- Evolución del corpus de personas clasificadas por sensibilidad.

Tendencias adversas (incremento de takedowns sin resolver, repunte de incidentes) disparan revisión del marco.

## Justificación

### Por qué clasificación por entidad y no por documento

Una misma persona aparece en múltiples documentos con contextos distintos. Clasificar al sujeto, no al documento, permite consistencia.

### Por qué takedown verificable y no automático

Takedown automático (cualquier solicitud se procesa sin verificación) abre canal de abuso: terceros pidiendo retiradas de testigos legítimos. Verificación protege contra ese abuso.

### Por qué bloqueo por agregación

El daño por agregación es real y subestimado. Cualquier persona individual del archivo puede ser inocua, pero el cruce produce daño. Detectar y obligar deliberación es el contrapeso operativo.

### Por qué negativa pública a deanonymization

Declararla públicamente protege al proyecto de presión externa para implementarla. Es declaración de carácter.

### Por qué política sobre material clasificado

El proyecto no quiere ser canal de filtración. La línea editorial debe estar fuera de toda duda para sobrevivir presiones legales y éticas a largo plazo.

## Consecuencias

**Positivas**
- Personas en el archivo tienen recurso real.
- Daño por agregación es contrapesado.
- Posición pública sobre deanonymization protege al proyecto.
- Política sobre material clasificado evita problemas legales serios.

**Negativas**
- Curaduría con disciplina ética añade trabajo.
- Algunos exportes serán bloqueados o requerirán justificación.
- Política conservadora puede percibirse como excesiva en casos límite.

**Neutras**
- El marco evoluciona; ningún detalle es eterno.

## Alternativas consideradas

### A. Sin marco ético explícito (asumido por convención)
**Descripción:** Cubrir solo con disclaimers genéricos.
**Razón de rechazo:** Las propiedades irrenunciables exigen operacionalización. Convenciones se erosionan.

### B. Anonimización por defecto de todo
**Descripción:** Maximalismo.
**Razón de rechazo:** Vacía de contenido el archivo. Imposibilita investigación legítima.

### C. Sin mecanismo de takedown
**Descripción:** Solo cumplimiento legal mínimo.
**Razón de rechazo:** Daño documentado a personas en el campo. Insuficiente.

### D. Comité externo obligatorio para cada decisión
**Descripción:** Externalizar todas las decisiones éticas.
**Razón de rechazo:** Inviable operativamente; comités lentos saturan el sistema.

## Alineación con ADR-0000

**Propiedades afectadas:** P4, P12.

**Cómo se alinean:**
- P12 (do-no-harm): operacionalización completa.
- P4 (neutralidad): el marco ético es neutro respecto a hipótesis sustantivas; solo regula tratamiento de personas y material.

**Tensión:** Apertura del archivo vs. protección. Aceptada con resolución caso a caso.

## Referencias

- GDPR Articles 6, 9, 17, 21.
- Belmont Report (1979). *Ethical Principles and Guidelines for the Protection of Human Subjects of Research.*
- WMA Declaration of Helsinki.
- Solove, D. (2008). *Understanding Privacy.*
- Tufekci, Z. (2014). *Engineering the Public.* (Daño por agregación.)
- Hutter, Z. & Lin, Y. (2024). Reflexiones contemporáneas sobre Right to be Forgotten en archivos académicos.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
