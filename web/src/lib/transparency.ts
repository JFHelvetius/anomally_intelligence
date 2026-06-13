/**
 * Client-side verification of AIP TransparencyManifest (Phase 1B).
 *
 * Mirrors `aip/transparency/signer.py` exactly:
 *   1. Structural: recompute manifest_hash from JCS of all fields except
 *      manifest_hash itself; compare to declared value.
 *   2. Crypto: verify fingerprint(public_key) == declared, then recompute
 *      signing payload (excludes signature + manifest_hash) and ed25519-verify.
 *
 * All verification runs in the browser. The portal does NOT trust the
 * backend that served the manifest — the cryptographic chain is the trust
 * anchor.
 */

// @noble/curves v2.x requires the explicit .js suffix in subpath imports
// (the package's exports map only lists "./ed25519.js", not "./ed25519").
import { ed25519 } from '@noble/curves/ed25519.js'
import { jcsCanonicalize, sha256Hex, type JCSValue } from './jcs'

export interface TransparencyManifest {
  sequence: number
  signed_at: string
  manifest_type: string
  operator_id: string
  public_key_fingerprint: string
  archive_manifest_hash: string
  audit_chain_head_hash: string
  audit_entry_count: number
  evidence_count: number
  attestation_count: number
  workspace_count: number
  timeline_count: number
  snapshot_count: number
  justification_count: number
  previous_manifest_hash: string
  signature: string
  signature_algorithm: string
  manifest_hash: string
  schema_version: string
}

export interface ManifestSummary {
  sequence: number
  manifest_hash: string
  previous_manifest_hash: string
  audit_chain_head_hash: string
  audit_entry_count: number
  evidence_count: number
  attestation_count: number
  signed_at: string
  operator_id: string
  public_key_fingerprint: string
}

export interface WitnessAttestation {
  attestation_type: string
  schema_version: string
  witness_operator_id: string
  witness_public_key_fingerprint: string
  target_manifest_hash: string
  target_manifest_sequence: number
  target_operator_id: string
  witnessed_at: string
  statement: string | null
  signature: string
  signature_algorithm: string
  attestation_hash: string
}

export const ZERO_HASH = '0'.repeat(64)

// ─── Canonical dict builders ─────────────────────────────────────────────

function fullDict(m: TransparencyManifest): Record<string, JCSValue> {
  return {
    sequence: m.sequence,
    signed_at: m.signed_at,
    manifest_type: m.manifest_type,
    operator_id: m.operator_id,
    public_key_fingerprint: m.public_key_fingerprint,
    archive_manifest_hash: m.archive_manifest_hash,
    audit_chain_head_hash: m.audit_chain_head_hash,
    audit_entry_count: m.audit_entry_count,
    evidence_count: m.evidence_count,
    attestation_count: m.attestation_count,
    workspace_count: m.workspace_count,
    timeline_count: m.timeline_count,
    snapshot_count: m.snapshot_count,
    justification_count: m.justification_count,
    previous_manifest_hash: m.previous_manifest_hash,
    signature: m.signature,
    signature_algorithm: m.signature_algorithm,
    manifest_hash: m.manifest_hash,
    schema_version: m.schema_version,
  }
}

function signingDict(m: TransparencyManifest): Record<string, JCSValue> {
  // Mirrors `_build_signing_payload` in signer.py: excludes signature,
  // manifest_hash, but INCLUDES signature_algorithm and schema_version.
  return {
    sequence: m.sequence,
    signed_at: m.signed_at,
    manifest_type: m.manifest_type,
    operator_id: m.operator_id,
    public_key_fingerprint: m.public_key_fingerprint,
    archive_manifest_hash: m.archive_manifest_hash,
    audit_chain_head_hash: m.audit_chain_head_hash,
    audit_entry_count: m.audit_entry_count,
    evidence_count: m.evidence_count,
    attestation_count: m.attestation_count,
    workspace_count: m.workspace_count,
    timeline_count: m.timeline_count,
    snapshot_count: m.snapshot_count,
    justification_count: m.justification_count,
    previous_manifest_hash: m.previous_manifest_hash,
    signature_algorithm: m.signature_algorithm,
    schema_version: m.schema_version,
  }
}

// ─── Structural verification ─────────────────────────────────────────────

export async function computeManifestHash(m: TransparencyManifest): Promise<string> {
  const dict = fullDict(m)
  delete dict.manifest_hash
  return sha256Hex(jcsCanonicalize(dict))
}

export async function verifyStructural(m: TransparencyManifest): Promise<boolean> {
  const computed = await computeManifestHash(m)
  return computed === m.manifest_hash
}

// ─── PEM → DER → raw ed25519 ────────────────────────────────────────────

