# ADR-0010: Ciclo de vida del caso

**Estado:** Aceptado
**Fecha:** 2026-06-03
**Autor:** AIP — autor fundador
**Supersede a:** ninguno
**Relacionado con:** ADR-0000, ADR-0002, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0016

---

## Contexto

ADR-0002 establece que el `Case` es un agregado **versionado** que actúa como vista sobre evidencia, claims, hipótesis y conclusiones. Falta especificar:

- Qué estados puede atravesar un caso.
- Qué transiciones están permitidas y bajo qué condiciones.
- Cómo se materializa el versionado.
- Cómo se cita un caso en un instante concreto de su historia.
- Cómo se retracta o archiva un caso sin destruir su rastro.

El campo del estudio de fenómenos anómalos sufre de archivos cuyo estado real no se puede determinar: ¿este caso está cerrado? ¿está en revisión? ¿la conclusión es del autor o del archivo? Sin un modelo de lifecycle explícito, el lector externo no sabe en qué estatus epistémico está la información.

## Decisión

`Case` es una entidad con identidad estable y secuencia inmutable de **revisiones** (`CaseRevision`). Cada revisión es un snapshot inmutable referenciado por hash de su contenido estructurado. El caso evoluciona pasando entre estados definidos (`CaseStatus`) mediante transiciones explícitas, cada una registrada con autoría, motivación y, opcionalmente, evidencia disparadora.

La cita estable de un caso es siempre `<case_id>@<revision_hash>`. Citar `<case_id>` sin revisión apunta a la **última publicada**, pero la doc indica cómo citar a una revisión específica para reproducibilidad.

## Modelo

```
Case {
  id: CaseId                       # ULID estable
  current_revision: RevisionHash   # apunta a la cabeza
  revisions: [CaseRevision]        # historial completo, append-only
  curator: ActorId                 # actor responsable canónico
  co_curators: [ActorId]
  created_at: timestamp
  schema_version: SemVer
}

CaseRevision {
  hash: RevisionHash               # hash del contenido estructurado del revision
  parent: RevisionHash?            # null en la primera; cada siguiente apunta a la anterior
  status: CaseStatus               # estado en esta revisión
  title: str
  abstract: markdown
  evidence_refs: [EvidenceRef]     # subconjunto de evidencia que el caso considera
  claim_refs: [ClaimRef]
  hypothesis_set_id: HypothesisSetId?
  active_conclusion: ConclusionId?
  geographic_anchors: [SpatialAnchor]   # ADR-0013
  temporal_anchors: [TemporalAnchor]    # ADR-0012
  authored_by: ActorId
  authored_at: timestamp
  transition: TransitionRecord     # qué cambió respecto a la revisión padre
  notes: markdown?
}
```

### CaseStatus

Siete estados, suficientes para cubrir el lifecycle real sin barroquismo:

| Status | Significado |
|--------|------------|
| `draft` | En construcción. No referenciable como caso publicado. Visible solo al curador. |
| `under_review` | Sometido a revisión interna por co-curadores antes de publicar. |
| `published` | Públicamente visible y citable. La revisión publicada es snapshot citable. |
| `revised` | Republicado con cambios materiales tras `published`. Las revisiones anteriores permanecen citables. |
| `disputed` | Existe disputa documentada sobre evidencia, claims o conclusión. El caso sigue visible con marca de disputa. |
| `superseded_by` | Reemplazado por un caso distinto que cubre el mismo evento con mejor evidencia o enfoque. Referencia obligatoria al sucesor. |
| `retracted` | Retirado del uso operativo por razones documentadas. Sigue accesible como histórico, marcado y con motivación. |

`retracted` **no implica borrado**. Implica marca y aislamiento de las vistas operativas. El contenido permanece reproducible.

### Transiciones permitidas

```
draft           → under_review | retracted
under_review    → draft | published | retracted
published       → revised | disputed | superseded_by | retracted
revised         → revised | disputed | superseded_by | retracted
disputed        → revised | superseded_by | retracted | published   (este último solo si la disputa se resuelve sin cambios)
superseded_by   → (terminal; no más transiciones, pero el caso sigue accesible)
retracted       → (terminal; no más transiciones, sigue accesible)
```

Transiciones no listadas son inválidas. La validez se chequea en la capa de modelo.

### TransitionRecord

```
TransitionRecord {
  from_status: CaseStatus?
  to_status: CaseStatus
  reason: TransitionReason         # ver enumeración
  triggered_by: [EvidenceRef | ClaimRef | ConclusionId | ExternalReference]
  rationale: markdown              # justificación legible
  authorized_by: ActorId
  authorized_at: timestamp
  signature: Signature?            # opcional
}
```

`TransitionReason` cubre: `initial_publication`, `new_evidence`, `evidence_retraction`, `evidence_authentication_change`, `new_hypothesis_added`, `conclusion_changed`, `dispute_raised`, `dispute_resolved`, `superseded_by_better_case`, `legal_takedown`, `witness_request_anonymization`, `do_no_harm`, `archival_decision`.

### Revisiones como hashes encadenados

Cada `CaseRevision` se identifica por hash del contenido estructurado canonicalizado (sin timestamp del cómputo del hash, sí con timestamp lógico de autoría). El hash es bit a bit reproducible.

El conjunto de revisiones forma una cadena lineal (no DAG por ahora — fork explícito mediante `superseded_by` apuntando a un caso distinto). Esta linealidad se justifica más abajo.

