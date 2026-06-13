/**
 * Client-side verification del audit log (ADR-0019).
 *
 * Mirror exacto de `src/aip/audit/log.py::_base_canonical_dict` y
 * `compute_entry_hash`. El audit log es la fundación del proyecto entero —
 * todo lo demás (manifests, witnesses, notarization, proofs) pinnea o se
 * ata al estado del audit log. Tener verificación client-side cierra el
 * thesis: "every layer is independently verifiable client-side, including
 * the foundation".
 *
 * Checks:
 *   1. Per-entry: SHA256(JCS(canonical_fields)) == declared entry_hash
 *   2. Linkage: entry[N].prev_hash == entry[N-1].entry_hash
 *   3. Bootstrap: entry[0].prev_hash == "0" * 64
 *   4. Sequence: entry[N].seq == N
 *
 * No verifica:
 *   - Semántica del action (e.g., que un INGEST_EVIDENCE tenga size_bytes)
 *   - Que el target URI sea well-formed
 */

import { jcsCanonicalize, sha256Hex, type JCSValue } from './jcs'

export interface AuditEntry {
  seq: number
  prev_hash: string
  timestamp: string         // ISO-8601 UTC "YYYY-MM-DDTHH:MM:SSZ"
  actor: string
  action: string
  target: string
  parameters: Record<string, string>
  result: string
  schema_version: string
  entry_hash: string
}

export const ZERO_HASH = '0'.repeat(64)

/**
 * Diccionario canónico SIN entry_hash. Mirror exacto de Python.
 * Orden: seq, prev_hash, timestamp, actor, action, target, parameters, result, schema_version.
 * (JCS reordenará por code-point UTF-16-BE — el orden en este dict es indiferente.)
 */
function baseCanonicalDict(entry: AuditEntry): Record<string, JCSValue> {
  return {
    seq: entry.seq,
    prev_hash: entry.prev_hash,
    timestamp: entry.timestamp,
    actor: entry.actor,
    action: entry.action,
    target: entry.target,
    parameters: { ...entry.parameters },
    result: entry.result,
    schema_version: entry.schema_version,
  }
}

export async function computeEntryHash(entry: AuditEntry): Promise<string> {
  return sha256Hex(jcsCanonicalize(baseCanonicalDict(entry)))
}

export async function verifyEntryHash(entry: AuditEntry): Promise<boolean> {
  return (await computeEntryHash(entry)) === entry.entry_hash
}

// ─── Chain-wide verification ────────────────────────────────────────────

export interface ChainVerifyReport {
  ok: boolean
  total: number
  brokenHashEntries: number[]        // seq numbers with hash mismatch
  brokenLinkages: { atSeq: number; reason: string }[]
  perEntryHashOk: Map<number, boolean>
}

export async function verifyEntireChain(entries: AuditEntry[]): Promise<ChainVerifyReport> {
  const report: ChainVerifyReport = {
    ok: true,
    total: entries.length,
    brokenHashEntries: [],
    brokenLinkages: [],
    perEntryHashOk: new Map(),
  }
  if (entries.length === 0) return report

  // Sort by seq just in case (defensive — backend SHOULD return ordered).
  const sorted = [...entries].sort((a, b) => a.seq - b.seq)

  // Per-entry hash check + linkage + sequence monotonicity.
  for (let i = 0; i < sorted.length; i++) {
    const e = sorted[i]

    // Sequence monotonicity.
    if (e.seq !== i + (sorted[0].seq)) {
      report.brokenLinkages.push({
        atSeq: e.seq,
        reason: `sequence break: expected ${i + sorted[0].seq}, got ${e.seq}`,
      })
    }

    // Per-entry hash.
    const ok = await verifyEntryHash(e)
    report.perEntryHashOk.set(e.seq, ok)
    if (!ok) report.brokenHashEntries.push(e.seq)

    // Linkage: prev_hash must match previous entry's entry_hash, or ZERO_HASH for seq=0.
    if (i === 0 && sorted[0].seq === 0) {
      if (e.prev_hash !== ZERO_HASH) {
        report.brokenLinkages.push({
          atSeq: e.seq,
          reason: `bootstrap entry (seq=0) must have prev_hash = 0*64`,
        })
      }
    } else if (i > 0) {
      const prev = sorted[i - 1]
      if (e.prev_hash !== prev.entry_hash) {
        report.brokenLinkages.push({
          atSeq: e.seq,
          reason: `prev_hash does not match entry_hash of seq ${prev.seq}`,
        })
      }
    }
  }

  report.ok = report.brokenHashEntries.length === 0 && report.brokenLinkages.length === 0
  return report
}
