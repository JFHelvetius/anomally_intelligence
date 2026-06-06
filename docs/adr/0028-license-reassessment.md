# ADR-0028: License Reassessment — re-examen explícito de Apache 2.0 frente a copyleft

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0022, ADR-0026

---

## Contexto

ADR-0022 estableció Apache License 2.0 como licencia del proyecto con justificación detallada. El Red Team Review §12 (Verdict 5) recomienda re-examinar la decisión:

> "Considerar GPL/AGPL en lugar de Apache. El razonamiento 'queremos que se construya sobre nosotros' suena bien y dejará el proyecto sin reciprocidad cuando alguien lo fork comercialice. La defensa de 'ecosistema compartido' requiere copyleft para ser efectiva en este campo concreto."

El argumento del revisor es sustantivo y merece respuesta formal, no descarte por estilo. En particular:

- El campo del estudio de fenómenos anómalos está históricamente capturado por actores que monetizan sin reciprocar (productoras de contenido, organizaciones que cobran por acceso a archivos que recibieron gratis, libros que reciclan material público sin atribuir).
- Una licencia permisiva como Apache facilita exactamente esa captura.
- AGPL es el contrapeso clásico cuando el modo SaaS es el vector de captura previsible.

Este ADR re-examina la decisión con disciplina, no la cambia automáticamente. La pregunta que el Red Team Review obliga a responder es: **¿qué evidencia haría falta para cambiar de Apache a GPL/AGPL, y por qué esa evidencia no existe hoy?**

## Decisión

Se **mantiene Apache License 2.0** como licencia del código. La decisión se reafirma con razonamiento explícito sobre la objeción del Red Team Review y se establecen **disparadores concretos** que dispararían reconsideración formal de la licencia mediante ADR posterior.

Adicionalmente, se **diferencia explícitamente** la licencia del **código** (Apache 2.0) de las licencias del **corpus de datos** que el sistema ingesta o genera, que pueden ser distintas.

## Justificación de la reafirmación

### Por qué Apache se reafirma a pesar de la crítica

La crítica del Red Team Review es correcta en su diagnóstico (Apache permite captura sin reciprocidad) y, en mi evaluación, **incorrecta en su prescripción** para esta arquitectura. Tres razones:

**Primera: AGPL no es defensa real contra la captura previsible en este campo.**

La captura típica en el campo no ocurre por re-distribución de software modificado. Ocurre por:
- Cobro de acceso a archivos de evidencia que el sistema ingestó libremente.
- Republicación de material como "investigación propia" sin atribución.
- Producción de contenido derivado (libros, documentales, podcasts) que usa el material analítico del sistema sin citar el archivo del que procede.

Ninguna de esas tres formas de captura se previene con copyleft de software. Son cuestiones de **licencia del corpus de datos**, **atribución académica**, y **reputación**, no de licencia del runtime.

**Segunda: copyleft excluye adopción institucional crítica para el éxito del proyecto.**

Universidades, archivos nacionales, organizaciones civiles serias tienen frecuentemente políticas que rechazan AGPL por miedo a contagio en sus propios sistemas. Adoptar AGPL maximiza la fracción del público objetivo del proyecto (audiencia primaria del ADR-0000) que **no podrá usarlo**.

El proyecto cuyo valor es ser **infraestructura compartida** no puede excluir estructuralmente a su audiencia primaria.

**Tercera: la defensa última contra captura es el fork bajo Apache, no la licencia copyleft.**

Si una entidad comercial captura el proyecto, deteriora su calidad, o lo reorienta sustantivamente, cualquier observador externo puede:
- Forkear el último estado abierto bajo Apache.
- Mantener el fork bajo Apache (o relicenciar a AGPL en el fork si lo justifica).
- Construir comunidad alrededor del fork.

Esta defensa **no es absoluta** —exige que alguien quiera mantener el fork— pero AGPL no la hace más fuerte; solo añade fricción de adopción.

### Por qué el riesgo del Red Team Review es real y no neutralizado

Reconocimiento honesto: la crítica identifica un riesgo que **se acepta como riesgo no eliminado**.

- Una entidad comercial puede forkear AIP, añadir features propietarios, ofrecerlo como SaaS, y no contribuir de vuelta. Apache lo permite.
- AIP como infraestructura compartida puede acabar siendo "el lado abierto" mientras el lado comercial domina la operación real del campo.

El proyecto opta por Apache **a pesar** de este riesgo, no por desconocerlo. La justificación es que la alternativa (excluir audiencia primaria) es peor.

## Diferenciación: licencia de código vs. licencia de corpus

ADR-0022 cubre exclusivamente el **código** del proyecto. El **corpus de datos** que el sistema ingesta o genera tiene licencias propias:

- **Material ingestado de fuentes externas:** conserva la licencia de la fuente original (dominio público, CC-BY, restricciones FOIA específicas, etc.). El sistema documenta la licencia en `Source.access_conditions` (ADR-0005).
- **Material generado por el sistema** (snapshots citables, exportaciones académicas, datasets de evaluación de fases futuras): adoptará licencia **Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)** como default.

CC BY-SA introduce reciprocidad copyleft específicamente sobre los **datos generados** por el sistema. Esto:

- Aborda la objeción del Red Team Review en su forma operativa real (el corpus es donde la captura por monetización ocurre).
- Preserva libertad de uso del código (Apache).
- Es coherente con prácticas académicas estándar (Wikipedia, OpenStreetMap, otros corpus colaborativos usan SA equivalente).

Esta separación —Apache para código, CC BY-SA para corpus— responde a la crítica donde realmente muerde sin sacrificar la adopción del código.

## Disparadores de reconsideración formal

La decisión se revisa por ADR posterior si ocurre **alguno** de los siguientes eventos:

D1. **Captura comercial documentada del proyecto** con daño claro a la integridad de las propiedades irrenunciables. Por ejemplo: una entidad comercial forkea AIP, añade features, monopoliza el espacio de "infraestructura para fenómenos anómalos" capturando a la audiencia primaria, y no contribuye al ecosistema. En ese caso, evaluar si re-licenciar el proyecto madre a AGPL prevendría escenarios futuros similares.

D2. **Cambio en el ecosistema de licencias que altere el cálculo institucional.** Por ejemplo: si universidades y archivos nacionales empiezan a aceptar AGPL sistemáticamente, la razón principal contra ella se debilita.

D3. **Adopción de gobernanza por fundación neutra** (NumFOCUS, OpenSSF, equivalente). En esos contextos, la elección de licencia se evalúa con criterios de la fundación, no del mantenedor único.

D4. **Emergencia de un patrón de captura específico** en el campo del estudio de fenómenos anómalos que se beneficie diferencialmente de AGPL.

Sin alguno de esos disparadores, la licencia se mantiene. La reconsideración por preferencia subjetiva sin disparador objetivo no abre ADR.

## Sobre licencias source-available no-OSS

ADR-0022 rechazó BSL, SSPL y similares. Este ADR-0028 lo reafirma sin matiz:

- El proyecto **no migrará** a licencias source-available no-OSS bajo ninguna circunstancia.
- Si las propiedades irrenunciables de P5 (licencia permisiva) exigen revisión sustantiva, esa revisión es ADR de supersesión al ADR-0000, no migración silenciosa.

## Consecuencias

**Positivas**
- La decisión se reafirma con razonamiento expuesto al juicio del lector.
- La separación código/corpus aborda la crítica donde tiene fuerza operativa real.
- Los disparadores hacen reversible la decisión si el contexto cambia.

**Negativas**
- El riesgo identificado por el Red Team Review se acepta como riesgo no eliminado.
- Algunos lectores discreparán con el balance Apache + CC BY-SA frente a AGPL pura. Aceptado.

**Neutras**
- Los procesos del proyecto (PRs, atribución, contribuciones) no cambian.

## Declaración de limitaciones

Este ADR **no afirma**:

- Que Apache 2.0 sea óptima en todos los contextos.
- Que la captura comercial sin reciprocidad sea imposible bajo el régimen elegido.
- Que CC BY-SA 4.0 sobre el corpus prevenga toda forma de monetización sin atribución.

Afirma que el balance, en este proyecto con este alcance y esta audiencia, prefiere Apache + CC BY-SA frente a las alternativas, **con disparadores explícitos** para revisar si el contexto cambia.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único:

- La activación de los disparadores D1–D4 depende de la observación del mantenedor. Captura comercial sutil puede no detectarse hasta tarde.
- El re-licenciamiento por ADR posterior requiere capacidad operativa del mantenedor en ejercicio.

Mitigación:

- Cualquier observador externo puede levantar la cuestión por issue público citando este ADR.
- El protocolo de sucesión (ADR-0026) prohíbe re-licenciamiento por sucesor sin revisión externa.

## Alineación con ADR-0000

**Propiedades afectadas:** P5 (licencia permisiva).

**Cómo se alinea:** este ADR **reafirma** P5 con razonamiento explícito que responde a la crítica del Red Team Review. La separación código/corpus es enriquecimiento operacional, no debilitación.

**Tensión:** la tensión entre permisividad y reciprocidad es **reconocida y aceptada conscientemente**. No es bug.

## Referencias

- `docs/reviews/adr_red_team_review.md`, sección §12 (Verdict 5).
- ADR-0022 (Apache License 2.0): este ADR-0028 lo reafirma con disparadores.
- Creative Commons Attribution-ShareAlike 4.0. https://creativecommons.org/licenses/by-sa/4.0/
- Meeker, H. (2017). *Open (Source) for Business.*
- OpenStreetMap Foundation ODbL transition (prior art en separación código/corpus).

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
