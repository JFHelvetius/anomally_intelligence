# ADR-0030: Repository Layout — estructura física del repositorio para V1

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0017, ADR-0023, ADR-0029, ADR-0031

---

## Contexto

Hasta este ADR, el repositorio contiene exclusivamente documentación:

```
anomaly-intelligence-platform/
├── LICENSE
├── MAINTAINERS.md
├── PROJECT_STATUS.md
├── README.md
└── docs/
    ├── adr/...
    ├── models/        (vacío)
    ├── phase-1/...
    └── reviews/...
```

Antes de escribir la primera línea de código, conviene decidir:

- Dónde vive el código del paquete `aip`.
- Dónde viven los tests.
- Dónde viven los scripts auxiliares, fixtures, datos de ejemplo.
- Cómo se separan componentes lógicos del paquete sin caer en sobre-modularización prematura.
- Qué convenciones se aplican a nombres, imports, y exportación pública.

Una decisión tardía sobre layout es una refactorización costosa. Una decisión temprana, formalizada, evita la refactorización.

ADR-0023 (Scope Reduction) compromete tres comandos: `evidence ingest`, `evidence show`, `archive verify`. ADR-0017 declara API Python como fuente de verdad semántica con CLI delgada encima. ADR-0029 fija Python 3.11+ con uv y pyproject.toml. Este ADR define la geometría física que materializa esos compromisos.

## Decisión

El repositorio adopta el **src layout estándar de Python** con un solo paquete distribuible (`aip`) y tres subpaquetes que reflejan la separación natural de V1:

```
anomaly-intelligence-platform/
├── LICENSE
├── MAINTAINERS.md
├── PROJECT_STATUS.md
├── README.md
├── pyproject.toml                 # PEP 621, dependencias, entry points
├── uv.lock                        # lockfile reproducible
├── ruff.toml                      # linting/format config (o sección en pyproject)
├── .gitignore
├── .python-version                # 3.11 mínimo declarado
├── src/
│   └── aip/                       # único paquete distribuible
│       ├── __init__.py            # exporta API pública estable
│       ├── _version.py            # versión del software
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── __main__.py        # entry point `python -m aip`
│       │   ├── main.py            # dispatch principal de la CLI
│       │   ├── evidence_commands.py
│       │   └── archive_commands.py
│       ├── core/                  # modelo de evidencia y dominio
│       │   ├── __init__.py
│       │   ├── hashing.py         # SHA-256, BLAKE3 opcional, JCS
│       │   ├── identifiers.py     # ULID, aip: URI
│       │   ├── evidence.py        # tipo Evidence, EvidenceKind, EvidenceStatus
│       │   ├── source.py          # tipo Source, AuthorityLevel, SourceKind
│       │   ├── provenance.py      # Provenance, ProvenanceStep
│       │   ├── authentication.py  # AuthenticationAssessment, AuthStatus
│       │   └── actor.py           # Actor mínimo
│       ├── storage/               # persistencia local
│       │   ├── __init__.py
│       │   ├── caos.py            # content-addressed object store en filesystem
│       │   ├── tables.py          # capa Parquet/DuckDB
│       │   ├── manifest.py        # ArchiveManifest + cómputo
│       │   └── layout.py          # paths convencionales del archive
│       ├── audit/                 # audit log
│       │   ├── __init__.py
│       │   ├── log.py             # append-only con hash chain
│       │   └── verify.py          # verificación de la cadena
│       └── errors.py              # jerarquía de excepciones tipadas
├── tests/
│   ├── conftest.py                # fixtures pytest compartidos
│   ├── data/                      # fixtures físicos versionados (pequeños)
│   │   └── README.md              # describe qué hay y por qué
│   ├── unit/
│   │   ├── core/
│   │   ├── storage/
│   │   ├── audit/
│   │   └── cli/
│   ├── integration/
│   │   └── demo_pipeline_test.py  # PDF → ingest → show → verify
│   └── reproducibility/
│       └── manifest_hash_test.py  # mismo input → mismo hash
├── docs/
│   ├── adr/
│   ├── models/
│   ├── phase-1/
│   └── reviews/
└── scripts/                       # utilidades auxiliares; no código de producción
    └── README.md                  # describe qué hay
```

Esta estructura es deliberadamente compacta: cuatro subpaquetes en `src/aip/`, una raíz limpia, un solo paquete distribuible.

## Justificación

### Por qué src layout y no flat layout

