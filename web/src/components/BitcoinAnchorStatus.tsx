import { useQueries } from '@tanstack/react-query'
import { Anchor, Clock, MinusCircle } from 'lucide-react'
import { api, type NotarizationStatus } from '../api/client'
import { useT } from '../i18n'

/**
 * For each transparency manifest, fetch and render its OpenTimestamps /
 * Bitcoin anchor status.
 *
 * Three states per manifest:
 *
 *   - "anchored":  OTS proof was upgraded and now carries a Bitcoin
 *                  block-header attestation. The browser-side report
 *                  verifier in `aip.report.builder` will recompute the
 *                  merkle root against the embedded block header.
 *   - "pending":   OTS proof exists but Bitcoin has not yet processed
 *                  the OpenTimestamps calendar batch. Operator should
 *                  run `aip notarize upgrade` in ~1h.
 *   - "absent":    No .ots file at all. Operator never ran
 *                  `aip notarize submit` on this manifest.
 *
 * No backend filesystem trust: every status comes from `/transparency/
 * notarization/{seq}` which is the reference implementation's own
 * read-only walk of the OTS proof tree.
 */

interface Props {
  manifestCount: number
}

export function BitcoinAnchorStatus({ manifestCount }: Props) {
  const t = useT()
  const sequences = Array.from({ length: manifestCount }, (_, i) => i)

  const queries = useQueries({
    queries: sequences.map(seq => ({
      queryKey: ['transparency-notarization', seq],
      queryFn: () => api.transparencyNotarization(seq),
    })),
  })

  if (manifestCount === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-5 py-4 text-[12.5px] text-slate-600">
        No manifests yet — publish one with{' '}
        <code className="bg-white px-1 rounded">aip transparency publish</code>.
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <table className="w-full text-[12.5px]">
        <thead className="bg-slate-50 text-[11px] uppercase tracking-wider font-semibold text-slate-600">
          <tr>
            <th className="text-left px-4 py-2">{t('dashboard.ots.headers.sequence')}</th>
            <th className="text-left px-4 py-2">{t('dashboard.ots.headers.status')}</th>
            <th className="text-left px-4 py-2">{t('dashboard.ots.headers.details')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sequences.map((seq, i) => (
            <Row key={seq} seq={seq} status={queries[i].data ?? null} loading={queries[i].isLoading} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Row({
  seq,
  status,
  loading,
}: {
  seq: number
  status: NotarizationStatus | null
  loading: boolean
}) {
  const t = useT()

  if (loading) {
    return (
      <tr>
        <td className="px-4 py-2.5 font-mono text-slate-500">#{seq.toString().padStart(6, '0')}</td>
        <td className="px-4 py-2.5" colSpan={2}>
          <div className="h-3 bg-slate-100 rounded w-32 animate-pulse" />
        </td>
      </tr>
    )
  }

  // No .ots file at all → "absent"
  if (status === null) {
    return (
      <tr>
        <td className="px-4 py-2.5 font-mono text-slate-500">#{seq.toString().padStart(6, '0')}</td>
        <td className="px-4 py-2.5">
          <StatusPill tone="slate" icon={MinusCircle} label={t('dashboard.ots.status.absent')} />
        </td>
        <td className="px-4 py-2.5 text-slate-500 text-[11.5px]">
          {t('dashboard.ots.details.absent')}
        </td>
      </tr>
    )
  }

  // Has Bitcoin attestation → "anchored"
  if (status.bitcoin_anchors.length > 0) {
    const heights = Array.from(new Set(status.bitcoin_anchors.map(b => b.height)))
    return (
      <tr>
        <td className="px-4 py-2.5 font-mono text-slate-500">#{seq.toString().padStart(6, '0')}</td>
        <td className="px-4 py-2.5">
          <StatusPill tone="green" icon={Anchor} label={t('dashboard.ots.status.anchored')} />
        </td>
        <td className="px-4 py-2.5 text-slate-700 text-[11.5px] font-mono">
          {heights
            .map(h => t('dashboard.ots.details.anchored').replace('{height}', String(h)))
            .join(', ')}
        </td>
      </tr>
    )
  }

  // OTS exists but no Bitcoin yet → "pending"
  return (
    <tr>
      <td className="px-4 py-2.5 font-mono text-slate-500">#{seq.toString().padStart(6, '0')}</td>
      <td className="px-4 py-2.5">
        <StatusPill tone="amber" icon={Clock} label={t('dashboard.ots.status.pending')} />
      </td>
      <td className="px-4 py-2.5 text-amber-700 text-[11.5px]">
        {t('dashboard.ots.details.pending').replace('{n}', String(status.pending_count))}
      </td>
    </tr>
  )
}

function StatusPill({
  tone,
  icon: Icon,
  label,
}: {
  tone: 'green' | 'amber' | 'slate'
  icon: typeof Anchor
  label: string
}) {
  const styles: Record<string, string> = {
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold uppercase tracking-wider border ${styles[tone]}`}
    >
      <Icon size={11} strokeWidth={2} />
      {label}
    </span>
  )
}
