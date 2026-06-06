# ADR-0001: Separación estricta de categorías epistémicas

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0006, ADR-0007, ADR-0008, ADR-0009

---

## Contexto

El campo del estudio de fenómenos anómalos sufre una patología recurrente: la mezcla, en un mismo objeto narrativo, de categorías epistémicas radicalmente distintas. Un caso típico de campo:

> "El 5 de marzo de 1973 un objeto plateado en forma de disco sobrevoló la base aérea de X durante 12 minutos. Tres pilotos lo confirmaron. Era una nave no humana realizando reconocimiento."

En esa única frase conviven:

- Un **hecho** verificable (la base aérea X existe).
- Una **afirmación** atribuida pero no verificada (que tres pilotos lo confirmaron).
- Una **interpretación** del observador (que era un disco plateado).
- Una **conclusión sustantiva** sin soporte explícito (que era una nave no humana realizando reconocimiento).

Cuando el modelo de datos no fuerza la separación, el resultado típico es la circulación indefinida de mezclas: cada vez que el caso se cita, las cuatro categorías viajan juntas, y un lector razonable no puede separar lo verificable de lo inferido.

Esta patología no es exclusiva del campo, pero el campo la sufre con especial intensidad por la combinación de incentivos de atención, fragilidad de fuentes, y carga emocional del material.

## Decisión

El modelo de datos del sistema separa de forma arquitectónica cinco categorías epistémicas y prohíbe estructuralmente su mezcla:

1. **Hecho** (`Fact`)
2. **Afirmación** (`Claim`)
3. **Interpretación** (`Interpretation`)
4. **Hipótesis** (`Hypothesis`)
5. **Conclusión** (`Conclusion`)

Cada categoría es un tipo distinto en el modelo. Un objeto vive en exactamente una categoría. Las transformaciones entre categorías son eventos explícitos, trazables, con autoría e instante registrados.

## Justificación

La alternativa —dejar la categorización como convención humana en campos de texto libre— produce el modo de fallo característico del campo: la conclusión emocionalmente fuerte se acaba presentando como si fuese el hecho. La separación arquitectónica fuerza al sistema, a los contribuidores y a los consumidores a hacer visible qué tipo de afirmación están manejando.

La taxonomía elegida es deliberadamente granular sin ser barroca. Cuatro categorías serían insuficientes (perderíamos la distinción crucial entre hipótesis competidoras formuladas para ser evaluadas y conclusiones que pesan esas hipótesis). Seis o más añadirían fricción sin claridad adicional.

### Definiciones operacionales

**Hecho (`Fact`)**
Un enunciado verificable independientemente mediante cadena de evidencia material. Ejemplo: "El radar del aeropuerto Z registró un retorno no identificado a las 23:14:07 UTC del 12 de noviembre de 1986, según el log archivado en `RAW-AB12CD`." Un hecho está siempre anclado a evidencia ingestada y direccionada por hash. No existe hecho sin evidencia.

**Afirmación (`Claim`)**
Un enunciado atribuido a una fuente identificada, no necesariamente verificado. Ejemplo: "El piloto A afirma haber visto un objeto luminoso a las 11 en punto durante 40 segundos." La afirmación es trazable a su fuente, pero la categoría no presupone la veracidad del enunciado. Una afirmación puede ser verdadera, falsa, parcialmente verdadera, o no verificable.

**Interpretación (`Interpretation`)**
Una lectura humana sobre hechos o afirmaciones, declarada como tal. Ejemplo: "La forma descrita por el piloto A es compatible con un globo meteorológico visto desde abajo en condiciones de iluminación frontal." Una interpretación tiene autor identificado, supuestos declarados, y referencia explícita a los hechos y afirmaciones que interpreta. Una interpretación no es ni verdadera ni falsa; es plausible o implausible bajo supuestos.

**Hipótesis (`Hypothesis`)**
Una explicación competidora del fenómeno reportado, formulada de manera que pueda ser favorecida o desfavorecida por evidencia. Una hipótesis declara:
- Qué afirmaría sobre el mundo si fuese cierta.
- Qué evidencia, hipotética o real, la favorece.
- Qué evidencia la desfavorece o la falsearía.
- Qué supuestos requiere.

Una hipótesis sin condiciones de falsabilidad no entra en el sistema como hipótesis; entra como conjetura no operativa, una categoría auxiliar fuera del modelo principal.

**Conclusión (`Conclusion`)**
Una evaluación de confianza relativa entre hipótesis competidoras, en un momento dado, con un cuerpo de evidencia dado. Una conclusión siempre lleva:
- El conjunto de hipótesis evaluadas.
- La distribución de confianza sobre ellas.
- La evidencia favorable y contradictoria considerada para cada una.
- Los supuestos.
- Las preguntas abiertas.
- El instante y el autor de la evaluación.

