# Anomaly Intelligence Platform (AIP)

> Plataforma open source para investigar, organizar y cuantificar la incertidumbre que rodea a los reportes de fenómenos anómalos aéreos, orbitales, marítimos, astronómicos y observacionales. Sin posturas. Sin sensacionalismo. Sin conclusiones predeterminadas.

**Estado del proyecto:** fase de fundación (redacción de ADRs). Sin código ejecutable todavía.

## Sobre este repositorio

AIP es un proyecto de horizonte largo (5+ años). Su primer artefacto no es código sino un cuerpo de decisiones arquitectónicas explícitas. Antes de escribir la primera línea queremos saber qué problema resuelve, qué propiedades no podrá violar nunca, y bajo qué condiciones el proyecto debería archivarse dignamente.

Toda esa conversación vive en [docs/adr/](docs/adr/). Si quieres entender el proyecto, ese es el único lugar donde empezar. El ADR-0000 es la brújula; todos los demás se alinean con él.

## La pregunta central

La plataforma **no** intenta demostrar ni refutar la existencia de UFOs, OVNIs, NHIs ni ninguna otra hipótesis sustantiva.

La pregunta central no es:

> "¿Qué es esto?"

La pregunta central es:

> "¿Qué nivel de confianza podemos asignar, con honestidad epistémica, a cada hipótesis competidora que explique este reporte?"

Esa reformulación es el ADN del proyecto. Cualquier diseño que la traicione queda fuera.

## Hoja de ruta a alto nivel

El proyecto se desarrolla en fases, cada una funcional y demostrable:

1. **Modelo de evidencia y fuentes** — esquemas formales, almacenamiento inmutable, trazabilidad bit a bit.
2. **Catálogo de casos** — ingestión de archivos históricos y modernos sobre el modelo de evidencia.
3. **Hipótesis y confianza** — sistema explícito de hipótesis competidoras y cuantificación de incertidumbre.
4. **Motor temporal y geoespacial** — reconstrucción de líneas de tiempo y de superposiciones geográficas verificables.
5. **Grafo de conocimiento** — relaciones entre personas, organizaciones, eventos, lugares, medios y documentos.
6. **Workflows de investigación abierta** — herramientas para que un investigador externo pueda reproducir o contradecir cualquier conclusión.

El detalle vive en los ADRs.

## Lo que el proyecto distingue rigurosamente

AIP nunca mezcla cinco categorías:

- **Hechos** — verificables independientemente, con cadena de custodia.
- **Afirmaciones** — atribuibles a una fuente, no necesariamente verificadas.
- **Interpretaciones** — lecturas humanas de hechos o afirmaciones.
- **Hipótesis** — explicaciones competidoras formuladas explícitamente.
- **Conclusiones** — evaluaciones de confianza relativa entre hipótesis, siempre revisables.

La arquitectura del sistema fuerza esa separación en el modelo de datos, no en convenciones humanas.

## Licencia

Distribuido bajo [Apache License 2.0](LICENSE). Uso comercial permitido. Cláusula de patentes incluida.

## Lengua

La documentación inicial se escribe en español. Una traducción al inglés está prevista como prerrequisito de la primera release pública (ver ADR pendiente sobre internacionalización).

## No-objetivos

AIP **no** existe para:

- Declarar origen extraterrestre, interdimensional, ni de ninguna naturaleza sustantiva.
- Promover teorías conspirativas, marcos ideológicos o agendas políticas.
- Generar contenido sensacionalista o viral.
- Esconder incertidumbre detrás de visualizaciones bonitas.
- Presentar especulación como hecho.

Estas prohibiciones son arquitectónicas, no editoriales. Están codificadas en el modelo de datos y en las propiedades irrenunciables del ADR-0000.
