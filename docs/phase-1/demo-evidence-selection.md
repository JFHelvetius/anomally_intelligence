# Pre-F1.C — Demo Evidence Selection

**Fecha:** 2026-06-04
**Estado:** Especificación pre-implementación
**Relacionado con:** ADR-0023, ADR-0006, ADR-0014 (limitado a fuente local en V1)

---

## Propósito

Definir el artefacto concreto que servirá como input de la demo de cierre de Fase 1. Sin un PDF identificado, los pasos restantes (Pre-F1.D, implementación, tests reproducibilidad) no pueden anclar sus valores canónicos.

Este documento **no** es un ADR. Es un acuerdo operativo sobre la elección del fixture de demo. Si cambia el documento elegido, este fichero se actualiza por PR y los valores canónicos en `tests/reproducibility/` se regeneran.

---

## Criterios de selección

El PDF debe satisfacer **todos** los criterios siguientes para ser admisible como fixture de demo. Los criterios reflejan las restricciones del ADR-0023 (V1 sin OSINT ni adquisidores) y del marco ético del ADR-0020.

### Criterio S1. Dominio público o licencia compatible

El documento debe estar en **dominio público** (preferido) o bajo licencia que permita su redistribución como fixture del repositorio bajo Apache 2.0.

Materiales producidos por funcionarios del gobierno federal de EE. UU. en el ejercicio de sus funciones están en dominio público (17 U.S.C. § 105). Los fondos de Project Blue Book conservados en NARA caen mayoritariamente en esta categoría.

### Criterio S2. Tamaño manejable

Tamaño del fichero entre **50 KB y 5 MB**. Justificación:

- **Mínimo 50 KB**: garantiza que el archivo no sea trivial; la demo debe operar sobre material representativo, no sobre un PDF de una sola página vacía.
- **Máximo 5 MB**: permite versionar el binario en el repositorio sin penalizar clones razonables. Por encima de 5 MB, conviene almacenamiento externo, lo que violaría P6 para la demo.

### Criterio S3. Sin testigos identificables vivos

El documento **no** debe contener:

- Nombres completos de testigos civiles cuyo consentimiento para uso académico contemporáneo no se pueda presumir.
- Datos personales sensibles (direcciones, números de identificación, datos médicos).
- Material con menores identificables en el momento del evento descrito.

Para Project Blue Book, esto se traduce en preferir:

- Documentos administrativos internos (memos, correspondencia inter-departamental).
- Análisis técnicos generales.
- Reportes de casos donde los testigos son **oficiales militares o civiles públicos** identificados en sus roles funcionales (no en su vida privada).
- Documentos sobre casos ampliamente publicados durante décadas en literatura abierta, donde la exposición adicional por demo es marginal.

### Criterio S4. Estabilidad pública sostenida

El documento debe estar disponible desde una fuente pública estable (NARA, Internet Archive, biblioteca académica) con **al menos cinco años de presencia continua**. Esto reduce riesgo de que el enlace muera en el horizonte de mantenimiento del ADR-0000.

### Criterio S5. Sin riesgo legal residual en jurisdicción del mantenedor

El mantenedor opera desde México. El documento no debe:

- Estar sujeto a restricciones de exportación específicas.
- Tener estatus de clasificación dudoso en su jurisdicción de origen (ver ADR-0020 política sobre material clasificado).
- Estar sujeto a litigio activo de privacidad o derechos.

Los documentos de Project Blue Book desclasificados públicamente y archivados en NARA satisfacen este criterio sin ambigüedad.

### Criterio S6. Verificabilidad independiente

Un revisor externo debe poder, sin asistencia del autor del proyecto:

1. Identificar el documento por su descripción canónica.
2. Localizarlo en su fuente estable.
3. Descargarlo y verificar que su SHA-256 coincide con el valor publicado.

Si la identificación o la localización requieren conocimiento privado del autor, el documento no es admisible.

