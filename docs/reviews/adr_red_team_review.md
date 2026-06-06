# Red Team Review — Arquitectura AIP (ADR-0000 .. ADR-0022)

**Fecha:** 2026-06-03
**Postura:** Revisor externo hostil. Sin afiliación al proyecto. Sin compromiso con su éxito.
**Alcance:** ADRs 0000 a 0022, README y LICENSE. Estado del proyecto al momento de la revisión: pre-código, todo el material son decisiones documentales.
**Objetivo:** identificar fallos arquitectónicos, supuestos ocultos, riesgos no mitigados, contradicciones internas, deshonestidades epistémicas, y modos plausibles de fracaso.

Este documento **no** es respondido por los mantenedores. Las críticas se preservan tal cual. Cualquier corrección entra al sistema como ADR de enmienda con cita explícita a la sección de esta revisión que la motiva.

---

## 1. Crítica a la postura epistémica fundacional

### 1.1. "Neutralidad de hipótesis" es propaganda

P4 (neutralidad de hipótesis) se vende como invariante arquitectónica. No lo es. Es una decisión sustantiva disfrazada de neutralidad.

- Decidir qué entra al "espacio de hipótesis canónicas" (familias en ADR-0008) es ya un acto editorial. La taxonomía elegida —`misidentification_natural`, `observer_error`, `classified_human_technology`, `non_human_intelligence`, etc.— refleja categorías occidentales contemporáneas. Una persona del campo que opera con categorías religiosas (fenómeno teofánico) o tradicionalmente shamánicas (visita de seres del bosque) no encuentra hogar limpio en este esquema. La taxonomía dice que esas categorías son `other` o `non_human_intelligence`, lo cual ya es una interpretación.
- El proyecto presume que las cinco categorías epistémicas (`Fact`, `Claim`, `Interpretation`, `Hypothesis`, `Conclusion`) son universales. No lo son. Son herramientas de la tradición intelectual eurocéntrica post-Ilustración. Aplicarlas a relatos de tradiciones que no las separan es una imposición que el ADR-0001 no reconoce.
- "Neutralidad" en intelligence analysis (referencia a Heuer ACH) opera dentro de instituciones que ya han decidido la pregunta significativa. Importar ese marco asume que aquí también está decidida.

**Riesgo concreto.** Operadores de tradiciones distintas a la occidental académica pueden no usar el sistema, o usarlo distorsionando sus propias categorías. El archivo terminará reflejando la perspectiva del mantenedor inicial, propagada por inercia.

### 1.2. La "honestidad epistémica" es selectiva

El sistema dice que cuantifica incertidumbre, pero la cuantificación opera dentro de un marco que asume que la incertidumbre es del tipo que el marco modela. Las incertidumbres que no caben en `KentLevel` o en distribución cuantitativa no existen para el sistema.

Ejemplos no cubiertos:

- **Incertidumbre de marco.** "No estoy seguro de que mi conjunto de hipótesis competidoras esté correctamente formulado". El campo `ExhaustivenessLevel` aborda parcialmente, pero superficialmente.
- **Incertidumbre lingüística.** El predicado natural del Claim es preservado pero su interpretación involucra suposiciones lingüísticas que el sistema no modela.
- **Incertidumbre de identidad de actor.** Un `ActorId` es estable en el sistema, pero ¿quién garantiza que dos curadores no creen dos `Actor` distintos para la misma persona real? El grafo lo gestiona como reconciliación, pero el problema está mal contenido.

### 1.3. La pregunta central ("qué confianza") presupone que las hipótesis son competidoras independientes

ACH y derivados modelan hipótesis como mutuamente excluyentes en cada `HypothesisSet`. La realidad es más complicada:

- Un caso puede ser **composite**: globo identificado + memoria sesgada por exposición previa. ADR-0008 reconoce `composite` como familia, pero el modelo formal no soporta composición probabilística clara entre hipótesis simples.
- Dos hipótesis pueden ser **lógicamente entrelazadas**: la hipótesis "fenómeno atmosférico natural raro" es parcialmente una afirmación sobre el estado de la atmósfera durante el evento; si la hipótesis "globo" es cierta, no por ello la atmósfera era especialmente activa, pero la coocurrencia puede confundirse.

El sistema no modela esto. La frase "distribución sobre hipótesis competidoras" suena rigurosa y oculta esta complicación.

---

