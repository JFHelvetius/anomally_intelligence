# Política de cumplimiento legal

**Estado:** Aceptado
**Fecha:** 2026-06-06
**Cadencia de revisión:** anual (próxima 2027-06-06), más reapertura automática ante triggers de §10.
**ADRs que lo exigen:**
- [`ADR-0019`](adr/0019-security-model.md) §"Cumplimiento legal": "La política de cumplimiento por jurisdicción se documenta en `docs/legal-compliance.md` y se actualiza con cadencia anual".
- [`ADR-0000`](adr/0000-long-term-vision.md) §"Cumplimiento legal de fuentes" (marco general).

---

## 1. Propósito

Define los **límites legales del proyecto AIP** y la **distribución de responsabilidades** entre el proyecto (mantenedores) y el operador (quien ejecuta una instancia local).

Existe para:

- Hacer explícito qué hace y qué no hace AIP desde el punto de vista de un revisor legal externo.
- Asignar inequívocamente las obligaciones de cumplimiento a quien las puede cumplir.
- Documentar las asunciones que AIP V1 hace sobre el material que ingesta.
- Servir de base honesta para futuras ampliaciones del alcance bajo nuevos ADRs.

## 2. Qué es AIP (desde la perspectiva legal)

### 2.1 Naturaleza del proyecto

- AIP es **software open source** distribuido bajo Apache License 2.0 ([`ADR-0022`](adr/0022-apache-license.md), reafirmado por [`ADR-0028`](adr/0028-license-reassessment.md)).
- El corpus de datos generado por el sistema, cuando exista, va bajo CC BY-SA 4.0 ([`ADR-0028`](adr/0028-license-reassessment.md)).
- AIP es **herramienta analítica de preservación de evidencia**, no canal de publicación ni servicio operacional.

### 2.2 Qué NO es

- AIP **no** opera servicios. No hay servidor mantenido por el proyecto; no hay endpoint público; no hay base de datos central.
- AIP **no** publica material. Cada operador ejecuta su propia instancia y administra lo que esa instancia ingesta.
- AIP **no** distribuye material clasificado. El proyecto incluye un fixture canónico (Twining Memo, 1947, dominio público USG bajo 17 U.S.C. § 105) exclusivamente para validar la cadena de evidencia. Ningún otro material binario está en el repositorio.
- AIP **no** ofrece garantías operacionales. El disclaimer del [`ADR-0000`](adr/0000-long-term-vision.md) §"Disclaimer operacional" sigue siendo el contrato vigente: los outputs son material analítico, no recomendaciones aplicables sin verificación independiente.

### 2.3 Disclaimer operacional (re-afirmado)

Repetido aquí literal porque es la frase que un revisor legal externo busca:

> *AIP no proporciona garantías operacionales para usos civiles, comerciales, gubernamentales o militares. Los outputs del sistema son material analítico, no recomendaciones aplicables sin verificación independiente. Cualquier uso aplicado es responsabilidad exclusiva del usuario.* — [`ADR-0000`](adr/0000-long-term-vision.md)

## 3. Responsabilidad del operador

### 3.1 Quién es el operador

El **operador** es la persona o entidad que:

- Instala el paquete `aip`.
- Crea o mantiene un archive AIP en su propia infraestructura (filesystem local, NAS, almacenamiento corporativo, etc.).
- Decide qué material ingestar.

El operador **es** el responsable jurídico de su instancia. El proyecto **no es** operador de las instancias que terceros ejecutan.

### 3.2 Obligaciones que asume el operador

- **Jurisdicción.** El operador opera bajo las leyes del lugar donde corre la instancia AIP. Esas leyes pueden variar respecto a copyright, protección de datos personales, material clasificado, retención documental, exportación de información, etc. El proyecto no clasifica esas leyes ni asesora sobre ellas.
- **Decisiones de ingesta.** El operador decide caso por caso si el material que ingesta es legal para él. Si el operador tiene dudas reales sobre un caso concreto, debe consultar a un abogado de su jurisdicción **antes** de ingestar. AIP provee procedimiento (ver [`docs/ethics-procedures/classified-material.md`](ethics-procedures/classified-material.md)) pero no provee asesoría.
- **Distribución del archive.** Si el operador comparte snapshots de su archive con terceros, asume responsabilidad sobre los términos de licencia del material incluido. Material en dominio público (como el fixture del proyecto) puede compartirse libremente; material con licencia restrictiva no.
- **Datos personales.** Cualquier obligación derivada de GDPR (UE), LFPDPPP (México), CCPA (California), LGPD (Brasil) o equivalentes recae sobre el operador.

