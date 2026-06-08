# ADR-0041: Operator Attestation Engine V1

**Estado:** Aceptado
**Fecha:** 2026-06-07
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0019, ADR-0024, ADR-0029, ADR-0030, ADR-0031, ADR-0036, ADR-0037, ADR-0038, ADR-0039, ADR-0040

---

## Contexto

Tras P1–P5, el archive **detecta** todos los vectores de tampering internos conocidos. Pero el modelo de confianza es **endógeno**: la única entidad que certifica la integridad es el propio archive. Un operador hostil podría producir un archive completamente sintético con hashes internos consistentes y reclamar "este es el archive real". Hoy nada lo desmiente externamente.

La pregunta central de la misión — *"¿qué evidencia existe realmente y cómo podemos demostrar que no ha sido alterada?"* — sigue dependiendo, en último término, de la palabra del operador.

## Decisión

Introducir `src/aip/attestation/`, capa de **atestación criptográfica** que permite a un operador firmar artefactos verificables con su clave privada ed25519. Cualquier tercero con la clave pública puede verificar la firma offline, sin acceso al archive.

**Propiedad central:**

> Operator Attestation **vincula un artefacto a una clave criptográfica controlada por un operador**. La firma demuestra que el titular de la clave privada vio y avaló el contenido exacto del artefacto. **No** prueba la identidad real del firmante (PKI fuera de scope V1). **No** prueba el momento absoluto de la firma (sin timestamping authority). **No** prueba la veracidad del contenido. Sólo prueba el vínculo clave-artefacto.

Convierte la verificación de **endógena** (auto-consistente) a **exógena** (verificable contra una clave externa).

## Modelo

```python
ATTESTATION_SCHEMA_VERSION: Final[str] = "1"
SIGNATURE_ALGORITHM: Final[str] = "ed25519-v1"

ALLOWED_ARTIFACT_KINDS: frozenset[str] = frozenset({
    "workspace", "timeline", "snapshot", "justification",
    "context_bundle", "manifest",
})

@dataclass(frozen=True)
class OperatorAttestation:
    artifact_kind: str
    artifact_hash: str               # SHA-256 hex del self-hash del artefacto firmado
    signer_id: str                   # string operator-supplied (no autenticado por sí mismo)
    public_key_fingerprint: str      # SHA-256 hex del DER public key
    signature: str                   # ed25519 signature hex (128 chars)
    signature_algorithm: str         # cerrado a "ed25519-v1" en V1
    signed_at: str                   # ISO-8601 UTC operator-supplied
    attestation_hash: str            # JCS self-hash excluding self
    schema_version: str = ATTESTATION_SCHEMA_VERSION
```

## Algoritmo

### Firma

1. Operador provee: `private_key.pem` (ed25519 PEM), `signer_id`, `signed_at`, ruta al artefacto.
2. Sistema lee el artefacto, extrae su self-hash (`workspace_hash`, `timeline_hash`, etc.).
3. Computa `public_key_fingerprint = SHA-256(public_key_DER_bytes)`.
4. Construye el "bytes to sign" canónico:
   ```
   payload = JCS({
     "artifact_kind": ...,
     "artifact_hash": ...,
     "signer_id": ...,
     "public_key_fingerprint": ...,
     "signature_algorithm": "ed25519-v1",
     "signed_at": ...,
     "schema_version": "1",
   })
   ```
5. Firma con ed25519: `signature = sign(private_key, payload)`.
6. Construye `OperatorAttestation` con todos los campos + `attestation_hash` JCS self-hash exclude-self.

### Verificación

1. Lee `OperatorAttestation` JSON.
2. Reconstituye `payload` canónico desde los campos.
3. Si se proveyó `public_key.pem`: verifica `SHA-256(public_key_DER) == public_key_fingerprint`.
4. `verify(public_key, payload, signature)` — ed25519 crypto check.
5. Recomputa `attestation_hash` y compara con el declarado.

Si la clave pública no se provee, sólo se recomputa `attestation_hash` (verificación estructural). Para verificación criptográfica completa se requiere la clave pública del firmante.

## Persistencia

`<archive>/attestations/<attestation_id>.json`. Periférico — no entra en `V1_TABLES`. `archive_manifest_hash` invariante.

## Garantías

