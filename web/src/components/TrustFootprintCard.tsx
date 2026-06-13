import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, AlertCircle, ExternalLink, Key } from 'lucide-react'
import { api, type KeyDeclarationResponse, type ExternalReference } from '../api/client'
import { useT } from '../i18n'

// Display the operator's key declaration (ADR-0043) plus consistency
// report. Two audiences share this component:
//
//   - "operator": the person running the archive — sees how to fix gaps.
//   - "recipient": the verifier — sees how to cross-check externally.
//
// Both share the same dictionary; the audience adjustment is per-block
// (different intro text, different CTA flavour).

type Audience = 'operator' | 'recipient'

export function TrustFootprintCard({ audience }: { audience: Audience }) {
  const t = useT()
  const q = useQuery({
    queryKey: ['transparency-key-declaration'],
    queryFn: api.transparencyKeyDeclaration,
  })

  if (q.isLoading) {
    return <SkeletonCard />
  }
  if (q.error || !q.data) {
    return <ErrorCard message={t('trust.error')} />
  }

  const { declaration, consistency } = q.data

  // ── State 1: no declaration ──
  if (!consistency.declaration_present || !declaration) {
    return <NoDeclarationCard audience={audience} />
  }

  // ── State 2/3: declaration present, consistent or not ──
  return (
    <DeclarationCard
      audience={audience}
      data={q.data}
    />
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────

function CardShell({
  tone,
  children,
}: {
  tone: 'ok' | 'warn' | 'fail'
  children: React.ReactNode
}) {
  const border =
    tone === 'ok' ? 'border-emerald-200' :
    tone === 'warn' ? 'border-amber-200' :
    'border-red-200'
  const bg =
    tone === 'ok' ? 'bg-emerald-50' :
    tone === 'warn' ? 'bg-amber-50' :
    'bg-red-50'
  return (
    <div className={`rounded-lg border ${border} ${bg}`}>
      {children}
    </div>
  )
}

function StatusHeader({
  tone,
  icon: Icon,
  title,
  subtitle,
}: {
  tone: 'ok' | 'warn' | 'fail'
  icon: typeof ShieldCheck
  title: string
  subtitle: string
}) {
  const color =
    tone === 'ok' ? 'text-emerald-700' :
    tone === 'warn' ? 'text-amber-700' :
    'text-red-700'
  return (
    <div className="flex items-start gap-3 px-5 py-4 border-b border-current/10">
      <Icon size={20} strokeWidth={1.75} className={color} />
      <div className="min-w-0 flex-1">
        <h3 className={`text-[13.5px] font-bold tracking-tight ${color}`}>
          {title}
        </h3>
        <p className={`text-[12px] mt-0.5 leading-snug ${color} opacity-80`}>
          {subtitle}
        </p>
      </div>
    </div>
  )
}

function NoDeclarationCard({ audience }: { audience: Audience }) {
  const t = useT()
  const body = audience === 'operator'
    ? (
      <>
        <p className="mb-3">
          {t('trust.absent.operator.intro')}{' '}
          <code className="text-[11.5px] bg-white/60 px-1 rounded">key-declaration.json</code>
          {t('trust.absent.operator.body')}
        </p>
        <p className="font-semibold mb-1">{t('trust.absent.operator.howto')}</p>
        <pre className="text-[11.5px] bg-white/60 border border-amber-200 rounded p-3 overflow-x-auto leading-snug">
{`aip transparency declare-key init --operator-id <YOU>
aip transparency declare-key add-reference \\
  --kind github_user_keys \\
  --uri https://github.com/<you>.keys`}
        </pre>
      </>
    )
    : (
      <p>
        {t('trust.absent.recipient.body')}{' '}
        <strong>{t('trust.absent.recipient.bodyEmphasis')}</strong>.
      </p>
    )

  return (
    <CardShell tone="warn">
      <StatusHeader
        tone="warn"
        icon={ShieldAlert}
        title={t('trust.absent.title')}
        subtitle={t('trust.absent.subtitle')}
      />
      <div className="px-5 py-4 text-[12.5px] leading-relaxed text-amber-900">
        {body}
      </div>
    </CardShell>
  )
}

function DeclarationCard({
  audience,
  data,
}: {
  audience: Audience
  data: KeyDeclarationResponse
}) {
  const t = useT()
  const { declaration, consistency } = data
  if (!declaration) return null

  const tone: 'ok' | 'warn' = consistency.ok ? 'ok' : 'warn'

  const op = declaration.operator
  const externalRefs = op.external_references ?? []

  const subtitle = audience === 'operator'
    ? `${t('trust.present.subtitle.operator')} ${op.operator_id}`
    : t('trust.present.subtitle.recipient')

  return (
    <CardShell tone={tone}>
      <StatusHeader
        tone={tone}
        icon={tone === 'ok' ? ShieldCheck : ShieldAlert}
        title={tone === 'ok' ? t('trust.present.title.ok') : t('trust.present.title.warn')}
        subtitle={subtitle}
      />
      <div className="px-5 py-4 space-y-4 text-[12.5px] text-slate-800">
        {/* Operator block */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Key size={13} strokeWidth={2} className="text-slate-500" />
            <p className="font-semibold text-[12px] uppercase tracking-wider text-slate-600">
              {t('trust.operator.section')}
            </p>
          </div>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-[11.5px]">
            <dt className="text-slate-500">{t('trust.operator.id')}</dt>
            <dd className="font-mono">{op.operator_id}</dd>

            <dt className="text-slate-500">{t('trust.operator.fingerprint')}</dt>
            <dd className="font-mono break-all">{op.public_key_fingerprint}</dd>

            {op.first_published_at && (
              <>
                <dt className="text-slate-500">{t('trust.operator.firstPublished')}</dt>
                <dd className="font-mono">{op.first_published_at}</dd>
              </>
            )}
          </dl>
        </div>

        {/* Fingerprint mismatch warning */}
        {!consistency.operator_matches && (
          <MismatchWarning
            label={t('trust.mismatch.fingerprint.label')}
            details={
              consistency.operator_fingerprint_declared !==
              consistency.operator_fingerprint_actual
                ? t('trust.mismatch.fingerprint.details')
                    .replace('{declared}', consistency.operator_fingerprint_declared?.slice(0,16) ?? '?')
                    .replace('{actual}', consistency.operator_fingerprint_actual?.slice(0,16) ?? '?')
                : t('trust.mismatch.fingerprint.missing')
            }
          />
        )}

        {/* Phantom witness warning */}
        {consistency.declared_witnesses_without_pem.length > 0 && (
          <MismatchWarning
            label={t('trust.mismatch.witness.label')}
            details={consistency.declared_witnesses_without_pem
              .map(w => `${w.witness_operator_id} (${w.public_key_fingerprint.slice(0,16)}…)`)
              .join(', ')}
          />
        )}

        {/* External references */}
        <div>
          <p className="font-semibold text-[12px] uppercase tracking-wider text-slate-600 mb-2">
            {t('trust.refs.title')} ({externalRefs.length})
          </p>
          {externalRefs.length === 0 ? (
            <p className="text-slate-500 italic text-[11.5px]">
              {t('trust.refs.empty')}
            </p>
          ) : (
            <ul className="space-y-2">
              {externalRefs.map((r, i) => (
                <ReferenceRow key={i} r={r} />
              ))}
            </ul>
          )}
        </div>

        {/* Receptor guidance only */}
        {audience === 'recipient' && externalRefs.length > 0 && (
          <p className="text-[11.5px] text-slate-600 leading-relaxed border-t border-slate-200 pt-3">
            <strong>{t('trust.howto.title')}</strong>{' '}
            {t('trust.howto.body')}{' '}
            <code className="bg-slate-100 px-1 rounded">openssl pkey -pubin -outform DER | sha256sum</code>
            {t('trust.howto.body_cont')}
          </p>
        )}
      </div>
    </CardShell>
  )
}

function ReferenceRow({ r }: { r: ExternalReference }) {
  return (
    <li className="bg-white border border-slate-200 rounded px-3 py-2 text-[11.5px]">
      <div className="flex items-start gap-2 mb-1">
        <span className="font-mono uppercase tracking-wider text-[10px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 shrink-0">
          {r.kind}
        </span>
        <a
          href={r.uri}
          target="_blank"
          rel="noreferrer"
          className="font-mono break-all text-blue-700 hover:underline inline-flex items-center gap-1 min-w-0"
        >
          <span className="truncate">{r.uri}</span>
          <ExternalLink size={10} className="shrink-0" />
        </a>
      </div>
      {r.note && (
        <p className="text-slate-500 text-[11px] leading-snug">{r.note}</p>
      )}
    </li>
  )
}

function MismatchWarning({
  label,
  details,
}: {
  label: string
  details: string
}) {
  return (
    <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded px-3 py-2 text-[11.5px] text-red-800">
      <AlertCircle size={13} strokeWidth={2.5} className="text-red-600 shrink-0 mt-0.5" />
      <div>
        <p className="font-semibold">{label}</p>
        <p className="text-red-700 mt-0.5">{details}</p>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white animate-pulse">
      <div className="h-[60px] border-b border-slate-100" />
      <div className="px-5 py-4 space-y-3">
        <div className="h-3 bg-slate-100 rounded w-1/3" />
        <div className="h-3 bg-slate-100 rounded w-2/3" />
        <div className="h-3 bg-slate-100 rounded w-1/2" />
      </div>
    </div>
  )
}

function ErrorCard({ message }: { message: string }) {
  const t = useT()
  return (
    <CardShell tone="fail">
      <StatusHeader
        tone="fail"
        icon={AlertCircle}
        title={t('trust.error')}
        subtitle={message}
      />
    </CardShell>
  )
}