### 3.3 Obligaciones del proyecto (mantenedores)

Los mantenedores del proyecto, sobre el código y los artefactos en este repositorio, asumen:

- **Cumplimiento de la licencia** de las dependencias open source (preservar avisos, no relicenciar de forma incompatible).
- **Cumplimiento de los términos del fixture canónico:** material en dominio público USG, atribución en `tests/data/README.md` y en [`docs/phase-1/demo-evidence-selection.md`](phase-1/demo-evidence-selection.md).
- **Sin obligaciones contractuales** con usuarios. No hay SLA (MAINTAINERS.md §"Política explícita de no-SLA").

## 4. Asunción de material público en V1

### 4.1 La asunción

**V1 ingesta exclusivamente material en dominio público o licencia que permite redistribución académica/abierta.** Esta asunción está respaldada por:

- El único fixture binario versionado del proyecto (Twining Memo, 1947) es dominio público USG bajo 17 U.S.C. § 105.
- V1 no incluye adquisidores de red ([`ADR-0014`](adr/0014-osint-strategy.md) diferido por [`ADR-0023`](adr/0023-scope-reduction.md)). La única vía de ingesta es `aip evidence ingest <path>` sobre material ya local del operador.
- V1 no incluye enclave para material sensible ([`ADR-0019`](adr/0019-security-model.md) §enclave diferido por [`ADR-0023`](adr/0023-scope-reduction.md)).
- V1 no incluye material relativo a testigos vivos identificables. El fixture canónico tiene 79 años y sus actores (General Twining, General Schulgen) son figuras históricas públicas fallecidas.

### 4.2 Lo que implica la asunción

Como consecuencia operativa:

- GDPR, LFPDPPP, CCPA y leyes equivalentes de protección de datos personales **no aplican al uso de V1 sobre material como el fixture canónico**. No hay sujetos vivos cuyos datos se procesen.
- La doctrina del "uso legítimo" / "fair use" / "uso transformativo" cubre la ingesta del fixture en cualquier jurisdicción razonable.
- El operador que respete §4.1 (solo material público) opera dentro del alcance asumido por el proyecto.

### 4.3 Cualquier desviación es responsabilidad del operador

Si un operador decide ingestar material **fuera de §4.1** (material con copyright vigente, material con personas vivas, material clasificado, material adquirido sin consentimiento, etc.):

- Esa decisión queda fuera del alcance asumido por el proyecto.
- El operador debe consultar a su asesoría legal antes de hacerlo.
- El proyecto no le garantiza que el sistema sea apto para ese caso de uso (las propiedades P12 do-no-harm y P9 fuentes públicas asumen el modelo operativo de §4.1).

## 5. Procedencia y términos de servicio externos

V1 no hace adquisición online. No hay scrapers, no hay clientes HTTP, no hay queries a APIs externas durante la operación del sistema.

La única red que ha tocado el proyecto en V1 es la descarga puntual del Twining Memo desde Internet Archive (operación manual del mantenedor con `scripts/fetch_demo_fixture.py`, fuera del runtime del paquete `aip`). Esa descarga respetó los términos de servicio de archive.org (acceso público, sin scraping masivo, sin bypass de mecanismos de acceso).

Cuando se levante [`ADR-0014`](adr/0014-osint-strategy.md) y existan adquisidores OSINT en `aip.osint`, esta sección se amplía para cubrir:

- Cumplimiento por adquisidor de los términos de servicio de cada fuente.
- Manejo de robots.txt y rate limits.
- Bases legales declaradas (`public_domain` / `permissive_license` / `tos_compliant_use` / `fair_use_research` / `mixed_per_item`).
- Política sobre jurisdicción del operador al usar adquisidores que tocan fuentes de jurisdicciones distintas.

Hasta entonces: no aplica en V1.

## 6. Datos personales

### 6.1 Estado en V1

V1 no procesa datos personales de personas vivas. El fixture canónico precede al GDPR en 71 años; los individuos nombrados están fallecidos.

