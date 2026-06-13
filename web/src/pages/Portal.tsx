import { useEffect, useMemo, useState } from 'react'
import {
  ShieldCheck, ShieldAlert, ShieldOff, Search, Upload, Lock,
  ChevronDown, ChevronUp, Link2, Hash as HashIcon, Clock,
  User, Fingerprint, FileText, Layers, Settings, Server, Globe,
  Check, Users, Bitcoin,
} from 'lucide-react'
import { TrustFootprintCard } from '../components/TrustFootprintCard'
import { useT } from '../i18n'
import {
  Card, CardHeader, Hash, Badge, PageHeader, EmptyState,
  Skeleton, InfoRow, Alert, SectionLabel,
} from '../components/ui'
import {
  verifyChain, verifyStructural, verifyCrypto, searchByHash,
  verifyWitnessStructural, verifyWitnessTargetMatch,
  type TransparencyManifest, type ManifestSummary,
  type ChainVerifyResult, type CryptoVerifyResult,
  type WitnessAttestation,
} from '../lib/transparency'
import {
  loadSourceConfig, saveSourceConfig, makeSource,
  type SourceConfig, type TransparencyStatus, type TransparencySource,
  type NotarizationSummary,
} from '../lib/transparencySource'

// ─── Verdict hero ────────────────────────────────────────────────────────

