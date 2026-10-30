import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { HeatmapDisplay, HeatmapPage } from './HeatmapPage'
import { parseHeatmap, type HeatmapData } from './heatmap'
import { HEATMAP_DATA_FIXTURE, HEATMAP_FIXTURE } from '../test/heatmapFixture'
import { edited } from '../test/editHelpers'

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

function checked(data: unknown = HEATMAP_DATA_FIXTURE): HeatmapData {
  const r = parseHeatmap(data)
  if (!r.ok) throw new Error(r.error)
  return r.data
}

const BY_DAY = 'Fixture grid by day'
const BY_SEASON = 'Fixture grid by season'

/** The body cells of a grid, row by row. */
const cellsOf = (title: string): HTMLElement[][] =>
  within(screen.getByRole('table', { name: title }))
    .getAllByRole('row')
    .slice(1)
    .map((r) => within(r).getAllByRole('cell'))

const bg = (cell: HTMLElement): string => cell.style.backgroundColor

// Colours, by hand (see heatColour.test.ts): channel = round(247 + (end - 247) * t), blue end 33,102,172, red end 178,24,43.
//   t = 1   -> blue rgb(33, 102, 172), red rgb(178, 24, 43)
//   t = 1/2 -> red  247 - 69/2 = 212.5 -> 213, 247 - 223/2 = 135.5 -> 136, 247 - 204/2 = 145 -> rgb(213, 136, 145)
//   t = 1/2 -> blue 247 - 214/2 = 140, 247 - 145/2 = 174.5 -> 175, 247 - 75/2 = 209.5 -> 210 -> rgb(140, 175, 210)
//   t = 1/4 -> red  247 - 69/4 = 229.75 -> 230, 247 - 223/4 = 191.25 -> 191, 247 - 204/4 = 196 -> rgb(230, 191, 196)
const NEUTRAL = 'rgb(247, 247, 247)'
const FULL_RED = 'rgb(178, 24, 43)'
const FULL_BLUE = 'rgb(33, 102, 172)'
const HALF_RED = 'rgb(213, 136, 145)'
const HALF_BLUE = 'rgb(140, 175, 210)'
const QUARTER_RED = 'rgb(230, 191, 196)'

