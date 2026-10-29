import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { FunnelDisplay, FunnelPage } from './FunnelPage'
import { parseSampleFunnel, type SampleFunnel } from './funnel'
import { FUNNEL_DATA_FIXTURE, FUNNEL_FIXTURE, FUNNEL_NULL_FIXTURE } from '../test/funnelFixture'

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The fixture with some top-level `data` fields replaced, as a whole file body. */
const withData = (patch: Record<string, unknown>) => ({ ...FUNNEL_FIXTURE, data: { ...FUNNEL_DATA_FIXTURE, ...patch } })

/** The checked data for `FunnelDisplay`, built by the same validator the page uses. */
function checked(patch: Record<string, unknown> = {}): SampleFunnel {
  const r = parseSampleFunnel({ ...FUNNEL_DATA_FIXTURE, ...patch })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

/** The text of every cell of the row that contains `label`. */
const cellsOf = (table: HTMLElement, label: string): string[] =>
  within(within(table).getByRole('row', { name: new RegExp(label) }))
    .getAllByRole('cell')
    .map((c) => c.textContent ?? '')

describe('FunnelPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading sample funnel')
    expect(screen.getByRole('heading', { name: 'Sample funnel' })).toBeInTheDocument()
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/sample_funnel.json by default, and the given url when there is one', async () => {
    const f = serving(FUNNEL_FIXTURE)
    const { unmount } = render(<FunnelPage fetchImpl={f} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(f).toHaveBeenCalledWith('data/sample_funnel.json', { cache: 'no-cache' })
    unmount()
    const g = serving(FUNNEL_FIXTURE)
    render(<FunnelPage url="x/sample_funnel.json" fetchImpl={g} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(g).toHaveBeenCalledWith('x/sample_funnel.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no tables, when the file is missing (HTTP 404)', async () => {
    render(<FunnelPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
  })
  it('shows an error for the previous schema version', async () => {
    render(<FunnelPage fetchImpl={serving({ ...FUNNEL_FIXTURE, schema_version: '0.2.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.2.0"')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error when the file is another kind (meta.json served at the funnel url)', async () => {
    render(<FunnelPage fetchImpl={serving({ ...FUNNEL_FIXTURE, kind: 'meta' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "meta", expected "sample_funnel"')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error naming the rule when the data has the wrong shape', async () => {
    render(<FunnelPage fetchImpl={serving(withData({ steps: [] }))} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data/sample_funnel.json: steps must be a non-empty array')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    // The first request answers last, with an error, and must not replace the newer page.
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<FunnelPage url="old/sample_funnel.json" fetchImpl={oldFetch} />)
    rerender(<FunnelPage url="new/sample_funnel.json" fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table', { name: 'Funnel steps' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('FunnelPage: the steps table and the bars', () => {
  it('has one row per step with the label, events, removed and reason exactly as given', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'Funnel steps' })
    expect(within(table).getAllByRole('row')).toHaveLength(3 + 1) // + header row
    expect(cellsOf(table, 'Fixture: every event').slice(0, 4)).toEqual(['Fixture: every event', '200', '0', '—']) // null reason
    expect(cellsOf(table, 'Fixture: timing known').slice(0, 4)).toEqual(['Fixture: timing known', '150', '50', 'fix_unknown|fix_unchecked'])
    expect(cellsOf(table, 'Fixture: inside the range').slice(0, 4)).toEqual(['Fixture: inside the range', '50', '100', 'fix_outside'])
  })
  it('keeps the order of the steps as written in the file', async () => {
    const steps = [...FUNNEL_DATA_FIXTURE.steps].reverse()
    render(<FunnelPage fetchImpl={serving(withData({ steps }))} />)
    const rows = within(await screen.findByRole('table', { name: 'Funnel steps' })).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Fixture: inside the range')
    expect(rows[3]).toHaveTextContent('Fixture: every event')
  })
  it('draws each bar as its n_events against the first step: 200 -> 100%, 150 -> 75%, 50 -> 25%', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(screen.getByRole('img', { name: '200 of 200 events' })).toHaveStyle({ width: '100%' })
    expect(screen.getByRole('img', { name: '150 of 200 events' })).toHaveStyle({ width: '75%' })
    expect(screen.getByRole('img', { name: '50 of 200 events' })).toHaveStyle({ width: '25%' })
  })
  it('measures every bar against the FIRST step, not against the step before it', () => {
    // 1000 -> 500 -> 250: against the previous step the last bar would be 50%; against the first it is 25%.
    const steps = [
      { step: 'a', label: 'Fixture A', n_events: 1000, n_removed: 0, reason: null },
      { step: 'b', label: 'Fixture B', n_events: 500, n_removed: 500, reason: 'r' },
      { step: 'c', label: 'Fixture C', n_events: 250, n_removed: 250, reason: 'r' },
    ]
    render(<FunnelDisplay funnel={checked({ steps })} />)
    expect(screen.getByRole('img', { name: '500 of 1000 events' })).toHaveStyle({ width: '50%' })
    expect(screen.getByRole('img', { name: '250 of 1000 events' })).toHaveStyle({ width: '25%' })
  })
  it('gives a non-round ratio its real width (1 of 3 = 33.33...%)', () => {
    const steps = [
      { step: 'a', label: 'Fixture A', n_events: 3, n_removed: 0, reason: null },
      { step: 'b', label: 'Fixture B', n_events: 1, n_removed: 2, reason: 'r' },
    ]
    render(<FunnelDisplay funnel={checked({ steps })} />)
    const width = parseFloat(screen.getByRole('img', { name: '1 of 3 events' }).style.width)
    expect(width).toBeCloseTo(33.3333, 3)
  })
  it('draws empty bars, and never NaN or Infinity, when the first step has no events', () => {
    const steps = [
      { step: 'a', label: 'Fixture A', n_events: 0, n_removed: 0, reason: null },
      { step: 'b', label: 'Fixture B', n_events: 0, n_removed: 0, reason: null },
    ]
    render(<FunnelDisplay funnel={checked({ steps })} />)
    for (const bar of screen.getAllByRole('img', { name: '0 of 0 events' })) expect(bar.style.width).toBe('0%')
  })
  it('shows numbers exactly as given: no thousands separator', () => {
    const steps = [
      { step: 'a', label: 'Fixture A', n_events: 12345, n_removed: 0, reason: null },
      { step: 'b', label: 'Fixture B', n_events: 6789, n_removed: 5556, reason: 'r' },
    ]
    render(<FunnelDisplay funnel={checked({ steps })} />)
    const table = screen.getByRole('table', { name: 'Funnel steps' })
    expect(cellsOf(table, 'Fixture A').slice(1, 3)).toEqual(['12345', '0'])
    expect(cellsOf(table, 'Fixture B').slice(1, 3)).toEqual(['6789', '5556'])
  })
})

describe('FunnelPage: samples, timing status, lookups, caveats', () => {
  it('lists the by_sample counts as given, in order', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'Events by sample' })
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(4 + 1)
    expect(rows.slice(1).map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))).toEqual([
      ['daily', '61'],
      ['mixed', '22'],
      ['coarse', '93'],
      ['none', '24'],
    ])
  })
  it('lists all seven timing statuses with their counts', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'Timing status counts' })
    const rows = within(table).getAllByRole('row').slice(1)
    const byStatus = Object.fromEntries(rows.map((r) => within(r).getAllByRole('cell').map((c) => c.textContent as string)))
    expect(byStatus).toEqual({ confirmed: '10', corrected: '20', inferred: '30', date_corrected: '5', no_document: '15', not_checked: '100', ambiguous: '20' })
    expect(rows).toHaveLength(7)
  })
  it('says "not computed yet: ..." for the two milestone-2 fields when the file has them null, with the text from the file', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_NULL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    const list = screen.getByRole('list', { name: 'Not computed yet' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('not computed yet: fixture terciles need the fixture forwards')
    expect(items[1]).toHaveTextContent('not computed yet: fixture variance is a later measure')
    expect(list.textContent).not.toContain('not_computed')
    // Null is not drawn as an empty table or a "0 of 0" line.
    expect(screen.queryByRole('table', { name: 'By move tercile' })).toBeNull()
    expect(screen.queryByText(/have E ≤ 0/)).toBeNull()
    expect(screen.queryByRole('heading', { name: 'By move tercile' })).toBeNull()
  })
  it('keeps a status text that does not start with "not_computed:" whole', () => {
    render(<FunnelDisplay funnel={checked({ by_move_tercile: null, by_move_tercile_status: 'waiting on fixture data' })} />)
    expect(screen.getByText('not computed yet: waiting on fixture data')).toBeInTheDocument()
  })
  it('does not list a filled field under "Not computed yet": no list at all when both are filled', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(screen.queryByRole('list', { name: 'Not computed yet' })).toBeNull()
    expect(screen.queryByText(/not computed yet/i)).toBeNull()
  })
  it('lists only the null field when just one of the two is null', () => {
    const { unmount } = render(<FunnelDisplay funnel={checked({ evar_nonpositive: null, evar_nonpositive_status: 'not_computed: fixture waits' })} />)
    let items = within(screen.getByRole('list', { name: 'Not computed yet' })).getAllByRole('listitem')
    expect(items).toHaveLength(1)
    expect(items[0]).toHaveTextContent('Non-positive event variance — not computed yet: fixture waits')
    expect(screen.getByRole('table', { name: 'By move tercile' })).toBeInTheDocument() // the filled one is still drawn
    unmount()
    render(<FunnelDisplay funnel={checked({ by_move_tercile: null, by_move_tercile_status: 'not_computed: fixture waits' })} />)
    items = within(screen.getByRole('list', { name: 'Not computed yet' })).getAllByRole('listitem')
    expect(items).toHaveLength(1)
    expect(items[0]).toHaveTextContent('By move tercile — not computed yet: fixture waits')
    expect(screen.getByText('5 of 190 events (0.125) have E ≤ 0, among 200 in the primary sample')).toBeInTheDocument()
  })
  it('shows the lookups done and "provisional" while they are not complete', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    const para = screen.getByText('7').closest('p') as HTMLElement
    expect(para).toHaveTextContent('7 lookups done provisional')
    expect(screen.queryByText('complete')).toBeNull()
  })
  it('shows "complete" instead when the lookups are complete', () => {
    render(<FunnelDisplay funnel={checked({ lookups: { n_done: 41, complete: true } })} />)
    const para = screen.getByText('41').closest('p') as HTMLElement
    expect(para).toHaveTextContent('41 lookups done complete')
    expect(screen.queryByText('provisional')).toBeNull()
  })
  it('lists every caveat in a visible list, in order', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    const items = within(screen.getByRole('list', { name: 'Caveats' })).getAllByRole('listitem')
    expect(items.map((i) => i.textContent)).toEqual(['Fixture caveat one: invented for the test.', 'Fixture caveat two: also invented.'])
    for (const item of items) expect(item).toBeVisible()
  })
  it('shows an empty caveats list when the file has none', () => {
    render(<FunnelDisplay funnel={checked({ caveats: [] })} />)
    expect(within(screen.getByRole('list', { name: 'Caveats' })).queryAllByRole('listitem')).toHaveLength(0)
  })
})

