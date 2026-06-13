import { useState, useRef, useCallback } from 'react'
import {
  ScanSearch, AlertCircle, CheckCircle2, HelpCircle,
  AlertTriangle, Eye, Lightbulb, ClipboardList, Info,
  Loader2, ImagePlus, X, ChevronDown, ChevronUp,
} from 'lucide-react'
import { api, type AnalysisResult, type AnalysisAnomaly } from '../api/client'
import { Badge, PageHeader, Card, CardHeader } from '../components/ui'
import { useT } from '../i18n'
import type { TKey } from '../i18n/en'

// ─── Assessment meta ──────────────────────────────────────────────────────

const ASSESSMENT_META: Record<string, {
  labelKey: TKey
  Icon: React.ElementType
  color: string
  bg: string
  badge: 'amber' | 'green' | 'blue'
}> = {
  anomalous: {
    labelKey: 'analyze.classification.anomaly',
    Icon: AlertCircle,
    color: 'text-amber-700',
    bg: 'bg-amber-50 border-amber-300',
    badge: 'amber',
  },
  conventional: {
    labelKey: 'analyze.classification.conventional',
    Icon: CheckCircle2,
    color: 'text-emerald-700',
    bg: 'bg-emerald-50 border-emerald-300',
    badge: 'green',
  },
  indeterminate: {
    labelKey: 'dashboard.conclusions.indeterminate.label',
    Icon: HelpCircle,
    color: 'text-blue-700',
    bg: 'bg-blue-50 border-blue-300',
    badge: 'blue',
  },
}

const SEVERITY_BADGE: Record<string, 'orange' | 'amber' | 'slate'> = {
  high:   'orange',
  medium: 'amber',
  low:    'slate',
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high:   'text-emerald-700',
  medium: 'text-amber-700',
  low:    'text-slate-400',
}

const QUALITY_COLOR: Record<string, string> = {
  good: 'text-emerald-700',
  fair: 'text-amber-700',
  poor: 'text-red-700',
}

const ALLOWED_MIME = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
const MAX_MB = 5

// ─── Upload zone ──────────────────────────────────────────────────────────