Un `src/` separado garantiza que los tests **no importan accidentalmente** desde el directorio del proyecto sin pasar por la instalación del paquete. Eso obliga a que la suite de tests refleje el comportamiento real del paquete instalado, no la geometría local del checkout. Es defensa estructural contra el bug clásico "funciona en el repo pero no cuando se instala".

### Por qué un solo paquete `aip` y no múltiples

Múltiples paquetes (e.g., `aip-core`, `aip-cli`, `aip-storage`) introducen overhead de empaquetado, versionado independiente, dependencias internas declaradas. Para V1 con 8 piezas implementadas, no hay beneficio. La unificación es defensa contra over-engineering bajo bus factor = 1.

Si en fases posteriores la separación se justifica (paquete `aip-osint` opcional, paquete `aip-graph` opcional), un ADR de enmienda la introduce con motivación concreta.

### Por qué cuatro subpaquetes (`cli`, `core`, `storage`, `audit`)

Los cuatro reflejan la **separación natural por responsabilidad** de los 8 componentes comprometidos en V1:

- `core` → modelo de dominio (4–6 tipos). Sin I/O, sin filesystem, sin dependencias pesadas. Es la pieza más fácil de testear unitariamente y la que define la semántica.
- `storage` → toda la persistencia. CAOS, Parquet, manifest. Es la pieza que toca disco.
- `audit` → audit log con hash chain. Aislado porque su política (append-only, sin mutación) merece código separado.
- `cli` → adapter delgado sobre `core` + `storage` + `audit`. Su test confirma que la CLI **no añade lógica**, solo orquesta.

Esta separación responde a ADR-0017 ("API Python como fuente de verdad, CLI delgado encima") materializada físicamente: `cli/` no implementa lógica de dominio.

### Por qué `errors.py` en raíz de `aip/`

Las excepciones cruzan capas. Centralizarlas en raíz evita ciclos de import entre subpaquetes y hace clara la superficie de errores pública.

### Por qué `__main__.py` en `cli/`

Permite `python -m aip` además de la entry point del console_script. Útil para entornos donde la entry point no está en `PATH`.

### Por qué `tests/` fuera de `src/`

Práctica estándar Python. Tests no se distribuyen con el paquete. La separación es nítida.

### Por qué tres categorías de tests (`unit/`, `integration/`, `reproducibility/`)

Refleja el ADR-0031 (Testing Strategy):

- `unit/` → tests rápidos, aislados, deterministas.
- `integration/` → demo de cierre F1 ejecutada como test automatizado. Confirma que pipeline completo funciona.
- `reproducibility/` → tests específicos de bit-a-bit hash y manifest. Confirman P5.

La separación física permite ejecutar subsets sin coste cognitivo.

### Por qué `tests/data/` con README explicativo

Cualquier fixture binario versionado lleva justificación. Sin README, los fixtures se vuelven artefactos opacos.

### Por qué `scripts/` separado y declarado no-producción

Cualquier utilidad auxiliar (herramientas de desarrollo, scripts de empaquetado, generadores de fixtures) vive en `scripts/`. No se distribuye, no entra en el paquete, no está sujeta al mismo nivel de tests. La separación es honesta: cierto código tiene status de "ayuda al mantenedor", no de "código de producción".

V1 puede empezar con `scripts/` vacío salvo su README.

### Por qué `.python-version`

Compatibilidad con pyenv y herramientas que respetan el fichero. Declaración secundaria de la versión mínima (la primaria está en `pyproject.toml`).

### Por qué no carpeta `notebooks/`

Notebooks no son código de producción. Si surgen notebooks (exploración, demostración), viven en `scripts/notebooks/` o en repositorio separado. No se mezclan con código de paquete.

### Por qué no carpeta `examples/` en V1

Los ejemplos viven en la documentación de la demo (`docs/phase-1/`). Una carpeta `examples/` separada añade superficie sin necesidad en V1.

## Convenciones

### C1. Nombres de módulos

- snake_case para módulos.
- Nombres descriptivos sin abreviaturas crípticas: `provenance.py`, no `prov.py`.
- Singular para módulos que definen un tipo principal: `evidence.py`, no `evidences.py`.

### C2. API pública vs. privada

- Símbolos públicos exportados desde `aip/__init__.py`.
- Símbolos internos viven con prefijo `_` o en módulos no re-exportados.
- Re-exportación de un símbolo desde múltiples lugares se documenta como conveniencia, no como duplicación.

### C3. Imports

