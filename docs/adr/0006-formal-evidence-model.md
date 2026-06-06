# ADR-0006: Modelo de evidencia formal

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0002, ADR-0005, ADR-0007, ADR-0009, ADR-0016

---

## Contexto

Evidence es la entidad raíz del sistema (ADR-0002). Su modelo formal debe satisfacer simultáneamente seis exigencias:

1. Direccionable por hash del contenido (P11).
2. Inmutable una vez ingestada (P11).
3. Trazable hasta su fuente y procedencia (ADR-0005).
4. Caracterizable en su tipo intrínseco (texto, imagen, audio, sensor, etc.).
5. Evaluable en credibilidad y autenticidad sin colapsar esa evaluación con la categoría epistémica.
6. Citable de forma estable durante décadas.

Los modelos tradicionales colapsan algunas de estas dimensiones. El campo OVNI/UAP ha producido bases donde "evidencia" significa todo a la vez: el artefacto, la afirmación del testigo sobre él, y la conclusión del investigador. ADR-0001 ya separa esas tres en categorías distintas; este ADR define formalmente la primera de ellas.

## Decisión

`Evidence` es un tipo inmutable, identificado por hash de contenido, con metadatos estructurados que cubren:

- **Identidad** (hash).
- **Contenido** (puntero al artefacto crudo en el storage local).
- **Tipo intrínseco** (`EvidenceKind`).
- **Procedencia** (referencia a `Source` y opcionalmente `Provenance`, ADR-0005).
- **Estatus** (`EvidenceStatus` — ortogonal a la categoría epistémica).
- **Autenticación** (`AuthenticationAssessment`, estructurada).
- **Integridad temporal** (cuándo fue ingestada, por quién, en qué versión del esquema).

Una `Evidence` ingestada no se modifica nunca. Las correcciones se modelan como **nuevas** evidencias derivadas con `Provenance` que apunta a la anterior y al motivo del derivado.

## Modelo

```
Evidence {
  hash: ContentHash                # SHA-256 del contenido crudo, en hex minúsculas
  kind: EvidenceKind               # ver enumeración
  content_uri: LocalURI            # puntero al blob en storage local
  size_bytes: int
  mime_type: str

  source_id: SourceId              # ADR-0005, referencia fuente primaria
  provenance: Provenance?          # ADR-0005, cadena explícita opcional

  status: EvidenceStatus           # ver enumeración
  authentication: AuthenticationAssessment
  intrinsic_metadata: dict         # metadatos del propio formato (EXIF, ID3, etc.)
  temporal_anchor: TemporalAnchor? # cuándo se afirma que se originó (ADR-0012)
  spatial_anchor: SpatialAnchor?   # dónde se afirma que se originó (ADR-0013)

  ingested_at: timestamp           # cuándo entró al sistema
  ingested_by: ActorId             # quién lo ingestó
  schema_version: SemVer           # versión del esquema usado al ingestar
  notes: markdown?
}
```

### EvidenceKind

Enumeración cerrada, extensible solo por ADR de enmienda. Refleja tipos intrínsecos, no categorías epistémicas.

| Kind | Ejemplo |
|------|---------|
| `document_text` | Documento textual (PDF nativo, TXT, transcripción) |
| `document_scan` | Escaneo de documento físico (PDF imagen, TIFF) |
| `still_image` | Foto, ilustración, sello |
| `moving_image` | Vídeo, película |
| `audio_recording` | Audio (transmisión, entrevista, ambiente) |
| `sensor_log` | Log de instrumento (radar, sismógrafo, sonar, IR) |
| `dataset_table` | Tabla estructurada (CSV, registros tabulares) |
| `spatial_data` | Capa geoespacial (GPX, KML, shapefile, GeoTIFF) |
| `code_or_model` | Código o modelo numérico ejecutable (notebook, script) |
| `correspondence` | Carta, email, fax, mensaje archivado |
| `interview_transcript` | Transcripción de entrevista con testigo |
| `physical_specimen_report` | Reporte sobre un objeto material (no el objeto en sí) |
| `composite` | Conjunto compuesto pre-existente que no se descompone (raro, evitar) |

