# ADR-0045: Trust Footprint Cross-Verification

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0023, ADR-0024, ADR-0041, ADR-0043

---

## Contexto

ADR-0043 introdujo el **trust footprint**: un fichero `key-declaration.json` donde el operador enumera dónde publica externamente su clave pública. El receptor cierra la vinculación clave-identidad cruzando manualmente al menos una de esas referencias contra una fuente independiente.

La pieza falla en la práctica por un motivo humano: **los receptores no cruzan**. Abren el reporte, ven el badge verde de las firmas internas, leen "External references (3)" y asumen verificación. La fricción operativa del cross-check manual (descargar la clave de GitHub, parsearla como SSH, convertirla a DER, calcular SHA-256, comparar carácter por carácter contra el fingerprint del reporte) hace que el paso se salte sistemáticamente.

Al mismo tiempo, automatizar el cross-check tiene un riesgo opuesto: si AIP fetcha por sí solo las referencias y dice "verified", el receptor confía en AIP en lugar de en la fuente externa. Se ha reintroducido la autoridad central que ADR-0043 quería evitar.

Necesitamos una posición intermedia: **AIP automatiza la mecánica del cross-check, pero el resultado no sustituye al juicio del receptor**.

## Decisión

Introducir `src/aip/transparency/footprint_verifier.py`, módulo que **fetchea cada referencia externa, extrae la clave declarada por ese canal, calcula su fingerprint, y compara contra el declarado en el archive**. El resultado es un reporte estructurado por referencia: `verified` / `mismatch` / `unreachable` / `unsupported`.

**Propiedad central:**

> Trust Footprint Cross-Verification automatiza la **mecánica** del cross-check externo (HTTP fetch, parseo de formato, cómputo de fingerprint, comparación). No sustituye al juicio del receptor sobre **qué canales confía**. El reporte sigue mostrando todas las referencias declaradas; AIP añade el resultado de su propio fetch, claramente marcado como "AIP machine check". El receptor sigue siendo soberano de elegir qué evidencia acepta.

Convierte el cross-check de **manual y sistemáticamente saltado** a **automatizado y visible**, sin transferir autoridad a AIP.

## Modelo

```python
SUPPORTED_KINDS: Final[frozenset[str]] = frozenset({
    "github_user_keys",
    "https_pem",
})
"""Vocabulario cerrado v1. Cada kind requiere un parser específico para
extraer la clave pública del formato nativo del canal."""

@dataclass(frozen=True, slots=True)
class ReferenceVerifyResult:
    kind: str
    uri: str
    status: Literal["verified", "mismatch", "unreachable", "unsupported"]
    fetched_fingerprint: str | None
    declared_fingerprint: str
    reason: str | None  # Para debug en mismatch/unreachable

@dataclass(frozen=True, slots=True)
class FootprintVerifyReport:
    operator_id: str
    declared_fingerprint: str
    references: tuple[ReferenceVerifyResult, ...]

    @property
    def verified_count(self) -> int: ...
    @property
    def mismatch_count(self) -> int: ...
    @property
    def reachable_count(self) -> int: ...
```

## Algoritmo

### Por kind soportado

**`github_user_keys`**

1. GET `<uri>` (esperado: `https://github.com/<user>.keys`).
2. Body es texto plano, una clave SSH por línea (`ssh-ed25519 <base64> <comment>`).
3. Parsear cada línea con `cryptography.hazmat.primitives.serialization.load_ssh_public_key`.
4. Filtrar sólo claves ed25519 (las RSA/ECDSA se ignoran — no es nuestro contrato).
5. Para cada ed25519 obtenida, calcular `SHA-256(DER SPKI)`.
6. Si **alguna** coincide con `declared_fingerprint` → `verified`. Si no, `mismatch`.

**`https_pem`**

1. GET `<uri>` (esperado: PEM SubjectPublicKeyInfo).
2. Parsear con `cryptography.hazmat.primitives.serialization.load_pem_public_key`.
3. Calcular `SHA-256(DER SPKI)`.
4. Comparar con `declared_fingerprint`.

**Cualquier otro kind**

`status = "unsupported"`. La referencia aparece en el reporte sin verificación automática. El receptor decide si la cruza a mano.

### Mecánica de red

- Stdlib only: `urllib.request`. Sin requests, sin httpx — minimiza supply chain.
- Timeout configurable (default 15 s por referencia).
- User-Agent identificativo (`aip-trust-footprint-verifier/1`).
- Sin redirects más de 3 hops.
- HTTPS-only (rechazar `http://`).

### Lo que NO hace