## 2. Crítica a las propiedades irrenunciables

### 2.1. Las propiedades P1–P12 son incompatibles entre sí en escenarios reales

Algunos pares específicos:

- **P9 (fuentes públicas como primarias) ⊥ P12 (do-no-harm).** Las fuentes públicas más valiosas (FOIA recientes) son las que más contienen identidades vivas. Operacionalizar P12 reduce P9. El ADR-0020 lo reconoce pero la política es conservadora; la consecuencia operativa es que parte del archivo público no se ingestará.
- **P3 (incertidumbre cuantificada) ⊥ P5 (reproducibilidad).** Cualquier método de cuantificación de incertidumbre involucra priors o supuestos. Documentarlos hace el cómputo reproducible, pero la elección del prior es no reproducible (no hay procedimiento universal para elegirlo). El sistema lo silencia.
- **P6 (local-first) ⊥ P9 (fuentes públicas).** Las fuentes públicas grandes (NARA, GEIPAN, archivos audiovisuales) requieren TB de espacio. "Local-first" para usuarios con discos modestos significa "subset de las fuentes públicas". Eso ya es captura editorial implícita.
- **P10 (no fabricación) ⊥ P11 (inmutabilidad de evidencia cruda).** Una evidencia ingestada con metadata derivada por LLM (timestamp extraído, ubicación geocodificada) genera fricción contra la inmutabilidad. ADR-0021 lo aborda con la separación `LlmAssist`, pero el flujo de promoción + revisión es teóricamente limpio y operativamente difícil de mantener bajo carga.

Las tensiones se reconocen pero no se resuelven; se "aceptan" con disclaimer en cada ADR. Eso no es resolución; es deuda epistémica acumulada.

### 2.2. P2 (trazabilidad bit a bit) es performativa

La trazabilidad bit a bit se predica con orgullo. En la práctica:

- Si el usuario usa LLM remoto cuyo modelo cambia, la trazabilidad se rompe. ADR-0021 lo dice "menos reproducible". Eso es deshonestidad: o es trazable o no lo es.
- Si la fuente externa (archivo nacional, agencia) reorganiza su sitio, los URIs cambian, y la rederivación es imposible. El WARC mitiga, pero el WARC depende de que la captura original sea exhaustiva, lo que rara vez es el caso para sitios dinámicos.
- La trazabilidad de transformaciones manuales (un humano edita metadata) depende de que ese humano sea disciplinado. El sistema obliga `authorized_by` pero no audita la veracidad de la edición. Un mantenedor malicioso puede falsificar atribución.

### 2.3. P7 (coste cercano a cero) sobrestima la capacidad del portátil moderno

El proyecto aspira a procesar TB de WARCs, embeddings opcionales, índices FTS y vectoriales, grafos de millones de aristas. "Portátil moderno" promedio en 2026 tiene 16–32 GB RAM y SSD de 1 TB. Eso ya pone límites duros al alcance real del archivo "completo".

El ADR-0015 lo trata con ligereza ("aceptable para usuario individual con disco moderno"). Para un proyecto de horizonte de décadas con aspiración de ser "referencia mundial", el portátil moderno no escala. El proyecto:

- O reduce el alcance del archivo "local" a un subset (captura editorial implícita).
- O depende de syncing parcial con almacenamiento externo (viola P6 funcionalmente).
- O añade capa de servidor (admite que no es 100% local-first).

Ninguna de las tres es declarada honestamente.

---

## 3. Crítica al modelo de datos

### 3.1. La separación de cinco categorías epistémicas asume madurez del modelo

`Fact` requiere "verificabilidad independiente con cadena de evidencia material". En la práctica para reportes históricos esto es raro. La mayoría del archivo será `Claim` y `Interpretation`. La existencia de `Fact` como categoría puede llenarse muy poco. Si está casi vacía, ¿para qué existe?

Y peor: la frontera Fact/Claim es borrosa en la práctica. ¿"El radar del aeropuerto Z registró un retorno"? Es un `Claim` del operador del radar, materializado por el log. ¿Es `Fact` porque el log existe? El log existe pero su interpretación como "retorno" es ya `Interpretation`. La categorización siempre tendrá zona gris no resoluble por convención.

### 3.2. `Hypothesis.falsifiability` es ingenua