### 6.2 Estado futuro

Si en el futuro se levanta el enclave de [`ADR-0019`](adr/0019-security-model.md) o la sección de takedown del [`ADR-0020`](adr/0020-ethics-framework.md), aplicarán las obligaciones de protección de datos personales conforme a la jurisdicción del operador. Este documento se actualizará para reflejar:

- Quién es controller y processor en el modelo distribuido de AIP (probablemente: el operador es controller; el proyecto no es processor porque no opera servicios).
- Cómo se ejecuta operacionalmente el derecho al olvido sin violar P11 (inmutabilidad de evidencia raw).
- Política sobre menores identificables y comunidades indígenas (ADR-0020 ya las define a nivel de política; el cumplimiento operativo se documentará aquí).

Hasta que esos ADRs se levanten: V1 opera bajo §4.1 y los datos personales no son superficie del problema.

## 7. Exportaciones y restricciones de doble uso

V1 no contiene:

- Algoritmos criptográficos propios (usa `hashlib.sha256` de la stdlib de Python, sin novedad).
- Capacidad ofensiva (no es malware, no es framework de pentesting, no es ataque a sistemas de terceros).
- Información sujeta a controles de exportación EAR / ITAR / Wassenaar Arrangement.

Apache License 2.0 es compatible con distribución internacional bajo regímenes de exportación estándar. El proyecto se distribuye desde GitHub (US-hosted) y no impone restricciones geográficas, dejando la decisión al usuario en su jurisdicción.

## 8. Material del proyecto (no del operador) cubierto

Esta política cubre, en su totalidad:

- El código fuente bajo `src/aip/`.
- Los tests bajo `tests/`.
- La documentación bajo `docs/` y `MAINTAINERS.md`, `README.md`, `PROJECT_STATUS.md`.
- El fixture canónico `tests/data/twining-memo-1947-09-23.pdf`.
- Los scripts auxiliares bajo `scripts/`.
- La configuración de CI bajo `.github/`.

No cubre instancias operadas por terceros, sus archives, ni el material que esos archives contengan.

## 9. Lo que este documento NO hace

- ❌ **No es asesoría legal.** Para cualquier caso concreto, el operador debe consultar a un abogado de su jurisdicción.
- ❌ **No cubre obligaciones específicas por jurisdicción.** El proyecto no clasifica leyes locales; eso supera la capacidad de mantenimiento bajo bus factor = 1 ([`ADR-0026`](adr/0026-sustainable-stewardship.md)).
- ❌ **No exime al operador** de su responsabilidad jurídica sobre la instancia que ejecuta.
- ❌ **No habilita** uso de AIP fuera del alcance asumido en §4.1 sin que el operador asuma responsabilidad explícita.
- ❌ **No protege** al proyecto de jurisdicciones cuyas leyes el proyecto desconoce; opera bajo el principio de buena fe y compromiso de revisión anual.

## 10. Triggers de revisión

Este documento se revisa:

- **Anualmente.** Próxima revisión calendárica: 2027-06-06.
- **Cuando se apruebe el ADR de levantamiento de [`ADR-0014`](adr/0014-osint-strategy.md).** Las obligaciones sobre términos de servicio externos cambian sustancialmente.
- **Cuando se apruebe el ADR de levantamiento del enclave de [`ADR-0019`](adr/0019-security-model.md).** Las obligaciones sobre datos personales entran en alcance.
- **Cuando se materialice un incidente o consulta legal** que el documento no cubra claramente. La aclaración entra por PR y queda registrada en el historial al pie.

## 11. Alineación con las cuatro garantías

| Garantía | Estado tras este documento |
|---|---|
| **Provenance** | **intacta** — el documento no toca `Source`, `Provenance`, ni adquisidores. |
| **Evidence integrity** | **intacta** — no toca CAOS, hashes, ni validadores. |
| **Reproducibility** | **intacta** — no toca canonicalización ni manifest. |
| **Hash stability** | **intacta** — ningún `EXPECTED_*` ni schema_hash se ve afectado. |

---

## Historial

| Fecha | Cambio |
|---|---|
| 2026-06-06 | Publicación inicial bajo track A de mantenimiento. Refleja el estado de V1 / `v0.1.0`. |