`composite` es deliberadamente desincentivado. Lo normal es que un compuesto se descomponga en evidencias atómicas con sus propios hashes.

### EvidenceStatus

Estado de salud de la evidencia. **Ortogonal** a su credibilidad y a su categoría epistémica.

| Status | Significado |
|--------|------------|
| `active` | Operativa. La evidencia es accesible y su procedencia se considera válida. |
| `superseded` | Hay una evidencia derivada más completa o corregida. Sigue accesible y citable. |
| `disputed` | Su procedencia o autenticidad están en disputa documentada. No se retira. |
| `retracted` | Retirada del uso operativo por motivos documentados (fraude probado, derecho a olvido legal, daño concreto a personas). Su hash y motivo permanecen accesibles en el sistema como hueco explícito. |
| `quarantined` | En revisión activa por sospecha grave. Visible pero etiquetada. |

Una evidencia `retracted` **no se borra del storage del archivo histórico** salvo orden legal explícita. Lo que se hace es marcarla como retirada con razón documentada, y propagar la marca a vistas dependientes.

### AuthenticationAssessment

Estructura explícita que evalúa autenticidad **sin colapsarla con confianza global**.

```
AuthenticationAssessment {
  status: AuthStatus               # ver enumeración
  assessor: ActorId                # quién evaluó
  assessed_at: timestamp
  method: AuthMethod               # qué método se aplicó
  evidence_for: [EvidenceRef]      # evidencias que sostienen el assessment
  evidence_against: [EvidenceRef]  # evidencias que lo contradicen
  open_questions: [str]            # preguntas no resueltas
  notes: markdown?
}
```

**`AuthStatus`** (jerárquico):

| Status | Significado |
|--------|------------|
| `authentic` | Confirmado autentico por método riguroso documentado. |
| `provisionally_authentic` | Sin razones para dudar; sin verificación exhaustiva. |
| `unverified` | No se ha realizado evaluación. Default al ingestar. |
| `inconclusive` | Evaluado, no se puede concluir en ninguna dirección. |
| `provisionally_inauthentic` | Hay indicios serios de manipulación o falsificación. |
| `inauthentic` | Confirmado no auténtico por método riguroso documentado. |

**`AuthMethod`** soporta una taxonomía de métodos: análisis forense de imagen, análisis de metadatos EXIF/PNG, comparación con originales archivados, peritaje caligráfico, análisis acústico, prueba carbono-14, etc. Cada método registra parámetros y resultado bruto.

### Inmutabilidad y derivación

Una evidencia **nunca se modifica**. Si se descubre un error de metadatos:
- Se ingesta una nueva evidencia derivada (`Provenance.steps` incluye paso `metadata_correction`).
- La anterior pasa a `status: superseded`.
- Las vistas dependientes (casos, hipótesis) referencian las versiones que vieron.

Si se descubre fraude:
- La evidencia pasa a `status: retracted` con `AuthStatus: inauthentic`.
- Su contenido sigue accesible para auditoría.
- Las hipótesis y conclusiones que dependían de ella se marcan automáticamente como "afectadas por retracción de E-XXX".

### Anclajes temporal y espacial

`temporal_anchor` y `spatial_anchor` son referencias opcionales a las estructuras de los motores temporal (ADR-0012) y geoespacial (ADR-0013). Si la evidencia no se puede ubicar con confianza en tiempo o espacio, el campo queda `None`; nunca se inventa.

### Identidad por hash

El `ContentHash` es SHA-256 sobre el contenido crudo del artefacto. Dos sistemas distintos que ingestan el mismo PDF llegan al mismo hash sin coordinación. La deduplicación es estructural.

