# ADR-0012: Motor temporal

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0006, ADR-0007, ADR-0010, ADR-0013

---

## Contexto

El sistema cubre reportes desde la antigüedad hasta el presente. Tiempo es un eje primario: cuándo ocurrió el evento afirmado, cuándo se hizo el reporte, cuándo se ingresó la evidencia al sistema. Cualquier reconstrucción de casos multi-fuente, cualquier análisis de patrones cross-case, cualquier auditoría de razonamiento descansa sobre representación rigurosa del tiempo.

Tiempo en este dominio es **inherentemente impreciso e incierto**:

- "Una noche de marzo de 1965, aproximadamente entre las 23h y la medianoche".
- "Durante la segunda dinastía de la Casa Han" → rango de siglos.
- "Mientras patrullábamos al sur del cabo, después de cenar" → orden parcial, no instante.
- "La transmisión está timestamped 1986-11-12T03:14:07Z según el log del controlador".

El motor temporal debe representar **todo** este espectro con precisión declarada, sin reducir a fechas falsamente precisas y sin colapsar incertidumbre.

## Decisión

El sistema modela tiempo con tres primitivos compatibles que cubren el espectro de precisión disponible:

1. **`TemporalInstant`** — un instante puntual con incertidumbre declarada.
2. **`TemporalInterval`** — un intervalo con bordes que pueden ser instantes o intervalos.
3. **`TemporalOrdering`** — orden parcial entre eventos cuando ninguno admite anclaje absoluto.

Todos los anclajes temporales del sistema (`TemporalAnchor`) son uno de estos tres tipos, nunca un campo `datetime` desnudo. El motor temporal opera sobre estas representaciones nativamente: consultas de superposición, ordenación, propagación de incertidumbre.

Toda visualización temporal del sistema **representa incertidumbre explícitamente** (no líneas finas mentirosas). Esta restricción es operativa, no estética.

## Modelo

### TemporalInstant

```
TemporalInstant {
  id: TemporalAnchorId
  representation: TemporalRepresentation     # ver más abajo
  uncertainty: TemporalUncertainty           # ver más abajo
  calendar: CalendarSystem                   # gregorian | julian | hijri | jewish | ... | mayan_long_count
  timezone: tz?                              # IANA tz si aplica; null si tiempo civil sin tz documentada
  attributed_to: ActorId                     # quién declaró este anclaje
  derived_from: [EvidenceRef | ClaimRef]     # de qué se deriva
  notes: markdown?
}
```

### TemporalRepresentation

Una `TemporalRepresentation` admite varios formatos compatibles con la precisión disponible:

| Formato | Ejemplo | Caso de uso |
|---------|---------|-------------|
| `iso8601_full` | `1986-11-12T03:14:07Z` | Tiempo con segundo (radar, log) |
| `iso8601_partial` | `1986-11`, `1986-11-12` | Precisión a mes o día |
| `year_only` | `1947` | Solo año |
| `decade` | `1950s` | Solo década |
| `century` | `12th century` | Solo siglo |
| `dynasty_or_period` | `late_han_dynasty` | Períodos históricos no datables a año |
| `relative_to_event` | `42_days_after(<event_ref>)` | Anclaje relativo a otro evento |
| `expressed_as` | "una noche de marzo de 1965" (literal) | Cuando no se debe normalizar |

`expressed_as` siempre se preserva junto al formato normalizado. La normalización es derivada, no destructiva.

### TemporalUncertainty

```
TemporalUncertainty {
  kind: UncertaintyKind                # ver enumeración
  lower_bound: TemporalInstant?        # límite inferior si aplica
  upper_bound: TemporalInstant?        # límite superior si aplica
  best_estimate: TemporalInstant?      # estimación puntual si aplica
  distribution: TemporalDistribution?  # opcional, para casos avanzados
  rationale: markdown                  # por qué la incertidumbre es la que es
}
```

**UncertaintyKind**:

| Kind | Significado |
|------|-------------|
| `exact` | Sin incertidumbre material. Raro fuera de logs de instrumento. |
| `bounded` | Bordes superiores e inferiores conocidos. Distribución desconocida o no relevante. |
| `gaussian_like` | Estimación central con margen 1σ. |
| `uniform` | Igualmente probable en todo el intervalo. |
| `qualitative_fuzzy` | "Una noche", "entre la primavera y el verano". |
| `unknown` | Hay declaración del tiempo pero no hay base para acotar la incertidumbre. |

### TemporalInterval

