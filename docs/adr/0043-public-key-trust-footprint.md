# ADR-0043: Public-Key Trust Footprint (Key Declaration v1)

**Estado:** Aceptado
**Fecha:** 2026-06-10
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0019, ADR-0023, ADR-0024, ADR-0029, ADR-0030, ADR-0041

---

## Contexto

Tras ADR-0041 (Operator Attestation) y las extensiones posteriores que llevaron firmas ed25519 a manifests de transparencia, certificados de captura y atestaciones de testigos, el reporte standalone HTML puede recomputar **client-side** todas las firmas y hashes embebidos. Cualquier receptor con un navegador moderno verifica sin backend que el archive es internamente consistente.

Queda un hueco de verificabilidad: el reporte embebe las claves públicas (operador y testigos), pero el receptor **no tiene forma de saber si esas claves son las que dice el reporte que son**. Un operador hostil podría generar un keypair fresco, firmar todo, y el reporte se auto-validaría. Las firmas son matemáticamente correctas; la vinculación clave-identidad es asertada, no probada.

El propio ADR-0041 lo declara explícito:

> No prueba la identidad real del firmante (PKI fuera de scope V1).

ADR-0023 mantiene PKI/CA chain fuera de scope. Necesitamos cerrar el hueco sin reintroducir una autoridad central.

## Decisión

Introducir `transparency/key-declaration.json`, un artefacto **opcional, declarativo y operator-supplied** donde el operador enumera los canales externos donde publica cada clave pública (la suya y la de cada testigo). El receptor cierra la vinculación clave-identidad cruzando manualmente al menos una de esas referencias contra una fuente independiente que ya confíe.

**Propiedad central:**

> Key Declaration **no** prueba quién es el operador. Provee un **mapa replicable** de dónde buscar la misma clave en canales externos independientes, de manera que el receptor pueda decidir con criterio propio si la coincidencia es suficiente para creer en la vinculación. El sistema no certifica las referencias — sólo las transporta tal como las declara el operador.

Convierte la verificación de identidad de **ausente** (V1 pre-0043) a **operador-publicada, receptor-validada** (post-0043). El AIP no se vuelve PKI; el receptor se convierte en su propia autoridad de validación.

## Modelo

```python
KEY_DECLARATION_TYPE: Final[str] = "aip.transparency.key-declaration.v1"
KEY_DECLARATION_FILENAME: Final[str] = "key-declaration.json"

# Vocabulario abierto. Los receptores deben tolerar kinds desconocidos
# (pasar a través). Documentar los kinds comunes facilita interoperabilidad.
COMMON_REFERENCE_KINDS: frozenset[str] = frozenset({
    "github_user_keys",   # https://github.com/<user>.keys (SSH-formato)
    "https_pem",          # URL HTTPS que sirve la pubkey en PEM
    "dns_txt",            # TXT record DNS con el fingerprint hex
    "git_signing_key",    # repo público con la clave en git history
    "verbal_in_person",   # comunicación humana directa (puede ser válida)
})

@dataclass(frozen=True)
class ExternalReference:
    kind: str             # de COMMON_REFERENCE_KINDS o custom (opaque)
    uri: str              # URI/locator dependiente del kind
    note: str | None      # operator-supplied; instrucciones de verificación

@dataclass(frozen=True)
class KeyEntry:
    public_key_fingerprint: str  # SHA-256 hex del DER public key
    external_references: tuple[ExternalReference, ...]

@dataclass(frozen=True)
class OperatorKeyEntry(KeyEntry):
    operator_id: str
    first_published_at: str | None  # ISO-8601 UTC, operator-supplied

@dataclass(frozen=True)
class WitnessKeyEntry(KeyEntry):
    witness_operator_id: str

@dataclass(frozen=True)
class KeyDeclaration:
    declaration_type: str
    schema_version: str
    operator: OperatorKeyEntry
    witnesses: tuple[WitnessKeyEntry, ...]
```

## Algoritmo

### Producción

1. Operador genera (manualmente o, en futuro, via `aip transparency declare-key`) el archivo JSON.
2. Lo deposita en `<archive>/transparency/key-declaration.json`.
3. **Publica externamente** cada `uri` declarada (e.g., commit a `~/.ssh/authorized_keys` en GitHub, despliega `.well-known/aip-public-key.pem` en HTTPS, añade TXT record DNS).
4. La declaration **no se firma**. Su confianza viene del cruce externo, no de la firma interna.

### Consumo (receptor)

