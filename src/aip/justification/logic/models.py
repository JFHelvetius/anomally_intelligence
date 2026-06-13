"""Modelos del Inference Proof Engine (Phase epistémica).

Una :class:`InferenceProof` es una DAG explícita de razonamiento que conecta
*premisas* (cada una anclada a evidencia del archive) con un *conclusion_claim*
via *inference steps* etiquetadas con reglas de un vocabulario cerrado.

Diferencia con :class:`aip.justification.InvestigationJustification`:

- ``InvestigationJustification`` (ADR-0040) lista el *inventario* de evidencias
  y assessments que respaldan una conclusión — pero no explicita el razonamiento.
- ``InferenceProof`` (este módulo) declara el *razonamiento estructural*:
  premisas → inferencias → claims derivados → conclusión.

Ambos artefactos son independientes y complementarios. Un proof puede atestar
una justification sin modificarla (atado por ``target_justification_hash``).

Lo que el sistema verifica de un proof:

- Cada inferencia referencia inputs existentes (premisas o claims previos)
- Cada ``rule`` ∈ vocabulario cerrado (ver :mod:`aip.justification.logic.rules`)
- La arity (cantidad de inputs) coincide con la regla
- ``conclusion_claim_id`` es alcanzable desde premisas via inferencias
- No hay ciclos en la DAG
- Inferencias con reglas no-deductivas (abduction) quedan flaggeadas

Lo que el sistema **NO** verifica:

- Verdad de las premisas — depende de evidencia externa, trabajo del analista
- Que el *texto* del output realmente se siga de los textos de los inputs
  bajo la regla — sin language formal en V1, sólo verificamos el esqueleto
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

INFERENCE_PROOF_SCHEMA_VERSION: Final[str] = "1"

PROOF_TYPE: Final[str] = "aip.justification.inference-proof.v1"
"""Discriminador. v2 será una clave distinta — los lectores rechazan tipos
desconocidos."""

ALLOWED_PREMISE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "observation",
        "documentary",
        "expert_assertion",
        "domain_axiom",
    }
)
"""Taxonomía cerrada de tipos de premisa:

- ``observation`` — hecho observado directamente (e.g., "el objeto aparece en IMG_001")
- ``documentary`` — afirmación respaldada por documento (e.g., "FAA registró vuelo X")
- ``expert_assertion`` — afirmación de experto identificable (e.g., "El Dr. Y afirma...")
- ``domain_axiom`` — premisa convencionalmente aceptada del dominio
  (e.g., "los aviones comerciales tienen transponder activo en espacio controlado")
