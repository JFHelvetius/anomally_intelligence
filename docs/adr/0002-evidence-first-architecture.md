# ADR-0002: Arquitectura evidence-first

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0005, ADR-0006, ADR-0011, ADR-0016

---

## Contexto

Los sistemas tradicionales de gestión de casos sobre fenómenos anómalos (bases de datos de NICAP, MUFON CMS, NUFORC reports, hojas de cálculo de archivos académicos) suelen organizarse alrededor del **caso** como entidad raíz. Un caso tiene campos: fecha, ubicación, descripción, testigo, fotos adjuntas, conclusión.

Ese diseño tiene un problema estructural: cuando la evidencia cambia (aparece una nueva foto, se desclasifica un radar, se reanaliza un audio), el caso muta, y la cadena de razonamiento previo se rompe sin trazabilidad. Las conclusiones, hipótesis e interpretaciones que dependían de la evidencia anterior quedan invalidadas implícitamente. El sistema no puede responder "¿en qué creíamos en 2019 y por qué?" porque la base ya no es la misma.

La alternativa es invertir la relación: el ciudadano de primera clase del sistema es la **evidencia**, no el caso. Los casos son agregados versionados sobre conjuntos de evidencia. Hipótesis, interpretaciones y conclusiones son funciones de evidencia, no propiedades del caso.

## Decisión

La entidad raíz del modelo de datos es la **evidencia** (`Evidence`), no el caso. El caso (`Case`) es un agregado versionado que **referencia** evidencia mediante punteros direccionados por hash, y que aloja la red de afirmaciones, interpretaciones, hipótesis y conclusiones que esa evidencia soporta.

Cuando la evidencia cambia (incorporación nueva, retracción, corrección de procedencia), el caso pasa a una nueva versión. Las versiones anteriores siguen existiendo, citables y reproducibles. Una conclusión publicada en el caso v3 se evalúa contra la evidencia disponible en v3, no contra la actual.

## Justificación

### Evidencia como invariante temporal

La evidencia cruda (una foto del 14 de marzo de 1965, un audio de un controlador aéreo, un documento desclasificado) tiene una propiedad rara y valiosa: no cambia. Lo que cambia es lo que hacemos con ella —cómo la interpretamos, qué metadatos le añadimos, qué hipótesis sostiene—. Anclar el sistema en la evidencia explota esa propiedad: el sustrato es estable, las capas de razonamiento son versionables sobre él.

### Trazabilidad de retracción

En el modelo case-first, retractar un caso por evidencia falsa requiere alterar el caso, lo que ensucia el historial. En el modelo evidence-first, retractar es un acto sobre la evidencia (marcarla como `retracted: true` con causa documentada) que se propaga automáticamente a todas las dependencias: cualquier hipótesis o conclusión que dependía de esa evidencia queda marcada como afectada, sin reescribir el grafo histórico.

### Casos como vistas

Un caso es, en este modelo, una vista materializada sobre un subconjunto de evidencia más la red de razonamiento sobre ella. Diferentes investigadores pueden mantener vistas distintas sobre la misma evidencia (un caso "AAWSAP report 2017" y un caso "Análisis civil 2024" pueden compartir el 90% de la evidencia y divergir en hipótesis). El modelo lo soporta nativamente.

### Composabilidad

La evidencia, como ciudadano raíz, puede participar en múltiples casos. Una desclasificación del 2024 puede afectar a doce casos históricos simultáneamente; el sistema lo refleja sin duplicación.

## Modelo conceptual

```
                          ┌──────────────────┐
                          │     Evidence     │  ← entidad raíz, inmutable
                          │  (content-hash)  │
                          └────────┬─────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
            ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
            │   Fact    │    │   Claim   │    │  Source   │
            └─────┬─────┘    └─────┬─────┘    └───────────┘
                  │                │
                  └────────┬───────┘
                           │
                  ┌────────▼──────────┐
                  │  Interpretation   │
                  └────────┬──────────┘
                           │
                  ┌────────▼──────────┐
                  │     Hypothesis    │  ← competidoras
                  └────────┬──────────┘
                           │
                  ┌────────▼──────────┐
                  │    Conclusion     │
                  └────────┬──────────┘
                           │
                  ┌────────▼──────────┐
                  │    Case (view)    │  ← agregado versionado
                  └───────────────────┘
```

Lo importante del diagrama:

- La evidencia es el suelo. Todo lo demás cuelga de ella.
- El caso no es el origen sino el destino: un agregado conceptual versionado.
- Hipótesis y conclusiones dependen de evidencia, no de caso. Pueden existir antes de que se cree un caso que las agrupe.

## Implicaciones de diseño

### Implicación 1: Identidad por hash de la evidencia
Cada artefacto crudo se identifica por hash de su contenido (ver ADR-0016). Eso permite que dos investigadores que ingestan el mismo PDF desclasificado del FOIA llegan, sin coordinación, al mismo identificador. La evidencia se deduplica naturalmente.

### Implicación 2: Casos versionados, evidencia inmutable
La evidencia raw no se versiona porque no muta. Lo que se versiona es el caso y sus capas de razonamiento. Un caso es una secuencia inmutable de snapshots; cada snapshot referencia un subconjunto de evidencia por hash.

### Implicación 3: Retracción propagada
Un campo `provenance.status` en la evidencia puede tomar valores `verified`, `unverified`, `disputed`, `retracted`, `fraudulent`. Cambios en ese campo se propagan a las vistas (casos) que dependen de esa evidencia, marcándolas como "afectadas" sin reescribirlas.

### Implicación 4: Agregados sin lock-in
Diferentes proyectos derivados pueden generar casos distintos sobre la misma base de evidencia. AIP no impone una única taxonomía de caso; provee la base sobre la que múltiples taxonomías cohabitan.

## Consecuencias

**Positivas**
- Trazabilidad bit a bit (P2): cualquier conclusión histórica es reproducible porque la evidencia subyacente es inmutable y direccionable por hash.
- Retracción limpia y propagada sin daño al historial.
- Composabilidad: una evidencia participa en múltiples casos sin duplicación.
- Naturalmente compatible con el modelo de hipótesis competidoras (P4): la misma evidencia puede sostener distintas hipótesis sin conflicto en el modelo.
- Permite snapshots citables del estado del archivo en cualquier momento histórico.

**Negativas**
- Más complejidad inicial. Un colaborador acostumbrado a "abrir un caso y rellenar campos" tiene que entender que el caso es una vista, no la raíz.
- Las herramientas de UI tienen que invertir su flujo mental: empiezan por evidencia, no por caso.
- Mayor coste de storage en metadatos relacionales (pero la evidencia cruda no se duplica, que es el coste dominante).

**Neutras**
- El paradigma es familiar para quienes han trabajado con sistemas content-addressable (Git, IPFS, Datomic).
- Cambia la forma de pensar pero no la cantidad de información necesaria.

## Alternativas consideradas

### A. Case-first tradicional
**Descripción:** Caso como raíz, evidencia como adjunto.
**Razón de rechazo:** Patología documentada del campo. La retracción ensucia historial. La duplicación de evidencia entre casos es endémica.

### B. Event-first
**Descripción:** El evento físico (lo que sea que ocurrió) como raíz.
**Razón de rechazo:** El evento es precisamente lo que el sistema **no asume**. Tomar el evento como raíz exige asumir que existió y que sabemos qué fue. Eso viola P4. La evidencia, en cambio, es indiscutible que existe (es un objeto material o digital ingestado).

### C. Witness-first
**Descripción:** El testigo como raíz, evidencias como output.
**Razón de rechazo:** Crea problemas de privacidad serios (P12) y deja sin hogar la evidencia que no procede de testigos (radar, satélite, foto sin autor identificado).

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P4, P5, P11.

**Cómo se alinean:**
- P2 (trazabilidad): la inmutabilidad de la evidencia es prerrequisito de cualquier reproducibilidad.
- P3 (incertidumbre): cuantificar incertidumbre exige saber sobre qué evidencia se calculó.
- P4 (neutralidad): la evidencia como raíz neutraliza el sesgo de "qué tipo de caso es esto" antes de que haya razonamiento.
- P11 (inmutabilidad de evidencia cruda): operacionalización directa.

**Tensión:** Coste cognitivo inicial vs. claridad operativa a largo plazo. Aceptable: la audiencia primaria del proyecto (P1 ADR-0000) tolera complejidad por rigor.

## Referencias

- Git (Linus Torvalds, 2005). Content-addressable storage como prior art.
- Datomic (Rich Hickey). Modelo de hechos inmutables como base de la base de datos.
- IPFS / content-addressable web. Direccionamiento por hash.
- W3C PROV-O. Ontología de procedencia.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