| # | Garantía | Verificación |
|---|---|---|
| G1 | Determinismo del JCS canonical bytes a firmar | mismo input ⇒ mismo payload bytes |
| G2 | Verificabilidad offline criptográfica | `verify_attestation` sólo necesita el JSON + clave pública |
| G3 | Vínculo verificable artefacto ↔ firmante | tampering del artefacto ⇒ `artifact_hash` no coincide; tampering de la firma ⇒ ed25519 falla |
| G4 | Cero alteración del archive base | atestaciones en directorio periférico |
| G5 | Backward compat total | firma opt-in; flujos previos intactos |
| G6 | Sin interpretación | sólo primitivas criptográficas; cero scoring |
| G7 | Roll-our-own crypto prohibido | usa `cryptography` library auditada |

## Componentes excluidos

- **Sin PKI (Public Key Infrastructure):** el `signer_id` es operator-supplied; verificar identidad real está fuera de scope V1. Operadores publican claves por sus canales (web, repos, etc.).
- **Sin Timestamping Authority (TSA):** `signed_at` es operator-supplied; un firmante puede backdate. Mitigación: el valor está en la cadena de atestaciones, no en el tiempo absoluto.
- **Sin rotación automática de claves.**
- **Sin cifrado de contenido:** las atestaciones firman hashes, no payloads. Los artefactos siguen siendo claros.
- **Sin secrets management:** las claves privadas son responsabilidad del operador.
- Cero IA, NLP, embeddings, ML, scoring, ranking, recomendaciones.

## CLI

```sh
# Generar par de claves (helper conveniencia — equivalente a openssl)
aip attestation keygen --output-private key.pem --output-public key.pub

# Firmar artefacto
aip attestation sign <artifact.json> \
    --private-key key.pem \
    --signer-id "@operator" \
    --signed-at 2026-06-07T12:00:00Z \
    [--archive PATH]  [--attestation-id ID]  [--output sig.json]

# Verificar firma offline (sin archive)
aip attestation verify <attestation.json> [--public-key key.pub]

# Listar / mostrar atestaciones persistidas
aip attestation show <attestation_id> --archive PATH
```

`aip verify <attestation.json>` (universal verifier) auto-detecta y delega.

## Reproducibilidad

El payload-a-firmar es JCS canónico y determinista. Mismo input ⇒ misma firma siempre que el firmante use la misma clave privada (ed25519 es determinista — característica del algoritmo).

`signed_at` se inyecta por el operador, así que NO es state-pure: la atestación incluye tiempo. Eso es esperado (la atestación es un acto temporal).

## Costes y mitigaciones

**Nueva dependencia:** `cryptography>=42,<46`.

Justificación: la atestación criptográfica es load-bearing para la misión ("demostrar que la información no ha sido alterada"). Rolling-our-own ed25519 es un anti-patrón de seguridad. `cryptography` es el estándar de facto en Python — mantenido por la PSF y la Open Tech Fund, wheels pre-construidos en Linux/macOS/Windows para Python 3.11/3.12, audit-friendly, ~5 MB de install.

**Mitigación de version-pinning:** rango `>=42,<46` cubre cuatro major versions, suficiente para 12+ meses de estabilidad. `uv.lock` pinea bit a bit.

## Garantías arquitectónicas

| # | Verificación operativa |
|---|---|
| G1 | `test_signed_payload_is_deterministic` — mismo artefacto + misma clave ⇒ misma firma |
| G2 | `test_verify_attestation_offline_with_public_key` |
| G3 | `test_tampered_artifact_invalidates_signature`, `test_tampered_signature_fails_verify` |
| G4 | `test_attestation_persistence_does_not_modify_manifest` |
| G5 | `test_existing_pipeline_unaffected_by_attestation_module` |
| G6 | `test_no_prohibited_tokens_in_attestation_module` (30+ tokens) |
| G7 | `test_attestation_imports_only_cryptography_for_crypto` (AST) |

## Alineación ADR-0000

P2 (trazabilidad) reforzada con vínculo criptográfico. P5 (reproducibilidad) preservada para el payload canónico. P8 (documentación) cubierta por este ADR + honesty fields obligatorios en el modelo. P11 (inmutabilidad) preservada — atestaciones nunca modifican el artefacto firmado.

**Tensión nueva:** ninguna fundamental. ADR-0023 §congelación no aplica (esto es hardening, no nuevo dominio analítico).

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
