# ADR-0022: Licencia Apache 2.0

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000

---

## Contexto

La licencia es decisión fundacional. Determina:

- Quién puede usar el código y con qué condiciones.
- Si los derivados deben ser abiertos.
- Si hay cláusula de patentes.
- Compatibilidad con otros proyectos open source.
- Aceptabilidad para integración en software comercial, académico y de organizaciones no abiertas.
- Modelo de captura potencial del proyecto.

P5 del ADR-0000 lo prefigura: "La licencia es Apache-2.0. Permite uso comercial, derivado, y sublicensing sin filtros. Esto es deliberado: queremos que se construya sobre el proyecto, no impedirlo." Este ADR fija formalmente la decisión y explicita su justificación.

## Decisión

El proyecto se distribuye bajo **Apache License 2.0** (Apache-2.0), sin excepciones ni cláusulas adicionales (no AGPL, no SSPL, no BSL, no licencias custom).

El archivo `LICENSE` en la raíz del repositorio contiene el texto íntegro de Apache-2.0.

Todas las contribuciones aceptadas se distribuyen bajo la misma licencia. Los contribuidores otorgan licencia sobre sus contribuciones bajo los términos de Apache-2.0 al someter un PR. No se requiere CLA adicional en V1; si fuera necesario en algún momento (por demanda de integradores corporativos), un ADR específico lo introduciría.

## Justificación

### Por qué open source

P5, P6, P7, P8 del ADR-0000 conjuntamente impiden cualquier modelo cerrado. Local-first, coste cero, fuentes públicas, documentación al mismo nivel del código exigen que el código esté disponible para inspección, modificación y redistribución.

### Por qué permisiva (Apache) y no copyleft (GPL/AGPL)

Argumentos para copyleft:

- Garantiza que derivados permanezcan abiertos.
- Protege el ecosistema de cierres.

Argumentos para permisiva:

- Maximiza adopción (organizaciones que no pueden adoptar copyleft sí adoptan Apache).
- Reduce fricción legal para casos académicos, periodísticos, institucionales.
- Permite construir productos sobre AIP sin obligación de abrir el producto. El proyecto **prefiere que se construya sobre él**.
- Las organizaciones serias que adoptan AIP probablemente publican sus mejoras por interés propio, no por obligación legal.

El proyecto opta por permisiva porque su valor es la **infraestructura compartida**, no el control sobre derivados. Si una farmacéutica, una agencia estatal o un periódico construyen un producto sobre AIP y no abren su código, el ecosistema sigue ganando: AIP sigue siendo el sustrato común.

### Por qué Apache 2.0 y no MIT/BSD

Diferencia clave: **cláusula de patentes explícita**.

- Apache 2.0 contiene un grant de patentes que protege a usuarios contra demandas de patentes por parte de contribuidores.
- MIT y BSD-3 no la contienen explícitamente; el grant es implícito en algunas jurisdicciones, ausente en otras.

Para un proyecto que aspira a infraestructura compartida a largo plazo, la cláusula de patentes es protección importante contra escenarios de captura por patente troll o por contribuidor que después litigia.

### Por qué no AGPL

AGPL extiende copyleft al uso como servicio: si AIP se ofreciera como SaaS, AGPL obligaría a abrir el código del SaaS. Esto suena alineado con los valores del proyecto, pero produce dos problemas:

1. Excluye adopción institucional importante. Agencias de archivo, universidades y bibliotecas frecuentemente tienen políticas que rechazan AGPL.
2. AGPL no es estable contra ataques de captura: variantes "AGPL+excepción comercial" se han usado para canalizar el proyecto a una sola entidad comercial.

Apache 2.0 evita ambos problemas a cambio de menos protección contra cerramiento. El trade-off se considera correcto.

### Por qué no licencias custom (BSL, SSPL, etc.)

BSL (Business Source License) y SSPL (Server Side Public License) son licencias source-available con restricciones que **no son open source según la definición OSI**. Adoptarlas:

- Excluiría AIP del ecosistema open source.
- Daría señales contradictorias a contribuidores.
- Sería contrario a la misión del proyecto.

