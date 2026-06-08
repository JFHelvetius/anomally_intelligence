# ADR-0029: Runtime Language Decision — Python 3.11+ como lenguaje del runtime

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0003, ADR-0015, ADR-0017, ADR-0023, ADR-0026

---

## Contexto

Varios ADRs anteriores asumen implícitamente Python como lenguaje del runtime:

- ADR-0003 menciona "el proyecto se ejecuta en Python (decisión a confirmar en ADR posterior sobre lenguaje)".
- ADR-0015 elige DuckDB embebido y Parquet, ecosistema dominado por Python para data analytics.
- ADR-0017 declara "API Python como fuente de verdad semántica".
- ADR-0023 (Scope Reduction) compromete una CLI `aip` y una API Python equivalente para V1.

La decisión está latente pero no formalizada. Sin ADR explícito:

- Un colaborador podría proponer migración o multi-lenguaje sin trigger arquitectónico claro.
- Las decisiones de versión mínima del runtime, gestor de entornos y herramientas asociadas no tienen anclaje documentado.
- La auditabilidad del compromiso de lenguaje (P5 reproducibilidad, P6 local-first) queda implícita.

Este ADR formaliza Python como lenguaje del runtime, fija versión mínima, y declara las implicaciones de mantenimiento bajo bus factor = 1.

## Decisión

El proyecto adopta **Python 3.11 o superior** como lenguaje único del runtime para todo el código de producción de AIP en V1 y, salvo ADR de supersesión, en fases posteriores.