Popper sigue siendo influyente pero el demarcationismo estricto está empíricamente cuestionado. Hipótesis legítimas en física teórica contemporánea no son falsables operativamente en horizontes razonables (gravitones, materia oscura específica). El proyecto exige falsabilidad operativa como condición de entrada al modelo. Esto:

- Excluye hipótesis legítimas que el campo discute.
- Privilegia hipótesis con asociación a evidencia accesible —que casualmente son las hipótesis "mundanas" (globos, errores). La supuesta neutralidad colapsa: la falsabilidad operativa filtra **a favor** de hipótesis ordinarias.

### 3.3. `EvidenceLink.weight_qualitative` es un score escondido

ADR-0009 rechaza scores escalares como representación principal y luego introduce `KentLevel` que **es** un score escalar con etiquetas verbales. La diferencia es cosmética. El sistema podrá decir "no usamos números, usamos palabras", pero la información operativa que un usuario externo extrae es la misma que extraería de un número.

### 3.4. El grafo de conocimiento sin reasoner es honesto pero limitante

ADR-0011 prohíbe auto-inferencia para proteger P10. Bien. Pero el efecto es que el grafo, construido manualmente arista por arista, será siempre incompleto. Y las queries útiles de varios saltos producirán resultados parciales sin que el usuario lo sepa. "Sin inferencia" suena puro; en la práctica significa "el grafo no sabe lo que ningún humano explícitamente metió".

### 3.5. La inmutabilidad del modelo de evidencia es teórica

ADR-0006 declara inmutabilidad. El mundo real tiene:

- Errores de ingestión (parser equivocó, output corrupto).
- Cambios de schema (algún campo se renombró).
- Re-procesamiento masivo (cambio de algoritmo de hash, migración de format).

El sistema dice "se ingesta una nueva versión derivada". En la práctica, la fragmentación del histórico hace consultas más lentas y caros, y el conteo de "versiones reales" del mismo artefacto explota. Después de cinco años, una evidencia famosa puede tener 20 versiones derivadas y nadie sabe cuál usar. La inmutabilidad pasa de virtud a fricción.

---

## 4. Crítica al lifecycle de caso

### 4.1. La cadena lineal de revisiones es ingenua para colaboración real

ADR-0010 elige cadena lineal con justificación "DAG es complejo, no hay demanda". Esto funciona mientras un solo curador opera un caso. En el momento que dos investigadores discrepan sustantivamente sobre interpretación, el modelo obliga a fork (caso distinto con `derived_from`), lo cual:

- Duplica esfuerzo de mantenimiento.
- Fragmenta evidencia y razonamiento.
- Pierde la capacidad de presentar al lector externo "este es **el** caso X con su pluralidad de interpretaciones".

El campo ya sufre de fragmentación; esta arquitectura la institucionaliza.

### 4.2. `disputed` como estado tiene incentivos perversos

Cualquier persona con suficiente disciplina documental puede disputar un caso para obligar revisión. El sistema espera buena fe. Una vez que el archivo es citable y sirve como referencia, los incentivos para disputa táctica crecen. ADR-0010 no contempla cómo gestionar disputa adversarial.

### 4.3. La inmutabilidad de revisiones produce churn

Cada cambio sustantivo genera revisión nueva. Para casos vivos con afluencia de evidencia, el historial crece sin límite. El consumidor externo que quiere "el caso" tiene que decidir entre `head` (vivo) y una revisión específica (potencialmente obsoleta). En la práctica los citadores externos elegirán `head` y citarán un objeto en movimiento, anulando la promesa de reproducibilidad académica.

---

## 5. Crítica a la estrategia OSINT

### 5.1. El "código de prácticas" no es vinculante

ADR-0014 promete un código documentado que cualquier adquisidor debe respetar. En la práctica:

- Los códigos voluntarios se erosionan con presión por cobertura.
- Si un colaborador presenta PR con adquisidor que técnicamente cumple los criterios pero éticamente es problemático, el mantenedor único enfrenta presión social.
- "Respeto de TOS" es interpretable; cada plataforma tiene zonas grises que la presión por cobertura empujará a explotar.

### 5.2. La política conservadora sobre redes sociales sacrifica datos críticos

Mucho del material contemporáneo más relevante (reportes inmediatos de testigos, evidencia visual con metadata EXIF intacta) vive en redes sociales. Excluirlo "por conservadurismo" produce un archivo retrasado respecto a la realidad del campo. El proyecto no será adoptado por investigadores que necesitan ese material; lo será solo por archivistas históricos.

