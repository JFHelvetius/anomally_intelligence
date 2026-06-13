import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, CheckCircle2, XCircle, AlertCircle,
  ChevronDown, ChevronUp, ExternalLink,
  ShieldCheck, MapPin, Smartphone, Clock as ClockIcon, User as UserIcon,
  Camera, Download, Link2, Bitcoin, Brain,
} from 'lucide-react'
import { useState } from 'react'
import {
  api,
  type AuditEntrySummary,
  type CoverageManifestSummary,
  type InferenceProofReference,
  type EvidenceDetail as EvidenceDetailType,
  type CaptureCertificate as CaptureCertificateType,
} from '../api/client'
import { Card, Hash, Badge, Alert, Skeleton, InfoRow, SectionLabel } from '../components/ui'
import { useT } from '../i18n'

// ─── Trust Timeline ──────────────────────────────────────────────────────
// Une cronológicamente la cadena de confianza completa: captura → ingest →
// audit chain → manifests de transparency → witnesses → Bitcoin anchors →
// inference proofs. Cada layer es opcional — la vista degrada con gracia
// cuando un layer no está presente.

type TimelineEventKind = 'capture' | 'ingest' | 'manifest' | 'bitcoin' | 'proof'

interface TimelineEvent {
  kind: TimelineEventKind
  timestamp: string | null            // ISO or null (proofs no tienen)
  title: string
  subtitle?: string
  hash?: string
  link?: string                       // optional internal route (e.g. /proofs/<id>)
  badges?: { variant: 'green' | 'blue' | 'amber' | 'orange' | 'purple' | 'slate' | 'red'; text: string; dot?: boolean }[]
  details?: { label: string; value: React.ReactNode; mono?: boolean }[]
}

const KIND_ICON: Record<TimelineEventKind, React.ElementType> = {
  capture:  Camera,
  ingest:   Download,
  manifest: Link2,
  bitcoin:  Bitcoin,
  proof:    Brain,
}

