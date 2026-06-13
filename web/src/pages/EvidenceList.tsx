import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, Search, ArrowRight, Filter, Grid3X3, List } from 'lucide-react'
import { api } from '../api/client'
import { Card, Hash, Badge, PageHeader, EmptyState, Skeleton } from '../components/ui'
import { useT } from '../i18n'

const KIND_COLOR: Record<string, 'green' | 'blue' | 'purple' | 'amber' | 'orange' | 'slate'> = {
  document_text:        'green',
  document_scan:        'blue',
  still_image:          'purple',
  moving_image:         'amber',
  audio_recording:      'amber',
  sensor_log:           'blue',
  dataset_table:        'green',
  code_or_model:        'purple',
  correspondence:       'green',
  interview_transcript: 'blue',
  radar_return:         'orange',
  telemetry:            'orange',
  video_footage:        'amber',
  witness_statement:    'blue',
  physical_sample:      'purple',
  spectral_data:        'orange',
  geospatial:           'green',
  medical_record:       'slate',
}

const KIND_ICON: Record<string, string> = {
  document_text:        '📄',
  document_scan:        '🖨️',
  still_image:          '🖼️',
  moving_image:         '🎬',
  audio_recording:      '🎙️',
  sensor_log:           '📡',
  dataset_table:        '📊',
  code_or_model:        '💻',
  correspondence:       '✉️',
  interview_transcript: '💬',
  radar_return:         '📡',
  telemetry:            '🛰️',
  video_footage:        '🎥',
  witness_statement:    '🗣️',
  physical_sample:      '🧪',
  spectral_data:        '🌈',
  geospatial:           '🗺️',
  medical_record:       '🏥',
}

// Technical taxonomy labels — kept English-only because they're a stable
// vocabulary close to the canonical ingest API kinds. Operators in either
// language read the same controlled identifiers.
const KIND_LABEL: Record<string, string> = {
  document_text:        'Text document',
  document_scan:        'Document scan',
  still_image:          'Still image',
  moving_image:         'Moving image',
  audio_recording:      'Audio recording',
  sensor_log:           'Sensor log',
  dataset_table:        'Tabular dataset',
  code_or_model:        'Code / model',
  correspondence:       'Correspondence',
  interview_transcript: 'Interview transcript',
  radar_return:         'Radar return',
  telemetry:            'Telemetry',
  video_footage:        'Video footage',
  witness_statement:    'Witness statement',
  physical_sample:      'Physical sample',
  spectral_data:        'Spectral data',
  geospatial:           'Geospatial data',
  medical_record:       'Medical record',
}

