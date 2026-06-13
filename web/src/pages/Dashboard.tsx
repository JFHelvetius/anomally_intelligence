import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import {
  FileText, Link2, Shield, ArrowRight, Database, Clock,
  Hash as HashIcon, FolderSearch, Eye,
} from 'lucide-react'
import { api, type AuditLogPage } from '../api/client'
import { Card, Hash, StatusDot, Badge, Alert, SkeletonCard } from '../components/ui'
import { TrustFootprintCard } from '../components/TrustFootprintCard'
import { BitcoinAnchorStatus } from '../components/BitcoinAnchorStatus'
import { useT } from '../i18n'
import type { TKey } from '../i18n/en'

// ─── Audit-log action vocabulary ──────────────────────────────────────────
// Untranslated stable identifiers (they're canonical action names).
// Colors are restrained — the chart already encodes meaning by count.
const ACTION_COLOR: Record<string, string> = {
  archive_bootstrap:     '#94a3b8',
  ingest_evidence:       '#475569',
  assess_authentication: '#94a3b8',
  build_workspace:       '#7c3aed',
  build_timeline:        '#7c3aed',
  build_snapshot:        '#7c3aed',
  build_justification:   '#7c3aed',
  sign_attestation:      '#0f172a',
}
const ACTION_LABEL: Record<string, string> = {
  archive_bootstrap:     'Bootstrap',
  ingest_evidence:       'Ingest',
  assess_authentication: 'Assess',
  build_workspace:       'Workspace',
  build_timeline:        'Timeline',
  build_snapshot:        'Snapshot',
  build_justification:   'Justification',
  sign_attestation:      'Sign',
}

function buildActivityData(log: AuditLogPage | undefined) {
  if (!log) return { actionCounts: [] }
  const counts: Record<string, number> = {}
  for (const e of log.entries) {
    const action = e.action as string
    counts[action] = (counts[action] ?? 0) + 1
  }
  return {
    actionCounts: Object.entries(counts)
      .map(([action, count]) => ({
        label: ACTION_LABEL[action] ?? action,
        count,
        color: ACTION_COLOR[action] ?? '#94a3b8',
      }))
      .sort((a, b) => b.count - a.count),
  }
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { value: number }[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[var(--border)] rounded-md px-2.5 py-1.5 text-[11px] shadow-sm">
      <p className="text-[var(--text)] font-medium">{payload[0].value} entries</p>
    </div>
  )
}

// ─── Investigation workflow / conclusion / section catalogs ──────────────
// All visual variation was previously encoded per-row via per-color
// backgrounds. The refresh moves to a single neutral surface; the icon
// itself does the visual work. Hierarchy comes from typography, not paint.

interface WorkflowStep {
  step: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  titleKey: TKey
  bodyKey: TKey
}

const WORKFLOW: WorkflowStep[] = [
  { step: '01', icon: FileText,     titleKey: 'dashboard.workflow.01.title', bodyKey: 'dashboard.workflow.01.body' },
  { step: '02', icon: Eye,          titleKey: 'dashboard.workflow.02.title', bodyKey: 'dashboard.workflow.02.body' },
  { step: '03', icon: FolderSearch, titleKey: 'dashboard.workflow.03.title', bodyKey: 'dashboard.workflow.03.body' },
  { step: '04', icon: Shield,       titleKey: 'dashboard.workflow.04.title', bodyKey: 'dashboard.workflow.04.body' },
]

interface ConclusionType {
  labelKey: TKey
  bodyKey: TKey
  tone: 'ok' | 'unknown' | 'indet' | 'bad'
}

