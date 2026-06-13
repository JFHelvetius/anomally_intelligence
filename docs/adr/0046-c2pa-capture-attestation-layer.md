# ADR-0046: C2PA Capture Attestation Layer

**Estado:** Aceptado
**Fecha:** 2026-06-11
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0019, ADR-0023, ADR-0024, ADR-0041, ADR-0043, ADR-0045

---

## Contexto

ADR-0023 mantiene fuera de scope V1 la prueba de que el **contenido de la evidencia** es real (versus escenificado o fabricado con anterioridad a la ingesta). ADR-0024 reafirma esa propiedad: AIP garantiza integridad desde la ingesta, no autenticidad del contenido pre-ingesta.

El año 2026 introduce un cambio relevante en el ecosistema: el estándar **C2PA** (Coalition for Content Provenance and Authenticity), respaldado por Adobe, Microsoft, BBC, Sony, Nikon, Leica y la Content Authenticity Initiative, empieza a estar disponible en cámaras de gama profesional y prosumer. Una cámara C2PA firma criptográficamente los bytes producidos en el momento de la captura con una clave anclada al chip del dispositivo. Cuando esa imagen pasa por un editor compatible, se añade un manifest adicional que documenta cada edición. La cadena resultante es **verificable contra una PKI gestionada por C2PA** (o el operador).

Esto cierra parcialmente el hueco "contenido falso desde el día uno": si la cámara firmó los bytes en el instante de captura, un actor que quisiera fabricar evidencia tendría que comprometer el firmware del dispositivo (mucho más caro que editar un fichero MP4).

Pero C2PA introduce su propia jerarquía de confianza (X.509 con cadena CA). Integrarlo naivamente sin guardrails reintroduciría exactamente el patrón "confía en una CA central" que ADR-0023 y ADR-0043 evitaron deliberadamente.

## Decisión

Introducir una **capa de atestación de captura** opcional basada en C2PA. AIP:

1. **Acepta y verifica manifests C2PA** asociados a una evidencia ingestada.
2. **Almacena el resultado de la verificación** como un sidecar JSON con procedencia completa.
3. **Surface la capa en el reporte HTML** como información adicional, claramente etiquetada como "operator-supplied via C2PA, verified against trust list X".

**Propiedad central:**

> C2PA Capture Attestation es una **capa de información adicional**, no un veredicto de autenticidad. AIP nunca acepta ni rechaza evidencia basándose en la presencia o ausencia de un manifest C2PA. La verificación C2PA es **información que se preserva con procedencia**; el analista humano la usa para informar su juicio, pero AIP no la convierte en conclusión.

Convierte la verificabilidad de captura de **ausente** (V1 pre-0046) a **opcional, transportada con honestidad sobre sus límites** (post-0046). AIP no se vuelve una CA C2PA; el operador y el receptor deciden qué trust list aceptan.

## Modelo

