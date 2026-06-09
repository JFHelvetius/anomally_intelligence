# Anomaly Intelligence Platform (AIP)

> Plataforma open source para investigar, organizar y cuantificar la incertidumbre que rodea a los reportes de fenómenos anómalos aéreos, orbitales, marítimos, astronómicos y observacionales. Sin posturas. Sin sensacionalismo. Sin conclusiones predeterminadas.

**Estado del proyecto:** **V1 arquitectónicamente cerrado · release `v0.2.0` (2026-06-08).** 42 ADRs aceptados + 3 enmiendas estructurales. Capa de atestación criptográfica ed25519 (ADR-0041), snapshot archive-wide atestable (ADR-0042), cadena de audit extendida a 6 dominios derivados (ADR-0019 §E1) y reconciliación disco↔log (ADR-0030 §E16). 910 tests · 17 pins canónicos de reproducibility · mypy --strict limpio. Ver [`CHANGELOG.md`](CHANGELOG.md) para el detalle completo.

## Sobre este repositorio

AIP es un proyecto de horizonte largo (5+ años). Su construcción siguió un proceso ADR-first: antes de escribir la primera línea de código se redactaron 31 decisiones arquitectónicas explícitas (`docs/adr/`) que delimitan el alcance, las propiedades irrenunciables, y las condiciones de archivo digno. Con `v0.1.0` esa fundación arquitectónica produjo un primer artefacto ejecutable —el modelo de evidencia y procedencia, reproducible bit a bit— sin abandonar la disciplina documental original. ADR-0032 levanta puntualmente la congelación V1 para introducir el motor de evaluación de autenticidad como capa **derivada** sobre el archive: cinco status booleanos, sin ML, sin scoring probabilístico, removible sin tocar la evidencia.

Toda la conversación arquitectónica vive en [docs/adr/](docs/adr/). Si quieres entender el proyecto, ese es el único lugar donde empezar. El ADR-0000 es la brújula; todos los demás se alinean con él. ADR-0023 (Scope Reduction) congela el alcance V1; cualquier ampliación requiere ADR explícito de levantamiento.

## La pregunta central

La plataforma **no** intenta demostrar ni refutar la existencia de UFOs, OVNIs, NHIs ni ninguna otra hipótesis sustantiva.

La pregunta central no es:

> "¿Qué es esto?"

La pregunta central es:

> "¿Qué nivel de confianza podemos asignar, con honestidad epistémica, a cada hipótesis competidora que explique este reporte?"

Esa reformulación es el ADN del proyecto. Cualquier diseño que la traicione queda fuera.

## Hoja de ruta a alto nivel

El proyecto se desarrolla en fases, cada una funcional y demostrable:

1. **Modelo de evidencia y fuentes** — esquemas formales, almacenamiento inmutable, trazabilidad bit a bit. ✅ **Entregada en `v0.1.0` (2026-06-06).**
2. **Catálogo de casos** — ingestión de archivos históricos y modernos sobre el modelo de evidencia.
3. **Hipótesis y confianza** — sistema explícito de hipótesis competidoras y cuantificación de incertidumbre.
4. **Motor temporal y geoespacial** — reconstrucción de líneas de tiempo y de superposiciones geográficas verificables.
5. **Grafo de conocimiento** — relaciones entre personas, organizaciones, eventos, lugares, medios y documentos.
6. **Workflows de investigación abierta** — herramientas para que un investigador externo pueda reproducir o contradecir cualquier conclusión.

Las fases 2–6 están **diseñadas** en ADRs aceptados pero **no comprometidas a calendario**: ADR-0023 (Scope Reduction) congela el alcance en V1; cualquier ampliación requiere ADR explícito de levantamiento. Ver [`docs/reviews/phase-1-review.md`](docs/reviews/phase-1-review.md) para el cierre formal de Fase 1.

El detalle vive en los ADRs.

## V1 ejecutable

Instalación canónica conforme a [ADR-0029](docs/adr/0029-runtime-language-decision.md) con [`uv`](https://github.com/astral-sh/uv) y el lockfile committeado:

```sh
# Desde un clone del repositorio:
uv sync --frozen --all-extras
```

`uv sync --frozen` instala exactamente las versiones declaradas en `uv.lock` (sin re-resolver). Tras la instalación, los comandos disponibles cubren cuatro capas:

```sh
# Núcleo V1 (ADR-0023): ingesta + verificación base
aip evidence ingest <pdf> --source-id ... --ingested-by @op
aip evidence show <hash>
aip archive verify [--quick|--full] [--derived] [--json]

# Capa derivada — motores (ADR-0032 a ADR-0040, opt-in, removible)
aip assess-authentication --archive PATH --evidence-id <hash> --actor @op
aip list-assessments --archive PATH [--evidence-id <hash>]
aip graph build|show|neighbors
aip impact analyze|show
aip context assemble|show|verify
aip workspace create|show|verify
aip timeline build|show|verify
aip snapshot create|show|verify
aip diff snapshots|justifications
aip justification build|show|verify

# Verificación universal (post-V1 hardening)
aip verify <artifact.json>          # auto-detecta 7 kinds + verifica self-hash

# Atestación criptográfica (ADR-0041 — ed25519)
aip attestation keygen --output-private key.pem --output-public key.pub
aip attestation sign <artifact.json> --signer-id @op --signed-at TS \
    --private-key key.pem [--archive PATH] [--attestation-id ID]
aip attestation verify <sig.json> [--public-key key.pub]

# Snapshot archive-wide (ADR-0042 — read-only, firmable)
aip archive snapshot [--generated-at TS] [--output FILE]
```

Pipeline canónico de compromiso público con archive-state:

```sh
aip archive snapshot --archive-root PATH > snap.json
aip attestation sign snap.json --signer-id @op --signed-at TS \
    --private-key priv.pem --output sig.json
aip attestation verify sig.json --public-key pub.pem    # rc=0 si íntegro
```

La demo reproducible vive en [`tests/integration/test_demo_pipeline.py`](tests/integration/test_demo_pipeline.py). Los 17 pins canónicos (PDF, manifests, audit chain, JCS, context bundle, justification, archive snapshot) viven en [`tests/reproducibility/`](tests/reproducibility/).

## Lo que el proyecto distingue rigurosamente

AIP nunca mezcla cinco categorías:

- **Hechos** — verificables independientemente, con cadena de custodia.
- **Afirmaciones** — atribuibles a una fuente, no necesariamente verificadas.
- **Interpretaciones** — lecturas humanas de hechos o afirmaciones.
- **Hipótesis** — explicaciones competidoras formuladas explícitamente.
- **Conclusiones** — evaluaciones de confianza relativa entre hipótesis, siempre revisables.

La arquitectura del sistema fuerza esa separación en el modelo de datos, no en convenciones humanas.

## Licencia

Distribuido bajo [Apache License 2.0](LICENSE). Uso comercial permitido. Cláusula de patentes incluida.

## Lengua

La documentación se escribe en español. Una traducción al inglés se considerará cuando aparezca contribuyente angloparlante sostenido; ningún calendario está comprometido y ningún ADR vigente exige la traducción para una versión específica.

## No-objetivos

AIP **no** existe para:

- Declarar origen extraterrestre, interdimensional, ni de ninguna naturaleza sustantiva.
- Promover teorías conspirativas, marcos ideológicos o agendas políticas.
- Generar contenido sensacionalista o viral.
- Esconder incertidumbre detrás de visualizaciones bonitas.
- Presentar especulación como hecho.

Estas prohibiciones son arquitectónicas, no editoriales. Están codificadas en el modelo de datos y en las propiedades irrenunciables del ADR-0000.
