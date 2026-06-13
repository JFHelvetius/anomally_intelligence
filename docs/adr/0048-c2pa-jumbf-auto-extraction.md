# ADR-0048: C2PA JUMBF Auto-Extraction

**Estado:** Aceptado
**Fecha:** 2026-06-13
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0023, ADR-0024, ADR-0046, ADR-0047

---

## Contexto

ADR-0046 introdujo la capa de atestación C2PA en AIP, pero diferió **explícitamente** la extracción binaria del JUMBF (JPEG Universal Metadata Box Format) embebido en JPEG/PNG/MP4. El operador debía usar tooling externa (`c2patool extract`) para sacar el manifest JSON antes de pasárselo a `aip evidence c2pa-verify`.

Esto generó fricción operativa real:

- Tres pasos manuales por evidencia (extract → revisar JSON → verify).
- Dependencia de tooling externa cuya disponibilidad varía por plataforma.
- El JSON intermedio es **operator-supplied**, y un operador malicioso podría alterar el output de `c2patool` antes de pasarlo a AIP. ADR-0047 cierra el hueco de la firma X.509, pero no el de la **fidelidad de la extracción**.

La librería oficial `c2pa-python` (binding de `c2pa-rs`) está estable, tiene wheels para Windows/macOS/Linux, y expone una API limpia (`Reader(path).json()`) que devuelve el manifest store completo. Integrarla cierra los tres problemas a la vez.

## Decisión

Introducir `src/aip/c2pa/extractor.py`, módulo que usa `c2pa-python` como **dependencia opcional** (`aip[c2pa]`) para extraer el manifest chain de un fichero JPEG/PNG/MP4/HEIC/AVIF/DNG/PDF/audio directamente, sin tooling externa.

El extractor:

1. Lee el fichero binario con `c2pa.Reader(path).json()`.
2. Transforma el formato C2PA nativo (manifests indexados por label) en la forma AIP (lista con `parent_manifest_label` explícito), que ya consume `aip.c2pa.parse_manifest_json`.
3. Devuelve el dict listo para pasar a `verify_manifest_chain` (ADR-0046) y, si el operador lo desea, `verify_x509_chain` (ADR-0047).

**Propiedad central:**

> AIP usa `c2pa-python` exclusivamente como **parser**. Nunca acepta su veredicto de verificación como autoritativo — la cadena X.509 se re-verifica en proceso (ADR-0047) cuando el operador suministra una trust list. La librería externa es un mecanismo de extracción, no una fuente de confianza.

## Modelo

```python
def extract_from_media(
    media_path: Path,
    *,
    include_validation_status: bool = True,
) -> dict[str, object]:
    """Extract the C2PA manifest chain from a media file.

    Returns a dict in the AIP shape (compatible with
    ``parse_manifest_json``). Raises ``AIPError`` if c2pa-python is not
    installed, if the file has no C2PA manifest, or if extraction fails.
    """
```

### Vocabulario de transformación

| C2PA shape                          | AIP shape                                |
|-------------------------------------|------------------------------------------|
| `manifests[label]` (dict)           | `manifests[i]` con `label = key`        |
| `active_manifest`                   | El primer manifest del array            |
| Ingredient chain (`ingredients[]`)  | `parent_manifest_label` cuando aplica   |
| `signature_info.alg / issuer / time`| `signature_info` AIP fields             |
| `validation_status[]`               | `chain_verified` boolean operator-supplied |
| Cert chain raw bytes                | `cert_chain_pem` (cuando exposable)     |

### Lo que NO hace

- **No fabrica el `cert_chain_pem` cuando `c2pa-python` no lo expone.** En `c2pa-python` 0.34, los bytes del cert chain del manifest no están siempre disponibles vía la API pública. Cuando faltan, el `cert_chain_pem` queda vacío y ADR-0047 cae al modo `operator-supplied`. Honest sobre la limitación; el follow-up (ADR-0049 si surge demanda) extraerá los certs directamente del JUMBF.
- **No verifica firmas.** La transformación es puramente sintáctica.
- **No modifica el fichero original.** Operación read-only.
- **No es obligatorio.** Sin la dep instalada, `aip evidence c2pa-verify` con un JSON pre-extraído sigue funcionando exactamente igual.

## Surface

### CLI

Nuevo comando:

```
aip evidence c2pa-extract <media_file> [--out <json_path>]
```