export function pemToDer(pem: string): Uint8Array {
  const body = pem
    .replace(/-----BEGIN [^-]+-----/g, '')
    .replace(/-----END [^-]+-----/g, '')
    .replace(/\s+/g, '')
  const binary = atob(body)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i)
  return out
}

/**
 * Extract the 32-byte raw ed25519 public key from an SPKI DER blob.
 * SPKI for ed25519 is exactly 44 bytes; the last 32 are the raw key.
 */
export function rawEd25519FromSpki(der: Uint8Array): Uint8Array {
  if (der.length !== 44) {
    throw new Error(
      `expected 44-byte ed25519 SPKI DER, got ${der.length} bytes`,
    )
  }
  return der.slice(12)
}

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error('odd-length hex string')
  const bytes = new Uint8Array(hex.length / 2)
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16)
  }
  return bytes
}

// ─── Cryptographic verification ─────────────────────────────────────────

export interface CryptoVerifyResult {
  ok: boolean
  fingerprint_match: boolean
  signature_valid: boolean
  computed_fingerprint: string
  reason?: string
}

export async function verifyCrypto(
  m: TransparencyManifest,
  publicKeyPem: string,
): Promise<CryptoVerifyResult> {
  let der: Uint8Array
  try {
    der = pemToDer(publicKeyPem)
  } catch (e) {
    return {
      ok: false,
      fingerprint_match: false,
      signature_valid: false,
      computed_fingerprint: '',
      reason: 'malformed PEM: ' + (e as Error).message,
    }
  }

  const computedFp = await sha256Hex(der)
  const fpMatch = computedFp === m.public_key_fingerprint

  if (!fpMatch) {
    return {
      ok: false,
      fingerprint_match: false,
      signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'public key fingerprint does not match manifest',
    }
  }

  let rawPub: Uint8Array
  try {
    rawPub = rawEd25519FromSpki(der)
  } catch (e) {
    return {
      ok: false,
      fingerprint_match: true,
      signature_valid: false,
      computed_fingerprint: computedFp,
      reason: (e as Error).message,
    }
  }

  let sigBytes: Uint8Array
  try {
    sigBytes = hexToBytes(m.signature)
  } catch (e) {
    return {
      ok: false,
      fingerprint_match: true,
      signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'malformed signature hex: ' + (e as Error).message,
    }
  }

  const msg = jcsCanonicalize(signingDict(m))
  let sigValid = false
  try {
    sigValid = ed25519.verify(sigBytes, msg, rawPub)
  } catch (e) {
    return {
      ok: false,
      fingerprint_match: true,
      signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'ed25519 verify threw: ' + (e as Error).message,
    }
  }

  return {
    ok: sigValid,
    fingerprint_match: true,
    signature_valid: sigValid,
    computed_fingerprint: computedFp,
    reason: sigValid ? undefined : 'ed25519 signature does not verify',
  }
}

// ─── Chain verification ─────────────────────────────────────────────────

export interface ChainVerifyResult {
  ok: boolean
  manifests_checked: number
  failures: { sequence: number; reason: string }[]
}

export async function verifyChain(
  manifests: TransparencyManifest[],
  publicKeyPem: string | null,
): Promise<ChainVerifyResult> {
  const failures: { sequence: number; reason: string }[] = []

  if (manifests.length === 0) {
    return { ok: true, manifests_checked: 0, failures: [] }
  }

  for (let i = 0; i < manifests.length; i++) {
    const m = manifests[i]
    if (m.sequence !== i) {
      failures.push({
        sequence: m.sequence,
        reason: `sequence mismatch at index ${i}: expected ${i}, got ${m.sequence}`,
      })
      continue
    }
    if (!(await verifyStructural(m))) {
      failures.push({
        sequence: m.sequence,
        reason: 'structural verification failed (manifest_hash mismatch)',
      })
      continue
    }
    const expectedPrev = i === 0 ? ZERO_HASH : manifests[i - 1].manifest_hash
    if (m.previous_manifest_hash !== expectedPrev) {
      failures.push({
        sequence: m.sequence,
        reason: `chain break: previous_manifest_hash != manifest_hash of seq ${i - 1}`,
      })
      continue
    }
    if (publicKeyPem !== null) {
      const cr = await verifyCrypto(m, publicKeyPem)
      if (!cr.ok) {
        failures.push({
          sequence: m.sequence,
          reason: cr.reason ?? 'crypto verification failed',
        })
      }
    }
  }
  return {
    ok: failures.length === 0,
    manifests_checked: manifests.length,
    failures,
  }
}

// ─── Search ─────────────────────────────────────────────────────────────

export interface SearchHit {
  manifest: ManifestSummary
  matched_field:
    | 'manifest_hash'
    | 'previous_manifest_hash'
    | 'audit_chain_head_hash'
    | 'public_key_fingerprint'
}

