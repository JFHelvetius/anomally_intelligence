# ADR-0044: Cross-Archive Divergence Detection

**Estado:** Aceptado
**Fecha:** 2026-06-10
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0003, ADR-0005, ADR-0019, ADR-0023, ADR-0024, ADR-0040, ADR-0041, ADR-0043

---

## Contexto

Hasta este punto AIP verifica integridad **dentro** de un archive: el audit chain enlaza con `prev_hash`, los manifests recomputan vía JCS, las firmas ed25519 atestan al firmante, las atestaciones de testigos validan acuerdo entre operadores que firman el mismo manifest. Todo es **consistencia interna**.

Hay un vector que esto no cierra: dos operadores independientes que ingestan **el mismo fichero** producen archives con cadenas internas distintas (sequence numbers, prev hashes, timestamps, firmas) — y eso es legítimo, cada uno mantiene su propio log. Pero si A dice "ingesté un PDF de 250022 bytes" y B dice "ingesté el mismo PDF (mismo SHA-256), 999999 bytes", uno de los dos miente sobre el contenido. Internamente ambos archives son consistentes; sólo cruzando los dos se ve el desacuerdo.

ADR-0023 mantiene la red de operadores fuera de scope V1, pero no rechaza la *verificación* cruzada entre archives existentes — es una operación local que cualquier receptor con acceso a dos archives puede ejecutar.

Sin una definición canónica de "qué campos son content-derived y deben coincidir, vs qué legítimamente diverge", la verificación cruzada queda al juicio de quien la implemente. Eso es ambigüedad inaceptable en código de confianza.

## Decisión

Introducir `src/aip/archive_compare/`, módulo de **comparación entre archives** que clasifica explícitamente cada campo como **must-match** (content-derived, divergencia indica tampering) o **may-differ** (per-operator, divergencia esperada). El módulo emite un :class:`CrossArchiveReport` que el CLI `aip diff archives` traduce a JSON + exit code.

**Propiedad central:**

> Cross-Archive Divergence Detection compara **artefactos con el mismo identificador de contenido** entre dos archives y reporta desacuerdo sólo en los campos cuyo valor está derivado del contenido. No declara cuál archive es correcto, no asume una autoridad arbitral, no fusiona estados. Sólo expone "estos dos operadores no están de acuerdo sobre estos hechos verificables".

Convierte la verificabilidad de **endo-archive** (un solo archive consistente consigo mismo) a **inter-archive** (dos archives consistentes con la misma realidad de contenido).

## Modelo

```python
CROSS_ARCHIVE_REPORT_SCHEMA_VERSION: Final[str] = "1"

# Campos content-derived que DEBEN coincidir si la evidencia es la misma.
# Cerrado v1; ampliar requiere ADR.
_CONTENT_DERIVED_PARAMS: frozenset[str] = frozenset({"size_bytes"})

@dataclass(frozen=True, slots=True)
class EvidenceDivergence:
    evidence_hash: str
    in_archive_a: bool
    in_archive_b: bool
    audit_params_a: dict[str, str]
    audit_params_b: dict[str, str]
    audit_params_match: bool | None         # None si falta en cualquier lado
    diverging_param_fields: tuple[str, ...]
    capture_cert_hash_a: str | None
    capture_cert_hash_b: str | None
    capture_cert_match: bool | None         # None si falta en cualquier lado

@dataclass(frozen=True, slots=True)
class ProofDivergence:
    proof_id: str
    target_justification_hash_a: str | None
    target_justification_hash_b: str | None
    proof_hash_a: str | None
    proof_hash_b: str | None
    in_archive_a: bool
    in_archive_b: bool

@dataclass(frozen=True, slots=True)
class CrossArchiveReport:
    archive_a_label: str
    archive_b_label: str
    shared_evidence: tuple[EvidenceDivergence, ...]
    a_only_evidence_hashes: tuple[str, ...]
    b_only_evidence_hashes: tuple[str, ...]
    shared_proofs: tuple[ProofDivergence, ...]
    a_only_proof_ids: tuple[str, ...]
    b_only_proof_ids: tuple[str, ...]
```

