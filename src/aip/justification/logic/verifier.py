"""Verificador estructural de :class:`InferenceProof`.

Hace cinco checks sobre la DAG declarada:

1. **Vocabulario** — cada ``rule`` ∈ vocabulario cerrado.
2. **Arity** — cantidad de inputs coincide con la regla.
3. **Referencias** — cada input_claim_id existe (premise o derived); cada
   output_claim_id existe en derived_claims y referencia esta inferencia
   en su ``inferred_by``.
4. **Acyclic** — no hay ciclos en la DAG (DFS).
5. **Reachability** — ``conclusion_claim_id`` es alcanzable desde alguna
   premisa via inferencias.

Además, identifica las inferencias con reglas no-deductivas (abduction) y
las reporta como ``weak_inferences`` — el caller decide qué hacer con esa
información.

Lo que el verifier **NO** hace:

- No verifica que el *texto* del output realmente se siga de los textos de
  los inputs bajo la regla. Solo verifica estructura.
- No verifica que la verdad de las premisas. Trabajo del analista.
- No verifica que ``proof_hash`` recompute (eso es ``verify_proof_hash``,
  función separada).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.justification.logic.models import (
    PROOF_TYPE,
    DerivedClaim,
    InferenceProof,
    InferenceStep,
    Premise,
)
from aip.justification.logic.rules import ALLOWED_RULES, check_arity, is_weak


@dataclass(frozen=True)
class WeakInferenceFlag:
    """Inferencia con regla no-deductiva. El verifier la marca pero no
    rechaza el proof — abduction es legítimo en investigación, solo debe
    estar identificado."""

    inference_id: str
    rule: str
    output_claim_id: str


@dataclass(frozen=True)
class VerifyLogicResult:
    """Resultado de la verificación estructural de un :class:`InferenceProof`."""

    ok: bool
    errors: tuple[str, ...] = ()
    weak_inferences: tuple[WeakInferenceFlag, ...] = ()
    structure: dict[str, object] = field(default_factory=dict)


def _canonical_dict(proof: InferenceProof) -> dict[str, JsonValue]:
    """Diccionario canónico del proof completo (incluye ``proof_hash``)."""
    return {
        "proof_type": proof.proof_type,
        "schema_version": proof.schema_version,
        "proof_id": proof.proof_id,
        "target_justification_id": proof.target_justification_id,
        "target_justification_hash": proof.target_justification_hash,
        "premises": [
            {
                "id": p.id,
                "text": p.text,
                "evidence_refs": list(p.evidence_refs),
                "kind": p.kind,
            }
            for p in proof.premises
        ],
        "inferences": [
            {
                "id": i.id,
                "rule": i.rule,
                "input_claim_ids": list(i.input_claim_ids),
                "output_claim_id": i.output_claim_id,
                "text": i.text,
            }
            for i in proof.inferences
        ],
        "derived_claims": [
            {"id": c.id, "text": c.text, "inferred_by": c.inferred_by}
            for c in proof.derived_claims
        ],
        "conclusion_claim_id": proof.conclusion_claim_id,
        "proof_hash": proof.proof_hash,
    }


def compute_proof_hash(proof: InferenceProof) -> str:
    """SHA-256 hex JCS del proof excluyendo ``proof_hash``."""
    data = _canonical_dict(proof)
    data.pop("proof_hash", None)
    return sha256_hex(jcs_canonicalize(cast(JsonValue, data)))


def verify_proof_hash(proof: InferenceProof) -> bool:
    """Recomputa el ``proof_hash`` y lo compara con el declarado."""
    return compute_proof_hash(proof) == proof.proof_hash


# --------------------------------------------------------------------- structural


def _detect_cycle(
    inference_by_id: dict[str, InferenceStep],
    claim_to_inference: dict[str, str],
) -> str | None:
    """DFS clásico de detección de ciclos sobre la DAG de inferencias.

    Edge: si claim X es input de inferencia I, e I produce claim Y, entonces
    hay edge X → Y. Detectamos ciclos via 3 colores (white/gray/black).

    Devuelve ``None`` si la DAG es acíclica, o un mensaje describiendo el
    ciclo encontrado.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    # Build adjacency: from each input claim to each output claim of inferences
    # that consume it.
    adj: dict[str, list[str]] = {}
    for inf in inference_by_id.values():
        for in_id in inf.input_claim_ids:
            adj.setdefault(in_id, []).append(inf.output_claim_id)

    def dfs(node: str, stack: list[str]) -> str | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in adj.get(node, []):
            c = color.get(nxt, WHITE)
            if c == GRAY:
                # Cycle: find the start of the cycle in the stack.
                if nxt in stack:
                    cycle_start = stack.index(nxt)
                    cycle_path = [*stack[cycle_start:], nxt]
                    return " → ".join(cycle_path)
                return f"{node} → {nxt}"
            if c == WHITE:
                result = dfs(nxt, stack)
                if result is not None:
                    return result
        color[node] = BLACK
        stack.pop()
        return None

    for node_id in list(adj.keys()) + list(claim_to_inference.keys()):
        if color.get(node_id, WHITE) == WHITE:
            cycle = dfs(node_id, [])
            if cycle is not None:
                return cycle
    return None