### Cita estable

Tres formas:

| Cita | Significado |
|------|-------------|
| `aip:case/<case_id>` | Resuelve a la última revisión publicada. Para uso narrativo. |
| `aip:case/<case_id>@<revision_hash>` | Snapshot exacto. Reproducible para siempre. **Forma preferida para citas académicas.** |
| `aip:case/<case_id>@head` | Forma explícita de "la última". Equivalente a la primera. |

La documentación pública del proyecto exige la segunda forma en cualquier publicación que pretenda ser reproducible.

### Vistas materializadas y consultas históricas

El sistema soporta consultas tipo "¿qué conclusión sostenía el caso X el 2031-04-12?": resuelve a la revisión más reciente con `authored_at <= 2031-04-12T23:59:59Z`. Esa revisión se materializa con su evidencia y su `Conclusion` exactas. Imposible falsificar restropectivamente.

### Casos derivados y forks

Un investigador externo puede crear un caso derivado que comparta evidencia con un caso existente pero ofrezca un análisis distinto. El derivado no muta el original; ambos coexisten. La relación entre ellos se materializa en el grafo de conocimiento (ADR-0011) como `derived_from` o `disagrees_with`.

## Justificación

### Por qué cadena lineal y no DAG

Un DAG de revisiones es atractivo (soportaría ramas paralelas). En la práctica reproduce los problemas de Git para colaboradores no técnicos: merges, conflictos, rebase. Para la mayoría del flujo (un curador trabaja un caso), la linealidad es suficiente. Los forks legítimos se modelan como casos distintos con relación `derived_from`. Esta decisión se reevaluará si una fase posterior demuestra demanda real de DAG.

### Por qué el caso es revisable y la evidencia no

ADR-0002 ya estableció la asimetría. Aquí se operacionaliza. La evidencia es realidad material: no la modificamos. El caso es razonamiento sobre evidencia: puede mejorar.

### Por qué la transición lleva motivación

Sin motivación, los cambios de status se acumulan como ruido. Con motivación, son material auditable y citable: "el caso pasó a disputed el 2027-03-15 porque apareció evidencia E-XXX que contradice la conclusión Y".

### Por qué `disputed` es estado, no marca

Hacerlo estado obliga a tomar decisión sobre disputa: o se mantiene la conclusión (vuelta a published), o se revisa (revised), o se cierra (retracted). Un caso no puede flotar indefinidamente en disputa.

### Por qué retracción no es borrado

Lo mismo que en ADR-0006 para evidencia. La retracción es marca; el contenido sigue accesible por trazabilidad.

## Consecuencias

**Positivas**
- El estado epistémico de cada caso es siempre legible.
- Citas académicas tienen forma estable y reproducible.
- La historia de un caso es interrogable: cómo evolucionó, qué evidencia disparó qué cambio.
- Disputa modelada como estado evita zombies de "disputado para siempre".

**Negativas**
- Curadores deben aprender el modelo de transiciones.
- Cualquier cambio sustantivo requiere revisión con autoría — incómodo para correcciones triviales (typos). Mitigado: typos en `notes` son `revised` con `TransitionReason.editorial_only` (subcategoría que indica "no afectó conclusión").
- Crecimiento de almacenamiento con la historia. Aceptable: revisiones son ligeras comparadas con la evidencia raw que referencian.

**Neutras**
- Forks como casos distintos en lugar de ramas exige más explicación documental, pero da mayor neutralidad: ningún caso "es el oficial".

## Alternativas consideradas

### A. Caso mutable con historial interno
**Descripción:** Editar el caso, mantener un changelog interno.
**Razón de rechazo:** El changelog interno se erosiona. La revisión inmutable es robusta.

### B. DAG de revisiones desde el inicio
**Descripción:** Soportar ramas paralelas y merges desde el día uno.
**Razón de rechazo:** Complejidad alta sin demanda demostrada. Forks externos cubren los casos legítimos.

### C. Estados sin transiciones explícitas
**Descripción:** Solo guardar el estado actual; no requerir motivación.
**Razón de rechazo:** Pierde trazabilidad bit a bit. Imposibilita auditoría.

### D. Borrado físico al retractar
**Descripción:** `retracted` significa "borrar del repo".
**Razón de rechazo:** Reescribe historia. Solo aceptable por orden legal documentada.

## Alineación con ADR-0000

**Propiedades afectadas:** P1, P2, P3, P5, P8, P11, P12.

**Cómo se alinean:**
- P2 (trazabilidad): el lifecycle preserva la historia completa de razonamiento sobre cada caso.
- P5 (reproducibilidad): la cita por `revision_hash` permite reproducir el estado del caso en cualquier momento.
- P11 (inmutabilidad de evidencia): el caso es el lugar donde se concentra el cambio; la evidencia subyacente sigue inmutable.
- P12 (do-no-harm): `TransitionReason.witness_request_anonymization` y `legal_takedown` operacionalizan la gestión de daño.

**Tensión:** Friction editorial vs. integridad histórica. Aceptada: el proyecto es de archivo, no de redacción periódica.

## Referencias

- Datomic / event sourcing patterns. Prior art para snapshots inmutables.
- Wikipedia / Mediawiki histories. Prior art negativa: revisiones mutables que ensucian auditoría.
- Git. Prior art para hashes encadenados, con la decisión consciente de no adoptar DAG todavía.

---

## Historial de enmiendas

*Sin enmiendas a fecha de aceptación.*