describe('FunnelPage: by move tercile (filled)', () => {
  const HEADER = [
    'Sample',
    'Tercile',
    'Events',
    'With crush',
    'Mean |move|',
    'Mean crush',
    'Gap check changed',
    'Gap contradicts',
    'confirmed',
    'corrected',
    'inferred',
    'date_corrected',
    'no_document',
    'not_checked',
    'ambiguous',
  ]
  const rowsOf = (table: HTMLElement): string[][] =>
    within(table)
      .getAllByRole('row')
      .slice(1)
      .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent ?? ''))

  it('has a heading, one column per field and per timing status, and one row per entry, in the order of the file', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'By move tercile' })
    expect(screen.getByRole('heading', { name: 'By move tercile' })).toBeInTheDocument()
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(HEADER)
    expect(within(table).getAllByRole('row')).toHaveLength(3 + 1) // + header row
    expect(rowsOf(table)[0].slice(0, 2)).toEqual(['daily', '1'])
    expect(rowsOf(table)[1].slice(0, 2)).toEqual(['mixed', '2'])
    expect(rowsOf(table)[2].slice(0, 2)).toEqual(['coarse', '3'])
  })
  it('draws every number exactly as in the file: counts, means, share and the seven timing counts', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const table = await screen.findByRole('table', { name: 'By move tercile' })
    // sample, tercile, n_events, n_crush, mean_abs_move, mean_crush_mean_adj, n_gap_check_changed, share_gap_contradicts, then confirmed ... ambiguous
    expect(rowsOf(table)).toEqual([
      ['daily', '1', '40', '38', '0.0125', '-0.15', '3', '0.25', '1', '2', '3', '4', '5', '24', '1'],
      ['mixed', '2', '10', '10', '0.04', '-0.2', '0', '—', '0', '0', '0', '0', '0', '10', '0'],
      ['coarse', '3', '20', '0', '—', '—', '2', '0', '6', '0', '0', '0', '0', '14', '0'],
    ])
  })
  it('shows "—" for a null share_gap_contradicts and for null means, but "0" for a real zero', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    const rows = rowsOf(await screen.findByRole('table', { name: 'By move tercile' }))
    expect(rows[1][7]).toBe('—') // share null
    expect(rows[2][7]).toBe('0') // share 0
    expect(rows[2][4]).toBe('—') // mean_abs_move null
    expect(rows[2][5]).toBe('—') // mean_crush_mean_adj null
  })
  it('puts each timing count under its own status, not in the order the keys happen to be written', () => {
    const counts = { ambiguous: 7, not_checked: 6, no_document: 5, date_corrected: 4, inferred: 3, corrected: 2, confirmed: 1 } // written backwards
    const row = { ...FUNNEL_DATA_FIXTURE.by_move_tercile[0], timing_status_counts: counts }
    render(<FunnelDisplay funnel={checked({ by_move_tercile: [row] })} />)
    expect(rowsOf(screen.getByRole('table', { name: 'By move tercile' }))[0].slice(8)).toEqual(['1', '2', '3', '4', '5', '6', '7'])
  })
  it('shows the status text from the file as a note, without the machine word "computed:"', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'By move tercile' })
    expect(screen.getByText('fixture terciles from the fixture forwards')).toBeInTheDocument()
    expect(screen.queryByText(/computed: fixture/)).toBeNull()
  })
  it('draws an empty array as a table with only its header row', () => {
    render(<FunnelDisplay funnel={checked({ by_move_tercile: [] })} />)
    expect(within(screen.getByRole('table', { name: 'By move tercile' })).getAllByRole('row')).toHaveLength(1)
  })
  it('does not break the other tables: the by-status table is still the funnel-wide one', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'By move tercile' })
    expect(within(screen.getByRole('table', { name: 'Timing status counts' })).getAllByRole('row')).toHaveLength(7 + 1)
  })
})

