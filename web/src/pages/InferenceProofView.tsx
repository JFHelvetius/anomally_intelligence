import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft, ShieldCheck, ShieldAlert, Brain, Target, FileText,
  AlertTriangle, ExternalLink,
} from 'lucide-react'
import { api } from '../api/client'
import { Card, CardHeader, Hash, Badge, PageHeader, Skeleton, Alert, InfoRow, OfflineState } from '../components/ui'
import { useT } from '../i18n'
import {
  verifyProofHash, verifyStructural, isWeakRule,
  type InferenceProof, type VerifyLogicResult,
  type Premise, type DerivedClaim, type InferenceStep,
} from '../lib/inferenceLogic'

// ─── DAG layout ──────────────────────────────────────────────────────────
// Vertical top-down: premises row → inference + claim pairs → conclusion at base.
// Algoritmo de layout simple: topological levels via BFS. Cada nivel se distribuye
// horizontalmente con espacio uniforme. Sin librerías externas — sólo SVG.

interface NodePos {
  id: string
  kind: 'premise' | 'inference' | 'claim'
  level: number
  col: number
  text: string
  meta?: string
}

interface EdgeSpec {
  from: string
  to: string
  isWeak: boolean
}

function computeLayout(proof: InferenceProof): { nodes: NodePos[]; edges: EdgeSpec[] } {
  // Build a mapping claim_id → produced_by_inference_id (for derived claims)
  const derivedByClaim = new Map<string, string>()
  for (const c of proof.derived_claims) derivedByClaim.set(c.id, c.inferred_by)

  // Compute the level of each node via BFS from premises.
  // - Premises are level 0.
  // - An inference's level is max(level of inputs) + 1.
  // - A derived claim's level is the level of its producing inference.
  const claimLevel = new Map<string, number>()
  for (const p of proof.premises) claimLevel.set(p.id, 0)

  const inferenceLevel = new Map<string, number>()
  let changed = true
  let safety = 0
  while (changed && safety++ < 100) {
    changed = false
    for (const inf of proof.inferences) {
      const inputLevels = inf.input_claim_ids.map(id => claimLevel.get(id))
      if (inputLevels.some(l => l === undefined)) continue
      const lvl = Math.max(...(inputLevels as number[])) + 1
      if (inferenceLevel.get(inf.id) !== lvl) {
        inferenceLevel.set(inf.id, lvl)
        changed = true
      }
      const outClaim = inf.output_claim_id
      if (claimLevel.get(outClaim) !== lvl) {
        claimLevel.set(outClaim, lvl)
        changed = true
      }
    }
  }

  // Group nodes by level. Inferences and claims at the same numeric level live
  // in adjacent sub-rows (inference on top, claim below).
  const byLevel = new Map<number, { premises: Premise[]; inferences: InferenceStep[]; claims: DerivedClaim[] }>()
  const ensureLevel = (lvl: number) => {
    if (!byLevel.has(lvl)) byLevel.set(lvl, { premises: [], inferences: [], claims: [] })
    return byLevel.get(lvl)!
  }

  for (const p of proof.premises) {
    ensureLevel(claimLevel.get(p.id) ?? 0).premises.push(p)
  }
  for (const inf of proof.inferences) {
    ensureLevel(inferenceLevel.get(inf.id) ?? 1).inferences.push(inf)
  }
  for (const c of proof.derived_claims) {
    ensureLevel(claimLevel.get(c.id) ?? 1).claims.push(c)
  }

  // Sort each level by id for determinism.
  for (const data of byLevel.values()) {
    data.premises.sort((a, b) => a.id.localeCompare(b.id))
    data.inferences.sort((a, b) => a.id.localeCompare(b.id))
    data.claims.sort((a, b) => a.id.localeCompare(b.id))
  }

  // Assign columns within each level.
  const nodes: NodePos[] = []
  const levels = [...byLevel.keys()].sort((a, b) => a - b)
  for (const lvl of levels) {
    const data = byLevel.get(lvl)!
    if (lvl === 0) {
      // Premises row.
      data.premises.forEach((p, i) => {
        nodes.push({ id: p.id, kind: 'premise', level: 0, col: i, text: p.text, meta: p.kind })
      })
    } else {
      // Inference + claim sub-rows. Pair each inference with its output claim.
      const pairs: { inf: InferenceStep; claim: DerivedClaim | undefined }[] = []
      for (const inf of data.inferences) {
        const c = data.claims.find(cc => cc.id === inf.output_claim_id)
        pairs.push({ inf, claim: c })
      }
      pairs.forEach((pair, i) => {
        nodes.push({
          id: pair.inf.id,
          kind: 'inference',
          level: lvl * 2 - 1, // inference sits in the "upper" half of level
          col: i,
          text: pair.inf.rule,
          meta: pair.inf.text,
        })
        if (pair.claim) {
          nodes.push({
            id: pair.claim.id,
            kind: 'claim',
            level: lvl * 2,
            col: i,
            text: pair.claim.text,
          })
        }
      })
    }
  }

  // Edges: every inference has edges from each input claim to itself, and from
  // itself to its output claim.
  const edges: EdgeSpec[] = []
  for (const inf of proof.inferences) {
    const weak = isWeakRule(inf.rule)
    for (const inId of inf.input_claim_ids) {
      edges.push({ from: inId, to: inf.id, isWeak: weak })
    }
    edges.push({ from: inf.id, to: inf.output_claim_id, isWeak: weak })
  }

  return { nodes, edges }
}

