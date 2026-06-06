# ADR-0031: Testing Strategy — política de pruebas para V1

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0003, ADR-0015, ADR-0016, ADR-0023, ADR-0026, ADR-0029, ADR-0030

---

## Contexto

V1 entrega un sistema cuyo valor está en su **integridad**: un PDF se ingesta, se direcciona por hash, se persiste con procedencia, se verifica bit a bit. Una sola línea de código equivocada en el camino crítico (hash, canonicalización JCS, manifest, audit chain) compromete las propiedades irrenunciables P2 (trazabilidad), P5 (reproducibilidad) y P11 (inmutabilidad de evidencia).

Bajo bus factor = 1 (ADR-0026), sin revisión por pares interna sostenida, la testing strategy compensa parcialmente la ausencia de cuatro ojos: los tests actúan como verificación automatizada del diseño y como red de seguridad frente al sesgo del único mantenedor.

Una testing strategy ingenua (sin tipos, sin reproducibilidad, con dependencias externas, sin distinción de capas) produce suite de baja confianza que cuesta mantener y no detecta los bugs que más importan. Este ADR fija las reglas operativas para que la suite de V1 sea **alineada con su alcance, reproducible bit a bit, y libre de dependencias externas**.

## Decisión

V1 adopta una testing strategy con cinco compromisos:

1. **Tres categorías de tests con propósito distinto**: `unit/`, `integration/`, `reproducibility/`.
2. **Cobertura mínima diferenciada por capa**: 95% en `core/` y `audit/`, 90% en `storage/`, 80% en `cli/`.
3. **Reproducibilidad bit a bit como propiedad testeable**: cualquier hash, manifest, audit chain producido por la suite debe ser idéntico entre ejecuciones y entre plataformas de referencia.
4. **Prohibición absoluta de dependencias externas en tests**: ningún test puede acceder a red, a servicios remotos, ni a recursos no versionados en el repositorio.
5. **Fixtures como artefactos versionados con explicación**: cualquier binario en `tests/data/` lleva su justificación documentada.

Estos cinco compromisos son verificables. Una violación es bug del PR, no estilo.

## Herramientas

- **pytest** como framework de tests (open source, maduro, soportado por la audiencia primaria).
- **pytest-cov** para medición de cobertura.
- **hypothesis** opcional para tests basados en propiedades de las primitivas (hash, canonicalización JCS). Su uso es **opcional**, no obligatorio; cuando se use, los seeds se fijan para reproducibilidad.
- **mypy** o **pyright** (decisión de ADR-0029) como capa de tipado verificable.
- **ruff** como linter, ejecutado como parte de CI.

Las cinco herramientas son open source, embebibles, sin dependencia de servicios remotos.

## Tipos de pruebas

### T1. Unit tests (`tests/unit/`)

**Propósito:** verificar comportamiento aislado de cada unidad lógica.

**Características obligatorias:**

- Sin I/O a disco salvo bajo `tmp_path` de pytest (fixture estándar).
- Sin red, sin subprocess, sin variables de entorno mutadas.
- Determinismo absoluto: el mismo test ejecutado N veces produce el mismo resultado.
- Tiempo de ejecución individual: < 100 ms por test típico. Si un test individual excede 1 s, justificarlo en docstring del test.
- Cada test verifica **una afirmación específica**. Tests con N afirmaciones se descomponen en N tests cuando es posible.

**Espejo del árbol de `src/`:**

- `tests/unit/core/test_hashing.py` verifica `src/aip/core/hashing.py`.
- `tests/unit/core/test_evidence.py` verifica `src/aip/core/evidence.py`.
- `tests/unit/storage/test_caos.py` verifica `src/aip/storage/caos.py`.
- Y así sucesivamente.

**Áreas de cobertura unit obligatorias:**

- Cómputo de SHA-256 bit a bit sobre bytes conocidos.
- Canonicalización JSON (RFC 8785) sobre casos canónicos.
- Construcción y validación de tipos del modelo (Evidence, Source, Provenance, AuthenticationAssessment).
- Generación y parseo de URIs `aip:`.
- Generación y parseo de ULIDs.
- Layout de paths del CAOS.
- Append-only del audit log: serie de N entradas produce cadena de N hashes correctos.
- Detección de tampering: una entrada modificada del audit log rompe la verificación.

### T2. Integration tests (`tests/integration/`)

