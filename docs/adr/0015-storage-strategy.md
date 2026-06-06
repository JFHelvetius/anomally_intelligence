# ADR-0015: Estrategia de almacenamiento

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0003, ADR-0006, ADR-0011, ADR-0016

---

## Contexto

El sistema necesita almacenar:

- **Blobs crudos** — los artefactos de evidencia inmutables (PDFs, imágenes, audios, WARCs, etc.). Tamaños desde KB hasta varios GB.
- **Metadatos estructurados** — fuentes, procedencia, claims, hipótesis, conclusiones, casos, anclajes temporales/espaciales, aristas del grafo.
- **Índices secundarios** — de búsqueda full-text, vectorial opcional, geoespacial, temporal.

Restricciones del ADR-0000:

- P6 local-first: todo accesible offline.
- P7 coste cero: sin servicios gestionados de pago obligatorios.
- P5 reproducibilidad: dos sistemas con el mismo dataset producen los mismos resultados.
- P11 inmutabilidad de evidencia cruda: el storage de blobs debe ser content-addressed.
- ADR-0003 reforzaba que dependencias deben ser open source y archivables.

La elección del stack es estratégica: errar produce lock-in difícil de revertir años después.

## Decisión

El almacenamiento se estructura en **tres capas separadas**, cada una con su tecnología y su responsabilidad:

1. **Capa de blobs (Content-Addressed Object Store, CAOS)**
   Filesystem local con layout deterministico content-addressed. Cada blob vive en `objects/<algo>/<2chars>/<rest_of_hash>`. Sin base de datos para blobs.

2. **Capa de metadatos estructurados (Tabular columnar)**
   Tablas en formato **Apache Parquet**, organizadas por entidad (`evidence/`, `claims/`, `hypotheses/`, etc.), consultables vía **DuckDB** embebido. Append-only por defecto; mutaciones se hacen por reescritura de partición con cita histórica.

3. **Capa de índices secundarios (Embedded)**
   - Full-text: **Tantivy** (rust, embebible) o **SQLite FTS5** según fase.
   - Geoespacial: **DuckDB-spatial** sobre las tablas Parquet.
   - Temporal: index ranged sobre `TemporalAnchor` materializado en Parquet.
   - Vectorial opcional (para búsqueda semántica complementaria): **LanceDB** o equivalente embebible. **Opcional**, nunca camino crítico.

La fuente de verdad son siempre los blobs + Parquet. Índices se regeneran desde la fuente de verdad sin pérdida.

## Layout en disco

```
<aip_root>/
├── manifest.json              # versión del esquema, hash root, manifiesto reproducible
├── objects/                   # CAOS
│   └── sha256/
│       ├── 00/
│       │   └── 1f4a...        # contenido raw del blob
│       ├── 01/
│       └── ...
├── tables/                    # metadatos columnares
│   ├── evidence/              # particionado por año de ingesta
│   │   └── ingested_year=2026/
│   │       └── part-001.parquet
│   ├── sources/
│   ├── claims/
│   ├── hypotheses/
│   ├── hypothesis_sets/
│   ├── conclusions/
│   ├── cases/
│   ├── case_revisions/
│   ├── evidence_links/
│   ├── temporal_anchors/
│   ├── spatial_anchors/
│   ├── graph_nodes/
│   ├── graph_edges/
│   ├── actors/
│   └── provenance_steps/
├── indices/                   # regenerables desde tables/
│   ├── fts/
│   ├── spatial/
│   ├── temporal/
│   └── vector/                # opcional
├── archives/                  # WARCs y bundles archivísticos
│   └── warc/
└── snapshots/                 # snapshots citables exportados
    └── <snapshot_id>/
```

`<aip_root>` por defecto es `~/.aip/` pero el usuario puede usar cualquier ruta.

## Justificación

### Por qué tres capas separadas

Mezclar blobs grandes con metadatos en una sola base (e.g., SQLite con BLOBs grandes) degrada rendimiento y restringe el set de herramientas que pueden operar sobre los datos. Separar permite:

- Los blobs sobreviven incluso si la capa de metadatos se corrompe. Pueden reconstruirse índices.
- Los metadatos columnares aprovechan herramientas estándar (DuckDB, Polars, Pandas, Spark si se necesita).
- Los índices son consumibles por código distinto sin tocar la fuente de verdad.

### Por qué Parquet

- Estándar columnar abierto, dominante en analítica open source.
- Soporta esquemas evolutivos.
- Compatible con ecosistema entero (DuckDB, Polars, Arrow, Spark, etc.).
- Comprime eficientemente metadatos con cardinalidad típica.
- Particionable por año, fuente, tipo, lo que permite escalar a archivos grandes.

### Por qué DuckDB como motor

