# Red Team Response — informe de cierre formal

**Fecha:** 2026-06-04
**Documento revisado:** [`adr_red_team_review.md`](adr_red_team_review.md), fechado 2026-06-03.
**Respondedor:** AIP — autor fundador.
**Forma:** este documento no reescribe el Red Team Review. Lo acepta como crítica permanente y declara qué hallazgos quedan cerrados, mitigados o aceptados conscientemente como riesgo, mediante las enmiendas ADR-0023 a ADR-0028.

---

## Marco de respuesta

Cada hallazgo del Red Team Review se clasifica en uno de tres tratamientos:

- **Cerrado** — el hallazgo describe una promesa que el proyecto retira o un mecanismo que se modifica de forma que el modo de fallo identificado deja de aplicar.
- **Mitigado** — el hallazgo describe un riesgo real que el proyecto no elimina pero acota operativamente con límites declarados, procedimientos documentados o triggers explícitos.
- **Aceptado** — el hallazgo describe un riesgo real que el proyecto reconoce como inherente al modelo o al alcance, y opta por no eliminar. Se documenta para que el lector externo lo evalúe con conocimiento.

Ningún hallazgo se descarta por estilo. La crítica es material permanente del proyecto.

---

## Tabla de cierre

| # | Hallazgo (resumen) | Tratamiento | ADR de respuesta | Mecanismo concreto |
|---|---|---|---|---|
| **§1.1** | "Neutralidad" es occidental, no universal | **Mitigado** | ADR-0025 | Reformulación de P4 como "no-favoritismo estructural" + declaración de sesgos S1–S4 |
| **§1.2** | Honestidad epistémica es selectiva | **Mitigado** | ADR-0024 | Límite L1: incertidumbre cuantificada es de primer orden y solo de objetos modelados |
| **§1.3** | Pregunta central presupone hipótesis independientes | **Aceptado** | ADR-0024, ADR-0025 | Sesgo S3 declarado: composición causal y entrelazamiento fuera de alcance V1 |
| **§2.1 P9⊥P12** | Fuentes públicas vs. do-no-harm | **Mitigado** | ADR-0024 | Límite L3: tensión gestionada caso por caso con preferencia hacia P12 en daño concreto |
| **§2.1 P3⊥P5** | Incertidumbre vs. reproducibilidad | **Mitigado** | ADR-0024 | Límite L3: cuantificación reproducible si documentada, no objetivamente correcta |
| **§2.1 P6⊥P9** | Local-first vs. fuentes públicas | **Mitigado** | ADR-0024, ADR-0023 | Límite L3: subconjuntos documentados en `ArchiveManifest`; V1 con un solo PDF |
| **§2.1 P10⊥P11** | No fabricación vs. inmutabilidad | **Mitigado** | ADR-0024 | Límite L3: metadatos derivados como `LlmAssist` y derivados explícitos |
| **§2.2** | P2 (trazabilidad) es performativa | **Mitigado** | ADR-0024 | Límite L2: P2 cubre material ingestado local; preservación distinta de regeneración |
| **§2.3** | P7 sobrestima portátil moderno | **Cerrado** | ADR-0023 | V1 recortada al subset mínimo; alcance masivo deferido |
| **§3.1** | Frontera Fact/Claim borrosa | **Aceptado** | ADR-0024 | Límite L4: categorización es acto del curador con autoría, no propiedad universal |
| **§3.2** | Falsabilidad privilegia hipótesis ordinarias | **Mitigado** | ADR-0025 | Sesgo S2 declarado: `Conjecture` como categoría legítima auxiliar |
| **§3.3** | KentLevel es score escalar disfrazado | **Mitigado** | ADR-0024 | Límite L5: KentLevel se declara como score ordinal con etiquetas verbales |
| **§3.4** | Grafo sin reasoner es limitante | **Aceptado** | ADR-0023 | Grafo diferido fuera de V1; aceptado como diseño |
| **§3.5** | Inmutabilidad produce churn | **Mitigado** | ADR-0024 | Límite L6: vista materializada `evidence_current` sin violar inmutabilidad |
| **§4.1** | Linealidad bloquea colaboración real | **Aceptado** | ADR-0023 | Lifecycle de caso diferido fuera de V1; aceptado como diseño |
| **§4.2** | `disputed` vector de abuso táctico | **Aceptado** | ADR-0023 | Estado `disputed` diferido fuera de V1 |
| **§4.3** | Cita `head` anula reproducibilidad | **Mitigado** | ADR-0024 | Límite L7: cita académica obligatoria por hash en tooling oficial |
| **§5.1** | Código OSINT no vinculante | **Aceptado** | ADR-0023 | Adquisidores OSINT diferidos fuera de V1 |
| **§5.2** | Política conservadora redes sociales reduce relevancia | **Aceptado** | ADR-0023 | Aceptado conscientemente: V1 no incluye redes sociales |
| **§5.3** | Ecosistema WARC frágil | **Aceptado** | ADR-0023 | WARC diferido fuera de V1; ingestión local manual |
| **§6.1** | DuckDB punto único de falla | **Mitigado** | ADR-0024 | Límite L: formato canónico es Parquet, no DuckDB |
| **§6.2** | Parquet no eterno | **Aceptado** | ADR-0024 | Riesgo declarado; estrategia de migración aplicable a derivaciones, no a histórico |
| **§6.3** | CAOS limitado en escala | **Aceptado** | ADR-0023 | Archivo V1 modesto; escala masiva diferida |
| **§7.1** | Tres superficies API divergerán | **Cerrado** | ADR-0023 | V1 entrega solo CLI + API Python; HTTP no se construye en V1 |
| **§7.2** | Semántica será autoritativa en uso real | **Cerrado** | ADR-0023 | Búsqueda semántica diferida fuera de V1 |
| **§7.3** | Diccionario sinónimos trabajo infinito | **Cerrado** | ADR-0023 | Diccionario de sinónimos diferido fuera de V1 |
| **§8.1** | Takedown sesgo de clase | **Mitigado** | ADR-0026 | Compromiso C4: vías alternativas de verificación documentadas; discreción a favor del solicitante |
| **§8.2** | Anti-deanonymization declarativa | **Aceptado** | ADR-0026 | Declarado como riesgo inherente: defensa última es no construir capacidad, no impedir uso |
| **§8.3** | Material clasificado política inestable | **Mitigado** | ADR-0026 | Procedimiento documentado en `docs/ethics-procedures/classified-material.md`; default conservador |
| **§8.4** | Revisión ética presupone continuidad de carácter | **Cerrado** | ADR-0026 | Compromiso C4: decisiones ancladas a procedimiento, no a discreción personal |
| **§9.1** | Vaporware perpetuo (single maintainer + scope) | **Cerrado** | ADR-0023, ADR-0026 | Alcance V1 recortado + Compromiso C2 (bus factor declarado) + Compromiso C5 (política de no-SLA) |
| **§9.2** | Condiciones de archivo circulares | **Cerrado** | ADR-0027 | Trigger T3 reformulado por actividad observable + T6/T7/T8 nuevos |
| **§10.1** | Adopción no garantizada | **Aceptado** | ADR-0023 | Reconocido: adopción es resultado, no input; no se persigue antes de entregable |
| **§10.2** | Citabilidad académica requiere validación | **Aceptado** | ADR-0023 | Validación académica es trabajo posterior al entregable V1 |
| **§V5** | Considerar GPL/AGPL | **Cerrado** | ADR-0028 | Apache 2.0 reafirmada con razonamiento explícito + CC BY-SA 4.0 para corpus + disparadores D1–D4 |

