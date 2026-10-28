import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AppShell } from './shell'
import { resetMemoryFallback, safeStorage } from './storage'
import { getMetrics } from './metrics'

const PAGES = [
  { id: 'dashboard', label: 'Dashboard', render: () => <p>dash-content</p> },
  { id: 'analysis', label: 'Analysis', render: () => <p>analysis-content</p> },
]

const STORE = safeStorage()

function shell(storage = STORE) {
  return <AppShell slug="test-app" title="Test App" subtitle="A test" pages={PAGES} storage={storage} footer={<p>footer-content</p>} />
}

beforeEach(() => {
  resetMemoryFallback()
  STORE.removeItem('qd:test-app:metrics')
  STORE.removeItem('qd:test-app:theme')
  window.location.hash = ''
  document.documentElement.removeAttribute('data-theme')
})

describe('AppShell navigation', () => {
  it('renders the nav with app pages plus Metrics (and no Admin), first page active', () => {
    render(shell())
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    for (const label of ['Dashboard', 'Analysis', 'Metrics']) {
      expect(nav).toContainElement(screen.getByRole('link', { name: label }))
    }
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
    expect(screen.getByText('dash-content')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })
  it('switches pages on nav click and updates the hash', () => {
    render(shell())
    fireEvent.click(screen.getByRole('link', { name: 'Analysis' }))
    expect(screen.getByText('analysis-content')).toBeInTheDocument()
    expect(screen.queryByText('dash-content')).not.toBeInTheDocument()
    expect(window.location.hash).toBe('#/analysis')
  })
  it('opens the page named by the URL hash, and falls back to the first page for an unknown hash', () => {
    window.location.hash = '#/analysis'
    const { unmount } = render(shell())
    expect(screen.getByText('analysis-content')).toBeInTheDocument()
    unmount()
    window.location.hash = '#/admin'
    render(shell())
    expect(screen.getByText('dash-content')).toBeInTheDocument()
  })
  it('tracks a pageview metric per visited route', () => {
    render(shell())
    fireEvent.click(screen.getByRole('link', { name: 'Analysis' }))
    const m = getMetrics('test-app', STORE)
    expect(m.counters['view.dashboard']).toBeGreaterThanOrEqual(1)
    expect(m.counters['view.analysis']).toBeGreaterThanOrEqual(1)
  })
  it('renders the footer on every page, including Metrics', () => {
    render(shell())
    expect(screen.getByText('footer-content')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'Metrics' }))
    expect(screen.getByText('footer-content')).toBeInTheDocument()
  })
})

describe('Theme toggle', () => {
  it('renders top-right, toggles corporate/dark on the document element, persists, and tracks', () => {
    render(shell())
    const btn = screen.getByRole('button', { name: 'Switch to corporate theme' })
    fireEvent.click(btn)
    expect(document.documentElement.getAttribute('data-theme')).toBe('corporate')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
    expect(STORE.getItem('qd:test-app:theme')).toBe('corporate')
    expect(getMetrics('test-app', STORE).counters['theme.toggle']).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
  it('honors a stored theme preference on mount', () => {
    STORE.setItem('qd:test-app:theme', 'corporate')
    render(shell())
    expect(document.documentElement.getAttribute('data-theme')).toBe('corporate')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
  })
})

describe('Metrics page', () => {
  it('shows counters accumulated from navigation, and resets', () => {
    render(shell())
    fireEvent.click(screen.getByRole('link', { name: 'Analysis' }))
    fireEvent.click(screen.getByRole('link', { name: 'Metrics' }))
    // The Metrics page lists the views recorded before it was opened (its own view is counted after it renders).
    expect(screen.getAllByText('view.dashboard').length).toBeGreaterThan(0)
    expect(screen.getAllByText('view.analysis').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Reset metrics' }))
    expect(screen.getByText('No events recorded yet.')).toBeInTheDocument()
  })
})
