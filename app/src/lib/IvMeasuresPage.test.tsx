import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { IvMeasuresDisplay, IvMeasuresPage } from './IvMeasuresPage'
import { parseIvMeasures, type IvMeasures } from './ivMeasures'
import { IV_MEASURES_DATA_FIXTURE, IV_MEASURES_FIXTURE } from '../test/ivMeasuresFixture'

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The fixture with some top-level `data` fields replaced, as a whole file body. */
const withData = (patch: Record<string, unknown>) => ({ ...IV_MEASURES_FIXTURE, data: { ...IV_MEASURES_DATA_FIXTURE, ...patch } })

/** The checked data for `IvMeasuresDisplay`, built by the same validator the page uses. */
function checked(patch: Record<string, unknown> = {}): IvMeasures {
  const r = parseIvMeasures({ ...IV_MEASURES_DATA_FIXTURE, ...patch })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

const IMPLIED_MOVE_TITLE = 'Implied move √E on day −1, events with E > 0'
const CRUSH_TITLE = '30-day IV crush, ln IV(day 0) − ln IV(day −1)'

/** The [label, value] pairs of a two-column table without a header row. */
const pairsOf = (table: HTMLElement): string[][] =>
  within(table)
    .getAllByRole('row')
    .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent ?? ''))

/** The [quantile, value] pairs of a quantile table, without its header row. */
const quantilesOf = (table: HTMLElement): string[][] => {
  expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Quantile', 'Value'])
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent ?? ''))
}

/** The bars of one histogram: accessible label and CSS height, in order. */
const barsOf = (name: string): [string, string][] =>
  within(screen.getByRole('group', { name }))
    .getAllByRole('img')
    .map((b) => [b.getAttribute('aria-label') ?? '', b.style.height])