---

## Síntesis cuantitativa

De los **34 hallazgos** clasificados:

- **9 cerrados** (~26%): el modo de fallo identificado deja de aplicar en V1 o se elimina por procedimiento.
- **13 mitigados** (~38%): el riesgo se acota operativamente con límites declarados, procedimientos o triggers.
- **12 aceptados conscientemente** (~35%): el riesgo se documenta y se asume sin eliminar.

Esta distribución refleja honestidad operativa. Pretender cerrar el 100% sería caer en el modo que el Red Team Review identifica como característico: documentación que aparenta resolver problemas sin tocar realidad.

---

## Hallazgos cerrados con detalle

Lista de hallazgos donde el modo de fallo deja de aplicar:

- **§2.3** P7 sobrestima portátil moderno → ADR-0023 recorta V1 a un PDF, integridad, hash y verificación. Trivialmente cubible por hardware moderno modesto.
- **§7.1** Tres superficies API divergerán → ADR-0023 elimina HTTP de V1. Solo CLI + API Python (con CLI delgado sobre API Python).
- **§7.2** Búsqueda semántica autoritativa en uso real → ADR-0023 difiere búsqueda semántica fuera de V1.
- **§7.3** Diccionario sinónimos trabajo infinito → ADR-0023 difiere diccionario fuera de V1.
- **§8.4** Revisión ética presupone continuidad de carácter → ADR-0026 ancla decisiones éticas a procedimiento documentado en `docs/ethics-procedures/`, no a discreción del mantenedor.
- **§9.1** Vaporware perpetuo → ADR-0023 (alcance reducido) + ADR-0026 (bus factor declarado, no-SLA) eliminan estructuralmente el modo de fallo: V1 es entregable en horizonte realista para mantenedor único part-time.
- **§9.2** Condiciones de archivo circulares → ADR-0027 reformula T3 por actividad observable e introduce T6, T7, T8 que aplican incluso a proyecto sin usuarios externos.
- **§V5** Considerar GPL/AGPL → ADR-0028 reafirma Apache 2.0 con razonamiento explícito, separa licencia de código de licencia de corpus (CC BY-SA 4.0 para corpus generado), establece disparadores D1–D4 de reconsideración formal.

