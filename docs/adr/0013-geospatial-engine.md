# ADR-0013: Motor geoespacial

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0006, ADR-0007, ADR-0010, ADR-0011, ADR-0012

---

## Contexto

Igual que el tiempo, el espacio es eje primario del sistema. Cada caso tiene ubicaciones afirmadas: dónde estaba el testigo, dónde se observó el fenómeno, qué trayectoria se le atribuye, qué región geográfica abarcaba.

Y, otra vez, el espacio es **inherentemente impreciso**:

- "Sobre el río, hacia el oeste" → vector cualitativo sin coordenadas.
- "A unos 200 metros del puente" → distancia con incertidumbre.
- "Cerca de Roswell, NM" → región con borde difuso.
- "Latitud 34.0522°, Longitud -118.2437° (GPS del dispositivo)" → punto con error declarado por el dispositivo.
- "En algún punto de la costa atlántica de Brasil" → región amplia.
- Trayectorias declaradas por testigos: ángulos sin distancia, sin posibilidad de triangulación.

El motor geoespacial debe representar este espectro sin colapsar a puntos falsamente precisos. Debe soportar consultas de proximidad, solapamiento de regiones, y proyección con incertidumbre, sin pretender precisión donde no la hay.

## Decisión

El sistema modela espacio con cuatro primitivos compatibles:

1. **`SpatialPoint`** — coordenada puntual con error declarado.
2. **`SpatialRegion`** — región (polígono, círculo, geometría compleja) con borde explícito y categoría de incertidumbre.
3. **`SpatialDirection`** — vector cualitativo desde un origen ("hacia el norte desde el puente"), opcionalmente con elevación, sin compromiso de distancia.
4. **`SpatialReference`** — referencia a un topónimo o región geográfica nombrada, con resolución a geometría diferida y revisable.

Todos los anclajes espaciales del sistema (`SpatialAnchor`) son uno de estos cuatro tipos, nunca lat/lon desnudos. El motor opera sobre estas representaciones nativamente, con visualización que **siempre representa incertidumbre**.

El sistema usa **WGS84** como sistema de referencia canónico interno. Cuando un sistema de coordenadas distinto (UTM local, sistemas históricos, etc.) es la representación original, se preserva junto a la conversión.

## Modelo

### SpatialPoint

