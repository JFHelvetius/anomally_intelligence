# ADR-0014: Estrategia OSINT

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0005, ADR-0006, ADR-0019, ADR-0020

---

## Contexto

OSINT (Open Source Intelligence) cubre la práctica de obtener inteligencia a partir de fuentes públicas. Aplicado al campo de fenómenos anómalos, OSINT es la materia prima principal del archivo:

- Registros desclasificados FOIA y equivalentes nacionales.
- Repositorios académicos abiertos (Internet Archive, arXiv, repositorios universitarios).
- Hemeroteca digital (periódicos públicos, archivos de prensa, agencias).
- Archivos civiles online (NICAP scans, MUFON CMS público, NUFORC público, GEIPAN público).
- Open data gubernamental (AARO public releases, transcripciones del Congreso, audiencias parlamentarias).
- Material de instrumentos públicos (catálogos satelitales, redes sísmicas, registros radar civiles, ADS-B histórico).
- Material audiovisual público (películas históricas, programas de TV con licencias accesibles, podcasts).
- Redes sociales públicas con contenido testimonial.

El reto es operacionalizar el flujo desde estas fuentes al modelo de evidencia formal (ADR-0006) **respetando**:

- Términos de servicio de cada fuente.
- Marco legal de cada jurisdicción (P9, P12 del ADR-0000).
- Ética: no doxxing de testigos, no agregación que produzca daño (P12, ADR-0020).
- Procedencia trazable (ADR-0005): cada artefacto ingestado lleva su origen documentado.

## Decisión

El sistema mantiene una **capa de adquisición OSINT** que es:

1. **Modular por fuente**. Cada fuente pública relevante tiene su propio módulo adquisidor con responsabilidades claras y aisladas.
2. **Sujeta a un código de prácticas explícito** documentado en `docs/osint-code-of-practice.md`. Cualquier adquisidor que viole el código no se merge.
3. **Trazable**. Cada adquisición registra qué fuente, cuándo, bajo qué parámetros, con qué resultado, y produce un manifiesto que entra al modelo de procedencia.
4. **Opt-in y opcional**. Ningún adquisidor se ejecuta automáticamente sin acto explícito del usuario. No hay scrapers de fondo.
5. **Respetuosa con los términos de servicio**. Robots.txt, rate limits, condiciones de uso son obligatorios. Bypass de medidas técnicas o legales es motivo de rechazo de PR.

La estrategia OSINT **no** incluye:

- Scraping masivo silencioso.
- Deanonymization de personas a partir de cruces de fuentes (P12, ADR-0020).
- Acceso a fuentes restringidas, vulneración de acceso autorizado, ingeniería social.
- Uso comercial encubierto de archivos públicos cuyas licencias lo prohíben.

## Modelo

### Acquirer (módulo adquisidor)

```
Acquirer {
  id: AcquirerId                   # nombre único del módulo
  source_id: SourceId              # ADR-0005, fuente que cubre
  legal_basis: LegalBasis          # ver enumeración
  compliance_doc: URI              # documento que justifica el cumplimiento
  rate_limit: RateLimitSpec
  output_kind: [EvidenceKind]      # qué tipos produce
  schema_version: SemVer
  maintained_by: ActorId
  status: AcquirerStatus           # active | deprecated | suspended_compliance_issue
}
```

`LegalBasis`:

| Basis | Significado |
|-------|------------|
| `public_domain` | Material en dominio público (e.g., USG works post-publication) |
| `permissive_license` | Licencia abierta del material (CC, etc.) |
| `tos_compliant_use` | Acceso permitido por TOS de la fuente |
| `fair_use_research` | Uso transformativo para investigación; documentado |
| `mixed_per_item` | El estatus depende del ítem individual; el adquisidor lo registra |

`AcquirerStatus.suspended_compliance_issue` se activa automáticamente cuando un test de compliance del adquisidor falla.

### Manifiesto de adquisición