export default function EvidenceList() {
  const t = useT()
  const [search, setSearch]       = useState('')
  const [viewMode, setViewMode]   = useState<'list' | 'grid'>('list')
  const [filterKind, setFilterKind] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['evidence-list'],
    queryFn: api.listEvidence,
  })

  const presentKinds = [...new Set((data ?? []).map(e => e.kind).filter(Boolean))]

  const filtered = (data ?? []).filter(e => {
    if (filterKind && e.kind !== filterKind) return false
    if (!search) return true
    const q = search.toLowerCase()
    return (
      e.hash.includes(q) ||
      e.kind?.toLowerCase().includes(q) ||
      e.mime_type?.toLowerCase().includes(q) ||
      e.ingested_by?.toLowerCase().includes(q) ||
      e.source_id?.toLowerCase().includes(q)
    )
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('evidence.list.title')}
        description={t('evidence.list.description')}
      />

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('evidence.list.searchPlaceholder')}
            className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-lg pl-9 pr-4 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-violet-500 transition-colors"
          />
        </div>
        <div className="flex items-center gap-1 bg-[var(--surface)] border border-[var(--border)] rounded-lg p-1">
          <button
            onClick={() => setViewMode('list')}
            className={`p-1.5 rounded transition-colors ${viewMode === 'list' ? 'bg-violet-100 text-violet-700' : 'text-slate-500 hover:text-slate-700'}`}
          ><List size={14} /></button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-1.5 rounded transition-colors ${viewMode === 'grid' ? 'bg-violet-100 text-violet-700' : 'text-slate-500 hover:text-slate-700'}`}
          ><Grid3X3 size={14} /></button>
        </div>
      </div>

      {/* Kind filter pills */}
      {!isLoading && presentKinds.length > 1 && (
        <div className="flex flex-wrap gap-2 items-center">
          <Filter size={12} className="text-slate-500" />
          <button
            onClick={() => setFilterKind(null)}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              !filterKind
                ? 'bg-violet-100 border-violet-400 text-violet-700'
                : 'border-[var(--border)] text-slate-500 hover:text-slate-700 hover:border-[var(--border2)]'
            }`}
          >
            {t('evidence.list.filter.all')} ({data?.length ?? 0})
          </button>
          {presentKinds.map(kind => {
            const count = (data ?? []).filter(e => e.kind === kind).length
            return (
              <button
                key={kind}
                onClick={() => setFilterKind(kind)}
                className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                  filterKind === kind
                    ? 'bg-violet-100 border-violet-400 text-violet-700'
                    : 'border-[var(--border)] text-slate-500 hover:text-slate-700 hover:border-[var(--border2)]'
                }`}
              >
                {KIND_ICON[kind] ?? '📁'} {KIND_LABEL[kind] ?? kind.replace(/_/g, ' ')} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Count */}
      {!isLoading && (
        <p className="text-xs text-slate-500">
          {t('evidence.list.countLine')
            .replace('{filtered}', String(filtered.length))
            .replace('{total}', String(data?.length ?? 0))}
          {search && ` · ${t('evidence.list.count.matching')} "${search}"`}
          {filterKind && ` · ${t('evidence.list.count.kind')} ${KIND_LABEL[filterKind] ?? filterKind}`}
        </p>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 space-y-2">
              <Skeleton className="h-3 w-48" />
              <Skeleton className="h-2.5 w-80" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="bg-red-50 border border-red-300 rounded-xl p-4 text-sm text-red-700">
          {t('evidence.list.error')}
        </div>
      )}

      {/* Empty */}
      {!isLoading && filtered.length === 0 && (
        <EmptyState
          icon={<FileText size={20} />}
          title={search || filterKind ? t('evidence.list.empty.noResults.title') : t('evidence.list.empty.none.title')}
          description={search || filterKind ? t('evidence.list.empty.noResults.body') : t('evidence.list.empty.none.body')}
        />
      )}

      {/* List view */}
      {!isLoading && filtered.length > 0 && viewMode === 'list' && (
        <Card>
          <div className="divide-y divide-[#1e2535]">
            {filtered.map((e) => (
              <Link
                key={e.hash}
                to={`/evidence/${e.hash}`}
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors group"
              >
                <div className="w-9 h-9 rounded-lg bg-[var(--surface2)] border border-[var(--border)] flex items-center justify-center text-base shrink-0">
                  {KIND_ICON[e.kind] ?? '📁'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Hash value={e.hash} />
                    <Badge variant={KIND_COLOR[e.kind] ?? 'slate'}>
                      {KIND_LABEL[e.kind] ?? e.kind?.replace(/_/g, ' ')}
                    </Badge>
                    <span className="text-[11px] text-slate-600">{e.mime_type}</span>
                  </div>
                  <div className="flex gap-3 text-[11px] text-slate-500 font-mono">
                    <span>{e.ingested_by}</span>
                    <span>·</span>
                    <span>{e.ingested_at?.slice(0, 10)}</span>
                    <span>·</span>
                    <span>{(e.size_bytes / 1024).toFixed(1)} KB</span>
                    {e.source_id && <><span>·</span><span>{e.source_id}</span></>}
                  </div>
                </div>
                <ArrowRight size={13} className="text-slate-700 group-hover:text-violet-500 transition-colors shrink-0" />
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* Grid view */}
      {!isLoading && filtered.length > 0 && viewMode === 'grid' && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {filtered.map((e) => (
            <Link
              key={e.hash}
              to={`/evidence/${e.hash}`}
              className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 hover:border-[var(--border2)] transition-colors group"
            >
              <div className="text-2xl mb-3">{KIND_ICON[e.kind] ?? '📁'}</div>
              <div className="mb-2">
                <Badge variant={KIND_COLOR[e.kind] ?? 'slate'}>
                  {KIND_LABEL[e.kind] ?? e.kind?.replace(/_/g, ' ')}
                </Badge>
              </div>
              <Hash value={e.hash} />
              <p className="text-[11px] text-slate-500 mt-2 font-mono">
                {(e.size_bytes / 1024).toFixed(1)} KB · {e.ingested_at?.slice(0, 10)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
