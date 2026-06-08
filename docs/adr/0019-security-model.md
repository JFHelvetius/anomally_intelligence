# ADR-0019: Modelo de seguridad

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0014, ADR-0017, ADR-0020

---

## Contexto

El sistema gestiona material de tres categorías sensibles:

1. **Datos personales de testigos** (nombres, ubicaciones, contactos, testimonios bajo condiciones específicas). Sometidos a GDPR, LFPDPPP y equivalentes.
2. **Material desclasificado de jurisdicciones distintas** con reglas heterogéneas sobre redistribución.
3. **Ingestión de fuentes externas** que potencialmente incluye material malicioso (PDFs con payloads, imágenes con esteganografía maliciosa, URLs que sirven contenido distinto bajo distintos User-Agents).

El modelo de seguridad debe abordar:

- Confidencialidad (cuando aplica).
- Integridad de los artefactos.
- Disponibilidad razonable para uso individual.
- Aislamiento de procesos de ingestión potencialmente maliciosos.
- Auditabilidad de acciones.
- Cumplimiento legal por jurisdicción.

Sin caer en seguridad teatral que entorpezca el uso legítimo.

## Decisión

El modelo de seguridad opera en cuatro planos coordinados:

1. **Confidencialidad selectiva**. La mayor parte del archivo es pública. El subset sensible (datos personales no consentidos para publicación, material bajo obligaciones legales específicas) vive en un **enclave** del archivo con cifrado at-rest, audit log, y políticas explícitas.

2. **Integridad por construcción**. Todo blob lleva su hash; toda lectura lo verifica; toda mutación se registra. Cualquier corrupción se detecta. Tampering local no pasa desapercibido.

3. **Sandboxing de adquisición**. Cualquier proceso de adquisición/parsing de material externo se ejecuta en sandbox (subprocess aislado, sin acceso a la red salvo el endpoint declarado, sin acceso al filesystem fuera del directorio de ingestión).

4. **Audit log append-only**. Toda acción mutante deja huella en `audit.log` (append-only, con hash chain estilo log inmutable). El operador puede consultar quién hizo qué y cuándo.

## Especificación

### Enclave de material sensible

Estructura:

```
<aip_root>/
├── ...
└── sensitive/
    ├── policy.yaml              # política aplicable al enclave
    ├── access.log               # quién accedió y cuándo (append-only)
    └── encrypted/               # blobs cifrados (age o equivalente)
```

`policy.yaml` declara, por subset:
- Base legal de retención (GDPR Art. 6/9, equivalente local).
- Período de retención máximo.
- Acceso permitido (lista de actores).
- Reglas de exportación (qué se puede sacar del enclave y bajo qué condiciones).
- Procedimiento de derecho al olvido si aplica.

El enclave **nunca se incluye en snapshots públicos** por defecto. Su exclusión es responsabilidad del comando `aip snapshot create` (verificada).

### Cifrado at-rest del enclave

