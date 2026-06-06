# ADR-0000: Visión a largo plazo del Anomaly Intelligence Platform

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** todos los ADR posteriores

---

## Naturaleza de este documento

Los ADR habitualmente capturan decisiones técnicas con consecuencias acotadas: qué base de datos, qué motor de búsqueda, qué formato de serialización. Este ADR captura algo distinto: la brújula.

Antes de elegir cualquier tecnología, este documento fija qué problema resuelve el proyecto, para quién, y bajo qué propiedades irrenunciables. Sin esa brújula, los ADR técnicos posteriores no pueden evaluarse como buenos o malos; solo como coherentes o incoherentes con un marco. Este ADR construye ese marco.

Cualquier ADR posterior debe declarar explícitamente cómo se alinea con éste. Si un ADR técnico entra en tensión con alguna de las propiedades irrenunciables aquí enumeradas, esa tensión debe declararse y justificarse, no ocultarse.

## Contexto

El estudio de los fenómenos anómalos —observaciones aéreas, orbitales, marítimas, astronómicas o atmosféricas que no se explican trivialmente con los modelos disponibles— vive desde hace ochenta años en una pinza desafortunada:

1. **Sistemas oficiales opacos.** Programas estatales (Project Blue Book, GEPAN/SEPRA/GEIPAN, AAWSAP/AATIP, AARO) producen archivos parciales, frecuentemente desclasificados a destiempo, sin acceso público a la cadena de evidencia ni a los criterios de evaluación.
2. **Comunidades de investigadores fragmentadas.** Organizaciones civiles (NICAP, CUFOS, MUFON, NUFORC, GEIPAN ciudadano, EuroUFO, etc.) acumulan reportes valiosos pero con esquemas incompatibles, niveles de rigor heterogéneos, y archivos que se deterioran físicamente o se pierden cuando un mantenedor desaparece.
3. **Mercado de contenido.** Plataformas mediáticas, productoras de TV, podcasts y editoriales generan un flujo continuo de afirmaciones sin trazabilidad, mezclando hechos verificables con interpretaciones y conclusiones extraordinarias, optimizando para atención y no para verdad.
4. **Software académico aislado.** Existen esfuerzos serios (UAPx, Galileo Project, SCU, varias tesis) pero sin una infraestructura común reutilizable: cada grupo reconstruye su pipeline de cero.

Falta una quinta categoría: una **infraestructura abierta, rigurosa, mantenida y epistémicamente honesta** que permita organizar reportes —históricos y modernos— sobre un modelo de evidencia formal, con incertidumbre cuantificada como ciudadano de primera clase, ejecutable por cualquier investigador con un portátil moderno.

AIP propone ocupar esa categoría.

## Misión

Construir la plataforma open source más rigurosa posible para **medir, organizar, trazar, comparar y cuantificar la incertidumbre** que rodea a los reportes de fenómenos anómalos, sin asumir ninguna conclusión sustantiva.

Cada palabra es deliberada:

- **Rigurosa** — el sesgo por defecto del proyecto es la falsabilidad y la trazabilidad, no el entusiasmo.
- **Medir, organizar, trazar, comparar, cuantificar** — cinco verbos infraestructurales, ninguno conclusivo.
- **Incertidumbre como ciudadano de primera clase** — todo objeto del sistema lleva su error, sus supuestos, y sus contradicciones internas explícitas.
- **Sin asumir ninguna conclusión sustantiva** — la plataforma no toma postura sobre el origen de los fenómenos. Cualquier diseño que la sesgue queda fuera.

## La pregunta central

La plataforma no responde a:

> "¿Qué es esto?"

La plataforma responde a:

> "¿Qué nivel de confianza podemos asignar, con honestidad epistémica, a cada hipótesis competidora que explique este reporte?"

Esa reformulación es el ADN del proyecto. El sistema **siempre** organiza la información en torno a hipótesis competidoras evaluadas con evidencia trazable, y nunca privilegia arquitectónicamente una hipótesis sobre otra.

Hipótesis competidoras típicas para un reporte aéreo:
- Identificación errónea (planeta, satélite, globo, dron, avión convencional, fenómeno atmosférico).
- Fabricación deliberada o engaño.
- Error del observador (memoria, percepción, expectativa).
- Sistema operacional clasificado (militar nacional o extranjero).
- Fenómeno natural raro pero conocido (rayo en bola, lente óptica atmosférica, halos).
- Fenómeno natural no caracterizado.
- Tecnología no caracterizada de origen humano.
- Otra hipótesis sustantiva.

