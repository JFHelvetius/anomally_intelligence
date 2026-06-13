import { useState, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Copy, Check, AlertTriangle, AlertCircle, XCircle, ServerCrash, ArrowRight, Terminal } from 'lucide-react'

// ─── Badge — dark theme via translucent tint + colored border + colored text.
//             Mantiene la API pública por variant pero todo via tokens. ────

type BadgeVariant = 'green' | 'red' | 'amber' | 'blue' | 'purple' | 'orange' | 'slate'

// Each variant maps to two CSS custom vars: a translucent bg tint + a
// solid foreground color. Border uses the foreground at low alpha via
// inline style below; the className here is layout only.
const BADGE_TOKENS: Record<BadgeVariant, { bg: string; fg: string }> = {
  green:  { bg: 'var(--green-bg)',  fg: 'var(--green)'  },
  red:    { bg: 'var(--red-bg)',    fg: 'var(--red)'    },
  amber:  { bg: 'var(--amber-bg)',  fg: 'var(--amber)'  },
  blue:   { bg: 'var(--blue-bg)',   fg: 'var(--blue)'   },
  purple: { bg: 'var(--accent-bg)', fg: 'var(--accent)' },
  orange: { bg: 'var(--amber-bg)',  fg: 'var(--orange)' },
  slate:  { bg: 'var(--surface2)',  fg: 'var(--text2)'  },
}

const BADGE: Record<BadgeVariant, string> = {
  green:  '',
  red:    '',
  amber:  '',
  blue:   '',
  purple: '',
  orange: '',
  slate:  '',
}

export function Badge({
  variant = 'slate',
  children,
  dot,
}: {
  variant?: BadgeVariant
  children: ReactNode
  dot?: boolean
}) {
  const tok = BADGE_TOKENS[variant]
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold uppercase tracking-wider border ${BADGE[variant]}`}
      style={{ background: tok.bg, color: tok.fg, borderColor: tok.fg }}
    >
      {dot && (
        <span
          className="w-1 h-1 rounded-full"
          style={{ background: tok.fg, boxShadow: `0 0 4px ${tok.fg}` }}
        />
      )}
      {children}
    </span>
  )
}

// ─── StatusDot ────────────────────────────────────────────────────────────

export function StatusDot({ ok, label }: { ok: boolean; label?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium ${ok ? 'text-emerald-700' : 'text-red-700'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-500 status-live' : 'bg-red-500'}`} />
      {label ?? (ok ? 'Healthy' : 'Issues')}
    </span>
  )
}

// ─── Card ─────────────────────────────────────────────────────────────────

type CardVariant = 'default' | 'elevated' | 'inset'

const CARD_STYLES: Record<CardVariant, string> = {
  default:  'bg-[var(--surface)] border border-[var(--border)] card-shadow',
  elevated: 'bg-[var(--surface)] border border-[var(--border)] card-shadow-lg',
  inset:    'bg-[var(--surface2)] border border-[var(--border)]',
}

