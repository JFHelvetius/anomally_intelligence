# ADR-0027: Graceful Archive Policy — disparadores temporales y procedimiento de archivo digno

**Estado:** Aceptado
**Fecha:** 2026-06-04
**Autor:** AIP — autor fundador
**Supersede a:** ninguno (enmienda operacional al ADR-0000 sección "Condiciones de archivo digno")
**Relacionado con:** ADR-0000, ADR-0023, ADR-0026

---

## Contexto

El ADR-0000 sección "Condiciones de archivo digno" declara cinco condiciones que disparan archivado:

1. Inviabilidad epistémica demostrada.
2. Colapso de fuentes.
3. Insostenibilidad de mantenimiento (doce meses sin capacidad de respuesta a issues críticos ni reemplazo de mantenedor).
4. Captura por intereses incompatibles con propiedades irrenunciables.
5. Daño documentado a testigos por defecto de diseño.

El Red Team Review §9.2 identifica una **circularidad en el trigger 3**: "doce meses sin capacidad de respuesta a issues críticos" presupone que existen issues críticos, lo que presupone usuarios, lo que presupone software entregado. Un proyecto pre-código nunca dispararía la condición 3 incluso si nadie trabaja en él.

El review también observa que el archivo digno requiere infraestructura (publicación de `ARCHIVED.md`, preservación en Software Heritage o equivalente, snapshot empaquetado) que no está operacionalizada en ningún ADR previo.

Este ADR no supersede al ADR-0000. **Enmienda operacionalmente la sección "Condiciones de archivo digno"** con disparadores temporales independientes de actividad de usuarios y con procedimiento explícito.

## Decisión

Se introducen **disparadores de actividad** que aplican incluso a un proyecto sin usuarios, y un **procedimiento de archivo digno** con tres pasos verificables.

Los cinco triggers originales del ADR-0000 se conservan. Se añaden tres triggers operacionales y se sustituye el trigger 3 por una formulación basada en actividad observable.

## Disparadores

### Triggers conservados del ADR-0000

T1. **Inviabilidad epistémica demostrada.** Sin cambios.

T2. **Colapso de fuentes.** Sin cambios.

T3. **Insostenibilidad de mantenimiento** — **reformulado**: doce meses consecutivos sin commit al main branch del repositorio público, sin actualización del `MAINTAINERS.md`, y sin comunicación pública del mantenedor único o de algún co-mantenedor activo. Este criterio aplica con o sin usuarios externos.

T4. **Captura por intereses incompatibles con propiedades irrenunciables.** Sin cambios.

T5. **Daño documentado a testigos por defecto de diseño.** Sin cambios.

### Nuevos triggers introducidos por este ADR

T6. **Dormancia declarada.** Si el mantenedor único declara públicamente intención de pausar el proyecto por más de seis meses, el proyecto entra en estado **dormant** con publicación de `DORMANT.md`. La dormancia no es archivado: el proyecto puede reactivarse. Pero si la dormancia se extiende más de 24 meses, dispara archivado.

T7. **Vacío de mantenimiento sin sucesión.** Si ocurre alguna combinación de:
- Mantenedor único inalcanzable durante seis meses por canales públicos declarados, **y**
- No hay co-mantenedor que asuma activamente.

Aplica plazo de tres meses adicionales para que cualquier interesado externo manifieste interés en asumir mantenimiento siguiendo el protocolo de sucesión (ADR-0026). Si transcurre el plazo sin sucesor confirmado, dispara archivado.

T8. **Inviabilidad técnica de dependencias críticas.** Si las dependencias declaradas críticas (Parquet, SHA-256, librerías de runtime Python) sufren cambios incompatibles que no son migrables por el mantenedor disponible, el proyecto puede archivarse con `ARCHIVED.md` que documenta la causa técnica concreta.

## Procedimiento de archivo digno

Cuando se dispara cualquier T1–T8, el procedimiento es:

### Paso 1. Anuncio público y `ARCHIVED.md`

El mantenedor en ejercicio (o el último mantenedor identificable) publica en la raíz del repositorio el fichero `ARCHIVED.md` con la plantilla:

```markdown
# AIP — proyecto archivado

**Fecha del archivado:** AAAA-MM-DD
**Trigger activado:** T<X> (referencia a ADR-0027)
**Causa concreta:** <descripción honesta>
**Último mantenedor en ejercicio:** <handle>
**Última release estable:** <tag o commit>

## Estado del archivo de datos

<inventario del estado: número de evidencias ingestadas, número de fuentes
registradas, integridad verificada por `aip archive verify`>

## Mensaje al lector futuro

<una a tres frases honestas sobre qué se logró y qué quedó incumplido>

## Continuidad

La licencia Apache 2.0 permanece vigente. Cualquier persona puede forkear
el proyecto, retomar el mantenimiento, y publicar su continuación. No es
necesaria autorización previa del mantenedor archivante.

## Preservación

<URL al snapshot en Software Heritage o equivalente, hash del manifiesto del
archivo final si lo hay>
```

### Paso 2. Última release estable

Se publica un commit final marcado con tag (`vX.Y.Z-final` o equivalente) que:

- Incluye `ARCHIVED.md`.
- No introduce funcionalidad nueva (solo documenta el archivado).
- Pasa los tests que el proyecto tenía vigentes.
- Actualiza el `README.md` con un banner que apunte a `ARCHIVED.md`.