El sistema soporta todas, no privilegia ninguna, y exige que cada una se evalúe con evidencia y supuestos explícitos.

## Horizonte de mantenimiento como heurística de diseño

Las decisiones arquitectónicas de este proyecto deberán evaluarse asumiendo un horizonte mínimo de cinco años de mantenimiento potencial, con aspiración a décadas. El campo cubre reportes con dos mil años de antigüedad; la infraestructura que lo organiza debe pensarse también en esa escala.

Esto no es un compromiso del autor con un calendario, sino una regla para evaluar trade-offs: una decisión cuyo coste agregado en una ventana de cinco años supera el de una alternativa razonable no debe adoptarse aunque sea atractiva a corto plazo. El horizonte es la lente, no la promesa.

## Visión de estado deseado

Estado del proyecto cuando esté maduro, descrito sin referencias temporales:

- Es la **infraestructura de referencia** para investigación abierta sobre fenómenos anómalos. Cualquier estudio académico, periodístico o ciudadano serio puede construirse sobre ella sin reinventar el modelo de datos.
- Mantiene un **archivo histórico continuo y verificable** que cubre reportes desde la antigüedad hasta la actualidad, con cadena de evidencia para cada uno y direccionamiento por hash de cada artefacto crudo.
- Su **modelo de evidencia** ha sido adoptado, citado o adaptado por al menos un programa académico independiente.
- Su **cuantificación de incertidumbre** es defendible: cada conclusión lleva su evidencia favorable, su evidencia contradictoria, sus supuestos, sus preguntas abiertas, y la familia de hipótesis competidoras consideradas.
- **Sigue ejecutándose en un portátil moderno** como producto principal. Cualquier desviación de esto exige ADR explícito.
- Es **citable**. Cualquier afirmación derivada del sistema lleva un identificador estable que un revisor externo puede resolver al estado exacto del archivo en ese momento.

"Maduro" no es una fecha. Es un estado verificable. Si la verificación falla durante un tiempo prolongado, la sección de condiciones de archivo digno aplica.

## Audiencias

### Audiencia primaria
- Investigadores académicos en historia de la ciencia, sociología, psicología, atmosféricas, astronomía, defensa, y campos afines.
- Periodistas de investigación que necesitan trazabilidad de evidencia.
- Archivistas y bibliotecarios trabajando con fondos sobre fenómenos anómalos (Hynek Center, Sign Oral History Project, archivos GEIPAN, fondos privados donados).
- Organizaciones civiles de reporte (CMI, MUFON capítulos, NUFORC, GEIPAN ciudadano y equivalentes nacionales) que quieran publicar sus archivos sobre un esquema común.
- Investigadores ciudadanos rigurosos con base técnica.

### Audiencia secundaria
- Cualquier proyecto o entidad que construya productos derivados sobre AIP. La licencia permisiva (Apache 2.0) habilita ese uso sin filtros sobre tipo de aplicación.
- Educadores en pensamiento crítico, epistemología y metodología científica que usen el sistema como caso de estudio sobre cómo se razona bajo incertidumbre.

### No-audiencia
- Usuarios buscando confirmación de creencias preexistentes. El sistema no entrega conclusiones sustantivas; entrega distribuciones de confianza sobre hipótesis competidoras.
- Productoras de contenido que necesiten material sensacionalista. La plataforma es deliberadamente aburrida para uso recreativo: muestra incertidumbre en lugar de esconderla.
- Operadores que necesiten outputs aplicables sin verificación independiente. Los outputs del sistema son analíticos, no operativos.

Reconocer la no-audiencia es una declaración de límites del proyecto, no un juicio sobre quién está autorizado a usar el código.

## Propiedades irrenunciables

Estas propiedades son invariantes del sistema. Ningún ADR posterior puede violarlas. Si un ADR posterior necesita relajar alguna, debe superseder a este ADR-0000 explícitamente, justificando por qué la propiedad ya no aplica.

### P1. Separación estricta de categorías epistémicas

El sistema distingue de forma arquitectónica, no editorial, cinco categorías:

- **Hecho** — verificable independientemente, con cadena de custodia material.
- **Afirmación** — atribuible a una fuente identificada, no necesariamente verificada.
- **Interpretación** — lectura humana de hechos o afirmaciones, declarada como tal.
- **Hipótesis** — explicación competidora formulada de manera que pueda ser favorecida o desfavorecida por evidencia.
- **Conclusión** — evaluación de confianza relativa entre hipótesis, siempre revisable.