## Clasificación de campos

### Must-match (divergencia = tampering)

| Categoría             | Campo                           | Razón                                                                 |
|-----------------------|----------------------------------|-----------------------------------------------------------------------|
| Audit (ingest params) | `size_bytes`                    | Derivado del contenido del fichero. Mismatch implica que un operador miente sobre los bytes que ingestó. |
| Capture certificate   | `certificate_hash`              | JCS self-hash del cert. Mismatch implica re-emisión con contenido modificado. |
| Inference proof       | `proof_hash`                    | JCS self-hash de la DAG completa. Mismatch implica que la DAG fue editada en un archive sin re-derivar en el otro. |
| Inference proof       | `target_justification_hash`     | Identifica qué justification atesta el proof. Mismatch implica que el "mismo" proof_id atesta justifications diferentes. |

### May-differ (divergencia legítima)

| Categoría             | Campo                           | Razón                                                                 |
|-----------------------|----------------------------------|-----------------------------------------------------------------------|
| Audit                 | `seq`, `prev_hash`, `entry_hash`| Posición en la cadena. Cada archive numera independientemente.       |
| Audit                 | `timestamp`, `actor`            | Operator-supplied y per-archive. Dos operadores ingestan en momentos distintos. |
| Audit                 | `parameters` fuera de `_CONTENT_DERIVED_PARAMS` | Anotaciones operativas (e.g., source_id local) no derivadas del contenido. |
| Transparency manifest | Todo                            | Cadena de manifests es completamente per-archive (sequence, hashes, firmas). |
| Witness attestation   | Todo                            | Witnesses atestan manifests específicos de un archive concreto.       |
| OpenTimestamps proofs | Todo                            | Per-archive — el operador eligió cuándo notarizar.                    |
| Signing keys          | `public_key_fingerprint` del manifest signer | Cada operador firma con su propia clave. Diferir es lo normal. |

### Explícitamente fuera de scope

- **Veracidad de las premisas** — fuera de scope siempre (ADR-0024).
- **Acuerdo semántico entre proofs** — dos proofs distintos sobre la misma evidencia pueden razonar de manera distinta sin contradicción.
- **Identidad legal/civil del operador** — ADR-0043 (key declaration) lo cubre externamente; no es competencia de la comparación.

## Algoritmo

### Estrategia general

1. Cargar audit logs de A y B; extraer `{evidence_hash → ingest_parameters}` para cada uno.
2. `shared_hashes = hashes_a ∩ hashes_b`; el resto va a `a_only` / `b_only`.
3. Por cada `shared_hash`:
   - Comparar parámetros restringidos a `_CONTENT_DERIVED_PARAMS`. Si falta en ambos un campo, no es informativo (no se reporta).
   - Si ambos tienen capture cert para esa evidencia: comparar `certificate_hash`. Si sólo uno o ninguno tiene, `capture_cert_match = None`.
4. Construir `{proof_id → (target_justification_hash, proof_hash)}` para cada archive y aplicar la misma lógica.
5. `has_divergence = any(shared_evidence | shared_proofs).has_divergence`.

### Re-ingestión

Si un `evidence_hash` aparece más de una vez en el audit log (re-ingestión legítima con metadatos ampliados), la última ocurrencia gana. Esto pin-ea un comportamiento determinista; alternativas (warnar, fusionar) introducen ambigüedad sin valor claro.

### Reentrancia y orden

`compare_archives(A, B)` y `compare_archives(B, A)` producen reportes simétricos modulo etiquetas. Las listas `shared_*` mantienen orden lexicográfico por hash/id para determinismo.

## Consecuencias

**Positivas**

