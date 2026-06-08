# ADR-0042: Archive State Snapshot V1

**Estado:** Aceptado
**Fecha:** 2026-06-08
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0016, ADR-0019, ADR-0030, ADR-0036, ADR-0041

---

## Contexto

Tras ADR-0041 (Operator Attestation Engine v1), ADR-0019 §enmienda E1 (audit chain archive-wide) y ADR-0030 §enmienda E16 (integrity audits attestations + reconciliation), el archive puede:

- Verificar internamente su integridad (blobs + manifest + audit chain + reconciliación disco↔log).
- Atestar criptográficamente artefactos individuales (workspace, timeline, snapshot, justification, context_bundle, manifest).

Pero **no** puede producir un único valor canónico que represente *"el archive como un todo en el momento T"*. Los dos hashes archive-wide existen pero viven separados:

- `archive_manifest_hash` pinea estado de tablas + blobs (el *qué*).
- `audit_log_head_hash` pinea historia hash-encadenada (el *cómo*).

Un operador que quiera comprometerse públicamente con el estado actual de su archivo, o atestar la combinación "esto es lo que hay + así es como llegamos aquí" en un único acto criptográfico, debe componer ambos hashes manualmente — protocolo no estandarizado.

**Vector de ataque dejado abierto antes de ADR-0042:** un operador hostil reconstruye un archive sintético con los mismos `(blobs, tablas)` pero historia distinta (audit log fabricado, distinto `audit_log_head_hash`), firma `manifest.json` con ADR-0041 (`artifact_kind="manifest"`), y la firma es válida contra una historia falsificada. La promesa central de la misión — *"demostrar que la información no fue alterada"* — descansa en que el verificador del tercero sepa componer manualmente los dos hashes.

## Decisión

Introducir `ArchiveSnapshot`, artefacto JCS-canónico que combina los dos hashes archive-wide existentes en un único valor atestable. Vive en `aip.audit.archive_state`. Read-only por construcción: no muta el archive.

**Propiedad central:**

> Un `ArchiveSnapshot` calculado sobre `(archive, generated_at)` es un **único valor canónico** que pinea simultáneamente (a) el estado actual de tablas+blobs vía `manifest_hash`, (b) la historia hash-encadenada vía `audit_log_head_hash`, y (c) la cardinalidad del log vía `audit_log_total_entries`. Es firmable via ADR-0041 con `artifact_kind="archive_snapshot"`. Cualquier mutación del archive (nueva ingesta, nueva entry derivada, tampering del log o las tablas) produce un `snapshot_hash` distinto.

No introduce nuevos subpaquetes ni nuevas dependencias. ADR-0041 ya soportaba 6 `ALLOWED_ARTIFACT_KINDS`; este ADR amplía a 7 añadiendo `archive_snapshot`. La maquinaria de firma/verificación es reutilización pura.

## Modelo

```python
ARCHIVE_SNAPSHOT_SCHEMA_VERSION: Final[str] = "1"

@dataclass(frozen=True)
class ArchiveSnapshot:
    manifest_hash: str                   # SHA-256 hex de ArchiveManifest
    audit_log_head_hash: str             # entry_hash de la última AuditEntry, o ZERO_HASH si vacío
    audit_log_total_entries: int         # cardinalidad de la cadena (>= 0)
    generated_at: str                    # ISO-8601 UTC operator-supplied (YYYY-MM-DDTHH:MM:SSZ)
    snapshot_hash: str                   # JCS self-hash exclude-self
    schema_version: str = "1"
```

Validadores regex en `__post_init__` (idéntico patrón a `OperatorAttestation`).

## Algoritmo

### Cálculo

1. Validar `generated_at` tz-aware UTC. Serializar a ISO-8601 con `microsecond=0` (ADR-0024 L2).
2. Leer `<archive>/manifest.json`, parsear como `ArchiveManifest`, computar `manifest_hash` via `ArchiveManifest.manifest_hash()`.
3. Recorrer `<archive>/audit.log` con `iter_entries`, extraer `entry_hash` de la última entry como `audit_log_head_hash` (o `ZERO_HASH` si el log no existe / está vacío). Contar `audit_log_total_entries`.
4. Construir un `ArchiveSnapshot` parcial con `snapshot_hash = "0" * 64`.
5. Recomputar `snapshot_hash = SHA-256(JCS(snapshot exclude snapshot_hash))`.
6. Devolver el snapshot final.

### Verificación

- **Estructural** (offline): `verify_archive_snapshot_hash(snap)` recomputa `snapshot_hash` y compara con el declarado.
- **Archive-wide** (requiere acceso al archive): recomputar via `compute_archive_snapshot(archive_root, generated_at=snap.generated_at)` y comparar campo a campo. Si difiere en cualquier campo, el archive ha cambiado respecto al snapshot.
- **Criptográfica** (offline con clave pública): si el snapshot está firmado via ADR-0041, `aip attestation verify <attestation.json> --public-key key.pub` verifica la firma sobre `snapshot_hash`.

## Persistencia

**Ninguna localización canónica en el archive.** ADR-0042 no introduce `<archive>/snapshots-archive/<id>.json` ni nada parecido. Un snapshot es un valor canónico, no estado del archive. El operador decide dónde guardarlo (`--output`, stdout, pipe a `attestation sign`, repositorio público, comunicado, etc.).

Esto es **intencional**: añadir persistencia canónica metería al snapshot en el grafo de reconciliación E16 y el snapshot dejaría de ser "lectura pura del archive". Manteniéndolo como valor efímero, el comando es trivialmente read-only y `archive_manifest_hash` permanece invariante.

## CLI

