import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Link2, Shield, Layers,
  FolderSearch, ChevronRight, ScanSearch, Globe2, Info,
} from 'lucide-react'
import { useT, useI18n } from '../i18n'
import type { TKey } from '../i18n/en'

// Dark-sidebar-tuned language switcher (the default one's colors are
// tuned for a light bg). Lives here to keep the visual contract local.
function SidebarLanguageSwitcher() {
  const { lang, setLang } = useI18n()
  const next = lang === 'en' ? 'es-ES' : 'en'
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      className="inline-flex items-center gap-1.5 font-mono uppercase tracking-wider transition-colors"
      style={{ color: 'var(--sidebar-muted)', fontSize: '10px' }}
      title={`Switch to ${next === 'en' ? 'English' : 'Español'}`}
    >
      <span style={{ opacity: 0.85 }}>{lang}</span>
      <span style={{ opacity: 0.5 }}>→</span>
      <span style={{ color: 'var(--sidebar-text)' }}>{next}</span>
    </button>
  )
}

// ─── Navigation structure ─────────────────────────────────────────────────

interface NavItem {
  to: string
  labelKey: TKey
  icon: typeof LayoutDashboard
  end?: boolean
}

interface NavGroup {
  labelKey: TKey
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    labelKey: 'nav.group.archive',
    items: [
      { to: '/',          labelKey: 'nav.item.about',    icon: Info,            end: true },
      { to: '/dashboard', labelKey: 'nav.item.overview', icon: LayoutDashboard },
    ],
  },
  {
    labelKey: 'nav.group.investigation',
    items: [
      { to: '/cases',    labelKey: 'nav.item.cases',    icon: FolderSearch },
      { to: '/evidence', labelKey: 'nav.item.evidence', icon: FileText },
    ],
  },
  {
    labelKey: 'nav.group.custody',
    items: [
      { to: '/audit-log',    labelKey: 'nav.item.audit',        icon: Link2 },
      { to: '/attestations', labelKey: 'nav.item.attestations', icon: Shield },
      { to: '/derived',      labelKey: 'nav.item.derived',      icon: Layers },
    ],
  },
  {
    labelKey: 'nav.group.public',
    items: [
      { to: '/portal', labelKey: 'nav.item.portal', icon: Globe2 },
    ],
  },
  {
    labelKey: 'nav.group.ai',
    items: [
      { to: '/analyze', labelKey: 'nav.item.analyze', icon: ScanSearch },
    ],
  },
]

const CRUMB: Record<string, TKey> = {
  '':             'nav.item.about',
  'about':        'nav.item.about',
  'dashboard':    'nav.item.overview',
  'cases':        'nav.item.cases',
  'evidence':     'nav.item.evidence',
  'audit-log':    'nav.item.audit',
  'attestations': 'nav.item.attestations',
  'derived':      'nav.item.derived',
  'analyze':      'nav.item.analyze',
  'portal':       'nav.item.portal',
}

// ─── Layout ───────────────────────────────────────────────────────────────

