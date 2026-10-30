import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import App from './App'
import { ARCH_LAYERS } from './lib/architecture'
import { MILESTONES, PITCH, PROJECT_TITLE, QUESTIONS } from './lib/studyContent'
import { resetMemoryFallback, safeStorage } from './lib/storage'
import { DRIVERS_DATA_FIXTURE, DRIVERS_FIXTURE } from './test/driversFixture'
import { EVENT_PATHS_DATA_FIXTURE, EVENT_PATHS_FIXTURE } from './test/eventPathsFixture'
import { FUNNEL_DATA_FIXTURE, FUNNEL_FIXTURE } from './test/funnelFixture'
import { HEATMAP_DATA_FIXTURE, HEATMAP_FIXTURE } from './test/heatmapFixture'
import { IMPLIED_REALISED_DATA_FIXTURE, IMPLIED_REALISED_FIXTURE } from './test/impliedRealisedFixture'
import { IV_MEASURES_DATA_FIXTURE, IV_MEASURES_FIXTURE } from './test/ivMeasuresFixture'
import { jsonFetch, META_DATA_FIXTURE, META_FIXTURE } from './test/metaFixture'
import { TESTS_DATA_FIXTURE, TESTS_FIXTURE } from './test/resultsFixture'
import { TERRAIN_FIXTURE } from './test/terrainFixture'

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

  it('names under the milestones exactly the pages the navigation has, each once', async () => {
    render(<App />)
    const labels = within(screen.getByRole('navigation', { name: 'Primary' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    const named = MILESTONES.flatMap((m) => m.pages)
    for (const p of named) expect(labels).toContain(p)
    expect([...named].sort()).toEqual([...labels].sort()) // every navigation page belongs to one milestone
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the milestone and source commit from data/meta.json in the footer', async () => {
    render(<App />)
    expect(await screen.findByText(/data contract 0\.5\.0 · milestone M4 · source commit abc1234/)).toBeInTheDocument()
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
    expect(nav.getAllByRole('link').map((a) => a.textContent)).toEqual(['About', 'Sample', 'IV measures', 'Results', 'Drivers', 'Implied vs realised', 'Crush paths', 'Heatmap', 'Architecture', '3D view', 'Metrics'])
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

  it('has a Results page, after IV measures, that draws tests.json (the fixture here) under a provisional-labels notice', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/tests.json' ? TESTS_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(server).not.toHaveBeenCalledWith('data/tests.json', expect.anything()) // not fetched until the page is opened
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Results' }))
    const primary = await screen.findByRole('table', { name: 'Primary family' })
    expect(server).toHaveBeenCalledWith('data/tests.json', { cache: 'no-cache' })
    expect(within(primary).getAllByRole('row')).toHaveLength(TESTS_DATA_FIXTURE.rows.filter((r) => r.role === 'primary').length + 1)
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing labels are provisional')
    for (const c of TESTS_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the Results page error, and keeps the app usable, when tests.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Results' }))
    expect(await screen.findByText(/results could not be shown/i)).toHaveTextContent('data/tests.json returned HTTP 404')
    expect(screen.queryByRole('table', { name: 'Primary family' })).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('has a Drivers page, after Results, that draws drivers.json (the fixture here) under a provisional-labels notice', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/drivers.json' ? DRIVERS_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(server).not.toHaveBeenCalledWith('data/drivers.json', expect.anything()) // not fetched until the page is opened
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Drivers' }))
    const gate = await screen.findByRole('table', { name: 'G1 calibration' })
    expect(server).toHaveBeenCalledWith('data/drivers.json', { cache: 'no-cache' })
    expect(within(gate).getAllByRole('row')).toHaveLength(DRIVERS_DATA_FIXTURE.g1.calibrated.length + 1)
    expect(screen.getAllByRole('table', { name: /^Model \d terms$/ })).toHaveLength(DRIVERS_DATA_FIXTURE.models.length)
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('Timing labels are provisional')
    // every caveat is in the notice (the one on the exploratory p and q also sits next to the coefficient tables)
    for (const c of DRIVERS_DATA_FIXTURE.caveats) expect(within(notice).getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the Drivers page error, and keeps the app usable, when drivers.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Drivers' }))
    expect(await screen.findByText(/drivers could not be shown/i)).toHaveTextContent('data/drivers.json returned HTTP 404')
    expect(screen.queryByRole('table', { name: 'G1 calibration' })).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('has an Implied vs realised page, after Drivers, that draws implied_vs_realised.json (the fixture here) under a provisional-labels notice', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/implied_vs_realised.json' ? IMPLIED_REALISED_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(server).not.toHaveBeenCalledWith('data/implied_vs_realised.json', expect.anything())
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Implied vs realised' }))
    expect(await screen.findByRole('img', { name: /Scatter of the realised absolute move against the expected absolute move, 4 events/ })).toBeInTheDocument()
    expect(server).toHaveBeenCalledWith('data/implied_vs_realised.json', { cache: 'no-cache' })
    expect(screen.getByRole('table', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing labels are provisional')
    for (const c of IMPLIED_REALISED_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the Implied vs realised page error, and keeps the app usable, when implied_vs_realised.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Implied vs realised' }))
    expect(await screen.findByText(/implied and realised moves could not be shown/i)).toHaveTextContent('data/implied_vs_realised.json returned HTTP 404')
    expect(screen.queryByRole('table', { name: 'Summary' })).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('has a Crush paths page that draws event_paths.json (the fixture here) and does not autoplay without a motion preference', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/event_paths.json' ? EVENT_PATHS_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(server).not.toHaveBeenCalledWith('data/event_paths.json', expect.anything())
    fireEvent.click(screen.getByRole('link', { name: 'Crush paths' }))
    expect(await screen.findByRole('img', { name: /Mean abnormal log IV path/ })).toBeInTheDocument()
    expect(server).toHaveBeenCalledWith('data/event_paths.json', { cache: 'no-cache' })
    expect(screen.getByRole('img', { name: /Per-event abnormal log IV paths, 3 events/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument() // jsdom has no matchMedia: reduced motion, no autoplay
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toBeInTheDocument()
    for (const c of EVENT_PATHS_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('has a Heatmap page that draws heatmap.json (the fixture here) under the provisional notice', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/heatmap.json' ? HEATMAP_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(server).not.toHaveBeenCalledWith('data/heatmap.json', expect.anything())
    fireEvent.click(screen.getByRole('link', { name: 'Heatmap' }))
    expect(await screen.findByRole('table', { name: 'Fixture grid by day' })).toBeInTheDocument()
    expect(server).toHaveBeenCalledWith('data/heatmap.json', { cache: 'no-cache' })
    expect(screen.getByRole('table', { name: 'Fixture grid by season' })).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toBeInTheDocument()
    for (const c of HEATMAP_DATA_FIXTURE.caveats) expect(screen.getByText(c)).toBeInTheDocument()
    await screen.findByText(/source commit abc1234/)
  })

  it('has a 3D view that loads terrain.json first, then lazy-loads the surface, with real-data wording and the provisional notice', async () => {
    const server = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => (url === 'data/terrain.json' ? TERRAIN_FIXTURE : META_FIXTURE) }) as Response)
    vi.stubGlobal('fetch', server)
    render(<App />)
    expect(screen.queryByTestId('r3f-canvas')).toBeNull() // not loaded on first paint
    expect(server).not.toHaveBeenCalledWith('data/terrain.json', expect.anything())
    fireEvent.click(screen.getByRole('link', { name: '3D view' }))
    expect(await screen.findByTestId('r3f-canvas')).toBeInTheDocument()
    expect(server).toHaveBeenCalledWith('data/terrain.json', { cache: 'no-cache' })
    expect(screen.getByRole('heading', { name: '3D view' })).toBeInTheDocument()
    expect(screen.getByText(/x: event day \(-1 to 1\)/)).toBeInTheDocument()
    expect(screen.queryByText(/Illustrative/i)).toBeNull()
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing labels are provisional')
    await screen.findByText(/source commit abc1234/)
  })

  it('shows the 3D view error, and keeps the app usable, when terrain.json is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => META_FIXTURE } as Response) : ({ ok: false, status: 404 } as Response))))
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: '3D view' }))
    expect(await screen.findByText(/3D view could not be shown/i)).toHaveTextContent('data/terrain.json returned HTTP 404')
    expect(screen.queryByTestId('r3f-canvas')).toBeNull()
    await screen.findByText(/source commit abc1234/)
  })

  it('offers no Admin page and no API-key field (there is no live mode)', async () => {
    render(<App />)
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
    expect(screen.queryByLabelText(/api key/i)).toBeNull()
    await screen.findByText(/source commit/)
  })
})
