const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? res.statusText)
  }
  return res.json()
}

export interface ArchiveStatus {
  root: string
  manifest_hash: string | null
  schema_version: string | null
  generated_at: string | null
  audit_entries: number
}

export interface ArchiveVerify {
  ok: boolean
  checks: { name: string; ok: boolean; detail: string }[]
}

export interface EvidenceSummary {
  hash: string
  kind: string
  mime_type: string
  size_bytes: number
  ingested_at: string
  ingested_by: string
  source_id: string
}

export interface CaptureCertificate {
  certificate_type: string
  schema_version: string
  evidence_sha256: string
  operator_id: string
  captured_at: string
  device_id: string | null
  location: string | null
  notes: string | null
  public_key_fingerprint: string
  signature: string
  signature_algorithm: string
  certificate_hash: string
}

export interface ProvenanceStepView {
  step_index: number
  kind: string
  actor: string | null
  description: string | null
  timestamp: string | null
  parameters?: Record<string, string>
}

export interface AuditEntrySummary {
  seq: number
  timestamp: string
  actor: string
  entry_hash: string
  parameters: Record<string, string>
}

export interface CoverageManifestSummary {
  sequence: number
  manifest_hash: string
  signed_at: string
  operator_id: string
  public_key_fingerprint: string
  audit_entry_count: number
  audit_chain_head_hash: string
}

export interface InferenceProofReference {
  proof_id: string
  proof_hash: string
  target_justification_id: string
  target_justification_hash: string
  conclusion_claim_id: string
  matched_premise_id: string
  inference_count: number
  weak_inference_count: number
}

export interface EvidenceDetail {
  evidence: {
    hash: string; kind: string; mime_type: string; size_bytes: number
    content_uri: string; ingested_at: string; ingested_by: string
    source_id: string; notes: string | null; status: string
  }
  source: { id: string; name: string; kind: string; authority_level: string; jurisdiction: string | null; license: string | null }
  provenance: { evidence_hash: string; gaps: string[]; steps: ProvenanceStepView[] }
  capture_certificate: CaptureCertificate | null
  audit_entry: AuditEntrySummary | null
  coverage_manifests: CoverageManifestSummary[]
  inference_proofs_referencing: InferenceProofReference[]
  derived_assessments: { method: string; status: string; assessed_at: string; assessed_by: string }[]
}

export interface AuditLogPage {
  total: number
  entries: Record<string, unknown>[]
}

export interface AttestationSummary {
  id: string
  artifact_kind: string
  signer_id: string
  signed_at: string
  attestation_hash: string
}

export interface DerivedSummary {
  id: string
  [key: string]: unknown
}

export interface CaseItem {
  id: string
  description: string | null
  evidence_count: number
  has_timeline: boolean
  timeline_count: number
  conclusion: string | null
  justification_id: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TransparencyManifestSummary {
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

export interface TransparencyStatus {
  manifest_count: number
  head: TransparencyManifestSummary | null
  public_key_available: boolean
  transparency_dir: string
  latest_filename: string
}

// ─── Key declaration (ADR-0043: trust footprint) ──────────────────────────

export interface ExternalReference {
  kind: string
  uri: string
  note?: string
}

export interface KeyDeclarationOperator {
  operator_id: string
  public_key_fingerprint: string
  first_published_at?: string
  external_references: ExternalReference[]
}

export interface KeyDeclarationWitness {
  witness_operator_id: string
  public_key_fingerprint: string
  external_references: ExternalReference[]
}

export interface KeyDeclaration {
  declaration_type: string
  schema_version: string
  operator: KeyDeclarationOperator
  witnesses: KeyDeclarationWitness[]
}

export interface KeyDeclarationConsistency {
  declaration_present: boolean
  operator_fingerprint_declared: string | null
  operator_fingerprint_actual: string | null
  operator_matches: boolean
  witnesses_declared: number
  witnesses_in_archive: number
  declared_witnesses_without_pem: {
    witness_operator_id: string
    public_key_fingerprint: string
  }[]
  extra_witness_pems_not_declared: string[]
  ok: boolean
}

export interface KeyDeclarationResponse {
  declaration: KeyDeclaration | null
  consistency: KeyDeclarationConsistency
}

// ─── OTS / Bitcoin anchor status ──────────────────────────────────────────

export interface BitcoinAnchor {
  height: number
  expected_merkle_root_le_hex: string
}

export interface NotarizationStatus {
  ots_filename: string
  leaf_sha256: string
  bitcoin_anchors: BitcoinAnchor[]
  pending_count: number
  pending_calendars: string[]
}

export const api = {
  archiveStatus: () => get<ArchiveStatus>('/archive/status'),
  archiveVerify: () => get<ArchiveVerify>('/archive/verify'),
  listEvidence: () => get<EvidenceSummary[]>('/evidence'),
  getEvidence: (hash: string) => get<EvidenceDetail>(`/evidence/${hash}`),
  auditLog: (offset = 0, limit = 100) => get<AuditLogPage>(`/audit-log?offset=${offset}&limit=${limit}`),
  listAttestations: () => get<AttestationSummary[]>('/attestations'),
  getAttestation: (id: string) => get<Record<string, unknown>>(`/attestations/${id}`),
  getInferenceProof:     (proofId: string) => get<Record<string, unknown>>(`/inference-proofs/${proofId}`),
  listInferenceProofs:   () => get<Record<string, unknown>[]>('/inference-proofs'),
  transparencyStatus:    () => get<TransparencyStatus>('/transparency/status'),
  transparencyManifests: () => get<TransparencyManifestSummary[]>('/transparency/manifests'),
  transparencyManifest:  (seq: number) => get<Record<string, unknown>>(`/transparency/manifests/${seq}`),
  transparencyPublicKey: async (): Promise<string | null> => {
    const res = await fetch(`${BASE}/transparency/public-key`)
    if (res.status === 404) return null
    if (!res.ok) throw new Error(res.statusText)
    return res.text()
  },
  transparencyKeyDeclaration: () =>
    get<KeyDeclarationResponse>('/transparency/key-declaration'),
  transparencyNotarization: async (seq: number): Promise<NotarizationStatus | null> => {
    const res = await fetch(`${BASE}/transparency/notarization/${seq}`)
    if (!res.ok) throw new Error(res.statusText)
    const data = (await res.json()) as NotarizationStatus | null
    return data
  },
  listCases: () => get<CaseItem[]>('/cases'),
  getCase: (id: string) => get<Record<string, unknown>>(`/cases/${id}`),
  listWorkspaces: () => get<DerivedSummary[]>('/workspaces'),
  listTimelines: () => get<DerivedSummary[]>('/timelines'),
  listSnapshots: () => get<DerivedSummary[]>('/snapshots'),
  listJustifications: () => get<DerivedSummary[]>('/justifications'),
}
