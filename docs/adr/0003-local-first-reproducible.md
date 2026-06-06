# ADR-0003: Local-first y reproducibilidad bit a bit

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0015, ADR-0016, ADR-0017

---

## Contexto

Los proyectos de investigación sobre fenómenos anómalos sufren históricamente dos modos de muerte:

1. **Captura por infraestructura.** Una organización monta su archivo sobre una plataforma cerrada (Filemaker, SharePoint, software propietario de gestión de casos). Cuando el mantenedor desaparece o la plataforma se discontinúa, el archivo queda inaccesible.
2. **Captura por servicio.** Una iniciativa se monta sobre una nube comercial (Google Drive, Notion, una base gráfica gestionada). Cuando el servicio cambia precios, términos o cesa, todo el archivo queda en tránsito hacia el olvido.

La consecuencia conjunta es que material valioso desaparece, no por falta de interés, sino por dependencia de infraestructura volátil.

A esto se suma un problema epistémico: si los resultados del sistema dependen de servicios externos cuyo comportamiento puede cambiar sin aviso (un modelo de embedding propietario que se actualiza silenciosamente, una API que retorna resultados distintos por mes), entonces la reproducibilidad bit a bit (P2) es imposible.

## Decisión

Todo el núcleo del sistema —ingestión de evidencia, modelo de razonamiento, motor de hipótesis, generación de conclusiones, búsqueda local, exploración de grafo, exportación citable— funciona **exclusivamente con recursos locales** sobre un portátil moderno. Sin conexión a Internet salvo durante la fase explícita de ingestión de fuentes externas.

Cualquier funcionalidad que requiera servicios externos vive en una capa marcada explícitamente como **opcional y no crítica**: si el servicio desaparece, el sistema sigue siendo plenamente operativo sobre la base local.

Toda inferencia del sistema es bit a bit reproducible: dada la misma evidencia (por hash) y el mismo código (por commit), las salidas son idénticas.

## Justificación

### Local-first como supervivencia del archivo

Un archivo replicable en disco local que pueda viajar en un disco duro USB sobrevive desastres de infraestructura. Es la forma más antigua y más robusta de preservación documental. Esta decisión se alinea con cómo los archivos físicos —Hynek Center, GEIPAN físico, fondos privados— han sobrevivido en realidad: por la dispersión y la facilidad de replicación.

### Reproducibilidad como exigencia epistémica

Una conclusión publicada por el sistema en 2027 debe poder reproducirse en 2042 sobre los mismos datos crudos. Para que eso sea cierto:

- No puede depender de un modelo propietario que ya no existe.
- No puede depender de un servicio cuya respuesta cambió.
- No puede depender de una versión de software que no se puede instalar.

La consecuencia operativa: todas las dependencias del sistema deben ser open source, archivables, y especificables en un manifiesto reproducible.

### Servicios externos como complemento, no como columna

Hay capacidades valiosas que solo son accesibles vía servicios externos: OCR avanzado, transcripción de audio histórico, análisis forense de imagen profesional, traducciones masivas. El sistema permite usarlas, pero las trata como **enriquecimientos opcionales** cuyo resultado se ingesta como artefacto derivado nuevo (con su propio hash y procedencia), no como dependencia de ejecución continua.

Si un usuario quiere reproducir un análisis y no tiene acceso al servicio externo, el sistema le indica claramente qué artefactos derivados no podrá regenerar y le permite operar con los que ya están en el archivo local.

## Implicaciones de diseño

### Runtime local

- El proyecto se ejecuta en Python (decisión a confirmar en ADR posterior sobre lenguaje) con todas sus dependencias instalables vía un gestor de entornos reproducible (uv / pip-tools con lockfile completo).
- El almacenamiento es local: ficheros en disco con un esquema controlado (ver ADR-0015).
- La interfaz primaria es CLI + Jupyter; una UI web local opcional para exploración.
- El grafo de conocimiento se materializa sobre almacenamiento local embebido (DuckDB / SQLite / Parquet, decisión en ADR-0015 y ADR-0011).

