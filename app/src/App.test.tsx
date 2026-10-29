import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import App from './App'
import { ARCH_LAYERS } from './lib/architecture'
import { PITCH, PROJECT_TITLE, QUESTIONS } from './lib/studyContent'
import { resetMemoryFallback, safeStorage } from './lib/storage'
import { FUNNEL_DATA_FIXTURE, FUNNEL_FIXTURE } from './test/funnelFixture'
import { IV_MEASURES_DATA_FIXTURE, IV_MEASURES_FIXTURE } from './test/ivMeasuresFixture'
import { jsonFetch, META_DATA_FIXTURE, META_FIXTURE } from './test/metaFixture'

// jsdom has no WebGL: replace the r3f Canvas and drei controls with inert stand-ins.
vi.mock('@react-three/fiber', () => ({ Canvas: () => <div data-testid="r3f-canvas" /> }))
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }))

const STORE = safeStorage()

beforeEach(() => {
  resetMemoryFallback()
  STORE.removeItem('qd:earnings-vol-study:theme')
  STORE.removeItem('qd:earnings-vol-study:metrics')
  window.location.hash = ''
  vi.stubGlobal('fetch', vi.fn(jsonFetch(META_FIXTURE)))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App (integration)', () => {
  it('opens on About with the title, pitch, questions and data sources', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: PROJECT_TITLE })).toBeInTheDocument()
    expect(screen.getAllByText(PITCH).length).toBeGreaterThan(0)
    expect(within(screen.getByRole('list', { name: 'Questions' })).getAllByRole('listitem')).toHaveLength(QUESTIONS.length)
    // The sources table is drawn from data/meta.json (the fixture here), not from a copy in the app.
    const table = await screen.findByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(META_DATA_FIXTURE.data_sources.length + 1)
    expect(within(table).getByRole('link', { name: 'Fixture open source' })).toHaveAttribute('href', 'https://example.com/open')
    expect(screen.getByText(META_DATA_FIXTURE.data_licence.attribution)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Not financial advice' })).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/) // let the footer fetch settle
  })

  it('shows the milestone and source commit from data/meta.json in the footer', async () => {
    render(<App />)
    expect(await screen.findByText(/data contract 0\.3\.0 · milestone M0 · source commit abc1234/)).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('data/meta.json', { cache: 'no-cache' }) // relative URL (works under a sub-path), always revalidated
  })

  it('shows an error in the footer, but keeps the app usable, when meta.json is invalid', async () => {
    vi.stubGlobal('fetch', vi.fn(jsonFetch({ ...META_FIXTURE, schema_version: '0.0.9' })))
    render(<App />)
    // Two places read meta.json and both say so: the footer and the data-sources section.
    const footer = screen.getByRole('contentinfo')
    expect(await within(footer).findByRole('alert')).toHaveTextContent('unsupported schema_version "0.0.9"')
    expect(await screen.findAllByRole('alert')).toHaveLength(2)
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Questions the study answers' })).toBeInTheDocument()
  })

  it('shows an error in the footer when meta.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404 }) as Response))
    render(<App />)
    expect(await within(screen.getByRole('contentinfo')).findByRole('alert')).toHaveTextContent('HTTP 404')
    expect(await screen.findAllByRole('alert')).toHaveLength(2)
  })

  it('has a Sample page, after About, that draws sample_funnel.json (the fixture here)', async () => {
    // One fake server for both files: the footer asks for meta.json, the Sample page for sample_funnel.json.
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/sample_funnel.json' ? FUNNEL_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    const nav = within(screen.getByRole('navigation', { name: 'Primary' }))
    expect(nav.getAllByRole('link').map((a) => a.textContent)).toEqual(['About', 'Sample', 'IV measures', 'Architecture', '3D preview', 'Metrics'])
    expect(server).not.toHaveBeenCalledWith('data/sample_funnel.json', expect.anything()) // not fetched until the page is opened
    fireEvent.click(nav.getByRole('link', { name: 'Sample' }))
    const steps = await screen.findByRole('table', { name: 'Funnel steps' })
    expect(server).toHaveBeenCalledWith('data/sample_funnel.json', { cache: 'no-cache' })
    expect(within(steps).getAllByRole('row')).toHaveLength(FUNNEL_DATA_FIXTURE.steps.length + 1)
    expect(within(steps).getByText('Fixture: timing known')).toBeInTheDocument()
    for (const c of FUNNEL_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the Sample page error, and keeps the app usable, when sample_funnel.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Sample' }))
    const main = await screen.findByText(/sample funnel could not be shown/i)
    expect(main).toHaveTextContent('data/sample_funnel.json returned HTTP 404')
    expect(screen.queryByRole('table', { name: 'Funnel steps' })).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('has an IV measures page, after Sample, that draws iv_measures.json (the fixture here)', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/iv_measures.json' ? IV_MEASURES_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    const nav = within(screen.getByRole('navigation', { name: 'Primary' }))
    expect(server).not.toHaveBeenCalledWith('data/iv_measures.json', expect.anything()) // not fetched until the page is opened
    fireEvent.click(nav.getByRole('link', { name: 'IV measures' }))
    const bars = await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(server).toHaveBeenCalledWith('data/iv_measures.json', { cache: 'no-cache' })
    expect(within(bars).getAllByRole('img')).toHaveLength(IV_MEASURES_DATA_FIXTURE.implied_move.counts.length)
    expect(screen.getByRole('group', { name: 'IV crush histogram' })).toBeInTheDocument()
    for (const c of IV_MEASURES_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the IV measures page error, and keeps the app usable, when iv_measures.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'IV measures' }))
    const main = await screen.findByText(/IV measures could not be shown/i)
    expect(main).toHaveTextContent('data/iv_measures.json returned HTTP 404')
    expect(screen.queryByRole('group', { name: 'Implied move histogram' })).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('has an Architecture page that draws the three diagrams from architecture.ts', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Architecture' }))
    const arch = screen.getByRole('img', { name: 'Architecture diagram' })
    for (const layer of ARCH_LAYERS) {
      expect(within(arch).getByText(layer.label.toUpperCase())).toBeInTheDocument()
      for (const box of layer.boxes) expect(within(arch).getByText(box)).toBeInTheDocument()
    }
    expect(screen.getByRole('img', { name: 'Sequence diagram' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Activity diagram' })).toBeInTheDocument()
    await screen.findByText(/source commit/)
  })

  it('has a 3D preview page that lazy-loads the surface and labels it as illustrative', async () => {
    render(<App />)
    expect(screen.queryByTestId('r3f-canvas')).toBeNull() // not loaded on first paint
    fireEvent.click(screen.getByRole('link', { name: '3D preview' }))
    expect(await screen.findByTestId('r3f-canvas')).toBeInTheDocument()
    expect(screen.getByText('Illustrative synthetic shape — not data')).toBeInTheDocument()
  })

  it('offers no Admin page and no API-key field (there is no live mode)', async () => {
    render(<App />)
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
    expect(screen.queryByLabelText(/api key/i)).toBeNull()
    await screen.findByText(/source commit/)
  })
})