- **No verifica TLS pinning.** Confía en la cadena de certificados del sistema. El operador que decide aceptar la verificación automática delega esa parte de la confianza a su sistema operativo. Documentado.
- **No detecta MITM activo en el momento del fetch.** Mitigación parcial: el receptor puede hacer el fetch desde redes distintas y comparar.
- **No verifica DNS TXT records.** Diferido: requeriría una dependencia DNS (`dnspython`) que evitamos en v1. ADR futuro si surge demanda.
- **No tira atrás verificaciones previas.** Cada ejecución es independiente — no persiste cache entre runs.

## Surface

### CLI

```
aip transparency verify-footprint --archive-root <root> [--json] [--timeout 15]
```

Exit code: `0` si **todas** las referencias soportadas y alcanzables verifican, `1` si **alguna** alcanzable da mismatch, `2` si todas las soportadas son inalcanzables.

### Reporte HTML standalone

Sección "Signer trust footprint" amplía cada referencia con un sub-badge:

- ✓ `verified by AIP at <timestamp>` (verde sobrio)
- ✗ `MISMATCH at <timestamp>` (rojo prominente)
- ⚠ `not reached (timeout / 404 / network)` (gris, no error)
- — `manual cross-check required` (kinds no soportados)

El badge siempre va **junto al resultado declarado**, nunca lo sustituye. El receptor ve ambas cosas:

> github_user_keys → https://github.com/JFHelvetius.keys
> ✓ AIP fetched and verified at 2026-06-11T18:23:00Z

El receptor sigue siendo libre de hacer su propio fetch desde otra red y comparar contra lo que AIP encontró.

## Consecuencias

**Positivas**

- Cierra la brecha operativa del cross-check manual: el receptor ya ve si las referencias declaradas casan con lo publicado.
- 100% local. AIP fetchea desde la máquina del receptor, no desde un servidor central.
- Granular: cada referencia se reporta por separado, con razón en caso de fallo.
- Vocabulario cerrado: añadir un kind nuevo requiere parser explícito + ADR de ampliación.

**Negativas**

- El receptor podría leer "verified by AIP" y dejar de cruzar a mano. Mitigación: el copy de la sección sigue diciendo "cross-check at least one reference against an independent source", y la badge dice "verified BY AIP" (no "verified"), recordando que AIP no es autoridad neutral si tu adversario controla tu red local.
- Dependencia transitiva del CA store del sistema. Un sistema con certificados raíz comprometidos da `verified` falsos. Documentado como límite.
- Más superficie de red. Cada fetch es un punto donde un MITM activo podría inyectar una clave falsa, aunque sólo con TLS comprometido.

**Neutras**

- Dependencia del sistema operativo para validación TLS. Diferente a la suite del sistema operativo cambia comportamiento. Esperado.
- El cache no persiste — cada `aip transparency verify-footprint` repite los fetches. Operacionalmente razonable, evita falsa confianza por resultado caducado.

## Alternativas consideradas

### A. Hacer el cross-check OBLIGATORIO antes de mostrar firmas como verificadas
**Descripción:** El reporte HTML se niega a renderizar el badge verde de la firma manifest si AIP no consigue verificar al menos una referencia externa.
**Razón de rechazo:** Acopla dos capas que ADR-0024 mantiene separadas. La firma del manifest es matemáticamente correcta independientemente de la identidad. Forzar la dependencia rompe el escenario común (firma válida + receptor sin red en el momento de verificar).

### B. Servidor centralizado de verificación
**Descripción:** Un servicio que cachea verificaciones y las firma con su propia clave. El reporte muestra "trust footprint verified at <serviceURL>".
**Razón de rechazo:** Reintroduce autoridad central exactamente lo que ADR-0043 evita. Inaceptable.

### C. PGP web of trust
**Descripción:** Operadores firman las claves de otros operadores. La verificación sigue cadenas de confianza.
**Razón de rechazo:** No escala fuera de comunidades densas. Un receptor periodista cruzando una clave nueva no tiene cadenas previas. Además, el operador objetivo es quien declara el footprint, no quien recibe firmas externas.

### D. No hacer nada
**Descripción:** Mantener el cross-check manual del ADR-0043. Documentar mejor en el reporte HTML cómo hacerlo.
**Razón de rechazo:** Empíricamente fallido. Receptores no cruzan a mano por la fricción. Documentar mejor no cambia el comportamiento.

## Alineación con ADR-0000

ADR-0000 mantiene la propiedad de **soberanía del receptor**: la verificación nunca transfiere autoridad a un tercero que el receptor no eligió. Esta decisión preserva eso — AIP automatiza la **mecánica** sin sustituir el juicio. El receptor sigue viendo todas las referencias declaradas, sigue pudiendo cruzarlas él mismo desde otra red, y el badge AIP es explícitamente atribuido ("verified by AIP", no "verified") para que el receptor sepa quién hizo el cómputo.

También refuerza la propiedad de **honestidad sobre los límites** (ADR-0024): los `unreachable` y `unsupported` se reportan como tales, no se ocultan. Un canal que falla nunca se marca como verificado.