```sh
# Emitir snapshot a stdout (read-only)
aip archive snapshot --archive-root PATH --generated-at 2026-06-07T12:00:00Z

# Emitir a archivo además de stdout
aip archive snapshot --archive-root PATH --output snap.json

# Firmar via ADR-0041
aip attestation sign snap.json --private-key key.pem \
    --signer-id "@operator" --signed-at 2026-06-07T12:00:00Z \
    --output sig.json

# Verificar firma offline
aip attestation verify sig.json --public-key key.pub

# Verificación universal estructural
aip verify snap.json
```

`generated_at` opcional en el comando — si se omite, se usa el reloj actual del sistema (`datetime.now(UTC)`). El operador es responsable de decidir si necesita reproducibility bit-a-bit (inyectar `--generated-at` fijo) o sólo un compromiso temporal (usar el reloj).

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo: mismo `(archive, generated_at)` ⇒ mismo `snapshot_hash` | `test_compute_archive_snapshot_deterministic` |
| G2 | Sensibilidad: añadir audit entry cambia `snapshot_hash` | `test_snapshot_hash_changes_when_audit_log_grows` |
| G3 | Sensibilidad temporal: `generated_at` distinto ⇒ `snapshot_hash` distinto | `test_snapshot_hash_changes_when_generated_at_changes` |
| G4 | Read-only: el comando no muta el archive | `test_compute_is_read_only_archive_bit_identical` + `test_snapshot_is_read_only` |
| G5 | Encode/decode roundtrip bit-a-bit | `test_encode_decode_roundtrip` |
| G6 | Integración ADR-0041: firmable + atestación se invalida ante mutación | `test_archive_snapshot_is_signable_via_attestation_engine`, `test_attestation_invalidates_when_archive_state_changes` |
| G7 | Boundary con verify_chain: compute lee `entry_hash` declarado, no recomputa; tampering de payload se detecta por `verify_chain` upstream | `test_snapshot_boundary_with_chain_tampering` |

## Componentes excluidos

- **Sin persistencia canónica.** Por diseño (ver §Persistencia).
- **Sin verificación criptográfica integrada en el snapshot.** La firma se delega a ADR-0041 vía taxonomía. Mantener responsabilidades separadas.
- **Sin PKI / TSA.** Heredado de ADR-0041 §componentes excluidos.
- **Sin Merkle tree de derivados.** El snapshot pinea el `manifest_hash` (tablas+blobs) y el `audit_log_head_hash` (historia). Los derivados (workspace, timeline, etc.) están implícitamente cubiertos por el audit log: cada `BUILD_*` entry contiene `parameters["self_hash"]`. Reescribir un workspace.json sin re-emitir entry queda detectado por E16 reconciliation, no aquí.
- **Sin verificación archive-wide en el verificador universal.** `aip verify <snapshot.json>` hace verificación **estructural** (recomputa `snapshot_hash`). Verificar que el snapshot corresponde al estado actual del archive requiere `compute_archive_snapshot` con acceso al archive y comparación campo a campo — operación distinta, no incluida en V1.
- **Sin scoring, sin interpretación, sin IA.** Heredado de la postura general del proyecto.

## Reproducibilidad

`compute_archive_snapshot` es determinista respecto a `(archive_state, generated_at)`. La canonicalización es JCS estricta (mismas reglas que `ArchiveManifest`).

**No es state-pure**: el snapshot incluye `generated_at` operator-supplied, así que dos invocaciones a tiempos distintos sobre el mismo archive producen snapshots distintos. Eso es esperado (es un acto temporal de compromiso).

## Costes

**Cero nuevas dependencias.** Reutiliza `cryptography` indirectamente vía ADR-0041 (sólo si el operador decide firmar).

**Superficie de código mínima**: un módulo nuevo (~150 líneas), un valor añadido al frozenset `ALLOWED_ARTIFACT_KINDS`, una entrada en `_SELF_HASH_FIELD_BY_KIND`, un subcomando CLI (`aip archive snapshot`), una rama en el detector del verificador universal. Cero nuevos subpaquetes.

## Garantías arquitectónicas

| # | Verificación operativa |
|---|---|
| G1 | `test_compute_archive_snapshot_deterministic` |
| G2 | `test_snapshot_hash_changes_when_audit_log_grows` |
| G3 | `test_snapshot_hash_changes_when_generated_at_changes` |
| G4 | `test_compute_is_read_only_archive_bit_identical`, `test_snapshot_is_read_only` |
| G5 | `test_encode_decode_roundtrip`, `test_encoded_json_is_canonical_sorted` |
| G6 | `test_archive_snapshot_is_signable_via_attestation_engine`, `test_attestation_invalidates_when_archive_state_changes` |
| G7 | `test_snapshot_boundary_with_chain_tampering` |
| Universal verifier | `test_universal_verify_autodetects_archive_snapshot`, `test_universal_verify_detects_tampered_archive_snapshot` |
| Reproducibility pins | 16/16 manifest/JCS/context/justification + 2/2 audit chain base — intactos |

## Alineación ADR-0000

- **P2 (trazabilidad):** los dos hashes archive-wide existentes se unifican en un valor atestable, sin perder ninguno.
- **P5 (reproducibilidad):** los 16 pins de reproducibility y los 2 pins de audit chain base quedan invariantes (el snapshot no entra en ninguna canonicalización pinned).
- **P11 (inmutabilidad):** el comando es read-only por construcción; verificable bit-a-bit en tests.
- **P8 (documentación):** este ADR cubre la nueva primitiva. Honesty fields explícitos: no prueba veracidad, no prueba identidad real, no prueba momento absoluto.

**Tensión nueva:** ninguna fundamental. Es un primitivo aditivo que no toca bytes existentes.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