- **age** (https://age-encryption.org/) como herramienta canónica por su simplicidad y minimalismo.
- Las claves del enclave viven fuera del repositorio (HSM, archivo en `~/.aip/keys/`, etc.). Por defecto, el sistema no genera claves automáticamente: el usuario las provee.
- El cifrado del filesystem subyacente (LUKS, FileVault, BitLocker) **no sustituye** al cifrado del enclave: protege contra robo físico, no contra acceso lógico del propio usuario que copia el directorio.

### Integridad de blobs

- Lectura de blob verifica hash contra el nombre del fichero en CAOS (ADR-0015).
- Discrepancia produce error `IntegrityError` con detalle: archivo esperado, archivo encontrado.
- Comando `aip archive verify` recorre todos los blobs y reporta cualquier corrupción.
- Auditoría periódica de integridad puede automatizarse con cron, sin estar dentro del runtime principal.

### Sandboxing de adquisición y parsing

Material entrante puede ser hostil:

- PDFs con JavaScript o exploits de visor.
- Imágenes con payloads de buffer overflow contra parsers vulnerables.
- WARCs con contenido HTML que ejecuta scripts si se renderiza.
- Archivos comprimidos con bombas zip.

Mitigaciones:

- Parsers ejecutados en subprocess aislado con:
  - User namespace separado donde el OS lo soporta.
  - Sin acceso de red salvo el endpoint declarado por el adquisidor.
  - Sin acceso al filesystem fuera del directorio temporal de ingestión.
  - Límites de CPU, memoria, tiempo y tamaño de output.
- Parsers explícitamente NO permitidos en producción: cualquier parser que requiera ejecución de scripts embebidos.
- Bibliotecas de parsing se actualizan con disciplina; CVEs se siguen activamente.

### Audit log

```
audit.log              # append-only, hash chain
audit.log.index        # índice para queries
```

Cada entrada del audit log:

```
AuditEntry {
  seq: int
  prev_hash: Hash       # hash del registro anterior
  timestamp: timestamp
  actor: ActorId
  action: ActionKind    # ver enumeración
  target: aip_uri       # qué se afectó
  parameters: dict
  result: ResultKind    # success | failure | partial
  request_origin: str?  # CLI, API Python, HTTP IP+token
  schema_version: SemVer
  entry_hash: Hash      # hash de la entrada incluyendo prev_hash
}
```

`ActionKind`: `ingest_evidence`, `create_claim`, `revise_case`, `change_evidence_status`, `enclave_access`, `snapshot_export`, etc.

Verificación de integridad de la audit log: la cadena de hashes encadenados detecta inserciones, eliminaciones o reordenaciones.

### Autenticación en HTTP API

Cubierto a nivel modelo aquí; los detalles en ADR-0017.

- Bind a `127.0.0.1` por defecto: sin auth.
- Bind a interfaz no local: auth obligatorio.
- Tokens emitidos con `aip auth issue --actor <id> --scope <scopes>`.
- Tokens revocables (`aip auth revoke <token_id>`).
- Tokens nunca embebidos en repositorio.

### Defensa contra modelos amenaza

| Amenaza | Mitigación |
|---------|-----------|
| Atacante con acceso al filesystem del usuario | Cifrado at-rest del enclave; logs no protegen contra esto, lo registran |
| Atacante con acceso a la red local | Bind local por defecto; tokens obligatorios en bind expuesto |
| Adquisición de material malicioso | Sandboxing de parsers; lista negra de parsers peligrosos |
| Tampering del archivo público | Integridad por hash; verificación periódica |
| Tampering del audit log | Hash chain |
| Doxxing por agregación accidental | Enclave para datos sensibles; revisión humana de exportes |
| Exfiltración de datos del enclave | Audit log + restricción de exportación |
| Acceso ilegítimo en jurisdicción no del usuario | Fuera de alcance del sistema; documentación advierte responsabilidad del operador |

### No-mitigaciones

Lo que el sistema **no promete**:

- Resistencia a un usuario root del propio sistema que decida modificar manualmente el filesystem. El sistema detecta corrupción y registra, pero no impide.
- Resistencia a coerción legal contra el operador del archivo. Si un juez ordena entregar el archivo entero, el sistema no lo bloquea.
- Resistencia a captura por intereses incompatibles (P4). El operador debe revisar el ADR-0000 sección de condiciones de archivo digno.

### Cumplimiento legal

- **GDPR (UE)**: el sistema soporta derecho al olvido (`TransitionReason.witness_request_anonymization` en cases; cifrado at-rest para datos personales; export del enclave bajo control).
- **LFPDPPP (México)**: análogo.
- **CCPA / equivalentes**: análogo.
- **FOIA / leyes de transparencia**: el sistema no entorpece publicación de material legalmente publicable; lo organiza.

La política de cumplimiento por jurisdicción se documenta en `docs/legal-compliance.md` y se actualiza con cadencia anual o ante cambio legal relevante.

## Justificación

### Por qué enclave separado en lugar de cifrar todo

Cifrar todo es coste sin beneficio para material público. La separación enclave/público hace explícito qué se protege y por qué. También permite distribuir el subset público sin fricción.

### Por qué age en lugar de PGP/GPG

age es simple, moderno, con menos modos de fallo. PGP/GPG son históricamente notables pero abusables y complejos. Para el caso de uso (cifrado at-rest de archivos), age es suficiente.

### Por qué sandboxing y no solo confianza en parsers

Parsers de PDF, imagen, audio históricamente han tenido vulnerabilidades severas. Asumir confiabilidad es imprudente. El coste de sandboxing es bajo comparado con el riesgo.

### Por qué audit log con hash chain

Sin hash chain, un atacante con acceso al log puede reescribir historia. Con hash chain, cualquier modificación se detecta (aunque no se impide).

### Por qué bind local por defecto

P6 (local-first). La mayoría de los usuarios no necesitan acceso remoto. Por defecto, el sistema no abre puertos a la red.

## Consecuencias

**Positivas**
- Material público sigue siendo público sin fricción.
- Material sensible está bajo control documentado.
- Integridad detectable.
- Audit log permite reconstruir qué pasó cuándo.

**Negativas**
- Operación del enclave requiere disciplina del usuario (claves, rotación).
- Sandboxing de adquisición es coste de implementación no trivial.
- Cumplimiento legal por jurisdicción es responsabilidad del operador, no del sistema.

**Neutras**
- El audit log crece linealmente con uso. Rotación opcional.

## Alternativas consideradas

### A. Sin enclave: todo público
**Descripción:** Simplificar asumiendo material exclusivamente público.
**Razón de rechazo:** Excluye casos legítimos con testigos vivos. Conflicto con P12.

### B. Cifrado total
**Descripción:** Cifrar el archivo entero.
**Razón de rechazo:** Coste sin beneficio para material público. Friction de distribución.

### C. PGP/GPG
**Descripción:** Estándar histórico.
**Razón de rechazo:** Complejidad y modos de fallo conocidos.

### D. Sin audit log
**Descripción:** Asumir que el sistema es single-user de confianza.
**Razón de rechazo:** Imposible auditar incidentes. Imposible trazabilidad si hay co-curadores.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P6, P11, P12.

**Cómo se alinean:**
- P12 (do-no-harm): enclave + procedimiento de takedown.
- P2 (trazabilidad): audit log encadenado.
- P11 (inmutabilidad de evidencia cruda): verificación de integridad por hash.
- P6 (local-first): bind local por defecto.

**Tensión:** Friction del enclave vs. uso fluido. Aceptada: el enclave solo afecta material sensible.

## Referencias

- age encryption tool. https://age-encryption.org/
- Sigstore project / transparency logs (prior art en hash chains).
- GDPR Articles 6, 9, 17 (right to erasure).
- LFPDPPP (México).
- OWASP Sandbox guidelines.

---

## Historial de enmiendas

### E1 — 2026-06-07 — Audit chain archive-wide (capa derivada)

**Motivación.** La versión original de ADR-0019 introdujo el audit log con dos
acciones de capa base (`ARCHIVE_BOOTSTRAP`, `INGEST_EVIDENCE`). El propio ADR
anticipaba que "otras acciones (`create_claim`, `revise_case`,
`enclave_access`, etc.) están diferidas; cuando se incorporen, deberán añadirse
a esta enum sin romper la cadena histórica."

