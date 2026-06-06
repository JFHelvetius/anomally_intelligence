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

*Sin enmiendas a fecha de aceptación.*