describe('FunnelPage: non-positive event variance (filled)', () => {
  it('says "n of n_identified events (share) have E ≤ 0, among n_events in the primary sample", all as given', async () => {
    render(<FunnelPage fetchImpl={serving(FUNNEL_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Funnel steps' })
    expect(screen.getByRole('heading', { name: 'Non-positive event variance' })).toBeInTheDocument()
    expect(screen.getByText('5 of 190 events (0.125) have E ≤ 0, among 200 in the primary sample')).toBeInTheDocument()
  })
  it('shows the share from the file, never n / n_identified (5 / 190 = 0.0263...)', () => {
    render(<FunnelDisplay funnel={checked()} />)
    expect(screen.queryByText(/0\.026/)).toBeNull()
    expect(screen.getByText(/\(0\.125\)/)).toBeInTheDocument()
  })
  it('shows the status text from the file as a note, without the machine word "computed:"', () => {
    render(<FunnelDisplay funnel={checked()} />)
    expect(screen.getByText('fixture variance at the fixture day -1')).toBeInTheDocument()
  })
  it('shows "—" for a null share (only possible when nothing was identified)', () => {
    render(<FunnelDisplay funnel={checked({ evar_nonpositive: { n_events: 12, n_identified: 0, n: 0, share: null } })} />)
    expect(screen.getByText('0 of 0 events (—) have E ≤ 0, among 12 in the primary sample')).toBeInTheDocument()
  })
  it('shows a share of exactly 0 as 0, not as a dash', () => {
    render(<FunnelDisplay funnel={checked({ evar_nonpositive: { n_events: 9, n_identified: 9, n: 0, share: 0 } })} />)
    expect(screen.getByText('0 of 9 events (0) have E ≤ 0, among 9 in the primary sample')).toBeInTheDocument()
  })
})