**Propósito:** verificar que los componentes orquestados producen el comportamiento end-to-end esperado.

**Características obligatorias:**

- Pueden usar disco bajo `tmp_path`.
- Pueden ejecutar la CLI como subprocess (pero **no** acceden a red).
- Tiempo de ejecución individual: < 30 s por test.

**Test canónico obligatorio: `demo_pipeline_test.py`**

Este test es la **demo de cierre F1 ejecutada como código**. Su existencia es bloqueante para la release V1.

Estructura:

1. Setup: copia del PDF de fixtures versionados (`tests/data/`) a `tmp_path`.
2. Acción: ejecuta `aip evidence ingest <pdf> --source-id <id> --source-name <name>` sobre `tmp_path/archive/`.
3. Verifica: hash SHA-256 reportado coincide con valor canónico fijado.
4. Acción: ejecuta `aip evidence show <hash> --archive-root <tmp_path/archive>`.
5. Verifica: output contiene los campos canónicos esperados (kind, source, provenance, status, ingested_at, ingested_by).
6. Acción: ejecuta `aip archive verify --archive-root <tmp_path/archive>`.
7. Verifica: exit code 0 y output canónico.
8. Teardown: pytest limpia `tmp_path` automáticamente.

Este test es el "smoke test" del proyecto. Su rotura es señal de bug en el camino crítico, no en un módulo aislado.

### T3. Reproducibility tests (`tests/reproducibility/`)

**Propósito:** verificar que las propiedades irrenunciables P2 y P5 se mantienen.

**Características obligatorias:**

- Cualquier hash, manifest o audit chain producido debe ser **idéntico** entre ejecuciones.
- Cualquier hash debe ser **idéntico** entre plataformas de referencia (Linux x86_64; soporte best-effort en macOS arm64 y Windows x86_64).
- Tests usan inputs canónicos versionados; rechazan inputs dinámicos.

**Tests canónicos obligatorios:**

- `manifest_hash_test.py`: dada una secuencia fija de operaciones (ingestar el PDF fixture, generar manifest), el `archive_manifest_hash` resultante es un valor canónico fijado en el test. Si cambia, ha cambiado alguna canonicalización del manifest y eso es bug arquitectónico crítico.
- `audit_chain_test.py`: dada una secuencia fija de operaciones, los hashes encadenados del audit log son valores canónicos.
- `jcs_test.py`: dado un conjunto de objetos JSON canónicos, su forma canonicalizada y su hash SHA-256 son valores canónicos.

Estos tests son la red de seguridad estructural contra el modo de fallo "cambio sutil en serialización que rompe reproducibilidad sin que nadie note hasta meses después".

## Cobertura mínima

### Por capa

| Capa | Cobertura mínima | Justificación |
|------|------------------|---------------|
| `src/aip/core/`    | **95%** | Modelo de dominio crítico. Bugs aquí se propagan a todo. |
| `src/aip/audit/`   | **95%** | Audit log es defensa contra tampering. Su correctitud es no negociable. |
| `src/aip/storage/` | **90%** | Capa de persistencia. Path handling y serialización tienen casos límite. |
| `src/aip/cli/`     | **80%** | Adapter delgado. La cobertura no es la métrica primaria; la integration test cubre el comportamiento real. |

La cobertura global mínima del proyecto: **90%**.

### Justificación de los umbrales

Umbrales altos en `core/` y `audit/` reflejan que esas capas son la columna vertebral del proyecto. Un bug no cubierto allí compromete propiedades irrenunciables.

Umbral más bajo en `cli/` reconoce que:

- El test de integración (`demo_pipeline_test.py`) cubre el camino feliz de la CLI completamente.
- Tests unitarios de CLI son menos valiosos por nodo, porque la CLI es orquestación.
- Buscar 95% en CLI lleva a tests artificiales (mock de argparse, etc.) que no añaden confianza.

### Qué la cobertura NO mide

- Cobertura no mide **corrección semántica**. Un test puede ejecutar una línea sin verificar que su comportamiento sea correcto. La cobertura es condición necesaria, no suficiente.
- Cobertura no mide **diseño**. Un módulo mal diseñado puede tener 100% de cobertura.
- Cobertura no mide **comportamiento de errores no testeados**. Las ramas de excepción se cuentan, pero los casos límite no cubiertos por test no se detectan.

