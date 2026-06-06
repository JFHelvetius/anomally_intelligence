# Mantenedores AIP

Este documento es el registro autoritativo de quién mantiene AIP en cada momento, qué responsabilidades asumen y bajo qué reglas opera el proyecto. Es artefacto del repositorio: su versión vigente es siempre la del `main`, y su historial es la historia del stewardship del proyecto.

Cumple los compromisos operativos C1 y C2 del ADR-0026 (Sustainable Stewardship).

---

## Roles definidos

El proyecto reconoce cuatro roles. No todos los roles necesitan estar ocupados en todo momento.

### `founder`

Quien fundó el proyecto y mantiene autoridad histórica sobre la visión del ADR-0000. Hay como máximo uno. Su retirada o desaparición no elimina el rol; pasa a `emeritus` con la fecha de transición.

### `co-maintainer`

Quien comparte responsabilidad activa de mantenimiento con `founder` u otros `co-maintainer`. Puede aceptar y revisar PRs sin co-firma cuando la decisión no toca ADRs aceptados.

### `area-maintainer`

Quien asume responsabilidad sobre un área concreta del código o de la documentación. Sus decisiones tienen autoridad dentro de su área; fuera de ella, opera como contribuyente.

### `emeritus`

Mantenedor que se ha retirado pero conserva conocimiento histórico del proyecto. No tiene autoridad operativa salvo consulta voluntaria. Su nombre permanece en el historial como reconocimiento.

---

## Activos

| Handle | Rol | Incorporado | Áreas | Contacto público |
|---|---|---|---|---|
| `@jfhelvetius` | `founder` | 2026-06-03 | Todas | A definir antes de release |

**Total de mantenedores activos:** 1.

---

## Bus factor

**Bus factor declarado:** **1**

**Última revisión:** 2026-06-04
**Próxima revisión obligatoria:** 2026-12-04 (semestralmente conforme a ADR-0026 C2)

### Implicaciones operativas de bus factor = 1

El proyecto declara públicamente al usuario externo que:

- Cualquier release puede ser la última si el mantenedor único deja el proyecto sin sucesor.
- No existe SLA de respuesta a issues, PRs ni cuestiones de seguridad.
- Decisiones arquitectónicas son sostenidas por una persona, sujetas a su sesgo individual reconocido en ADR-0025.
- La continuidad del proyecto depende de la disponibilidad voluntaria del mantenedor único.

Estas implicaciones no son advertencia legal: son descripción operativa honesta.

---

## Responsabilidades por rol

### Responsabilidades de `founder`

- Mantener viva la visión del ADR-0000 mientras el rol esté activo.
- Aceptar o rechazar PRs que modifiquen ADRs (a través de proceso de enmienda, no reescritura).
- Decidir disposición de propiedades irrenunciables si una decisión nueva las afecta.
- Mantener actualizado este `MAINTAINERS.md`.
- Revisar semestralmente el bus factor y publicar resultado.
- Ejecutar pasos del ADR-0027 (Graceful Archive Policy) si los triggers se activan.

### Responsabilidades de `co-maintainer`

- Revisar y aceptar PRs de código y documentación dentro del marco de ADRs aceptados.
- Co-firmar PRs que modifiquen ADRs (acuerdo entre mantenedores activos antes de merge).
- Mantener disciplina sobre las reglas de proceso documentadas en `docs/adr/README.md`.
- Reportar al `founder` (o al colectivo de mantenedores activos) si detecta tensión entre una decisión propuesta y las propiedades irrenunciables.

### Responsabilidades de `area-maintainer`

- Autoridad final sobre PRs dentro de su área declarada.
- Mantener la documentación de su área actualizada.
- Coordinar con otros mantenedores cuando un PR cruza áreas.

### Responsabilidades de `emeritus`

- Ninguna obligación operativa.
- Disponibilidad voluntaria para consulta histórica.
- Veto suave: cualquier mantenedor activo puede consultar a un `emeritus` sobre decisiones que afecten la integridad del ADR-0000 antes de proceder.

---

## Proceso de sucesión

Cumple ADR-0026 Compromiso C3. Aplica a cualquier incorporación de `co-maintainer` o sucesor de `founder`.

### Paso 1. Manifestación de interés

Cualquier persona puede manifestar interés en mantener AIP mediante issue público en el repositorio con el título `[stewardship] candidatura de mantenedor`. El issue debe incluir:

- Identidad pública (handle, nombre opcional, contacto público).
- Motivación.
- Disponibilidad estimada (horas/semana razonablemente sostenibles).
- Áreas de interés.
- Conformidad explícita con las propiedades irrenunciables P1–P12 del ADR-0000 y con los sesgos declarados S1–S4 del ADR-0025.

### Paso 2. Lectura documentada

El candidato confirma por PR sobre este `MAINTAINERS.md` (o sobre un fichero adjunto) que ha leído íntegramente:

- ADR-0000 (visión).
- ADRs 0023–0028 (enmiendas de honestidad).
- `docs/reviews/adr_red_team_review.md` y `docs/reviews/red_team_response.md`.
- `PROJECT_STATUS.md` vigente.

La confirmación es una firma en el documento con su handle y la fecha de lectura. No se exige examen de contenidos; se exige reconocimiento explícito de que el material se conoce.

### Paso 3. Acuerdo escrito

El candidato firma una sección de **Acuerdo de Mantenimiento** que se anexa al final de este `MAINTAINERS.md`. El texto canónico:

> Yo, `<handle>`, en fecha `<fecha>`, acepto las propiedades irrenunciables P1–P12 del ADR-0000, los siete límites operativos del ADR-0024, los cuatro sesgos declarados del ADR-0025 y los cinco compromisos del ADR-0026 como marco vinculante de mi rol como `<rol>` en el proyecto AIP. Reconozco que no puedo modificar unilateralmente el ADR-0000 ni el ADR-0022/0028 (licencia), y que cualquier modificación sustantiva del marco ético (ADR-0020) requiere revisión externa documentada conforme al ADR-0026.

### Paso 4. Aceptación

El mantenedor en ejercicio (o consenso de mantenedores activos si hay más de uno) acepta el candidato mediante merge del PR que añade su entrada a la tabla "Activos" y la fila correspondiente en el historial.

Cuando hay solo un mantenedor activo y este acepta un primer `co-maintainer`, su decisión basta. Una vez incorporado el primero, futuras incorporaciones requieren acuerdo entre mantenedores activos.

### Caso especial: sucesión por desaparición del mantenedor único

Si el mantenedor único es **inalcanzable durante seis meses** por todos los canales públicos declarados, aplica el trigger T7 del ADR-0027:

1. Cualquier interesado externo puede declarar su intención de asumir mantenimiento abriendo issue público y siguiendo los Pasos 1–3 anteriores.
2. Se abre **plazo público de tres meses adicionales** para que aparezcan otros candidatos o para que el mantenedor original responda.
3. Si transcurren los tres meses sin que el mantenedor original retome contacto y aparece un candidato que ha completado Pasos 1–3, ese candidato puede merger su propio PR como `founder` sucesor.
4. Si transcurren los tres meses sin candidato confirmado, se activa el archivado digno del ADR-0027.

Este mecanismo no es ideal pero es la única defensa estructural ante desaparición silenciosa.

---

## Reglas de decisión

### D1. Decisiones que **requieren ADR**

- Cualquier cambio que afecte una propiedad irrenunciable P1–P12.
- Cualquier cambio en el modelo de datos público (Evidence, Source, Provenance, etc.).
- Cualquier cambio de licencia.
- Cualquier ampliación de alcance respecto al definido en ADR-0023.
- Cualquier supersedencia o enmienda a un ADR existente.
- Cualquier cambio sustantivo en el marco ético (ADR-0020) o en los procedimientos derivados (`docs/ethics-procedures/`).

Las decisiones por ADR siguen el proceso del `docs/adr/README.md`. Sin ADR aprobado, la decisión no es vinculante para el proyecto.

### D2. Decisiones que **no requieren ADR**

- Bugfixes que no cambian semántica documentada.
- Mejoras de rendimiento que preservan invariantes.
- Documentación adicional que no contradice ADRs vigentes.
- Pruebas adicionales sobre comportamiento ya especificado.
- Refactorizaciones internas sin cambio de API pública.

Estas decisiones se aceptan por revisión normal de PR sin proceso adicional.

### D3. Decisiones bloqueadas mientras bus factor = 1

Aunque técnicamente el mantenedor único puede aprobar cualquier cosa, el propio mantenedor se compromete a **no ejecutar las siguientes acciones** mientras bus factor = 1, salvo emergencia documentada:

- Re-licenciamiento del código fuera de los disparadores D1–D4 del ADR-0028.
- Supersesión del ADR-0000.
- Cambio en el conjunto de propiedades irrenunciables.
- Aceptación de patrocinios o financiación que condicionen la dirección del proyecto.

Estas auto-restricciones son defensa contra captura emocional o presión externa sobre un actor único. Se relajan cuando bus factor ≥ 2.

### D4. Resolución de conflictos entre mantenedores

Cuando hay desacuerdo sustantivo entre mantenedores activos:

1. **Documentar el desacuerdo** en un issue público con las posiciones razonadas de cada parte.
2. **Período de reflexión** de al menos siete días naturales sin merge de la decisión disputada.
3. **Búsqueda de revisor externo** sin afiliación previa al proyecto si el desacuerdo persiste.
4. **Decisión por consenso** después de la revisión externa. Si el consenso es imposible, el desacuerdo se documenta como tal y la decisión por defecto es **no actuar**: el statu quo se preserva.

---

## Política explícita de no-SLA

Esta sección operacionaliza el Compromiso C5 del ADR-0026.

### El proyecto NO promete

- ❌ Tiempos de respuesta a issues, en ningún horizonte.
- ❌ Tiempos de revisión de PRs, en ningún horizonte.
- ❌ Frecuencia de releases.
- ❌ Compatibilidad hacia delante ni hacia atrás de cualquier API que no esté declarada estable en su ADR correspondiente.
- ❌ Disponibilidad del mantenedor para asistencia personal.
- ❌ Resolución de bugs en un plazo determinado, incluyendo bugs de seguridad.
- ❌ Continuidad del proyecto más allá de la próxima release.

### El proyecto SÍ promete

- ✅ Que cualquier release lleve manifiesto reproducible (ADR-0016).
- ✅ Que las decisiones tomadas se documentan como ADR (D1).
- ✅ Que las decisiones de ética concretas se documentan caso por caso conforme a `docs/ethics-procedures/`.
- ✅ Que los mantenedores cuyo nombre figura en este documento declaran disposición razonable a recibir comunicación pública.
- ✅ Que el `ARCHIVED.md` (ADR-0027) se publica si y cuando el proyecto se archiva.
- ✅ Que la licencia Apache 2.0 + CC BY-SA 4.0 (corpus) permite continuación independiente por cualquier interesado.

Las promesas son seis. Las no-promesas son siete. Esa proporción es deliberada y honesta.

---

## Quality gates declarados y CI

Quality gates declarados en ADR-0031, ejecutados por `.github/workflows/ci.yml` en cada push y PR a `main`:

| Gate | Comando | Plataforma | Estado en `main` |
|---|---|---|---|
| ruff lint | `ruff check src tests` | Ubuntu × Python 3.11, 3.12 | bloqueante |
| mypy strict | `mypy` | Ubuntu × Python 3.11, 3.12 | bloqueante |
| pytest + cobertura | `pytest --cov=aip --cov-fail-under=90` | Ubuntu × Python 3.11, 3.12 | bloqueante |
| pytest (sin lint/cov) | `pytest -q` | macOS-latest (arm64), Windows-latest (x86_64) | best-effort (`continue-on-error: true`) |

La distinción Ubuntu / best-effort sigue ADR-0029 §M3: el mantenedor único no opera cotidianamente en macOS ni Windows; bloquear merge por una rotura ahí sería política de equipo grande, no la realidad operativa de este proyecto. **Pero**: cualquier divergencia de pinned hashes entre Ubuntu y los runners best-effort se trata como bug arquitectónico crítico (ADR-0024 §formato canónico vs. motor), no como degradación aceptable.

### Herramientas explícitamente NO añadidas al CI

- **CodeQL.** Evaluado y rechazado para V1. Justificación: AIP V1 no expone HTTP, no recibe input no-sanitizado de red, no ejecuta SQL parametrizado, no procesa datos de usuario por LLM, no llama subprocess con entradas externas. Las clases de hallazgo que CodeQL detecta en Python (deserialización insegura, inyección de comandos, path traversal, SQL injection) no tienen superficie real en V1. El coste de revisar falsos positivos bajo bus factor = 1 supera el beneficio de signal. Esta decisión se revisa **automáticamente** cuando se aprueben los ADRs de levantamiento de `aip.http`, `aip.osint`, `aip.llm` o `aip.search`.
- **Mutation testing en CI.** Útil pero caro de mantener bajo bus factor = 1. Puede ejecutarse localmente cuando el mantenedor lo elija; no es gate.
- **Bandit / safety / pip-audit.** Solapan con `dependabot security-only` (`.github/dependabot.yml`). Sin valor incremental para este alcance.