Si la causa del archivado impide ejecutar tests (por ejemplo, dependencia crítica rota), se documenta en `ARCHIVED.md` y se publica de todos modos.

### Paso 3. Preservación a largo plazo

Cuando es operativamente posible:

- El repositorio se replica en **Software Heritage** (https://www.softwareheritage.org/) o repositorio académico equivalente.
- Si existe corpus de datos generado por el proyecto (snapshots citables del ADR-0010), se publica en **Zenodo** o equivalente con DOI.
- El `archive_manifest_hash` final (ADR-0016) se publica en `ARCHIVED.md` para verificación de integridad por cualquier observador futuro.

Si por circunstancias del archivado (falta de tiempo, desaparición súbita del mantenedor) el paso 3 no es ejecutable, los pasos 1 y 2 son suficientes para considerarse archivo digno **mínimo**. El paso 3 es **deseable**, no condición.

## Distinción entre dormancia y archivado

| Estado | Significado | Reversible | Trigger |
|--------|-------------|-----------|---------|
| `active` | Mantenedor activo, cadencia honesta declarada | — | (default) |
| `dormant` | Pausa explícita anunciada por mantenedor | Sí | T6 si > 24 meses |
| `archived` | Archivo digno ejecutado | No (pero forkable) | T1–T8 |

El proyecto puede transitar `active → dormant → active` cuantas veces necesite, con `DORMANT.md` actualizado en cada transición. Solo `archived` es estado terminal del repositorio original; cualquier continuación es fork externo.

## Defensa contra archivado prematuro vs. archivado tardío

ADR-0000 declaró: "Archivar a tiempo es responsabilidad; archivar tarde es daño." Este ADR operacionaliza ambas direcciones:

**Defensa contra archivado prematuro:**
- Triggers T1, T2, T4, T5 requieren documentación pública de la causa antes del archivado.
- Trigger T3 reformulado requiere doce meses consecutivos, no episodios breves.
- Trigger T6 (dormancia declarada) es reversible y no precipita archivado hasta 24 meses.

**Defensa contra archivado tardío:**
- Trigger T3 reformulado aplica aunque no haya usuarios.
- Trigger T7 introduce ventana fija para sucesión.
- Bus factor declarado (ADR-0026) hace visible el riesgo antes de que se materialice.

## Consecuencias

**Positivas**
- El proyecto tiene final digno asegurado incluso sin usuarios externos.
- El lector externo entiende qué estado significa qué.
- La circularidad del trigger original del ADR-0000 queda resuelta.
- Reactivación tras dormancia es trayectoria legítima, no fracaso.

**Negativas**
- Más burocracia documental.
- La distinción dormant/archived requiere comunicación pública que un mantenedor en crisis puede no estar en condiciones de hacer.

**Neutras**
- Si el mantenedor desaparece súbitamente sin ejecutar los pasos del archivado, el repositorio queda en limbo. Mitigación: trigger T7 + protocolo de sucesión del ADR-0026 abren ventana para sucesión externa.

## Declaración de limitaciones

Este ADR **no garantiza**:

- Que el mantenedor en crisis terminal ejecute los pasos del archivado en orden.
- Que Software Heritage o Zenodo sigan disponibles cuando se necesiten.
- Que un fork externo aparezca para continuar el proyecto cuando se archive.

Estas dependencias son del mundo, no del proyecto. El ADR establece la **intención** y el **procedimiento**; la ejecución depende de circunstancias.

## Declaración de riesgo de mantenedor único

Bajo mantenedor único:

- La detección de los triggers depende de la auto-evaluación del mantenedor mismo. El mantenedor en agotamiento o en negación puede no reconocer T3 o T6.
- La ejecución de los pasos del archivado requiere capacidad operativa que un mantenedor en crisis puede no tener.

Mitigación parcial:
- El bus factor declarado (ADR-0026) hace visible la situación al usuario externo, que puede ofrecerse a sucesión.
- La política T7 abre ventana explícita para sucesión externa cuando el mantenedor está inalcanzable.

## Enmienda al ADR-0000

Como parte de la aceptación de este ADR, se añade al historial de enmiendas del ADR-0000:

> *2026-06-04 — AIP autor fundador:* La sección "Condiciones de archivo digno" se opera conforme al ADR-0027. El trigger 3 del ADR-0000 ("insostenibilidad de mantenimiento") se reformula como T3 del ADR-0027 (basado en actividad observable, no en presencia de usuarios). Se añaden T6 (dormancia declarada), T7 (vacío de mantenimiento sin sucesión) y T8 (inviabilidad técnica de dependencias críticas) como triggers adicionales.

## Alineación con ADR-0000

**Propiedades afectadas:** P8 (documentación al nivel del código), sostenibilidad del ADR-0000.

**Cómo se alinea:** este ADR **fortalece** el compromiso del ADR-0000 con archivo digno haciéndolo operacional. Resuelve la circularidad del trigger original.

**Tensión:** ninguna nueva. La tensión del ADR-0000 entre archivar pronto y archivar tarde se gestiona con triggers múltiples.

## Referencias

- `docs/reviews/adr_red_team_review.md`, sección §9.2.
- Software Heritage Foundation. https://www.softwareheritage.org/
- Zenodo. https://zenodo.org/
- OCFL (Oxford Common Filesystem Layout). Prior art en preservación a largo plazo.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