Bajo bus factor = 1, la cobertura es una herramienta. No es la métrica de calidad.

## Reglas de reproducibilidad

### R1. Determinismo del wall clock

Ningún test depende del wall clock real. Cuando un test verifica comportamiento que involucra timestamps:

- Inyectar reloj mock o usar un valor fijado.
- El timestamp del test no es `datetime.now()`, es un valor canónico.

### R2. Determinismo de IDs aleatorios

Cuando un test verifica generación de ULIDs u otros IDs con componente aleatorio:

- Inyectar generador con seed fijo.
- O verificar la **estructura** del ID, no su valor exacto.

### R3. Determinismo de orden

Iteración sobre dicts, sets, o sistemas de archivos puede producir órdenes no deterministas. Tests:

- Ordenan explícitamente antes de comparar.
- Usan estructuras ordenadas (lista) cuando el orden es semánticamente relevante.

### R4. Hashes canónicos en tests

Tests de reproducibilidad codifican valores canónicos esperados:

```python
EXPECTED_PDF_SHA256 = "abcdef0123..."  # valor pinned
EXPECTED_MANIFEST_HASH = "fedcba9876..."  # valor pinned
```

Cuando el valor canónico cambia, **el cambio entra por PR explícito** que documenta la causa (cambio de canonicalización, cambio de algoritmo, etc.). Un cambio silencioso es bug.

### R5. Reproducibilidad entre plataformas

Linux x86_64 es la plataforma de referencia. Los valores canónicos fijados en tests se generan en Linux x86_64.

Para macOS arm64 y Windows x86_64 (soporte best-effort):

- Si los valores canónicos no coinciden por diferencia legítima (line endings, encoding de path), el test marca skip explícito con motivo documentado, no se silencia.
- Si los valores no coinciden por bug del proyecto, es bug crítico independiente de la plataforma.

### R6. Tiempo de ejecución reproducible

Los tests no asumen rendimiento mínimo. Un test que falla por timeout en máquina lenta es bug del test, no del código.

## Prohibición de dependencias externas en tests

**Esta sección es la disciplina más estricta del ADR.**

### P1. Sin red en ningún test

- Sin `requests.get`, sin `urllib.request.urlopen`, sin `socket.connect`.
- Sin OAuth, sin descargas, sin webhooks.
- Si un test necesita "datos de Internet", el PR lo rechaza.

Si el código bajo test requiere acceso a red por su naturaleza (no es el caso en V1), el test inyecta un mock estricto del cliente HTTP y verifica que las llamadas se construyen correctamente. **Nunca** llama a red real.

### P2. Sin servicios remotos

- Sin Docker requerido para ejecutar tests.
- Sin bases de datos remotas.
- Sin colas de mensajes.
- Sin APIs de proveedores externos (modelos LLM, geocoders, OCR).

V1 no tiene componentes que requieran estos servicios. La prohibición está pensada para que cuando lleguen fases posteriores, esta política sea ya cultura del proyecto.

### P3. Sin secrets ni credenciales

- Sin variables de entorno con tokens.
- Sin acceso a `~/.config/` o paths de configuración del usuario.
- Tests operan en su propio sandbox (`tmp_path`).

### P4. Sin reloj de pared

Cubierto en R1 (determinismo). Aquí se reafirma como prohibición.

### P5. Sin instalaciones globales

- Tests no asumen que herramientas externas están en `PATH` salvo Python y las dependencias declaradas en `pyproject.toml`.
- Sin asumir `git`, `tar`, `curl` u otros binarios disponibles.

### P6. Sin LLM ni modelos remotos

V1 no usa LLMs (ADR-0023). La prohibición es estructural: cuando un futuro componente use LLM, sus tests usarán stubs deterministas, nunca el modelo real.

### Excepciones documentadas

Ningún test puede declarar excepción individual a estas prohibiciones. Si surge una necesidad legítima, requiere ADR de enmienda específico al ADR-0031. La política es brutal por diseño: facilidad de excepción erosiona la garantía.

## Estructura de un test típico

