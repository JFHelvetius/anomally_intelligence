/**
 * Abstracción de fuente de transparency log (Phase 1C).
 *
 * Dos implementaciones:
 *
 *   - BackendSource — usa `/api/transparency/*` del backend del operador.
 *     Útil cuando estás en la red del operador y confías en el transporte
 *     (la verificación criptográfica sigue siendo client-side).
 *
 *   - StaticBundleSource — descarga `index.json`, `public-key.pem` y
 *     `manifest-NNNNNN.json` desde una URL base estática (GitHub Pages,
 *     S3, IPFS, http.server local). NO requiere backend del operador.
 *     Esta es la razón de ser de Phase 1C: cualquiera puede verificar.
 *
 * El portal selecciona la implementación según la config persistente del
 * usuario (URL params → localStorage → default = backend).
 */

import type {
  ManifestSummary, TransparencyManifest, WitnessAttestation,
} from './transparency'

export interface BitcoinAnchor {
  height: number
  expected_merkle_root_le_hex: string
}

export interface NotarizationSummary {
  ots_filename: string
  leaf_sha256: string
  bitcoin_anchors: BitcoinAnchor[]
  pending_count: number
  pending_calendars: string[]
}

export interface TransparencyStatus {
  manifest_count: number
  head: ManifestSummary | null
  public_key_available: boolean
}

export interface TransparencySource {
  readonly kind: 'backend' | 'static'
  readonly label: string
  readonly baseUrl: string
  status(): Promise<TransparencyStatus>
  manifestList(): Promise<ManifestSummary[]>
  manifest(seq: number): Promise<TransparencyManifest>
  publicKey(): Promise<string | null>
  witnessesForManifest(seq: number): Promise<WitnessAttestation[]>
  notarizationForManifest(seq: number): Promise<NotarizationSummary | null>
}

// ─── BackendSource — operator's AIP HTTP API ────────────────────────────

export class BackendSource implements TransparencySource {
  readonly kind = 'backend'
  constructor(public readonly baseUrl: string = '/api/transparency') {}
  get label(): string { return `Backend del operador · ${this.baseUrl}` }

  async status(): Promise<TransparencyStatus> {
    const res = await fetch(`${this.baseUrl}/status`)
    if (!res.ok) throw new Error(`status ${res.status}: ${res.statusText}`)
    const data = await res.json()
    return {
      manifest_count:        data.manifest_count,
      head:                  data.head,
      public_key_available:  data.public_key_available,
    }
  }

  async manifestList(): Promise<ManifestSummary[]> {
    const res = await fetch(`${this.baseUrl}/manifests`)
    if (!res.ok) throw new Error(`manifests ${res.status}: ${res.statusText}`)
    return res.json()
  }

  async manifest(seq: number): Promise<TransparencyManifest> {
    const res = await fetch(`${this.baseUrl}/manifests/${seq}`)
    if (!res.ok) throw new Error(`manifest ${seq} ${res.status}: ${res.statusText}`)
    return res.json()
  }

  async publicKey(): Promise<string | null> {
    const res = await fetch(`${this.baseUrl}/public-key`)
    if (res.status === 404) return null
    if (!res.ok) throw new Error(`public-key ${res.status}: ${res.statusText}`)
    return res.text()
  }

  async witnessesForManifest(seq: number): Promise<WitnessAttestation[]> {
    const res = await fetch(`${this.baseUrl}/witnesses/${seq}`)
    if (!res.ok) return []
    return res.json()
  }

  async notarizationForManifest(seq: number): Promise<NotarizationSummary | null> {
    const res = await fetch(`${this.baseUrl}/notarization/${seq}`)
    if (!res.ok) return null
    const data = await res.json()
    return data as NotarizationSummary | null
  }
}

// ─── StaticBundleSource — pure static files, no backend ─────────────────

interface BundleWitnessSummary {
  attestation_hash: string
  filename: string
  witness_operator_id: string
  witness_public_key_fingerprint: string
  witnessed_at: string
  statement: string | null
}

interface BundleManifestEntry extends ManifestSummary {
  filename: string
  witnesses: BundleWitnessSummary[]
  witness_count: number
  notarization: NotarizationSummary | null
}

interface BundleIndex {
  $type: string
  schema_version: string
  exported_at: string
  operator: { id: string; public_key_fingerprint: string; public_key_file: string }
  manifests: BundleManifestEntry[]
  head: { sequence: number; manifest_hash: string; signed_at: string; audit_chain_head_hash: string }
  total_witnesses?: number
  manifests_with_witnesses?: number
}