El gestor de entornos canónico es **uv** (https://github.com/astral-sh/uv), con lockfile reproducible (`uv.lock`). La especificación del proyecto vive en `pyproject.toml` con metadatos PEP 621.

Componentes complementarios al lenguaje (no son alternativas, son ecosistema):

- **Runtime CPython** como referencia. Otros intérpretes (PyPy) son aceptables si pasan los tests; no se garantizan.
- **uv** para gestión de entornos y lockfile (ADR-0003 P5).
- **pyproject.toml** como única fuente de metadatos del proyecto.
- **ruff** para linting y format (open source, único proceso, suficientemente rápido para no añadir fricción).
- **pytest** para tests (ver ADR-0031).
- **mypy** o **pyright** para chequeo de tipos estáticos. La elección concreta queda a discreción operativa; ambos producen el mismo nivel de garantía.

## Justificación

### Por qué Python

Cinco razones convergentes:

**1. Audiencia primaria del proyecto.**
La audiencia primaria declarada en ADR-0000 (investigadores académicos, periodistas, archivistas, organizaciones civiles) opera mayoritariamente en Python para análisis. Adoptar Python reduce barreras de adopción y permite integración fluida con notebooks, pipelines existentes y herramientas estándar (pandas, polars, Arrow, scikit-learn, geopandas, etc.).

**2. Ecosistema de datos.**
Los formatos y motores comprometidos en V1 (Parquet, DuckDB) tienen su mejor soporte en Python. Los SDKs son maduros, mantenidos y open source. Las alternativas (Rust con polars-rs, Go con Arrow-go) son más jóvenes y producen mayor fricción.

**3. Suficiencia para V1.**
V1 es modesto (ADR-0023): tres comandos, ingestión, hash, audit log, verificación. Python cubre estos requisitos con holgura. Las preocupaciones de rendimiento que motivarían lenguajes compilados (Rust, Go) no aplican a este alcance.

**4. Coherencia con bus factor = 1.**
Bajo mantenedor único part-time (ADR-0026), la elección de lenguaje familiar es defensa estructural contra fricción de mantenimiento. El mantenedor único declara competencia razonable en Python; introducir Rust o Go añadiría coste cognitivo sin beneficio operativo en V1.

**5. Local-first (P6) y coste cero (P7).**
Python, uv, ruff, pytest, mypy son todos open source con licencias permisivas, instalables localmente, sin dependencia de servicios remotos. El stack respeta P6 y P7 sin excepciones.

### Por qué Python 3.11 como mínimo

Cuatro razones:

**1. PEP 657 (Fine-grained error locations).** Trazas de error con localización a nivel de expresión. Útil para depuración en proyecto que prioriza honestidad de procedencia.

**2. PEP 654 (Exception groups).** Permite agregar y manejar excepciones múltiples de forma estructurada. Útil en `aip archive verify` cuando múltiples blobs pueden fallar verificación.

**3. PEP 680 (`tomllib` en stdlib).** Lectura de TOML sin dependencia externa, lo que reduce superficie del lockfile.

**4. Mejoras de rendimiento del intérprete.** Python 3.11 introdujo el specializing adaptive interpreter, con ganancias medibles. Para `aip archive verify` sobre archivos no triviales, importa.

Python 3.12 y 3.13 son aceptables y soportados. La declaración "3.11 o superior" es deliberada: no se fija una versión máxima.

### Por qué uv y no pip/poetry/conda

- **pip puro** carece de lockfile estandarizado. Requiere `pip-tools` u otra capa.
- **poetry** es maduro pero tiene cadencia de bugs en resolución de dependencias y lockfile no es bit-a-bit estable entre plataformas en todos los casos.
- **conda/mamba** introduce su propio universo de paquetes y curva de aprendizaje no alineada con la audiencia primaria.
- **uv** es rápido, tiene lockfile reproducible, está construido en Rust con compromiso de mantenimiento sostenido por Astral, y es coherente con la elección hecha en `orbital-sentinel` (consistencia entre los proyectos del mismo mantenedor reduce coste cognitivo).

### Por qué ruff y no múltiples herramientas

Sustituye black + isort + flake8 + parte de pylint con un solo binario. Coherente con el principio de minimizar fricción bajo bus factor = 1.

## Alternativas consideradas

### A. Rust como lenguaje único

**Descripción:** Implementar todo en Rust con bindings Python opcionales.

**Razón de rechazo:**
- Audiencia primaria no opera mayoritariamente en Rust.
- Curva de aprendizaje significativa; bajo bus factor = 1 aumenta riesgo de discontinuación.
- Ecosistema de datos en Rust es vibrante pero menos maduro que el de Python para Parquet/Arrow/DuckDB.
- El requisito de rendimiento de V1 no justifica el coste.

Rust permanece como **opción de optimización local** en módulos críticos si surgieran cuellos de botella reales y demostrados. Bindings vía PyO3 son la vía aceptable, no la reescritura completa.

### B. Go como lenguaje único

**Descripción:** Implementar en Go aprovechando su simplicidad.

**Razón de rechazo:**
- Ecosistema de análisis de datos significativamente más débil que Python.
- Soporte Parquet/Arrow en Go existe pero es menor.
- Audiencia primaria no opera en Go.
- Sin razón operativa que compense.

### C. TypeScript/Node.js

**Descripción:** Lenguaje familiar para desarrollo web; ecosistema amplio.

**Razón de rechazo:**
- Ecosistema de datos columnar inmaduro.
- Audiencia académica no opera en Node.js.
- Inestabilidad de ecosistema (npm churn) penaliza horizonte largo.

### D. Julia

**Descripción:** Lenguaje científico moderno con buen rendimiento.

**Razón de rechazo:**
- Comunidad técnica de nicho.
- Adopción de la audiencia primaria mucho menor que Python.
- Ecosistema Parquet/DuckDB inmaduro.

### E. Multi-lenguaje desde el inicio (Python + Rust core)

**Descripción:** API Python sobre core Rust.

**Razón de rechazo:**
- Complejidad de build y distribución.
- Coste cognitivo elevado bajo bus factor = 1.
- Sin demanda real en V1.

No descartado como evolución futura si surgen cuellos de botella verificados.

### F. Python sin uv (gestión clásica)

**Descripción:** Solo pip + requirements.txt.

**Razón de rechazo:**
- Lockfile no estandarizado.
- Reproducibilidad bit a bit del entorno (P5) más frágil.
- Velocidad de resolución de dependencias significativamente peor en proyectos con muchas deps.

## Implicaciones de mantenimiento

### Implicación M1. Disciplina de versión mínima

El soporte de "Python 3.11 o superior" significa que el código del proyecto **no usa características exclusivas de 3.12+** sin compromiso explícito. La opción de levantar el mínimo (a 3.12 cuando 3.11 alcance EOL, por ejemplo) es decisión por ADR de enmienda. No se eleva silenciosamente.

### Implicación M2. Disciplina de dependencias

El lockfile (`uv.lock`) es artefacto auditable del repositorio. Su modificación entra por PR como cualquier otra. Updates masivos de dependencias se documentan en commit con motivo (security update, feature requirement, etc.).

Bajo bus factor = 1:
- Updates de dependencias se hacen cuando son **necesarias**, no por moda.
- Se prefieren dependencias maduras y de bajo churn.
- Cualquier dependencia que pase a estado abandonado (sin releases en 18+ meses) es candidata a evaluación de sustitución.

### Implicación M3. Soporte de plataformas

V1 declara soporte en:

- **Linux x86_64** (referencia primaria; CI obligatorio).
- **macOS arm64** (soporte best-effort; mantenedor opera en Windows pero macOS es plataforma frecuente de audiencia académica).
- **Windows x86_64** (soporte best-effort).

"Best-effort" significa: tests deben pasar; si un bug es específico de la plataforma y no se puede reproducir en Linux, el bug se documenta como conocido sin commitment de fix bajo bus factor = 1.

Linux es la plataforma de referencia para la demo de cierre F1 y para reproducibilidad bit a bit del `archive_manifest_hash`.

### Implicación M4. Tipado estático

El proyecto adopta tipado estático con anotaciones obligatorias en la API pública (`aip` package) y en los modelos de datos. mypy o pyright se ejecutan como parte de CI. El nivel de strictness se documenta en `pyproject.toml`.

Las anotaciones son disciplina, no decoración: bajo bus factor = 1, el tipado estático compensa la falta de revisión por pares interna detectando errores temprano.

### Implicación M5. Compatibilidad de runtime declarada en ArchiveManifest

El `ArchiveManifest` (ADR-0016) registra:

- Versión exacta de Python usada al generar el archivo.
- Hash del `uv.lock` en el momento de la operación.
- Versiones de las librerías críticas (parquet, duckdb, sha256, etc.).

Esto permite que un revisor externo en el futuro reproduzca bit a bit el estado del archivo en su momento.

### Implicación M6. Ausencia de C/C++ propio

V1 no contiene código C/C++ propio. Las dependencias que internamente usen C (numpy, duckdb, etc.) son responsabilidad de sus mantenedores. Esto reduce superficie de build a Python puro + binarios precompilados de las dependencias.

Si en fases posteriores surge necesidad de código nativo propio, requiere ADR específico que documente la justificación, el lenguaje (Rust vía PyO3 preferido), y los costes operativos.

## Consecuencias

**Positivas**
- Decisión formalizada, deja de ser implícita.
- Versión mínima compartida con la audiencia primaria moderna.
- Stack reproducible bit a bit a través del lockfile.
- Bajo coste cognitivo bajo bus factor = 1.
- Coherencia con `orbital-sentinel`, reduciendo carga mental del mantenedor entre proyectos.

**Negativas**
- Excluye implícitamente colaboradores que solo operan en otros lenguajes.
- Cualquier cuello de botella de rendimiento futuro tendrá que resolverse dentro de Python o vía extensiones nativas, ambas con coste.
- Apuesta por uv como herramienta joven (riesgo de churn temprano del propio gestor).

**Neutras**
- Familias de lenguaje "modernas" (Rust, Go, Zig) quedan como opciones futuras para componentes específicos si surgen.

## Declaración de limitaciones

Este ADR **no afirma** que Python sea óptimo en todos los ejes (rendimiento, type safety estricta, ergonomía de concurrencia). Afirma que es el balance correcto para esta arquitectura, esta audiencia y este alcance bajo bus factor = 1.

Para componentes con requisitos extremos no comparables a V1 (procesamiento en tiempo real, sistemas embebidos), Python no sería la elección. Tales componentes no caben en V1 y la decisión se reabriría por ADR si surgen.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único:

- La elección de Python depende en parte de la competencia individual del mantenedor. Un sucesor con perfil distinto podría legítimamente preferir otro lenguaje.
- El protocolo de sucesión del ADR-0026 no impide ese cambio: un sucesor puede proponer ADR de migración. La migración real, sin embargo, exige reescritura de código, con coste alto.
- El compromiso con Python es **soft anchor**: el sucesor lo hereda como inversión, pero no como cadena.

## Trigger de revisión

Este ADR se revisa si:

- Python 3.11 alcanza EOL y el proyecto sigue activo.
- uv introduce cambios incompatibles graves o se discontinúa.
- Aparece cuello de botella de rendimiento verificado que no se resuelve con Python + extensión nativa.
- Sucesor del proyecto propone migración con justificación documentada.

## Alineación con ADR-0000

**Propiedades afectadas:** P5, P6, P7, P8.

**Cómo se alinean:**
- **P5 (reproducibilidad):** lockfile reproducible + versión mínima fija + manifest que registra runtime.
- **P6 (local-first):** stack instalable sin servicios externos.
- **P7 (coste cercano a cero):** todas las herramientas open source.
- **P8 (documentación):** este ADR documenta una decisión hasta ahora implícita.

**Tensión:** ninguna nueva.

## Referencias

- Python Software Foundation. *Python Release Schedule.* PEP 664.
- PEP 621 (pyproject.toml metadata).
- PEP 654 (Exception Groups).
- PEP 657 (Fine-grained error locations).
- PEP 680 (`tomllib`).
- uv documentation. https://github.com/astral-sh/uv
- ruff documentation. https://github.com/astral-sh/ruff
- `orbital-sentinel` ADR-0003 (src layout + uv) como prior art coherente del mismo mantenedor.

---

## Historial de enmiendas

### E1 — 2026-06-07 — `cryptography>=42,<46` (ADR-0041)

ADR-0041 (Operator Attestation Engine V1) introduce una nueva dependencia
de runtime: `cryptography>=42,<46`. Es la **quinta** dependencia de
runtime del proyecto y la única que aporta primitivas criptográficas
(ed25519 sign/verify).

**Justificación:**

- **Load-bearing para la misión:** la atestación criptográfica responde
  directamente a la pregunta del proyecto ("¿qué evidencia existe y cómo
  demostramos que no fue alterada?"). Sin firma ed25519 no hay
  verificación exógena posible.
- **Rolling-our-own ed25519 es anti-patrón:** implementar primitivas
  asimétricas en código propio es uno de los modos clásicos de falla en
  software de seguridad. La regla operativa es delegar en una librería
  auditada.
- **`cryptography` es el estándar de facto en Python:** mantenida por la
  PSF y la Open Tech Fund, audit-friendly, wheels pre-construidos en
  Linux/macOS/Windows para Python 3.11/3.12, ~5 MB de install.
- **Rango `>=42,<46` cubre cuatro major versions** — suficiente para
  12+ meses de estabilidad. `uv.lock` pinea bit a bit.

**Trigger de revisión adicional:**

- Vulnerabilidad CVE significativa en `cryptography` que requiera salto
  de major fuera del rango pineado.
- Aparición de alternativa auditada con superficie menor (p. ej. binding
  directo de libsodium con manifest más estable).

Sin esta enmienda, el ADR-0041 no podría implementarse de forma compatible
con la política de dependencias de este ADR.
