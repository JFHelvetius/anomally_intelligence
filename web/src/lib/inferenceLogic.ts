/**
 * Client-side verification de InferenceProof (Phase 5).
 *
 * Mirror exacto de `src/aip/justification/logic/verifier.py`. Mismos checks:
 *  1. proof_hash recomputa via JCS+SHA256
 *  2. rule ∈ vocabulario cerrado
 *  3. arity coincide con la regla
 *  4. inputs existen (premise o claim previo)
 *  5. output_claim_id existe y referencia esta inference en su inferred_by
 *  6. derived claim inferred_by referencia una inference existente
 *  7. DAG acyclic (DFS 3-color)
 *  8. conclusion alcanzable desde premises via forward-BFS
 *
 * NO verifica verdad de premisas. Solo estructura.
 */

import { jcsCanonicalize, sha256Hex, type JCSValue } from './jcs'

// ─── Types ───────────────────────────────────────────────────────────────

export interface Premise {
  id: string
  text: string
  evidence_refs: string[]
  kind: 'observation' | 'documentary' | 'expert_assertion' | 'domain_axiom'
}

export interface InferenceStep {
  id: string
  rule: string
  input_claim_ids: string[]
  output_claim_id: string
  text: string
}

export interface DerivedClaim {
  id: string
  text: string
  inferred_by: string
}

export interface InferenceProof {
  proof_type: string
  schema_version: string
  proof_id: string
  target_justification_id: string
  target_justification_hash: string
  premises: Premise[]
  inferences: InferenceStep[]
  derived_claims: DerivedClaim[]
  conclusion_claim_id: string
  proof_hash: string
}

// ─── Rules ───────────────────────────────────────────────────────────────

interface RuleSpec {
  name: string
  minInputs: number
  maxInputs: number | null
  classification: 'deductive' | 'weak'
  description: string
}

const RULES: ReadonlyArray<RuleSpec> = [
  { name: 'modus_ponens', minInputs: 2, maxInputs: 2, classification: 'deductive',
    description: 'From A and (A→B), conclude B.' },
  { name: 'conjunction_intro', minInputs: 2, maxInputs: null, classification: 'deductive',
    description: 'From A, B, …, conclude A∧B∧….' },
  { name: 'inference_to_specific_instance', minInputs: 2, maxInputs: 2, classification: 'deductive',
    description: 'From ∀x P(x) and x=a, conclude P(a).' },
  { name: 'elimination_by_contradiction', minInputs: 2, maxInputs: 2, classification: 'deductive',
    description: 'From A and ¬A, conclude ⊥.' },
  { name: 'abduction_to_best_explanation', minInputs: 1, maxInputs: null, classification: 'weak',
    description: 'From observations, conclude best available explanation. NON-DEDUCTIVE.' },
]

const RULES_BY_NAME: Record<string, RuleSpec> = Object.fromEntries(RULES.map(r => [r.name, r]))
export const ALLOWED_RULES: ReadonlySet<string> = new Set(RULES.map(r => r.name))
export const WEAK_RULES: ReadonlySet<string> = new Set(RULES.filter(r => r.classification === 'weak').map(r => r.name))

export function getRule(name: string): RuleSpec | undefined {
  return RULES_BY_NAME[name]
}

export function isWeakRule(name: string): boolean {
  return WEAK_RULES.has(name)
}

function checkArity(ruleName: string, inputCount: number): string | null {
  const spec = RULES_BY_NAME[ruleName]
  if (spec === undefined) return `unknown rule '${ruleName}'`
  if (inputCount < spec.minInputs) {
    return `rule '${ruleName}' requires at least ${spec.minInputs} inputs; got ${inputCount}`
  }
  if (spec.maxInputs !== null && inputCount > spec.maxInputs) {
    return `rule '${ruleName}' admits at most ${spec.maxInputs} inputs; got ${inputCount}`
  }
  return null
}

// ─── Hash verification ───────────────────────────────────────────────────

function fullDict(p: InferenceProof): Record<string, JCSValue> {
  return {
    proof_type: p.proof_type,
    schema_version: p.schema_version,
    proof_id: p.proof_id,
    target_justification_id: p.target_justification_id,
    target_justification_hash: p.target_justification_hash,
    premises: p.premises.map(x => ({
      id: x.id, text: x.text,
      evidence_refs: [...x.evidence_refs],
      kind: x.kind,
    })),
    inferences: p.inferences.map(x => ({
      id: x.id, rule: x.rule,
      input_claim_ids: [...x.input_claim_ids],
      output_claim_id: x.output_claim_id,
      text: x.text,
    })),
    derived_claims: p.derived_claims.map(x => ({
      id: x.id, text: x.text, inferred_by: x.inferred_by,
    })),
    conclusion_claim_id: p.conclusion_claim_id,
    proof_hash: p.proof_hash,
  }
}

export async function computeProofHash(p: InferenceProof): Promise<string> {
  const dict = fullDict(p)
  delete dict.proof_hash
  return sha256Hex(jcsCanonicalize(dict))
}

export async function verifyProofHash(p: InferenceProof): Promise<boolean> {
  return (await computeProofHash(p)) === p.proof_hash
}

// ─── Structural verification ─────────────────────────────────────────────

export interface WeakInferenceFlag {
  inference_id: string
  rule: string
  output_claim_id: string
}

export interface VerifyLogicResult {
  ok: boolean
  errors: string[]
  weak_inferences: WeakInferenceFlag[]
  structure: {
    premise_count: number
    inference_count: number
    derived_claim_count: number
    rules_used: Record<string, number>
    weak_rule_uses: number
  }
}