// ─── DAG SVG renderer ────────────────────────────────────────────────────

const NODE_W = 220
const NODE_H = 64
const LEVEL_GAP = 32
const COL_GAP = 24

function DAGSvg({
  proof, selectedId, onSelect,
}: {
  proof: InferenceProof
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const { nodes, edges } = useMemo(() => computeLayout(proof), [proof])
  const conclusionId = proof.conclusion_claim_id

  // Compute SVG canvas size.
  const maxLevel = Math.max(...nodes.map(n => n.level), 0)
  const maxColByLevel = new Map<number, number>()
  for (const n of nodes) {
    maxColByLevel.set(n.level, Math.max(maxColByLevel.get(n.level) ?? 0, n.col))
  }
  const maxColAny = Math.max(...maxColByLevel.values(), 0)
  const width = (maxColAny + 1) * (NODE_W + COL_GAP) + COL_GAP
  const height = (maxLevel + 1) * (NODE_H + LEVEL_GAP) + LEVEL_GAP

  // Position lookup.
  const pos = new Map<string, { x: number; y: number }>()
  // Center each level's nodes horizontally.
  for (const n of nodes) {
    const colsInLevel = (maxColByLevel.get(n.level) ?? 0) + 1
    const levelTotalWidth = colsInLevel * (NODE_W + COL_GAP) - COL_GAP
    const startX = (width - levelTotalWidth) / 2
    pos.set(n.id, {
      x: startX + n.col * (NODE_W + COL_GAP),
      y: LEVEL_GAP + n.level * (NODE_H + LEVEL_GAP),
    })
  }

  const nodeColor = (n: NodePos) => {
    if (n.id === conclusionId) return { fill: '#d1fae5', stroke: '#10b981', text: '#065f46' }
    if (n.kind === 'premise') return { fill: '#ede9fe', stroke: '#7c3aed', text: '#5b21b6' }
    if (n.kind === 'inference') {
      const isWeak = isWeakRule(n.text)
      return isWeak
        ? { fill: '#fef3c7', stroke: '#f59e0b', text: '#92400e' }
        : { fill: '#dbeafe', stroke: '#3b82f6', text: '#1e40af' }
    }
    return { fill: '#f1f5f9', stroke: '#64748b', text: '#334155' }
  }

  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
        </marker>
        <marker id="arrow-weak" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
        </marker>
      </defs>

      {edges.map((e, i) => {
        const from = pos.get(e.from)
        const to = pos.get(e.to)
        if (!from || !to) return null
        const fx = from.x + NODE_W / 2
        const fy = from.y + NODE_H
        const tx = to.x + NODE_W / 2
        const ty = to.y
        const midY = (fy + ty) / 2
        const path = `M ${fx} ${fy} C ${fx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`
        return (
          <path
            key={i}
            d={path}
            stroke={e.isWeak ? '#f59e0b' : '#64748b'}
            strokeWidth={e.isWeak ? 2 : 1.5}
            strokeDasharray={e.isWeak ? '4 3' : undefined}
            fill="none"
            markerEnd={e.isWeak ? 'url(#arrow-weak)' : 'url(#arrow)'}
          />
        )
      })}

      {nodes.map(n => {
        const p = pos.get(n.id)!
        const col = nodeColor(n)
        const isSelected = selectedId === n.id
        const label = n.kind === 'inference' ? `[${n.text}]` : n.text
        const subLabel = n.kind === 'inference' ? n.meta : (n.kind === 'premise' ? n.meta : '')
        return (
          <g
            key={n.id}
            transform={`translate(${p.x}, ${p.y})`}
            onClick={() => onSelect(n.id)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={6}
              fill={col.fill}
              stroke={isSelected ? '#0f172a' : col.stroke}
              strokeWidth={isSelected ? 2.5 : 1.5}
            />
            <text
              x={10} y={18}
              fontSize={9}
              fontFamily="JetBrains Mono, ui-monospace, monospace"
              fontWeight="bold"
              fill={col.text}
              style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              {n.kind === 'inference' && isWeakRule(n.text) ? `WEAK · ${n.id}` : `${n.kind} · ${n.id}`}
            </text>
            <foreignObject x={10} y={22} width={NODE_W - 20} height={NODE_H - 26}>
              <div
                style={{
                  color: col.text,
                  fontSize: 11,
                  lineHeight: '1.25',
                  overflow: 'hidden',
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  fontFamily: n.kind === 'inference' ? 'JetBrains Mono, monospace' : 'Inter, sans-serif',
                  fontWeight: n.kind === 'inference' ? 600 : 500,
                }}
                title={subLabel || label}
              >
                {label}
              </div>
            </foreignObject>
            {n.id === conclusionId && (
              <text x={NODE_W - 8} y={14} fontSize={9} fontWeight="bold" fill="#065f46" textAnchor="end">
                ★ CONCLUSION
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ─── Side panel showing detail of selected node ──────────────────────────

function NodeDetail({
  proof, nodeId,
}: {
  proof: InferenceProof
  nodeId: string | null
}) {
  if (nodeId === null) {
    return (
      <Card>
        <CardHeader title="Detalle" sub="Click cualquier nodo de la DAG" />
        <div className="px-5 py-8 text-center text-[12px] text-[var(--muted)]">
          Selecciona un nodo para ver su texto completo, kind, evidence_refs o regla aplicada.
        </div>
      </Card>
    )
  }
  const premise = proof.premises.find(p => p.id === nodeId)
  const inference = proof.inferences.find(i => i.id === nodeId)
  const claim = proof.derived_claims.find(c => c.id === nodeId)

  if (premise) {
    return (
      <Card>
        <CardHeader title={`Premise · ${premise.id}`} sub={premise.kind} />
        <div className="p-5 space-y-3">
          <p className="text-[13px] text-[var(--text2)] leading-relaxed">{premise.text}</p>
          {premise.evidence_refs.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider mb-2">
                Evidence refs ({premise.evidence_refs.length})
              </p>
              <div className="space-y-1">
                {premise.evidence_refs.map(ref => (
                  <Link
                    key={ref}
                    to={`/evidence/${ref}`}
                    className="block hover:bg-[var(--surface2)] -mx-1 px-1 py-0.5 rounded"
                  >
                    <Hash value={ref} />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>
    )
  }
  if (inference) {
    const weak = isWeakRule(inference.rule)
    return (
      <Card>
        <CardHeader
          title={`Inference · ${inference.id}`}
          sub={inference.rule}
          action={
            weak
              ? <Badge variant="amber" dot>weak (non-deductive)</Badge>
              : <Badge variant="blue" dot>deductive</Badge>
          }
        />
        <div className="p-5 space-y-3">
          <p className="text-[13px] text-[var(--text2)] leading-relaxed">{inference.text}</p>
          <InfoRow label="Rule" mono>{inference.rule}</InfoRow>
          <InfoRow label="Inputs">
            <div className="flex flex-wrap gap-1.5">
              {inference.input_claim_ids.map(id => (
                <span key={id} className="font-mono text-[10.5px] bg-[var(--surface2)] border border-[var(--border)] px-1.5 py-0.5 rounded">
                  {id}
                </span>
              ))}
            </div>
          </InfoRow>
          <InfoRow label="Output" mono>{inference.output_claim_id}</InfoRow>
        </div>
      </Card>
    )
  }
  if (claim) {
    const isConclusion = claim.id === proof.conclusion_claim_id
    return (
      <Card>
        <CardHeader
          title={`${isConclusion ? 'Conclusion' : 'Derived claim'} · ${claim.id}`}
          sub={`inferred by ${claim.inferred_by}`}
          action={isConclusion ? <Badge variant="green" dot>conclusion</Badge> : undefined}
        />
        <div className="p-5">
          <p className="text-[13px] text-[var(--text2)] leading-relaxed">{claim.text}</p>
        </div>
      </Card>
    )
  }
  return <Alert variant="error">Nodo no encontrado: {nodeId}</Alert>
}

// ─── Main page ───────────────────────────────────────────────────────────

export default function InferenceProofView() {
  const t = useT()
  const { proof_id } = useParams<{ proof_id: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['inference-proof', proof_id],
    queryFn: () => api.getInferenceProof(proof_id!),
    enabled: !!proof_id,
  })

  const proof = data as unknown as InferenceProof | undefined
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [structural, setStructural] = useState<VerifyLogicResult | null>(null)
  const [hashOk, setHashOk] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!proof) return
    setStructural(verifyStructural(proof))
    verifyProofHash(proof).then(ok => {
      if (!cancelled) setHashOk(ok)
    })
    return () => { cancelled = true }
  }, [proof])

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    )
  }

  if (isError || !proof) {
    return (
      <OfflineState
        title="Inference proof no encontrada"
        body="Las inference proofs (DAG estructural de razonamiento del analista) se sirven desde el archive AIP local."
        detail={(error as Error)?.message}
      />
    )
  }

  const verdictOk = structural?.ok === true && hashOk === true
  const verdictVariant = verdictOk ? 'green' : structural?.ok === false || hashOk === false ? 'red' : 'slate'
  const VerdictIcon = verdictOk ? ShieldCheck : ShieldAlert

  return (
    <div className="space-y-5 animate-in">
      <Link to="/derived" className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--accent)] font-medium">
        <ArrowLeft size={12} /> Back to Analysis Layers
      </Link>

      <PageHeader
        tag="Inference proof · machine-checkable reasoning"
        title={proof.proof_id}
        description={`Structured reasoning DAG that derives conclusion '${proof.conclusion_claim_id}' from ${proof.premises.length} premise${proof.premises.length !== 1 ? 's' : ''} via ${proof.inferences.length} inference step${proof.inferences.length !== 1 ? 's' : ''}.`}
      />

      {/* Verdict + metadata strip */}
      <div className="rounded-lg border border-[var(--border)] bg-white p-4 card-shadow flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <VerdictIcon size={16} className={verdictOk ? 'text-[var(--green)]' : 'text-red-700'} />
          <Badge variant={verdictVariant} dot>
            {hashOk === null ? 'Verifying…' : verdictOk ? 'Structurally valid' : 'Invalid'}
          </Badge>
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
          <Target size={11} /> target justification:
          <span className="font-mono text-[var(--text2)]">{proof.target_justification_id}</span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <Hash value={proof.proof_hash} />
          <a
            href={`/api/inference-proofs/${proof.proof_id}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-[var(--muted)] hover:text-[var(--accent)]"
          >
            raw JSON <ExternalLink size={9} />
          </a>
        </div>
      </div>

      {structural && structural.errors.length > 0 && (
        <Alert variant="error">
          <p className="font-semibold mb-1">Structural errors:</p>
          <ul className="space-y-0.5 text-[11.5px]">
            {structural.errors.map((e, i) => <li key={i} className="font-mono">· {e}</li>)}
          </ul>
        </Alert>
      )}

      {structural && structural.weak_inferences.length > 0 && (
        <div className="flex items-start gap-3 rounded-md bg-[var(--amber-bg)] border border-[var(--amber)] px-4 py-3">
          <AlertTriangle size={14} className="text-[var(--amber)] mt-0.5 shrink-0" />
          <div className="text-[12.5px] text-[var(--amber)] leading-relaxed">
            <span className="font-semibold">{structural.weak_inferences.length} weak (non-deductive) inference{structural.weak_inferences.length !== 1 ? 's' : ''}.</span>
            {' '}Abduction premises don't <em>follow</em> from observations — they're the best available explanation, which could be wrong even if every input is true.
          </div>
        </div>
      )}

      {/* DAG + side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <Card>
          <CardHeader
            title="Reasoning DAG"
            sub={`${structural?.structure.premise_count ?? 0} premises · ${structural?.structure.inference_count ?? 0} inferences · ${structural?.structure.derived_claim_count ?? 0} derived claims`}
            action={
              <div className="flex items-center gap-1 text-[10px]">
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[var(--accent-bg)] text-[var(--accent)]"><Brain size={9} /> premise</span>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-100 text-[var(--blue)]">deductive</span>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[var(--amber-bg)] text-[var(--amber)]">weak</span>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[var(--green-bg)] text-[var(--green)]">conclusion</span>
              </div>
            }
          />
          <div className="p-5 overflow-x-auto">
            <DAGSvg proof={proof} selectedId={selectedNode} onSelect={setSelectedNode} />
          </div>
        </Card>

        <NodeDetail proof={proof} nodeId={selectedNode} />
      </div>

      <Card>
        <CardHeader title="Metadata" />
        <div className="p-5">
          <InfoRow label="Proof ID" mono>{proof.proof_id}</InfoRow>
          <InfoRow label="Proof hash" mono>{proof.proof_hash}</InfoRow>
          <InfoRow label="Schema" mono>{proof.proof_type} · v{proof.schema_version}</InfoRow>
          <InfoRow label="Target justification" mono>{proof.target_justification_id}</InfoRow>
          <InfoRow label="Target justification hash" mono>{proof.target_justification_hash}</InfoRow>
          <InfoRow label="Conclusion" mono>{proof.conclusion_claim_id}</InfoRow>
          <InfoRow label="Rules used">
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(structural?.structure.rules_used ?? {}).map(([rule, count]) => (
                <Badge key={rule} variant={isWeakRule(rule) ? 'amber' : 'blue'}>
                  {rule} × {count}
                </Badge>
              ))}
            </div>
          </InfoRow>
        </div>
      </Card>

      {/* Reading hint */}
      <div className="flex items-start gap-3 rounded-md bg-[var(--surface2)] border border-[var(--border)] px-4 py-3">
        <FileText size={13} className="text-[var(--muted)] mt-0.5 shrink-0" />
        <div className="text-[12px] text-[var(--muted2)] leading-relaxed">
          <span className="font-semibold">{t('proof.hint.verifiesLabel')}</span> {t('proof.hint.verifiesBody')}
          {' '}<span className="font-semibold">{t('proof.hint.notVerifiedLabel')}</span> {t('proof.hint.notVerifiedBody')}
        </div>
      </div>
    </div>
  )
}