### 5.3. WARC como contenedor archivístico es maduro pero las dependencias asociadas no

WARC en sí es estándar. Las librerías para producir, parsear y rederivar contenido desde WARC en Python son menos maduras que el formato. El proyecto adopta una pieza estable encima de un ecosistema frágil. Cuando una librería se rompe, el formato sigue siendo correcto y el contenido inaccesible.

---

## 6. Crítica a las decisiones de storage e infraestructura

### 6.1. DuckDB es excelente y único punto de falla

ADR-0015 apuesta fuerte por DuckDB para queries analíticas y geoespaciales. DuckDB es maravilloso pero:

- Es un proyecto joven con ritmo de cambio rápido.
- Cambios de versión pueden romper queries en sutilezas no documentadas.
- Extensiones (spatial, FTS) tienen su propio ritmo de cambio.

Comprometer la fuente de verdad del proyecto a una única tecnología joven es riesgo concentrado. ADR-0015 no aborda contingencia si DuckDB pivotea o se discontinúa.

### 6.2. Parquet como formato y as is, no es eterno

Parquet evolucionará. Cambios de spec pueden romper datasets antiguos. El proyecto asume implícitamente que Parquet seguirá siendo legible en décadas. Lo mismo se asumió de tantos otros formatos columnar que hoy son arqueología.

### 6.3. CAOS basado en filesystem es robusto pero limitado en escala

Filesystems con millones de inodos en `objects/sha256/00/...` empiezan a tener problemas operativos (listing, backup, sync). El proyecto asume operación en disco con millones de blobs. Eso es realista con archivos modestos; con archivos masivos requiere capas de organización adicionales no documentadas.

---

## 7. Crítica a la API y al modelo de búsqueda

### 7.1. Tres superficies API es un compromiso, no una virtud

ADR-0017 mantiene CLI, Python y HTTP. Cada superficie tiene su propio backlog de bugs, casos límite y documentación. "Mismas reglas, misma semántica" suena bonito y en la práctica diverge. Después de tres releases, los usuarios reportan que la API Python permite cosas que la HTTP rechaza, y viceversa.

### 7.2. Búsqueda semántica "auxiliar" será autoritativa en la práctica

ADR-0018 establece que la búsqueda semántica es auxiliar y no citable. Bien. Pero la realidad es que los usuarios la usarán como primer puerto de entrada y la formularán como query reproducible solo en publicaciones. Esto significa que el descubrimiento real de evidencia depende de un sistema no reproducible, y la reproducibilidad académica es teatro post-hoc. El proyecto no tiene defensa contra esto.

### 7.3. Diccionario de sinónimos versionado es trabajo infinito

Mantenerlo requiere expertise lingüística cross-cultural y cross-temporal. Para un proyecto que aspira a cubrir reportes desde la antigüedad hasta hoy en múltiples idiomas, este trabajo es desmesurado. Sin ese mantenimiento, la búsqueda léxica pierde capacidad y los usuarios migran al modo semántico (que el sistema dice que no es autoritativo).

---

## 8. Crítica al marco ético

### 8.1. Mecanismo de takedown es desigual

Una persona con recursos legales (abogado, equipo de PR) puede ejercer takedown con verificación trivial. Una persona sin recursos enfrenta verificación que probablemente no puede completar. El sistema introduce sesgo de clase en quién protege su privacidad.

### 8.2. La negativa a deanonymization es declarativa

"El proyecto no provee funcionalidad nativa para deanonymization". El proyecto provee un grafo de conocimiento, búsqueda combinada estructurada+léxica, y API completa. Cualquier capacidad de cruce que produzca deanonymization puede construirse con esas herramientas. La negativa es performativa.

### 8.3. La política sobre material clasificado es inestable

"El proyecto no es canal de filtración". Bien. ¿Qué pasa cuando un colaborador ingesta material en la zona gris (publicado por leaker, no confirmado clasificado)? El procedimiento ADR-0020 dice "caso por caso", lo cual es decisión política sostenida por una persona. Bajo presión, esa persona toma decisiones que pueden no resistir escrutinio posterior.

### 8.4. La revisión ética anual presupone continuidad de carácter

El marco ético es estable mientras el mantenedor fundador opera. La sustitución del mantenedor —que P12 contempla— es punto de fragilidad: un sucesor con ética distinta hereda la arquitectura y la usa diferente. El proyecto no tiene defensa estructural contra captura por sucesión.