- Imports absolutos siempre: `from aip.core.evidence import Evidence`, no `from .evidence import Evidence` entre subpaquetes.
- Imports relativos permitidos solo dentro del mismo subpaquete (vecinos cercanos).
- `__init__.py` de un subpaquete re-exporta los símbolos públicos del subpaquete.

### C4. Tipos y anotaciones

- Anotaciones obligatorias en toda función pública (firma + retorno).
- Anotaciones obligatorias en atributos públicos de clases.
- Modelos de dominio (Evidence, Source, etc.) usan dataclasses o pydantic; la elección concreta se decide al implementar con criterio: dataclasses si la validación necesaria es mínima; pydantic si necesitamos validación al construir desde JSON.

### C5. Organización del orden dentro de un módulo

Cuando un módulo es no trivial, el orden esperado:

1. Docstring del módulo.
2. Imports (stdlib → terceros → propios).
3. Constantes.
4. Tipos auxiliares (enums, type aliases).
5. Clases principales.
6. Funciones de alto nivel.
7. Helpers privados (prefijo `_`).

Esta convención reduce la fricción de lectura.

### C6. Tests reflejan el árbol de `src/`

`tests/unit/core/test_evidence.py` testea `src/aip/core/evidence.py`. La correspondencia 1:1 es deseable pero no obligatoria.

### C7. Sin estado global

Ningún módulo expone singleton mutable (sin `current_archive`, sin caches globales modificables). El handle del archivo se pasa como argumento o se construye explícitamente. Esto facilita tests y operaciones multi-archive (un usuario operando dos archivos a la vez).

### C8. Sin reflexión mágica

Sin metaclasses propias, sin decoradores que muten clases en tiempo de import, sin lookups dinámicos sobre namespaces. Python permite muchas cosas; este proyecto se mantiene en el subconjunto explícito por defecto. Excepciones se documentan.

### C9. Encoding y line endings

- UTF-8 sin BOM en todos los ficheros de texto.
- LF como line ending en todos los ficheros de código y documentación.
- `.gitattributes` declara la normalización.

## Separación de módulos: principios

### S1. `core/` no depende de `storage/` ni de `cli/` ni de `audit/`

`core/` define el modelo de dominio. Es la pieza más pura. Si `core/` depende de capas externas, la testabilidad y la reusabilidad colapsan.

### S2. `storage/` puede depender de `core/`

`storage/` persiste tipos de `core/`. Esa dirección de dependencia es legítima.

### S3. `audit/` puede depender de `core/` y `storage/`

`audit/` lee/escribe usando primitivas de storage y referencia tipos de core.

### S4. `cli/` depende de todo lo demás

`cli/` es el adapter. Importa de los tres subpaquetes y orquesta.

### S5. Sin dependencias circulares

Cualquier import circular detectado en CI es bug, no estilo.

Estos cinco principios son verificables automáticamente con herramientas (e.g., `import-linter`). La verificación se integra en CI conforme a ADR-0031.

## Alineación con alcance V1

Esta estructura **materializa exactamente** los 8 componentes comprometidos por ADR-0023:

| Componente V1 (ADR-0023)          | Vive en                                 |
|-----------------------------------|-----------------------------------------|
| CLI con 3 comandos                | `src/aip/cli/`                          |
| API Python equivalente            | `src/aip/core/`, `src/aip/storage/`     |
| Modelo de evidencia (ADR-0006)    | `src/aip/core/evidence.py`              |
| Modelo de fuente y procedencia    | `src/aip/core/source.py`, `provenance.py` |
| CAOS en filesystem                | `src/aip/storage/caos.py`               |
| Almacenamiento Parquet            | `src/aip/storage/tables.py`             |
| ArchiveManifest y URI `aip:`      | `src/aip/storage/manifest.py`, `src/aip/core/identifiers.py` |
| Audit log con hash chain          | `src/aip/audit/`                        |

No hay módulos para componentes diferidos (`claim/`, `hypothesis/`, `graph/`, `temporal/`, `spatial/`, `osint/`, `search/`, `http/`, `enclave/`, `llm/`). Su ausencia es deliberada.

## Lo que no entra en V1

Para preservar la disciplina del recorte:

- **Sin `src/aip/claim/`**. Diferido por ADR-0023.
- **Sin `src/aip/hypothesis/`**. Diferido por ADR-0023.
- **Sin `src/aip/graph/`**. Diferido por ADR-0023.
- **Sin `src/aip/temporal/`** ni `src/aip/spatial/`. Diferidos por ADR-0023.
- **Sin `src/aip/osint/`**. Diferido por ADR-0023.
- **Sin `src/aip/search/`**. Diferido por ADR-0023.
- **Sin `src/aip/http/`**. Diferido por ADR-0023.
- **Sin `src/aip/enclave/`**. Diferido por ADR-0023.
- **Sin `src/aip/llm/`**. Diferido por ADR-0023.

Cuando estos componentes entren en su fase correspondiente, su layout se decidirá por ADR de enmienda específico. Por defecto, cada uno será un subpaquete adicional bajo `src/aip/`. Si alguno crece a paquete distribuible separado, requerirá decisión explícita.

## Consecuencias

**Positivas**
- Estructura clara, audita por cualquier lector externo.
- Compatible con herramientas estándar de Python (pip install, uv, ruff, mypy, pytest).
- Dependencias internas explícitas y verificables.
- Sin sobreingeniería: cuatro subpaquetes para 8 componentes.

**Negativas**
- Cualquier reorganización futura (e.g., extraer `core/` como paquete propio) tendrá coste de refactorización.
- La cardinalidad pequeña de subpaquetes puede sentirse "incompleta" comparada con proyectos similares en otras industrias.

**Neutras**
- La separación física no impide cohesión lógica: nada impide que un tipo de `core/` y su persistencia en `storage/` evolucionen juntos en un mismo PR.

## Declaración de limitaciones

Este ADR **no decide**:

- Si los modelos de dominio usan dataclasses o pydantic (decisión de implementación local).
- Versiones exactas de librerías (decisión del `uv.lock`).
- Política de versionado SemVer del paquete (cubierto en ADR-0016 a nivel de esquema; la versión del paquete sigue convención SemVer estándar implícita).

Estas decisiones se documentan al implementar.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único:

- La disciplina de respetar S1–S5 depende de la auto-disciplina del mantenedor.
- Sin revisión por pares interna, una dependencia circular o un acoplamiento inadecuado puede colarse hasta CI.
- Mitigación: la verificación automática de imports en CI compensa parcialmente la falta de revisión humana.

## Trigger de revisión

Este ADR se revisa si:

- Alguno de los componentes diferidos entra en fase de implementación (cada uno trae su propio ADR de layout).
- Surge necesidad de paquetes distribuibles separados.
- Aparece colaborador externo cuyo perfil sugiera reorganización beneficiosa.

## Alineación con ADR-0000

**Propiedades afectadas:** P5, P6, P8.

**Cómo se alinean:**
- **P5 (reproducibilidad):** layout claro facilita reproducir el build desde el lockfile.
- **P6 (local-first):** ninguna parte de la estructura depende de servicios externos.
- **P8 (documentación):** este ADR documenta una decisión hasta ahora no formalizada.

**Tensión:** ninguna nueva.

## Referencias

- Python Packaging Authority. *Packaging Python Projects* (src layout).
- PEP 621 (pyproject.toml metadata).
- import-linter. Verificación automática de dependencias entre módulos.
- `orbital-sentinel` ADR-0003 (src layout + uv) como prior art coherente.

---

## Historial de enmiendas

### Enmienda al pie — 2026-06-06 (post-cierre F1)

Durante la implementación de V1 (commits Pre-F1 → `v0.1.0`), el layout real divergió del árbol descrito arriba en cinco puntos. Ninguna divergencia altera S1–S5 ni la separación por responsabilidad; se documentan aquí como **enmienda al pie** en vez de abrir ADR de levantamiento porque las cinco son consolidaciones que reducen superficie (no la amplían) y todas son **observables en el árbol committeado** de `v0.1.0`.

**E1. `src/aip/archive.py` a nivel raíz del paquete.**
La fachada de alto nivel que orquesta ingest/show/verify (consumida por `cli/` y por la API Python pública de ADR-0017) vive en `src/aip/archive.py`, no en un subpaquete. Razón: el módulo es delgado (compone `core/` + `storage/` + `audit/`) y meterlo en un subpaquete propio introduciría un nodo vacío sin ganar separación lógica. Conserva S1–S5: `archive.py` depende de las tres capas inferiores, ninguna depende de él.

**E2. `src/aip/__main__.py` a nivel raíz (no en `cli/`).**
Para que `python -m aip` funcione, el shim de entry point debe vivir en la raíz del paquete distribuible, no en un subpaquete. El módulo es de **dos líneas** y delega a `aip.cli.main:main`. `src/aip/cli/__main__.py` no existe; el ADR original lo ubicaba por error allí.