1. Reporte HTML embebe la declaration completa en `data.key_declaration`.
2. Receptor lee la sección "Signer trust footprint" del reporte.
3. Para cada clave que le importe verificar:
   - Elige al menos una referencia externa.
   - Recupera la clave de esa fuente por su propio canal (no via el HTML).
   - Calcula `SHA-256(DER pubkey)` y compara con el `public_key_fingerprint` declarado.
4. Si coincide en al menos un canal independiente que el receptor confía, considera vinculada la identidad-clave.

### Consistencia interna mínima

El builder del reporte verifica que cada `witness_operator_id` declarado tenga su `.pem` correspondiente en `transparency/witness-keys/<fingerprint>.pem`. Si no, surface un warning visible. Esto detecta declarations corruptas o desincronizadas; no añade confianza.

## Consecuencias

**Positivas**

- Cierra el último eslabón de verificabilidad del reporte standalone sin añadir backend ni PKI.
- Opt-in puro: archives sin declaration siguen funcionando exactamente igual; el HTML muestra una advertencia honesta en lugar de inventarse confianza.
- Vocabulario de `kind` abierto: operadores pueden declarar canales no anticipados (Keybase, atestaciones notariales, Twitter pinned tweet) sin requerir cambios al schema.
- El receptor es soberano: elige qué canales acepta y qué umbral de evidencia exige.

**Negativas**

- La declaration **es** operator-supplied. Un operador puede publicar referencias falsas (URIs que no existen, TXT records inventados). El sistema no lo detecta; el receptor lo descubre cuando intenta seguirlas. Es honesto: el AIP nunca afirma haber verificado las referencias.
- Receptores perezosos podrían ver "External references (3)" y asumir verificación sin cruzar ninguna. Mitigado por el copy explícito de la sección ("Cross-check at least one external reference per key").
- Schema v1 no firma la declaration. Un atacante que sustituya el archivo en tránsito puede inyectar URIs maliciosas. Mitigado por que el receptor cruza contra su propio canal de confianza, no contra las URIs declaradas.

**Neutras**

- El operador tiene una carga operacional nueva: mantener al día las publicaciones externas. Si una URL deja de servir la pubkey, los receptores futuros no podrán verificar por ese canal. Esperado.
- Witnesses pueden declarar sus propias referencias dentro del bloque `witnesses[]`. Esto facilita que un operador publique en nombre de testigos que no participan en el deploy del archive.

## Alternativas consideradas

### A. PKI clásica con CA jerárquica
**Descripción:** Emitir certificados X.509 firmados por una CA root para cada operador y testigo.
**Razón de rechazo:** Reintroduce una autoridad central que ADR-0023 excluyó deliberadamente. Crea single point of failure y dependencia de continuidad institucional. El receptor termina confiando en la CA en lugar de en evidencia.

### B. Web of trust (PGP-style)
**Descripción:** Operadores se firman mutuamente las claves; el receptor sigue cadenas de confianza.
**Razón de rechazo:** Funciona en comunidades de alta densidad social; falla en investigación periodística donde un periodista puede ser el primer receptor jamás. Schema complicado para utilidad limitada.

### C. Blockchain-anchored key registry
**Descripción:** Anclar cada fingerprint a una transacción Bitcoin/Ethereum vía OpenTimestamps extendido.
**Razón de rechazo:** Prueba existencia temporal de la clave, no vinculación a identidad. La identidad sigue siendo asertada. Añade fricción operativa significativa sin cerrar el hueco real.

### D. No hacer nada
**Descripción:** Dejar el hueco documentado en el reporte y confiar en que el receptor entienda la limitación.
**Razón de rechazo:** Inaceptable. El reporte muestra checkmarks verdes en todas las firmas; el receptor razonable concluye "está verificado". Sin declaration, "verificado" significa "matemáticamente consistente pero clave-identidad no probada" — una distinción que sólo es legible para criptógrafos.

## Alineación con ADR-0000

ADR-0000 establece como propiedad irrenunciable que el sistema sea **honesto sobre lo que no puede probar**. La declaration es exactamente eso: superficie un hueco que la crypto no cierra, lo nombra, y ofrece un camino de cierre que **no compromete** el resto del modelo (no añade backend, no añade autoridad, no añade dependencia).

Refuerza también la propiedad de **soberanía del receptor**: el AIP no decide qué canales son válidos; el receptor decide. El sistema sólo se compromete a transportar las referencias declaradas con fidelidad y a no inventar confianza donde no la hay.