### Criterio S7. Representatividad del modelo de evidencia

El documento debe permitir poblar de forma natural los campos canónicos del modelo `Evidence` (ADR-0006) y `Source` / `Provenance` (ADR-0005). Específicamente:

- Un `EvidenceKind` claro (en el caso de un escaneo: `document_scan`).
- Un `Source` identificable con autoridad declarable (`government_archive`, autoridad `secondary` típicamente para escaneos digitalizados de un original NARA).
- Una procedencia mínima con al menos un paso (`analog_to_digital` o equivalente).

Si el documento no permite poblar estos campos honestamente, no sirve como demo del modelo.

---

## Candidato primario

### Identidad canónica

**Memorandum del General Nathan F. Twining sobre "Flying Discs"**, dirigido al Brigadier General George Schulgen, fechado **23 de septiembre de 1947**, identificado en la literatura como **"Twining Memo"** o **AMC Opinion Concerning "Flying Discs"**.

### Por qué este documento

- **Dominio público**: documento de Air Materiel Command, Wright Field, producido por un oficial USG en ejercicio de funciones. Dominio público bajo 17 U.S.C. § 105.
- **Tamaño**: dos páginas, típicamente entre 100 y 500 KB como escaneo PDF a resolución estándar. Cumple S2.
- **Sin testigos privados**: documento administrativo interno militar. Solo nombra al General Twining (firmante) y al General Schulgen (destinatario), ambos figuras públicas identificadas en sus roles. Cumple S3.
- **Estabilidad pública sostenida**: documento liberado en los años 70 vía FOIA. Reproducido en libros académicos durante más de cinco décadas. Múltiples copias archivadas en NARA, Internet Archive, repositorios universitarios. Cumple S4.
- **Sin riesgo legal residual**: completamente desclasificado, ampliamente reproducido en literatura abierta. Cumple S5.
- **Verificabilidad**: cualquier interesado puede localizar el documento por su descripción canónica en bibliografía estándar del campo. Cumple S6.
- **Representatividad**: documento escaneado de original mecanografiado. Permite poblar `EvidenceKind=document_scan`, un `Source` de tipo `government_archive`, una procedencia mínima con `analog_to_digital`. Cumple S7.

### Atributos canónicos para el modelo

| Campo de `Evidence` (ADR-0006) | Valor propuesto |
|---|---|
| `kind` | `document_scan` |
| `mime_type` | `application/pdf` |
| `intrinsic_metadata.title_human` | `"AMC Opinion Concerning 'Flying Discs' (Twining Memo)"` |
| `intrinsic_metadata.date_authored` | `"1947-09-23"` |
| `temporal_anchor.expressed_as` | `"23 September 1947"` |
| `temporal_anchor.calendar` | `gregorian` |
| `temporal_anchor.precision` | día |
| `status` | `active` |
| `authentication.status` | `unverified` (default al ingestar; el documento está ampliamente referenciado pero V1 no implementa peritaje) |

| Campo de `Source` (ADR-0005) | Valor propuesto |
|---|---|
| `kind` | `government_archive` |
| `name` | `"NARA — Project Blue Book records"` |
| `authority` | `secondary` (escaneo derivado; el primario sería el documento mecanografiado original) |
| `jurisdiction` | `USA` |
| `access_conditions.license` | `public_domain` |

| Campo de `Provenance` (ADR-0005) | Valor propuesto |
|---|---|
| `origin_source_id` | referencia a la `Source` anterior |
| `steps[0].kind` | `original_capture` (documento mecanografiado original, autor Twining) |
| `steps[1].kind` | `analog_to_digital` (escaneo del original) |
| `steps[1].actor` | declarado como `unknown` o como NARA si la versión específica del PDF lo documenta |
| `is_complete` | `false` (admitimos que la cadena puede tener pasos intermedios no documentados) |
| `gaps` | uno declarado: "pasos intermedios entre original mecanografiado y escaneo digital actualmente disponibles no totalmente documentados" |

