import { useQuery } from '@tanstack/react-query'
import {
  Layers, FolderOpen, Clock, Camera, BookOpen,
  ArrowRight, CheckCircle2, AlertCircle,
  HelpCircle, AlertTriangle, FileText,
} from 'lucide-react'
import { api } from '../api/client'
import { Card, CardHeader, Badge, PageHeader, EmptyState } from '../components/ui'
import { useT } from '../i18n'
import type { TKey } from '../i18n/en'

// ─── Conclusion badge ─────────────────────────────────────────────────────
// Labels live in the i18n dictionary (reused from cases.conclusion.*).

const CONCLUSION_META: Record<string, {
  labelKey: TKey
  variant: 'green' | 'blue' | 'amber' | 'orange' | 'slate'
  Icon: React.ElementType
}> = {
  explained:     { labelKey: 'cases.conclusion.explained.label',     variant: 'green',  Icon: CheckCircle2 },
  unexplained:   { labelKey: 'cases.conclusion.unexplained.label',   variant: 'amber',  Icon: AlertCircle },
  indeterminate: { labelKey: 'cases.conclusion.indeterminate.label', variant: 'blue',   Icon: HelpCircle },
  contaminated:  { labelKey: 'cases.conclusion.contaminated.label',  variant: 'orange', Icon: AlertTriangle },
}

function ConclusionBadge({ value }: { value: string | null | undefined }) {
  const t = useT()
  if (!value) return null
  const m = CONCLUSION_META[value]
  if (!m) return <Badge variant="slate">{value}</Badge>
  const Icon = m.Icon
  return (
    <Badge variant={m.variant}>
      <Icon size={10} className="mr-0.5" />
      {t(m.labelKey)}
    </Badge>
  )
}

// ─── Layer stack diagram ──────────────────────────────────────────────────

