import { Link } from 'react-router-dom'
import {
  ShieldCheck, FileSearch, Layers3, GitCompare, Network, Anchor,
  ArrowRight, FileCode2, BookOpen, ExternalLink,
  Check, X, Hash, Eye, Globe2, ScrollText, Code2,
} from 'lucide-react'
import { useT } from '../i18n'
import type { TKey } from '../i18n/en'

const REPO_URL = 'https://github.com/JFHelvetius/anomally_intelligence'
const DEMO_REPORT_URL = '/demo-report.html'
const SCHEMAS_URL = `${REPO_URL}/tree/main/docs/schemas`
const ADRS_URL = `${REPO_URL}/tree/main/docs/adr`

// ────────────────────────────────────────────────────────────────────────────
// Visual primitives — consistent rhythm across the page.
// All sections share: 11px eyebrow / 17px heading / 12.5px body.
// All cards share: var(--surface) bg + var(--border) border + p-5.
// ────────────────────────────────────────────────────────────────────────────

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string
  title?: string
  children: React.ReactNode
}) {
  return (
    <section className="mb-14">
      {(eyebrow || title) && (
        <header className="mb-6">
          {eyebrow && (
            <p
              className="text-[10.5px] font-bold uppercase tracking-[0.16em] mb-1.5"
              style={{ color: 'var(--muted3)' }}
            >
              {eyebrow}
            </p>
          )}
          {title && (
            <h2
              className="text-[17px] font-semibold tracking-tight leading-tight"
              style={{ color: 'var(--text)' }}
            >
              {title}
            </h2>
          )}
        </header>
      )}
      {children}
    </section>
  )
}