Una conclusión nunca elimina hipótesis del sistema; las reordena en confianza. Una hipótesis con confianza muy baja sigue existiendo y puede recuperarse si nueva evidencia la favorece.

### Transformaciones permitidas

Un objeto en una categoría no puede mutar silenciosamente a otra. Las transformaciones permitidas son eventos explícitos:

- Una **afirmación** puede dar lugar a una **interpretación** o a una **hipótesis** derivada, vinculada con relación explícita y autoría.
- Un **hecho** puede dar lugar a **interpretaciones** o **hipótesis**.
- Una **hipótesis** puede ser evaluada en una **conclusión**.
- Una **conclusión** puede actualizar la distribución de confianza de hipótesis sin alterar la integridad de las hipótesis.

Lo que **nunca** ocurre:
- Una afirmación se promueve a hecho automáticamente porque se repita en N fuentes.
- Una interpretación se promueve a hecho porque se considere "razonable".
- Una hipótesis se promueve a conclusión sin pasar por una evaluación explícita.

## Consecuencias

**Positivas**
- Lectores externos, revisores académicos, periodistas y jueces pueden auditar de qué tipo de afirmación se trata, sin depender de la convención editorial.
- La regresión a la patología del campo (mezcla narrativa) es estructuralmente difícil.
- El sistema soporta investigadores con sesgos opuestos sin convertirse en arena ideológica: cada uno opera sobre su propia capa de interpretación e hipótesis, sin alterar hechos ni afirmaciones.
- Permite versionado granular: cambia una interpretación sin alterar el hecho subyacente.

**Negativas**
- Fricción de ingestión. Un colaborador no puede volcar texto libre; debe categorizar. Esto desincentiva contribuciones rápidas.
- Riesgo de "categorizaciones políticas": clasificar como interpretación lo que otro considera hecho. Mitigado por el requisito de trazabilidad de la categorización (quién y cuándo categorizó qué, con justificación).
- Curva de aprendizaje no trivial para usuarios nuevos.

**Neutras**
- El sistema se vuelve verbose. Un caso ocupa más espacio descriptivo del que ocuparía en una narración tradicional.
- El esquema invita a que herramientas auxiliares (extractores, parsers) tengan que clasificar antes de insertar, lo que aumenta su complejidad.

## Alternativas consideradas

### A. Etiquetas convencionales sin tipado estricto
**Descripción:** Cada elemento del caso lleva una etiqueta `kind: fact|claim|...` pero el sistema no impone la separación a nivel de tipo.
**Razón de rechazo:** Convenciones que no están en el tipo son convenciones que se erosionan. Los datos del campo demuestran que esta erosión ocurre por defecto.

### B. Solo dos categorías (verificable / no verificable)
**Descripción:** Reducir a un dualismo.
**Razón de rechazo:** Pierde la distinción operativa entre afirmación atribuida no verificada, interpretación humana, hipótesis competidora e evaluación. Esas distinciones no son ornamentales; son la materia que el sistema debe organizar.

### C. Cuatro categorías (fusionar interpretación e hipótesis)
**Descripción:** Tratar interpretación e hipótesis como un solo tipo.
**Razón de rechazo:** Una interpretación es una lectura particular sobre evidencia presente; una hipótesis es una explicación generalizable con condiciones de falsabilidad. Fusionarlas hace imposible la evaluación competitiva del ADR-0008.

### D. Seis categorías (separar evidencia primaria/secundaria/terciaria del hecho)
**Descripción:** Tratar como categoría epistémica lo que en realidad es una propiedad de la fuente.
**Razón de rechazo:** Confunde el plano de la fuente (cubierto por ADR-0005) con el plano epistémico. La granularidad de la evidencia vive en el modelo de fuente, no aquí.

## Alineación con ADR-0000

**Propiedades afectadas:** P1 (separación de categorías), P3 (incertidumbre cuantificada), P4 (neutralidad de hipótesis), P8 (documentación), P10 (no fabricación).

**Cómo se alinean:** Esta decisión es la operacionalización primaria de P1. Sin esta separación arquitectónica, P3 sería imposible (no se puede cuantificar incertidumbre sobre objetos cuya categoría epistémica es ambigua). P4 quedaría reducida a una declaración de intenciones sin soporte estructural. P10 perdería su anclaje: si todo es lo mismo, un texto generado por LLM se confunde con un hecho ingestado.

**Tensión:** Friction de ingestión vs. velocidad de incorporación de archivos legacy. Mitigada con herramientas de asistencia para clasificación (ver ADR-0021) y con una categoría de transición auxiliar "no clasificado" que existe solo dentro del staging, nunca en el archivo publicado.

## Referencias

- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.*
- Toulmin, S. (1958). *The Uses of Argument.* (Modelo de evidencia, claim, warrant, backing.)
- Pearl, J., & Mackenzie, D. (2018). *The Book of Why.*
- Walton, D. (2008). *Informal Logic: A Pragmatic Approach.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