const LAYERS: Array<{
  key: string
  labelKey: TKey
  descKey: TKey
  icon: React.ElementType
  color: string
  bg: string
}> = [
  { key: 'justifications', labelKey: 'derived.layers.justification.label', descKey: 'derived.layers.justification.desc', icon: BookOpen,    color: 'text-amber-700',   bg: 'bg-amber-50 border-amber-200' },
  { key: 'snapshots',      labelKey: 'derived.layers.snapshot.label',      descKey: 'derived.layers.snapshot.desc',      icon: Camera,      color: 'text-indigo-700',  bg: 'bg-indigo-50 border-indigo-200' },
  { key: 'timelines',      labelKey: 'derived.layers.timeline.label',      descKey: 'derived.layers.timeline.desc',      icon: Clock,       color: 'text-blue-700',    bg: 'bg-blue-50 border-blue-200' },
  { key: 'workspaces',     labelKey: 'derived.layers.workspace.label',     descKey: 'derived.layers.workspace.desc',     icon: FolderOpen,  color: 'text-violet-700',  bg: 'bg-violet-50 border-violet-200' },
  { key: '_base',          labelKey: 'derived.layers.base.label',          descKey: 'derived.layers.base.desc',          icon: FileText,    color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
]

function LayerStack({ counts }: { counts: Record<string, number> }) {
  const t = useT()
  return (
    <div className="flex flex-col gap-1 items-center w-full max-w-sm mx-auto py-2">
      {LAYERS.map((l, i) => {
        const Icon = l.icon
        const n = l.key === '_base' ? null : counts[l.key]
        return (
          <div key={l.key} className="w-full flex flex-col items-center">
            <div className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border ${l.bg}`}
              style={{ maxWidth: `${100 - i * 8}%` }}>
              <Icon size={14} className={l.color} />
              <div className="flex-1">
                <span className={`text-xs font-semibold ${l.color}`}>{t(l.labelKey)}</span>
                <span className="text-[11px] text-slate-500 ml-2">{t(l.descKey)}</span>
              </div>
              {n !== null && (
                <span className="text-[11px] font-mono text-slate-500">{n}</span>
              )}
            </div>
            {i < LAYERS.length - 1 && (
              <div className="w-px h-3 bg-[#1e2535]" />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── CLI reference ────────────────────────────────────────────────────────

const CLI_COMMANDS: Array<{ labelKey: TKey; cmd: string }> = [
  { labelKey: 'derived.cli.createWorkspace',   cmd: 'aip workspace create --label "Case #001"' },
  { labelKey: 'derived.cli.buildTimeline',     cmd: 'aip timeline build  --workspace-id <ws-id>' },
  { labelKey: 'derived.cli.freezeSnapshot',    cmd: 'aip snapshot create --workspace-id <ws-id> --timeline-id <tl-id>' },
  { labelKey: 'derived.cli.addJustification',  cmd: 'aip justification declare --workspace-id <ws-id> --conclusion unexplained' },
]

// ─── Section items ────────────────────────────────────────────────────────

type DerivedItem = { id: string; [k: string]: unknown }

function WorkspaceRow({ item }: { item: DerivedItem }) {
  const t = useT()
  const refs = (item.artifact_refs as string[] | undefined) ?? []
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <div className="w-8 h-8 rounded-lg border bg-violet-50 border-violet-200 flex items-center justify-center shrink-0">
        <FolderOpen size={13} className="text-violet-700" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-800 font-mono truncate">{item.id}</p>
        <div className="flex flex-wrap gap-3 mt-0.5 text-[11px] text-slate-500 font-mono">
          {refs.length > 0 && <span>{refs.length} {t('derived.row.artefacts')}</span>}
          {(item.generated_at || item.created_at) && (
            <span>{String(item.generated_at ?? item.created_at).slice(0, 10)}</span>
          )}
          {item.description && <span className="truncate max-w-xs">{String(item.description)}</span>}
        </div>
      </div>
      <a href={`/api/workspaces/${item.id}`} target="_blank" rel="noreferrer"
        className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-violet-700 transition-colors">
        JSON <ArrowRight size={10} />
      </a>
    </div>
  )
}

function TimelineRow({ item }: { item: DerivedItem }) {
  const events = (item.events as unknown[] | undefined) ?? []
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <div className="w-8 h-8 rounded-lg border bg-blue-50 border-blue-200 flex items-center justify-center shrink-0">
        <Clock size={13} className="text-blue-700" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-800 font-mono truncate">{item.id}</p>
        <div className="flex flex-wrap gap-3 mt-0.5 text-[11px] text-slate-500 font-mono">
          {events.length > 0 && <span>{events.length} evento{events.length !== 1 ? 's' : ''}</span>}
          {item.workspace_id && <span>ws: {String(item.workspace_id).slice(0, 16)}…</span>}
          {(item.generated_at || item.created_at) && (
            <span>{String(item.generated_at ?? item.created_at).slice(0, 10)}</span>
          )}
        </div>
      </div>
      <a href={`/api/timelines/${item.id}`} target="_blank" rel="noreferrer"
        className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-violet-700 transition-colors">
        JSON <ArrowRight size={10} />
      </a>
    </div>
  )
}

function SnapshotRow({ item }: { item: DerivedItem }) {
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <div className="w-8 h-8 rounded-lg border bg-indigo-50 border-indigo-200 flex items-center justify-center shrink-0">
        <Camera size={13} className="text-indigo-700" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-800 font-mono truncate">{item.id}</p>
        <div className="flex flex-wrap gap-3 mt-0.5 text-[11px] text-slate-500 font-mono">
          {item.workspace_id && <span>ws: {String(item.workspace_id).slice(0, 12)}…</span>}
          {item.timeline_id  && <span>tl: {String(item.timeline_id).slice(0, 12)}…</span>}
          {(item.generated_at || item.created_at) && (
            <span>{String(item.generated_at ?? item.created_at).slice(0, 10)}</span>
          )}
        </div>
      </div>
      <a href={`/api/snapshots/${item.id}`} target="_blank" rel="noreferrer"
        className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-violet-700 transition-colors">
        JSON <ArrowRight size={10} />
      </a>
    </div>
  )
}

function JustificationRow({ item }: { item: DerivedItem }) {
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <div className="w-8 h-8 rounded-lg border bg-amber-50 border-amber-200 flex items-center justify-center shrink-0">
        <BookOpen size={13} className="text-amber-700" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-sm text-slate-800 font-mono truncate">{item.id}</p>
          <ConclusionBadge value={item.conclusion as string | null} />
        </div>
        <div className="flex flex-wrap gap-3 mt-0.5 text-[11px] text-slate-500 font-mono">
          {item.workspace_id && <span>ws: {String(item.workspace_id).slice(0, 16)}…</span>}
          {(item.generated_at || item.created_at) && (
            <span>{String(item.generated_at ?? item.created_at).slice(0, 10)}</span>
          )}
        </div>
      </div>
      <a href={`/api/justifications/${item.id}`} target="_blank" rel="noreferrer"
        className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-violet-700 transition-colors">
        JSON <ArrowRight size={10} />
      </a>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────

export default function Derived() {
  const t = useT()
  const workspaces     = useQuery({ queryKey: ['workspaces'],     queryFn: api.listWorkspaces })
  const timelines      = useQuery({ queryKey: ['timelines'],      queryFn: api.listTimelines })
  const snapshots      = useQuery({ queryKey: ['snapshots'],      queryFn: api.listSnapshots })
  const justifications = useQuery({ queryKey: ['justifications'], queryFn: api.listJustifications })

  const ws   = workspaces.data     ?? []
  const tl   = timelines.data      ?? []
  const sn   = snapshots.data      ?? []
  const just = justifications.data ?? []

  const total   = ws.length + tl.length + sn.length + just.length
  const loading = [workspaces, timelines, snapshots, justifications].some(q => q.isLoading)

  const counts = {
    workspaces:     ws.length,
    timelines:      tl.length,
    snapshots:      sn.length,
    justifications: just.length,
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('derived.title')}
        description={t('derived.description')}
      />

      {/* Layer stack + CLI side-by-side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Layer pyramid */}
        <Card>
          <CardHeader title={t('derived.layers.title')} sub={t('derived.layers.subtitle')} />
          <div className="px-5 pb-5">
            <LayerStack counts={counts} />
          </div>
        </Card>

        {/* CLI quick-reference */}
        <Card>
          <CardHeader title={t('derived.cli.title')} sub={t('derived.cli.subtitle')} />
          <div className="divide-y divide-[#1e2535]">
            {CLI_COMMANDS.map(({ labelKey, cmd }) => (
              <div key={labelKey} className="px-5 py-3">
                <p className="text-[11px] text-slate-500 mb-1">{t(labelKey)}</p>
                <code className="text-[11px] font-mono text-violet-700 bg-violet-50 px-2 py-1 rounded block overflow-x-auto">
                  {cmd}
                </code>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Empty state global */}
      {!loading && total === 0 && (
        <EmptyState
          icon={<Layers size={20} />}
          title={t('derived.empty.title')}
          description={t('derived.empty.body')}
        />
      )}

      {/* ── Workspaces ── */}
      {ws.length > 0 && (
        <Card>
          <CardHeader
            title="Workspaces"
            sub={t('derived.section.workspaces.sub').replace('{n}', String(ws.length))}
            action={<Badge variant="purple">{ws.length}</Badge>}
          />
          <div className="divide-y divide-[#1e2535]">
            {ws.map(item => <WorkspaceRow key={item.id} item={item as DerivedItem} />)}
          </div>
        </Card>
      )}

      {/* ── Timelines ── */}
      {tl.length > 0 && (
        <Card>
          <CardHeader
            title="Timelines"
            sub={t('derived.section.timelines.sub').replace('{n}', String(tl.length))}
            action={<Badge variant="blue">{tl.length}</Badge>}
          />
          <div className="divide-y divide-[#1e2535]">
            {tl.map(item => <TimelineRow key={item.id} item={item as DerivedItem} />)}
          </div>
        </Card>
      )}

      {/* ── Snapshots ── */}
      {sn.length > 0 && (
        <Card>
          <CardHeader
            title="Snapshots"
            sub={t('derived.section.snapshots.sub').replace('{n}', String(sn.length))}
            action={<Badge variant="blue">{sn.length}</Badge>}
          />
          <div className="divide-y divide-[#1e2535]">
            {sn.map(item => <SnapshotRow key={item.id} item={item as DerivedItem} />)}
          </div>
        </Card>
      )}

      {/* ── Justifications ── */}
      {just.length > 0 && (
        <Card>
          <CardHeader
            title="Justifications"
            sub={t('derived.section.justifications.sub').replace('{n}', String(just.length))}
            action={<Badge variant="amber">{just.length}</Badge>}
          />
          <div className="divide-y divide-[#1e2535]">
            {just.map(item => <JustificationRow key={item.id} item={item as DerivedItem} />)}
          </div>
        </Card>
      )}

      {/* Per-section empty prompts (only when archive has some data but layer is empty) */}
      {!loading && total === 0 && null}
      {!loading && total > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {[
            { show: ws.length === 0,   icon: FolderOpen, color: 'text-violet-700', title: 'Sin workspaces',    cmd: 'aip workspace create' },
            { show: tl.length === 0,   icon: Clock,      color: 'text-blue-700',   title: 'Sin timelines',     cmd: 'aip timeline build --workspace-id <id>' },
            { show: sn.length === 0,   icon: Camera,     color: 'text-indigo-700', title: 'Sin snapshots',     cmd: 'aip snapshot create --workspace-id <id> --timeline-id <id>' },
            { show: just.length === 0, icon: BookOpen,   color: 'text-amber-700',  title: 'Sin justificaciones', cmd: 'aip justification declare --workspace-id <id> --conclusion unexplained' },
          ].filter(s => s.show).map(({ icon: Icon, color, title, cmd }) => (
            <div key={title} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 flex items-start gap-3">
              <Icon size={14} className={`${color} mt-0.5 shrink-0`} />
              <div>
                <p className="text-xs text-slate-400 font-medium mb-1">{title}</p>
                <code className="text-[10px] font-mono text-slate-600">{cmd}</code>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