---

## 9. Crítica al modelo de sostenibilidad

### 9.1. "Maintainer único, part-time, sin compromiso" es honesto y frágil

El propio ADR-0000 reconoce la fragilidad. Lo que no se reconoce: el alcance del proyecto (24 ADRs antes de código, 6 fases, modelo de evidencia complejo, grafo de conocimiento, motor temporal/geoespacial, OSINT, ética) **excede** capacidad realista de un mantenedor único part-time.

Estimación honesta: solo Fase 1 (modelo de evidencia y fuentes) implementada con la calidad que los ADRs prometen requiere ~6–12 meses de trabajo full-time. F1+F2 con la disciplina prometida, 18–24 meses full-time. El proyecto a una persona part-time entrará en estado de **vaporware perpetuo** en la fase de implementación, con cada vez más documentación de planes y cada vez menos software.

### 9.2. Las condiciones de archivo digno son ambiguas

"Doce meses sin capacidad de respuesta a issues críticos" exige que existan issues críticos —que solo existen si hay usuarios— que solo existe si hay software. Una circularidad: el proyecto no se archivará por inactividad porque nunca tendrá la actividad necesaria para que el criterio de inactividad dispare.

---

## 10. Crítica a la asunción de adopción

### 10.1. El "ecosistema" presupuesto no es claro que llegará

El proyecto se diseña como infraestructura sobre la que se construirán productos derivados. Para que eso ocurra:

- Tiene que existir software funcional. (Punto 9.1.)
- El software tiene que ser usable por la audiencia primaria. Investigadores académicos prefieren formatos con los que ya operan (CSV, Excel, SPSS, JSON estándar). El modelo formal de AIP introduce curva de aprendizaje no trivial.
- Las organizaciones civiles existentes tienen ya sus propias herramientas (CMSes propios, hojas de cálculo). Migrar sus archivos a AIP exige esfuerzo que ninguna recompensa inmediata justifica.

La adopción esperada es plausible solo si el proyecto demuestra valor entregando algo, no documentando algo. El estado actual (pre-código, todo documentación) no genera adopción; consume credibilidad inicial.

### 10.2. Citabilidad académica requiere validación de pares

El proyecto promete que sus snapshots serán citables académicamente. Para que una revista o conferencia acepte una cita `aip:case/...@hash`, el proyecto necesita:

- Infraestructura de resolución persistente (¿quién aloja los snapshots? ¿Zenodo? El proyecto no controla esto).
- Reconocimiento por las revistas relevantes (que las hay pocas en el campo y son cautelosas).
- Caso de uso demostrado.

Sin ese trabajo de validación, las "citas" terminarán siendo enlaces a repositorios GitHub que pueden desaparecer.

---

## 11. Modos plausibles de fracaso

Combinando los puntos anteriores, los modos de fracaso más probables:

| Modo | Descripción | Probabilidad |
|------|-------------|--------------|
| Vaporware perpetuo | Proyecto entrega ADRs y mucha doc, nunca produce software usable | Alto |
| Captura por mantenedor sucesor | Mantenedor fundador desaparece, sucesor reorienta sustantivamente | Medio |
| Erosión de neutralidad por presión | La famosa "neutralidad de hipótesis" cede ante presión de comunidad activa | Medio |
| Fragmentación por fork | Discrepancias importantes se modelan como casos distintos hasta colapsar el archivo | Medio |
| Filtración de datos personales por agregación | Pese a salvaguardas, alguien combina exportes y daña a testigos | Bajo-medio |
| Dependencia crítica que se rompe | DuckDB o Parquet pivotan, el proyecto no tiene capacidad de migrar | Medio |
| Litigio por material en zona gris | Material sensible ingestado provoca demanda; proyecto no tiene defensa legal | Bajo-medio |
| Adopción nula | Nunca pasa de proyecto del autor; archivado por las propias condiciones del ADR-0000 | Medio-alto |

---

## 12. Veredicto del revisor

El cuerpo de ADRs es **excepcionalmente sofisticado para un proyecto sin código**. Eso es a la vez su mayor virtud y su mayor síntoma.