```
TemporalInterval {
  id: TemporalAnchorId
  start: TemporalInstant | "unknown_open"
  end: TemporalInstant | "unknown_open"
  is_open_start: bool
  is_open_end: bool
  bounds_are_inclusive: (bool, bool)
  calendar: CalendarSystem
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

`unknown_open` significa que el borde está vivo a un lado: por ejemplo, "el fenómeno ya había comenzado cuando llegamos". El sistema rechaza fingir un borde inventado.

### TemporalOrdering

```
TemporalOrdering {
  id: TemporalAnchorId
  before: [EventRef]          # eventos que ocurren antes
  after: [EventRef]           # eventos que ocurren después
  during: [EventRef]?         # eventos que solapan
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

Esto permite afirmar "el avistamiento ocurrió después de que el avión X aterrizara y antes del cambio de turno del controlador" sin comprometerse con un instante absoluto.

### Calendarios

El sistema soporta múltiples sistemas de calendario y convierte entre ellos cuando se pide explícitamente, **preservando siempre el sistema original**. Una fecha "del calendario chino tradicional" no se almacena solo como su conversión gregoriana; ambas versiones coexisten. La conversión se documenta con el algoritmo y la fuente de las tablas (e.g., reglas de Meeus para conversiones astronómicas).

Calendarios soportados en la primera implementación:

- Gregoriano (default actual).
- Juliano (para reportes anteriores a 1582 y eclesiásticos posteriores).
- Hijri.
- Hebreo.
- Cuenta larga maya.
- Chino tradicional.
- "Períodos históricos" (dinastías, eras) como representación cualitativa sin conversión automática.

Cualquier calendario adicional requiere ADR de enmienda.

### Husos horarios

Para reportes modernos con huso conocido, IANA tz se almacena junto al instante. Para reportes históricos sin tz documentada, el sistema rechaza inventar UTC: almacena la representación literal con `timezone=null` y marca la incertidumbre.

### Resolución para consultas

Operaciones del motor:

- **Solapamiento**: dos anclajes solapan si sus intervalos de incertidumbre se intersectan. La operación devuelve `definitely | possibly | definitely_not`.
- **Orden**: análoga, con valores `definitely_before | possibly_before | possibly_after | definitely_after | overlapping`.
- **Composición**: dos intervalos con `unknown_open` se componen preservando la apertura.

Estas operaciones nunca devuelven booleanos puros; devuelven valores trivaluados que preservan incertidumbre.

### Visualización

Toda visualización temporal del sistema **debe representar la incertidumbre**. Esto incluye:

- Marcas de instante no son puntos sino barras de incertidumbre.
- Intervalos con bordes abiertos se dibujan con extremos visualmente abiertos.
- Calendarios alternativos se exponen como facetas seleccionables.

La especificación de visualización se materializa en una guía de estilo (`docs/visualization-guidelines.md`) cuando llegue Fase 4.

## Justificación

### Por qué tres primitivos y no uno

Forzar todo a `TemporalInterval` (un solo primitivo) sería más simple pero perdería la distinción operativa entre orden parcial sin anclaje absoluto y intervalo con bordes. La orden parcial es el caso real frecuente en reportes históricos.

### Por qué preservar `expressed_as`

La normalización es lossy. Una frase "una noche de marzo de 1965" lleva información que `1965-03-XX` no captura (alusión a una noche concreta que el contexto identifica). Preservar el literal protege contra paráfrasis que cambian el sentido.

### Por qué calendarios múltiples desde el principio

El proyecto aspira a cubrir milenios. Aplazar el soporte multi-calendario sería diseñar para Occidente moderno y reparar después. Reparar después es más caro que diseñar bien al principio.

### Por qué `unknown_open`

Es el caso real: muchos reportes describen fenómenos cuyo inicio o fin no observa el testigo. Imputar bordes inventados es deshonestidad estructural.

### Por qué operaciones trivaluadas

Las operaciones bivaluadas sobre tiempo incierto producen confianzas falsas. Trivaluado preserva honestidad epistémica en el plano operativo.

## Consecuencias

**Positivas**
- Reportes antiguos y modernos conviven en el mismo modelo sin distorsión.
- Reconstrucción temporal multi-fuente no colapsa incertidumbre.
- Consultas de solapamiento y orden devuelven honestidad, no booleanos cómodos.
- Calendarios alternativos son ciudadanos del modelo.

**Negativas**
- Modelo más complejo que un `datetime`.
- Visualizaciones más densas. Imposible un timeline limpio de "líneas finas".
- Indexación temporal más compleja: requiere ranged indexes sobre intervalos.

**Neutras**
- Las queries temporales típicas son alcanzables con SQL extendido sobre DuckDB.

## Alternativas consideradas

### A. Solo ISO 8601 desnudo
**Descripción:** Cualquier evento se reduce a UTC ISO con precisión arbitraria.
**Razón de rechazo:** Pierde calendarios y orden parcial. Imputa precisión inexistente.

### B. Modelo OWL-Time
**Descripción:** Adoptar la ontología OWL-Time del W3C.
**Razón de rechazo:** Buen prior art para inspiración. Adopción literal es excesiva.

### C. Calendarios solo gregoriano + nota libre
**Descripción:** Almacenar todo en gregoriano y libertad textual para casos exóticos.
**Razón de rechazo:** Pierde estructura. Hace imposible consultas a través de calendarios.

### D. Eventos como triples instante + duración + tz
**Descripción:** Compromiso simplificado.
**Razón de rechazo:** No captura orden parcial sin anclaje.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P9, P10.

**Cómo se alinean:**
- P3 (incertidumbre): el motor representa incertidumbre temporal nativamente.
- P10 (no fabricación): rechazo de inventar bordes o tz.
- P9 (fuentes públicas): tablas de conversión de calendarios son open data.

**Tensión:** Complejidad del modelo vs. simplicidad de ingesta. Aceptada: tooling de ingesta puede ofrecer atajos para casos modernos (`ingest_now()`) sin sacrificar el modelo subyacente.

## Referencias

- W3C OWL-Time Ontology. https://www.w3.org/TR/owl-time/
- Meeus, J. (1998). *Astronomical Algorithms.*
- Reingold, E. M., & Dershowitz, N. (2018). *Calendrical Calculations.*
- Allen, J. F. (1983). *Maintaining knowledge about temporal intervals.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