```python
C2PA_REPORT_SCHEMA_VERSION: Final[str] = "1"
C2PA_REPORT_TYPE: Final[str] = "aip.capture.c2pa.attestation.v1"

@dataclass(frozen=True)
class C2PAAssertion:
    """Una afirmación dentro de un manifest C2PA (e.g., 'captured at lat/lon
    on 2026-06-11', 'edited with Photoshop 25.4', 'AI-generated content')."""
    label: str
    data: dict[str, JsonValue]

@dataclass(frozen=True)
class C2PASignatureInfo:
    """Quién firmó este manifest según el certificado embebido. Las firmas
    de cámaras profesionales identifican al fabricante (e.g., 'Sony Imaging
    Products & Solutions Inc.'). Las firmas de editores identifican la
    aplicación (e.g., 'Adobe Inc.')."""
    issuer_common_name: str
    issuer_organization: str | None
    cert_serial: str
    not_before: str  # ISO-8601 UTC
    not_after: str   # ISO-8601 UTC
    chain_verified_against: str  # nombre de la trust list usada

@dataclass(frozen=True)
class C2PAManifest:
    """Un manifest individual dentro de la cadena C2PA. Una cámara genera
    el primer manifest; cada editor añade uno encadenado al anterior."""
    label: str  # identificador del manifest
    signature_info: C2PASignatureInfo
    assertions: tuple[C2PAAssertion, ...]
    parent_manifest_label: str | None  # None en el primer manifest (cámara)

@dataclass(frozen=True)
class C2PAReport:
    """Resultado completo de verificar la cadena C2PA de una evidencia."""
    report_type: str  # const "aip.capture.c2pa.attestation.v1"
    schema_version: str
    evidence_sha256: str  # hash del fichero al que aplica
    verified_at: str      # ISO-8601 UTC, cuándo AIP corrió la verificación
    trust_list_name: str  # 'c2pa-default-trust-list-v1' o el override
    chain_verified: bool  # True si TODA la cadena verifica
    failure_reason: str | None
    manifests: tuple[C2PAManifest, ...]
    report_hash: str  # SHA-256 JCS sobre el dict excluyendo report_hash
```

## Algoritmo

### Verificación

1. Operador externamente extrae el manifest C2PA del fichero (usando `c2patool extract` o equivalente). El JSON resultante se pasa a AIP.
   - Alternativa futura (ADR posterior): AIP integra `c2pa-python` para extracción automática durante `aip evidence ingest`.
2. AIP recibe `(manifest_json, expected_evidence_sha256, trust_list)`.
3. Verifica que el `assertions` contiene un `c2pa.hash.data` que coincide con `expected_evidence_sha256`.
   - Si no coincide → `chain_verified=False`, `failure_reason="manifest does not bind to declared evidence hash"`.
4. Verifica cada signature contra la trust list configurada.
   - Trust list por defecto: `c2pa-default-trust-list-v1` (la oficial de C2PA, incluida en el repo como JSON estático).
   - Operador puede pasar `--trust-list <path>` para override.
5. Construye un `C2PAReport` con todos los manifests, sus firmantes según el cert, las assertions, y el verdict global.
6. Calcula `report_hash` JCS y persiste como `<archive>/c2pa-attestations/<evidence_sha256>.json`.

### Lo que NO hace

- **No extrae el manifest del binario** en v1. Requiere extracción externa con `c2patool` o `c2pa-python`. ADR posterior si añade demanda.
- **No verifica que las assertions sean ciertas.** Si el manifest declara "captured at GPS=40.4N,3.7W", AIP confirma que la cámara firmó esa assertion, pero no que la cámara realmente estuviera allí (un actor con acceso físico al dispositivo puede falsificar coords).
- **No vincula identidad humana al firmante.** El cert de la cámara identifica al fabricante; saber qué humano operaba la cámara es trabajo del analista (ADR-0043 cubre la vinculación clave-identidad para operadores de archives, no para fabricantes).
- **No condiciona el archive a la presencia de C2PA.** Una evidencia sin C2PA se ingesta normalmente. Una con C2PA gana una capa adicional. Cero discriminación.

## Surface

### CLI

```
aip evidence c2pa-verify <manifest_json_path> \
    --evidence-sha256 <hex> \
    [--trust-list <path>] \
    [--archive-root <root>]
```

Verifica el manifest contra la trust list, computa el report, y opcionalmente lo persiste en el archive.

Exit code:
- `0` — manifest verifica completamente y vincula a la evidencia declarada.
- `1` — manifest no verifica o no vincula. El report se emite igualmente con `chain_verified=False`.
- `2` — input inválido (JSON corrupto, evidence_sha256 mal formado).

### Reporte HTML standalone

Nueva sección "Capture attestation (C2PA)" justo después de "Capture certificate":

- Si no hay C2PA report en el archive: sección omitida (no se renderiza).
- Si hay: muestra cada manifest de la cadena con su firmante, fecha del cert, assertions relevantes, y el verdict global como badge.
- El copy debe ser explícito sobre lo que el C2PA prueba y lo que no — alineado con ADR-0024.

