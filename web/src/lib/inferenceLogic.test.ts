/**
 * Tests for client-side inference-proof verification (mirror of
 * `aip.justification.logic.verifier`). These tests are the canonical
 * safety net for the verifier: a regression here would silently break
 * both the React portal and the inlined verifier embedded in the
 * standalone HTML report (`src/aip/report/builder.py`).
 *
 * Coverage is structured around the eight checks in the Python mirror
 * plus a happy path. The fixture is intentionally tiny so failures point
 * at the exact rule being exercised; broader scenarios belong in the
 * integration tests on the Python side.
 */

import { describe, it, expect } from 'vitest'
import {
  ALLOWED_RULES,
  WEAK_RULES,
  computeProofHash,
  getRule,
  isWeakRule,
  verifyProofHash,
  verifyStructural,
  type InferenceProof,
} from './inferenceLogic'

// ─── fixture helpers ──────────────────────────────────────────────────

function makeValidProof(): InferenceProof {
  // Minimal but legal: abduction from one premise + one premise to a single
  // derived claim. Matches the integration-test fixture
  // `tmp/integration-test/archive/inference-proofs/uap-001-anomaly-v1.json`.
  return {
    proof_type: 'aip.justification.inference-proof.v1',
    schema_version: '1',
    proof_id: 'uap-001-anomaly-v1',
    target_justification_id: 'uap-001-investigation',
    target_justification_hash: 'f'.repeat(64),
    premises: [
      {
        id: 'P1',
        text: 'Anomaly observation in field document UAP-001',
        evidence_refs: ['8033a0c7427531fc1f23b0dfc36250de052140a2f6ccfdf6654ee1a88ae5d5d7'],
        kind: 'observation',
      },
      {
        id: 'P2',
        text: 'Industrial zone is restricted airspace per local FAA equivalent',
        evidence_refs: [],
        kind: 'domain_axiom',
      },
    ],
    inferences: [
      {
        id: 'I1',
        rule: 'abduction_to_best_explanation',
        input_claim_ids: ['P1', 'P2'],
        output_claim_id: 'C1',
        text: 'Most plausible: object was unauthorized aerial vehicle',
      },
    ],
    derived_claims: [
      { id: 'C1', inferred_by: 'I1', text: 'Object was unauthorized UAV' },
    ],
    conclusion_claim_id: 'C1',
    // Hash is meaningful only for the happy-path hash test; we recompute
    // it on the fly there so the fixture stays editable without breaking
    // every structural test.
    proof_hash: '0'.repeat(64),
  }
}

// ─── vocabulary ───────────────────────────────────────────────────────

describe('rule vocabulary', () => {
  it('exposes exactly the five v1 rules', () => {
    expect(new Set(ALLOWED_RULES)).toEqual(
      new Set([
        'modus_ponens',
        'conjunction_intro',
        'inference_to_specific_instance',
        'elimination_by_contradiction',
        'abduction_to_best_explanation',
      ]),
    )
  })

  it('flags abduction as the only weak rule', () => {
    expect(new Set(WEAK_RULES)).toEqual(new Set(['abduction_to_best_explanation']))
    expect(isWeakRule('abduction_to_best_explanation')).toBe(true)
    expect(isWeakRule('modus_ponens')).toBe(false)
  })

  it('returns undefined for unknown rule lookups', () => {
    expect(getRule('wishful_thinking')).toBeUndefined()
  })

  it('matches Python rule arity for each rule', () => {
    // Pin every (min, max) tuple. If Python changes one of these without
    // updating the TS, the test fails — protects the JS verifier's
    // arity guard from drifting silently.
    expect(getRule('modus_ponens')).toMatchObject({ minInputs: 2, maxInputs: 2 })
    expect(getRule('conjunction_intro')).toMatchObject({ minInputs: 2, maxInputs: null })
    expect(getRule('inference_to_specific_instance')).toMatchObject({ minInputs: 2, maxInputs: 2 })
    expect(getRule('elimination_by_contradiction')).toMatchObject({ minInputs: 2, maxInputs: 2 })
    expect(getRule('abduction_to_best_explanation')).toMatchObject({ minInputs: 1, maxInputs: null })
  })
})

// ─── proof_hash recompute ─────────────────────────────────────────────

describe('verifyProofHash', () => {
  it('accepts a proof whose declared proof_hash matches the recomputed JCS+SHA256', async () => {
    const p = makeValidProof()
    p.proof_hash = await computeProofHash(p)
    expect(await verifyProofHash(p)).toBe(true)
  })

  it('rejects a proof whose declared hash is tampered', async () => {
    const p = makeValidProof()
    p.proof_hash = 'a'.repeat(64)
    expect(await verifyProofHash(p)).toBe(false)
  })

  it('rejects when any content field is mutated', async () => {
    // Even a one-character change in a premise text invalidates the hash.
    const p = makeValidProof()
    p.proof_hash = await computeProofHash(p)
    p.premises[0].text = p.premises[0].text + ' (edited)'
    expect(await verifyProofHash(p)).toBe(false)
  })
})

// ─── structural happy path ───────────────────────────────────────────