- Cierra un vector verificable que ninguna comprobación endo-archive puede detectar.
- 100% local y offline: el receptor con acceso a dos archives ejecuta `aip diff archives` sin red, sin tokens, sin dependencias externas.
- La clasificación de campos como must-match vs may-differ vive como `frozenset` cerrado en código + tabla en este ADR. Cambios requieren PR explícito.
- Reusable: el módulo es JSON-out, sin scoring; cualquier UI (CLI, futuro dashboard, scripts batch de auditoría) puede consumirlo.

**Negativas**

- Sólo detecta tampering, no lo prevé. Un operador hostil puede divergir y mantener sus dos archives separados; la comparación requiere que un tercero tenga acceso a ambos.
- `_CONTENT_DERIVED_PARAMS` v1 sólo contiene `size_bytes`. Si en futuras versiones añadimos otros campos derivados del contenido (MIME-as-detected, hash de cabecera PDF, etc.) hay que actualizar este set. El test suite lo pin-ea para evitar olvido silencioso.
- No compara firmas porque cada operador firma con su propia clave — un operador que falsifica el contenido pero firma honestamente con su propia clave queda detectado por la divergencia de hash, no por la firma. Esto es correcto pero no obvio.

**Neutras**

- El módulo no opina sobre cuál archive es correcto. Resolver disputas es responsabilidad del receptor — alineado con ADR-0024 (epistemic honesty).
- Re-ingestión usa "last write wins" — operacionalmente razonable, formalmente arbitrario. Si una investigación necesita historial completo de re-ingestas, ese es un módulo separado.

## Alternativas consideradas

### A. Comparación bit-a-bit de todo el archive
**Descripción:** `diff -r archive-a archive-b`; cualquier diferencia es divergencia.
**Razón de rechazo:** Genera falsos positivos masivos. Cada manifest tiene timestamps distintos, cada cadena tiene secuencias distintas, cada firma usa una clave distinta. Inútil para detectar tampering real.

### B. Comparación basada en manifestos firmados
**Descripción:** Pedir a ambos operadores que firmen un "joint manifest" describiendo la evidencia compartida, comparar firmas.
**Razón de rechazo:** Requiere coordinación entre operadores en línea, que es exactamente lo que ADR-0023 mantiene fuera de scope. La comparación cruzada debe funcionar sobre archives que existen ya, sin intervención de los operadores.

### C. Whitelist explícita en lugar de blacklist implícita
**Descripción:** Comparar TODOS los campos, salvo una lista declarada de "estos pueden diverger".
**Razón de rechazo:** Frágil: el día que se añade un campo nuevo (por ejemplo, en una v2 de manifest), automáticamente se compara y produce falsos positivos en archives v1+v2 mezclados. La estrategia adoptada (whitelist de must-match) es robusta a campos nuevos.

### D. No hacer nada y confiar en la blockchain
**Descripción:** Si ambos manifestos están OTS-anclados, ambos hashes existen en Bitcoin. Dejar al receptor que verifique allí.
**Razón de rechazo:** Bitcoin sólo prueba que ambos hashes existieron antes del bloque, no que sus contenidos coincidan. El tampering quirúrgico de `size_bytes` produce dos manifestos completamente diferentes, ambos válidamente anclados.

## Alineación con ADR-0000

ADR-0000 establece como propiedad irrenunciable que el sistema **detecte tampering, no lo asuma ausente**. Esta decisión cierra el último vector verificable de tampering: el desacuerdo silencioso entre operadores. Sin ella, dos archives internamente consistentes pueden mentir cada uno por su lado sin que nadie lo detecte; con ella, un tercero con acceso a ambos puede exponerlo en segundos.

Refuerza también la propiedad de **soberanía del receptor** (ADR-0043): la verificación cruzada no la hace una autoridad central — la hace cualquiera que tenga los dos archives en disco. AIP sólo provee el algoritmo y el formato del reporte.
