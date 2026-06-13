# ADR-0047: C2PA In-Process X.509 Verification

**Estado:** Aceptado
**Fecha:** 2026-06-12
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0024, ADR-0043, ADR-0045, ADR-0046

---

## Contexto

ADR-0046 introdujo la capa de atestación de captura (C2PA) en AIP, pero dejó un hueco de verificabilidad real explícito y honesto: el booleano `signature_info.chain_verified` del manifest JSON es **operator-supplied**. AIP lo lee y lo transporta tal cual.

Esto es un compromiso aceptable cuando la única tooling C2PA del operador (`c2patool`, `c2pa-python`) ya hizo la verificación X.509 en proceso y reporta su resultado. Pero crea una vulnerabilidad operacional clara:

- Un operador hostil que controla el JSON puede mentir poniendo `chain_verified: true` sin que ningún manifest C2PA real respalde esa afirmación.
- Un operador desinformado puede no haber corrido la verificación X.509 y poner `true` por defecto.
- Un fichero JSON corrupto en tránsito puede tener el booleano alterado sin que el resto del documento parezca sospechoso.

El receptor del reporte HTML lee "verified by C2PA against c2pa-default-trust-list-v1" y asume verificación real. La promesa rompe el modelo de honestidad de ADR-0024.

## Decisión

Implementar **verificación X.509 en proceso** dentro de AIP usando la librería `cryptography` (ya dependencia). El verificador walks la cadena de certificados — leaf → intermediate(s) → root — y comprueba cada eslabón:

1. **Signature**: la firma de cada cert verifica contra la clave pública del issuer (el siguiente cert hacia arriba).
2. **Validity**: la fecha actual está dentro de `[not_before, not_after]` de cada cert en la cadena.
3. **Trust anchor**: el root cert es uno de los root CAs declarados en la trust list que el operador suministra.

**Propiedad central:**

> AIP no confía en el booleano `chain_verified` operator-supplied. Cuando el operador suministra una trust list y el manifest JSON incluye los bytes de la cadena de certificados, AIP recomputa la verificación localmente y sustituye el booleano por su propio veredicto. Cuando falta cualquiera de los dos inputs, AIP reporta honestamente que **no pudo verificar en proceso** y preserva el valor operator-supplied tal cual, junto con una marca explícita.

Convierte la verificabilidad de la capa C2PA de **endo-cadena de tooling externa** (V1, ADR-0046) a **endo-AIP cuando hay inputs para hacerlo, honesta sobre las limitaciones cuando no** (post-0047).

## Modelo

```python
@dataclass(frozen=True)
class X509VerifyResult:
    """Resultado de verificar UNA cadena X.509 contra una trust list."""
    verified: bool
    used_chain: bool          # True if AIP walked the chain in-process
    reason: str | None        # Specific failure string, None on success
    trust_anchor_subject: str | None  # CN of the matched root, when verified


def verify_x509_chain(
    cert_chain_pem: list[str],   # leaf..root order
    *,
    trust_list_pem: str,         # one or more root CAs concatenated as PEM
    now: dt.datetime | None = None,
) -> X509VerifyResult:
    ...
```

Extensión del JSON del manifest:

```json
{
  "label": "camera-001",
  "signature_info": {
    "...": "...",
    "chain_verified": true,
    "cert_chain_pem": [
      "-----BEGIN CERTIFICATE-----\n... leaf ...\n-----END CERTIFICATE-----",
      "-----BEGIN CERTIFICATE-----\n... intermediate ...\n-----END CERTIFICATE-----",
      "-----BEGIN CERTIFICATE-----\n... root ...\n-----END CERTIFICATE-----"
    ]
  }
}
```

El campo `cert_chain_pem` es **opcional**. Sin él, AIP no puede hacer la verificación in-process; preserva `chain_verified` operator-supplied y lo marca como tal en el reporte.

## Algoritmo

### Verificación in-process per-manifest

1. Si `cert_chain_pem` está vacío o ausente → mantener `chain_verified` operator-supplied, marcar `verification_mode="operator-supplied"`. Sin cambio.
2. Si `cert_chain_pem` está presente Y la CLI recibió `--trust-list-pem`:
   - Parsear cada cert PEM con `cryptography.x509.load_pem_x509_certificate`.
   - Parsear la trust list PEM en `roots: list[Certificate]`.
   - Walk la cadena leaf→root:
     - Para cada par `(child, parent)`, verificar `child.signature` contra `parent.public_key()`.
     - Comprobar que `now ∈ [child.not_valid_before_utc, child.not_valid_after_utc]`.
   - El último cert de la cadena (root) debe estar en la trust list (matching por subject DN + serial number).
   - Si todo pasa → `chain_verified=True`, `verification_mode="in-process"`, `trust_anchor_subject=<root CN>`.
   - Si algo falla → `chain_verified=False`, `failure_reason=<specific message>`, `verification_mode="in-process"`.
3. Si `cert_chain_pem` está presente pero NO se pasó `--trust-list-pem`:
   - Tratar como caso (1) — preservar operator-supplied. Marcar `verification_mode="operator-supplied"` con nota: "cert chain provided but no trust list to verify against".

### Algoritmo de signature verification

Para certs ed25519:
```python
parent.public_key().verify(child.signature, child.tbs_certificate_bytes)
```

Para certs RSA / ECDSA: la librería `cryptography` provee `cert.verify_directly_issued_by(parent)` desde la versión 40+, que maneja todos los algoritmos correctamente. AIP usa esta API cuando está disponible.

### Lo que NO hace