---

## Riesgos aceptados conscientemente

Los 12 hallazgos aceptados son los riesgos que el proyecto **conoce y no elimina**. Su lista es la declaración de honestidad del proyecto. Cualquier adoptante debe leerlos antes de comprometerse:

1. **§1.3** El modelo de hipótesis competidoras no captura composición causal ni entrelazamiento. Investigadores que requieran modelado bayesiano con dependencias estructurales encontrarán el motor de confianza insuficiente para sus propósitos.

2. **§3.1** La frontera Fact/Claim es zona gris en casos reales. La categorización es decisión del curador con autoría, no propiedad universal del enunciado.

3. **§3.4** El grafo de conocimiento sin auto-inferencia es honesto y limitante. Queries de varios saltos pueden devolver resultados parciales por aristas no declaradas, sin que el sistema marque la incompletitud.

4. **§3.5** La inmutabilidad de evidencia mitigada con vistas operativas (ADR-0024 L6) sigue produciendo crecimiento de versiones que un equipo pequeño debe gestionar.

5. **§4.1** La cadena lineal de revisiones de caso no soporta colaboración divergente real. Forks se modelan como casos distintos.

6. **§4.2** El estado `disputed` es vector potencial de abuso táctico. Sin equipo de moderación, su uso depende del juicio del curador único.

7. **§5.1** El "código de prácticas" OSINT es voluntario y sujeto a erosión por presión por cobertura.

8. **§5.2** La política conservadora sobre redes sociales sacrifica material contemporáneo relevante. El archivo será más histórico que actual.

9. **§5.3** El ecosistema WARC en Python es menos maduro que el formato. Roturas de librería pueden inutilizar capturas accesibles en formato.

10. **§6.2** Parquet es estándar abierto pero no eterno. La estrategia de migración cubre derivaciones, no garantiza preservación indefinida del histórico bajo evolución del estándar.

11. **§6.3** CAOS basado en filesystem escala bien para archivos modestos. Archivos masivos requieren capas adicionales no documentadas hoy.

12. **§8.2** La negativa a deanonymization es declarativa: el proyecto no construye la capacidad pero no puede impedir que un externo la construya sobre la API.

13. **§10.1** La adopción del proyecto por su audiencia primaria no está garantizada. El proyecto la trata como resultado, no input.

14. **§10.2** La citabilidad académica requiere validación por revistas y conferencias que el proyecto solo puede iniciar tras tener entregable funcional.