function VerdictHero({
  loading, result, publicKeyLoaded, sourceLabel,
}: {
  loading: boolean
  result: ChainVerifyResult | null
  publicKeyLoaded: boolean
  sourceLabel: string
}) {
  const t = useT()
  if (loading) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 card-shadow">
        <Skeleton className="h-5 w-64 mb-2" />
        <Skeleton className="h-3 w-96" />
      </div>
    )
  }
  if (!result) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 card-shadow flex items-start gap-4">
        <div className="w-10 h-10 rounded-md bg-slate-100 border border-[var(--border)] flex items-center justify-center">
          <ShieldOff size={18} className="text-slate-400" />
        </div>
        <div>
          <p className="text-[15px] font-semibold text-slate-900">{t('portal.verdict.empty.title')}</p>
          <p className="text-[13px] text-[var(--muted)] mt-0.5">{sourceLabel}</p>
        </div>
      </div>
    )
  }

  const ok = result.ok
  const Icon = ok ? ShieldCheck : ShieldAlert
  const accentBg = ok ? 'bg-emerald-50' : 'bg-amber-50'
  const accentBorder = ok ? 'border-emerald-200' : 'border-amber-200'
  const iconColor = ok ? 'text-emerald-700' : 'text-amber-700'

  const verdictLine = ok
    ? publicKeyLoaded
      ? t('portal.verdict.ok.crypto')
      : t('portal.verdict.ok.structural')
    : t('portal.verdict.fail')

  const n = result.manifests_checked
  const summary = `${n} ${n === 1 ? t('portal.verdict.summary.singular') : t('portal.verdict.summary.plural')}`
  const summaryDetail = publicKeyLoaded
    ? ` ${t('portal.verdict.summary.withKey')}`
    : ` ${t('portal.verdict.summary.noKey')}`

  return (
    <div className={`rounded-lg border ${accentBorder} bg-white card-shadow overflow-hidden`}>
      <div className={`${accentBg} px-5 py-4 border-b ${accentBorder} flex items-start gap-4`}>
        <div className={`w-11 h-11 rounded-md ${accentBg} border ${accentBorder} flex items-center justify-center shrink-0`}>
          <Icon size={20} className={iconColor} />
        </div>
        <div className="flex-1">
          <p className={`text-[15px] font-bold ${iconColor} tracking-tight`}>{verdictLine}</p>
          <p className="text-[13px] text-[var(--muted2)] mt-0.5 leading-relaxed">
            {summary}{summaryDetail}. {t('portal.verdict.summary.tail')}
          </p>
        </div>
      </div>
      {result.failures.length > 0 && (
        <div className="px-5 py-3 bg-amber-50/40 border-t border-amber-100">
          <p className="text-[10px] font-bold text-amber-800 uppercase tracking-wider mb-1.5">{t('portal.verdict.failures')}</p>
          <ul className="space-y-1">
            {result.failures.map((f, i) => (
              <li key={i} className="text-[12px] font-mono text-amber-900">
                · seq {f.sequence}: {f.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ─── Settings drawer ─────────────────────────────────────────────────────

function SettingsPanel({
  config, onSave, onClose,
}: {
  config: SourceConfig
  onSave: (c: SourceConfig) => void
  onClose: () => void
}) {
  const t = useT()
  const [kind, setKind]       = useState<SourceConfig['kind']>(config.kind)
  const [baseUrl, setBaseUrl] = useState(config.baseUrl)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)

  // Preset URLs stay untranslated (they're literal paths). Only the
  // human-facing label uses the dictionary.
  const presetSamples = [
    { label: t('portal.source.backend.label'), kind: 'backend' as const, url: '/api/transparency' },
    { label: t('portal.source.static.label'),  kind: 'static'  as const, url: '/transparency-bundle' },
  ]

  const handleTest = async () => {
    setTesting(true); setTestResult(null)
    try {
      const src = makeSource({ kind, baseUrl })
      const st = await src.status()
      setTestResult({ ok: true, msg: `${st.manifest_count} manifest${st.manifest_count !== 1 ? 's' : ''} · head: ${st.head?.manifest_hash.slice(0, 12) ?? '—'}…` })
    } catch (e) {
      setTestResult({ ok: false, msg: (e as Error).message })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm z-50 flex items-start justify-center pt-24 animate-fade" onClick={onClose}>
      <div className="bg-white rounded-lg border border-[var(--border)] card-shadow-lg w-full max-w-lg mx-4 animate-scale" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
          <div>
            <h2 className="text-[14px] font-bold text-slate-900 tracking-tight">{t('portal.source.title')}</h2>
            <p className="text-[12px] text-[var(--muted)] mt-0.5">{t('portal.source.description')}</p>
          </div>
        </div>

        <div className="p-5 space-y-4">
          {/* Kind selector */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setKind('backend')}
              className={`px-3 py-2.5 rounded-md border text-left transition-colors ${
                kind === 'backend'
                  ? 'bg-violet-50 border-violet-300 ring-2 ring-violet-100'
                  : 'bg-white border-[var(--border)] hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Server size={13} className={kind === 'backend' ? 'text-violet-700' : 'text-[var(--muted)]'} />
                <span className={`text-[12.5px] font-semibold ${kind === 'backend' ? 'text-violet-900' : 'text-slate-900'}`}>{t('portal.source.backend.label')}</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">{t('portal.source.backend.body')}</p>
            </button>
            <button
              onClick={() => setKind('static')}
              className={`px-3 py-2.5 rounded-md border text-left transition-colors ${
                kind === 'static'
                  ? 'bg-violet-50 border-violet-300 ring-2 ring-violet-100'
                  : 'bg-white border-[var(--border)] hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Globe size={13} className={kind === 'static' ? 'text-violet-700' : 'text-[var(--muted)]'} />
                <span className={`text-[12.5px] font-semibold ${kind === 'static' ? 'text-violet-900' : 'text-slate-900'}`}>{t('portal.source.static.label')}</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">{t('portal.source.static.body')}</p>
            </button>
          </div>

          {/* URL input */}
          <div>
            <label className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider">{t('portal.source.baseUrl')}</label>
            <input
              value={baseUrl}
              onChange={e => { setBaseUrl(e.target.value); setTestResult(null) }}
              placeholder={kind === 'backend' ? '/api/transparency' : 'https://operator.github.io/aip-log'}
              className="mt-1.5 w-full bg-white border border-[var(--border)] rounded-md px-3 py-2 text-[13px] text-slate-900 font-mono focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
            />
            <p className="text-[11px] text-[var(--muted)] mt-1.5">
              {kind === 'backend'
                ? t('portal.source.urlHint.backend')
                : t('portal.source.urlHint.static')}
            </p>
          </div>

          {/* Presets */}
          <div>
            <p className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider mb-1.5">{t('portal.source.presets')}</p>
            <div className="space-y-1">
              {presetSamples.map(p => (
                <button
                  key={p.label}
                  onClick={() => { setKind(p.kind); setBaseUrl(p.url); setTestResult(null) }}
                  className="w-full text-left px-3 py-1.5 rounded text-[12px] hover:bg-slate-50 text-slate-700 transition-colors flex items-center justify-between"
                >
                  <span>{p.label}</span>
                  <code className="font-mono text-[10.5px] text-[var(--muted)]">{p.url}</code>
                </button>
              ))}
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div className={`rounded-md border px-3 py-2.5 ${testResult.ok ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
              <p className={`text-[12px] font-mono ${testResult.ok ? 'text-emerald-800' : 'text-red-800'}`}>
                {testResult.ok ? '✓ ' : '✗ '}{testResult.msg}
              </p>
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 border-t border-[var(--border)] flex items-center justify-end gap-2 bg-slate-50/50">
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-3 py-1.5 rounded text-[12px] font-semibold border border-[var(--border)] bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            {testing ? t('portal.source.testing') : t('portal.source.test')}
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-[12px] font-semibold text-[var(--muted2)] hover:text-slate-900 transition-colors"
          >
            {t('portal.source.cancel')}
          </button>
          <button
            onClick={() => { onSave({ kind, baseUrl }); onClose() }}
            className="px-4 py-1.5 rounded text-[12px] font-semibold bg-violet-600 text-white hover:bg-violet-700 transition-colors flex items-center gap-1.5"
          >
            <Check size={12} /> {t('portal.source.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Witnesses sub-section (Door #3) ─────────────────────────────────────

function WitnessRow({
  attestation, structuralOk, targetOk,
}: {
  attestation: WitnessAttestation
  structuralOk: boolean | null
  targetOk: boolean | null
}) {
  const t = useT()
  let badge: React.ReactNode
  if (structuralOk === null) badge = <Badge variant="slate">…</Badge>
  else if (!structuralOk) badge = <Badge variant="red" dot>{t('portal.badge.invalid')}</Badge>
  else if (targetOk === false) badge = <Badge variant="amber" dot>{t('portal.badge.targetFail')}</Badge>
  else badge = <Badge variant="green" dot>{t('portal.badge.structureOk')}</Badge>

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-t border-[var(--border)]">
      <Users size={11} className="text-[var(--muted)] shrink-0" />
      <span className="text-[12px] font-semibold text-slate-900 truncate min-w-[150px]">
        {attestation.witness_operator_id}
      </span>
      <Hash value={attestation.attestation_hash} />
      <span className="text-[11px] font-mono text-[var(--muted)] hidden lg:inline truncate">
        {attestation.witnessed_at.replace('T', ' ').replace('Z', ' UTC')}
      </span>
      <span className="ml-auto shrink-0">{badge}</span>
    </div>
  )
}

// ─── Manifest row ────────────────────────────────────────────────────────

function ManifestRow({
  summary, structuralOk, cryptoResult, onClick, expanded, fullManifest, loadingFull,
  witnesses, witnessStructural, witnessTarget, notarization,
}: {
  summary: ManifestSummary
  structuralOk: boolean | null
  cryptoResult: CryptoVerifyResult | null
  onClick: () => void
  expanded: boolean
  fullManifest: TransparencyManifest | null
  loadingFull: boolean
  witnesses: WitnessAttestation[]
  witnessStructural: Record<string, boolean>
  witnessTarget: Record<string, boolean>
  notarization: NotarizationSummary | null
}) {
  const t = useT()
  let statusBadge: React.ReactNode
  if (structuralOk === null) {
    statusBadge = <Badge variant="slate">{t('portal.badge.checking')}</Badge>
  } else if (!structuralOk) {
    statusBadge = <Badge variant="red" dot>{t('portal.badge.invalid')}</Badge>
  } else if (cryptoResult === null) {
    statusBadge = <Badge variant="blue" dot>{t('portal.badge.structureOk')}</Badge>
  } else if (cryptoResult.ok) {
    statusBadge = <Badge variant="green" dot>{t('portal.badge.signatureOk')}</Badge>
  } else {
    statusBadge = <Badge variant="amber" dot>{t('portal.badge.signatureFail')}</Badge>
  }

  const witnessCount = witnesses.length
  const anchorCount = notarization?.bitcoin_anchors.length ?? 0
  const anchorHeight = notarization?.bitcoin_anchors[0]?.height

  return (
    <div className="border-b border-[var(--border)] last:border-0">
      <button
        onClick={onClick}
        className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors text-left"
      >
        <span className="text-[11px] font-mono font-bold w-8 shrink-0 text-[var(--muted)]">
          #{summary.sequence}
        </span>
        <Hash value={summary.manifest_hash} />
        <span className="text-[11px] font-mono text-[var(--muted)] hidden md:inline">
          {summary.signed_at.replace('T', ' ').replace('Z', ' UTC')}
        </span>
        <span className="ml-auto flex items-center gap-2">
          {anchorCount > 0 && anchorHeight !== undefined && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold border bg-orange-50 text-orange-700 border-orange-200 tracking-wide" title={`Anchored to Bitcoin (${anchorCount} attestation${anchorCount !== 1 ? 's' : ''})`}>
              <Bitcoin size={9} /> btc #{anchorHeight.toLocaleString()}
            </span>
          )}
          {notarization && anchorCount === 0 && notarization.pending_count > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold border bg-amber-50 text-amber-700 border-amber-200 tracking-wide" title="OTS submitted, awaiting Bitcoin confirmation">
              <Bitcoin size={9} /> pending
            </span>
          )}
          {witnessCount > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200 tracking-wide">
              <Users size={9} /> {witnessCount} witness{witnessCount !== 1 ? 'es' : ''}
            </span>
          )}
          {statusBadge}
        </span>
        {expanded
          ? <ChevronUp size={13} className="text-[var(--muted)]" />
          : <ChevronDown size={13} className="text-[var(--muted)]" />}
      </button>

      {expanded && (
        <div className="px-5 pb-5 bg-slate-50/60">
          {loadingFull && <Skeleton className="h-32 w-full mt-3" />}
          {fullManifest && (
            <div className="bg-white border border-[var(--border)] rounded-md mt-3">
              <InfoRow label="Sequence">{fullManifest.sequence}</InfoRow>
              <InfoRow label="Signed at" mono>{fullManifest.signed_at}</InfoRow>
              <InfoRow label="Operator">{fullManifest.operator_id}</InfoRow>
              <InfoRow label="Manifest hash" mono>{fullManifest.manifest_hash}</InfoRow>
              <InfoRow label="Previous hash" mono>{fullManifest.previous_manifest_hash}</InfoRow>
              <InfoRow label="Archive manifest" mono>{fullManifest.archive_manifest_hash}</InfoRow>
              <InfoRow label="Audit head" mono>{fullManifest.audit_chain_head_hash}</InfoRow>
              <InfoRow label="Audit entries">{fullManifest.audit_entry_count}</InfoRow>
              <InfoRow label="Evidence">{fullManifest.evidence_count}</InfoRow>
              <InfoRow label="Attestations">{fullManifest.attestation_count}</InfoRow>
              <InfoRow label="Workspaces">{fullManifest.workspace_count}</InfoRow>
              <InfoRow label="Timelines">{fullManifest.timeline_count}</InfoRow>
              <InfoRow label="Snapshots">{fullManifest.snapshot_count}</InfoRow>
              <InfoRow label="Justifications">{fullManifest.justification_count}</InfoRow>
              <InfoRow label="Public key FP" mono>{fullManifest.public_key_fingerprint}</InfoRow>
              <InfoRow label="Algorithm" mono>{fullManifest.signature_algorithm}</InfoRow>
              <InfoRow label="Signature" mono>
                <span className="break-all text-[10.5px]">{fullManifest.signature}</span>
              </InfoRow>
            </div>
          )}

          {witnessCount > 0 && (
            <div className="bg-white border border-emerald-200 rounded-md mt-3 overflow-hidden">
              <div className="bg-emerald-50 px-4 py-2.5 border-b border-emerald-200 flex items-center gap-2">
                <Users size={12} className="text-emerald-700" />
                <span className="text-[11.5px] font-bold text-emerald-800 tracking-tight">
                  Co-signed by {witnessCount} witness{witnessCount !== 1 ? 'es' : ''}
                </span>
                <span className="text-[11px] text-emerald-900/60 ml-auto">
                  Cross-operator attestations · estructura verificada client-side
                </span>
              </div>
              {witnesses.map(w => (
                <WitnessRow
                  key={w.attestation_hash}
                  attestation={w}
                  structuralOk={witnessStructural[w.attestation_hash] ?? null}
                  targetOk={witnessTarget[w.attestation_hash] ?? null}
                />
              ))}
            </div>
          )}

          {notarization && (
            <div className="bg-white border border-orange-200 rounded-md mt-3 overflow-hidden">
              <div className="bg-orange-50 px-4 py-2.5 border-b border-orange-200 flex items-center gap-2">
                <Bitcoin size={12} className="text-orange-700" />
                <span className="text-[11.5px] font-bold text-orange-800 tracking-tight">
                  {anchorCount > 0
                    ? `Anchored to Bitcoin · ${anchorCount} attestation${anchorCount !== 1 ? 's' : ''}`
                    : 'Notarization pending Bitcoin confirmation'}
                </span>
                <span className="text-[11px] text-orange-900/60 ml-auto">
                  OpenTimestamps · external time anchor
                </span>
              </div>
              <div className="px-4 py-3 space-y-2.5">
                <div className="text-[11px] font-mono text-[var(--muted)]">
                  Leaf SHA-256 (manifest file bytes): <span className="break-all text-slate-700">{notarization.leaf_sha256}</span>
                </div>
                {notarization.bitcoin_anchors.map((a, i) => (
                  <div key={i} className="flex items-start gap-3 p-2.5 rounded bg-orange-50/40 border border-orange-100">
                    <Bitcoin size={11} className="text-orange-700 mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] font-semibold text-slate-900">Bitcoin block #{a.height.toLocaleString()}</div>
                      <div className="text-[10.5px] font-mono text-[var(--muted)] break-all mt-0.5">
                        expected merkle root (LE): {a.expected_merkle_root_le_hex}
                      </div>
                      <div className="text-[10.5px] text-[var(--muted)] mt-1 italic">
                        Verify externally: compare this merkle root with the block at the claimed height.
                      </div>
                    </div>
                  </div>
                ))}
                {notarization.pending_count > 0 && (
                  <div className="text-[11px] text-[var(--muted)] mt-2">
                    <span className="font-semibold text-amber-700">{notarization.pending_count} pending</span>
                    {' '}calendars · Bitcoin batch not yet confirmed
                    {anchorCount > 0 && ' (extra redundancy expected from additional calendars)'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────

export default function Portal() {
  const t = useT()
  const [config, setConfig] = useState<SourceConfig>(() => loadSourceConfig())
  const source: TransparencySource = useMemo(() => makeSource(config), [config])

  const [showSettings, setShowSettings] = useState(false)

  const [status, setStatus]     = useState<TransparencyStatus | null>(null)
  const [summaries, setSummaries] = useState<ManifestSummary[] | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [loading, setLoading]   = useState(true)

  const [publicKeyPem, setPublicKeyPem]   = useState<string | null>(null)
  const [pkSource, setPkSource]           = useState<'source' | 'upload' | null>(null)
  const [pkError, setPkError]             = useState<string | null>(null)

  const [chainResult, setChainResult]     = useState<ChainVerifyResult | null>(null)
  const [verifying, setVerifying]         = useState(false)

  const [structuralByseq, setStructuralByseq] = useState<Record<number, boolean>>({})
  const [cryptoByseq, setCryptoByseq]     = useState<Record<number, CryptoVerifyResult>>({})

  const [expanded, setExpanded]           = useState<Set<number>>(new Set())
  const [fullCache, setFullCache]         = useState<Record<number, TransparencyManifest>>({})
  const [loadingSeq, setLoadingSeq]       = useState<number | null>(null)

  const [witnessesBySeq, setWitnessesBySeq] = useState<Record<number, WitnessAttestation[]>>({})
  const [witnessStructural, setWitnessStructural] = useState<Record<string, boolean>>({})
  const [witnessTarget, setWitnessTarget] = useState<Record<string, boolean>>({})

  const [notarizationBySeq, setNotarizationBySeq] = useState<Record<number, NotarizationSummary>>({})

  const [query, setQuery]                 = useState('')

  // ── Load source data when source changes ──────────────────────────────
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    setStatus(null)
    setSummaries(null)
    setChainResult(null)
    setStructuralByseq({})
    setCryptoByseq({})
    setFullCache({})
    setExpanded(new Set())
    setPublicKeyPem(null)
    setPkSource(null)
    setWitnessesBySeq({})
    setWitnessStructural({})
    setWitnessTarget({})
    setNotarizationBySeq({})

    ;(async () => {
      try {
        const [st, list, pk] = await Promise.all([
          source.status(),
          source.manifestList(),
          source.publicKey().catch(() => null),
        ])
        if (cancelled) return
        setStatus(st)
        setSummaries(list)
        if (pk) { setPublicKeyPem(pk); setPkSource('source') }
      } catch (e) {
        if (!cancelled) setFetchError((e as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [source])

  // ── Verify chain whenever data changes ────────────────────────────────
  useEffect(() => {
    let cancelled = false
    if (!summaries || summaries.length === 0) return
    setVerifying(true)
    ;(async () => {
      const fulls: TransparencyManifest[] = []
      for (const s of summaries) {
        const m = await source.manifest(s.sequence)
        fulls.push(m)
      }
      if (cancelled) return
      const r = await verifyChain(fulls, publicKeyPem)
      if (cancelled) return
      setChainResult(r)
      const structural: Record<number, boolean> = {}
      const crypto: Record<number, CryptoVerifyResult> = {}
      for (const m of fulls) {
        structural[m.sequence] = await verifyStructural(m)
        if (publicKeyPem !== null && structural[m.sequence]) {
          crypto[m.sequence] = await verifyCrypto(m, publicKeyPem)
        }
      }
      if (cancelled) return
      setStructuralByseq(structural)
      setCryptoByseq(crypto)
      const cache: Record<number, TransparencyManifest> = {}
      for (const m of fulls) cache[m.sequence] = m
      setFullCache(cache)

      // Witnesses: fetch + structural + target-match (no crypto verify yet —
      // we don't have witnesses' public keys in this view).
      const witnessesMap: Record<number, WitnessAttestation[]> = {}
      const wStructural: Record<string, boolean> = {}
      const wTarget: Record<string, boolean> = {}
      for (const m of fulls) {
        const ws = await source.witnessesForManifest(m.sequence)
        if (ws.length > 0) witnessesMap[m.sequence] = ws
        for (const w of ws) {
          wStructural[w.attestation_hash] = await verifyWitnessStructural(w)
          wTarget[w.attestation_hash] = await verifyWitnessTargetMatch(w, m)
        }
      }
      if (cancelled) return
      setWitnessesBySeq(witnessesMap)
      setWitnessStructural(wStructural)
      setWitnessTarget(wTarget)

      // Notarization (Phase 4): fetch per manifest, null when not notarized.
      const notarizationMap: Record<number, NotarizationSummary> = {}
      for (const m of fulls) {
        const n = await source.notarizationForManifest(m.sequence)
        if (n) notarizationMap[m.sequence] = n
      }
      if (cancelled) return
      setNotarizationBySeq(notarizationMap)
    })().finally(() => { if (!cancelled) setVerifying(false) })
    return () => { cancelled = true }
  }, [summaries, publicKeyPem, source])

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleUploadPem = async (file: File) => {
    setPkError(null)
    const text = await file.text()
    if (!text.includes('-----BEGIN')) {
      setPkError(t('portal.publicKey.invalidPem'))
      return
    }
    setPublicKeyPem(text)
    setPkSource('upload')
  }

  const handleRowClick = async (seq: number) => {
    const next = new Set(expanded)
    if (next.has(seq)) { next.delete(seq); setExpanded(next); return }
    next.add(seq)
    setExpanded(next)
    if (!fullCache[seq]) {
      setLoadingSeq(seq)
      try {
        const m = await source.manifest(seq)
        setFullCache(prev => ({ ...prev, [seq]: m }))
      } finally {
        setLoadingSeq(null)
      }
    }
  }

  const saveAndSwitch = (c: SourceConfig) => {
    saveSourceConfig(c)
    setConfig(c)
  }

  // ── derived ──────────────────────────────────────────────────────────

  const hits = summaries ? searchByHash(summaries, query) : []
  const head = status?.head
  const totalManifests = summaries?.length ?? 0

  return (
    <div className="space-y-6 animate-in">
      {/* Page header with settings button */}
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          tag={t('portal.header.tag')}
          title={t('portal.header.title')}
          description={t('portal.header.description')}
        />
        <button
          onClick={() => setShowSettings(true)}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border)] bg-white hover:bg-slate-50 text-[12px] font-medium text-slate-700 transition-colors mt-1"
        >
          <Settings size={12} /> {t('portal.cta.changeSource')}
        </button>
      </div>

      {/* Active source pill */}
      <div className="flex items-center gap-2 text-[11.5px]">
        {source.kind === 'backend'
          ? <Server size={12} className="text-violet-700" />
          : <Globe size={12} className="text-violet-700" />}
        <span className="text-[var(--muted)]">{t('portal.activeSource')}</span>
        <span className="font-mono text-slate-900">{source.label}</span>
      </div>

      {/* Trust model strip */}
      <div className="flex items-start gap-3 rounded-md bg-violet-50 border border-violet-200 px-4 py-3">
        <Lock size={14} className="text-violet-700 mt-0.5 shrink-0" />
        <div className="text-[12.5px] text-violet-900 leading-relaxed">
          <span className="font-semibold">{t('portal.trustModel.label')} </span>
          {t('portal.trustModel.body')} <code className="font-mono">SHA-256(JCS(manifest))</code>{' '}
          {t('portal.trustModel.bodyMid')} <code className="font-mono">@noble/curves</code>
          {t('portal.trustModel.bodyTail')}{' '}
          <code className="font-mono">previous_manifest_hash</code> {t('portal.trustModel.bodyEnd')}
        </div>
      </div>

      {fetchError && (
        <Alert variant="error">
          Error al cargar la fuente: <code className="font-mono">{fetchError}</code>. Revisa la URL en <em>Cambiar fuente</em>.
        </Alert>
      )}

      <VerdictHero
        loading={verifying || loading}
        result={chainResult}
        publicKeyLoaded={publicKeyPem !== null}
        sourceLabel={source.label}
      />

      {/* ── Trust footprint (ADR-0043) ───────────────────────────────────
          Only meaningful when the source is the operator backend (the
          /transparency/key-declaration endpoint lives there). Static
          bundles do not currently ship a key-declaration.json copy. */}
      <div>
        <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-widest mb-1.5">
          {t('portal.trustFootprint.heading')}
        </p>
        <p className="text-[12px] text-slate-500 mb-3">
          {t('portal.trustFootprint.subtitle')}
        </p>
        {source.kind === 'backend' ? (
          <TrustFootprintCard audience="recipient" />
        ) : (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-[12.5px] text-slate-600">
            {t('portal.trustFootprint.staticNote')}
          </div>
        )}
      </div>

      {/* Top row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        <Card>
          <CardHeader title={t('portal.operator.cardTitle')} sub={t('portal.operator.cardSubtitle')} />
          <div className="px-5 py-4 space-y-3">
            {head ? (
              <>
                <div className="flex items-center gap-2">
                  <User size={13} className="text-[var(--muted)]" />
                  <span className="text-[13px] font-medium text-slate-900">{head.operator_id}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Fingerprint size={13} className="text-[var(--muted)]" />
                  <Hash value={head.public_key_fingerprint} />
                </div>
                <div className="text-[11px] text-[var(--muted)]">
                  {t('portal.operator.fingerprintHint')}
                </div>
              </>
            ) : (
              <p className="text-[12px] text-[var(--muted)]">{t('portal.operator.noManifests')}</p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title={t('portal.publicKey.title')}
            sub={pkSource === 'source' ? t('portal.publicKey.loaded') : pkSource === 'upload' ? t('portal.publicKey.loaded') : '—'}
          />
          <div className="px-5 py-4 space-y-3">
            {publicKeyPem ? (
              <>
                <div className="flex items-center gap-2">
                  <Lock size={13} className="text-emerald-700" />
                  <span className="text-[12.5px] font-medium text-emerald-700">{t('portal.publicKey.loaded')} · {publicKeyPem.length} bytes</span>
                </div>
                <button
                  onClick={() => { setPublicKeyPem(null); setPkSource(null) }}
                  className="text-[11px] text-violet-700 hover:text-violet-900 font-medium"
                >
                  {t('portal.publicKey.upload')}
                </button>
              </>
            ) : (
              <>
                <p className="text-[12px] text-[var(--muted)] leading-relaxed">
                  {t('portal.publicKey.body')}
                </p>
                <label className="inline-flex items-center gap-2 px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white text-[12px] font-medium rounded cursor-pointer transition-colors">
                  <Upload size={12} />
                  {t('portal.publicKey.upload')}
                  <input
                    type="file"
                    accept=".pem,.pub,.key,.txt"
                    className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleUploadPem(f) }}
                  />
                </label>
                {pkError && <p className="text-[11px] text-red-700 mt-1">{pkError}</p>}
              </>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title={t('portal.chain.cardTitle')} sub={t('portal.chain.cardSubtitle')} />
          <div className="px-5 py-4 space-y-2.5">
            <div className="flex items-center gap-2">
              <Link2 size={13} className="text-[var(--muted)]" />
              <span className="text-[13px] text-slate-900">
                <span className="font-bold">{totalManifests}</span> manifest{totalManifests !== 1 ? 's' : ''}
              </span>
            </div>
            {head && (
              <>
                <div className="flex items-center gap-2">
                  <HashIcon size={13} className="text-[var(--muted)]" />
                  <span className="text-[11px] text-[var(--muted)]">head:</span>
                  <Hash value={head.manifest_hash} />
                </div>
                <div className="flex items-center gap-2">
                  <Clock size={13} className="text-[var(--muted)]" />
                  <span className="text-[11px] font-mono text-[var(--muted2)]">
                    {head.signed_at.replace('T', ' ').replace('Z', ' UTC')}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
                  <FileText size={11} /> {head.evidence_count} evidencias
                  <Layers size={11} className="ml-2" /> {head.attestation_count} attestations
                </div>
              </>
            )}
          </div>
        </Card>
      </div>

      {/* Search */}
      <div>
        <SectionLabel>{t('portal.section.searchByHash')}</SectionLabel>
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted3)]" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Pega un manifest_hash, audit_chain_head_hash o fingerprint (min 4 chars)…"
            className="w-full bg-white border border-[var(--border)] rounded-md pl-9 pr-4 py-2.5 text-[13px] text-slate-900 placeholder:text-[var(--muted3)] focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100 font-mono"
          />
        </div>
        {query.trim().length >= 4 && (
          <div className="mt-2">
            {hits.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)]">Sin coincidencias en {totalManifests} manifests.</p>
            ) : (
              <p className="text-[12px] text-emerald-700">
                {hits.length} coincidencia{hits.length !== 1 ? 's' : ''}: {hits.map(h => `seq ${h.manifest.sequence} (${h.matched_field})`).join(', ')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Manifest list */}
      <div>
        <SectionLabel>{t('portal.section.appendOnlyChain')}</SectionLabel>
        {loading && (
          <Card>
            <div className="p-5 space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-9 rounded" />)}
            </div>
          </Card>
        )}
        {!loading && totalManifests === 0 && !fetchError && (
          <EmptyState
            icon={<Link2 size={18} />}
            title={t('portal.manifests.empty.title')}
            description={t('portal.manifests.empty.body')}
          />
        )}
        {totalManifests > 0 && summaries && (
          <Card>
            {summaries.map(s => (
              <ManifestRow
                key={s.sequence}
                summary={s}
                structuralOk={structuralByseq[s.sequence] ?? null}
                cryptoResult={cryptoByseq[s.sequence] ?? null}
                onClick={() => handleRowClick(s.sequence)}
                expanded={expanded.has(s.sequence)}
                fullManifest={fullCache[s.sequence] ?? null}
                loadingFull={loadingSeq === s.sequence}
                witnesses={witnessesBySeq[s.sequence] ?? []}
                witnessStructural={witnessStructural}
                witnessTarget={witnessTarget}
                notarization={notarizationBySeq[s.sequence] ?? null}
              />
            ))}
          </Card>
        )}
      </div>

      {showSettings && (
        <SettingsPanel
          config={config}
          onSave={saveAndSwitch}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}
