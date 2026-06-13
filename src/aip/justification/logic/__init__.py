"""Machine-checkable inference proofs sobre :class:`InvestigationJustification`.

Capa epistémica del proyecto. La crypto (Phases 1-4) prueba "evidencia íntegra";
este módulo prueba "razonamiento estructuralmente válido". Único en el espacio
open-source forense.

Modelo: :class:`InferenceProof` = DAG explícita de
    premisas (ancladas a evidencia) → inferencias (etiquetadas con reglas) →
    claims derivados → conclusión

Vocabulario de reglas v1 (cerrado, ver :mod:`rules`):

- ``modus_ponens`` — deductive
- ``conjunction_intro`` — deductive
- ``inference_to_specific_instance`` — deductive
- ``elimination_by_contradiction`` — deductive
- ``abduction_to_best_explanation`` — **weak** (no-deductive, flaggeado)

Lo que **NO** verifica el sistema:

- Verdad de las premisas — depende de evidencia externa, trabajo del analista.
- Que el texto del output realmente se siga de los textos de los inputs bajo
  la regla — sin language formal en V1, sólo verificamos el esqueleto.

Lo que SÍ verifica :func:`verify_structural`:

- Cada inferencia referencia inputs existentes (premise o claim previo)
- Cada ``rule`` ∈ vocabulario cerrado
- Arity coincide
- Sin ciclos en la DAG
- Conclusión alcanzable desde premisas via inferencias
- Inferencias con reglas no-deductivas → flaggeadas
"""

from __future__ import annotations

from aip.justification.logic.models import (
    ALLOWED_PREMISE_KINDS,
    INFERENCE_PROOF_SCHEMA_VERSION,
    PROOF_TYPE,
    DerivedClaim,
    InferenceProof,
    InferenceStep,
    Premise,
)
from aip.justification.logic.rules import (
    ALLOWED_RULES,
    WEAK_RULES,
    RuleSpec,
    check_arity,
    get_rule,
    is_weak,
)
from aip.justification.logic.store import (
    INFERENCE_PROOFS_DIRNAME,
    InferenceProofError,
    decode_proof,
    encode_proof,
    load_proof,
    proof_path,
)
from aip.justification.logic.verifier import (
    VerifyLogicResult,
    WeakInferenceFlag,
    compute_proof_hash,
    verify_proof_hash,
    verify_structural,
)

__all__ = [
    "ALLOWED_PREMISE_KINDS",
    "ALLOWED_RULES",
    "INFERENCE_PROOFS_DIRNAME",
    "INFERENCE_PROOF_SCHEMA_VERSION",
    "PROOF_TYPE",
    "WEAK_RULES",
    "DerivedClaim",
    "InferenceProof",
    "InferenceProofError",
    "InferenceStep",
    "Premise",
    "RuleSpec",
    "VerifyLogicResult",
    "WeakInferenceFlag",
    "check_arity",
    "compute_proof_hash",
    "decode_proof",
    "encode_proof",
    "get_rule",
    "is_weak",
    "load_proof",
    "proof_path",
    "verify_proof_hash",
    "verify_structural",
]