const KIND_COLOR: Record<TimelineEventKind, { bg: string; border: string; text: string; iconBg: string }> = {
  capture:  { bg: 'bg-violet-50',  border: 'border-violet-200',  text: 'text-violet-700',  iconBg: 'bg-violet-100' },
  ingest:   { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', iconBg: 'bg-emerald-100' },
  manifest: { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-700',    iconBg: 'bg-blue-100' },
  bitcoin:  { bg: 'bg-orange-50',  border: 'border-orange-200',  text: 'text-orange-700',  iconBg: 'bg-orange-100' },
  proof:    { bg: 'bg-purple-50',  border: 'border-purple-200',  text: 'text-purple-700',  iconBg: 'bg-purple-100' },
}

function buildTimelineEvents(
  cert: CaptureCertificateType | null,
  audit: AuditEntrySummary | null,
  manifests: CoverageManifestSummary[],
  proofs: InferenceProofReference[],
): TimelineEvent[] {
  const events: TimelineEvent[] = []

  if (cert) {
    events.push({
      kind: 'capture',
      timestamp: cert.captured_at,
      title: 'Captured at source',
      subtitle: `by ${cert.operator_id}${cert.device_id ? ` · device ${cert.device_id}` : ''}`,
      hash: cert.certificate_hash,
      badges: [{ variant: 'green', dot: true, text: 'ed25519 signed' }],
      details: [
        ...(cert.location ? [{ label: 'Location', value: cert.location }] : []),
        ...(cert.notes ? [{ label: 'Notes', value: cert.notes }] : []),
        { label: 'Public key FP', value: cert.public_key_fingerprint, mono: true },
      ],
    })
  }

  if (audit) {
    const certInAudit = audit.parameters.capture_certificate_hash
    events.push({
      kind: 'ingest',
      timestamp: audit.timestamp,
      title: `Ingested into archive · audit seq #${audit.seq}`,
      subtitle: `by ${audit.actor}`,
      hash: audit.entry_hash,
      badges: [
        { variant: 'blue', dot: true, text: `audit seq ${audit.seq}` },
        ...(certInAudit ? [{ variant: 'green' as const, dot: true, text: 'cert validated' }] : []),
      ],
      details: [
        { label: 'Audit entry hash', value: audit.entry_hash, mono: true },
        { label: 'Size', value: `${audit.parameters.size_bytes ?? '?'} bytes`, mono: true },
      ],
    })
  }

  // Manifests covering this evidence + their Bitcoin anchors (if we had that data, but
  // we don't fetch .ots data per evidence — we just list manifest references).
  for (const m of manifests) {
    events.push({
      kind: 'manifest',
      timestamp: m.signed_at,
      title: `Covered by transparency manifest seq ${m.sequence}`,
      subtitle: `signed by ${m.operator_id}`,
      hash: m.manifest_hash,
      badges: [{ variant: 'blue', dot: true, text: `manifest seq ${m.sequence}` }],
      details: [
        { label: 'Manifest hash', value: m.manifest_hash, mono: true },
        { label: 'Audit chain head', value: m.audit_chain_head_hash, mono: true },
        { label: 'Audit entries pinned', value: `${m.audit_entry_count}`, mono: true },
      ],
    })
  }

  for (const p of proofs) {
    events.push({
      kind: 'proof',
      timestamp: null,
      title: `Referenced in inference proof ${p.proof_id}`,
      subtitle: `as premise ${p.matched_premise_id} → conclusion ${p.conclusion_claim_id}`,
      hash: p.proof_hash,
      link: `/proofs/${p.proof_id}`,
      badges: [
        { variant: 'purple', dot: true, text: `${p.inference_count} inferences` },
        ...(p.weak_inference_count > 0
          ? [{ variant: 'amber' as const, dot: true, text: `${p.weak_inference_count} weak` }]
          : []),
      ],
      details: [
        { label: 'Justification', value: p.target_justification_id, mono: true },
        { label: 'Proof hash', value: p.proof_hash, mono: true },
        { label: 'Conclusion claim', value: p.conclusion_claim_id, mono: true },
      ],
    })
  }

  // Chronological sort, with null timestamps at the end.
  events.sort((a, b) => {
    if (a.timestamp === null && b.timestamp === null) return 0
    if (a.timestamp === null) return 1
    if (b.timestamp === null) return -1
    return a.timestamp.localeCompare(b.timestamp)
  })

  return events
}

function TimelineEventRow({ event }: { event: TimelineEvent }) {
  const Icon = KIND_ICON[event.kind]
  const c = KIND_COLOR[event.kind]
  const timeStr = event.timestamp
    ? event.timestamp.replace('T', ' ').replace(/(\.\d+)?Z?(\+\d+:\d+)?$/, ' UTC')
    : null

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center shrink-0">
        <div className={`w-9 h-9 rounded-full ${c.iconBg} border ${c.border} flex items-center justify-center`}>
          <Icon size={14} className={c.text} />
        </div>
        <div className="w-px flex-1 bg-[var(--border)] mt-1" />
      </div>
      <div className={`flex-1 mb-4 rounded-md border ${c.border} ${c.bg} overflow-hidden`}>
        {event.link ? (
          <Link to={event.link} className="block px-4 py-2.5 border-b border-white/40 hover:bg-white/40 transition-colors">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <p className={`text-[13px] font-semibold ${c.text} leading-snug flex items-center gap-1.5`}>
                  {event.title}
                  <ExternalLink size={11} className="opacity-60" />
                </p>
                {event.subtitle && (
                  <p className="text-[11.5px] text-[var(--muted2)] mt-0.5 font-mono truncate">{event.subtitle}</p>
                )}
              </div>
              <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                {event.badges?.map((b, i) => (
                  <Badge key={i} variant={b.variant} dot={b.dot}>{b.text}</Badge>
                ))}
              </div>
            </div>
            {timeStr && (
              <p className="text-[10.5px] font-mono text-[var(--muted)] mt-1.5 flex items-center gap-1">
                <ClockIcon size={9} /> {timeStr}
              </p>
            )}
          </Link>
        ) : (
          <div className="px-4 py-2.5 border-b border-white/40">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <p className={`text-[13px] font-semibold ${c.text} leading-snug`}>{event.title}</p>
                {event.subtitle && (
                  <p className="text-[11.5px] text-[var(--muted2)] mt-0.5 font-mono truncate">{event.subtitle}</p>
                )}
              </div>
              <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                {event.badges?.map((b, i) => (
                  <Badge key={i} variant={b.variant} dot={b.dot}>{b.text}</Badge>
                ))}
              </div>
            </div>
            {timeStr && (
              <p className="text-[10.5px] font-mono text-[var(--muted)] mt-1.5 flex items-center gap-1">
                <ClockIcon size={9} /> {timeStr}
              </p>
            )}
          </div>
        )}
        {event.details && event.details.length > 0 && (
          <div className="px-4 py-2 bg-white/60 divide-y divide-white/80">
            {event.details.map((d, i) => (
              <div key={i} className="py-1 flex items-start gap-3 text-[11px]">
                <span className="text-[var(--muted)] font-bold uppercase tracking-wider w-32 shrink-0">{d.label}</span>
                <span className={`flex-1 break-all ${d.mono ? 'font-mono text-[10.5px] text-slate-700' : 'text-slate-700'}`}>
                  {d.value}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TrustTimeline({ data }: { data: EvidenceDetailType }) {
  const t = useT()
  const events = buildTimelineEvents(
    data.capture_certificate,
    data.audit_entry,
    data.coverage_manifests,
    data.inference_proofs_referencing,
  )

  if (events.length === 0) return null

  const layerCounts = {
    capture:  events.filter(e => e.kind === 'capture').length,
    ingest:   events.filter(e => e.kind === 'ingest').length,
    manifest: events.filter(e => e.kind === 'manifest').length,
    proof:    events.filter(e => e.kind === 'proof').length,
  }
  const totalLayers = Object.values(layerCounts).filter(c => c > 0).length

  return (
    <div>
      <SectionLabel>Trust timeline · {totalLayers} layer{totalLayers !== 1 ? 's' : ''} active</SectionLabel>
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 card-shadow">
        <p className="text-[11.5px] text-[var(--muted)] mb-4 leading-relaxed">
          {t('evidence.detail.trust.subtitle')}
        </p>
        <div>
          {events.map((e, i) => (
            <TimelineEventRow key={i} event={e} />
          ))}
        </div>
      </div>
    </div>
  )
}

const STATUS_INFO: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  active:   { icon: CheckCircle2, color: 'text-emerald-700', label: 'Activo' },
  inactive: { icon: XCircle,      color: 'text-[#546175]',   label: 'Inactivo' },
  disputed: { icon: AlertCircle,  color: 'text-amber-700',   label: 'Disputado' },
}

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 transition-colors"
        style={{ borderBottom: open ? '1px solid var(--border)' : 'none' }}
        onMouseEnter={ev => (ev.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
        onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}
      >
        <span className="text-[10px] font-bold uppercase tracking-[0.13em]" style={{ color: 'var(--muted)' }}>
          {title}
        </span>
        {open
          ? <ChevronUp size={13} style={{ color: 'var(--muted)' }} />
          : <ChevronDown size={13} style={{ color: 'var(--muted)' }} />}
      </button>
      {open && <div className="px-5 py-1">{children}</div>}
    </Card>
  )
}

export default function EvidenceDetail() {
  const t = useT()
  const { hash } = useParams<{ hash: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['evidence', hash],
    queryFn: () => api.getEvidence(hash!),
    enabled: !!hash,
  })

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-3.5 w-32 rounded" />
        <Skeleton className="h-9 w-72 rounded-lg" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-xl p-5 space-y-3" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            {[...Array(4)].map((_, j) => <Skeleton key={j} className="h-3 rounded" />)}
          </div>
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Link to="/evidence" className="flex items-center gap-1.5 text-xs transition-colors hover:text-violet-700" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={12} /> Volver a Evidence
        </Link>
        <Alert variant="error">{(error as Error).message}</Alert>
      </div>
    )
  }
  if (!data) return null

  const { evidence: e, source: s, provenance: p, derived_assessments: da } = data
  const statusInfo = STATUS_INFO[e.status] ?? STATUS_INFO.active
  const StatusIcon = statusInfo.icon

  return (
    <div className="max-w-3xl mx-auto space-y-4 animate-in">

      {/* Back */}
      <Link
        to="/evidence"
        className="inline-flex items-center gap-1.5 text-xs font-medium transition-colors hover:text-violet-700"
        style={{ color: 'var(--muted)' }}
      >
        <ArrowLeft size={12} /> Volver a Evidence
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="green">{e.kind?.replace(/_/g, ' ')}</Badge>
            <span className="flex items-center gap-1.5 text-xs">
              <StatusIcon size={12} className={statusInfo.color} />
              <span className={`font-medium ${statusInfo.color}`}>{statusInfo.label}</span>
            </span>
          </div>
          <Hash value={e.hash} full />
        </div>
        <a
          href={`/api/evidence/${e.hash}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors hover:text-violet-700"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--muted2)' }}
        >
          Raw JSON <ExternalLink size={10} />
        </a>
      </div>

      {/* ── Trust Timeline (unified view across all phases) ────── */}
      <TrustTimeline data={data} />

      {/* ── Captura firmada en origen (Phase 2) ─────────────────── */}
      {data.capture_certificate && (
        <div className="rounded-lg border border-emerald-200 bg-white card-shadow overflow-hidden">
          <div className="bg-emerald-50 px-5 py-3.5 border-b border-emerald-200 flex items-start gap-3">
            <div className="w-10 h-10 rounded-md bg-white border border-emerald-200 flex items-center justify-center shrink-0">
              <ShieldCheck size={18} className="text-emerald-700" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13.5px] font-bold text-emerald-800 tracking-tight">
                {t('evidence.detail.capture.title')}
              </p>
              <p className="text-[12px] text-emerald-900/70 mt-0.5 leading-relaxed">
                {t('evidence.detail.capture.body')}{' '}
                <code className="font-mono bg-white/60 px-1.5 py-0.5 rounded text-emerald-800">aip capture verify</code>.
              </p>
            </div>
            <Badge variant="green" dot>{t('evidence.detail.capture.signed')}</Badge>
          </div>

          {/* Quick-glance metadata grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-[var(--border)] border-b border-[var(--border)]">
            <div className="bg-white px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)] mb-1.5 flex items-center gap-1">
                <UserIcon size={9} /> {t('evidence.detail.capture.field.operator')}
              </p>
              <p className="text-[13px] text-slate-900 font-medium truncate">{data.capture_certificate.operator_id}</p>
            </div>
            <div className="bg-white px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)] mb-1.5 flex items-center gap-1">
                <ClockIcon size={9} /> {t('evidence.detail.capture.field.captured')}
              </p>
              <p className="text-[12px] text-slate-900 font-mono truncate">
                {data.capture_certificate.captured_at.replace('T', ' ').replace('Z', ' UTC')}
              </p>
            </div>
            <div className="bg-white px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)] mb-1.5 flex items-center gap-1">
                <Smartphone size={9} /> {t('evidence.detail.capture.field.device')}
              </p>
              <p className="text-[13px] text-slate-900 font-medium truncate">
                {data.capture_certificate.device_id ?? <span className="text-[var(--muted3)]">{t('evidence.detail.capture.field.notDeclared')}</span>}
              </p>
            </div>
            <div className="bg-white px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)] mb-1.5 flex items-center gap-1">
                <MapPin size={9} /> {t('evidence.detail.capture.field.location')}
              </p>
              <p className="text-[13px] text-slate-900 font-medium truncate">
                {data.capture_certificate.location ?? <span className="text-[var(--muted3)]">{t('evidence.detail.capture.field.notDeclared')}</span>}
              </p>
            </div>
          </div>

          {/* Cryptographic details */}
          <div className="px-5 py-1">
            <InfoRow label="Cert hash" mono>{data.capture_certificate.certificate_hash}</InfoRow>
            <InfoRow label="Public key FP" mono>{data.capture_certificate.public_key_fingerprint}</InfoRow>
            <InfoRow label={t('evidence.detail.capture.field.algorithm')} mono>{data.capture_certificate.signature_algorithm}</InfoRow>
            <InfoRow label="Schema" mono>{data.capture_certificate.certificate_type} · v{data.capture_certificate.schema_version}</InfoRow>
            <InfoRow label={t('evidence.detail.capture.field.signature')} mono>
              <span className="break-all text-[10px] text-[var(--muted2)]">{data.capture_certificate.signature}</span>
            </InfoRow>
            {data.capture_certificate.notes && (
              <InfoRow label={t('evidence.detail.capture.field.notes')}>{data.capture_certificate.notes}</InfoRow>
            )}
          </div>
        </div>
      )}

      {/* Evidence metadata */}
      <Section title={t('evidence.detail.section.metadata')}>
        <InfoRow label="MIME type"   mono>{e.mime_type}</InfoRow>
        <InfoRow label={t('evidence.detail.field.size')}>{`${e.size_bytes.toLocaleString()} bytes (${(e.size_bytes / 1024).toFixed(2)} KB)`}</InfoRow>
        <InfoRow label="Content URI" mono>{e.content_uri}</InfoRow>
        <InfoRow label={t('evidence.detail.field.ingestedBy')} mono>{e.ingested_by}</InfoRow>
        <InfoRow label={t('evidence.detail.field.ingestedAt')} mono>{e.ingested_at}</InfoRow>
        {e.notes && <InfoRow label={t('evidence.detail.field.notes')}>{e.notes}</InfoRow>}
      </Section>

      {/* Source */}
      <Section title={t('evidence.detail.section.sourceLabel')}>
        <InfoRow label={t('evidence.detail.source.id')} mono>{s.id}</InfoRow>
        <InfoRow label={t('evidence.detail.source.name')}>{s.name}</InfoRow>
        <InfoRow label={t('evidence.detail.source.kind')}><Badge variant="blue">{s.kind?.replace(/_/g, ' ')}</Badge></InfoRow>
        <InfoRow label={t('evidence.detail.source.authority')}><Badge variant="amber">{s.authority_level}</Badge></InfoRow>
        {s.jurisdiction && <InfoRow label={t('evidence.detail.source.jurisdiction')}>{s.jurisdiction}</InfoRow>}
        {s.license && <InfoRow label={t('evidence.detail.source.license')}>{s.license}</InfoRow>}
      </Section>

      {/* Provenance chain */}
      <Section title={`Cadena de procedencia · ${p.steps.length} paso${p.steps.length !== 1 ? 's' : ''}`}>
        {p.gaps.length > 0 && (
          <div
            className="mb-4 mt-2 flex items-start gap-2.5 rounded-xl px-3.5 py-3"
            style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.25)' }}
          >
            <AlertCircle size={13} className="text-amber-700 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-amber-700 mb-1">Gaps declarados en la cadena</p>
              <ul className="text-xs text-amber-700/70 space-y-0.5">
                {p.gaps.map((g, i) => <li key={i}>· {g}</li>)}
              </ul>
            </div>
          </div>
        )}

        <div className="relative py-2">
          {p.steps.map((st, i) => (
            <div key={st.step_index} className="flex gap-3 mb-4 last:mb-0">
              <div className="flex flex-col items-center shrink-0">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold"
                  style={{ background: 'rgba(124,58,237,0.15)', border: '1px solid rgba(124,58,237,0.35)', color: 'var(--accent2)' }}
                >
                  {st.step_index}
                </div>
                {i < p.steps.length - 1 && (
                  <div className="w-px flex-1 mt-1.5" style={{ background: 'var(--border)' }} />
                )}
              </div>
              <div className="flex-1 pb-3">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <Badge variant="purple">{st.kind?.replace(/_/g, ' ')}</Badge>
                  <span className="text-[11px] font-mono" style={{ color: 'var(--muted2)' }}>{st.actor}</span>
                  {st.timestamp && (
                    <span className="text-[11px] font-mono ml-auto" style={{ color: 'var(--muted)' }}>
                      {st.timestamp.slice(0, 10)}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-700">{st.description}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Authentication assessments */}
      {da.length > 0 && (
        <Section title={`Evaluaciones de autenticidad · ${da.length}`}>
          {da.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-4 py-2.5 last:pb-0"
              style={{ borderBottom: i < da.length - 1 ? '1px solid var(--border)' : 'none' }}
            >
              <Badge variant="blue">{a.method?.replace(/_/g, ' ')}</Badge>
              <Badge variant={a.status === 'authenticated' ? 'green' : a.status === 'contested' ? 'red' : 'amber'}>
                {a.status}
              </Badge>
              <span className="text-[11px] font-mono ml-auto" style={{ color: 'var(--muted2)' }}>{a.assessed_by}</span>
              <span className="text-[11px] font-mono" style={{ color: 'var(--muted)' }}>{a.assessed_at?.slice(0, 10)}</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  )
}