function DropZone({
  onFile, disabled,
}: { onFile: (f: File) => void; disabled: boolean }) {
  const t = useT()
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handle = useCallback((f: File | null) => {
    if (!f) return
    if (!ALLOWED_MIME.has(f.type)) {
      alert('Format not supported. Use JPEG, PNG, GIF or WebP.')
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      alert(t('analyze.upload.tooLarge').replace('{n}', String(MAX_MB)))
      return
    }
    onFile(f)
  }, [onFile, t])

  return (
    <div
      onDragOver={e => { e.preventDefault(); if (!disabled) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) handle(e.dataTransfer.files[0] ?? null)
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`
        relative flex flex-col items-center justify-center gap-3
        rounded-2xl border-2 border-dashed p-10 cursor-pointer transition-all
        ${dragging
          ? 'border-violet-500 bg-violet-50'
          : disabled
            ? 'border-[var(--border)] bg-[var(--bg)] cursor-default opacity-50'
            : 'border-[var(--border2)] bg-[var(--surface)] hover:border-violet-600/60 hover:bg-violet-50'
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        className="hidden"
        onChange={e => handle(e.target.files?.[0] ?? null)}
      />
      <div className="w-12 h-12 rounded-2xl bg-violet-50 border border-violet-200 flex items-center justify-center">
        <ImagePlus size={22} className="text-violet-700" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-slate-700">
          {dragging ? t('analyze.upload.drop') : t('analyze.upload.idle')}
        </p>
        <p className="text-xs text-slate-600 mt-1">{t('analyze.upload.formats')}</p>
      </div>
    </div>
  )
}

// ─── Collapsible section ──────────────────────────────────────────────────

function ResultSection({
  title, icon: Icon, iconColor, count, children, defaultOpen = true,
}: {
  title: string
  icon: React.ElementType
  iconColor: string
  count?: number
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors border-b border-[var(--border)]"
      >
        <Icon size={14} className={iconColor} />
        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex-1 text-left">
          {title}
        </span>
        {count !== undefined && (
          <span className="text-[11px] font-mono text-slate-500 mr-2">{count}</span>
        )}
        {open
          ? <ChevronUp size={13} className="text-slate-500" />
          : <ChevronDown size={13} className="text-slate-500" />}
      </button>
      {open && <div className="px-5 py-4">{children}</div>}
    </Card>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────

export default function Analyze() {
  const t = useT()
  const [file, setFile]           = useState<File | null>(null)
  const [preview, setPreview]     = useState<string | null>(null)
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState<AnalysisResult | null>(null)
  const [error, setError]         = useState<string | null>(null)

  const handleFile = (f: File) => {
    setFile(f)
    setResult(null)
    setError(null)
    const reader = new FileReader()
    reader.onload = e => setPreview(e.target?.result as string)
    reader.readAsDataURL(f)
  }

  const clearFile = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
  }

  const runAnalysis = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await api.analyzeImage(file)
      setResult(r)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const a = result?.analysis
  const assessmentKey = a?.overall_assessment ?? 'indeterminate'
  const meta = ASSESSMENT_META[assessmentKey] ?? ASSESSMENT_META.indeterminate
  const AssessIcon = meta.Icon

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anomaly Detector"
        description={t('analyze.description')}
      />

      {/* How it works strip */}
      <div className="bg-violet-50 border border-violet-200 rounded-xl px-5 py-4 flex items-start gap-3">
        <ScanSearch size={15} className="text-violet-700 mt-0.5 shrink-0" />
        <div className="text-xs text-slate-400 leading-relaxed space-y-1">
          <p>
            <span className="text-violet-700 font-medium">{t('analyze.how.label')} </span>
            {t('analyze.how.body')}
          </p>
          <p className="text-slate-600">
            Los resultados son sugerencias del modelo — no conclusiones. Ingesta la imagen como
            evidencia con <code className="font-mono text-violet-700/70">aip evidence ingest</code> para
            preservarla en el archive con hash SHA-256.
          </p>
        </div>
      </div>

      {/* Upload + preview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-3">
          {!file
            ? <DropZone onFile={handleFile} disabled={loading} />
            : (
              <div className="relative">
                <img
                  src={preview!}
                  alt="preview"
                  className="w-full rounded-2xl border border-[var(--border)] object-contain max-h-64 bg-black"
                />
                <button
                  onClick={clearFile}
                  className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/70 border border-[var(--border2)] flex items-center justify-center text-slate-400 hover:text-red-700 transition-colors"
                >
                  <X size={13} />
                </button>
              </div>
            )}

          {file && (
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3 space-y-1">
              <p className="text-xs text-slate-700 font-medium truncate">{file.name}</p>
              <p className="text-[11px] text-slate-600 font-mono">
                {file.type} · {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          )}
        </div>

        {/* Right panel: action + status */}
        <div className="flex flex-col justify-center gap-4">
          <button
            onClick={runAnalysis}
            disabled={!file || loading}
            className={`
              w-full flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl
              text-sm font-semibold transition-all duration-150
              ${file && !loading
                ? 'bg-violet-600 hover:bg-violet-500 text-slate-900 shadow-lg shadow-violet-900/40'
                : 'bg-[var(--surface)] border border-[var(--border)] text-slate-600 cursor-default'}
            `}
          >
            {loading
              ? <><Loader2 size={16} className="animate-spin" /> Analizando imagen…</>
              : <><ScanSearch size={16} /> Analizar imagen</>}
          </button>

          {!file && (
            <p className="text-xs text-slate-600 text-center">
              {t('analyze.placeholder')}
            </p>
          )}

          {loading && (
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Loader2 size={12} className="animate-spin text-violet-700" />
                Enviando imagen a Claude Vision…
              </div>
              <div className="flex items-center gap-2 text-[11px] text-slate-600">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-700 animate-pulse" />
                {t('analyze.detecting')}
              </div>
              <div className="flex items-center gap-2 text-[11px] text-slate-600">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-700 animate-pulse" />
                Evaluando explicaciones convencionales
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-300 rounded-xl p-4 text-xs text-red-700 leading-relaxed">
              <p className="font-medium mb-1">{t('analyze.error.title')}</p>
              <p>{error}</p>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {result && a && !a.parse_error && (
        <div className="space-y-4">

          {/* Verdict header */}
          <div className={`border rounded-2xl p-5 flex items-start gap-4 ${meta.bg}`}>
            <div className={`w-12 h-12 rounded-xl border flex items-center justify-center shrink-0 ${meta.bg}`}>
              <AssessIcon size={22} className={meta.color} />
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <p className={`text-lg font-bold ${meta.color}`}>{t(meta.labelKey)}</p>
                <Badge variant={meta.badge}>{assessmentKey}</Badge>
              </div>
              <div className="flex flex-wrap gap-4 text-[11px] font-mono">
                <span>
                  Confianza:{' '}
                  <span className={CONFIDENCE_COLOR[a.confidence] ?? 'text-slate-400'}>
                    {a.confidence}
                  </span>
                </span>
                <span>
                  Calidad de imagen:{' '}
                  <span className={QUALITY_COLOR[a.image_quality] ?? 'text-slate-400'}>
                    {a.image_quality}
                  </span>
                </span>
                <span className="text-slate-500">
                  Modelo: {result.model}
                </span>
              </div>
              {a.analysis_notes && (
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">{a.analysis_notes}</p>
              )}
            </div>
          </div>

          {/* Objects detected */}
          {a.objects_detected?.length > 0 && (
            <ResultSection
              title="Objetos detectados"
              icon={Eye}
              iconColor="text-blue-700"
              count={a.objects_detected.length}
            >
              <div className="space-y-2.5">
                {a.objects_detected.map((obj, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--surface2)] border border-[var(--border)]">
                    <div className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                      obj.is_anomalous
                        ? 'bg-amber-100 border-amber-300'
                        : 'bg-emerald-100 border-emerald-300'
                    }`}>
                      {obj.is_anomalous
                        ? <AlertCircle size={10} className="text-amber-700" />
                        : <CheckCircle2 size={10} className="text-emerald-700" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-800">{obj.description}</p>
                      <div className="flex flex-wrap gap-3 mt-1 text-[11px] text-slate-500 font-mono">
                        {obj.conventional_match && (
                          <span>Match convencional: {obj.conventional_match}</span>
                        )}
                        {obj.location_in_image && (
                          <span>{t('analyze.position')} {obj.location_in_image}</span>
                        )}
                      </div>
                    </div>
                    {obj.is_anomalous && <Badge variant="amber">{t('analyze.anomalousBadge')}</Badge>}
                  </div>
                ))}
              </div>
            </ResultSection>
          )}

          {/* Anomalies */}
          {a.anomalies?.length > 0 && (
            <ResultSection
              title={t('analyze.section.anomalies')}
              icon={AlertTriangle}
              iconColor="text-amber-700"
              count={a.anomalies.length}
            >
              <div className="space-y-2">
                {a.anomalies.map((an: AnalysisAnomaly, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={SEVERITY_BADGE[an.severity] ?? 'slate'}>
                          {an.severity}
                        </Badge>
                        <span className="text-[11px] font-mono text-slate-500">{an.type}</span>
                      </div>
                      <p className="text-xs text-slate-700">{an.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </ResultSection>
          )}

          {/* Conventional explanations */}
          {a.conventional_explanations?.length > 0 && (
            <ResultSection
              title="Explicaciones convencionales consideradas"
              icon={Lightbulb}
              iconColor="text-emerald-700"
              count={a.conventional_explanations.length}
              defaultOpen={false}
            >
              <ul className="space-y-1.5">
                {a.conventional_explanations.map((ex, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                    <CheckCircle2 size={11} className="text-emerald-700 mt-0.5 shrink-0" />
                    {ex}
                  </li>
                ))}
              </ul>
            </ResultSection>
          )}

          {/* Recommended next steps */}
          {a.recommended_investigation_steps?.length > 0 && (
            <ResultSection
              title={t('analyze.section.investigationSteps')}
              icon={ClipboardList}
              iconColor="text-violet-700"
              defaultOpen={false}
            >
              <div className="space-y-2">
                {a.recommended_investigation_steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-violet-50 border border-violet-200">
                    <span className="text-[11px] font-mono font-bold text-violet-700 shrink-0 mt-0.5">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <p className="text-xs text-slate-700">{step}</p>
                  </div>
                ))}
              </div>
            </ResultSection>
          )}

          {/* Recommended classification + analyst caveat */}
          <Card>
            <CardHeader title={t('analyze.section.classification')} />
            <div className="px-5 pb-5 space-y-4">
              <div className="flex items-center gap-3">
                <Badge variant={
                  a.recommended_classification === 'explained'     ? 'green'  :
                  a.recommended_classification === 'unexplained'   ? 'amber'  :
                  a.recommended_classification === 'contaminated'  ? 'orange' : 'blue'
                }>
                  {a.recommended_classification}
                </Badge>
                <p className="text-[11px] text-slate-500 italic">
                  {t('analyze.classification.note')}
                </p>
              </div>

              {a.analyst_caveat && (
                <div className="flex items-start gap-2 bg-[var(--bg)] border border-[var(--border)] rounded-xl p-3">
                  <Info size={13} className="text-slate-600 mt-0.5 shrink-0" />
                  <p className="text-xs text-slate-500 italic leading-relaxed">{a.analyst_caveat}</p>
                </div>
              )}

              <div className="bg-[var(--bg)] border border-violet-200 rounded-xl p-3">
                <p className="text-[11px] text-slate-500 mb-2 font-medium">Para preservar esta imagen en el archive:</p>
                <code className="text-[11px] font-mono text-violet-700/80 block">
                  aip evidence ingest --file &lt;ruta/imagen&gt; --kind still_image --source-id &lt;id_fuente&gt;
                </code>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Raw parse error fallback */}
      {result && a?.parse_error && (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 space-y-2">
          <p className="text-xs text-amber-700 font-medium">Respuesta del modelo (no parseada como JSON)</p>
          <pre className="text-[11px] text-slate-400 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
            {a.raw_response}
          </pre>
        </div>
      )}
    </div>
  )
}
