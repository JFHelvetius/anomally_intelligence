import { useState, ReactNode } from 'react'
import { Copy, Check, AlertTriangle, AlertCircle, XCircle } from 'lucide-react'

// ─── Badge — light theme, restrained ──────────────────────────────────────

type BadgeVariant = 'green' | 'red' | 'amber' | 'blue' | 'purple' | 'orange' | 'slate'

const BADGE: Record<BadgeVariant, string> = {
  green:  'bg-emerald-50 text-emerald-700 border-emerald-200',
  red:    'bg-red-50     text-red-700     border-red-200',
  amber:  'bg-amber-50   text-amber-700   border-amber-200',
  blue:   'bg-blue-50    text-blue-700    border-blue-200',
  purple: 'bg-violet-50  text-violet-700  border-violet-200',
  orange: 'bg-orange-50  text-orange-700  border-orange-200',
  slate:  'bg-slate-100  text-slate-700   border-slate-200',
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
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] text-[10.5px] font-semibold uppercase tracking-wider border ${BADGE[variant]}`}>
      {dot && (
        <span
          className={`w-1 h-1 rounded-full ${
            variant === 'green'  ? 'bg-emerald-500' :
            variant === 'amber'  ? 'bg-amber-500'   :
            variant === 'red'    ? 'bg-red-500'     :
            variant === 'blue'   ? 'bg-blue-500'    :
            variant === 'purple' ? 'bg-violet-500'  :
            variant === 'orange' ? 'bg-orange-500'  :
            'bg-slate-500'
          }`}
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

const ALERT_STYLES = {
  error:   { bg: 'bg-red-50     border-red-200',     text: 'text-red-800',     Icon: XCircle },
  warning: { bg: 'bg-amber-50   border-amber-200',   text: 'text-amber-800',   Icon: AlertTriangle },
  info:    { bg: 'bg-blue-50    border-blue-200',    text: 'text-blue-800',    Icon: AlertCircle },
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
    <div className={`flex items-start gap-3 border rounded-lg px-4 py-3 text-[13px] ${s.bg} ${s.text}`}>
      <Icon size={14} className="mt-0.5 shrink-0 opacity-85" />
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