// ─── Witness attestation verification (Door #3) ─────────────────────────

function witnessFullDict(att: WitnessAttestation): Record<string, JCSValue> {
  return {
    attestation_type: att.attestation_type,
    schema_version: att.schema_version,
    witness_operator_id: att.witness_operator_id,
    witness_public_key_fingerprint: att.witness_public_key_fingerprint,
    target_manifest_hash: att.target_manifest_hash,
    target_manifest_sequence: att.target_manifest_sequence,
    target_operator_id: att.target_operator_id,
    witnessed_at: att.witnessed_at,
    statement: att.statement,
    signature: att.signature,
    signature_algorithm: att.signature_algorithm,
    attestation_hash: att.attestation_hash,
  }
}

function witnessSigningDict(att: WitnessAttestation): Record<string, JCSValue> {
  return {
    attestation_type: att.attestation_type,
    schema_version: att.schema_version,
    witness_operator_id: att.witness_operator_id,
    witness_public_key_fingerprint: att.witness_public_key_fingerprint,
    target_manifest_hash: att.target_manifest_hash,
    target_manifest_sequence: att.target_manifest_sequence,
    target_operator_id: att.target_operator_id,
    witnessed_at: att.witnessed_at,
    statement: att.statement,
    signature_algorithm: att.signature_algorithm,
  }
}

export async function computeWitnessHash(att: WitnessAttestation): Promise<string> {
  const dict = witnessFullDict(att)
  delete dict.attestation_hash
  return sha256Hex(jcsCanonicalize(dict))
}

export async function verifyWitnessStructural(att: WitnessAttestation): Promise<boolean> {
  return (await computeWitnessHash(att)) === att.attestation_hash
}

export async function verifyWitnessTargetMatch(
  att: WitnessAttestation,
  manifest: TransparencyManifest,
): Promise<boolean> {
  return (
    att.target_manifest_hash === manifest.manifest_hash &&
    att.target_manifest_sequence === manifest.sequence &&
    att.target_operator_id === manifest.operator_id
  )
}

export async function verifyWitnessCrypto(
  att: WitnessAttestation,
  witnessPublicKeyPem: string,
): Promise<CryptoVerifyResult> {
  let der: Uint8Array
  try {
    der = pemToDer(witnessPublicKeyPem)
  } catch (e) {
    return {
      ok: false, fingerprint_match: false, signature_valid: false,
      computed_fingerprint: '', reason: 'malformed PEM: ' + (e as Error).message,
    }
  }
  const computedFp = await sha256Hex(der)
  if (computedFp !== att.witness_public_key_fingerprint) {
    return {
      ok: false, fingerprint_match: false, signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'public key fingerprint does not match witness attestation',
    }
  }
  let rawPub: Uint8Array
  try { rawPub = rawEd25519FromSpki(der) } catch (e) {
    return {
      ok: false, fingerprint_match: true, signature_valid: false,
      computed_fingerprint: computedFp, reason: (e as Error).message,
    }
  }
  let sigBytes: Uint8Array
  try { sigBytes = hexToBytes(att.signature) } catch (e) {
    return {
      ok: false, fingerprint_match: true, signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'malformed signature hex: ' + (e as Error).message,
    }
  }
  const msg = jcsCanonicalize(witnessSigningDict(att))
  let valid = false
  try { valid = ed25519.verify(sigBytes, msg, rawPub) } catch (e) {
    return {
      ok: false, fingerprint_match: true, signature_valid: false,
      computed_fingerprint: computedFp,
      reason: 'ed25519 verify threw: ' + (e as Error).message,
    }
  }
  return {
    ok: valid, fingerprint_match: true, signature_valid: valid,
    computed_fingerprint: computedFp,
    reason: valid ? undefined : 'ed25519 signature does not verify',
  }
}

// ─── Search ─────────────────────────────────────────────────────────────

export function searchByHash(
  manifests: ManifestSummary[],
  query: string,
): SearchHit[] {
  const q = query.trim().toLowerCase()
  if (q.length < 4) return []
  const hits: SearchHit[] = []
  for (const m of manifests) {
    if (m.manifest_hash.startsWith(q)) {
      hits.push({ manifest: m, matched_field: 'manifest_hash' })
    } else if (m.previous_manifest_hash.startsWith(q)) {
      hits.push({ manifest: m, matched_field: 'previous_manifest_hash' })
    } else if (m.audit_chain_head_hash.startsWith(q)) {
      hits.push({ manifest: m, matched_field: 'audit_chain_head_hash' })
    } else if (m.public_key_fingerprint.startsWith(q)) {
      hits.push({ manifest: m, matched_field: 'public_key_fingerprint' })
    }
  }
  return hits
}