- Embebible, sin servidor.
- Soporte nativo de Parquet con pushdown de predicados.
- SQL recursivo apto para queries de grafo (ADR-0011).
- DuckDB-spatial cubre el motor geoespacial (ADR-0013).
- Velocidad analítica suficiente para datasets de cientos de millones de filas en portátil.
- Apache 2.0, sin lock-in.

### Por qué CAOS con filesystem

- Simple, transparente. Cualquier herramienta de filesystem opera sobre los blobs.
- Backups con rsync/borgbackup funcionan trivialmente.
- Compatible con OCFL (Oxford Common Filesystem Layout), estándar archivístico maduro, evaluación pendiente para Fase 1.
- No requiere proceso adicional running para acceso.

### Por qué append-only por defecto en metadatos

Operaciones de mutación destructivas son fuente de bugs irreproducibles. Append-only con superseding (ADR-0010, ADR-0016) preserva trazabilidad. Cuando una compactación es necesaria, se hace como evento explícito que reescribe particiones con marca temporal.

### Por qué FTS5 / Tantivy y no Elasticsearch

Elasticsearch requiere servidor JVM. Choca con P6, P7. FTS5 (SQLite) es trivial. Tantivy (Rust, embebible) es más potente y se evaluará en Fase 5 si SQLite FTS5 no escala.

### Por qué vectorial opcional

La búsqueda semántica es valiosa pero introduce dependencia de modelos de embedding cuya reproducibilidad bit a bit es frágil (versión del modelo, hardware, etc.). Se mantiene como capa **opcional**: el sistema funciona sin búsqueda vectorial. Cuando se usa, se documenta el modelo y la versión exactos en el manifiesto.

### Por qué snapshots en su propio directorio

Un snapshot es una exportación citable de un estado completo del archivo. Vive en `snapshots/` separado, comprimido o no, con su propio manifiesto. Citaciones académicas pueden apuntar a un snapshot publicado en Zenodo/IPFS sin ambigüedad.

## Consecuencias

**Positivas**
- Robustez frente a corrupción: blobs sobreviven a metadatos corruptos.
- Herramientas estándar de datos analíticos funcionan sin adaptación.
- Backups son triviales (rsync directorio entero).
- Reproducibilidad bit a bit alcanzable: dos clones del directorio responden idénticamente a las mismas queries.
- Sin servidor running para uso individual.

**Negativas**
- El directorio del archivo puede llegar a varios TB con archivos grandes. Decisión: aceptable para usuario individual con disco moderno; para datasets mayores se admite split por dataset.
- Particionar Parquet bien requiere disciplina. Documentada.
- No hay transacciones ACID multi-tabla nativas. Mitigado con escritura por partición + manifiesto atómico.

**Neutras**
- El modelo prescribe layout pero el usuario puede ubicarlo en cualquier ruta.

## Alternativas consideradas

### A. PostgreSQL con todo (blobs incluidos)
**Descripción:** Stack tradicional.
**Razón de rechazo:** Requiere servidor, choca con P6/P7 para uso individual. Lock-in en backup. Costes de admin no triviales.

### B. SQLite para todo, incluidos blobs
**Descripción:** Único fichero.
**Razón de rechazo:** Blobs grandes en SQLite degradan rendimiento. Imposibilita operar blobs con herramientas externas.

### C. MongoDB / base documental
**Descripción:** Documentos JSON con GridFS para blobs.
**Razón de rechazo:** Lock-in en formato. Sin licencia open source consistente. Queries analíticas inferiores a columnar.

### D. CSV en lugar de Parquet
**Descripción:** Texto plano.
**Razón de rechazo:** Sin tipos, sin compresión, sin pushdown. Inviable para grafos de cientos de millones de filas.

### E. Object store cloud (S3) como fuente de verdad
**Descripción:** Todo en S3 o equivalente.
**Razón de rechazo:** Choca con P6 local-first. Aceptable como sync opcional para usuarios que lo desean (no parte del núcleo).

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P6, P7, P9, P11.

**Cómo se alinean:**
- P6 (local-first): todo el stack es embebible sin servidor.
- P7 (coste cero): dependencias todas Apache/MIT.
- P11 (inmutabilidad de evidencia cruda): CAOS content-addressed.
- P5 (reproducibilidad): dos clones idénticos del directorio responden idénticamente.
- P9 (fuentes públicas): el formato del archivo es open standard exportable.

**Tensión:** Sin transacciones ACID multi-tabla. Aceptada con mitigación explícita.

## Referencias

- Apache Parquet specification.
- DuckDB documentation.
- OCFL (Oxford Common Filesystem Layout) specification.
- BagIt File Packaging Format (RFC 8493).
- Apache Arrow project.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