## Branch protection (intent)

**Estado actual:** sin branch protection enforced sobre `main`. Justificación: bus factor = 1 hace que reglas como "required PR review from non-author" bloqueen al único mantenedor activo, lo cual transforma el mecanismo de protección en mecanismo de obstrucción.

**Cuando se active (bus factor ≥ 2 declarado en este documento)**, la configuración intencionada es:

| Regla | Valor intencionado | Razón |
|---|---|---|
| Required status checks | `gates (Ubuntu / py3.11)`, `gates (Ubuntu / py3.12)` | Los tres gates de quality. macOS/Windows quedan informativos. |
| Require branches to be up to date | Sí | Evita merges sobre base antigua. |
| Require pull request reviews | 1 reviewer, no author | Mínimo razonable bajo bus factor = 2. |
| Dismiss stale reviews on new commits | Sí | Cualquier cambio post-review re-dispara aprobación. |
| Require linear history | Sí | No merge commits; rebase only. |
| Allow force pushes | No | Sin excepciones. |
| Allow deletions | No | El historial es trazabilidad (ADR-0024 L2). |
| Restrict who can push to matching branches | Maintainers activos | Sin excepciones. |

Estas reglas **no se aplican hoy**. Se documentan aquí para que la transición sea inmediata cuando bus factor suba.

### Excepciones permitidas incluso con branch protection activa

- Bumps de `dependabot` security-only pueden auto-mergearse si pasan los gates obligatorios. Será decisión explícita del primer co-maintainer.
- Documentación que no toca código (`docs/**/*.md`) puede mergearse por el autor del PR si los gates pasan, sin segunda aprobación. Decisión a confirmar cuando aplique.

---

## Alineación con ADR-0026

Este documento **opera** los cinco compromisos de ADR-0026:

| Compromiso ADR-0026 | Sección de este documento |
|---|---|
| C1. `MAINTAINERS.md` como artefacto obligatorio | Todo este documento |
| C2. Bus factor declarado | Sección "Bus factor" |
| C3. Protocolo de sucesión | Sección "Proceso de sucesión" |
| C4. Decisiones ancladas a procedimiento | Sección "Reglas de decisión" + referencia a `docs/ethics-procedures/` |
| C5. Política de no-SLA | Sección "Política explícita de no-SLA" |

Si este documento entra en contradicción operativa con ADR-0026, prevalece el ADR. Las correcciones se aplican aquí mediante PR; las correcciones al ADR-0026 requieren ADR de enmienda.

---

## Historial de cambios en la lista de mantenedores

| Fecha | Cambio | Bus factor resultante |
|---|---|---|
| 2026-06-03 | Fundación del proyecto. `@jfhelvetius` incorporado como `founder` único. | 1 |
| 2026-06-04 | Publicación inicial de este `MAINTAINERS.md` conforme a ADR-0026. Sin cambios en la lista. | 1 |
| 2026-06-06 | Hardening de CI. Añadidas secciones "Quality gates declarados y CI" y "Branch protection (intent)". Decisión razonada de no añadir CodeQL/Bandit/safety. Sin cambios en la lista. | 1 |

---

## Acuerdos de Mantenimiento (firmas)

Esta sección recoge la firma del Acuerdo de Mantenimiento (Paso 3 de la sucesión) de cada mantenedor activo, con fecha.

> **`@jfhelvetius`** — 2026-06-04
> Como `founder` único del proyecto, acepto las propiedades irrenunciables P1–P12 del ADR-0000, los siete límites operativos del ADR-0024, los cuatro sesgos declarados del ADR-0025 y los cinco compromisos del ADR-0026 como marco vinculante de mi rol. Reconozco que las auto-restricciones D3 aplican a mi propia capacidad de decisión mientras bus factor = 1. Reconozco públicamente los cinco riesgos del modelo de mantenedor único declarados en ADR-0026 y no prometo eliminarlos.