Estos valores son **propuestas para el momento de la implementación**, no compromisos rígidos. Cualquier ajuste se documenta cuando se implementen los tipos del modelo.

---

## Candidatos secundarios (fallback)

Si por cualquier razón el candidato primario deja de ser admisible (cambio en su disponibilidad pública, dudas sobre redistribución, etc.), los siguientes son fallbacks aceptables:

### Fallback F1. Project Blue Book — Special Report No. 14

Reporte estadístico de Battelle Memorial Institute publicado por la USAF en 1955. Dominio público USG. Tamaño mayor que Twining (~5 MB en algunas versiones; revisar contra S2). Documento técnico sin testigos privados.

### Fallback F2. Robertson Panel Report (1953, desclasificado)

Resumen del panel del CIA sobre el fenómeno. Dominio público USG. Texto sin testigos privados. Necesita verificación de la versión específica que cumpla S2.

### Fallback F3. Memorando individual de Blue Book sobre un caso ampliamente publicado

Memo de Blue Book sobre el caso de Mantell (1948) o McMinnville (1950). Eventos ampliamente documentados en literatura desde hace 70+ años; el testigo público es figura histórica. Verificar S3 con cuidado: el material debe ceñirse a aspectos públicos del caso, no a datos privados del testigo.

Cualquier fallback se documenta como sustitución en este fichero antes de regenerar valores canónicos.

---

## Procedimiento para publicación del SHA-256

Una vez seleccionada la versión exacta del PDF que servirá como fixture, el procedimiento de publicación de su hash es:

### Paso P1. Selección del fichero exacto

- Descargar el PDF desde la fuente pública estable.
- Verificar visualmente que el contenido coincide con la identidad canónica documentada.
- Anotar la URL exacta de descarga.
- Anotar la fecha de descarga.
- Anotar el tamaño en bytes.

### Paso P2. Cómputo del SHA-256

- Computar SHA-256 sobre los bytes del fichero crudo.
- En referencia: comando estándar como `sha256sum <fichero>` (Linux) o equivalente.
- Codificación: hexadecimal, **minúsculas**, longitud 64 caracteres.

### Paso P3. Anotación canónica en este documento

Añadir al pie de este fichero, en la sección "**Pinned values**":

```
## Pinned values

### Demo fixture (primary candidate)

- **Document:** Twining Memo (AMC Opinion Concerning "Flying Discs"), 1947-09-23
- **Source URL:** <URL exacta de descarga, anotada en el momento de la selección>
- **Download date:** <YYYY-MM-DD>
- **File size (bytes):** <N>
- **SHA-256 (hex, lowercase):** <hash>
- **MIME type:** application/pdf
- **Selected by:** <handle del mantenedor>
- **Selected at:** <YYYY-MM-DD>
```

Una vez anotado, este valor es **canónico**. Cualquier cambio futuro se registra como nueva entrada con motivo documentado, sin reescribir la anterior.

### Paso P4. Versionado del binario en `tests/data/`

- Copiar el PDF a `tests/data/twining-memo-1947-09-23.pdf` (o nombre canónico equivalente).
- Verificar que el hash del fichero versionado coincide con el hash pinned.
- Añadir entrada en `tests/data/README.md` describiendo el fichero, su procedencia, su licencia, y su uso (fixture de demo).
- Commit con mensaje explícito sobre la incorporación del fixture.

### Paso P5. Fijación de hashes derivados

Una vez el binario está en `tests/data/`, generar y fijar:

- `EXPECTED_PDF_SHA256` en `tests/reproducibility/manifest_hash_test.py`.
- `EXPECTED_MANIFEST_HASH` después de ejecutar el pipeline canónico una vez con código estable.
- Cualquier valor adicional que la suite de reproducibilidad necesite.

Estos valores son los que el ADR-0031 referencia como "canonical pinned values".

---