const CONCLUSION_TYPES: ConclusionType[] = [
  { labelKey: 'dashboard.conclusions.explained.label',     bodyKey: 'dashboard.conclusions.explained.body',     tone: 'ok' },
  { labelKey: 'dashboard.conclusions.unexplained.label',   bodyKey: 'dashboard.conclusions.unexplained.body',   tone: 'unknown' },
  { labelKey: 'dashboard.conclusions.indeterminate.label', bodyKey: 'dashboard.conclusions.indeterminate.body', tone: 'indet' },
  { labelKey: 'dashboard.conclusions.tampered.label',      bodyKey: 'dashboard.conclusions.tampered.body',      tone: 'bad' },
]

interface SectionCard {
  to: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  titleKey: TKey
  bodyKey: TKey
}

const SECTIONS: SectionCard[] = [
  { to: '/cases',        icon: FolderSearch, titleKey: 'dashboard.sections.cases.title',        bodyKey: 'dashboard.sections.cases.body' },
  { to: '/evidence',     icon: FileText,     titleKey: 'dashboard.sections.evidence.title',     bodyKey: 'dashboard.sections.evidence.body' },
  { to: '/audit-log',    icon: Link2,        titleKey: 'dashboard.sections.audit.title',        bodyKey: 'dashboard.sections.audit.body' },
  { to: '/attestations', icon: Shield,       titleKey: 'dashboard.sections.attestations.title', bodyKey: 'dashboard.sections.attestations.body' },
]

// ─── Stat card — neutral surface, no colored chip ─────────────────────────

function StatCard({
  icon: Icon, label, value, to, primary,
}: {
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>
  label: string
  value: React.ReactNode
  to?: string
  /** When true, the card uses an accent-tinted background so the eye lands here first. */
  primary?: boolean
}) {
  const inner = (
    <div
      className="rounded-lg border p-4 transition-colors hover:bg-[var(--surface2)]"
      style={{
        background: primary ? 'var(--accent-bg)' : 'var(--surface)',
        borderColor: primary ? 'var(--accent3)' : 'var(--border)',
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <Icon
          size={14}
          style={{ color: primary ? 'var(--accent2)' : 'var(--muted)' }}
        />
        {to && (
          <ArrowRight
            size={12}
            style={{ color: primary ? 'var(--accent3)' : 'var(--border2)' }}
          />
        )}
      </div>
      <p
        className="text-[22px] font-semibold leading-none mb-1.5 tracking-tight"
        style={{ color: 'var(--text)' }}
      >
        {value}
      </p>
      <p
        className="text-[11px] uppercase tracking-wider font-medium"
        style={{ color: primary ? 'var(--accent2)' : 'var(--muted)' }}
      >
        {label}
      </p>
    </div>
  )
  return to ? <Link to={to}>{inner}</Link> : inner
}

// ─── Section header — consistent typography across all sub-blocks ────────

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-3">
      <p
        className="text-[10.5px] font-bold uppercase tracking-[0.14em] mb-1"
        style={{ color: 'var(--muted3)' }}
      >
        {title}
      </p>
      {subtitle && (
        <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
          {subtitle}
        </p>
      )}
    </header>
  )
}