describe('verifyStructural — happy path', () => {
  it('accepts a legal abduction proof and flags it as weak', () => {
    const r = verifyStructural(makeValidProof())
    expect(r.ok).toBe(true)
    expect(r.errors).toEqual([])
    expect(r.weak_inferences).toEqual([
      { inference_id: 'I1', rule: 'abduction_to_best_explanation', output_claim_id: 'C1' },
    ])
    expect(r.structure).toMatchObject({
      premise_count: 2,
      inference_count: 1,
      derived_claim_count: 1,
      rules_used: { abduction_to_best_explanation: 1 },
      weak_rule_uses: 1,
    })
  })
})

// ─── structural tamper cases ─────────────────────────────────────────

describe('verifyStructural — tamper detection', () => {
  it('rejects rule outside the closed vocabulary', () => {
    const p = makeValidProof()
    p.inferences[0].rule = 'wishful_thinking'
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(r.errors.some(e => e.includes('not in allowed vocabulary'))).toBe(true)
  })

  it('rejects inference with too few inputs for its rule', () => {
    const p = makeValidProof()
    // modus_ponens requires exactly 2; give it 1 to trigger the arity guard.
    p.inferences[0].rule = 'modus_ponens'
    p.inferences[0].input_claim_ids = ['P1']
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(
      r.errors.some(e => e.includes("requires at least 2 inputs; got 1")),
    ).toBe(true)
  })

  it('rejects inference with too many inputs for a bounded rule', () => {
    const p = makeValidProof()
    // modus_ponens admits at most 2 inputs; supply 3.
    p.inferences[0].rule = 'modus_ponens'
    p.inferences[0].input_claim_ids = ['P1', 'P2', 'P1']
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(r.errors.some(e => e.includes('admits at most 2'))).toBe(true)
  })

  it('rejects input_claim_id that does not exist', () => {
    const p = makeValidProof()
    p.inferences[0].input_claim_ids = ['P_ghost', 'P2']
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(
      r.errors.some(e =>
        e.includes("input_claim_id 'P_ghost' does not exist"),
      ),
    ).toBe(true)
  })

  it('rejects when output_claim_id is missing from derived_claims', () => {
    const p = makeValidProof()
    p.inferences[0].output_claim_id = 'C_missing'
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(
      r.errors.some(e =>
        e.includes("'C_missing' not declared in derived_claims"),
      ),
    ).toBe(true)
  })

  it('rejects when derived claim references an unknown inference', () => {
    const p = makeValidProof()
    p.derived_claims[0].inferred_by = 'I_phantom'
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(
      r.errors.some(e =>
        e.includes("'I_phantom' references unknown inference"),
      ),
    ).toBe(true)
  })

  it('rejects DAG with a cycle', () => {
    // Add a second claim+inference that produces a cycle:
    // C1 (output of I1) → C2 (output of I2 consuming C1) → back into I1 via C2 input.
    const p = makeValidProof()
    p.derived_claims.push({ id: 'C2', inferred_by: 'I2', text: 'derived loop' })
    p.inferences.push({
      id: 'I2',
      rule: 'abduction_to_best_explanation',
      input_claim_ids: ['C1'],
      output_claim_id: 'C2',
      text: 'derived loop step',
    })
    // Now make C2 feed back into I1.
    p.inferences[0].input_claim_ids = ['C2']
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(r.errors.some(e => e.startsWith('cycle detected in DAG:'))).toBe(true)
  })

  it('rejects when the declared conclusion id is unknown', () => {
    const p = makeValidProof()
    p.conclusion_claim_id = 'C_does_not_exist'
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    expect(
      r.errors.some(e =>
        e.includes("'C_does_not_exist' is not declared as premise or derived claim"),
      ),
    ).toBe(true)
  })

  it('rejects when the conclusion exists but is unreachable from premises', () => {
    // Add an orphan derived claim that no inference produces. Declared as
    // conclusion → unreachable from any premise.
    const p = makeValidProof()
    // Add a self-consistent extra inference I2 whose output is C_orphan,
    // but feed I2 from another orphan derived claim that itself has no
    // producer. Result: the DAG is well-formed per rule checks but the
    // path from premises never reaches C_orphan.
    //
    // Simpler shape: declare an orphan that points back to I1 (so the
    // earlier checks all pass) but then route the conclusion through it
    // via a side-DAG that's disconnected from premises.
    p.derived_claims.push({
      id: 'C_orphan',
      inferred_by: 'I_orphan',
      text: 'no producer feeds from premises',
    })
    p.inferences.push({
      id: 'I_orphan',
      rule: 'abduction_to_best_explanation',
      input_claim_ids: ['C_orphan'],  // self-input — no premise reaches here
      output_claim_id: 'C_orphan',
      text: 'self-loop disconnected from premises',
    })
    p.conclusion_claim_id = 'C_orphan'
    const r = verifyStructural(p)
    expect(r.ok).toBe(false)
    // Either reachability or cycle fires first; both are valid signals
    // that the proof is broken.
    expect(
      r.errors.some(
        e =>
          e.includes('not reachable from premises') ||
          e.startsWith('cycle detected in DAG:'),
      ),
    ).toBe(true)
  })
})

// ─── trivial case: conclusion is itself a premise ─────────────────────

describe('verifyStructural — premise-as-conclusion edge case', () => {
  it('accepts a proof whose conclusion id is one of the premises', () => {
    // Legal per the Python verifier — odd but explicitly allowed. The
    // result is a tautology; the structural verifier does not judge
    // semantic value.
    const p = makeValidProof()
    p.conclusion_claim_id = 'P1'
    const r = verifyStructural(p)
    expect(r.ok).toBe(true)
  })
})