## Procedimiento de verificación independiente

Este procedimiento es lo que cualquier revisor externo ejecuta para confirmar la integridad del fixture. Es la operación que cierra parcialmente la demo F1.

### Paso V1. Acceso al documento canónico

El revisor:

1. Lee la sección "Pinned values" de este documento.
2. Localiza la URL fuente o, si la URL ha cambiado/expirado, localiza el documento por su descripción canónica en NARA o en repositorios académicos equivalentes.
3. Descarga el PDF.

### Paso V2. Verificación del SHA-256

El revisor computa SHA-256 sobre los bytes del fichero descargado. Compara contra el valor pinned en este documento.

**Resultado posible 1: coincidencia exacta.** El fichero descargado es bit-a-bit idéntico al fixture canónico. Verificación pasa.

**Resultado posible 2: no coincidencia.** El fichero descargado difiere del fixture canónico. Causas posibles:

- La fuente pública ha re-escaneado el documento (PDF distinto del original).
- El revisor ha descargado una versión derivada (con OCR posterior, con compresión distinta).
- El fixture canónico necesita actualización en el repositorio.

En el caso 2, el revisor reporta la discrepancia como issue. El issue dispara revisión del fixture canónico. Si la versión nueva sigue cumpliendo los criterios S1–S7, se actualiza por PR; si no, se mantiene la versión anterior y se documenta dónde encontrarla.

### Paso V3. Verificación contra `tests/data/`

Independientemente del paso V2, el revisor puede:

1. Clonar el repositorio AIP.
2. Computar SHA-256 sobre `tests/data/twining-memo-1947-09-23.pdf`.
3. Comparar contra el valor pinned.

Si el fichero versionado en el repo no coincide con el valor pinned, hay corrupción de repositorio o tampering. Es bug crítico.

---

## Lo que este documento NO decide

- **No** decide si la demo usa exclusivamente este PDF. Una versión futura puede expandir a múltiples PDFs cuando F2+ esté en alcance. Por ahora, **uno solo**.
- **No** decide cómo se distribuye el PDF si su tamaño excediera 5 MB en alguna versión nueva. Esa decisión requiere ADR si afecta a P6.
- **No** decide el formato del manifiesto de la demo más allá de los pinned values. Eso se cierra cuando Pre-F1.D defina el output exacto de `aip evidence show`.

---

## Pinned values

*(Esta sección se rellena cuando se ejecute el procedimiento P1–P3 contra una copia descargada concreta del documento. Mientras no se haya ejecutado, la sección queda explícitamente vacía. Sin pinned values, la implementación no puede empezar la fase F1 stricto sensu, porque los tests de reproducibilidad no tienen valor canónico contra el que comparar.)*

### Demo fixture (primary candidate)

- **Document:** Twining Memo (AMC Opinion Concerning "Flying Discs"), 1947-09-23
- **Source URL:** *(pendiente — se anotará al ejecutar P1)*
- **Download date:** *(pendiente)*
- **File size (bytes):** *(pendiente)*
- **SHA-256 (hex, lowercase):** *(pendiente)*
- **MIME type:** application/pdf
- **Selected by:** *(pendiente — `@jfhelvetius` cuando complete P1)*
- **Selected at:** *(pendiente)*

---

## Estado de este documento

- **Criterios definidos:** sí.
- **Candidato primario identificado:** sí (Twining Memo).
- **Candidatos secundarios identificados:** sí (tres fallbacks).
- **Procedimiento de publicación del SHA-256 definido:** sí.
- **Procedimiento de verificación independiente definido:** sí.
- **Pinned values rellenados:** **no** (acción operativa pendiente del mantenedor antes de cerrar Pre-F1).

**Bloqueante para inicio de implementación F1:** rellenar los pinned values siguiendo los pasos P1–P3 de este documento. Eso requiere acceso de red para descargar el PDF (acción puntual, no funcionalidad del proyecto).