Estas categorías son **tipos del modelo de datos**, no etiquetas convencionales. Un objeto del sistema sabe en qué categoría vive y no puede mutar entre categorías sin un evento explícito y trazable.

### P2. Trazabilidad bit a bit

Cualquier inferencia del sistema, hoy o en el pasado, debe poder reproducirse a partir de:
- los datos crudos hasheados que la originaron,
- la versión exacta del algoritmo o lógica que la produjo,
- los parámetros usados,
- las versiones de las dependencias y modelos relevantes.

Esta propiedad es la diferencia entre una herramienta científica y una opinión bonita.

### P3. Incertidumbre cuantificada como first-class citizen

Toda visualización, API, reporte y salida del sistema representa incertidumbre. La incertidumbre incluye:
- Confianza puntual o distribución sobre hipótesis competidoras.
- Evidencia favorable y contradictoria, no solo el score agregado.
- Supuestos asumidos.
- Preguntas abiertas no resueltas.

Una conclusión sin esos cinco elementos visibles no es una conclusión del sistema; es un bug.

### P4. Neutralidad de hipótesis

El sistema no privilegia arquitectónicamente ninguna hipótesis sustantiva sobre el origen de los fenómenos. Esto incluye:
- No hay un "flag de UAP genuino" en el modelo de datos.
- No hay un esquema de "casos resueltos vs. inexplicables" donde "inexplicable" arrastre carga sustantiva implícita.
- No hay rankings editoriales sobre qué hipótesis es "más razonable" fuera de la evidencia ingresada.

La neutralidad no es agnosticismo blando: es la negativa estructural a colocar el dedo en la balanza desde la infraestructura.

### P5. Reproducibilidad

Cualquier resultado del sistema debe poder reproducirse partiendo del repositorio, los datos crudos referenciados por hash y un entorno especificado. No hay "se ejecuta en mi máquina" aceptable. No hay "no podemos publicar la evidencia por razones internas" en el núcleo abierto.

### P6. Local-first

Toda funcionalidad fundamental del sistema debe poder ejecutarse localmente, sin conexión a servicios externos. Servicios externos pueden ampliar capacidades pero nunca son dependencia obligatoria del flujo de investigación básico. Operacionalizada en ADR-0003.

### P7. Coste de operación cercano a cero

El proyecto debe poder ejecutarse, en su totalidad, en un portátil doméstico moderno sin servicios de pago. Las APIs externas de pago son siempre opcionales y nunca camino crítico. Esto excluye arquitecturas con dependencias caras de tiempo de ejecución (LLMs propietarios obligatorios, bases gráficas comerciales, sistemas de búsqueda gestionados como dependencia primaria).

### P8. Documentación al mismo nivel que el código

Una funcionalidad sin documentación de usuario no se considera entregada. Una decisión sin ADR no se considera tomada. No es burocracia: es la condición de supervivencia del proyecto si cambia el mantenedor o si un investigador externo debe entender el sistema cinco años después.

### P9. Fuentes públicas y reproducibles como primarias

Cualquier capacidad del sistema debe ser obtenible con fuentes públicas. Datos privados, propietarios o restringidos pueden coexistir como complemento opcional, pero el núcleo abierto debe funcionar exclusivamente con material accesible públicamente. Criterio práctico: si un nuevo investigador no puede reproducir un resultado sin acceso privilegiado, ese resultado no pertenece al núcleo.

### P10. No fabricación, no alucinación, no narrativización

El sistema **no genera** afirmaciones que no estén ancladas en evidencia ingresada. Modelos de lenguaje grandes pueden usarse como herramientas auxiliares (extracción de entidades, traducción, sumarización con cita), pero su salida nunca entra al modelo de evidencia como hecho, afirmación, interpretación, hipótesis o conclusión sin proceso humano de verificación y atribución. Operacionalizada en ADR-0021.

### P11. Inmutabilidad de la evidencia cruda

Los artefactos crudos ingestados (imágenes originales, audios, documentos escaneados, transcripciones primarias) son inmutables y direccionables por hash. Las transformaciones (recortes, mejoras, traducciones) viven como artefactos derivados con su propia cadena de procedencia. Borrar evidencia cruda del núcleo es un acto excepcional, registrado, y motivado solo por razones legales o de daño concreto (P12).