"""

_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-]+$")
_SHA256_HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, order=True)
class Premise:
    """Premisa anclada a evidencia. Inmutable, totalmente ordenable.

    ``evidence_refs`` son hashes SHA-256 hex (lowercase) de Evidence entries
    del archive. El verifier estructural no comprueba que existan en el archive
    — eso es trabajo separado (``aip evidence show <hash>``). Sólo verifica
    el formato.
    """

    id: str
    text: str
    evidence_refs: tuple[str, ...]
    kind: str

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"premise id {self.id!r} contains characters outside [A-Za-z0-9._-]."
            )
        if not self.text:
            raise ValueError("premise text must be non-empty.")
        if self.kind not in ALLOWED_PREMISE_KINDS:
            raise ValueError(
                f"invalid premise kind {self.kind!r}; "
                f"must be one of {sorted(ALLOWED_PREMISE_KINDS)}."
            )
        for ref in self.evidence_refs:
            if not _SHA256_HEX_PATTERN.match(ref):
                raise ValueError(
                    f"evidence_ref {ref!r} must be SHA-256 hex lowercase."
                )


@dataclass(frozen=True, order=True)
class DerivedClaim:
    """Claim derivado por aplicación de una :class:`InferenceStep`.

    ``inferred_by`` referencia el ``id`` de la InferenceStep que lo derivó.
    Cada DerivedClaim tiene exactamente una inferencia que lo produce —
    si la misma proposición se deriva por dos caminos distintos, debe
    declararse como dos DerivedClaims con ids distintos.
    """

    id: str
    text: str
    inferred_by: str

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"derived claim id {self.id!r} contains characters outside [A-Za-z0-9._-]."
            )
        if not self.text:
            raise ValueError("derived claim text must be non-empty.")
        if not _ID_PATTERN.match(self.inferred_by):
            raise ValueError(
                f"inferred_by {self.inferred_by!r} must be a valid id."
            )


@dataclass(frozen=True, order=True)
class InferenceStep:
    """Paso explícito de inferencia.

    ``input_claim_ids`` referencia ids de Premises o DerivedClaims previos.
    El verifier verifica:

    - Que cada id exista (en premises o claims declarados antes en la DAG)
    - Que la arity (cantidad de inputs) coincida con la regla
    - Que ``output_claim_id`` exista en :attr:`InferenceProof.derived_claims`
      y que ESE claim referencie esta inference vía ``inferred_by``
    """

    id: str
    rule: str
    input_claim_ids: tuple[str, ...]
    output_claim_id: str
    text: str

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.id):
            raise ValueError(
                f"inference id {self.id!r} contains characters outside [A-Za-z0-9._-]."
            )
        if not self.rule:
            raise ValueError("inference rule must be non-empty.")
        if not self.input_claim_ids:
            raise ValueError(
                f"inference {self.id!r} must have at least one input_claim_id."
            )
        for in_id in self.input_claim_ids:
            if not _ID_PATTERN.match(in_id):
                raise ValueError(
                    f"input_claim_id {in_id!r} contains invalid characters."
                )
        if not _ID_PATTERN.match(self.output_claim_id):
            raise ValueError(
                f"output_claim_id {self.output_claim_id!r} contains invalid characters."
            )
        if not self.text:
            raise ValueError("inference text must be non-empty.")


@dataclass(frozen=True)
class InferenceProof:
    """DAG completa de razonamiento atestando una conclusión.

    Identidad canónica: ``proof_id`` + ``target_justification_hash``. Mover el
    target justification a otro hash invalida ``proof_hash``.

    ``proof_hash`` se computa via JCS sobre todos los campos excluyendo el
    propio ``proof_hash`` — sigue el patrón de :class:`TransparencyManifest`
    y :class:`WitnessAttestation`.
    """

    proof_type: str
    schema_version: str
    proof_id: str
    target_justification_id: str
    target_justification_hash: str
    premises: tuple[Premise, ...]
    inferences: tuple[InferenceStep, ...]
    derived_claims: tuple[DerivedClaim, ...]
    conclusion_claim_id: str
    proof_hash: str

    def __post_init__(self) -> None:
        if self.proof_type != PROOF_TYPE:
            raise ValueError(
                f"proof_type must be {PROOF_TYPE!r}; got {self.proof_type!r}."
            )
        if not _ID_PATTERN.match(self.proof_id):
            raise ValueError(
                f"proof_id {self.proof_id!r} contains invalid characters."
            )
        if not self.target_justification_id:
            raise ValueError("target_justification_id must be non-empty.")
        if not _SHA256_HEX_PATTERN.match(self.target_justification_hash):
            raise ValueError(
                "target_justification_hash must be SHA-256 hex lowercase."
            )
        if not _SHA256_HEX_PATTERN.match(self.proof_hash):
            raise ValueError("proof_hash must be SHA-256 hex lowercase.")
        if not _ID_PATTERN.match(self.conclusion_claim_id):
            raise ValueError(
                f"conclusion_claim_id {self.conclusion_claim_id!r} contains invalid characters."
            )
        # Sorted-by-id requirement (canonical serialization stability).
        for name, items in (
            ("premises", self.premises),
            ("inferences", self.inferences),
            ("derived_claims", self.derived_claims),
        ):
            sorted_items = tuple(sorted(items, key=lambda x: x.id))
            if items != sorted_items:
                raise ValueError(
                    f"{name} must be canonically sorted by id (ascending)."
                )
        # Unique ids per collection.
        for name, ids in (
            ("premises", [p.id for p in self.premises]),
            ("inferences", [i.id for i in self.inferences]),
            ("derived_claims", [c.id for c in self.derived_claims]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"{name} contains duplicate ids.")
        # No id collision between premises and derived claims (they share namespace).
        all_claim_ids = [p.id for p in self.premises] + [
            c.id for c in self.derived_claims
        ]
        if len(set(all_claim_ids)) != len(all_claim_ids):
            raise ValueError(
                "premise ids and derived_claim ids share namespace; "
                "they must all be distinct."
            )