Tras P1–P5 y ADRs 0032–0041, el archive tiene **9 dominios** con estado
persistido. Solo **1** (ingesta) emite entries de audit. Los otros 8
(`analysis`, `workspace`, `timeline`, `snapshot`, `diff`, `justification`,
`context`, `attestation`) persisten artefactos sin dejar rastro en la cadena
hash-encadenada. Esto deja la promesa central del proyecto — *"demostrar que
la información no fue alterada"* — cubriendo sólo la ingesta base. Un
operador hostil puede crear, sobrescribir o borrar workspaces, timelines,
snapshots, justifications o **incluso atestaciones criptográficas** sin que
la cadena append-only registre nada.

**Decisión.** Extender `ActionKind` con **6 valores nuevos**, uno por cada
dominio que persiste estado canónico en una localización del archive:

| ActionKind | Dominio | Localización canónica |
|---|---|---|
| `ASSESS_AUTHENTICATION` | `analysis` (ADR-0032) | tabla `authentication_assessments` |
| `BUILD_WORKSPACE` | `workspace` (ADR-0036) | `<archive>/workspaces/<id>.json` |
| `BUILD_TIMELINE` | `timeline` (ADR-0037) | `<archive>/timelines/<id>.json` |
| `BUILD_SNAPSHOT` | `snapshot` (ADR-0038) | `<archive>/snapshots/<id>.json` |
| `BUILD_JUSTIFICATION` | `justification` (ADR-0040) | `<archive>/justifications/<id>.json` |
| `SIGN_ATTESTATION` | `attestation` (ADR-0041) | `<archive>/attestations/<id>.json` |

Cada función de persistencia (`persist_workspace`, `persist_timeline`,
`persist_snapshot`, `persist_justification`, `persist_attestation`,
`Archive.assess_authentication`) recibe `actor: str` y
`clock: Callable[[], datetime]` como keyword args **requeridos**, y tras la
escritura llama al helper compartido `audit_log.record_derived_artifact(...)`.

El helper enforza estructuralmente:

- El `target` sigue el esquema URI canónico `aip:<kind>/<id>`.
- El `self_hash` del artefacto se incluye en `parameters`.
- Sólo se aceptan ActionKinds de la capa derivada (el helper rechaza
  `INGEST_EVIDENCE` y `ARCHIVE_BOOTSTRAP` — esas son responsabilidad de la
  capa base, contra reuso accidental).

