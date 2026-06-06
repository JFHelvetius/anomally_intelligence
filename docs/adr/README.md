# Architecture Decision Records — AIP

Este directorio contiene los Architecture Decision Records (ADRs) del Anomaly Intelligence Platform. Los ADRs son el artefacto canónico del proyecto: ninguna decisión arquitectónica se considera tomada hasta que existe un ADR que la documenta.

## Cómo leer este directorio

1. **Empieza por [`0000-long-term-vision.md`](0000-long-term-vision.md).** Es la brújula del proyecto. Todos los demás ADR se alinean con él.
2. Después, los ADR están numerados en orden creciente. Cada uno declara su relación con los anteriores en la cabecera.
3. La plantilla canónica vive en [`template.md`](template.md). Cualquier ADR nuevo debe partir de ella.

## Estado de los ADRs

### Bloque fundacional (0000–0022)

| ID   | Título                                                                 | Estado     | Implementación V1 |
|------|------------------------------------------------------------------------|------------|-------------------|
| 0000 | Visión a largo plazo                                                   | Aceptado   | —                 |
| 0001 | Separación estricta hecho / afirmación / interpretación / hipótesis / conclusión | Aceptado   | Parcial (solo `Evidence`)  |
| 0002 | Arquitectura evidence-first                                            | Aceptado   | Sí                |
| 0003 | Local-first y reproducibilidad bit a bit                               | Aceptado   | Sí                |
| 0004 | Arquitectura por fases                                                 | Aceptado   | Sí (F1)           |
| 0005 | Modelo de fuente y procedencia                                         | Aceptado   | Sí                |
| 0006 | Modelo de evidencia formal                                             | Aceptado   | Sí (núcleo)       |
| 0007 | Modelo de afirmación (claim)                                           | Aceptado   | **Diferido** (ADR-0023) |
| 0008 | Modelo de hipótesis competidoras                                       | Aceptado   | **Diferido** (ADR-0023) |
| 0009 | Marco de incertidumbre y confianza                                     | Aceptado   | **Diferido** (ADR-0023) |
| 0010 | Ciclo de vida del caso                                                 | Aceptado   | **Diferido** (ADR-0023) |
| 0011 | Diseño del grafo de conocimiento                                       | Aceptado   | **Diferido** (ADR-0023) |
| 0012 | Motor temporal                                                         | Aceptado   | **Diferido** (ADR-0023) |
| 0013 | Motor geoespacial                                                      | Aceptado   | **Diferido** (ADR-0023) |
| 0014 | Estrategia OSINT                                                       | Aceptado   | **Diferido** (ADR-0023) |
| 0015 | Estrategia de almacenamiento                                           | Aceptado   | Sí (subset)       |
| 0016 | Versionado y direccionamiento por contenido                            | Aceptado   | Sí                |
| 0017 | Diseño de API                                                          | Aceptado   | Sí (CLI + Python, sin HTTP) |
| 0018 | Estrategia de búsqueda                                                 | Aceptado   | **Diferido** (ADR-0023) |
| 0019 | Modelo de seguridad                                                    | Aceptado   | Sí (audit log; enclave diferido) |
| 0020 | Marco ético y do-no-harm                                               | Aceptado   | **Diferido** (ADR-0023) |
| 0021 | No-fabricación por LLMs                                                | Aceptado   | **Diferido** (ADR-0023) |
| 0022 | Licencia Apache 2.0                                                    | Aceptado   | Sí                |

### Bloque de enmiendas en respuesta al Red Team Review (0023–0028)

| ID   | Título                                                                 | Estado     | Tipo de enmienda     |
|------|------------------------------------------------------------------------|------------|----------------------|
| 0023 | Scope Reduction                                                        | Aceptado   | Recorte de V1        |
| 0024 | Epistemic Honesty Amendment                                            | Aceptado   | Límites operativos   |
| 0025 | Neutrality Clarification                                               | Aceptado   | Reformulación de P4  |
| 0026 | Sustainable Stewardship                                                | Aceptado   | Gobernanza operativa |
| 0027 | Graceful Archive Policy                                                | Aceptado   | Triggers de archivo  |
| 0028 | License Reassessment                                                   | Aceptado   | Reafirmación con disparadores |

Las enmiendas no superseden a los ADRs fundacionales. Los acotan, los operacionalizan, o los reafirman explícitamente. Las enmiendas al ADR-0000 introducidas por ADR-0025 y ADR-0027 viven en el historial de enmiendas del ADR-0000.

### Bloque operativo Pre-F1 (0029–0031)

| ID   | Título                                                                 | Estado     | Función                       |
|------|------------------------------------------------------------------------|------------|-------------------------------|
| 0029 | Runtime Language Decision                                              | Aceptado   | Formaliza Python 3.11+ + uv  |
| 0030 | Repository Layout                                                      | Aceptado   | src layout + 4 subpaquetes   |
| 0031 | Testing Strategy                                                       | Aceptado   | unit/integration/reproducibility, sin red |

Estos tres ADRs no introducen alcance nuevo. Formalizan decisiones operativas hasta ahora implícitas o latentes, prerrequisitos de la implementación de Fase 1.

## Especificaciones Pre-F1 fuera de ADR

Documentos de especificación pre-implementación que no son ADR pero son contrato operativo:

- [`../phase-1/demo-evidence-selection.md`](../phase-1/demo-evidence-selection.md) — Pre-F1.C: PDF fixture canónico de la demo, criterios de selección, procedimientos de publicación y verificación del SHA-256.
- [`../phase-1/command-specification.md`](../phase-1/command-specification.md) — Pre-F1.D: contrato testeable de los tres comandos (`evidence ingest`, `evidence show`, `archive verify`).

## Revisiones externas

Las revisiones críticas de la arquitectura (red team, peer review) viven en [`../reviews/`](../reviews/). Son ataques deliberados al diseño desde una postura hostil. Se mantienen sin sanear como materia prima para enmiendas posteriores.

El informe formal de respuesta a la revisión del 2026-06-03 vive en [`../reviews/red_team_response.md`](../reviews/red_team_response.md) y categoriza cada hallazgo como cerrado, mitigado o aceptado conscientemente.

## Reglas de proceso

- **Un ADR se propone, no se impone.** Los PRs de ADR deben abrir conversación antes de mergearse.
- **Un ADR aceptado no se reescribe.** Se enmienda al pie o se supersede con uno nuevo.
- **Un ADR sin sección "Alineación con ADR-0000" no se merge.** Sin excepciones.
- **Numeración estricta.** No se reutilizan números. Un ADR anulado conserva su número y su contenido, con estado "Anulado".