- Virtud: las decisiones están razonadas, las propiedades son explícitas, los trade-offs documentados.
- Síntoma: el proyecto ha invertido en pensamiento mucho más que lo razonable antes de ensuciar las manos con código. Eso suele indicar uno de dos patrones: (a) un mantenedor que cree que la calidad del diseño previo puede compensar la fragilidad de la entrega, o (b) un mantenedor que disfruta más diseñando que construyendo. Ambos terminan en vaporware con frecuencia alarmante.

Recomendaciones desde la posición hostil:

1. **Recortar el alcance brutalmente.** Fase 1 con CLI mínima que ingesta y consulta. Punto. Todo lo demás se evalúa después.
2. **Aceptar que P3 (incertidumbre cuantificada) en sentido fuerte es aspiración, no propiedad real para V1.** Operacionalizar con `KentLevel` solo es honesto.
3. **Reducir la promesa de "infraestructura mundial".** Posicionar como "herramienta de un investigador" inicialmente. La promesa grande termina disminuyendo la credibilidad cuando la entrega es modesta.
4. **Eliminar la pretensión de neutralidad pura.** Adoptar postura honesta: "el proyecto prefiere hipótesis falsables; cualquier hipótesis que no quepa en el modelo no participa de evaluación competitiva en el sistema, pero puede vivir como `Conjecture`". Eso es más defendible que "somos neutros".
5. **Considerar GPL/AGPL en lugar de Apache.** El razonamiento "queremos que se construya sobre nosotros" suena bien y dejará el proyecto sin reciprocidad cuando alguien lo fork comercialice. La defensa de "ecosistema compartido" requiere copyleft para ser efectiva en este campo concreto.
6. **Documentar la fragilidad del modelo de un mantenedor.** El ADR-0000 dice "puede archivarse"; debería decir "probablemente se archivará si no hay incorporación adicional, y aquí está el plan para que eso ocurra dignamente".

El proyecto, en su forma actual, es una declaración filosófica importante con un riesgo de implementación real. Vale la pena, pero el revisor hostil no apostaría su reputación a su éxito.

---

## Apéndice: lista compacta de hallazgos por ADR

| ADR | Hallazgos críticos |
|-----|--------------------|
| 0000 | P4 no es realmente neutral. P2 es performativa. P7 sobrestima portátil. Modelo de sostenibilidad incompatible con alcance. |
| 0001 | Las cinco categorías son occidentales contemporáneas, no universales. Frontera Fact/Claim es borrosa. |
| 0002 | Evidence-first es elegante; complica retracción operativa con masas de versiones derivadas. |
| 0003 | Local-first con archivos públicos masivos es contradicción no resuelta. |
| 0004 | Linearidad estricta de fases es ideal académico; bloquea adopción por entregar tarde. |
| 0005 | Procedencia declarada presupone disciplina improbable bajo carga. |
| 0006 | Inmutabilidad produce churn. AuthenticationAssessment es estructura inacumulable sin equipo. |
| 0007 | Modalidad y contexto preservan riqueza; ingreso real será mínimo. |
| 0008 | Falsabilidad operativa privilegia hipótesis ordinarias. |
| 0009 | KentLevel es score escalar disfrazado. |
| 0010 | Linealidad bloquea colaboración real. Disputed es vector de abuso táctico. |
| 0011 | Grafo sin reasoner es honesto y limitante. Vocabulario controlado es trabajo infinito. |
| 0012 | Modelo temporal es excelente y casi nadie lo usará bien sin tooling especializado. |
| 0013 | Modelo geoespacial análogo: rico, exigente. |
| 0014 | Código OSINT no vinculante. Política de redes sociales reduce relevancia contemporánea. |
| 0015 | DuckDB es punto único de falla concentrado. |
| 0016 | Migración de hash es aspiracional; en décadas falla. |
| 0017 | Tres superficies divergerán. |
| 0018 | Búsqueda semántica será autoritativa en uso real, citación reproducible es teatro. |
| 0019 | Enclave depende de disciplina del operador; en práctica se relajará. |
| 0020 | Takedown introduce sesgo de clase. Negativa a deanonymization es declarativa. |
| 0021 | LlmAssist flow es teóricamente puro y operativamente improbable bajo carga. |
| 0022 | Apache permite captura comercial sin reciprocidad; el proyecto la celebra como adopción. |

---

*Esta revisión no recibe respuesta de los mantenedores. Cualquier corrección entra como ADR de enmienda. La crítica permanece para que un futuro lector vea el diseño tal como lo expuso un crítico hostil al momento de su redacción.*