describe('IvMeasuresPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading IV measures')
    expect(screen.getByRole('heading', { name: 'IV measures' })).toBeInTheDocument()
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/iv_measures.json by default, and the given url when there is one', async () => {
    const f = serving(IV_MEASURES_FIXTURE)
    const { unmount } = render(<IvMeasuresPage fetchImpl={f} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(f).toHaveBeenCalledWith('data/iv_measures.json', { cache: 'no-cache' })
    unmount()
    const g = serving(IV_MEASURES_FIXTURE)
    render(<IvMeasuresPage url="x/iv_measures.json" fetchImpl={g} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(g).toHaveBeenCalledWith('x/iv_measures.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no histogram, when the file is missing (HTTP 404)', async () => {
    render(<IvMeasuresPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The IV measures could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('group')).toBeNull()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
  })
  it('shows an error for the previous schema version', async () => {
    render(<IvMeasuresPage fetchImpl={serving({ ...IV_MEASURES_FIXTURE, schema_version: '0.2.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.2.0": this app only understands "0.3.0"')
    expect(screen.queryByRole('img')).toBeNull()
  })
  it('shows an error when the file is another kind (sample_funnel.json served at the iv url)', async () => {
    render(<IvMeasuresPage fetchImpl={serving({ ...IV_MEASURES_FIXTURE, kind: 'sample_funnel' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "sample_funnel", expected "iv_measures"')
    expect(screen.queryByRole('img')).toBeNull()
  })
  it('shows an error naming the rule when the data has the wrong shape (counts that do not add up to n)', async () => {
    const crush = { ...IV_MEASURES_DATA_FIXTURE.crush, counts: [0, 3, 5] }
    render(<IvMeasuresPage fetchImpl={serving(withData({ crush }))} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data/iv_measures.json: crush.counts add up to 8, but n is 9')
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    // The first request answers last, with an error, and must not replace the newer page.
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<IvMeasuresPage url="old/iv_measures.json" fetchImpl={oldFetch} />)
    rerender(<IvMeasuresPage url="new/iv_measures.json" fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('group', { name: 'Implied move histogram' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('IvMeasuresPage: the two histograms and their bars', () => {
  it('has a heading for each measure with the wording asked for, and shows the sample and units from the file', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(screen.getByRole('heading', { name: IMPLIED_MOVE_TITLE })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: CRUSH_TITLE })).toBeInTheDocument()
    expect(screen.getByText(/Sample:/)).toHaveTextContent('Sample: fixture-daily, 12 events.')
    expect(screen.getByText('Units: Fixture units (0.1 = 10%)')).toBeInTheDocument()
    expect(screen.getByText('Units: Fixture log change')).toBeInTheDocument()
  })
  it('draws one bar per bin, labelled with the edges as written and the count, in the order of the file', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(barsOf('Implied move histogram').map(([label]) => label)).toEqual(['0.01 to 0.02: 1 event', '0.02 to 0.03: 4 events', '0.03 to 0.04: 2 events'])
    expect(barsOf('IV crush histogram').map(([label]) => label)).toEqual(['-0.6 to -0.4: 0 events', '-0.4 to -0.2: 3 events', '-0.2 to 0: 6 events'])
  })
  it('sizes each bar against the LARGEST count of its histogram: [1, 4, 2] -> 25%, 100%, 50%', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    expect(barsOf('Implied move histogram').map(([, h]) => h)).toEqual(['25%', '100%', '50%'])
  })
  it('sizes the two histograms independently: crush [0, 3, 6] -> 0%, 50%, 100% (not against the implied-move maximum of 4)', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'IV crush histogram' })
    expect(barsOf('IV crush histogram').map(([, h]) => h)).toEqual(['0%', '50%', '100%'])
  })
  it('puts the tallest bar where the largest count is, wherever that is (first bin, last bin)', () => {
    const first = { ...IV_MEASURES_DATA_FIXTURE.implied_move, counts: [4, 2, 1] }
    const { unmount } = render(<IvMeasuresDisplay iv={checked({ implied_move: first })} />)
    expect(barsOf('Implied move histogram').map(([, h]) => h)).toEqual(['100%', '50%', '25%'])
    unmount()
    const last = { ...IV_MEASURES_DATA_FIXTURE.implied_move, counts: [1, 2, 4] }
    render(<IvMeasuresDisplay iv={checked({ implied_move: last })} />)
    expect(barsOf('Implied move histogram').map(([, h]) => h)).toEqual(['25%', '50%', '100%'])
  })
  it('gives a non-round ratio its real height (1 of 3 = 33.33...%)', () => {
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, n: 4, counts: [1, 3, 0] }
    render(<IvMeasuresDisplay iv={checked({ implied_move: move })} />)
    const height = parseFloat(barsOf('Implied move histogram')[0][1])
    expect(height).toBeCloseTo(33.3333, 3)
  })
  it('draws empty bars, and never NaN or Infinity, when every count is 0', () => {
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, n: 0, n_nonpositive: 0, n_identified: 0, sqrt_mean_evar: null, quantiles: null, counts: [0, 0, 0] }
    render(<IvMeasuresDisplay iv={checked({ implied_move: move })} />)
    const bars = barsOf('Implied move histogram')
    expect(bars).toHaveLength(3)
    for (const [label, height] of bars) {
      expect(height).toBe('0%')
      expect(label).toMatch(/: 0 events$/)
    }
  })
  it('says there is no histogram, and draws no bars for it, when the file has no bins', () => {
    const empty = { ...IV_MEASURES_DATA_FIXTURE.crush, n: 0, mean: null, quantiles: null, bin_edges: [], counts: [] }
    render(<IvMeasuresDisplay iv={checked({ crush: empty })} />)
    expect(screen.getByText('No histogram: the file has no bins.')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'IV crush histogram' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Implied move histogram' })).toBeInTheDocument() // the other one is still drawn
  })
  it('shows the first and last bin edge under the bars, as written', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    const axis = screen.getByRole('group', { name: 'Implied move histogram' }).nextElementSibling as HTMLElement
    expect(Array.from(axis.children).map((c) => c.textContent)).toEqual(['0.01', '0.04'])
    const crushAxis = screen.getByRole('group', { name: 'IV crush histogram' }).nextElementSibling as HTMLElement
    expect(Array.from(crushAxis.children).map((c) => c.textContent)).toEqual(['-0.6', '0'])
  })
  it('uses the singular "event" for a count of 1 and a plural for the rest', () => {
    render(<IvMeasuresDisplay iv={checked()} />)
    expect(screen.getByRole('img', { name: '0.01 to 0.02: 1 event' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /1 events/ })).toBeNull()
    expect(screen.getByRole('img', { name: '-0.6 to -0.4: 0 events' })).toBeInTheDocument()
  })
})

describe('IvMeasuresPage: the numbers beside each histogram', () => {
  it('shows n, n_identified, n_nonpositive and sqrt_mean_evar for the implied move, as given', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'Implied move numbers' })
    expect(pairsOf(table)).toEqual([
      ['Events in the histogram (n)', '7'],
      ['Events with E worked out (n_identified)', '8'],
      ['E ≤ 0, no implied move', '1'],
      ['√(mean E), all events, E signed', '0.0375'],
    ])
  })
  it('shows n and the mean for the crush, as given', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'IV crush numbers' })
    expect(pairsOf(table)).toEqual([
      ['Events in the histogram (n)', '9'],
      ['Mean', '-0.25'],
    ])
  })
  it('lists the five quantiles p10 .. p90 for each measure, as given, in that order', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    const move = await screen.findByRole('table', { name: 'Implied move quantiles' })
    expect(quantilesOf(move)).toEqual([['p10', '0.011'], ['p25', '0.022'], ['p50', '0.033'], ['p75', '0.044'], ['p90', '0.055']])
    const crush = screen.getByRole('table', { name: 'IV crush quantiles' })
    expect(quantilesOf(crush)).toEqual([['p10', '-0.55'], ['p25', '-0.45'], ['p50', '-0.35'], ['p75', '-0.25'], ['p90', '-0.15']])
  })
  it('shows "—" for a null sqrt_mean_evar and a null mean', () => {
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, sqrt_mean_evar: null }
    const crush = { ...IV_MEASURES_DATA_FIXTURE.crush, mean: null }
    render(<IvMeasuresDisplay iv={checked({ implied_move: move, crush })} />)
    expect(pairsOf(screen.getByRole('table', { name: 'Implied move numbers' }))[3]).toEqual(['√(mean E), all events, E signed', '—'])
    expect(pairsOf(screen.getByRole('table', { name: 'IV crush numbers' }))[1]).toEqual(['Mean', '—'])
  })
  it('shows a zero as 0, not as a dash', () => {
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, sqrt_mean_evar: 0 }
    const crush = { ...IV_MEASURES_DATA_FIXTURE.crush, mean: 0 }
    render(<IvMeasuresDisplay iv={checked({ implied_move: move, crush })} />)
    expect(pairsOf(screen.getByRole('table', { name: 'Implied move numbers' }))[3][1]).toBe('0')
    expect(pairsOf(screen.getByRole('table', { name: 'IV crush numbers' }))[1][1]).toBe('0')
  })
  it('says the file has no quantiles, instead of drawing an empty table, when they are null', () => {
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, quantiles: null }
    render(<IvMeasuresDisplay iv={checked({ implied_move: move })} />)
    expect(screen.queryByRole('table', { name: 'Implied move quantiles' })).toBeNull()
    expect(screen.getByText('No quantiles: the file has none for the Implied move.')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'IV crush quantiles' })).toBeInTheDocument() // the crush ones are still drawn
  })
  it('shows numbers exactly as given: no thousands separator, no rounding', () => {
    const crush = { ...IV_MEASURES_DATA_FIXTURE.crush, n: 12345, counts: [0, 3, 12342], mean: -0.123456789 }
    const move = { ...IV_MEASURES_DATA_FIXTURE.implied_move, n_identified: 20000, n_nonpositive: 7655, n: 12345, counts: [1, 4, 12340] }
    render(<IvMeasuresDisplay iv={checked({ crush, implied_move: move })} />)
    expect(pairsOf(screen.getByRole('table', { name: 'IV crush numbers' }))).toEqual([
      ['Events in the histogram (n)', '12345'],
      ['Mean', '-0.123456789'],
    ])
    expect(pairsOf(screen.getByRole('table', { name: 'Implied move numbers' })).slice(0, 3).map((p) => p[1])).toEqual(['12345', '20000', '7655'])
  })
})

describe('IvMeasuresPage: caveats', () => {
  it('lists every caveat in a visible list, in order', async () => {
    render(<IvMeasuresPage fetchImpl={serving(IV_MEASURES_FIXTURE)} />)
    await screen.findByRole('group', { name: 'Implied move histogram' })
    const items = within(screen.getByRole('list', { name: 'Caveats' })).getAllByRole('listitem')
    expect(items.map((i) => i.textContent)).toEqual(['Fixture caveat A: invented for the test.', 'Fixture caveat B: also invented.'])
    for (const item of items) expect(item).toBeVisible()
  })
  it('shows an empty caveats list when the file has none', () => {
    render(<IvMeasuresDisplay iv={checked({ caveats: [] })} />)
    expect(within(screen.getByRole('list', { name: 'Caveats' })).queryAllByRole('listitem')).toHaveLength(0)
  })
})