// ─── Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const t = useT()
  const status   = useQuery({ queryKey: ['archive-status'],    queryFn: api.archiveStatus })
  const verify   = useQuery({ queryKey: ['archive-verify'],    queryFn: api.archiveVerify })
  const evidence = useQuery({ queryKey: ['evidence-list'],     queryFn: api.listEvidence })
  const attests  = useQuery({ queryKey: ['attestations-list'], queryFn: api.listAttestations })
  const auditLog = useQuery({ queryKey: ['audit-log', 0],      queryFn: () => api.auditLog(0, 500) })
  const workspaces = useQuery({ queryKey: ['workspaces'],      queryFn: api.listWorkspaces })
  const transparency = useQuery({ queryKey: ['transparency-status'], queryFn: api.transparencyStatus })

  const d = status.data
  const loading = status.isLoading
  const { actionCounts } = buildActivityData(auditLog.data)

  return (
    <div className="max-w-5xl space-y-10">

      {/* ── Hero — tinted block, accent rail, status pill ────────── */}
      <header
        className="relative overflow-hidden rounded-xl border px-7 py-7"
        style={{
          background: 'linear-gradient(135deg, var(--surface-tint) 0%, var(--bg2) 60%)',
          borderColor: 'var(--border)',
        }}
      >
        <div
          className="absolute left-0 top-5 bottom-5 w-[3px] rounded-r-sm"
          style={{ background: 'var(--accent)' }}
        />
        <div className="relative">
          <div className="flex items-center gap-3 mb-3">
            <span
              className="text-[10.5px] font-bold uppercase tracking-[0.16em]"
              style={{ color: 'var(--accent2)' }}
            >
              {t('dashboard.hero.eyebrow')}
            </span>
            {!loading && verify.data && (
              <StatusDot
                ok={verify.data.ok}
                label={verify.data.ok ? t('dashboard.hero.status.ok') : t('dashboard.hero.status.fail')}
              />
            )}
          </div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight mb-2.5 max-w-2xl"
            style={{ color: 'var(--text)' }}
          >
            {t('dashboard.hero.title')}
          </h1>
          <p
            className="text-[13px] leading-relaxed max-w-2xl"
            style={{ color: 'var(--muted2)' }}
          >
            {t('dashboard.hero.body')}
          </p>
          <p
            className="text-[11.5px] font-mono italic mt-3"
            style={{ color: 'var(--muted)' }}
          >
            {'> '}
            {t('dashboard.hero.question')}
          </p>
        </div>
      </header>

      {/* ── Offline / demo-mode banner ───────────────────────────── */}
      {status.isError && <OfflineBanner />}

      {/* ── Stats row ─────────────────────────────────────────────── */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : d ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={FolderSearch} label={t('dashboard.stats.cases')}        value={workspaces.data?.length ?? 0} to="/cases"        primary />
          <StatCard icon={FileText}     label={t('dashboard.stats.evidence')}     value={evidence.data?.length ?? 0}   to="/evidence" />
          <StatCard icon={Link2}        label={t('dashboard.stats.audit')}        value={d.audit_entries}              to="/audit-log" />
          <StatCard icon={Shield}       label={t('dashboard.stats.attestations')} value={attests.data?.length ?? 0}   to="/attestations" />
        </div>
      ) : status.isError && (
        <PreviewStats />
      )}

      {/* ── Archive status bar ────────────────────────────────────── */}
      {d && (
        <Card className="px-4 py-2.5">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[11px]">
            <span className="flex items-center gap-1.5" style={{ color: 'var(--muted)' }}>
              <Database size={10} style={{ color: 'var(--muted3)' }} />
              <span className="font-mono truncate max-w-xs" style={{ color: 'var(--muted2)' }}>{d.root}</span>
            </span>
            {d.manifest_hash && (
              <span className="flex items-center gap-1.5" style={{ color: 'var(--muted)' }}>
                <HashIcon size={10} style={{ color: 'var(--muted3)' }} /> <Hash value={d.manifest_hash} />
              </span>
            )}
            {d.generated_at && (
              <span className="flex items-center gap-1.5 font-mono" style={{ color: 'var(--muted)' }}>
                <Clock size={10} style={{ color: 'var(--muted3)' }} />
                {d.generated_at.replace('T', ' ').replace('Z', ' UTC')}
              </span>
            )}
            <span className="ml-auto">
              <Badge variant={verify.data?.ok ? 'green' : 'red'} dot>
                {verify.data?.ok ? t('dashboard.hero.status.ok') : t('dashboard.hero.status.fail')}
              </Badge>
            </span>
          </div>
        </Card>
      )}

      {/* ── Trust footprint + OTS / Bitcoin anchor status ───────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <SectionHeader
            title={t('dashboard.trust.title')}
            subtitle={t('dashboard.trust.subtitle')}
          />
          {status.isError
            ? <PreviewCard bodyKey="dashboard.offline.trust.body" />
            : <TrustFootprintCard audience="operator" />}
        </div>
        <div>
          <SectionHeader
            title={t('dashboard.ots.title')}
            subtitle={t('dashboard.ots.subtitle')}
          />
          {status.isError
            ? <PreviewCard bodyKey="dashboard.offline.ots.body" />
            : transparency.data && (
              <BitcoinAnchorStatus manifestCount={transparency.data.manifest_count} />
            )}
        </div>
      </div>

      {/* ── Activity chart ────────────────────────────────────────── */}
      {auditLog.data && auditLog.data.total > 0 && (
        <div>
          <SectionHeader
            title={t('dashboard.activity.title')}
            subtitle={t('dashboard.activity.subtitle')}
          />
          <Card>
            <div className="p-5 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={actionCounts} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10.5 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="label" tick={{ fill: '#94a3b8', fontSize: 10.5 }}
                    axisLine={false} tickLine={false} width={78} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
                  <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                    {actionCounts.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {/* ── Integrity issues ─────────────────────────────────────── */}
      {verify.data && !verify.data.ok && (
        <Alert variant="warning">
          <strong>{t('dashboard.integrity.fail.title')}</strong>
          <ul className="mt-1 space-y-0.5">
            {verify.data.checks.filter(c => !c.ok).map((c, i) => (
              <li key={i} className="text-xs font-mono">· {c.name}{c.detail ? ` — ${c.detail}` : ''}</li>
            ))}
          </ul>
        </Alert>
      )}

      {/* ── Recent evidence ──────────────────────────────────────── */}
      {evidence.data && evidence.data.length > 0 && (
        <div>
          <SectionHeader title={t('dashboard.recent.heading')} />
          <Card>
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {evidence.data.slice(0, 4).map((e) => (
                <Link key={e.hash} to={`/evidence/${e.hash}`}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-[var(--surface2)] transition-colors group">
                  <FileText size={14} className="text-[var(--muted3)] shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <Hash value={e.hash} />
                      <Badge variant="slate">{e.kind?.replace(/_/g, ' ')}</Badge>
                    </div>
                    <p className="text-[11px] text-[var(--muted)] font-mono">
                      {e.ingested_by} · {e.ingested_at?.slice(0, 10)} · {(e.size_bytes / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <ArrowRight size={12} className="text-[var(--muted3)] group-hover:text-[var(--muted)] transition-colors shrink-0" />
                </Link>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── EXPLAINER FOOTER — workflow, conclusions, sections ──────
            Moved to the bottom so live data leads. Visually subdued
            (no colored backgrounds) so it doesn't compete for the
            operator's attention. */}
      <section className="pt-10 border-t" style={{ borderColor: 'var(--border)' }}>
        <SectionHeader
          title={t('dashboard.workflow.title')}
          subtitle={t('dashboard.workflow.subtitle')}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-10">
          {WORKFLOW.map((s) => {
            const Icon = s.icon
            return (
              <div key={s.step}
                className="rounded-lg border p-4"
                style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <div className="flex items-start gap-3">
                  <Icon size={14} className="text-[var(--muted)] mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono font-bold" style={{ color: 'var(--muted3)' }}>{s.step}</span>
                      <p className="text-[12.5px] font-semibold" style={{ color: 'var(--text)' }}>{t(s.titleKey)}</p>
                    </div>
                    <p className="text-[11.5px] leading-relaxed" style={{ color: 'var(--muted)' }}>{t(s.bodyKey)}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <SectionHeader
          title={t('dashboard.conclusions.title')}
          subtitle={t('dashboard.conclusions.subtitle')}
        />
        <div className="grid grid-cols-2 gap-3 mb-10">
          {CONCLUSION_TYPES.map((c) => (
            <ConclusionPill key={c.labelKey} c={c} />
          ))}
        </div>

        <SectionHeader title={t('dashboard.sections.heading')} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SECTIONS.map(({ to, icon: Icon, titleKey, bodyKey }) => (
            <Link key={to} to={to}
              className="rounded-lg border p-4 flex items-start gap-3 transition-colors hover:bg-[var(--surface2)]"
              style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <Icon size={14} className="text-[var(--muted)] mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12.5px] font-semibold mb-0.5" style={{ color: 'var(--text)' }}>{t(titleKey)}</p>
                <p className="text-[11.5px] leading-relaxed" style={{ color: 'var(--muted)' }}>{t(bodyKey)}</p>
              </div>
              <ArrowRight size={12} className="text-[var(--muted3)] shrink-0 mt-1" />
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}

// ─── Conclusion tone pill ─────────────────────────────────────────────────

function ConclusionPill({ c }: { c: ConclusionType }) {
  const t = useT()
  const toneColor: Record<ConclusionType['tone'], string> = {
    ok:      'var(--green)',
    unknown: 'var(--amber)',
    indet:   'var(--blue)',
    bad:     'var(--red)',
  }
  return (
    <div
      className="rounded-lg border p-3.5"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: toneColor[c.tone] }} />
        <span className="text-[12.5px] font-semibold" style={{ color: 'var(--text)' }}>{t(c.labelKey)}</span>
      </div>
      <p className="text-[11.5px] leading-relaxed" style={{ color: 'var(--muted)' }}>{t(c.bodyKey)}</p>
    </div>
  )
}

// ─── Offline / demo-mode components ───────────────────────────────────────

function OfflineBanner() {
  const t = useT()
  return (
    <div
      className="rounded-lg border p-5"
      style={{ background: 'var(--surface2)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-start gap-3 mb-3">
        <Database size={15} className="text-[var(--muted)] mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <h3 className="text-[13px] font-semibold tracking-tight leading-snug" style={{ color: 'var(--text)' }}>
            {t('dashboard.offline.banner.title')}
          </h3>
          <p className="text-[12.5px] leading-relaxed mt-1" style={{ color: 'var(--muted2)' }}>
            {t('dashboard.offline.banner.body')}
          </p>
        </div>
      </div>
      <pre
        className="text-[11px] rounded-md p-3 overflow-x-auto leading-relaxed"
        style={{
          background: 'var(--bg2)',
          border: '1px solid var(--border)',
          color: 'var(--text2)',
        }}
      >
{`# Run from the repo root, in a separate terminal:
$env:AIP_ARCHIVE_PATH = "./docs/demo/demo_archive"
.venv\\Scripts\\aip-web.exe`}
      </pre>
      <p className="text-[11px] mt-2 italic" style={{ color: 'var(--muted)' }}>
        {t('dashboard.offline.banner.hint')}
      </p>
    </div>
  )
}

function PreviewStats() {
  const t = useT()
  return (
    <div
      className="rounded-lg border border-dashed px-5 py-4 flex items-start gap-3"
      style={{ background: 'var(--bg2)', borderColor: 'var(--border2)' }}
    >
      <Database size={14} className="text-[var(--muted3)] mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <h3 className="text-[12.5px] font-semibold leading-snug mb-1" style={{ color: 'var(--text2)' }}>
          {t('dashboard.offline.stats.title')}
        </h3>
        <p className="text-[11.5px] leading-relaxed" style={{ color: 'var(--muted)' }}>
          {t('dashboard.offline.stats.body')}
        </p>
      </div>
    </div>
  )
}

function PreviewCard({ bodyKey }: { bodyKey: TKey }) {
  const t = useT()
  return (
    <div
      className="rounded-lg border border-dashed px-5 py-6 text-center"
      style={{ background: 'var(--bg2)', borderColor: 'var(--border2)' }}
    >
      <Database size={18} strokeWidth={1.5} className="text-[var(--muted3)] mx-auto mb-3" />
      <p className="text-[12px] leading-relaxed max-w-md mx-auto" style={{ color: 'var(--muted2)' }}>
        {t(bodyKey)}
      </p>
    </div>
  )
}
