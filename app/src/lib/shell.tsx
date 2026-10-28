/**
 * App shell: primary navigation (hash-routed), theme toggle, Metrics page and an optional footer.
 * Markup is fixed and semantic; each app's stylesheet decides the visual identity
 * (top bar vs left rail, palette, type) purely via CSS on the shell-* classes.
 */
import { useState, useEffect, type ReactNode } from 'react'
import { safeStorage, type StorageLike } from './storage'
import { getMetrics, resetMetrics, track } from './metrics'
import { applyTheme, getStoredTheme, setStoredTheme, type ThemeName } from './theme'

export interface ShellPage {
  id: string
  label: string
  render: () => ReactNode
}

function readRoute(fallback: string): string {
  const m = /^#\/([a-z0-9-]+)/i.exec(window.location.hash)
  return m ? m[1] : fallback
}

export function AppShell({
  slug,
  title,
  subtitle,
  pages,
  footer,
  storage = safeStorage(),
  defaultTheme = 'dark',
}: {
  slug: string
  title: string
  subtitle?: string
  pages: ShellPage[]
  /** Rendered below every page (e.g. the data-contract status line). */
  footer?: ReactNode
  storage?: StorageLike | null
  defaultTheme?: ThemeName
}) {
  const fallback = pages[0]?.id ?? 'metrics'
  const [theme, setTheme] = useState<ThemeName>(() => getStoredTheme(slug, storage) ?? defaultTheme)
  useEffect(() => {
    applyTheme(theme)
  }, [theme])
  const toggleTheme = () => {
    const next: ThemeName = theme === 'dark' ? 'corporate' : 'dark'
    setTheme(next)
    setStoredTheme(slug, next, storage)
    track(slug, 'theme.toggle', { to: next }, { storage })
  }
  const [route, setRoute] = useState(() => readRoute(fallback))
  useEffect(() => {
    const on = () => setRoute(readRoute(fallback))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [fallback])
  useEffect(() => {
    track(slug, `view.${route}`, undefined, { storage })
  }, [slug, route, storage])

  const navItems = [...pages.map((p) => ({ id: p.id, label: p.label })), { id: 'metrics', label: 'Metrics' }]
  const activeId = navItems.some((n) => n.id === route) ? route : fallback
  const activePage = pages.find((p) => p.id === activeId)

  const go = (id: string) => (e: { preventDefault: () => void }) => {
    e.preventDefault()
    if (window.location.hash !== `#/${id}`) window.location.hash = `#/${id}`
    setRoute(id)
  }

  return (
    <div className="shell">
      <header className="shell-head">
        <div className="shell-brand">
          <h1>{title}</h1>
          {subtitle && <p className="sub">{subtitle}</p>}
        </div>
        <div className="shell-right">
          <nav className="shell-nav" aria-label="Primary">
            {navItems.map((n) => (
              <a key={n.id} href={`#/${n.id}`} onClick={go(n.id)} aria-current={n.id === activeId ? 'page' : undefined} className={n.id === activeId ? 'active' : ''}>
                {n.label}
              </a>
            ))}
          </nav>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to corporate theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Corporate theme' : 'Dark theme'}
          >
            {theme === 'dark' ? (
              /* sun glyph: switch to corporate (light) */
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
                <circle cx="7.5" cy="7.5" r="3.2" />
                <path d="M7.5 0.8v1.8M7.5 12.4v1.8M0.8 7.5h1.8M12.4 7.5h1.8M2.8 2.8l1.3 1.3M10.9 10.9l1.3 1.3M12.2 2.8l-1.3 1.3M4.1 10.9l-1.3 1.3" />
              </svg>
            ) : (
              /* moon glyph: switch to dark */
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
                <path d="M12.8 9.2A5.7 5.7 0 1 1 5.8 2.2a4.6 4.6 0 0 0 7 7z" />
              </svg>
            )}
          </button>
        </div>
      </header>
      <main className="shell-main">{activeId === 'metrics' ? <MetricsPage slug={slug} storage={storage} /> : activePage?.render()}</main>
      {footer}
    </div>
  )
}

export function MetricsPage({ slug, storage }: { slug: string; storage: StorageLike | null }) {
  // getMetrics is cheap; calling it per render keeps the page current, and the
  // state bump below exists purely to trigger a re-render on Reset/Refresh.
  const [, bump] = useState(0)
  const m = getMetrics(slug, storage)
  const rows = Object.entries(m.counters).sort((a, b) => b[1] - a[1])
  const recent = m.events.slice(-20).reverse()
  return (
    <section className="metrics">
      <h2>Metrics — this app, this browser</h2>
      <p className="sub">
        Page views and timings recorded locally (localStorage, namespaced to <code>{slug}</code>). Nothing is sent anywhere; the numbers stay
        in this browser.
      </p>
      <div className="grid">
        <div className="stat">
          <div className="k">Distinct metrics</div>
          <div className="v">{rows.length}</div>
        </div>
        <div className="stat">
          <div className="k">Total events</div>
          <div className="v">{rows.reduce((a, [, n]) => a + n, 0)}</div>
        </div>
        <div className="stat">
          <div className="k">Recorded since</div>
          <div className="v">{m.since === null ? '—' : new Date(m.since).toLocaleString()}</div>
        </div>
      </div>
      <h2>Counters</h2>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Count</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={2}>No events recorded yet.</td>
              </tr>
            ) : (
              rows.map(([name, n]) => (
                <tr key={name}>
                  <td className="num">{name}</td>
                  <td className="num">{n}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <h2>Recent events</h2>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Event</th>
              <th>Props</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((e, i) => (
              <tr key={`${e.at}-${i}`}>
                <td className="num">{new Date(e.at).toLocaleTimeString()}</td>
                <td className="num">{e.name}</td>
                <td className="num">{e.props ? JSON.stringify(e.props) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="controls">
        <button
          onClick={() => {
            resetMetrics(slug, storage)
            bump((t) => t + 1)
          }}
        >
          Reset metrics
        </button>
        <button onClick={() => bump((t) => t + 1)}>Refresh</button>
      </div>
    </section>
  )
}
