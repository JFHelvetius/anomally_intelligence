"""Vocabulario cerrado de reglas de inferencia v1.

V1 cubre lógica proposicional básica + un poco de instanciación. Suficiente
para ~80% de razonamientos forenses prácticos. Lo que queda fuera v1:

- Negación explícita (¬), cuantificadores universales/existenciales
- Modal logic, lógicas multi-valuadas, probabilidades
- Inference rules estadísticas (regression, correlation)

Cada regla tiene tres atributos load-bearing:

- ``arity`` (mínimo, máximo|None) — cuántos inputs admite
- ``classification`` — ``"deductive"`` o ``"weak"``
  - **deductive**: si los inputs son ciertos, el output es necesariamente cierto
  - **weak**: el output es plausible, no necesario. **Flaggeado** por el verifier
- ``description`` — humano-legible, para inspección

El verifier estructural verifica arity. La verificación semántica (que el
texto del output realmente se siga de los textos de los inputs bajo la regla)
queda explícitamente fuera de scope — sin language formal en V1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class RuleSpec:
    """Especificación de una regla del vocabulario."""

    name: str
    min_inputs: int
    max_inputs: int | None  # None = sin límite superior
    classification: str  # "deductive" | "weak"
    description: str


_RULES: Final[tuple[RuleSpec, ...]] = (
    RuleSpec(
        name="modus_ponens",
        min_inputs=2,
        max_inputs=2,
        classification="deductive",
        description=(
            "Of A and (A→B), concludes B. Two inputs: the antecedent claim "
            "and the conditional claim."
        ),
    ),
    RuleSpec(
        name="conjunction_intro",
        min_inputs=2,
        max_inputs=None,
        classification="deductive",
        description=(
            "Of A, B, C, …, concludes A∧B∧C∧…. Two or more inputs, no upper "
            "bound."
        ),
    ),
    RuleSpec(
        name="inference_to_specific_instance",
        min_inputs=2,
        max_inputs=2,
        classification="deductive",
        description=(
            "Of ∀x P(x) and (x=a), concludes P(a). Two inputs: universal "
            "premise + instance identification."
        ),
    ),
    RuleSpec(
        name="elimination_by_contradiction",
        min_inputs=2,
        max_inputs=2,
        classification="deductive",
        description=(
            "Of A and ¬A, concludes ⊥ (contradiction; refutation of premise "
            "set). Two inputs in tension."
        ),
    ),
    RuleSpec(
        name="abduction_to_best_explanation",
        min_inputs=1,
        max_inputs=None,
        classification="weak",
        description=(
            "Of observations O1, O2, …, concludes 'H is the best available "
            "explanation'. **Non-deductive** — H could be wrong even if all "
            "Oi are true. Flagged by the verifier."
        ),
    ),
)
"""Tabla maestra de reglas. Cerrada para v1. Añadir nuevas requiere ADR."""


ALLOWED_RULES: Final[frozenset[str]] = frozenset(r.name for r in _RULES)
"""Set de nombres válidos para ``InferenceStep.rule``."""

WEAK_RULES: Final[frozenset[str]] = frozenset(
    r.name for r in _RULES if r.classification == "weak"
)
"""Subset de reglas no-deductivas. El verifier las flaggea en su output."""

_BY_NAME: Final[dict[str, RuleSpec]] = {r.name: r for r in _RULES}


def get_rule(name: str) -> RuleSpec | None:
    """Devuelve la spec de una regla o ``None`` si no es válida."""
    return _BY_NAME.get(name)


def check_arity(rule_name: str, input_count: int) -> str | None:
    """Verifica que ``input_count`` esté dentro del rango de la regla.

    Devuelve ``None`` si OK, o un mensaje de error descriptivo si falla.
    Asume que ``rule_name`` ya está en :data:`ALLOWED_RULES`; si no, devuelve
    error de regla desconocida.
    """
    spec = _BY_NAME.get(rule_name)
    if spec is None:
        return f"unknown rule {rule_name!r}"
    if input_count < spec.min_inputs:
        return (
            f"rule {rule_name!r} requires at least {spec.min_inputs} inputs; "
            f"got {input_count}"
        )
    if spec.max_inputs is not None and input_count > spec.max_inputs:
        return (
            f"rule {rule_name!r} admits at most {spec.max_inputs} inputs; "
            f"got {input_count}"
        )
    return None


def is_weak(rule_name: str) -> bool:
    """``True`` si la regla está clasificada como no-deductiva."""
    return rule_name in WEAK_RULES