function detectCycle(
  inferences: InferenceStep[],
  derivedClaims: DerivedClaim[],
): string | null {
  // Build adjacency: from each input claim to each output claim.
  const adj: Record<string, string[]> = {}
  for (const inf of inferences) {
    for (const inId of inf.input_claim_ids) {
      if (!adj[inId]) adj[inId] = []
      adj[inId].push(inf.output_claim_id)
    }
  }

  const WHITE = 0, GRAY = 1, BLACK = 2
  const color: Record<string, number> = {}

  function dfs(node: string, stack: string[]): string | null {
    color[node] = GRAY
    stack.push(node)
    for (const nxt of adj[node] ?? []) {
      const c = color[nxt] ?? WHITE
      if (c === GRAY) {
        if (stack.includes(nxt)) {
          const idx = stack.indexOf(nxt)
          return [...stack.slice(idx), nxt].join(' → ')
        }
        return `${node} → ${nxt}`
      }
      if (c === WHITE) {
        const r = dfs(nxt, stack)
        if (r !== null) return r
      }
    }
    color[node] = BLACK
    stack.pop()
    return null
  }

  const seeds = new Set<string>([
    ...Object.keys(adj),
    ...derivedClaims.map(c => c.id),
  ])
  for (const seed of seeds) {
    if ((color[seed] ?? WHITE) === WHITE) {
      const cycle = dfs(seed, [])
      if (cycle !== null) return cycle
    }
  }
  return null
}

function reachableFromPremises(
  conclusionId: string,
  premiseIds: Set<string>,
  inferences: InferenceStep[],
): boolean {
  const adj: Record<string, string[]> = {}
  for (const inf of inferences) {
    for (const inId of inf.input_claim_ids) {
      if (!adj[inId]) adj[inId] = []
      adj[inId].push(inf.output_claim_id)
    }
  }
  const visited = new Set<string>()
  const stack: string[] = [...premiseIds]
  while (stack.length > 0) {
    const node = stack.pop()!
    if (visited.has(node)) continue
    visited.add(node)
    if (node === conclusionId) return true
    for (const nxt of adj[node] ?? []) stack.push(nxt)
  }
  return false
}

export function verifyStructural(p: InferenceProof): VerifyLogicResult {
  const errors: string[] = []
  const weak: WeakInferenceFlag[] = []
  const rulesUsed: Record<string, number> = {}

  const premiseById = new Map(p.premises.map(x => [x.id, x]))
  const derivedById = new Map(p.derived_claims.map(x => [x.id, x]))
  const inferenceById = new Map(p.inferences.map(x => [x.id, x]))
  const allClaimIds = new Set([...premiseById.keys(), ...derivedById.keys()])

  // Per-inference checks: vocab, arity, refs, output roundtrip.
  for (const inf of p.inferences) {
    if (!ALLOWED_RULES.has(inf.rule)) {
      errors.push(`inference '${inf.id}': rule '${inf.rule}' not in allowed vocabulary.`)
      continue
    }
    rulesUsed[inf.rule] = (rulesUsed[inf.rule] ?? 0) + 1
    const arityErr = checkArity(inf.rule, inf.input_claim_ids.length)
    if (arityErr !== null) errors.push(`inference '${inf.id}': ${arityErr}.`)
    for (const inId of inf.input_claim_ids) {
      if (!allClaimIds.has(inId)) {
        errors.push(`inference '${inf.id}': input_claim_id '${inId}' does not exist as premise or derived claim.`)
      }
    }
    const outputClaim = derivedById.get(inf.output_claim_id)
    if (!outputClaim) {
      errors.push(`inference '${inf.id}': output_claim_id '${inf.output_claim_id}' not declared in derived_claims.`)
    } else if (outputClaim.inferred_by !== inf.id) {
      errors.push(
        `inference '${inf.id}': output claim '${inf.output_claim_id}' has inferred_by='${outputClaim.inferred_by}', expected '${inf.id}'.`
      )
    }
    if (WEAK_RULES.has(inf.rule)) {
      weak.push({ inference_id: inf.id, rule: inf.rule, output_claim_id: inf.output_claim_id })
    }
  }

  // Orphan derived claims: inferred_by points to unknown inference.
  for (const claim of p.derived_claims) {
    if (!inferenceById.has(claim.inferred_by)) {
      errors.push(`derived claim '${claim.id}': inferred_by '${claim.inferred_by}' references unknown inference.`)
    }
  }

  // Cycle check.
  const cycle = detectCycle(p.inferences, p.derived_claims)
  if (cycle !== null) errors.push(`cycle detected in DAG: ${cycle}.`)

  // Conclusion exists.
  if (!allClaimIds.has(p.conclusion_claim_id)) {
    errors.push(`conclusion_claim_id '${p.conclusion_claim_id}' is not declared as premise or derived claim.`)
  }

  // Reachability.
  if (errors.length === 0 && !premiseById.has(p.conclusion_claim_id)) {
    const reach = reachableFromPremises(
      p.conclusion_claim_id,
      new Set(premiseById.keys()),
      p.inferences,
    )
    if (!reach) {
      errors.push(`conclusion '${p.conclusion_claim_id}' is not reachable from premises via the inference DAG.`)
    }
  }

  return {
    ok: errors.length === 0,
    errors,
    weak_inferences: weak,
    structure: {
      premise_count: p.premises.length,
      inference_count: p.inferences.length,
      derived_claim_count: p.derived_claims.length,
      rules_used: rulesUsed,
      weak_rule_uses: weak.length,
    },
  }
}
