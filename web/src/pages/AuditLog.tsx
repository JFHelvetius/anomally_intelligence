import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Link2, ChevronRight, CheckCircle2, XCircle, Filter,
  ShieldCheck, ShieldAlert, Loader2, ChevronDown, ChevronUp,
} from 'lucide-react'
import { api } from '../api/client'
import { Hash, Badge, PageHeader, EmptyState, Alert } from '../components/ui'
import {
  verifyEntireChain, computeEntryHash,
  type AuditEntry, type ChainVerifyReport,
} from '../lib/auditChain'
import { useT } from '../i18n'

const ACTION_META: Record<string, { color: string; variant: 'green'|'blue'|'amber'|'purple'|'orange'|'slate'; icon: string }> = {
  archive_bootstrap:     { color: '#3b82f6', variant: 'blue',   icon: '⬡' },
  ingest_evidence:       { color: '#10b981', variant: 'green',  icon: '↓' },
  assess_authentication: { color: '#f59e0b', variant: 'amber',  icon: '✓' },
  build_workspace:       { color: '#8b5cf6', variant: 'purple', icon: '⊞' },
  build_timeline:        { color: '#a78bfa', variant: 'purple', icon: '↕' },
  build_snapshot:        { color: '#6366f1', variant: 'purple', icon: '⊙' },
  build_justification:   { color: '#7c3aed', variant: 'purple', icon: '⊢' },
  sign_attestation:      { color: '#f97316', variant: 'orange', icon: '🔐' },
}

const ALL_ACTIONS = Object.keys(ACTION_META)