export function Card({
  children,
  className = '',
  variant = 'default',
}: {
  children: ReactNode
  className?: string
  variant?: CardVariant
}) {
  return (
    <div className={`rounded-lg ${CARD_STYLES[variant]} ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  sub,
  action,
}: {
  title: string
  sub?: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border)]">
      <div className="min-w-0">
        <h2 className="text-[13px] font-semibold text-[var(--text)] tracking-tight leading-tight">{title}</h2>
        {sub && <p className="text-[12px] text-[var(--muted)] mt-0.5 truncate">{sub}</p>}
      </div>
      {action && <div className="ml-4 shrink-0">{action}</div>}
    </div>
  )
}

// ─── CopyButton ───────────────────────────────────────────────────────────

export function CopyButton({ value, className = '' }: { value: string; className?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(value).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={copy}
      title="Copy"
      className={`p-1 rounded hover:bg-[var(--surface3)] transition-colors text-[var(--muted3)] hover:text-[var(--text2)] ${className}`}
    >
      {copied
        ? <Check size={10} className="text-emerald-600" />
        : <Copy size={10} />}
    </button>
  )
}

// ─── Hash display ─────────────────────────────────────────────────────────

export function Hash({ value, full = false }: { value: string; full?: boolean }) {
  if (!value) return null
  const display = full ? value : `${value.slice(0, 8)}…${value.slice(-4)}`
  return (
    <span className="inline-flex items-center gap-1 group">
      <code className="mono-pill" title={value}>
        {display}
      </code>
      <span className="opacity-0 group-hover:opacity-100 transition-opacity">
        <CopyButton value={value} />
      </span>
    </span>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}

export function SkeletonCard() {
  return (
    <Card className="p-5 space-y-3">
      <Skeleton className="h-7 w-7 rounded-md" />
      <Skeleton className="h-6 w-14 rounded" />
      <Skeleton className="h-2.5 w-24 rounded" />
    </Card>
  )
}

// ─── EmptyState ───────────────────────────────────────────────────────────

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center select-none">
      <div className="w-11 h-11 rounded-lg border border-[var(--border)] bg-[var(--surface2)] flex items-center justify-center text-[var(--muted)] mb-4">
        {icon}
      </div>
      <p className="text-[13.5px] font-semibold text-[var(--text)] tracking-tight">{title}</p>
      {description && (
        <p className="text-[12.5px] text-[var(--muted)] mt-1.5 max-w-sm leading-relaxed">{description}</p>
      )}
    </div>
  )
}

// ─── Alert ────────────────────────────────────────────────────────────────
// Calibrado para dark theme: borde + tint translúcido del color status,
// texto del propio status. Sin chocar con el fondo oscuro.

const ALERT_STYLES = {
  error:   { Icon: XCircle,       color: 'var(--red)',    bg: 'var(--red-bg)' },
  warning: { Icon: AlertTriangle, color: 'var(--amber)',  bg: 'var(--amber-bg)' },
  info:    { Icon: AlertCircle,   color: 'var(--blue)',   bg: 'var(--blue-bg)' },
}

export function Alert({
  variant = 'info',
  children,
}: {
  variant?: 'error' | 'warning' | 'info'
  children: ReactNode
}) {
  const s = ALERT_STYLES[variant]
  const Icon = s.Icon
  return (
    <div
      className="flex items-start gap-3 border rounded-lg px-4 py-3 text-[13px]"
      style={{ background: s.bg, borderColor: s.color, color: s.color }}
    >
      <Icon size={14} className="mt-0.5 shrink-0 opacity-95" />
      <div className="leading-relaxed">{children}</div>
    </div>
  )
}

// ─── PageHeader ───────────────────────────────────────────────────────────

export function PageHeader({
  title,
  description,
  tag,
  action,
}: {
  title: string
  description?: string
  tag?: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 pb-1 mb-1">
      <div className="min-w-0">
        {tag && (
          <p className="text-[10px] font-bold text-[var(--accent2)] uppercase tracking-[0.16em] mb-2">
            {tag}
          </p>
        )}
        <h1 className="text-[22px] font-bold text-[var(--text)] tracking-tight leading-tight">
          {title}
        </h1>
        {description && (
          <p className="text-[var(--muted)] text-[13.5px] mt-1.5 leading-relaxed max-w-2xl">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0 mt-0.5">{action}</div>}
    </div>
  )
}

// ─── SectionLabel ─────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-[0.14em] mb-3 mt-1">
      {children}
    </p>
  )
}

// ─── Divider ──────────────────────────────────────────────────────────────

export function Divider({ className = '' }: { className?: string }) {
  return <div className={`border-t border-[var(--border)] ${className}`} />
}

// ─── InfoRow ──────────────────────────────────────────────────────────────

export function InfoRow({
  label,
  children,
  mono = false,
}: {
  label: string
  children: ReactNode
  mono?: boolean
}) {
  return (
    <div className="grid grid-cols-[150px_1fr] items-start gap-3 py-2.5 border-b border-[var(--border)] last:border-0">
      <span className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-[0.10em] pt-0.5">
        {label}
      </span>
      <span className={`text-[13px] text-[var(--text2)] break-all ${mono ? 'font-mono text-[11.5px] text-[var(--muted2)]' : ''}`}>
        {children ?? <span className="text-[var(--muted3)]">—</span>}
      </span>
    </div>
  )
}

// ─── OfflineState ─────────────────────────────────────────────────────────
// Estado para páginas operator que requieren backend cuando se cargan
// en GH Pages u otro entorno sin /api. Vibe cypherpunk: ServerCrash icon,
// borde violet con glow, panel con el comando para arrancar aip-web,
// CTA al portal público que sí funciona sin backend.

export function OfflineState({
  title,
  body,
  detail,
}: {
  title: string
  body: string
  detail?: string
}) {
  return (
    <div className="max-w-2xl mx-auto py-12 animate-in">
      <div
        className="rounded-lg border p-7 relative overflow-hidden"
        style={{
          background: 'var(--surface)',
          borderColor: 'var(--accent-line)',
          boxShadow: '0 0 24px rgba(167,139,250,0.10), 0 0 0 1px rgba(167,139,250,0.05) inset',
        }}
      >
        <div className="aurora-backdrop" style={{ opacity: 0.5 }} />

        <div className="relative">
          <div className="flex items-center gap-3 mb-5">
            <div
              className="w-10 h-10 rounded-md flex items-center justify-center shrink-0"
              style={{
                background: 'var(--accent-bg)',
                border: '1px solid var(--accent-line)',
              }}
            >
              <ServerCrash size={18} style={{ color: 'var(--accent)' }} strokeWidth={1.8} />
            </div>
            <div>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] mb-1" style={{ color: 'var(--accent)' }}>
                no backend · offline
              </p>
              <h3 className="text-[15px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
                {title}
              </h3>
            </div>
          </div>

          <p className="text-[13px] leading-relaxed mb-5" style={{ color: 'var(--text2)' }}>
            {body}
          </p>

          {detail && (
            <p className="text-[12px] leading-relaxed mb-5" style={{ color: 'var(--muted)' }}>
              {detail}
            </p>
          )}

          <div
            className="rounded-md p-3 mb-6 font-mono text-[11.5px]"
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border2)',
              color: 'var(--text2)',
            }}
          >
            <div className="flex items-center gap-1.5 mb-2 pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
              <Terminal size={11} style={{ color: 'var(--signal)' }} />
              <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                arranca el backend local
              </span>
            </div>
            <div className="space-y-1">
              <div><span style={{ color: 'var(--muted)' }}># desde la raíz del repo</span></div>
              <div>
                <span style={{ color: 'var(--signal)' }}>$</span> <span style={{ color: 'var(--accent)' }}>pip install</span> <span>-e <span style={{ color: 'var(--green)' }}>'.[web]'</span></span>
              </div>
              <div>
                <span style={{ color: 'var(--signal)' }}>$</span> <span style={{ color: 'var(--accent)' }}>aip-web</span> --archive <span style={{ color: 'var(--green)' }}>./docs/demo/demo_archive</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/portal"
              className="group inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-[12.5px] font-semibold transition-all border"
              style={{
                background: 'var(--accent2)',
                borderColor: 'var(--accent)',
                color: '#fff',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 0 20px rgba(167,139,250,0.5)' }}
              onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none' }}
            >
              ir al portal público
              <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              to="/"
              className="text-[12px] font-medium transition-colors"
              style={{ color: 'var(--muted)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--muted)' }}
            >
              volver al inicio
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