### Por qué sin CLA

CLAs (Contributor License Agreements) añaden fricción a contribuir. En proyectos pequeños sin necesidad de relicenciamiento futuro, son sobrecargas. La licencia Apache 2.0 ya implica concesión de licencia sobre la contribución, sin necesidad de CLA separado.

Si en algún momento se necesita CLA (por ejemplo, una fundación lo exige), se introduce con ADR específico que cuantifique el beneficio.

### Atribución y NOTICE

Apache 2.0 exige preservar atribuciones en redistribuciones. AIP mantiene un fichero `NOTICE` cuando incluye código de terceros bajo Apache 2.0 que lo requiere. Para el código propio del proyecto, la atribución vive en cabeceras de fichero o en metadata del paquete.

## Consecuencias

**Positivas**
- Adoptable por cualquier organización, incluyendo aquellas con políticas restrictivas sobre copyleft.
- Cláusula de patentes protege contra captura por patente troll.
- Sin CLA, contribuciones tienen mínima fricción.
- Compatible con prácticamente cualquier otra licencia open source.
- Distribuido con claridad: el texto de la licencia es estándar y universalmente entendido.

**Negativas**
- Derivados pueden ser cerrados; el proyecto pierde la capacidad de exigir reciprocidad.
- Un fork comercial con valor agregado puede competir sin contribuir de vuelta.
- En sectores específicos (juegos, software de defensa), Apache puede ser percibido como "demasiado abierto" para integración. Mitigable; depende del integrador.

**Neutras**
- La licencia no resuelve gobernanza. Cuestiones de captura por dirección del proyecto se abordan en `MAINTAINERS.md` y en el modelo de sostenibilidad del ADR-0000.

## Alternativas consideradas

### A. AGPL-3.0
**Descripción:** Copyleft fuerte con cláusula SaaS.
**Razón de rechazo:** Exclusión institucional probable. Inestable contra captura por excepción comercial.

### B. GPL-3.0
**Descripción:** Copyleft sin cláusula SaaS.
**Razón de rechazo:** Misma exclusión institucional; sin la ventaja SaaS.

### C. MIT
**Descripción:** Permisiva minimal.
**Razón de rechazo:** Falta cláusula de patentes explícita.

### D. BSD-3-Clause
**Descripción:** Permisiva clásica.
**Razón de rechazo:** Misma razón que MIT.

### E. Apache 2.0 + Commons Clause
**Descripción:** Restricción de uso comercial añadida.
**Razón de rechazo:** No es OSS según OSI. Compromete misión.

### F. BSL (Business Source License)
**Descripción:** Restricción comercial temporal.
**Razón de rechazo:** No es OSS. Excluye del ecosistema.

### G. CC BY-SA (para datos) + Apache (para código)
**Descripción:** Mixta para tratar datos y código diferente.
**Razón de rechazo:** El código es el núcleo de este ADR. Los datasets de ejemplo que el proyecto ingesta llevan la licencia de su fuente original; los datasets generados por el proyecto pueden adoptar CC BY 4.0 documentado caso por caso. Eso no requiere cambiar la licencia del código.

## Alineación con ADR-0000

**Propiedades afectadas:** P5, P6, P7, P8, P9.

**Cómo se alinean:**
- P5 (licencia permisiva): operacionalización directa.
- P6 (local-first), P7 (coste cero): la licencia permite distribución y modificación libres.
- P8 (documentación): la licencia es documento; su elección está documentada aquí.
- P9 (fuentes públicas): el código del proyecto es fuente pública adicional para el ecosistema.

**Tensión:** Riesgo de cerramiento de derivados vs. adopción amplia. Aceptada conscientemente.

## Referencias

- Apache License, Version 2.0. https://www.apache.org/licenses/LICENSE-2.0
- Open Source Initiative (OSI) Definition.
- Free Software Foundation. Comparación de licencias.
- Heather Meeker. *Open (Source) for Business.* (Capítulo sobre familias de licencias.)
- StephenWalli, S. (2021). Análisis de SSPL/BSL desde perspectiva de comunidad.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