def _reachable_from_premises(
    conclusion_id: str,
    premise_ids: set[str],
    inference_by_id: dict[str, InferenceStep],
    claim_to_inference: dict[str, str],
) -> bool:
    """``True`` si ``conclusion_id`` es alcanzable backward desde alguna premisa.

    BFS hacia atrás desde la conclusión: para cada claim, busca la inferencia
    que lo produce, y sigue a sus inputs. Si todos los caminos terminan en
    premisas, la conclusión es reachable.
    """
    # Forward-reachability from a premise to the conclusion.
    # Build forward adjacency: claim X → all claims Y produced by inferences
    # that consume X.
    adj: dict[str, list[str]] = {}
    for inf in inference_by_id.values():
        for in_id in inf.input_claim_ids:
            adj.setdefault(in_id, []).append(inf.output_claim_id)

    visited: set[str] = set()
    stack: list[str] = list(premise_ids)
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if node == conclusion_id:
            return True
        stack.extend(adj.get(node, []))
    return False


def _validate_single_inference(
    inf: InferenceStep,
    *,
    all_claim_ids: set[str],
    derived_by_id: dict[str, DerivedClaim],
    errors: list[str],
    rules_used: dict[str, int],
    weak: list[WeakInferenceFlag],
) -> None:
    """Aplica checks 1-3 a una inferencia individual. Muta listas in-place
    (cohesión con el caller). Extraído para reducir complejidad ciclomática
    de :func:`verify_structural`."""
    if inf.rule not in ALLOWED_RULES:
        errors.append(
            f"inference {inf.id!r}: rule {inf.rule!r} not in allowed vocabulary "
            f"{sorted(ALLOWED_RULES)}."
        )
        return
    rules_used[inf.rule] = rules_used.get(inf.rule, 0) + 1
    arity_err = check_arity(inf.rule, len(inf.input_claim_ids))
    if arity_err is not None:
        errors.append(f"inference {inf.id!r}: {arity_err}.")
    for in_id in inf.input_claim_ids:
        if in_id not in all_claim_ids:
            errors.append(
                f"inference {inf.id!r}: input_claim_id {in_id!r} does not "
                "exist as premise or derived claim."
            )
    if inf.output_claim_id not in derived_by_id:
        errors.append(
            f"inference {inf.id!r}: output_claim_id {inf.output_claim_id!r} "
            "is not declared in derived_claims."
        )
    else:
        output_claim = derived_by_id[inf.output_claim_id]
        if output_claim.inferred_by != inf.id:
            errors.append(
                f"inference {inf.id!r}: output claim "
                f"{inf.output_claim_id!r} has inferred_by="
                f"{output_claim.inferred_by!r}, expected {inf.id!r}."
            )
    if is_weak(inf.rule):
        weak.append(
            WeakInferenceFlag(
                inference_id=inf.id,
                rule=inf.rule,
                output_claim_id=inf.output_claim_id,
            )
        )


def verify_structural(proof: InferenceProof) -> VerifyLogicResult:
    """Verifica la estructura completa del proof.

    NO verifica ``proof_hash`` — eso es ``verify_proof_hash``. Llamar a las
    dos por separado para tener mensajes claros.
    """
    errors: list[str] = []

    if proof.proof_type != PROOF_TYPE:
        errors.append(
            f"unexpected proof_type {proof.proof_type!r}; expected {PROOF_TYPE!r}."
        )

    premise_by_id: dict[str, Premise] = {p.id: p for p in proof.premises}
    derived_by_id: dict[str, DerivedClaim] = {
        c.id: c for c in proof.derived_claims
    }
    inference_by_id: dict[str, InferenceStep] = {
        i.id: i for i in proof.inferences
    }
    all_claim_ids = set(premise_by_id) | set(derived_by_id)

    # Checks 1-3 per inference: vocabulary, arity, refs.
    rules_used: dict[str, int] = {}
    weak: list[WeakInferenceFlag] = []
    for inf in proof.inferences:
        _validate_single_inference(
            inf,
            all_claim_ids=all_claim_ids,
            derived_by_id=derived_by_id,
            errors=errors,
            rules_used=rules_used,
            weak=weak,
        )

    # Check 4: every derived claim must have its inferred_by pointing at an
    # existing inference whose output is this claim. (Catches orphan derived
    # claims not produced by any declared inference.)
    for claim in proof.derived_claims:
        if claim.inferred_by not in inference_by_id:
            errors.append(
                f"derived claim {claim.id!r}: inferred_by "
                f"{claim.inferred_by!r} references unknown inference."
            )

    # Check 5: no cycles.
    claim_to_inference = {
        c.id: c.inferred_by for c in proof.derived_claims
    }
    cycle = _detect_cycle(inference_by_id, claim_to_inference)
    if cycle is not None:
        errors.append(f"cycle detected in DAG: {cycle}.")

    # Check 6: conclusion exists.
    if proof.conclusion_claim_id not in all_claim_ids:
        errors.append(
            f"conclusion_claim_id {proof.conclusion_claim_id!r} is not "
            "declared as a premise or derived claim."
        )

    # Check 7: conclusion is reachable from premises via the DAG.
    if not errors:  # Only worth checking if the DAG is well-formed.
        if proof.conclusion_claim_id in premise_by_id:
            # Conclusion = premise (trivial case, valid but odd — flag info).
            pass
        else:
            reachable = _reachable_from_premises(
                proof.conclusion_claim_id,
                set(premise_by_id),
                inference_by_id,
                claim_to_inference,
            )
            if not reachable:
                errors.append(
                    f"conclusion {proof.conclusion_claim_id!r} is not "
                    "reachable from premises via the inference DAG."
                )

    structure: dict[str, object] = {
        "premise_count": len(proof.premises),
        "inference_count": len(proof.inferences),
        "derived_claim_count": len(proof.derived_claims),
        "rules_used": rules_used,
        "weak_rule_uses": len(weak),
    }

    return VerifyLogicResult(
        ok=not errors,
        errors=tuple(errors),
        weak_inferences=tuple(weak),
        structure=structure,
    )