Notar: el hash es sobre el contenido crudo bit a bit. Cambios de formato (e.g., resave de PDF que altera bytes sin alterar contenido visible) producen un hash distinto. Eso es **deseable**: tratar como distintas dos cosas distintas. Si dos representaciones se quieren tratar como "equivalentes para algún propósito", se hace mediante una **relación explícita** (`semantic_equivalence`) en el grafo de conocimiento, no fusionando hashes.

## Justificación

### Por qué la autenticidad es estructura, no campo

La autenticidad es una evaluación con autor, método, evidencia favorable y contradictoria. Tratarla como un campo `is_authentic: bool` colapsa lo que es —correctamente— una conclusión en miniatura. La estructura `AuthenticationAssessment` es coherente con el resto del sistema: una conclusión sobre evidencia, formada con evidencia.

### Por qué inmutabilidad pura

Si la evidencia muta, la reproducibilidad histórica muere. El precio es duplicación de metadatos al corregir (la versión vieja y la nueva conviven). El precio se asume.

### Por qué retracción sin borrado por defecto

Borrar reescribe historia. Para responder a daño concreto se permite, pero como excepción documentada con motivación legal explícita. La política por defecto es marcar, no borrar.

### Por qué un hash, no varios

Tener un único identificador estable (SHA-256) simplifica todo el resto del sistema. Algoritmos adicionales (SHA-3, BLAKE3) se pueden añadir como **campos suplementarios** para resistencia a futuras roturas criptográficas, pero el identificador canónico es uno solo en el modelo.

## Consecuencias

**Positivas**
- Inmutabilidad bit a bit garantiza reproducibilidad (P5).
- Autenticación como estructura permite evaluaciones competitivas (dos peritos pueden registrar evaluaciones independientes sin conflicto).
- Deduplicación natural en ingestiones de archivos públicos.
- Retracción limpia sin sobreescritura histórica.

**Negativas**
- Tamaño de metadatos no trivial para evidencias pequeñas (un documento de 1 KB con su metadata completa puede pesar varias veces más en JSON).
- La inmutabilidad complica casos legítimos de corrección: hay que generar derivados, no editar.
- Riesgo de mal uso del campo `composite` por colaboradores impacientes.

**Neutras**
- El sistema produce un volumen de evidencia retirada visible pero no operativa. La interfaz debe ocultarla por defecto en navegación, mostrarla en auditoría.

## Alternativas consideradas

### A. Evidencia mutable con historial de cambios
**Descripción:** Cada `Evidence` mantiene su historial de versiones internas.
**Razón de rechazo:** El modelo content-addressed pierde sentido. Dos sistemas no convergerían naturalmente. Y el "historial interno" se erosiona en práctica.

### B. Autenticación como score escalar
**Descripción:** Un `authenticity_score: float [0,1]`.
**Razón de rechazo:** Colapsa lo que debe ser estructura. Esconde el porqué del score. Inauditable.

### C. Evidencia con borrado físico al retractar
**Descripción:** Retractar borra el contenido del storage.
**Razón de rechazo:** Reescribe historia. Falsifica la evaluación de hipótesis que dependían de esa evidencia en momentos anteriores. Solo se permite por orden legal explícita.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P10, P11.

**Cómo se alinean:**
- P11 (inmutabilidad de evidencia cruda): operacionalización primaria.
- P2 (trazabilidad) y P5 (reproducibilidad): el hash + procedencia + esquema versionado es el cimiento.
- P3 (incertidumbre): `AuthenticationAssessment` estructura la incertidumbre sobre autenticidad sin colapsarla.
- P10 (no fabricación): metadatos intrínsecos se ingestan tal cual; análisis derivados son derivados explícitos.

**Tensión:** Tamaño de metadatos vs. ergonomía. Aceptada: el coste es lineal con el volumen y compensable con storage barato.

## Referencias

- ADR-0005 (fuente y procedencia).
- BagIt File Packaging Format (RFC 8493). Prior art en empaquetado verificable.
- IPFS / CIDv1. Prior art en content-addressing.
- Schum, D. A. (1994). *The Evidential Foundations of Probabilistic Reasoning.* (Esquema evidence-for / evidence-against.)

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