export default function AuditLog() {
  const t = useT()
  const [offset, setOffset]             = useState(0)
  const [filterAction, setFilterAction] = useState<string | null>(null)
  const [chainReport, setChainReport]   = useState<ChainVerifyReport | null>(null)
  const [verifying, setVerifying]       = useState(false)
  const [expanded, setExpanded]         = useState<Set<number>>(new Set())
  const [computedHashes, setComputedHashes] = useState<Record<number, string>>({})
  const limit = 50

  const { data, isLoading, isError } = useQuery({
    queryKey: ['audit-log', offset],
    queryFn: () => api.auditLog(0, 500),
  })

  const allEntries = data?.entries ?? []

  // Client-side verify whenever entries change.
  useEffect(() => {
    let cancelled = false
    if (allEntries.length === 0) {
      setChainReport(null)
      setComputedHashes({})
      return
    }
    setVerifying(true)
    ;(async () => {
      const typed = allEntries as unknown as AuditEntry[]
      const report = await verifyEntireChain(typed)
      if (cancelled) return
      // Also recompute hashes (separately, for the broken-entry inspector).
      const hashes: Record<number, string> = {}
      for (const seq of report.brokenHashEntries) {
        const e = typed.find(x => x.seq === seq)
        if (e) hashes[seq] = await computeEntryHash(e)
      }
      if (cancelled) return
      setChainReport(report)
      setComputedHashes(hashes)
    })().finally(() => { if (!cancelled) setVerifying(false) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])
  const filtered = filterAction
    ? allEntries.filter(e => (e.action as string) === filterAction)
    : allEntries

  const total   = filtered.length
  const page    = filtered.slice(offset, offset + limit)
  const pages   = Math.ceil(total / limit)
  const pageNum = Math.floor(offset / limit)

  const pillBase = 'px-3 py-1 rounded-full text-[11px] border transition-all duration-150 font-medium'
  const pillActive = 'bg-[var(--accent-bg)] border-[var(--accent)] text-[var(--accent)]'
  const pillInactive = 'border-[#16203a] text-[#546175] hover:text-[var(--text2)] hover:border-[#1d2d50] hover:bg-white/[0.03]'

  return (
    <div className="space-y-5">
      <PageHeader
        tag={t('audit.tag')}
        title={t('audit.title')}
        description={t('audit.description')}
      />

      {/* Chain verification banner */}
      {(verifying || chainReport) && (
        <ChainVerifyBanner verifying={verifying} report={chainReport} />
      )}

      {/* Filter pills */}
      {allEntries.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <Filter size={11} className="text-[#546175]" />
          <button
            onClick={() => { setFilterAction(null); setOffset(0) }}
            className={`${pillBase} ${!filterAction ? pillActive : pillInactive}`}
          >
            {t('audit.filter.all')} ({allEntries.length})
          </button>
          {ALL_ACTIONS.filter(a => allEntries.some(e => e.action === a)).map(action => {
            const meta = ACTION_META[action]
            const count = allEntries.filter(e => e.action === action).length
            return (
              <button
                key={action}
                onClick={() => { setFilterAction(action); setOffset(0) }}
                className={`${pillBase} ${filterAction === action ? pillActive : pillInactive}`}
              >
                <span style={{ color: meta.color }}>{meta.icon}</span>{' '}
                {action.replace(/_/g, ' ')} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-[#090d1c] border border-[#16203a] rounded-xl h-16 skeleton" />
          ))}
        </div>
      )}

      {isError && <Alert variant="error">{t('audit.error.load')}</Alert>}

      {!isLoading && filtered.length === 0 && (
        <EmptyState
          icon={<Link2 size={20} />}
          title={t('audit.empty.title')}
          description={t('audit.empty.body')}
        />
      )}

      {/* Chain view */}
      {!isLoading && page.length > 0 && (
        <div className="relative">
          {/* Vertical chain line */}
          <div className="absolute left-[19px] top-5 bottom-5 w-px" style={{ background: 'var(--border)' }} />

          <div className="space-y-1.5">
            {page.map((e: Record<string, unknown>, i) => {
              const action = e.action as string
              const meta = ACTION_META[action]
              const seq = e.seq as number
              const hashOk = chainReport?.perEntryHashOk.get(seq)
              const linkBroken = chainReport?.brokenLinkages.some(b => b.atSeq === seq) ?? false
              const isExpanded = expanded.has(seq)
              const computedHash = computedHashes[seq]

              return (
                <div key={i} className="flex gap-3 group animate-fade" style={{ animationDelay: `${Math.min(i * 15, 200)}ms` }}>
                  {/* Chain node */}
                  <div className="relative z-10 shrink-0 w-10 flex items-start justify-center pt-4">
                    <div
                      className="w-4 h-4 rounded-full border-2 flex items-center justify-center text-[8px] font-bold font-mono transition-transform group-hover:scale-110"
                      style={{
                        borderColor:     meta?.color ?? '#546175',
                        backgroundColor: (meta?.color ?? '#546175') + '20',
                        color:           meta?.color ?? '#7e92b0',
                        boxShadow:       `0 0 8px ${(meta?.color ?? '#546175')}30`,
                      }}
                    >
                      {(e.seq as number) % 10}
                    </div>
                  </div>

                  {/* Entry card */}
                  <div
                    className="flex-1 rounded-xl px-4 py-3 transition-all duration-150 card-shadow"
                    style={{
                      background:   'var(--surface)',
                      border:       '1px solid var(--border)',
                    }}
                    onMouseEnter={ev => (ev.currentTarget.style.borderColor = 'var(--border2)')}
                    onMouseLeave={ev => (ev.currentTarget.style.borderColor = 'var(--border)')}
                  >
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <span className="text-[11px] font-mono w-7 shrink-0" style={{ color: 'var(--border3)' }}>
                        #{seq}
                      </span>

                      <Badge variant={meta?.variant ?? 'slate'}>
                        {action.replace(/_/g, ' ')}
                      </Badge>

                      {(e.result as string) === 'success'
                        ? <CheckCircle2 size={12} className="text-[var(--green)]" />
                        : <XCircle size={12} className="text-red-500" />}

                      {/* Chain verification badge */}
                      {hashOk === false && (
                        <Badge variant="red" dot>hash mismatch</Badge>
                      )}
                      {linkBroken && (
                        <Badge variant="amber" dot>chain break</Badge>
                      )}
                      {hashOk === true && !linkBroken && (
                        <Badge variant="green" dot>verified</Badge>
                      )}

                      <span className="text-[11px] font-mono" style={{ color: 'var(--muted2)' }}>
                        {e.actor as string}
                      </span>

                      <span className="text-[11px] font-mono ml-auto" style={{ color: 'var(--muted)' }}>
                        {(e.timestamp as string)?.replace('T', ' ').replace('Z', ' UTC')}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <p className="text-xs truncate flex-1 font-mono" style={{ color: 'var(--muted2)' }} title={e.target as string}>
                        <ChevronRight size={10} className="inline mr-1" style={{ color: 'var(--muted)' }} />
                        {e.target as string}
                      </p>
                      <Hash value={e.entry_hash as string} />
                    </div>

                    {(e.seq as number) > 0 && (
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <Link2 size={9} style={{ color: 'var(--border2)' }} />
                        <span className="text-[10px] font-mono" style={{ color: 'var(--border3)' }}>prev:</span>
                        <span className="text-[10px] font-mono" style={{ color: 'var(--border3)' }}>
                          {(e.prev_hash as string)?.slice(0, 18)}…
                        </span>

                        {/* Inspector toggle for broken entries */}
                        {hashOk === false && (
                          <button
                            onClick={() => {
                              const next = new Set(expanded)
                              if (next.has(seq)) next.delete(seq); else next.add(seq)
                              setExpanded(next)
                            }}
                            className="ml-auto inline-flex items-center gap-1 text-[10.5px] font-mono text-red-700 hover:text-red-900 font-semibold"
                          >
                            {isExpanded ? <><ChevronUp size={10} /> hide</> : <><ChevronDown size={10} /> inspect hash mismatch</>}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Hash mismatch inspector */}
                    {isExpanded && hashOk === false && computedHash && (
                      <div className="mt-2 p-2.5 rounded bg-red-50 border border-red-200">
                        <p className="text-[10px] font-bold text-[var(--red)] uppercase tracking-wider mb-1.5">Hash mismatch</p>
                        <div className="space-y-1 text-[10.5px] font-mono">
                          <div>
                            <span className="text-[var(--red)] font-semibold">declared: </span>
                            <span className="text-red-700 break-all">{e.entry_hash as string}</span>
                          </div>
                          <div>
                            <span className="text-[var(--red)] font-semibold">computed: </span>
                            <span className="text-red-700 break-all">{computedHash}</span>
                          </div>
                        </div>
                        <p className="text-[10.5px] text-[var(--red)] mt-1.5">
                          The declared entry_hash does not match the SHA-256 of the canonical fields.
                          This entry has been tampered with or the audit log has been corrupted.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center gap-3 pt-2">
          <button
            disabled={pageNum === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-30"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted2)' }}
            onMouseEnter={ev => !ev.currentTarget.disabled && (ev.currentTarget.style.borderColor = 'var(--border2)')}
            onMouseLeave={ev => (ev.currentTarget.style.borderColor = 'var(--border)')}
          >
            {t('audit.pagination.previous')}
          </button>
          <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>
            {t('audit.pagination.summary')
              .replace('{pageNum}', String(pageNum + 1))
              .replace('{pages}', String(pages))
              .replace('{total}', String(total))}
          </span>
          <button
            disabled={pageNum >= pages - 1}
            onClick={() => setOffset(offset + limit)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-30"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted2)' }}
            onMouseEnter={ev => !ev.currentTarget.disabled && (ev.currentTarget.style.borderColor = 'var(--border2)')}
            onMouseLeave={ev => (ev.currentTarget.style.borderColor = 'var(--border)')}
          >
            {t('audit.pagination.next')}
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Chain verification banner ───────────────────────────────────────────

function ChainVerifyBanner({
  verifying, report,
}: {
  verifying: boolean
  report: ChainVerifyReport | null
}) {
  const t = useT()
  if (verifying && !report) {
    return (
      <div className="rounded-md border border-[var(--border)] bg-white px-4 py-3 flex items-center gap-3 card-shadow">
        <Loader2 size={14} className="animate-spin text-[var(--accent)]" />
        <div className="text-[12.5px] text-[var(--muted2)]">
          {t('audit.verify.computing')}
        </div>
      </div>
    )
  }
  if (!report) return null

  const Icon = report.ok ? ShieldCheck : ShieldAlert
  const accentBg = report.ok ? 'bg-[var(--green-bg)]' : 'bg-red-50'
  const accentBorder = report.ok ? 'border-[var(--green)]' : 'border-red-200'
  const iconColor = report.ok ? 'text-[var(--green)]' : 'text-red-700'
  const titleColor = report.ok ? 'text-[var(--green)]' : 'text-[var(--red)]'

  return (
    <div className={`rounded-md border ${accentBorder} ${accentBg} px-4 py-3.5 card-shadow`}>
      <div className="flex items-start gap-3">
        <Icon size={18} className={`${iconColor} mt-0.5 shrink-0`} />
        <div className="flex-1 min-w-0">
          <p className={`text-[14px] font-bold ${titleColor} tracking-tight`}>
            {report.ok
              ? `Chain verified · ${report.total} entries · 0 breaks`
              : `Chain integrity FAILED · ${report.brokenHashEntries.length} hash mismatch, ${report.brokenLinkages.length} linkage break${report.brokenLinkages.length !== 1 ? 's' : ''}`}
          </p>
          <p className="text-[12px] text-[var(--muted2)] mt-1 leading-relaxed">
            {report.ok ? t('audit.verify.ok.body') : t('audit.verify.fail.body')}
          </p>
          {!report.ok && report.brokenLinkages.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-[11px] font-mono text-[var(--red)]">
              {report.brokenLinkages.slice(0, 5).map((b, i) => (
                <li key={i}>· seq {b.atSeq}: {b.reason}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