### P12. Do-no-harm

El sistema no expone información que produce daño concreto a personas identificables sin contrapeso de interés público proporcional. Esto incluye:
- Anonimización de testigos donde el consentimiento original no cubre publicación.
- Mecanismo de takedown por testigo verificable.
- Política explícita sobre datos sensibles (médicos, geolocalización en tiempo real, menores).

La libertad de información no es absoluta cuando colisiona con daños evitables a personas concretas. Esta propiedad está operacionalizada en ADR-0019 y ADR-0020.

## No-objetivos explícitos

Lo que este proyecto **nunca** será, mientras ADR-0000 esté vigente:

- **No declarará origen extraterrestre, interdimensional, ni de ninguna otra naturaleza sustantiva.** El sistema entrega distribuciones de confianza, no veredictos.
- **No promoverá teorías conspirativas, marcos ideológicos ni agendas políticas.**
- **No producirá contenido optimizado para viralidad.**
- **No será un servicio gestionado comercial.** Si alguien quiere construirlo encima, la licencia lo permite; no es responsabilidad del proyecto.
- **No reemplazará a las autoridades de investigación oficial.** Coexiste, archiva, organiza y ofrece infraestructura; no opera como autoridad sustantiva.
- **No publicará material que viole derechos de testigos identificables sin contrapeso de interés público proporcional.**
- **No alojará evidencia clasificada activa.** Si llega material que se determina clasificado vigente, se aplica el procedimiento de excepción de P11 y se documenta la decisión.

## Disclaimer operacional

AIP no proporciona garantías operacionales para usos civiles, comerciales, gubernamentales o militares. Los outputs del sistema son material analítico, no recomendaciones aplicables sin verificación independiente. Cualquier uso aplicado es responsabilidad exclusiva del usuario.

Este disclaimer es técnicamente neutro: el proyecto no filtra usuarios ni casos de uso más allá de lo que exigen las propiedades P10 y P12 y el marco ético del ADR-0020. La licencia Apache-2.0 reafirma esa neutralidad.

## Cumplimiento legal de fuentes

Los proveedores de datos públicos (archivos nacionales desclasificados, repositorios académicos, archivos de organizaciones civiles que publican bajo licencias específicas) establecen términos de uso como condición de acceso. El proyecto los respeta. Si un término de servicio cambia y limita una capacidad, el proyecto se adapta o documenta la limitación.

Los reportes con testigos vivos identificables están sujetos a regulaciones de protección de datos personales (GDPR en la UE, LFPDPPP en México, leyes equivalentes en otras jurisdicciones). El núcleo del sistema cumple esas regulaciones por construcción.

## Modelo de sostenibilidad

El proyecto debe sobrevivir sin presupuesto y sin equipo dedicado.

**Estado inicial.** Maintainer único: el autor fundador. Trabajo part-time sostenido, sin compromiso de cadencia. Aceptación de PRs externas reactiva.

**Estado intermedio.** Posibles co-maintainers si emerge contribución externa sostenida. Governance ligera y documentada: política de revisión, criterios de merge, criterios de inclusión de archivos.

**Estado consolidado.** Posible afiliación a una fundación neutra (NumFOCUS, OpenSSF, OpenCollective, archivos universitarios) si la base de usuarios lo justifica y si la fundación no introduce sesgos sustantivos sobre las hipótesis. Hasta entonces, ninguna estructura legal añadida.

**Governance.** El proyecto declara públicamente quién lo mantiene en cada momento, en `MAINTAINERS.md`. La identidad de los mantenedores es información estructural, no biográfica.

Ningún modelo de monetización es objetivo. Donaciones pasivas (GitHub Sponsors, OpenCollective sin sponsors con interés sustantivo en el campo) aceptables si no condicionan la dirección.

Cualquier momento en el que sostener el proyecto requiera una promesa que no se pueda cumplir es un momento para reducir alcance, no para acelerar.

## Condiciones de archivo digno

Un proyecto de horizonte largo debe declarar de antemano bajo qué condiciones se cierra. Archivar a tiempo es responsabilidad; archivar tarde es daño.

AIP se archivará — con notificación pública, último release estable, y documentación clara del estado final — si se cumple alguna de:

1. **Inviabilidad epistémica demostrada**: si se demuestra que el modelo de evidencia no captura propiedades esenciales del campo que ningún ajuste pueda recuperar.
2. **Colapso de fuentes**: si las fuentes públicas críticas (archivos desclasificados, registros civiles) desaparecen o pasan a régimen cerrado durante más de doce meses sin alternativa equivalente.
3. **Insostenibilidad de mantenimiento**: si durante doce meses consecutivos no hay capacidad de respuesta a issues críticos ni reemplazo viable del mantenedor.
4. **Captura por intereses incompatibles con las propiedades irrenunciables**: si el control del proyecto pasa, por cualquier vía, a un actor cuyo uso del mismo viole P1–P12. Esto incluye captura por movimientos ideológicos en cualquier dirección del campo.
5. **Daño documentado a testigos por el propio sistema**: si el sistema, por defecto de diseño y no por mal uso de terceros, ha producido daño concreto a personas y la corrección no es posible sin violar otras propiedades.

En cualquiera de esos casos, el proyecto se archiva en estado legible, con un `ARCHIVED.md` que explique por qué, y la licencia permisiva garantiza que cualquier interesado pueda continuar el código sin colaboración previa.

## Cómo evaluamos salud del proyecto

Sin métricas numéricas dogmáticas atadas a calendario. Cada release publica una evaluación cualitativa sobre seis ejes:

1. **Cobertura del archivo.** Qué fracción del material público sobre el campo está accesible desde el sistema, y desde qué fuentes. Se reporta el dato bruto, no un objetivo.
2. **Calidad epistémica.** Distribución de casos por categoría de evidencia, distribución de confianza, número de casos con hipótesis competidoras explícitas vs. casos con hipótesis única.
3. **Trazabilidad operativa.** Capacidad de regenerar cualquier output histórico desde los datos crudos por hash. Se verifica con tests de regresión que reejecutan inferencias antiguas.
4. **Diversidad de fuentes.** Que el archivo no esté capturado por un único proveedor de material ni una única perspectiva.
5. **Citabilidad.** Número de citas académicas, periodísticas o judiciales que apuntan a snapshots del sistema vs. número total de releases.
6. **Salud de mantenimiento.** Tiempo de CI, antigüedad de issues sin triar, frecuencia de releases. Sin objetivos numéricos rígidos; lo importante es la tendencia y la honestidad sobre ella.

Si alguno de estos ejes se degrada sostenidamente sin explicación, debe disparar el ejercicio de revisión del ADR-0000.

## Cómo este ADR limita a los siguientes

Todo ADR técnico posterior debe incluir una sección **"Alineación con ADR-0000"** que conteste:

1. ¿Cuáles de las propiedades irrenunciables P1–P12 ve afectadas esta decisión?
2. ¿La decisión las refuerza, las mantiene neutras, o introduce alguna tensión?
3. Si hay tensión, ¿cuál es la mitigación o por qué la tensión es aceptable?

La plantilla de ADR (`template.md`) incluye esta sección. Una PR con un ADR que la omita no debe mergearse.

## Revisión de este ADR

Este ADR se revisa formalmente con cadencia anual. La revisión puede resultar en:

- **Confirmación sin cambios** (lo normal en períodos de continuidad).
- **Enmienda** añadida al historial al pie, sin reescribir el cuerpo.
- **Supersesión** por un ADR-0000-v2 si la visión cambia sustancialmente. Las supersesiones requieren consenso explícito de los mantenedores activos y una revisión externa documentada en `docs/reviews/`.

## Alineación con ADR-0000

(Sección obligatoria en todos los ADR. En este caso particular, ADR-0000 **es** la visión, por lo que la sección queda como sigue:)

Este ADR define las propiedades de referencia. No se alinea con nadie; los demás se alinean con él.

## Referencias

- Hynek, J. A. (1972). *The UFO Experience: A Scientific Inquiry.*
- Vallée, J. (1990). *Confrontations: A Scientist's Search for Alien Contact.*
- Sagan, C. (1996). *The Demon-Haunted World: Science as a Candle in the Dark.*
- Galileo Project (Loeb et al.). Public documentation and observational protocols.
- AARO (All-domain Anomaly Resolution Office). Public reports.
- GEIPAN / CNES. Procedimientos de catalogación pública.
- Nygard, M. (2011). *Documenting Architecture Decisions.*
- Pearl, J., & Mackenzie, D. (2018). *The Book of Why.* (Por su tratamiento de causalidad e inferencia.)
- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.* (Marco formal de evidencia.)
- Apache Software Foundation. *Apache License, Version 2.0*.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
