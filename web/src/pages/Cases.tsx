import { useQuery } from '@tanstack/react-query'
import {
  FolderSearch, CheckCircle2, AlertCircle,
  HelpCircle, AlertTriangle, Clock, FileText, GitBranch,
} from 'lucide-react'
import { api, type CaseItem } from '../api/client'
import { Card, CardHeader, Badge, PageHeader, EmptyState, Skeleton, OfflineState } from '../components/ui'
import { useT } from '../i18n'
import type { TKey } from '../i18n/en'

type Conclusion = 'explained' | 'unexplained' | 'indeterminate' | 'contaminated'

// Labels removed — they now live in the i18n dictionary
// (cases.conclusion.<key>.label/body). The visual metadata stays here.
const CONCLUSION_META: Record<Conclusion, {
  labelKey: TKey
  bodyKey: TKey
  variant: 'green' | 'blue' | 'amber' | 'orange' | 'purple' | 'slate'
  Icon: React.ElementType
  bg: string
  border: string
  iconColor: string
}> = {
  explained: {
    labelKey: 'cases.conclusion.explained.label',
    bodyKey: 'cases.conclusion.explained.body',
    variant: 'green',
    Icon: CheckCircle2,
    bg: 'bg-[var(--green-bg)]',
    border: 'border-[var(--green)]',
    iconColor: 'text-[var(--green)]',
  },
  unexplained: {
    labelKey: 'cases.conclusion.unexplained.label',
    bodyKey: 'cases.conclusion.unexplained.body',
    variant: 'amber',
    Icon: AlertCircle,
    bg: 'bg-[var(--amber-bg)]',
    border: 'border-[var(--amber)]',
    iconColor: 'text-[var(--amber)]',
  },
  indeterminate: {
    labelKey: 'cases.conclusion.indeterminate.label',
    bodyKey: 'cases.conclusion.indeterminate.body',
    variant: 'blue',
    Icon: HelpCircle,
    bg: 'bg-[var(--blue-bg)]',
    border: 'border-[var(--blue)]',
    iconColor: 'text-[var(--blue)]',
  },
  contaminated: {
    labelKey: 'cases.conclusion.contaminated.label',
    bodyKey: 'cases.conclusion.contaminated.body',
    variant: 'orange',
    Icon: AlertTriangle,
    bg: 'bg-[var(--amber-bg)]',
    border: 'border-[var(--orange)]',
    iconColor: 'text-[var(--orange)]',
  },
}

const OPEN_META = {
  labelKey: 'cases.tile.open' as TKey,
  variant: 'purple' as const,
  Icon: FolderSearch,
  bg: 'bg-[var(--accent-bg)]',
  border: 'border-[var(--accent-line)]',
  iconColor: 'text-[var(--accent)]',
}

function conclusionMeta(c: string | null) {
  if (!c) return OPEN_META
  return CONCLUSION_META[c as Conclusion] ?? OPEN_META
}