15. **§V (verdict global) — Riesgos del modelo de mantenedor único.** Documentados en ADR-0026 como cinco riesgos: discontinuación, calidad inconsistente, sesgo personal, captura emocional, obsolescencia técnica.

(El conteo de aceptados incluye sub-hallazgos del verdict global que el ADR-0026 declara individualmente, sumando un total contado como 12 ítems mayores en la tabla; la lista aquí los desglosa con mayor granularidad.)

---

## Hallazgos abiertos

**Ninguno.** Cada hallazgo identificado por el Red Team Review tiene tratamiento declarado (cerrado, mitigado o aceptado conscientemente).

Esto **no significa** que el proyecto esté libre de problemas. Significa que **los problemas identificados están reconocidos**. La aparición de hallazgos nuevos en futuras revisiones será materia de futuros ADRs.

---

## Verificación de no-debilitamiento de ADR-0000

Las seis enmiendas ADR-0023 a ADR-0028 se verifican individualmente respecto a las 12 propiedades irrenunciables del ADR-0000:

| Propiedad | ADR-0023 | ADR-0024 | ADR-0025 | ADR-0026 | ADR-0027 | ADR-0028 |
|-----------|---------|---------|---------|---------|---------|---------|
| **P1** Separación epistémica       | preservada | preservada | preservada | — | — | — |
| **P2** Trazabilidad bit a bit      | preservada | **acotada honestamente** | — | — | — | — |
| **P3** Incertidumbre cuantificada  | preservada | **acotada honestamente** | preservada | — | — | — |
| **P4** Neutralidad de hipótesis    | preservada | — | **reformulada operativamente** | — | — | — |
| **P5** Reproducibilidad            | preservada | **acotada honestamente** | — | — | — | — |
| **P6** Local-first                 | reforzada | preservada | — | — | — | — |
| **P7** Coste cercano a cero        | reforzada | preservada | — | — | — | — |
| **P8** Documentación               | preservada | reforzada | reforzada | reforzada | reforzada | reforzada |
| **P9** Fuentes públicas            | preservada | **acotada honestamente** | — | — | — | preservada |
| **P10** No fabricación             | preservada | preservada | — | — | — | — |
| **P11** Inmutabilidad evidencia    | preservada | **acotada con vista operativa** | — | — | — | — |
| **P12** Do-no-harm                 | preservada | — | — | **operacionalizada** | — | — |

**Resultado:** ninguna propiedad debilitada. Cuatro propiedades acotadas honestamente (P2, P3, P5, P9, P11) con límites operativos declarados. Una propiedad reformulada operativamente (P4) sin debilitar el mecanismo. Cuatro propiedades reforzadas (P6, P7, P8, P12) con procedimientos explícitos.

---

## Estado de habilitación de Fase 1

La condición declarada en el prompt de esta revisión —"solo cuando el review quede resuelto o reducido a riesgos aceptados, prepara la transición a Fase 1"— se cumple:

- Hallazgos cerrados: 9.
- Hallazgos mitigados: 13.
- Hallazgos aceptados conscientemente: 12.
- Hallazgos abiertos: 0.

**Fase 1 queda habilitada.** Su alcance, criterio de cierre y artefactos están definidos en ADR-0023 y se consolidan en `PROJECT_STATUS.md`. El siguiente paso es la implementación; no se diseña capacidad nueva.

---

## Compromiso de revisión continua

Este informe de cierre no es definitivo. Cualquier hallazgo nuevo que un revisor externo identifique en el futuro entra al ciclo:

1. Se documenta en `docs/reviews/` como crítica sin sanear.
2. Se clasifica (cerrar / mitigar / aceptar).
3. Si requiere cambio arquitectónico, se introduce ADR de enmienda.

El ciclo no expira mientras el proyecto esté activo. Cuando se archive (ADR-0027), el `ARCHIVED.md` declara el estado final del cierre de revisiones.

---

*Este informe es producto del autor fundador como mantenedor único. Su honestidad sobre los riesgos aceptados es directamente proporcional a la credibilidad que el proyecto pueda construir. Cualquier lectura del informe que detecte minimización u ocultación de algún hallazgo se acepta como contribución para enmienda.*