export class StaticBundleSource implements TransparencySource {
  readonly kind = 'static'
  private indexCache: Promise<BundleIndex> | null = null

  constructor(public readonly baseUrl: string) {
    // Normalize: strip trailing slash
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  get label(): string { return `Bundle estático · ${this.baseUrl}` }

  private fetchIndex(): Promise<BundleIndex> {
    if (this.indexCache) return this.indexCache
    this.indexCache = (async () => {
      const res = await fetch(`${this.baseUrl}/index.json`)
      if (!res.ok) throw new Error(`index.json ${res.status}: ${res.statusText}`)
      const data = await res.json()
      if (data.$type !== 'aip.transparency.bundle.v1') {
        throw new Error(`unsupported bundle type: ${data.$type}`)
      }
      return data as BundleIndex
    })()
    return this.indexCache
  }

  async status(): Promise<TransparencyStatus> {
    const idx = await this.fetchIndex()
    const head = idx.manifests.length > 0
      ? idx.manifests[idx.manifests.length - 1]
      : null
    return {
      manifest_count:       idx.manifests.length,
      head,
      public_key_available: true,
    }
  }

  async manifestList(): Promise<ManifestSummary[]> {
    const idx = await this.fetchIndex()
    return idx.manifests.map(m => ({
      sequence:                m.sequence,
      manifest_hash:           m.manifest_hash,
      previous_manifest_hash:  m.previous_manifest_hash,
      audit_chain_head_hash:   m.audit_chain_head_hash,
      audit_entry_count:       m.audit_entry_count,
      evidence_count:          m.evidence_count,
      attestation_count:       m.attestation_count,
      signed_at:               m.signed_at,
      operator_id:             m.operator_id,
      public_key_fingerprint:  m.public_key_fingerprint,
    }))
  }

  async manifest(seq: number): Promise<TransparencyManifest> {
    const idx = await this.fetchIndex()
    const entry = idx.manifests.find(m => m.sequence === seq)
    if (!entry) throw new Error(`manifest ${seq} not in bundle index`)
    const res = await fetch(`${this.baseUrl}/${entry.filename}`)
    if (!res.ok) throw new Error(`${entry.filename} ${res.status}: ${res.statusText}`)
    return res.json()
  }

  async publicKey(): Promise<string | null> {
    const idx = await this.fetchIndex()
    const res = await fetch(`${this.baseUrl}/${idx.operator.public_key_file}`)
    if (res.status === 404) return null
    if (!res.ok) throw new Error(`public key ${res.status}: ${res.statusText}`)
    return res.text()
  }

  async witnessesForManifest(seq: number): Promise<WitnessAttestation[]> {
    const idx = await this.fetchIndex()
    const entry = idx.manifests.find(m => m.sequence === seq)
    if (!entry || !entry.witnesses?.length) return []
    const out: WitnessAttestation[] = []
    for (const w of entry.witnesses) {
      const res = await fetch(`${this.baseUrl}/${w.filename}`)
      if (!res.ok) continue
      out.push(await res.json())
    }
    return out
  }

  async notarizationForManifest(seq: number): Promise<NotarizationSummary | null> {
    const idx = await this.fetchIndex()
    const entry = idx.manifests.find(m => m.sequence === seq)
    return entry?.notarization ?? null
  }
}

// ─── Config persistence ─────────────────────────────────────────────────

export interface SourceConfig {
  kind: 'backend' | 'static'
  baseUrl: string
}

const STORAGE_KEY = 'aip-portal-source-v1'
const DEFAULT_CONFIG: SourceConfig = { kind: 'backend', baseUrl: '/api/transparency' }

export function loadSourceConfig(): SourceConfig {
  // 1) URL query: ?log=URL forces static bundle mode.
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search)
    const logParam = params.get('log')
    if (logParam) return { kind: 'static', baseUrl: logParam }
  }
  // 2) localStorage
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as SourceConfig
        if (
          (parsed.kind === 'backend' || parsed.kind === 'static') &&
          typeof parsed.baseUrl === 'string'
        ) {
          return parsed
        }
      }
    } catch { /* ignore */ }
  }
  return DEFAULT_CONFIG
}

export function saveSourceConfig(c: SourceConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(c))
  } catch { /* ignore quota / private mode */ }
}

export function makeSource(c: SourceConfig): TransparencySource {
  return c.kind === 'backend'
    ? new BackendSource(c.baseUrl)
    : new StaticBundleSource(c.baseUrl)
}