function CaseCard({ item }: { item: CaseItem }) {
  const t = useT()
  const meta = conclusionMeta(item.conclusion)
  const Icon = meta.Icon
  const date = item.updated_at ?? item.created_at

  return (
    <div className={`bg-[var(--surface)] border rounded-xl p-5 hover:border-[var(--border2)] transition-colors group ${meta.border}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className={`w-10 h-10 rounded-xl border flex items-center justify-center shrink-0 ${meta.bg} ${meta.border}`}>
          <Icon size={16} className={meta.iconColor} />
        </div>
        <Badge variant={meta.variant}>{t(meta.labelKey)}</Badge>
      </div>

      {/* ID */}
      <p className="text-sm font-mono text-[var(--text)] truncate mb-1">{item.id}</p>
      {item.description && (
        <p className="text-xs text-[var(--muted)] mb-3 truncate">{item.description}</p>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-3 text-[11px] text-[var(--muted2)] font-mono mt-3 pt-3 border-t border-[var(--border)]">
        <span className="flex items-center gap-1">
          <FileText size={10} className="text-[var(--text2)]" />
          {item.evidence_count} artefacto{item.evidence_count !== 1 ? 's' : ''}
        </span>
        {item.has_timeline && (
          <span className="flex items-center gap-1">
            <GitBranch size={10} className="text-[var(--text2)]" />
            {item.timeline_count} timeline{item.timeline_count !== 1 ? 's' : ''}
          </span>
        )}
        {date && (
          <span className="flex items-center gap-1 ml-auto">
            <Clock size={10} className="text-[var(--text2)]" />
            {date.slice(0, 10)}
          </span>
        )}
      </div>
    </div>
  )
}

const STATUS_COUNTS = ['open', 'explained', 'unexplained', 'indeterminate', 'contaminated'] as const
type FilterStatus = typeof STATUS_COUNTS[number]

function statusOf(item: CaseItem): FilterStatus {
  if (!item.conclusion) return 'open'
  return (item.conclusion as FilterStatus) ?? 'open'
}

export default function Cases() {
  const t = useT()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cases'],
    queryFn: api.listCases,
  })

  const counts = {
    open:          (data ?? []).filter(c => !c.conclusion).length,
    explained:     (data ?? []).filter(c => c.conclusion === 'explained').length,
    unexplained:   (data ?? []).filter(c => c.conclusion === 'unexplained').length,
    indeterminate: (data ?? []).filter(c => c.conclusion === 'indeterminate').length,
    contaminated:  (data ?? []).filter(c => c.conclusion === 'contaminated').length,
  }

  const total = data?.length ?? 0

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('cases.title')}
        description={t('cases.description')}
      />

      {/* Status summary tiles */}
      {!isLoading && total > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {([
            ['open',          t('cases.tile.open'),          'text-[var(--accent)]',  OPEN_META],
            ['explained',     t('cases.tile.explained'),     'text-[var(--green)]', CONCLUSION_META.explained],
            ['unexplained',   t('cases.tile.unexplained'),   'text-[var(--amber)]',   CONCLUSION_META.unexplained],
            ['indeterminate', t('cases.tile.indeterminate'), 'text-[var(--blue)]',    CONCLUSION_META.indeterminate],
            ['contaminated',  t('cases.tile.contaminated'),  'text-[var(--orange)]',  CONCLUSION_META.contaminated],
          ] as const).map(([key, label, color, meta]) => {
            const n = counts[key as FilterStatus]
            if (key !== 'open' && n === 0) return null
            const Icon = meta.Icon
            return (
              <div key={key} className={`bg-[var(--surface)] border rounded-xl p-4 ${meta.border}`}>
                <div className={`w-7 h-7 rounded-lg border flex items-center justify-center mb-2 ${meta.bg} ${meta.border}`}>
                  <Icon size={13} className={meta.iconColor} />
                </div>
                <p className={`text-xl font-bold ${color}`}>{n}</p>
                <p className="text-[11px] text-[var(--muted)] mt-0.5">{label}</p>
              </div>
            )
          })}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 space-y-3">
              <Skeleton className="h-10 w-10 rounded-xl" />
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-2.5 w-28" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <OfflineState
          title={t('cases.error')}
          body="Las investigaciones (workspaces, timelines, snapshots, justifications) viven en el archive AIP local del operador. En el deploy público no hay archive; arranca el backend para verlas."
        />
      )}

      {!isLoading && total === 0 && (
        <EmptyState
          icon={<FolderSearch size={20} />}
          title={t('cases.empty.title')}
          description={t('cases.empty.body')}
        />
      )}

      {/* Grid */}
      {!isLoading && total > 0 && (
        <>
          {/* Open cases */}
          {counts.open > 0 && (
            <section className="space-y-2">
              <h2 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider flex items-center gap-2">
                <FolderSearch size={11} /> {t('cases.group.open')}
                <span className="font-mono normal-case text-[var(--accent)]">{counts.open}</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(data ?? []).filter(c => statusOf(c) === 'open').map(item => (
                  <CaseCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          )}

          {/* Closed cases (have a conclusion) */}
          {(counts.explained + counts.unexplained + counts.indeterminate + counts.contaminated) > 0 && (
            <section className="space-y-2">
              <h2 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider flex items-center gap-2">
                <CheckCircle2 size={11} /> {t('cases.group.closed')}
                <span className="font-mono normal-case text-[var(--muted3)]">
                  {counts.explained + counts.unexplained + counts.indeterminate + counts.contaminated}
                </span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(data ?? []).filter(c => statusOf(c) !== 'open').map(item => (
                  <CaseCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Explainer */}
      <Card>
        <CardHeader title={t('cases.about.title')} />
        <div className="px-5 pb-5 space-y-3 text-xs text-[var(--muted3)] leading-relaxed">
          <p>{t('cases.about.body')}</p>
          <div className="grid grid-cols-2 gap-3 mt-3">
            {Object.entries(CONCLUSION_META).map(([key, m]) => {
              const Icon = m.Icon
              return (
                <div key={key} className={`flex items-start gap-2 p-3 rounded-lg border ${m.bg} ${m.border}`}>
                  <Icon size={13} className={`${m.iconColor} mt-0.5 shrink-0`} />
                  <div>
                    <p className="font-medium text-[var(--text)]">{t(m.labelKey)}</p>
                    <p className="text-[11px] text-[var(--muted)] mt-0.5">{t(m.bodyKey)}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </Card>
    </div>
  )
}
