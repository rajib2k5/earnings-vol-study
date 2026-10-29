import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ThreeDPreview } from './ThreeDPreview'
import { TERRAIN_DATA_FIXTURE, TERRAIN_FIXTURE } from '../test/terrainFixture'
import { edited } from '../test/editHelpers'

const mode = vi.hoisted(() => ({ canvasThrows: false }))
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: { children: { props: { terrain: { vertexCount: number; missingCount: number } } } }) => {
    if (mode.canvasThrows) throw new Error('WebGL context lost')
    const t = children.props.terrain
    return <div data-testid="r3f-canvas" data-vertices={t.vertexCount} data-missing={t.missingCount} />
  },
}))
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }))

afterEach(() => {
  mode.canvasThrows = false
  vi.restoreAllMocks()
})

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

describe('ThreeDPreview', () => {
  it('loads terrain.json first (no canvas, so no WebGL, on first paint), then lazy-loads the surface', async () => {
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading terrain data')
    expect(screen.queryByTestId('r3f-canvas')).toBeNull()
    expect(await screen.findByTestId('r3f-canvas')).toBeInTheDocument()
    expect(screen.queryByText('Loading 3D view…')).toBeNull()
  })

  it('never starts the 3D view while the file is still loading', () => {
    const never = vi.fn(() => new Promise<Response>(() => {})) as unknown as typeof fetch
    render(<ThreeDPreview fetchImpl={never} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading terrain data')
    expect(screen.queryByTestId('r3f-canvas')).toBeNull()
    expect(screen.queryByText('Loading 3D view…')).toBeNull()
  })

  it('requests the relative data/terrain.json by default, and the given url when there is one', async () => {
    const f = serving(TERRAIN_FIXTURE)
    const { unmount } = render(<ThreeDPreview fetchImpl={f} />)
    await screen.findByTestId('r3f-canvas')
    expect(f).toHaveBeenCalledWith('data/terrain.json', { cache: 'no-cache' })
    unmount()
    const g = serving(TERRAIN_FIXTURE)
    render(<ThreeDPreview url="x/terrain.json" fetchImpl={g} />)
    await screen.findByTestId('r3f-canvas')
    expect(g).toHaveBeenCalledWith('x/terrain.json', { cache: 'no-cache' })
  })

  it('draws the file\'s grid: one vertex per company x event day, and the null cell as a hole', async () => {
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    const canvas = await screen.findByTestId('r3f-canvas')
    expect(canvas).toHaveAttribute('data-vertices', '9') // 3 companies x 3 days
    expect(canvas).toHaveAttribute('data-missing', '1') // the one null
  })

  it('explains the real data: x event day, z company in the file\'s order, height and colour the file\'s units', async () => {
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    await screen.findByTestId('r3f-canvas')
    expect(screen.getByRole('heading', { level: 2, name: '3D view' })).toBeInTheDocument()
    expect(screen.getByText(/x: event day \(-1 to 1\)/)).toHaveTextContent(
      "x: event day (-1 to 1) · z: company (3, in the file's order: fixture sector, then id) · height and colour: fixture abnormal log IV. Gaps are cells with no data. Drag to orbit, scroll to zoom.",
    )
  })

  it('no longer calls itself a placeholder or illustrative', async () => {
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    await screen.findByTestId('r3f-canvas')
    expect(screen.queryByText(/Placeholder/)).toBeNull()
    expect(screen.queryByText(/Illustrative/i)).toBeNull()
    expect(screen.queryByRole('heading', { name: '3D preview' })).toBeNull()
  })

  it('says the timing labels are provisional, and lists every caveat of the file once', async () => {
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    await screen.findByTestId('r3f-canvas')
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('Timing labels are provisional: 3 timing look-ups are done')
    for (const c of TERRAIN_DATA_FIXTURE.caveats) expect(within(notice).getAllByText(c)).toHaveLength(1)
  })

  it('shows a data error, and starts no 3D view, when terrain.json is missing', async () => {
    render(<ThreeDPreview fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The 3D view could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByTestId('r3f-canvas')).toBeNull()
    expect(screen.getByRole('heading', { name: '3D view' })).toBeInTheDocument()
  })

  it('shows a data error naming the rule when the grid is ragged, and for the wrong kind or version', async () => {
    const ragged = { ...TERRAIN_FIXTURE, data: edited(TERRAIN_DATA_FIXTURE, ['values', 1], [0.5, 0.25]) }
    const { unmount } = render(<ThreeDPreview fetchImpl={serving(ragged)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/terrain.json: values[1] must have 3 entries (one per rel_days entry), got 2')
    unmount()
    const kind = render(<ThreeDPreview fetchImpl={serving({ ...TERRAIN_FIXTURE, kind: 'heatmap' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "heatmap", expected "terrain"')
    kind.unmount()
    render(<ThreeDPreview fetchImpl={serving({ ...TERRAIN_FIXTURE, schema_version: '0.3.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.3.0"')
    expect(screen.queryByTestId('r3f-canvas')).toBeNull()
  })

  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<ThreeDPreview url="old/terrain.json" fetchImpl={oldFetch} />)
    rerender(<ThreeDPreview url="new/terrain.json" fetchImpl={serving(TERRAIN_FIXTURE)} />)
    await screen.findByTestId('r3f-canvas')
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows an error message instead of a blank page when the 3D view cannot start', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs caught render errors
    mode.canvasThrows = true
    render(<ThreeDPreview fetchImpl={serving(TERRAIN_FIXTURE)} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The 3D view could not start (it needs WebGL): WebGL context lost')
    expect(screen.getByRole('heading', { name: '3D view' })).toBeInTheDocument() // page survives
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toBeInTheDocument() // and still says the labels are provisional
  })
})
