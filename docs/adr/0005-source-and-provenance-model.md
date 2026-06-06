# ADR-0005: Modelo de fuente y procedencia

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0001, ADR-0002, ADR-0006, ADR-0016

---

## Contexto

Toda evidencia en el sistema viene de algún lugar. Sin un modelo formal de **fuente** y **procedencia**, la cadena epistémica del sistema queda rota en su raíz: no hay forma de auditar de dónde salió la información, qué transformaciones sufrió antes de llegar al sistema, ni en qué condición la recibimos.

El campo del estudio de fenómenos anómalos sufre especialmente esta carencia. Un mismo "documento desclasificado" puede haber pasado por:
- Liberación FOIA con redacciones.
- Escaneo a 200 DPI por un archivo civil.
- Re-OCR por un investigador en 1998 con software de la época.
- Re-escaneo a 600 DPI con corrección de color en 2014.
- Distribución por blog o foro sin metadatos.
- Re-recopilación por una organización que lo presenta como primario.

Cada una de esas etapas introduce posibles distorsiones (redacciones, errores OCR, recortes, falsificaciones). Sin un modelo de procedencia, todas se confunden.

W3C publicó PROV-O como ontología estándar para procedencia. La adopción directa es atractiva pero excesiva en granularidad. Necesitamos un subconjunto operable, compatible con PROV-O en exportación, pero adaptado al material del campo.

## Decisión

El sistema define dos tipos principales:

- **`Source`** — la entidad de la que procede directamente un artefacto ingresado al sistema. Tiene identidad estable, tipo, autoridad, y condiciones de acceso.
- **`Provenance`** — el grafo dirigido de transformaciones que un artefacto crudo ha sufrido desde su origen reconstruible hasta su forma actual en el sistema.

Cada `Evidence` (ADR-0006) referencia exactamente una `Source` primaria y opcionalmente un `Provenance` con la cadena completa de pasos intermedios. La procedencia es **declarada**, no inferida: si no se conoce un paso de la cadena, se registra como `unknown_step` con justificación, no se omite.

Toda procedencia es exportable a PROV-O para interoperabilidad externa.

## Modelo

### Source

```
Source {
  id: SourceId                   # ULID estable
  kind: SourceKind               # ver enumeración
  name: str                      # nombre humano
  authority: AuthorityLevel      # ver enumeración
  jurisdiction: ISO3166?         # país donde se origina, si aplica
  access_conditions: AccessSpec  # licencia, restricciones, fecha de acceso
  contact_info: ContactSpec?     # cómo verificar con la fuente, si aplica
  first_seen: date               # primera vez que el sistema vio esta fuente
  notes: markdown?
}
```

**`SourceKind`** (enumeración cerrada, extensible solo por ADR):

| Kind | Ejemplo |
|------|---------|
| `government_archive` | FOIA US, Archives Nationales, archivos GEIPAN |
| `military_report`    | Reportes desclasificados de servicios armados |
| `academic_publication` | Paper revisado por pares, tesis indexada |
| `civilian_organization` | NICAP, MUFON, NUFORC, CUFOS, GEIPAN ciudadano |
| `news_outlet` | Periódico, agencia de noticias, programa de TV |
| `witness_testimony` | Testimonio directo de un testigo identificado |
| `personal_archive` | Archivo de un investigador independiente con acceso a su material |
| `physical_artifact` | Objeto material (presunto fragmento, sello, marca en superficie) |
| `instrument_reading` | Radar, sonar, sismógrafo, sensor de satélite |
| `audiovisual_recording` | Foto, vídeo, audio originales con cadena de custodia |
| `online_aggregator` | Foro, base de datos online, agregador no curado |
| `social_media` | Red social pública |
| `unknown` | Fuente no determinable — debe explicarse en `notes` |

**`AuthorityLevel`** (cuatro niveles, deliberadamente austeros):

| Nivel | Significado |
|-------|------------|
| `primary` | Es el origen reconstruible del artefacto. No hay capa anterior accesible. |
| `secondary` | Recoge directamente de una fuente primaria, identificable. |
| `tertiary` | Recoge de secundaria. Múltiples capas de mediación. |
| `unattributable` | No se puede determinar la cadena hasta una fuente primaria. |

El nivel **no** mide credibilidad. Una fuente primaria puede ser falsa; una fuente terciaria puede transcribir fielmente. La credibilidad se evalúa en el plano de la evidencia (ADR-0006), no en el plano de la fuente.

### Provenance

```
Provenance {
  evidence_hash: ContentHash       # el artefacto cuya procedencia describe
  origin_source_id: SourceId       # raíz de la cadena
  steps: [ProvenanceStep]          # cadena ordenada cronológicamente
  is_complete: bool                # true si la cadena cubre toda la historia conocida
  gaps: [GapDescription]           # huecos conocidos, declarados
  attestor: ActorId                # quién declaró esta procedencia
  attested_at: timestamp
  signature: Signature?            # opcional, para procedencias atestiguadas con firma
}

ProvenanceStep {
  step_id: int                     # orden en la cadena
  kind: StepKind                   # ver enumeración
  actor: ActorId?                  # quién realizó el paso, si se conoce
  timestamp: timestamp?            # cuándo, si se conoce
  inputs: [ContentHash]            # artefactos de entrada
  outputs: [ContentHash]           # artefactos de salida (típicamente uno)
  parameters: dict                 # parámetros relevantes (DPI, software, etc.)
  notes: markdown?
}
```

**`StepKind`** ejemplos representativos:

| Kind | Descripción |
|------|-------------|
| `original_capture` | Captura original (foto tomada, audio grabado, documento mecanografiado) |
| `analog_to_digital` | Escaneo de papel, digitalización de cinta |
| `format_conversion` | Cambio de codec, contenedor, formato |
| `ocr` | Reconocimiento óptico de caracteres |
| `transcription` | Transcripción humana o automática |
| `translation` | Traducción a otro idioma |
| `redaction` | Aplicación de redacciones (por autoridad o por privacidad) |
| `crop_or_excerpt` | Recorte o extracto parcial |
| `enhancement` | Mejora de imagen/audio (filtros, denoise, etc.) |
| `attribution_change` | Cambio en la atribución declarada |
| `republication` | Republicación sin transformación material |
| `unknown_step` | Paso conocido como existente pero sin detalles |

### Cadena de custodia

Para evidencia con testigos vivos o material sensible (P12 del ADR-0000), `Provenance` admite una sub-estructura de **chain of custody** que registra transferencias físicas o de propiedad del artefacto. Esa estructura es opcional para evidencia documental pública.

### Identidad de actores

Los `ActorId` referidos arriba apuntan a un tipo `Actor` que puede ser:
- Persona identificada (`Person`).
- Organización (`Organization`).
- Sistema automático (`System`, ej. un escáner concreto en una sesión concreta).
- Anónimo declarado (`AnonymousActor`, con justificación).

`Actor` participa también en el grafo de conocimiento (ADR-0011).

## Justificación

### Por qué fuente y procedencia separadas

Una fuente es **dónde** lo encontramos; una procedencia es **cómo llegó hasta ahí**. Confundirlos colapsa la cadena: dos artefactos pueden venir de la misma fuente (un archivo civil) pero tener procedencias radicalmente distintas (uno escaneado por la propia institución, otro recibido por donación con tres pasos opacos previos). Tratarlos como un solo campo pierde esa distinción.

### Por qué cuatro niveles de autoridad y no más

Cuatro niveles cubren la práctica real del campo sin barroquismo. `primary`, `secondary`, `tertiary` son la jerarquía clásica de archivística. `unattributable` reconoce explícitamente lo no determinable, evitando que se camufle como terciaria por defecto.

### Por qué la procedencia es declarada, no inferida

El sistema **nunca** infiere automáticamente que un paso ocurrió ("este PDF fue OCR'd porque tiene capa de texto"). Tal inferencia, si necesaria, ocurre en una capa de interpretación auxiliar y se ingesta como una **afirmación sobre procedencia** que un humano debe revisar antes de promoverla a la procedencia oficial del artefacto. Esta separación protege P10 (no fabricación).

### Por qué huecos explícitos

Un `gap` declarado es información honesta. Un hueco silencioso es deshonestidad estructural. El sistema fuerza la primera opción.

### Por qué firma opcional

La firma de procedencia es valiosa cuando un archivo institucional atesta una cadena; es excesiva para uso individual. Se ofrece como opción, no como requisito, para no expulsar usuarios sin infraestructura PKI.

## Consecuencias

**Positivas**
- Auditabilidad de la cadena epistémica desde el primer momento.
- Compatible con PROV-O para interoperabilidad académica.
- Permite distinguir artefactos aparentemente idénticos con historias muy distintas.
- Soporta retracción granular: si se descubre que un paso intermedio fue fraudulento, el sistema puede invalidar todo lo posterior sin tocar lo anterior.

**Negativas**
- Ingestión más costosa. Un colaborador debe reconstruir cadena, no solo soltar el archivo.
- Riesgo de "procedencia teatral": rellenar campos con datos plausibles pero no verificados. Mitigado por requisito de atestación con `attestor` identificado.
- Coste de almacenamiento de metadatos no trivial.

**Neutras**
- Adopta vocabulario PROV-O en exportación, pero no fuerza al usuario a aprenderlo para uso interno.

## Alternativas consideradas

### A. PROV-O directo
**Descripción:** Usar PROV-O sin adaptación.
**Razón de rechazo:** Granularidad excesiva para uso habitual. Vocabulario alienante para investigadores no técnicos. Mantener compatibilidad de exportación es suficiente.

### B. Un único campo `source: str` libre
**Descripción:** Mínimo viable.
**Razón de rechazo:** Reproduce la patología del campo. Inauditable.

### C. Solo `Source`, sin `Provenance` separada
**Descripción:** La cadena va embebida en metadatos de la fuente.
**Razón de rechazo:** Confunde dónde con cómo. Hace imposible distinguir el caso en que el mismo archivo institucional aloja dos versiones del mismo artefacto con cadenas distintas.

### D. Procedencia como hash chain (estilo blockchain)
**Descripción:** Cada paso firmado por su actor en una cadena criptográficamente verificable.
**Razón de rechazo:** Excesivo para mayoría de casos. Atractivo en contextos institucionales — admitido como opción mediante el campo `signature`, pero no exigido.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P10, P11, P12.

**Cómo se alinean:**
- P2 (trazabilidad): operacionalización primaria. Sin procedencia, no hay trazabilidad.
- P10 (no fabricación): la procedencia es declarada por un actor identificado, no inferida.
- P11 (inmutabilidad de evidencia cruda): el origen reconstruible se preserva con su cadena.
- P12 (do-no-harm): la cadena de custodia opcional protege a testigos cuando aplica.

**Tensión:** Fricción de ingestión vs. honestidad de procedencia. Aceptada: P2 es no negociable.

## Referencias

- W3C PROV-O Recommendation. https://www.w3.org/TR/prov-o/
- Lemieux, V. L. (2016). *Trusting Records in the Cloud.*
- Hedstrom, M. (2002). *Archival Science perspectives on digital preservation.*

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