Lee el fichero, extrae el manifest, emite el JSON en forma AIP (a stdout o al fichero `--out`). Exit code:
- `0` — extracción correcta y manifest no vacío.
- `1` — fichero sin manifest C2PA (no es error si el operador lo intentó "por si acaso", pero el receptor sabe que no hay capa).
- `2` — dep no instalada o error de parseo del fichero.

Pipeline end-to-end típico:

```
aip evidence c2pa-extract photo.jpg --out manifest.json
aip evidence c2pa-verify manifest.json \
    --evidence-sha256 <hex> \
    --trust-list-pem trust.pem \
    --archive-root <root>
```

### Dependencia opcional

`pyproject.toml`:

```toml
[project.optional-dependencies]
c2pa = ["c2pa-python >=0.34,<1"]
```

Sin el extra, `aip evidence c2pa-extract` falla con un mensaje claro:

```
Error: c2pa extraction requires the optional dependency.
Install with: pip install 'aip[c2pa]'
```

## Consecuencias

**Positivas**

- Elimina el paso manual `c2patool extract`.
- AIP controla la fidelidad del parseo — un operador no puede inyectar JSON alterado, porque AIP mismo extrae del binario.
- Compatible con cualquier formato C2PA que `c2pa-rs` soporte (lista creciente: JPEG, PNG, MP4, HEIC, AVIF, DNG, audio, PDF).
- Backward compatible. El flujo de ADR-0046 (operator-supplied JSON) sigue funcionando.

**Negativas**

- Nueva dependencia native (Rust binding). Aumenta supply chain. Mitigación: es opcional, no obligatoria.
- `c2pa-python` tiene su propia trust list interna que AIP ignora. Confusión potencial para el operador que ve "verified" en la output de `c2pa-python` y "FAILED" en AIP, o viceversa. Documentado: AIP's verdict es el único autoritativo.
- Lock-in soft a la API de `c2pa-python` 0.34. Cambios mayores en la librería requerirán ajuste del módulo.

**Neutras**

- Cuando `cert_chain_pem` no se puede extraer, ADR-0047 cae a `operator-supplied`. El operador puede comparar con la output de `c2pa-python --trust-anchors` y decidir.
- El JSON de salida usa la forma AIP, no la forma C2PA nativa. Documentado en el output del CLI.

## Alternativas consideradas

### A. Parsear el JUMBF manualmente sin dependencia
**Descripción:** Implementar parser del box JUMBF en Python puro.
**Razón de rechazo:** JUMBF + CBOR + COSE + X.509 son ~500 páginas de spec. Mantener un parser propio es alto coste sin valor diferenciado. `c2pa-rs` ya lo hace bien y está mantenida por la CAI.

### B. Llamar a `c2patool` como subproceso
**Descripción:** Si `c2patool` está en `PATH`, AIP lo invoca y parsea su output.
**Razón de rechazo:** Reintroduce la dependencia de tooling externa que ADR-0048 intenta eliminar. Sólo trasladaría el problema.

### C. Hacer `c2pa-python` dependencia obligatoria
**Descripción:** Empaquetar `c2pa-python` con AIP siempre.
**Razón de rechazo:** Operadores que no usan C2PA pagan supply chain extra. Mejor: opcional, instalable bajo demanda.

### D. No hacer la extracción y mantener tooling externa
**Descripción:** Statu quo de ADR-0046.
**Razón de rechazo:** Fricción real medida. La capa C2PA es menos usada por la fricción del paso manual.

## Alineación con ADR-0000

ADR-0000 establece que **el sistema debe ser honesto sobre lo que prueba** y **el operador y el receptor deben mantener soberanía**. Esta decisión preserva ambas:

- `c2pa-python` se usa como parser, no como autoridad. Si la librería verifica una firma que ADR-0047 considera inválida, el verdict de AIP prevalece — y el reporte HTML siempre dice "verified in-process by AIP" vs "operator-supplied", nunca "verified by c2pa-python".
- La dep es opcional. Operadores que prefieren no instalar binarios native pueden seguir con el flujo manual.

Refuerza también la propiedad de **fidelidad de la extracción**: hasta ADR-0048, un operador malicioso podía alterar la output de `c2patool` antes de dársela a AIP. Con la extracción in-process, el único punto donde se puede manipular es el fichero binario original, cuya hash SHA-256 ya está atado por la cadena de custodia de AIP desde el ingest.