### Sin telemetría obligatoria

El sistema no envía datos a servidores remotos por defecto. Cualquier telemetría opcional debe ser opt-in explícito con consentimiento informado. Una declaración de privacidad acompaña cualquier release.

### Manifiesto reproducible

Cada release del software incluye:
- Lockfile completo de dependencias (`uv.lock` o equivalente).
- Hashes de los modelos opcionales soportados (si los hay).
- Versión del esquema de datos (ver ADR-0016).
- Versión del runtime de Python.

Cualquier resultado del sistema referencia el commit del software y el manifiesto que se usó.

### Snapshot reproducible del archivo

El archivo local se puede empaquetar como un snapshot citable: un directorio con la evidencia cruda direccionada por hash, los metadatos versionados, y el manifiesto del software. Dos copias del mismo snapshot generan los mismos resultados ante las mismas consultas. Un snapshot puede archivarse en Zenodo, IPFS, o cualquier preservación de largo plazo.

## Consecuencias

**Positivas**
- Robustez: el archivo sobrevive desastres de infraestructura porque vive en discos locales replicables.
- Reproducibilidad: dos investigadores en años distintos llegan al mismo resultado.
- Acceso universal: cualquier portátil moderno basta. No hay barrera económica de servicios.
- Soberanía de datos: el investigador es dueño de su archivo, no inquilino de una plataforma.
- Auditabilidad: el código y los datos están al alcance del revisor, sin "no podemos compartir el detalle del modelo propietario".

**Negativas**
- Algunas capacidades de frontera (modelos grandes, análisis forense profesional) quedan como opcionales y no garantizadas.
- El usuario asume responsabilidad sobre backups y disponibilidad de su archivo.
- Distribución de archivos grandes (TBs) requiere infraestructura externa de transferencia (no parte del sistema).
- Imposible escalar a "todos los reportes de UAP del mundo en tiempo real" como producto único centralizado. Decisión consciente.

**Neutras**
- El sistema se distribuye también como servidor opcional para colaboración multiusuario, pero ese modo es secundario al modo single-user-local.

## Alternativas consideradas

### A. Cloud-first
**Descripción:** Servicio web central con almacenamiento gestionado.
**Razón de rechazo:** Captura por infraestructura. Coste operativo no compatible con P7. Captura potencial por intereses sustantivos via control del servicio (P4).

### B. Hybrid con cloud opcional
**Descripción:** Local-first pero con sync cloud como característica de primer nivel.
**Razón de rechazo:** El sync cloud, si es de primer nivel, atrae presión de diseño que erosiona la primacía local. La hibridez se mantiene, pero estrictamente en orden: local primero, opcional después.

### C. Peer-to-peer (IPFS-first)
**Descripción:** Distribuir la evidencia y los metadatos vía protocolos P2P.
**Razón de rechazo:** Atractivo a largo plazo. No descartado como evolución futura. Hoy añade complejidad sin ROI para la audiencia primaria. ADR futuro puede reconsiderarlo.

## Alineación con ADR-0000

**Propiedades afectadas:** P2, P5, P6, P7, P11.

**Cómo se alinean:**
- P6 (local-first): operacionalización directa.
- P7 (coste cercano a cero): sin servicios de pago obligatorios.
- P2 (trazabilidad) y P5 (reproducibilidad): imposibles sin dependencias estables y open source.
- P11 (inmutabilidad de evidencia cruda): natural en almacenamiento local content-addressed.

**Tensión:** Frontera técnica accesible vs. reproducibilidad. Algunas capacidades de vanguardia (modelos multimodales de última generación) son difíciles de replicar localmente. Tensión aceptada: el núcleo no depende de ellas; entran como opcionales con artefactos derivados explícitos.

## Referencias

- Kleppmann, M. et al. (2019). *Local-first software.*
- Git, IPFS, Datomic. Prior art en almacenamiento content-addressable.
- Software Carpentry / Open Science Framework. Estándares de reproducibilidad.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