- **CRL / OCSP**: AIP no consulta revocation lists ni OCSP responders. Una cert revocada que no ha pasado su `not_after` se considerará válida. ADR posterior si surge demanda (requiere red en proceso, lo que viola el modelo local-first por defecto).
- **Verificación de hostname / SAN**: irrelevante para C2PA donde el cert identifica al dispositivo, no a un servidor DNS.
- **Trust list updates**: AIP no actualiza la trust list por sí solo. El operador la suministra. Si C2PA rota una CA, el operador actualiza su trust list y vuelve a correr `aip evidence c2pa-verify`.
- **Path constraints exhaustivos**: AIP verifica las basic constraints (CA flag) y key usage suficiente para C2PA, pero no implementa el algoritmo PKIX completo de RFC 5280. Suficiente para el modelo de amenazas de v1; documentado.

## Surface

### CLI

`aip evidence c2pa-verify` gana un flag opcional:

```
--trust-list-pem <path>
```

Cuando se pasa, AIP carga el PEM bundle como roots de confianza y aplica el algoritmo arriba. Sin el flag, comportamiento V1 (operator-supplied booleano preservado).

El JSON de output gana un campo nuevo por manifest:

```json
"verification_mode": "in-process" | "operator-supplied" | "in-process-failed"
```

### Reporte HTML

El badge "verified by C2PA against \<trust list\>" se anota:
- Si `verification_mode == "in-process"`: "**verified in-process by AIP** against \<root CN\>"
- Si `verification_mode == "operator-supplied"`: "verified by external tooling (operator-supplied)"
- Si `verification_mode == "in-process-failed"`: "**FAILED in-process verification** — \<reason\>" (rojo prominente)

El contraste deliberado entre "in-process" (AIP lo computó) y "operator-supplied" (AIP transporta el verdict que vino en el JSON) es load-bearing: el receptor sabe inmediatamente quién hizo la verificación.

## Consecuencias

**Positivas**

- Cierra el hueco real "operator miente con el booleano". Cuando hay inputs suficientes, AIP no acepta la palabra del operador.
- 100% local. Ninguna conexión de red durante la verificación (CRL/OCSP intencionalmente excluidos del scope).
- Trust list es operator-supplied: AIP no impone qué CAs confiar. Mantiene la soberanía del receptor (que puede pasar una trust list distinta para auditar).
- Backward compatible: archives existentes sin `cert_chain_pem` siguen funcionando exactamente igual.

**Negativas**

- Sin CRL/OCSP, un cert revocado pero no expirado se considera válido. Documentado. Mitigación parcial: la trust list operator-supplied puede excluir CAs cuya revocación se conoce.
- AIP tiene que mantener la lógica X.509 de walk de cadena. Hay riesgo de bug. Tests exhaustivos requeridos.
- El JSON de manifest crece — un cert chain de 3 certs ed25519 añade ~1.5 KB. Aceptable.

**Neutras**

- La librería `cryptography` ya era dependencia (ADR-0041 para ed25519). Sin nuevo footprint.
- El operador debe explícitamente proveer la trust list. No hay default — porque ningún default es genuinamente neutro (C2PA-default tiene su propia política de gobierno). Documentado como decisión consciente.

## Alternativas consideradas

### A. Usar la API `PolicyBuilder` de `cryptography.x509.verification`
**Descripción:** Usar la API moderna de cryptography 42+ que hace path validation completo PKIX.
**Razón de aplazamiento (no rechazo):** La API requiere indicar `client_verifier` o `server_verifier` con DNS name / IP. C2PA no es un caso de TLS — el cert identifica un dispositivo. Adaptar la API requiere pasar valores ficticios que pueden romper en versiones futuras de la librería. La verificación manual de leaf→root es más robusta al contrato real de C2PA y no es complicada.

### B. Confiar siempre en el booleano operator-supplied
**Descripción:** Statu quo de ADR-0046.
**Razón de rechazo:** Hueco de verificabilidad real (descrito en el Contexto). El propio ADR-0046 lo declara como deferred trabajo, no como decisión final.

### C. Implementar CRL + OCSP en v1
**Descripción:** Hacer la verificación completa con revocation checks.
**Razón de rechazo:** Requiere conexión de red en proceso, lo que viola el modelo local-first y reintroduce el patrón "AIP fetchea por ti" que ADR-0045 acotó cuidadosamente. ADR posterior si llega demanda; el operador puede correr CRL externamente y excluir CAs revocadas de su trust list.

### D. Defaultear a la C2PA-default-trust-list-v1
**Descripción:** AIP empaqueta la trust list oficial de C2PA y la usa por defecto.
**Razón de rechazo:** Transfiere autoridad implícita a C2PA / Adobe. Si AIP por defecto confía en cualquier cert firmado por la C2PA root, AIP está endosando esa jerarquía PKI silenciosamente. Mejor: ningún default — el operador documenta su trust list explícitamente.

## Alineación con ADR-0000

ADR-0000 establece como propiedad irrenunciable que **el sistema debe ser honesto sobre lo que prueba**. Esta decisión la refuerza: cuando AIP puede verificar in-process, lo dice explícitamente ("**verified in-process by AIP**"). Cuando solo puede transportar el verdict operator-supplied, también lo dice explícitamente ("operator-supplied"). El receptor sabe en cada momento quién hizo la verificación.

Refuerza también la **soberanía del receptor** (ADR-0043, ADR-0045): el receptor inspecciona la trust list que se usó (operator-supplied) y decide si la acepta. AIP no decide por él.