```
SpatialPoint {
  id: SpatialAnchorId
  lat: float                       # WGS84 grados decimales
  lon: float                       # WGS84 grados decimales
  altitude_m: float?               # MSL u otra referencia declarada
  altitude_reference: AltitudeRef  # msl | wgs84_ellipsoid | local_ground | unknown
  horizontal_error_m: float?       # 1σ aprox., declarado por la fuente o estimado por el ingestor
  vertical_error_m: float?
  source_crs: CRS?                 # CRS original si distinto de WGS84
  source_representation: str       # cadena literal original
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

### SpatialRegion

```
SpatialRegion {
  id: SpatialAnchorId
  geometry: Geometry               # GeoJSON-like: Polygon | MultiPolygon | Circle | ConvexHull
  boundary_kind: BoundaryKind      # crisp | fuzzy | administrative | natural
  uncertainty_kind: RegionUncertaintyKind
  central_estimate: SpatialPoint?  # punto representativo si aplica
  source_crs: CRS?
  source_representation: str
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

**BoundaryKind**:

| Kind | Significado |
|------|-------------|
| `crisp` | Borde geométrico bien definido. |
| `fuzzy` | Borde difuso ("cerca de", "aproximadamente"). |
| `administrative` | Borde administrativo (frontera de país, estado, municipio) con autoridad declarada. |
| `natural` | Borde físico natural (río, cordillera). |

**RegionUncertaintyKind**: análogo a temporal — `bounded`, `gaussian_like`, `uniform`, `qualitative_fuzzy`, `unknown`.

### SpatialDirection

```
SpatialDirection {
  id: SpatialAnchorId
  origin: SpatialPoint | SpatialRegion        # desde dónde se observa
  azimuth_deg: float?                          # 0=N, 90=E, NaN si solo cualitativo
  azimuth_qualitative: str?                    # "norte", "al oeste del puente"
  elevation_deg: float?                        # ángulo sobre horizonte
  elevation_qualitative: str?
  uncertainty_azimuth_deg: float?
  uncertainty_elevation_deg: float?
  distance_constraint: DistanceConstraint?     # opcional: rango, sin compromiso
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

`SpatialDirection` representa el caso muy común de testigos que reportan ángulos sin distancia: el sistema no puede triangular sin más datos, y honra esa imposibilidad.

### SpatialReference

```
SpatialReference {
  id: SpatialAnchorId
  toponym: str                                 # nombre tal como aparece
  toponym_language: BCP47
  resolved_to: SpatialRegion | SpatialPoint?   # opcional, resolución concreta
  resolution_method: ResolutionMethod?         # geocoder | manual | gazetteer | ambiguous
  gazetteer_id: str?                           # ID en GeoNames, WikiData, etc.
  resolution_confidence: KentLevel             # ADR-0009
  alternative_resolutions: [SpatialAnchorId]   # candidatos rechazados o no decididos
  attributed_to: ActorId
  derived_from: [EvidenceRef | ClaimRef]
  notes: markdown?
}
```

`SpatialReference` permite ingestar "cerca de Lima" sin comprometerse con una geometría exacta hasta que se resuelva. Resoluciones automáticas por geocoder se marcan claramente como tales y son reversibles.

### Sistemas de referencia

- WGS84 (EPSG:4326) como canónico interno.
- Conversiones desde UTM, sistemas históricos, sistemas militares (MGRS) son tooling al borde de ingestión. La representación original se preserva en `source_crs` y `source_representation`.
- Los sistemas históricos que carecen de mapping moderno preciso (cartografía antigua, descripciones cualitativas) **no se convierten forzosamente**. Se almacenan como `source_representation` y se acompañan de `SpatialReference` o `SpatialRegion` aproximada con incertidumbre alta.

### Operaciones del motor

- **Distancia con incertidumbre**: entre dos `SpatialPoint`, devuelve distancia + propagación de errores. Entre puntos y regiones, devuelve rango.
- **Intersección**: `definitely_overlaps | possibly_overlaps | definitely_disjoint`.
- **Contención**: análoga.
- **Proximidad temporal-espacial**: combinada con motor temporal, "¿qué reportes ocurrieron a menos de 50 km y menos de 24 horas de este caso?".
- **Triangulación con incertidumbre**: dadas N direcciones desde N orígenes, calcular región probable.

Resultados son siempre con incertidumbre explícita, no booleanos.

### Visualización

Visualizaciones geoespaciales del sistema **representan incertidumbre**:

- Puntos con horizontal_error se dibujan como círculos de confianza, no como puntos finos.
- Regiones fuzzy se dibujan con gradientes de borde, no líneas duras.
- Direcciones sin distancia se dibujan como conos abiertos desde el origen.
- Trayectorias se dibujan como tubos de incertidumbre.

La guía de estilo se especifica en `docs/visualization-guidelines.md` al alcanzar Fase 4.

## Justificación

### Por qué cuatro primitivos

Cada uno cubre un caso real frecuente que los demás no cubren bien:
- `SpatialPoint`: medidas modernas.
- `SpatialRegion`: descripciones de área.
- `SpatialDirection`: testigo sin GPS.
- `SpatialReference`: topónimos no resueltos o ambiguos.

Forzar todo a uno de ellos pierde casos legítimos.

### Por qué WGS84 como canónico interno

Estándar de facto para datos abiertos, compatible con la mayoría de fuentes públicas, soportado por todas las librerías geoespaciales open source.

### Por qué resolución de topónimos diferida y reversible

Geocoders cometen errores frecuentes en topónimos antiguos, ambiguos o multilingües. Comprometerse con una resolución al ingestar es atar el caso a un error. Diferir, marcar la resolución como confianza Kent, y permitir reversión protege la integridad.

### Por qué incertidumbre obligatoria en visualización

P3 (incertidumbre como first-class) y P10 (no fabricación) lo exigen. Una línea fina como trayectoria es una mentira (eco directo del ADR-0008 de orbital-sentinel y del propio ADR-0000).

### Por qué no usar PostGIS

PostGIS es excelente pero requiere PostgreSQL. Eso choca con P6 (local-first) y P7 (coste cercano a cero) para usuario individual. El sistema usa GeoParquet + DuckDB-spatial, que cubre los patrones operativos con dependencia open source embebible.

## Consecuencias

**Positivas**
- Reportes históricos sin coordenadas tienen primitivos honestos.
- Reportes modernos con GPS tienen primitivos precisos.
- Resolución de topónimos es revisable.
- Consultas espacio-temporales combinadas son operativas.

**Negativas**
- Modelo más complejo que lat/lon planos.
- Visualizaciones más densas.
- Geocoders externos son recursos opcionales; la resolución manual a topónimos exóticos requiere esfuerzo.

**Neutras**
- Las consultas geoespaciales típicas son alcanzables con DuckDB-spatial.

## Alternativas consideradas

### A. PostGIS como motor obligatorio
**Descripción:** Adoptar PostGIS desde el inicio.
**Razón de rechazo:** Choca con local-first sin servicios externos para usuario individual.

### B. Solo lat/lon + texto libre
**Descripción:** Mínimo viable.
**Razón de rechazo:** Reproduce la pérdida de información del campo. Imposibilita búsqueda estructurada.

### C. Sistemas históricos forzados a WGS84
**Descripción:** Convertir todo, descartar representación original.
**Razón de rechazo:** Distorsión silenciosa de fuentes. Imposibilita auditoría de la conversión.

### D. Geocoder automático al ingestar
**Descripción:** Resolver topónimos siempre, automáticamente, al ingestar.
**Razón de rechazo:** Errores se amplifican. La política `SpatialReference` con resolución diferida es más honesta.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P6, P7, P9, P10.

**Cómo se alinean:**
- P3: incertidumbre espacial es ciudadana de primera clase.
- P6, P7: GeoParquet + DuckDB-spatial es local y libre.
- P9: fuentes geoespaciales primarias (OpenStreetMap, GeoNames, Natural Earth) son públicas.
- P10: rechazo a inventar precisión geocodificando agresivamente.

**Tensión:** Cobertura cartográfica histórica vs. disponibilidad de datos. Aceptada: el sistema honra la incertidumbre que el dato implica.

## Referencias

- OGC GeoJSON / OGC Simple Features.
- DuckDB-spatial extension.
- GeoParquet specification.
- GeoNames gazetteer.
- Natural Earth cartographic data.
- Cervantes, M. (2010). *Spatial Uncertainty in Ecology.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
