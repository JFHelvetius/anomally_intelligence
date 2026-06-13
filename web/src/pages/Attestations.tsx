import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Shield, ArrowLeft, ArrowRight, CheckCircle2, ExternalLink } from 'lucide-react'
import { api } from '../api/client'
import { Card, CardHeader, Hash, Badge, PageHeader, EmptyState, Skeleton, OfflineState } from '../components/ui'

const KIND_COLOR: Record<string, 'green'|'blue'|'purple'|'amber'|'orange'|'slate'> = {
  workspace:       'purple',
  timeline:        'blue',
  snapshot:        'blue',
  justification:   'amber',
  context_bundle:  'green',
  manifest:        'slate',
  archive_snapshot: 'orange',
}

export function AttestationsList() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['attestations-list'],
    queryFn: api.listAttestations,
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Attestations"
        description="Cryptographic ed25519 signatures binding artifacts to an operator key. Offline-verifiable without access to the archive."
      />

      {/* Explanation card */}
      <div className="bg-[var(--accent-bg)] border border-[var(--accent-line)] rounded-xl px-5 py-4 flex items-start gap-3">
        <Shield size={16} className="text-[var(--accent)] mt-0.5 shrink-0" />
        <div className="text-sm">
          <p className="text-violet-200 font-medium mb-0.5">How attestations work</p>
          <p className="text-[var(--muted3)] text-xs leading-relaxed">
            Each attestation signs the SHA-256 hash of an artifact with an operator's ed25519 private key.
            Any third party with the public key can verify the signature offline — no access to the archive needed.
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 space-y-2">
              <Skeleton className="h-3 w-48" /><Skeleton className="h-2.5 w-72" />
            </div>
          ))}
        </div>
      )}
      {isError && (
        <OfflineState
          title="No se pudieron cargar las atestaciones"
          body="Las atestaciones firmadas (ed25519) viven en el archive AIP local. Sin backend `aip-web`, esta vista queda en blanco."
        />
      )}

      {!isLoading && (!data || data.length === 0) && (
        <EmptyState
          icon={<Shield size={20} />}
          title="No attestations"
          description="Use aip attestation sign to create cryptographic attestations over archive artifacts."
        />
      )}

      {data && data.length > 0 && (
        <Card>
          <CardHeader title="Signed Artifacts" sub={`${data.length} attestation${data.length !== 1 ? 's' : ''}`} />
          <div className="divide-y divide-[#1e2535]">
            {data.map((a) => (
              <Link
                key={a.id}
                to={`/attestations/${a.id}`}
                className="flex items-center gap-4 px-5 py-4 hover:bg-[var(--surface2)] transition-colors group"
              >
                <div className="w-9 h-9 rounded-lg bg-[var(--amber-bg)] border border-[var(--orange)] flex items-center justify-center shrink-0">
                  <CheckCircle2 size={14} className="text-[var(--orange)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-sm text-[var(--text)] font-mono">{a.id}</span>
                    <Badge variant={KIND_COLOR[a.artifact_kind] ?? 'slate'}>
                      {a.artifact_kind?.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[11px] text-[var(--muted)] font-mono">
                    <span>Signer: {a.signer_id}</span>
                    <span>·</span>
                    <span>{a.signed_at?.replace('T', ' ').replace('Z', ' UTC')}</span>
                    {a.attestation_hash && <><span>·</span><Hash value={a.attestation_hash} /></>}
                  </div>
                </div>
                <ArrowRight size={13} className="text-[var(--text2)] group-hover:text-[var(--accent)] transition-colors shrink-0" />
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

export function AttestationDetail() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['attestation', id],
    queryFn: () => api.getAttestation(id!),
    enabled: !!id,
  })

  if (isLoading) return <div className="p-6 text-[var(--muted)] text-sm">Loading…</div>
  if (isError) return (
    <OfflineState
      title="Atestación no encontrada"
      body="No se pudo cargar esta atestación. O bien no existe en el archive local, o el backend `aip-web` no está corriendo."
    />
  )
  if (!data) return null

  const kind = data.artifact_kind as string
  const ok = data.signature_algorithm !== undefined

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <Link to="/attestations" className="flex items-center gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--accent)] transition-colors">
        <ArrowLeft size={12} /> Back to Attestations
      </Link>

      {/* Header card */}
      <div className="bg-[var(--surface)] border border-[var(--orange)] rounded-xl p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[var(--amber-bg)] border border-[var(--orange)] flex items-center justify-center">
            <Shield size={18} className="text-[var(--orange)]" />
          </div>
          <a
            href={`/api/attestations/${id}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--accent)]"
          >
            Raw JSON <ExternalLink size={11} />
          </a>
        </div>
        <p className="text-lg font-bold text-[var(--text)] font-mono mb-2">{id}</p>
        <div className="flex flex-wrap gap-2">
          <Badge variant={KIND_COLOR[kind] ?? 'slate'}>{kind?.replace(/_/g, ' ')}</Badge>
          <Badge variant="green">ed25519-v1</Badge>
          {ok && <Badge variant="green"><CheckCircle2 size={10} /> Valid structure</Badge>}
        </div>
      </div>

      {/* Fields */}
      <Card className="divide-y divide-[#1e2535]">
        {[
          ['Signer ID',          data.signer_id],
          ['Signed At',          data.signed_at],
          ['Algorithm',          data.signature_algorithm],
          ['Artifact Kind',      data.artifact_kind],
          ['Artifact Hash',      data.artifact_hash],
          ['Attestation Hash',   data.attestation_hash],
          ['Public Key FP',      data.public_key_fingerprint],
          ['Schema Version',     data.schema_version],
        ].map(([label, value]) => value && (
          <div key={label as string} className="grid grid-cols-[160px_1fr] gap-3 px-5 py-3 items-start">
            <span className="text-[11px] text-[var(--muted)] uppercase tracking-wider pt-0.5">{label}</span>
            <span className="text-xs font-mono text-[var(--text2)] break-all">{value as string}</span>
          </div>
        ))}
      </Card>

      {/* Signature raw */}
      {data.signature && (
        <Card>
          <CardHeader title="Signature (base64)" />
          <div className="px-5 py-4">
            <code className="text-[11px] font-mono text-[var(--muted3)] break-all leading-relaxed">
              {data.signature as string}
            </code>
          </div>
        </Card>
      )}
    </div>
  )
}