```python
# tests/unit/core/test_hashing.py

"""Tests for src/aip/core/hashing.py."""

from aip.core.hashing import sha256_hex, jcs_canonicalize


def test_sha256_empty_bytes() -> None:
    """SHA-256 of empty bytes is a known constant."""
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_hex(b"") == expected


def test_sha256_known_string() -> None:
    """SHA-256 of 'AIP' (UTF-8) matches reference value."""
    expected = "8f4a9c0a..."  # pinned reference, generated once
    assert sha256_hex(b"AIP") == expected


def test_jcs_canonicalization_orders_keys() -> None:
    """JCS canonicalization produces keys in lexicographic order."""
    obj = {"b": 1, "a": 2}
    canonical = jcs_canonicalize(obj)
    assert canonical == b'{"a":2,"b":1}'
```

Un test típico es **corto, directo, con una afirmación clara, sin setup innecesario**.

## Integración con CI

CI ejecuta en cada PR:

1. **Lint** con ruff. Errores bloquean el merge.
2. **Type check** con mypy o pyright en strict mode sobre `src/aip/`.
3. **Tests** completos: unit + integration + reproducibility.
4. **Cobertura** medida y comparada contra umbrales.
5. **Verificación de dependencias internas**: no hay ciclos, no se viola la separación de capas del ADR-0030.

Fallo en cualquiera de los cinco bloquea el merge. Sin excepciones rutinarias.

## Lo que NO entra en testing strategy de V1

Para preservar el recorte de alcance:

- ❌ **Performance tests**. V1 es modesto; el rendimiento no es propiedad bajo test.
- ❌ **Fuzzing**. Valioso pero no prioritario en V1.
- ❌ **Mutation testing**. Excesivo bajo bus factor = 1.
- ❌ **Tests de UI/UX**. V1 solo tiene CLI textual.
- ❌ **Tests cross-version exhaustivos**. CI prueba en la versión mínima declarada y en la última estable; otras versiones se asumen.
- ❌ **Tests de carga**. V1 no tiene caso de uso de carga.

Estas categorías pueden introducirse en fases posteriores con ADR específico cuando aplique.

## Consecuencias

**Positivas**
- Suite reproducible bit a bit detecta bugs sutiles en propiedades críticas.
- Prohibición de red en tests garantiza que el proyecto se puede testear sin conexión.
- Cobertura diferenciada refleja honestidad sobre qué importa más.
- Tests funcionan como documentación ejecutable del comportamiento esperado.

**Negativas**
- Umbrales altos en `core/` y `audit/` requieren disciplina sostenida.
- Tests sin red excluyen ciertos modos de prueba útiles en otras industrias.
- Reproducibilidad bit a bit en hashes obliga a cuidar serialización con disciplina.

**Neutras**
- Suite quizá pequeña en V1; crecerá con las fases.

## Declaración de limitaciones

Este ADR **no garantiza**:

- Que la suite detecte todos los bugs. Cobertura no implica corrección.
- Que los tests cubran todos los casos de uso que la audiencia real encuentre.
- Que la suite siga siendo manejable cuando el proyecto crezca; eso depende de disciplina futura.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único:

- La calidad de los tests depende del juicio del único autor de los mismos.
- Casos límite que el mantenedor no anticipa pueden no estar cubiertos.
- La revisión por pares interna sostenida no existe; CI compensa parcialmente.

Mitigación parcial:

- Reproducibility tests detectan regresiones sutiles que un revisor humano podría no notar.
- La separación clara de capas (ADR-0030) reduce la superficie donde un bug puede esconderse.
- La prohibición de dependencias externas reduce el espacio de "tests que pasan por casualidad".

## Trigger de revisión

Este ADR se revisa si:

- Aparece colaborador externo cuyo perfil sugiera prácticas de testing distintas.
- Una fase posterior introduce componentes (búsqueda semántica, OSINT, etc.) cuyos tests requieren políticas distintas.
- Se detecta un modo de fallo recurrente que la estrategia no cubre.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P6, P8.

**Cómo se alinean:**
- **P2 (trazabilidad):** los reproducibility tests son la verificación operativa de P2.
- **P5 (reproducibilidad):** misma razón.
- **P6 (local-first):** prohibición de red en tests garantiza local-first incluso en CI.
- **P8 (documentación):** los tests son documentación ejecutable.

**Tensión:** ninguna nueva.

## Referencias

- pytest documentation.
- pytest-cov documentation.
- hypothesis documentation.
- ruff documentation.
- mypy / pyright documentation.
- RFC 8785 (JSON Canonicalization Scheme).
- ADR-0016 (Versionado y direccionamiento por contenido).
- ADR-0030 (Repository Layout): este ADR depende de su organización de carpetas.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