describe('HeatmapPage: loading and errors', () => {
  it('shows a loading line first, then the grids', async () => {
    render(<HeatmapPage fetchImpl={serving(HEATMAP_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading heatmap')
    expect(screen.getByRole('heading', { level: 2, name: 'Heatmap' })).toBeInTheDocument()
    await screen.findByRole('table', { name: BY_DAY })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/heatmap.json by default, and the given url when there is one', async () => {
    const f = serving(HEATMAP_FIXTURE)
    const { unmount } = render(<HeatmapPage fetchImpl={f} />)
    await screen.findByRole('table', { name: BY_DAY })
    expect(f).toHaveBeenCalledWith('data/heatmap.json', { cache: 'no-cache' })
    unmount()
    const g = serving(HEATMAP_FIXTURE)
    render(<HeatmapPage url="x/heatmap.json" fetchImpl={g} />)
    await screen.findByRole('table', { name: BY_DAY })
    expect(g).toHaveBeenCalledWith('x/heatmap.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no grid, when the file is missing (HTTP 404)', async () => {
    render(<HeatmapPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The heatmap could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error for the previous schema version, another kind and a ragged grid', async () => {
    const { unmount } = render(<HeatmapPage fetchImpl={serving({ ...HEATMAP_FIXTURE, schema_version: '0.3.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.3.0": this app only understands "0.5.0"')
    unmount()
    const other = render(<HeatmapPage fetchImpl={serving({ ...HEATMAP_FIXTURE, kind: 'tests' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "tests", expected "heatmap"')
    other.unmount()
    const body = { ...HEATMAP_FIXTURE, data: edited(HEATMAP_DATA_FIXTURE, ['grids', 0, 'values', 1], [0.5]) }
    render(<HeatmapPage fetchImpl={serving(body)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/heatmap.json: grids[0].values[1] must have 3 entries (one per column label), got 1')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<HeatmapPage url="old/heatmap.json" fetchImpl={oldFetch} />)
    rerender(<HeatmapPage url="new/heatmap.json" fetchImpl={serving(HEATMAP_FIXTURE)} />)
    await screen.findByRole('table', { name: BY_DAY })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table', { name: BY_DAY })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('HeatmapDisplay: notice, titles and structure', () => {
  it('states that the timing labels are provisional and lists every caveat once', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing labels are provisional: 3 timing look-ups are done')
    for (const c of HEATMAP_DATA_FIXTURE.caveats) expect(screen.getAllByText(c)).toHaveLength(1)
  })
  it('draws both grids, each under its own title with its measure and units', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    expect(screen.getByRole('heading', { name: BY_DAY })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: BY_SEASON })).toBeInTheDocument()
    expect(screen.getByText(/fix_measure_a · fixture units A/)).toBeInTheDocument()
    expect(screen.getByText(/fix_measure_b · fixture units B/)).toBeInTheDocument()
  })
  it('has one cell per row and column, the column labels as headers and the row labels as row headers', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const day = screen.getByRole('table', { name: BY_DAY })
    expect(within(day).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['', '-1', '0', '1'])
    expect(within(day).getAllByRole('rowheader').map((h) => h.textContent)).toEqual(['FXA', 'FXB'])
    expect(cellsOf(BY_DAY).map((r) => r.length)).toEqual([3, 3])
    const season = screen.getByRole('table', { name: BY_SEASON })
    expect(within(season).getAllByRole('rowheader').map((h) => h.textContent)).toEqual(['FX Alpha', 'FX Beta']) // labels, not keys
    expect(cellsOf(BY_SEASON).map((r) => r.length)).toEqual([2, 2])
  })
})

describe('HeatmapDisplay: every cell says its row, column, value and n', () => {
  it('uses the same text for the title and the aria-label', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    for (const row of cellsOf(BY_DAY)) {
      for (const c of row) {
        expect(c.getAttribute('title')).toBeTruthy()
        expect(c.getAttribute('title')).toBe(c.getAttribute('aria-label'))
      }
    }
  })
  it('gives row, column, value as given, and n', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const labels = cellsOf(BY_DAY).map((r) => r.map((c) => c.getAttribute('aria-label')))
    expect(labels).toEqual([
      ['FXA, -1: -0.5 (n = 4)', 'FXA, 0: 0 (n = 4)', 'FXA, 1: 0.25 (n = 3)'],
      ['FXB, -1: 0.5 (n = 5)', 'FXB, 0: no data (n = 0)', 'FXB, 1: -0.25 (n = 5)'],
    ])
  })
  it('adds the q-value to the cells of a grid that has them', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    expect(cellsOf(BY_SEASON).map((r) => r.map((c) => c.getAttribute('aria-label')))).toEqual([
      ['FX Alpha, 2031Q1: 1 (n = 1), q = 0.5', 'FX Alpha, 2031Q2: no data (n = 0)'],
      ['FX Beta, 2031Q1: -2 (n = 1), q = 0.125', 'FX Beta, 2031Q2: 0.5 (n = 1), q = 0.25'],
    ])
  })
  it('can be found by its accessible name', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    expect(screen.getByRole('cell', { name: 'FXB, 1: -0.25 (n = 5)' })).toBeInTheDocument()
  })
})

describe('HeatmapDisplay: colours on a diverging scale symmetric around 0, using the grid\'s own max |value|', () => {
  it('colours the day grid on a scale of ±0.5: -0.5 full blue, 0 neutral, 0.25 half red, 0.5 full red, -0.25 half blue', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const cells = cellsOf(BY_DAY)
    expect(bg(cells[0][0])).toBe(FULL_BLUE) // -0.5 of 0.5
    expect(bg(cells[0][1])).toBe(NEUTRAL) // 0
    expect(bg(cells[0][2])).toBe(HALF_RED) // 0.25 of 0.5
    expect(bg(cells[1][0])).toBe(FULL_RED) // 0.5 of 0.5
    expect(bg(cells[1][2])).toBe(HALF_BLUE) // -0.25 of 0.5
  })
  it('scales each grid by its own max: 0.5 is full red in the day grid, but a quarter strength in the season grid (max 2)', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const season = cellsOf(BY_SEASON)
    expect(bg(season[1][1])).toBe(QUARTER_RED) // 0.5 of 2
    expect(bg(season[0][0])).toBe(HALF_RED) // 1 of 2
    expect(bg(season[1][0])).toBe(FULL_BLUE) // -2 of 2
  })
  it('is symmetric: +x and -x are equally strong (here ±0.25 of 0.5 -> half red and half blue)', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const cells = cellsOf(BY_DAY)
    expect(bg(cells[0][2])).toBe(HALF_RED)
    expect(bg(cells[1][2])).toBe(HALF_BLUE)
  })
  it('draws a cell with no value empty: no fill, marked as empty, and visibly different from a real 0', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const cells = cellsOf(BY_DAY)
    const empty = cells[1][1]
    expect(bg(empty)).toBe('')
    expect(empty).toHaveClass('heat-empty')
    expect(empty.getAttribute('aria-label')).toContain('no data')
    // a real zero is neutral, filled, and not marked empty
    expect(bg(cells[0][1])).toBe(NEUTRAL)
    expect(cells[0][1]).not.toHaveClass('heat-empty')
    // and the season grid's null cell is empty too
    expect(cellsOf(BY_SEASON)[0][1]).toHaveClass('heat-empty')
    expect(bg(cellsOf(BY_SEASON)[0][1])).toBe('')
  })
  it('marks exactly the null cells as empty: 1 in the day grid, 1 in the season grid', () => {
    const { container } = render(<HeatmapDisplay heatmap={checked()} />)
    expect(container.querySelectorAll('.heat-empty')).toHaveLength(2)
    expect(container.querySelectorAll('.heat-cell')).toHaveLength(6 + 4)
  })
  it('labels the legend of each grid with its own -max and +max', () => {
    render(<HeatmapDisplay heatmap={checked()} />)
    const day = screen.getByRole('img', { name: `${BY_DAY} colour scale` })
    expect(within(day).getByText('-0.5')).toBeInTheDocument()
    expect(within(day).getByText('+0.5')).toBeInTheDocument()
    const season = screen.getByRole('img', { name: `${BY_SEASON} colour scale` })
    expect(within(season).getByText('-2')).toBeInTheDocument()
    expect(within(season).getByText('+2')).toBeInTheDocument()
  })
  it('keeps every cell neutral, and labels the legend 0, for a grid of zeros', () => {
    const zeros = { ...HEATMAP_DATA_FIXTURE.grids[0], values: [[0, 0, 0], [0, 0, 0]] }
    render(<HeatmapDisplay heatmap={checked(edited(HEATMAP_DATA_FIXTURE, ['grids'], [zeros]))} />)
    for (const row of cellsOf(BY_DAY)) for (const c of row) expect(bg(c)).toBe(NEUTRAL)
    const legend = screen.getByRole('img', { name: `${BY_DAY} colour scale` })
    expect(within(legend).getAllByText('0')).toHaveLength(2)
  })
  it('draws a grid with no values at all as all empty cells', () => {
    const empty = { ...HEATMAP_DATA_FIXTURE.grids[0], values: [[null, null, null], [null, null, null]], n: [[0, 0, 0], [0, 0, 0]] }
    const { container } = render(<HeatmapDisplay heatmap={checked(edited(HEATMAP_DATA_FIXTURE, ['grids'], [empty]))} />)
    expect(container.querySelectorAll('.heat-empty')).toHaveLength(6)
  })
})