Cada ejecución de un adquisidor produce un manifiesto que se ingresa al modelo de procedencia (ADR-0005):

```
AcquisitionManifest {
  acquirer_id: AcquirerId
  executed_by: ActorId
  executed_at: timestamp
  parameters: dict                 # qué parámetros se usaron
  source_endpoint: URI             # URL o referencia exacta
  http_capture: HttpCapture?       # opcional: hash del bundle WARC/MHTML
  artifacts_produced: [ContentHash]
  errors: [ErrorRecord]
  retries: int
  tos_consulted_at: timestamp      # hash de la versión del TOS vigente en la captura
  notes: markdown?
}
```

`http_capture` es opcional pero recomendado: empaqueta la respuesta HTTP completa (cabeceras, cuerpo) en WARC. Permite re-derivar el artefacto si el endpoint original cambia o desaparece.

### Tipos de adquisidores

**Adquisidores de archivo (snapshot)**
Adquisidores que toman un snapshot de una fuente estable (un archivo desclasificado, una página de archivo nacional). Una vez snapshot tomado, el adquisidor no vuelve a ejecutarse sobre el mismo objeto.

**Adquisidores incrementales**
Adquisidores que pollean periódicamente una fuente que cambia (nuevas desclasificaciones de un archivo, nuevos reportes ciudadanos publicados). Cada poll respeta rate limits y `If-Modified-Since`.

**Adquisidores manuales asistidos**
Para fuentes que solo pueden adquirirse con interacción humana (uploads desde el filesystem del usuario, registro de testimonio en grabación local). El adquisidor proporciona herramientas y produce el manifiesto, pero no ejecuta llamadas remotas.

### Fuentes priorizadas para fase inicial

Sin orden de implementación rígido (depende del estado real de cada fuente), las prioridades operativas son:

| Fuente | Tipo | Justificación |
|--------|------|---------------|
| Project Blue Book (NARA) | Archivo público USG | Material histórico canónico, dominio público |
| GEIPAN / CNES | Archivo público FR | Material institucional con esquema propio |
| AARO public releases | Gobierno actual | Material contemporáneo de interés |
| Internet Archive (selección) | Agregador con licencia clara por ítem | Fuente secundaria con metadatos preservados |
| NICAP scans (públicos) | Archivo civil | Material histórico ampliamente citado |
| NUFORC reports (público) | Archivo civil | Material contemporáneo ciudadano |
| Congressional hearings (USG) | Transcripciones públicas | Material reciente de alto perfil |

Otras fuentes (MUFON, archivos europeos nacionales, archivos latinoamericanos) requieren evaluación case-by-case de TOS y se incorporan caso por caso.

### Política sobre redes sociales y contenido individual

Las redes sociales públicas contienen testimonios valiosos pero plantean problemas serios:

- TOS de las plataformas son restrictivos y cambiantes.
- Los autores son individuos identificables que pueden no haber consentido a ingestión académica.
- El contenido es típicamente efímero, de baja calidad de procedencia.

Política:

- **No se ingestan redes sociales por scraping masivo.**
- Material individual puede ingestarse con **consentimiento del autor** o si el contenido satisface criterios documentados de interés público suficiente para invocar uso transformativo, **caso por caso**, con autorización del curador del proyecto (no del adquisidor automático).
- Nunca se ingestan datos personales identificables que el autor no haya hecho públicos a sabiendas como parte de una declaración pública.

### Cumplimiento por jurisdicción

El sistema reconoce que adquirir contenido legal en una jurisdicción puede ser ilegal en otra. Política:

- Cada adquisidor declara la jurisdicción bajo la cual evalúa la legalidad de su acción.
- Operadores en otras jurisdicciones son responsables de evaluar si pueden ejecutarlo localmente.
- El proyecto no asume responsabilidad sobre la legalidad de la operación de un usuario individual en su contexto.

### Captura web archivística