export default function Layout() {
  const t = useT()
  const loc = useLocation()
  const segments = loc.pathname.split('/').filter(Boolean)
  const crumbs = segments.map((s, i) => {
    const key = CRUMB[s]
    return {
      label: key ? t(key) : s.slice(0, 20),
      path:  '/' + segments.slice(0, i + 1).join('/'),
    }
  })

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>

      {/* ── Sidebar — dark surface, anchors the layout ──────────── */}
      <aside
        className="w-[240px] shrink-0 flex flex-col"
        style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--sidebar-border)' }}
      >

        {/* Brand */}
        <div
          className="px-5 py-[18px]"
          style={{ borderBottom: '1px solid var(--sidebar-border)' }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-[26px] h-[26px] rounded-md flex items-center justify-center font-bold text-[10px] tracking-tight shrink-0"
              style={{
                background: 'var(--accent)',
                color: '#fff',
                boxShadow: '0 0 0 1px rgba(255,255,255,0.05) inset',
              }}
            >
              AIP
            </div>
            <div className="min-w-0 leading-tight">
              <p
                className="text-[12.5px] font-semibold tracking-tight"
                style={{ color: 'var(--sidebar-text)' }}
              >
                {t('app.brand.name')}
              </p>
              <p
                className="text-[9.5px] mt-0.5 font-semibold uppercase tracking-[0.14em]"
                style={{ color: 'var(--sidebar-muted2)' }}
              >
                {t('app.brand.tagline')}
              </p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto space-y-4">
          {NAV_GROUPS.map(group => (
            <div key={group.labelKey}>
              <p
                className="text-[9.5px] font-bold uppercase tracking-[0.14em] px-2 mb-1.5"
                style={{ color: 'var(--sidebar-muted2)' }}
              >
                {t(group.labelKey)}
              </p>

              <div className="space-y-px">
                {group.items.map(({ to, labelKey, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      `nav-item flex items-center gap-2.5 px-2 py-1.5 rounded-[5px] text-[12.5px] cursor-pointer select-none ${
                        isActive ? 'nav-active' : ''
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          size={13}
                          strokeWidth={isActive ? 2 : 1.75}
                          style={{ color: isActive ? 'var(--sidebar-active)' : 'var(--sidebar-muted)' }}
                        />
                        <span
                          className="leading-none"
                          style={{ color: isActive ? 'var(--sidebar-active)' : 'var(--sidebar-text)' }}
                        >
                          {t(labelKey)}
                        </span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div
          className="px-4 py-3"
          style={{ borderTop: '1px solid var(--sidebar-border)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full status-live" style={{ background: '#10b981' }} />
              <span
                className="text-[9.5px] uppercase tracking-[0.13em] font-semibold"
                style={{ color: 'var(--sidebar-muted)' }}
              >
                {t('app.live.label')}
              </span>
            </div>
            <span
              className="text-[9.5px] font-mono"
              style={{ color: 'var(--sidebar-muted2)' }}
            >
              :8000
            </span>
          </div>
          <div
            className="flex items-center justify-between text-[9.5px] font-mono mb-2.5"
            style={{ color: 'var(--sidebar-muted2)' }}
          >
            <span>v0.2.1</span>
            <span>ADR-0042</span>
          </div>
          <div
            className="pt-2.5 border-t"
            style={{ borderColor: 'var(--sidebar-border)' }}
          >
            <SidebarLanguageSwitcher />
          </div>
        </div>
      </aside>

      {/* ── Main ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Topbar */}
        <header
          className="h-10 shrink-0 flex items-center px-6 gap-1.5"
          style={{ background: 'var(--bg2)', borderBottom: '1px solid var(--border)' }}
        >
          <NavLink
            to="/"
            className="text-[10.5px] font-bold uppercase tracking-[0.14em] transition-colors hover:text-[var(--text)]"
            style={{ color: 'var(--muted2)' }}
          >
            AIP
          </NavLink>

          {crumbs.map((c, i) => (
            <span key={c.path} className="flex items-center gap-1.5">
              <ChevronRight size={10} style={{ color: 'var(--muted3)' }} />
              {i === crumbs.length - 1 ? (
                <span className="text-[11.5px] font-semibold" style={{ color: 'var(--text)' }}>
                  {c.label}
                </span>
              ) : (
                <NavLink
                  to={c.path}
                  className="text-[11.5px] font-medium transition-colors hover:text-[var(--text)]"
                  style={{ color: 'var(--muted2)' }}
                >
                  {c.label}
                </NavLink>
              )}
            </span>
          ))}

          {/* Env indicator */}
          <div className="ml-auto">
            <span
              className="text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded uppercase tracking-[0.14em]"
              style={{
                background: 'var(--surface3)',
                color: 'var(--muted2)',
                border: '1px solid var(--border)',
              }}
            >
              DEV
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto" style={{ background: 'var(--bg)' }}>
          <div className="max-w-6xl mx-auto px-10 py-10 animate-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