## Consecuencias

**Positivas**

- Cierra parcialmente el "contenido falso desde el día uno" para evidencia capturada con dispositivos C2PA-compliant.
- Compatible con el ecosistema 2026+: Sony Alpha 1 II, Leica M11-P, BBC News, Reuters Pictures, AFP — todos usan C2PA.
- Operator-supplied, opt-in, sin discriminar la evidencia que no lo tiene.
- Trust list overridable: el operador puede usar una trust list distinta para casos especiales (e.g., cámaras militares con CA propia).

**Negativas**

- Introduce dependencia conceptual de la PKI de C2PA por defecto. El operador puede sobreescribirla, pero la mayoría aceptará el default; eso transfiere parcialmente la confianza a una organización (C2PA / Adobe).
- Verificación C2PA real requiere parsear X.509 con CRL/OCSP — `cryptography` (ya dependencia) lo permite, pero añade complejidad de manejo de revocación.
- "Verified by AIP" vs "Verified by C2PA" en el reporte HTML — copy cuidadoso para que el receptor no asuma que un manifest C2PA verificado equivale a "esto es real".

**Neutras**

- El primer manifest de la cadena identifica al fabricante de la cámara, no al humano que disparó. Esto está alineado con C2PA pero podría sorprender a quien espere identidad humana. Documentado en el copy.
- La extracción del JUMBF queda como tarea externa en v1. Reduce scope pero genera fricción operativa para el operador.

## Alternativas consideradas

### A. Integrar `c2pa-python` para extracción automática en `ingest`
**Descripción:** Cuando `aip evidence ingest` recibe un fichero, intenta extraer el manifest C2PA automáticamente con la librería Python.
**Razón de aplazamiento (no rechazo):** Requiere dependencia native (Rust binding). Útil pero suma supply chain. Vale la pena cuando suficiente demanda lo justifique — ADR posterior con la integración real.

### B. Hacer la verificación C2PA bloqueante: rechazar evidencia sin manifest válido
**Descripción:** Si la evidencia ingestada tiene un manifest C2PA pero no verifica, AIP rechaza la ingesta.
**Razón de rechazo:** Discrimina contra evidencia legítima de dispositivos sin C2PA (la enorme mayoría del mundo). Viola la propiedad de "AIP nunca decide qué es real" (ADR-0024). El analista humano decide si la falta o fallo de C2PA afecta su valoración.

### C. Aceptar cualquier trust list operator-supplied sin defaults
**Descripción:** AIP no incluye ninguna trust list por defecto. El operador siempre tiene que pasar una.
**Razón de rechazo:** Genera fricción operativa innecesaria para el caso común (operadores que aceptan la trust list oficial de C2PA). Mejor: default razonable + override explícito.

### D. No integrar C2PA en absoluto
**Descripción:** Mantener el statu quo. Los operadores que necesiten verificar C2PA usan herramientas externas y adjuntan los resultados como evidencia documental adicional.
**Razón de rechazo:** Pierde la oportunidad de cerrar parcialmente el hueco más conocido del modelo. El esfuerzo de integración como capa pasiva es modesto.

## Alineación con ADR-0000

ADR-0000 establece que **AIP preserva evidencia con honestidad sobre lo que prueba y lo que no**. Esta decisión preserva ambas:

- El C2PA report se almacena con procedencia (cuándo se verificó, contra qué trust list, qué assertions contiene) — preservación honesta.
- AIP nunca convierte un manifest C2PA verificado en "esto es real" — honestidad sobre los límites mantenida.

Refuerza también la **soberanía del receptor** (ADR-0043): el receptor puede inspeccionar la trust list usada, comparar contra su propio entendimiento de qué CAs confía, y descartar la atestación si no le parece confiable. AIP no decide por él; sólo transporta la info con su procedencia completa.