**E3. Consolidaciones de `core/` por ADR-0023.**
ADR-0023 §V1.3 consolidó tipos que el árbol original separaba:
- `AuthenticationAssessment` queda **embebido** en `evidence.py` (sin `authentication.py`).
- `Actor` queda **embebido** en `source.py` (sin `actor.py`).
La tabla `authentication_assessments` se reserva en `V1_TABLES` (ADR-0015) pero permanece vacía en V1; ver nota en `src/aip/storage/layout.py:38`.

**E4. CAOS implementado dentro de `layout.py` (no en `caos.py`).**
Las primitivas del Content-Addressed Object Store (`caos_path_for`, `caos_relative_uri_for`, `ensure_archive_layout`) viven en `storage/layout.py` junto con las constantes de paths canónicos, no en `storage/caos.py`. Razón: el CAOS V1 es **convención de paths sin estado**, no un servicio con ciclo de vida propio. Separar `caos.py` introduciría import circular con `layout.py` o duplicación de constantes. Si en F2+ aparece lógica con estado (locking, GC, dedup), la división se reabrirá por ADR.

**E5. Convención de naming de tests: `test_*.py` (no `*_test.py`).**
El árbol original mostraba `demo_pipeline_test.py` y `manifest_hash_test.py`. La convención efectiva, alineada con el default de pytest y con C6 ("Tests reflejan el árbol de `src/`"), es **prefijo**: `test_demo_pipeline.py`, `test_manifest_hash.py`. No requiere configuración custom en `pyproject.toml`.

**E6. `docs/models/` permanece vacío.**
El directorio existe (heredado del árbol original) pero V1 no genera modelos UML/ER separados: el modelo canónico vive en los tipos Pydantic de `src/aip/core/`. ADR-0024 §formato canónico hace de los `schema_hash` la fuente de verdad del esquema, no de diagramas. El directorio se conserva por simetría con futuros ADRs de F2+ que sí podrían poblarlo (por ejemplo, esquemas de hipótesis o grafo).

**Alineación P5 / P8:** ninguna de E1–E6 mueve bytes hasheados (los `EXPECTED_*_HASH` pinned se mantienen idénticos). E1–E5 son verificables leyendo `src/aip/` y `tests/`. E6 es un no-op observable como directorio vacío.

**No requiere ADR de enmienda formal porque:** ninguna divergencia introduce dependencias nuevas, viola S1–S5, ni amplía el alcance V1 más allá de lo comprometido por ADR-0023. Son simplificaciones efectuadas durante implementación y consignadas aquí para que cualquier lector del ADR encuentre el árbol real sin trabajar con un mapa obsoleto.

### Enmienda al pie — 2026-06-06 (E7, post-ADR-0032)

ADR-0032 (Authentication Assessment Engine v1) introdujo un **quinto subpaquete** bajo `src/aip/`: `analysis/`. La estructura original de este ADR-0030 declaraba cuatro subpaquetes (`cli/`, `core/`, `storage/`, `audit/`); la realidad actual es:

```
src/aip/
├── analysis/   ← nuevo (ADR-0032): capa derivada e inmutable
├── audit/
├── cli/
├── core/
└── storage/
```

**Por qué `analysis/` es una capa propia y no parte de `core/`:** `core/` contiene el modelo de **verdad observada** (Evidence, Source, Provenance). Confundir verdad con interpretación derivada es exactamente lo que ADR-0000 prohíbe arquitectónicamente. Un subpaquete propio materializa esa separación: un lector del código sabe inmediatamente que un módulo en `analysis/` es derivado y removible, no fuente.

**Coherencia con S1–S5 (separación de dependencias):**
- `analysis/` puede depender de `core/` (para validar tipos) y de `storage/` (para leer tablas). Idéntico patrón al de `audit/` (S3). Ver S6 propuesto a continuación.
- `analysis/` **no** depende de `cli/` ni de `audit/`. Esa dirección no tiene sentido lógico ni práctico.
- `core/` y `storage/` siguen sin depender de `analysis/`. Mantiene S1, S2, S5.

**S6 (propuesto y vigente desde 2026-06-06):** `analysis/` puede depender de `core/` y `storage/`. Ninguna otra capa depende de `analysis/`. Borrar `analysis/` no rompe el resto del paquete — es la materialización física de la garantía G4 de ADR-0032 (removibilidad).