**Excluidos explícitamente de V1 (decisión coherente, no oversight).**

- **`diff`** (ADR-0039): es ephemeral, no tiene localización canónica en el
  archive; sólo se emite por CLI a stdout/`--output`. Auditar diff sería
  registrar ejecución de queries, no cambios de estado del archive — error
  de categoría.
- **`context`** (ADR-0035): `assemble_context` produce un ContextBundle
  pero no lo persiste en una localización canónica; el CLI puede emitirlo
  a `--output` pero esa es una operación de lectura más serialización, no
  un cambio de estado del archive.

Cuando alguno de estos dominios gane una localización canónica
persistente (futuro ADR de enmienda), su ActionKind se añade entonces, no
antes.

**Contrato de actor y clock.**

- `actor` es operator-supplied (igual que `signer_id` en ADR-0041 §componentes
  excluidos: no PKI en V1). El CLI lo expone como `--actor` requerido en
  los 5 comandos write-side (`workspace create`, `timeline build`,
  `snapshot create`, `justification build`, `assess-authentication`). Para
  `attestation sign` se reutiliza `--signer-id` (mismo actor del acto
  criptográfico).
- `clock` es un `Callable[[], datetime]` inyectable. En tests se pasa un
  clock fijo para reproducibilidad bit a bit. En la CLI se usa
  `datetime.now(UTC)`. La regla `microsecond=0` del ADR-0024 L2 se aplica
  en `append_entry` (truncado defensivo).

**Garantías estructurales (verificadas por `tests/unit/audit/test_derived_actions.py`).**

- **G_E1_a — exactamente una entry por persistencia derivada.** Llamar a
  `persist_workspace`, `persist_timeline`, etc. añade UNA entry, no cero, no
  dos. La entry contiene `action`, `target=aip:<kind>/<id>`,
  `parameters["self_hash"]=<artifact_hash>`.
- **G_E1_b — la cadena verifica con derivados intercalados y el verifier
  detecta tampering.** `verify_chain(root)` recorre las entries derivadas
  igual que las de la capa base. Editar el `actor` (o cualquier otro
  campo) de una entry derivada en disco hace que el verifier devuelva
  `ok=False` con `first_failure_seq` apuntando a la entry alterada.
- **G_E1_c — `audit_log_head_hash` es archive-state fingerprint
  diferenciador.** Dos archives con misma evidencia base pero distintos
  derivados producen heads distintos. Esto convierte el par
  (`manifest_hash`, `audit_log_head_hash`) en fingerprint completo del
  archive: el primero pinea el estado actual de tablas+blobs, el segundo
  pinea la historia de operaciones.
- **Invariante de manifest preservada.** Las entries derivadas no entran
  en la canonicalización del manifest; `archive_manifest_hash` permanece
  bit-idéntico ante operaciones de capa derivada (consistente con las
  reglas S11, S15, S16 de ADR-0030 — los directorios `workspaces/`,
  `timelines/`, etc. son periféricos a `V1_TABLES`).

**Compatibilidad con pins de reproducibility.**

- Los 16 hashes pinned en `tests/reproducibility/test_manifest_hash.py` y
  `tests/reproducibility/test_jcs.py` permanecen idénticos. Razón: el
  manifest no incluye el audit log y los JCS pins no canonicalizan audit
  entries.
- Los 2 hashes pinned en `tests/reproducibility/test_audit_chain.py`
  (`EXPECTED_BOOTSTRAP_HASH`, `EXPECTED_INGEST_HASH`) permanecen idénticos.
  Razón: ese test construye su cadena de dos entries manualmente sin pasar
  por engines derivados; los valores string de `ARCHIVE_BOOTSTRAP` e
  `INGEST_EVIDENCE` son estables.

**Alineación ADR-0000.**

- **P2 (trazabilidad):** se extiende de 1/9 dominios a 6/6 dominios con
  estado persistido canónico. Ningún cambio de estado del archive escapa
  ya de la cadena hash-encadenada.
- **P11 (inmutabilidad):** el audit log gana cobertura simétrica sobre todos
  los artefactos derivados. Si un row de assessment o un workspace.json se
  borran, la entry permanece como rastro append-only de que el acto
  ocurrió.
- **P5 (reproducibilidad):** los 16 pins se mantienen verdes.

Sin esta enmienda, ADR-0041 (Operator Attestation Engine) dejaba un hueco
estructural: una atestación criptográfica puede registrar el vínculo
clave↔artefacto, pero el **acto** de atestar (cuándo, por quién, sobre
qué artefacto) no entraba en ninguna cadena append-only. E1 cierra ese
ciclo.