Para adquisición web no trivial, el sistema usa formato WARC (Web Archive) como contenedor primario antes de derivar evidencia atómica. Esto:

- Preserva la respuesta HTTP completa (incluyendo cabeceras, fecha del servidor).
- Es estándar adoptado por archivos nacionales (Internet Archive, Bibliothèque nationale de France, British Library).
- Permite reproducir el render del recurso en su época.

WARC es el contenedor; los `Evidence` extraídos son derivados con procedencia que cita el WARC original.

## Justificación

### Por qué modular por fuente

Cada fuente tiene TOS, autenticación, formatos y peculiaridades distintas. Un adquisidor monolítico se vuelve frágil. Los módulos aislados pueden suspenderse o actualizarse independientemente.

### Por qué `legal_basis` declarada por adquisidor

Sin esto, cada adquisición sería ad-hoc y no auditable. Declarado por módulo, una auditoría externa puede verificar el portfolio entero rápidamente.

### Por qué no scraping silencioso

Cuatro razones convergentes: (1) viola TOS típicos; (2) crea costes legales al proyecto; (3) crea daño potencial a personas mencionadas en el contenido; (4) la información obtenida sin trazabilidad legal no es defendible.

### Por qué política conservadora sobre redes sociales

El balance riesgo/beneficio es desfavorable. El testimonio social mediado es típicamente de procedencia frágil, los autores tienen derechos, y los TOS son restrictivos. La política conservadora preserva el carácter del archivo.

### Por qué WARC como contenedor

Estándar archivístico maduro. Compatible con la práctica de archivos nacionales. Permite reproducir el render en época. Open source y bien soportado.

## Consecuencias

**Positivas**
- Cumplimiento legal y ético explícito y auditable.
- Procedencia rigurosa desde la adquisición.
- Adquisidores son módulos versionables y reutilizables.
- WARC preserva contexto.

**Negativas**
- Adquisición es más lenta de implementar que un script ad-hoc.
- Fuentes con TOS restrictivos quedan fuera incluso si tienen contenido relevante.
- Política conservadora sobre redes sociales puede percibirse como limitación.

**Neutras**
- Operadores en jurisdicciones distintas tienen responsabilidades distintas.

## Alternativas consideradas

### A. Scraper único universal
**Descripción:** Un solo crawler que recoge todo lo accesible.
**Razón de rechazo:** Frágil, opaco, riesgo legal acumulado.

### B. Política agresiva sobre redes sociales
**Descripción:** Ingestar todo lo público disponible.
**Razón de rechazo:** Daño potencial a individuos. Conflicto con P12.

### C. Sin adquisidores nativos; solo upload manual
**Descripción:** Cada ingestión es manual.
**Razón de rechazo:** Hace imposible la escala con fuentes activas como AARO releases.

### D. Adquisidores sin manifiesto formal
**Descripción:** Adquisición sin registro estructurado.
**Razón de rechazo:** Rompe procedencia (ADR-0005).

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P9, P11, P12.

**Cómo se alinean:**
- P9 (fuentes públicas como primarias): operacionalización primaria.
- P2 (trazabilidad) y P11 (inmutabilidad): manifiestos de adquisición y WARC preservados.
- P12 (do-no-harm): política sobre redes sociales y datos personales.
- P5 (reproducibilidad): re-ejecución del adquisidor desde el manifiesto produce el mismo resultado bit a bit si la fuente no ha cambiado.

**Tensión:** Cobertura de archivo vs. respeto de TOS. Aceptada: cobertura sin legitimidad no es cobertura defendible.

## Referencias

- IIPC (International Internet Preservation Consortium). WARC specification.
- robotstxt.org. Robots Exclusion Standard.
- Bellotti, V., & Edwards, K. (2001). *Intelligibility and Accountability.*
- Bertot, J. C., Jaeger, P. T., & Grimes, J. M. (2010). *Crowd-sourcing Transparency.*
- Cumplimiento GDPR para investigación. EDPB guidelines.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