**Por qué `analysis/` no se mete en `cli/assessment_commands.py`:** la regla determinista `classify()` y el modelo `AuthenticationAssessment` son lógica de dominio derivado, no UX. La CLI los usa pero no los define. Esta separación permite que la regla evolucione (por ADR de enmienda al motor) sin tocar el CLI, y permite que la API Python exponga el motor sin obligar al caller a entrar por argparse.

**Tabla actualizada del §"Por qué cuatro subpaquetes":** ahora son **cinco**. Cuando ADR-0032 cubre el subpaquete entero, la celda "deja de ser cuatro" del ADR original se reinterpreta como "deja de ser N", donde N = 4 + cantidad de capas derivadas autorizadas por ADRs posteriores. ADR-0023 §congelación V1 sigue activa: cualquier futura capa derivada (e.g., `analysis/temporal_review/`) requerirá su propio ADR de levantamiento puntual.

**E7 no muta bytes hasheados:** `EXPECTED_DEMO_MANIFEST_HASH`, `EXPECTED_EMPTY_MANIFEST_HASH`, los 5 `schema_hashes` y los pares JCS canónicos siguen idénticos. El árbol de `src/` no entra en ninguna canonicalización.

### Enmienda al pie — 2026-06-07 (E8, post-ADR-0033)

ADR-0033 (Evidence Graph V1) introdujo un **sexto subpaquete** bajo `src/aip/`: `graph/`. La estructura actual es:

```
src/aip/
├── analysis/   ← ADR-0032 (capa derivada de assessments)
├── audit/
├── cli/
├── core/
├── graph/      ← nuevo (ADR-0033): grafo de procedencia derivado
└── storage/
```

**Por qué `graph/` es subpaquete propio y no parte de `analysis/`:** `analysis/` aloja productores de artefactos derivados (cada `AuthenticationAssessment` es un artefacto que el operador decide producir corriendo `aip assess-authentication`). `graph/` aloja **lectura estructural** del archive: el grafo no es un artefacto que se "decide producir"; es una vista del estado actual que se reconstruye en cada llamada. Mezclar ambos en un mismo subpaquete confundiría dos tipos de operación: "derivar y persistir" vs. "leer y proyectar".

**Coherencia con S1–S6 y propuesta S7:**

- `graph/` puede depender de `core/`, `storage/` y `analysis/`. Lee tipos de las tres capas para construir nodos y aristas.
- `graph/` **no** depende de `audit/` ni de `cli/`. Esa dirección no tiene sentido lógico (el grafo no se audita; el grafo es proyección).
- `core/`, `storage/`, `audit/` y `analysis/` siguen sin depender de `graph/`. Mantiene la propiedad ya declarada en S1, S2, S5, S6: ninguna capa core o derivada productora depende de la capa de proyección.

**S7 (propuesto y vigente desde 2026-06-07):** `graph/` puede depender de `core/`, `storage/` y `analysis/`. Ninguna otra capa depende de `graph/`. Borrar `graph/` no rompe el resto del paquete — materialización física de la garantía G2 de ADR-0033 (removibilidad).

**Por qué no usar `aip.knowledge_graph` o similar:** ADR-0011 reserva el dominio "knowledge graph" completo (personas, organizaciones, eventos, etc.) y sigue diferido por ADR-0023. Usar ese nombre invitaría a confusión sobre alcance. `graph/` con ADR-0033 cubre **estrictamente** procedencia entre Evidence/Source/Assessment; el grafo de conocimiento real seguirá requiriendo levantamiento explícito de ADR-0011.

**Tabla actualizada del §"Por qué cuatro subpaquetes":** ahora son **seis**. Cualquier futura capa de proyección o derivación seguirá la misma regla: subpaquete propio, ADR de levantamiento puntual, S-rule específica que documente direcciones de dependencia.

**E8 no muta bytes hasheados:** los hashes pinned (5 schema_hashes, empty manifest, demo manifest, demo+assessment manifest, audit chain, JCS pairs) siguen idénticos. El árbol de `src/` no entra en ninguna canonicalización.

### Enmienda al pie — 2026-06-07 (E9, post-ADR-0034)

ADR-0034 (Impact Analysis Engine V1) introdujo un **séptimo subpaquete** bajo `src/aip/`: `impact/`. La estructura actual es:

```
src/aip/
├── analysis/   ← ADR-0032 (capa derivada de assessments)
├── audit/
├── cli/
├── core/
├── graph/      ← ADR-0033 (grafo de procedencia derivado)
├── impact/     ← nuevo (ADR-0034): análisis de impacto downstream
└── storage/
```