function Surface({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={`rounded-lg border ${className}`}
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      {children}
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────────────────────

export default function About() {
  const t = useT()

  return (
    <div className="max-w-5xl">
      {/* ── Hero — tinted block with violet accent line ────────────── */}
      <header
        className="relative overflow-hidden rounded-xl border mb-14 px-9 py-10"
        style={{
          background: 'linear-gradient(135deg, var(--surface-tint) 0%, var(--bg2) 60%)',
          borderColor: 'var(--border)',
        }}
      >
        {/* Left accent rail */}
        <div
          className="absolute left-0 top-6 bottom-6 w-[3px] rounded-r-sm"
          style={{ background: 'var(--accent)' }}
        />

        {/* Decorative gradient orb (subtle, behind the title) */}
        <div
          className="absolute -top-24 -right-16 w-72 h-72 rounded-full opacity-50 pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(124,58,237,0.10) 0%, rgba(124,58,237,0) 70%)',
          }}
        />

        <div className="relative">
          <div className="flex items-center gap-2 mb-4">
            <span
              className="text-[10.5px] font-bold uppercase tracking-[0.18em]"
              style={{ color: 'var(--accent2)' }}
            >
              v0.2.1
            </span>
            <span style={{ color: 'var(--muted3)' }}>·</span>
            <span className="text-[10.5px] font-bold uppercase tracking-[0.18em]" style={{ color: 'var(--muted2)' }}>
              {t('about.pill.license')}
            </span>
            <span style={{ color: 'var(--muted3)' }}>·</span>
            <span className="text-[10.5px] font-bold uppercase tracking-[0.18em]" style={{ color: 'var(--muted2)' }}>
              {t('about.pill.adrs')}
            </span>
          </div>

          <h1
            className="text-[32px] font-semibold tracking-tight leading-[1.1] mb-4 max-w-3xl"
            style={{ color: 'var(--text)' }}
          >
            {t('about.hero.title')}
          </h1>

          <p
            className="text-[15.5px] leading-relaxed max-w-2xl mb-3"
            style={{ color: 'var(--muted2)' }}
          >
            {t('about.hero.lead')}{' '}
            <span style={{ color: 'var(--text)', fontWeight: 600 }}>
              {t('about.hero.leadStrong')}
            </span>
            {t('about.hero.leadTail')}
          </p>

          <p
            className="text-[13.5px] leading-relaxed max-w-2xl"
            style={{ color: 'var(--muted)' }}
          >
            {t('about.hero.sub')}
          </p>

          <div className="flex flex-wrap items-center gap-1 mt-8">
            <a
              href={DEMO_REPORT_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md text-[13px] font-semibold transition-colors mr-2 shadow-sm hover:shadow-md"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Eye size={13} strokeWidth={2.25} />
              {t('about.hero.cta.demo')}
              <ArrowRight size={12} />
            </a>
            <TextLink href={ADRS_URL} external icon={BookOpen}>
              {t('about.hero.cta.adrs')}
            </TextLink>
            <TextLink href={REPO_URL} external icon={Code2}>
              {t('about.hero.cta.github')}
            </TextLink>
          </div>
        </div>
      </header>

      {/* ── Problem / answer / limits ─────────────────────────────────── */}
      <Section
        eyebrow={t('about.section.solves.eyebrow')}
        title={t('about.section.solves.title')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <PrincipleCard
            label={t('about.solves.problem.badge')}
            title={t('about.solves.problem.title')}
            body={t('about.solves.problem.body')}
          />
          <PrincipleCard
            label={t('about.solves.answer.badge')}
            title={t('about.solves.answer.title')}
            body={t('about.solves.answer.body')}
            accent
          />
          <PrincipleCard
            label={t('about.solves.limits.badge')}
            title={t('about.solves.limits.title')}
            body={t('about.solves.limits.body')}
          />
        </div>
      </Section>

      {/* ── The 5 crypto layers ───────────────────────────────────────── */}
      <Section
        eyebrow={t('about.section.layers.eyebrow')}
        title={t('about.section.layers.title')}
      >
        <Surface>
          <div className="grid grid-cols-1 md:grid-cols-5 divide-y md:divide-y-0 md:divide-x" style={{ borderColor: 'var(--border)' }}>
            <LayerCell n={1} Icon={Hash}        titleKey="about.layer.audit.title"     bodyKey="about.layer.audit.body" />
            <LayerCell n={2} Icon={ScrollText}  titleKey="about.layer.manifest.title"  bodyKey="about.layer.manifest.body" />
            <LayerCell n={3} Icon={ShieldCheck} titleKey="about.layer.capture.title"   bodyKey="about.layer.capture.body" />
            <LayerCell n={4} Icon={Network}     titleKey="about.layer.witnesses.title" bodyKey="about.layer.witnesses.body" />
            <LayerCell n={5} Icon={Anchor}      titleKey="about.layer.bitcoin.title"   bodyKey="about.layer.bitcoin.body" />
          </div>
        </Surface>
      </Section>

      {/* ── 8 differentiators — dense 4-col grid, no colors ──────────── */}
      <Section
        eyebrow={t('about.section.properties.eyebrow')}
        title={t('about.section.properties.title')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-7">
          {(['01','02','03','04','05','06','07','08'] as const).map(n => (
            <PropertyRow
              key={n}
              n={n}
              titleKey={`about.props.${n}.title` as TKey}
              bodyKey={`about.props.${n}.body` as TKey}
            />
          ))}
        </div>
      </Section>

      {/* ── Honesty: side-by-side compact lists ──────────────────────── */}
      <Section
        eyebrow={t('about.section.honesty.eyebrow')}
        title={t('about.section.honesty.title')}
      >
        <Surface>
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x" style={{ borderColor: 'var(--border)' }}>
            <HonestyColumn
              tone="ok"
              headingKey="about.honesty.does.heading"
              itemKeys={[
                'about.honesty.does.01', 'about.honesty.does.02', 'about.honesty.does.03',
                'about.honesty.does.04', 'about.honesty.does.05', 'about.honesty.does.06',
              ]}
            />
            <HonestyColumn
              tone="warn"
              headingKey="about.honesty.does_not.heading"
              itemKeys={[
                'about.honesty.does_not.01', 'about.honesty.does_not.02', 'about.honesty.does_not.03',
                'about.honesty.does_not.04', 'about.honesty.does_not.05', 'about.honesty.does_not.06',
              ]}
            />
          </div>
        </Surface>
      </Section>

      {/* ── Try it + Where to next, merged into one row ─────────────── */}
      <Section
        eyebrow={t('about.section.try.eyebrow')}
        title={t('about.section.try.title')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-10">
          <TryCard
            Icon={Eye}
            titleKey="about.try.demo.title"
            bodyKey="about.try.demo.body"
            ctaKey="about.try.demo.cta"
            href={DEMO_REPORT_URL}
            external
          />
          <TryCard
            Icon={Globe2}
            titleKey="about.try.portal.title"
            bodyKey="about.try.portal.body"
            ctaKey="about.try.portal.cta"
            href="/portal"
          />
          <TryCard
            Icon={FileCode2}
            titleKey="about.try.schemas.title"
            bodyKey="about.try.schemas.body"
            ctaKey="about.try.schemas.cta"
            href={SCHEMAS_URL}
            external
          />
        </div>

        <p
          className="text-[10.5px] font-bold uppercase tracking-[0.16em] mb-3"
          style={{ color: 'var(--muted3)' }}
        >
          {t('about.section.where.title')}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <InternalLink to="/dashboard" Icon={Layers3}     titleKey="about.where.dashboard.title" bodyKey="about.where.dashboard.body" />
          <InternalLink to="/evidence"  Icon={FileSearch}  titleKey="about.where.evidence.title"  bodyKey="about.where.evidence.body" />
          <InternalLink to="/audit-log" Icon={GitCompare}  titleKey="about.where.audit.title"     bodyKey="about.where.audit.body" />
        </div>
      </Section>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer
        className="mt-16 pt-6 border-t text-[12px] leading-relaxed max-w-3xl"
        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
      >
        {t('about.footer.preamble')}{' '}
        <a
          href={ADRS_URL}
          target="_blank"
          rel="noreferrer"
          className="font-semibold underline underline-offset-2 inline-flex items-center gap-1"
          style={{ color: 'var(--text)' }}
        >
          {t('about.footer.adrs_link')}
          <ExternalLink size={10} />
        </a>
        {t('about.footer.body')}{' '}
        <em>{t('about.footer.question')}</em>{' '}
        {t('about.footer.tail')}{' '}
        <em>{t('about.footer.notQuestion')}</em>.
      </footer>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Local components
// ────────────────────────────────────────────────────────────────────────────

function TextLink({
  href,
  children,
  external,
  icon: Icon,
}: {
  href: string
  children: React.ReactNode
  external?: boolean
  icon: typeof Eye
}) {
  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noreferrer' : undefined}
      className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-md text-[13px] font-medium transition-colors hover:bg-slate-100"
      style={{ color: 'var(--text2)' }}
    >
      <Icon size={13} strokeWidth={1.75} />
      {children}
      {external && <ExternalLink size={10} style={{ color: 'var(--muted)' }} />}
    </a>
  )
}

function PrincipleCard({
  label,
  title,
  body,
  accent,
}: {
  label: string
  title: string
  body: string
  accent?: boolean
}) {
  return (
    <div
      className="rounded-lg border p-5"
      style={{
        background: accent ? 'var(--accent-bg)' : 'var(--surface)',
        borderColor: accent ? 'var(--accent3)' : 'var(--border)',
      }}
    >
      <p
        className="text-[10px] font-bold uppercase tracking-[0.14em] mb-2.5"
        style={{ color: accent ? 'var(--accent2)' : 'var(--muted3)' }}
      >
        {label}
      </p>
      <h3
        className="text-[13.5px] font-semibold tracking-tight mb-2 leading-snug"
        style={{ color: 'var(--text)' }}
      >
        {title}
      </h3>
      <p
        className="text-[12.5px] leading-relaxed"
        style={{ color: 'var(--muted2)' }}
      >
        {body}
      </p>
    </div>
  )
}

function LayerCell({
  n,
  Icon,
  titleKey,
  bodyKey,
}: {
  n: number
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number; style?: React.CSSProperties }>
  titleKey: TKey
  bodyKey: TKey
}) {
  const t = useT()
  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-3">
        <Icon size={16} strokeWidth={1.75} style={{ color: 'var(--text2)' }} />
        <span
          className="text-[10px] font-mono font-bold"
          style={{ color: 'var(--muted3)' }}
        >
          L{n}
        </span>
      </div>
      <h3
        className="text-[12.5px] font-semibold tracking-tight mb-1.5 leading-snug"
        style={{ color: 'var(--text)' }}
      >
        {t(titleKey)}
      </h3>
      <p
        className="text-[11.5px] leading-relaxed"
        style={{ color: 'var(--muted)' }}
      >
        {t(bodyKey)}
      </p>
    </div>
  )
}

function PropertyRow({
  n,
  titleKey,
  bodyKey,
}: {
  n: string
  titleKey: TKey
  bodyKey: TKey
}) {
  const t = useT()
  return (
    <div className="flex gap-4">
      <span
        className="shrink-0 text-[11.5px] font-mono font-bold pt-0.5"
        style={{ color: 'var(--muted3)' }}
      >
        {n}
      </span>
      <div className="min-w-0">
        <h3
          className="text-[13px] font-semibold tracking-tight mb-1 leading-snug"
          style={{ color: 'var(--text)' }}
        >
          {t(titleKey)}
        </h3>
        <p
          className="text-[12.5px] leading-relaxed"
          style={{ color: 'var(--muted)' }}
        >
          {t(bodyKey)}
        </p>
      </div>
    </div>
  )
}

function HonestyColumn({
  tone,
  headingKey,
  itemKeys,
}: {
  tone: 'ok' | 'warn'
  headingKey: TKey
  itemKeys: TKey[]
}) {
  const t = useT()
  const IconC = tone === 'ok' ? Check : X
  const tint = tone === 'ok' ? 'var(--green)' : 'var(--amber)'
  return (
    <div className="p-5">
      <h3
        className="text-[10.5px] font-bold uppercase tracking-[0.14em] mb-3.5"
        style={{ color: tint }}
      >
        {t(headingKey)}
      </h3>
      <ul className="space-y-2.5">
        {itemKeys.map((k, i) => (
          <li key={i} className="flex gap-2.5 text-[12.5px] leading-snug">
            <IconC
              size={13}
              strokeWidth={2.5}
              style={{ color: tint, marginTop: 2, flexShrink: 0 }}
            />
            <span style={{ color: 'var(--text2)' }}>{t(k)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function TryCard({
  Icon,
  titleKey,
  bodyKey,
  ctaKey,
  href,
  external,
}: {
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number; style?: React.CSSProperties }>
  titleKey: TKey
  bodyKey: TKey
  ctaKey: TKey
  href: string
  external?: boolean
}) {
  const t = useT()
  const inner = (
    <>
      <Icon
        size={16}
        strokeWidth={1.75}
        style={{ color: 'var(--text2)', marginBottom: 14 }}
      />
      <h3
        className="text-[13px] font-semibold tracking-tight mb-1.5 leading-snug"
        style={{ color: 'var(--text)' }}
      >
        {t(titleKey)}
      </h3>
      <p
        className="text-[12.5px] leading-relaxed mb-4 flex-1"
        style={{ color: 'var(--muted)' }}
      >
        {t(bodyKey)}
      </p>
      <span
        className="inline-flex items-center gap-1.5 text-[12px] font-semibold"
        style={{ color: 'var(--text)' }}
      >
        {t(ctaKey)}
        {external ? <ExternalLink size={10} /> : <ArrowRight size={11} />}
      </span>
    </>
  )
  const cls = 'rounded-lg border p-5 flex flex-col transition-colors hover:bg-slate-50'
  const sty = { background: 'var(--surface)', borderColor: 'var(--border)' } as const
  return external ? (
    <a href={href} target="_blank" rel="noreferrer" className={cls} style={sty}>
      {inner}
    </a>
  ) : (
    <Link to={href} className={cls} style={sty}>
      {inner}
    </Link>
  )
}

function InternalLink({
  to,
  Icon,
  titleKey,
  bodyKey,
}: {
  to: string
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number; style?: React.CSSProperties }>
  titleKey: TKey
  bodyKey: TKey
}) {
  const t = useT()
  return (
    <Link
      to={to}
      className="rounded-lg border p-4 flex items-start gap-3 transition-colors hover:bg-slate-50"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <Icon size={15} strokeWidth={1.75} style={{ color: 'var(--text2)', marginTop: 2 }} />
      <div className="min-w-0">
        <h3
          className="text-[12.5px] font-semibold tracking-tight mb-0.5 leading-snug"
          style={{ color: 'var(--text)' }}
        >
          {t(titleKey)}
        </h3>
        <p
          className="text-[11.5px] leading-relaxed"
          style={{ color: 'var(--muted)' }}
        >
          {t(bodyKey)}
        </p>
      </div>
      <ArrowRight size={12} className="shrink-0 ml-auto" style={{ color: 'var(--muted3)', marginTop: 4 }} />
    </Link>
  )
}