**Por qué `impact/` es subpaquete propio y no parte de `graph/`:** `graph/` provee la primitiva estructural (`EvidenceGraph`, queries genéricas). `impact/` consume esa primitiva con una intención específica: responder una sola pregunta operativa ("¿qué se queda sin respaldo si esto desaparece?"). Mezclar primitiva y aplicación borraría el contrato declarativo del grafo y mezclaría dos niveles de abstracción.

**S8 (propuesto y vigente desde 2026-06-07):** `impact/` puede depender de `core/`, `graph/` y de `aip._version`. Ninguna otra capa depende de `impact/`. Borrar `impact/` deja al resto del paquete funcional, incluido `graph/` — materialización física de la garantía G3 de ADR-0034 (removibilidad).

**Por qué no `impact_analysis/` o nombre largo:** ADR-0034 ya documenta el alcance (análisis de impacto downstream sin scoring). El nombre corto deja el ADR como referencia.

**Tabla actualizada del §"Por qué cuatro subpaquetes":** ahora son **siete**. El patrón ya es claro: cada capa derivada con propósito específico vive en su subpaquete propio, con regla S-rule de dependencias documentada, y permanece removible bit a bit.

**E9 no muta bytes hasheados:** los hashes pinned siguen idénticos. El árbol de `src/` no entra en ninguna canonicalización.

### Enmienda al pie — 2026-06-07 (E10, post-ADR-0035)

ADR-0035 (Context Assembly Layer V1) introdujo un **octavo subpaquete** bajo `src/aip/`: `context/`. La estructura actual es:

```
src/aip/
├── analysis/   ← ADR-0032 (capa derivada de assessments)
├── audit/
├── cli/
├── context/    ← nuevo (ADR-0035): capa de composición/agregación
├── core/
├── graph/      ← ADR-0033 (grafo de procedencia derivado)
├── impact/     ← ADR-0034 (análisis de impacto downstream)
└── storage/
```

**Por qué `context/` es subpaquete propio:** las capas derivadas anteriores (`analysis/`, `graph/`, `impact/`) son **productoras** de información derivada. `context/` es la primera capa **agregadora**: no produce información nueva, compone outputs canónicos de productores existentes. Mezclar agregación con producción borraría una distinción arquitectónica importante (ADR-0035 §G3).

**S9 (propuesto y vigente desde 2026-06-07):** `context/` puede depender de `core/`, `analysis/`, `graph/`, `impact/`, `storage/` y de `aip._version`. Ninguna otra capa depende de `context/`. Borrar `context/` deja al resto del paquete funcional — materialización física de la garantía G2 de ADR-0035 (removibilidad).

**Propiedad arquitectónica nueva expuesta por S9:** `context/` es la única capa que depende de **todas** las capas derivadas. Esta posición topológica refleja su rol declarado: agregación pura sobre productores existentes.

**E10 no muta bytes hasheados:** los hashes pinned siguen idénticos. El árbol de `src/` no entra en ninguna canonicalización. El nuevo `EXPECTED_DEMO_CONTEXT_BUNDLE_HASH` pinned en `tests/reproducibility/test_manifest_hash.py` describe un artefacto derivado nuevo (el bundle), no muta ninguno preexistente.

### Enmienda al pie — 2026-06-07 (E11, post-ADR-0036)

ADR-0036 (Investigation Workspace V1) introdujo un **noveno subpaquete** bajo `src/aip/`: `workspace/`. La estructura actual es:

```
src/aip/
├── analysis/   ← ADR-0032 (capa derivada de assessments)
├── audit/
├── cli/
├── context/    ← ADR-0035 (capa de composición/agregación)
├── core/
├── graph/      ← ADR-0033 (grafo de procedencia derivado)
├── impact/     ← ADR-0034 (análisis de impacto downstream)
├── storage/
└── workspace/  ← nuevo (ADR-0036): índice reproducible de investigación
```

**Por qué `workspace/` es subpaquete propio:** las capas derivadas anteriores (`analysis/`, `graph/`, `impact/`, `context/`) producen o componen información derivada del archive. `workspace/` representa **metadatos de investigación**: una colección de referencias a artefactos derivados, sin ejecutar nuevos análisis. Mezclar metadatos investigativos con productores/agregadores difumina una distinción importante.

**S10 (propuesto y vigente desde 2026-06-07):** `workspace/` puede depender de `core/` (para `hashing`), `storage/` (para `layout` + `ArchiveManifest`) y `errors`. **No depende** de `analysis/`, `graph/`, `impact/`, ni `context/` — éste es el sello arquitectónico de G3 (no ejecuta motores). El test `test_workspace_imports_no_engines` verifica vía AST que ningún módulo de `workspace/` importa de las capas derivadas analíticas.

**Topología nueva:** `workspace/` es la primera capa derivada de **metadatos** (no de información). Su lugar en el árbol refleja esta diferencia: a la misma profundidad que las capas productoras, pero con dependencias mucho más acotadas.

**Persistencia de workspaces:** los archivos JSON de workspace se persisten en `<archive>/workspaces/<id>.json` — un directorio nuevo bajo la raíz del archive. **No entra en `V1_TABLES`, ni en `compute_manifest`, ni en `is_archive`**. Por construcción, `archive_manifest_hash` es invariante ante operaciones de workspace. Test `test_workspace_persistence_does_not_modify_archive_manifest` lo confirma bit a bit.

**E11 no muta bytes hasheados:** los hashes pinned (incluido `EXPECTED_DEMO_CONTEXT_BUNDLE_HASH`) siguen idénticos. El árbol de `src/` no entra en ninguna canonicalización. El directorio `<archive>/workspaces/` no entra en la canonicalización del manifest.

### Enmienda al pie — 2026-06-07 (E12, post-ADR-0037/0038/0039)

ADR-0037/0038/0039 introdujeron tres subpaquetes simultáneamente bajo `src/aip/`:

```
src/aip/
├── ...
├── workspace/   ← ADR-0036
├── timeline/    ← ADR-0037 (vista cronológica)
├── snapshot/    ← ADR-0038 (congelación reference-only)
└── diff/        ← ADR-0039 (set-difference puro)
```

**S11 (vigente desde 2026-06-07):** `timeline/` puede depender de `core/`, `storage/`, `analysis/`, `workspace/` y `errors`. **No** depende de `graph/`, `impact/`, `context/`, `snapshot/`, `diff/`.

**S12 (vigente desde 2026-06-07):** `snapshot/` puede depender de `core/`, `workspace/`, `timeline/` y `errors`. **No** depende de `graph/`, `impact/`, `context/`, `diff/`.

**S13 (vigente desde 2026-06-07):** `diff/` puede depender de `core/`, `snapshot/` y `errors`. **No** depende de `graph/`, `impact/`, `context/`, `analysis/`, `timeline/` (depende sólo del snapshot final, no del timeline subyacente).

**Cadena de dependencias topológica (estricta, nunca al revés):**
`timeline → workspace → ...`
`snapshot → timeline → workspace → ...`
`diff → snapshot → timeline → workspace → ...`

Verificado por tests AST inspect en cada subpaquete.

**Persistencia:** los tres usan directorios periféricos bajo el archive root (`<archive>/timelines/`, `<archive>/snapshots/`) que **no entran** en `V1_TABLES` ni en `compute_manifest`. `archive_manifest_hash` es invariante ante operaciones de timeline/snapshot/diff.

**E12 no muta bytes hasheados:** los hashes pinned siguen idénticos.

### Enmienda al pie — 2026-06-07 (E13, post-ADR-0040)

ADR-0040 (Investigation Justification Engine V1) introdujo un **décimo subpaquete** bajo `src/aip/`:

```
src/aip/
├── ...
├── workspace/
├── timeline/
├── snapshot/
├── diff/
└── justification/   ← nuevo (ADR-0040): cadena deductiva categorizada
```

**S14 (vigente desde 2026-06-07):** `justification/` puede depender de `core/`, `storage/`, `analysis/`, `graph/`, `workspace/` y `errors`. **No** depende de `impact/`, `context/`, `timeline/`, `snapshot/`, `diff/`. Tampoco depende de librerías ML/red. AST inspect lo verifica.

**Persistencia:** `<archive>/justifications/<id>.json` — directorio periférico, no entra en `V1_TABLES` ni en `compute_manifest`. `archive_manifest_hash` invariante ante operaciones de justification.

**Integración con ADR-0039 sin modificar su subpaquete:** el subcomando `aip diff justifications` se añade a `src/aip/cli/diff_commands.py` (capa CLI, no capa de modelo). El subpaquete `aip.diff` no se modifica — el CLI orquesta la composición.

**E13 no muta bytes hasheados:** los hashes pinned siguen idénticos.
