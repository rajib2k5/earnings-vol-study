import { describe, it, expect, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { ImpliedRealisedDisplay, ImpliedRealisedPage } from './ImpliedRealisedPage'
import { parseImpliedRealised, type ImpliedRealisedData } from './impliedRealised'
import { IMPLIED_REALISED_DATA_FIXTURE, IMPLIED_REALISED_FIXTURE } from '../test/impliedRealisedFixture'
import { edited } from '../test/editHelpers'

/*
 * Mutations this file must catch: 18 of 18 tried were killed at milestone 4. Each was applied to src/lib/ImpliedRealisedPage.tsx, one at a time,
 * and this file then failed; the file was restored and its sha256 checked each time (script outside the repo).
 *   IP1: BMO and AMC marks swapped
 *   IP2: share shown as a fraction, not a percent
 *   IP3: benchmark hard-coded instead of read from the file
 *   IP4: gate note flipped (passed/failed text swapped)
 *   IP5: verdict badge always says pass
 *   IP6: Wald degrees of freedom swapped
 *   IP7: role text inverted
 *   IP8: all-events-drawn text on the wrong count
 *   IP9: hover title swaps expected and realised
 *   IP10: provisional notice removed
 *   IP11: "timing unknown" always in the legend
 *   IP12: null status shows as an empty cell
 *   IP13: diagonal line flipped
 *   IP14: event count taken from the wrong summary field
 *   IP15: slope row shows the intercept
 *   IP16: mean log ratio row shows the median ratio
 *   IP17: late answer for an old url no longer ignored
 *   IP18: empty-chart message never shown
 * After fix R1 the tests behind IP3, IP4, IP5 and IP7 changed; those four were re-tried (killed). New (3 of 3 killed):
 *   IP19: the one-way p shows the null as a dash instead of "withheld (G1 ...)"
 *   IP20: the primary's stays-in-the-family sentence dropped
 *   IP21: the band upper edge shows the rate instead
 */

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The checked data for `ImpliedRealisedDisplay`, built by the same validator the page uses, with some top-level fields replaced. */
function checked(patch: Record<string, unknown> = {}): ImpliedRealisedData {
  const r = parseImpliedRealised({ ...IMPLIED_REALISED_DATA_FIXTURE, ...patch })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

/**
 * The checked fixture with the regression fields replaced AFTER the validator: for display tests whose data the parser's
 * cross-field rules would refuse (a verdict that contradicts its rate, another benchmark). The page must still show it as given.
 */
function uncheckedRegression(patch: Record<string, unknown>, summaryPatch: Record<string, unknown> = {}): ImpliedRealisedData {
  const data = checked()
  return { ...data, summary: { ...data.summary, ...summaryPatch, regression: { ...data.summary.regression, ...patch } } }
}

/** The [name, value, detail] of each row of the summary table. */
const summaryOf = (): string[][] =>
  within(screen.getByRole('table', { name: 'Summary' }))
    .getAllByRole('row')
    .slice(1)
    .map((r) => [within(r).getByRole('rowheader').textContent ?? '', ...within(r).getAllByRole('cell').map((c) => c.textContent ?? '')])

/** The value cell of the summary row called `name`. */
const valueOf = (name: string): string => (summaryOf().find((r) => r[0] === name) as string[])[1]
const detailOf = (name: string): string => (summaryOf().find((r) => r[0] === name) as string[])[2]

const scatter = (events = 4): HTMLElement =>
  screen.getByRole('img', { name: `Scatter of the realised absolute move against the expected absolute move, ${events} events, with the line where they are equal` })
const dots = (svg: HTMLElement): Element[] => Array.from(svg.querySelectorAll('use.dot'))
const attr = (e: Element, name: string): number => Number(e.getAttribute(name))

describe('ImpliedRealisedPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<ImpliedRealisedPage fetchImpl={serving(IMPLIED_REALISED_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading implied and realised moves')
    expect(screen.getByRole('heading', { level: 2, name: 'Implied vs realised' })).toBeInTheDocument()
    await screen.findByRole('table', { name: 'Summary' })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/implied_vs_realised.json by default, and the given url when there is one', async () => {
    const f = serving(IMPLIED_REALISED_FIXTURE)
    const { unmount } = render(<ImpliedRealisedPage fetchImpl={f} />)
    await screen.findByRole('table', { name: 'Summary' })
    expect(f).toHaveBeenCalledWith('data/implied_vs_realised.json', { cache: 'no-cache' })
    unmount()
    const g = serving(IMPLIED_REALISED_FIXTURE)
    render(<ImpliedRealisedPage url="x/implied.json" fetchImpl={g} />)
    await screen.findByRole('table', { name: 'Summary' })
    expect(g).toHaveBeenCalledWith('x/implied.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no table, no chart and no notice, when the file is missing (HTTP 404)', async () => {
    render(<ImpliedRealisedPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The implied and realised moves could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('complementary')).toBeNull()
  })
  it('shows an error for the previous schema version (0.4.0)', async () => {
    render(<ImpliedRealisedPage fetchImpl={serving({ ...IMPLIED_REALISED_FIXTURE, schema_version: '0.4.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.4.0": this app only understands "0.5.0"')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error when the file is another kind (drivers.json served at the implied-vs-realised url)', async () => {
    render(<ImpliedRealisedPage fetchImpl={serving({ ...IMPLIED_REALISED_FIXTURE, kind: 'drivers' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "drivers", expected "implied_vs_realised"')
  })
  it('shows an error naming the rule when the data has the wrong shape (a reversed slope interval)', async () => {
    const body = { ...IMPLIED_REALISED_FIXTURE, data: edited(IMPLIED_REALISED_DATA_FIXTURE, ['summary', 'regression', 'b_ci'], [1.25, 0.25]) }
    render(<ImpliedRealisedPage fetchImpl={serving(body)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/implied_vs_realised.json: summary.regression.b_ci must not decrease: the low end (1.25) is above the high end (0.25)')
    expect(screen.queryByRole('img')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<ImpliedRealisedPage url="old.json" fetchImpl={oldFetch} />)
    rerender(<ImpliedRealisedPage url="new.json" fetchImpl={serving(IMPLIED_REALISED_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Summary' })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('ImpliedRealisedDisplay: the provisional-labels notice', () => {
  it('opens with the provisional notice built from the lookups, and every caveat once', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('Timing labels are provisional: 7 timing look-ups are done')
    for (const c of IMPLIED_REALISED_DATA_FIXTURE.caveats) expect(screen.getAllByText(c)).toHaveLength(1)
    expect(within(notice).getAllByRole('listitem')).toHaveLength(IMPLIED_REALISED_DATA_FIXTURE.caveats.length)
  })
  it('says the labels are complete when the file says so', () => {
    render(<ImpliedRealisedDisplay data={checked({ lookups: { n_done: 9, complete: true } })} />)
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing look-ups are complete: 9 done.')
  })
  it('puts the notice before the summary and the chart', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const notice = screen.getByRole('complementary')
    expect(notice.compareDocumentPosition(screen.getByRole('table', { name: 'Summary' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(notice.compareDocumentPosition(scatter()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
  it('shows the sample label of the provenance', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(screen.getByText(/Sample:/)).toHaveTextContent('Sample: fixture-sample.')
  })
})

describe('ImpliedRealisedDisplay: the summary', () => {
  it('lists the measures asked for, in order, each with its value and detail', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(summaryOf()).toEqual([
      ['Events', '5', '4 with an expected move; 1 with a non-positive event variance'],
      ['Share with realised move above the expected move', '50.00%', 'SE 12.50%; p = 0.75 against the benchmark 42.50%'],
      ['Slope b of realised on implied variance', '0.75', 'SE 0.25; interval [0.25, 1.25]'],
      ['Intercept a', '0.001', 'SE 0.0005'],
      ['Joint Wald test a = 0, b = 1', 'F(2, 9) = 2.5', 'p = 0.125; Holm p 0.5; one-way p withheld (G1 62.50%); n = 5; 4 date clusters, 3 firm clusters'],
      ['Role of the test', 'primary', 'in the confirmatory family'],
      ['Gate G1 for the test', 'fail56.25%', 'rejection rate under the calibrated null; band upper edge 50.00%'],
      ['Mean log ratio', '-0.25', 'of the realised to the expected |move|'],
      ['Median ratio', '0.75', 'of the realised to the expected |move|'],
    ])
  })
  it('takes the counts from the file\'s summary, not from the points (they may be a different subset)', () => {
    const summary = { ...IMPLIED_REALISED_DATA_FIXTURE.summary, n: 336, n_with_implied_abs_move: 332, n_evar_nonpositive: 4 }
    render(<ImpliedRealisedDisplay data={checked({ summary })} />)
    expect(valueOf('Events')).toBe('336')
    expect(detailOf('Events')).toBe('332 with an expected move; 4 with a non-positive event variance')
  })
  it('compares the share with the benchmark the file gives, not a fixed 42.5%', () => {
    // the parser accepts only the declared 0.425 (rule I4); the page must still read the benchmark from the data
    render(<ImpliedRealisedDisplay data={uncheckedRegression({}, { share_exceed_benchmark: 0.5, share_exceed: 0.4006, share_exceed_se: 0.0242, share_exceed_p: 0.3191 })} />)
    expect(valueOf('Share with realised move above the expected move')).toBe('40.06%')
    expect(detailOf('Share with realised move above the expected move')).toBe('SE 2.42%; p = 0.3191 against the benchmark 50.00%')
  })
  it('shows the slope, intercept and Wald numbers as the file has them, and a Holm and one-way p-value when there are any', () => {
    const regression = {
      ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression,
      b: 0.767, b_se: 0.1504, b_ci: [0.4648, 1.0691], a: 0.00082971, a_se: 0.00080379, wald_f: 1.3253, wald_df: 49, wald_p: 0.2751, p_holm: 0.55,
      wald_p_one_way: 0.0123, g1_rate_one_way: 0.25, g1_pass_one_way: true,
    }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    expect(valueOf('Slope b of realised on implied variance')).toBe('0.767')
    expect(detailOf('Slope b of realised on implied variance')).toBe('SE 0.1504; interval [0.4648, 1.0691]')
    expect(valueOf('Intercept a')).toBe('0.00082971')
    expect(detailOf('Intercept a')).toBe('SE 0.00080379')
    expect(valueOf('Joint Wald test a = 0, b = 1')).toBe('F(2, 49) = 1.3253')
    expect(detailOf('Joint Wald test a = 0, b = 1')).toBe('p = 0.2751; Holm p 0.55; one-way p 0.0123; n = 5; 4 date clusters, 3 firm clusters')
  })
  it('does no arithmetic: a p-value that does not match the F statistic is shown as given', () => {
    const regression = { ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression, wald_f: 100, wald_p: 0.9 }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    expect(valueOf('Joint Wald test a = 0, b = 1')).toBe('F(2, 9) = 100')
    expect(detailOf('Joint Wald test a = 0, b = 1')).toContain('p = 0.9;')
  })
  it('shows the role as written: primary says it is in the confirmatory family, exploratory that it is not', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(valueOf('Role of the test')).toBe('primary')
    expect(detailOf('Role of the test')).toBe('in the confirmatory family')
  })
  it('shows an exploratory test with no Holm p', () => {
    const regression = { ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression, role: 'exploratory', p_holm: null }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    expect(valueOf('Role of the test')).toBe('exploratory')
    expect(detailOf('Role of the test')).toBe('not in the confirmatory family')
    expect(detailOf('Joint Wald test a = 0, b = 1')).toContain('Holm p —;')
  })
  it('shows the one-way p-value as withheld with its G1 rate when its check failed, as a dash when it was never sized', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(detailOf('Joint Wald test a = 0, b = 1')).toContain('one-way p withheld (G1 62.50%);')
    cleanup()
    const regression = { ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression, wald_p_one_way: null, g1_rate_one_way: null, g1_pass_one_way: null }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    expect(detailOf('Joint Wald test a = 0, b = 1')).toContain('one-way p —;')
  })
  it('shows the G1 rate as a percent next to the verdict badge', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(valueOf('Gate G1 for the test')).toBe('fail56.25%')
  })
  it('says the primary joint test failed its size check, is liberal and a rejection would not be trusted, and stays in the family with its Holm p (fix R1)', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(screen.getByRole('note', { name: 'Gate G1 verdict' })).toHaveTextContent(
      "The joint test failed gate G1's size check: under the calibrated null it rejects 56.25% of the time, above the band's upper edge (50.00%). " +
        'It is liberal on this design, so a rejection by it would not be trusted. It stays in the declared Holm family as a primary test with its p-value (Holm p 0.5).',
    )
  })
  it('says a failed exploratory joint test is an indication, not a test', () => {
    const regression = { ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression, role: 'exploratory', p_holm: null }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    const note = screen.getByRole('note', { name: 'Gate G1 verdict' })
    expect(note).toHaveTextContent(/a rejection by it would not be trusted\. Its p-value is exploratory: read it as an indication, not as a test\.$/)
    expect(note).not.toHaveTextContent('Holm family')
  })
  it('says the joint test passed gate G1 when the file says so, with a pass badge, and does not say it failed', () => {
    const regression = { ...IMPLIED_REALISED_DATA_FIXTURE.summary.regression, g1_pass: true, g1_rate: 0.0425 }
    render(<ImpliedRealisedDisplay data={checked({ summary: { ...IMPLIED_REALISED_DATA_FIXTURE.summary, regression } })} />)
    const note = screen.getByRole('note', { name: 'Gate G1 verdict' })
    expect(note).toHaveTextContent("The joint test passed gate G1: under the calibrated null it rejects 4.25% of the time, within the band's upper edge (50.00%).")
    expect(note).not.toHaveTextContent('failed')
    expect(valueOf('Gate G1 for the test')).toBe('pass4.25%')
  })
  it('shows the verdict as written, not recomputed: a rate of 99% marked pass stays pass', () => {
    // the parser refuses this verdict (rule I2); the page must still not recompute it
    render(<ImpliedRealisedDisplay data={uncheckedRegression({ g1_pass: true, g1_rate: 0.99 })} />)
    expect(valueOf('Gate G1 for the test')).toBe('pass99.00%')
  })
})

describe('ImpliedRealisedDisplay: the scatter', () => {
  it('draws one dot per event that has an expected move, in file order, and none for the event without one', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const svg = scatter()
    expect(dots(svg).map((d) => d.getAttribute('data-event'))).toEqual(['FIXA:2031-01-01', 'FIXB:2031-02-01', 'FIXC:2031-03-01', 'FIXD:2031-04-01'])
    expect(svg.querySelector('[data-event="FIXE:2031-05-01"]')).toBeNull()
  })
  it('puts each dot at its hand-worked pixel: x is the expected move, y the realised move, y growing upwards', () => {
    // Axes 0 .. 10% over the 448 pixel plot area (x 56..504, y 464..16): cx = 56 + x / 0.1 * 448, cy = 464 - y / 0.1 * 448
    render(<ImpliedRealisedDisplay data={checked()} />)
    const px = dots(scatter()).map((d) => [attr(d, 'x'), attr(d, 'y')])
    const expected = [[280, 352], [336, 16], [196, 296], [224, 408]]
    px.forEach(([x, y], i) => {
      expect(x, `dot ${i} x`).toBeCloseTo(expected[i][0], 6)
      expect(y, `dot ${i} y`).toBeCloseTo(expected[i][1], 6)
    })
  })
  it('draws the line y = x from the bottom left to the top right corner of the plot area', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const line = scatter().querySelector('line.diagonal') as Element
    expect([attr(line, 'x1'), attr(line, 'y1'), attr(line, 'x2'), attr(line, 'y2')]).toEqual([56, 464, 504, 16])
  })
  it('gives BMO, AMC and unknown timing different marks (shape through the symbol, colour through the class)', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const svg = scatter()
    expect(dots(svg).map((d) => [d.getAttribute('href'), d.getAttribute('class')])).toEqual([
      ['#mark-bmo', 'dot mark-bmo'],
      ['#mark-amc', 'dot mark-amc'],
      ['#mark-amc', 'dot mark-amc'],
      ['#mark-unknown', 'dot mark-unknown'],
    ])
    // the three symbols the dots refer to exist, and the two named ones differ in shape
    expect(svg.querySelector('defs circle#mark-bmo')).not.toBeNull()
    expect(svg.querySelector('defs path#mark-amc')).not.toBeNull()
    expect(svg.querySelector('defs circle#mark-unknown')).not.toBeNull()
  })
  it('titles each dot with the event, its timing and both moves as percents', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(dots(scatter()).map((d) => d.querySelector('title')?.textContent)).toEqual([
      'FIXA 2031-01-02 (BMO): expected 5.00%, realised 2.50%',
      'FIXB 2031-02-02 (AMC): expected 6.25%, realised 10.00%',
      'FIXC 2031-03-03 (AMC): expected 3.13%, realised 3.75%',
      'FIXD 2031-04-02 (timing unknown): expected 3.75%, realised 1.25%',
    ])
  })
  it('labels both axes with the same round percents, and names them', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const texts = Array.from(scatter().querySelectorAll('text.tick')).map((t) => t.textContent)
    // per tick: the y label, then the x label
    expect(texts.slice(0, 12)).toEqual(['0%', '0%', '2%', '2%', '4%', '4%', '6%', '6%', '8%', '8%', '10%', '10%'])
    expect(texts.slice(12)).toEqual(['expected |move| from the options, day -1', 'realised |move|, day 0'])
  })
  it('has one gridline per tick on each axis', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(scatter().querySelectorAll('line.grid-line')).toHaveLength(12)
  })
  it('has a legend that names BMO, AMC and unknown timing, because colour is not the only cue', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const items = within(screen.getByRole('list', { name: 'Legend' })).getAllByRole('listitem')
    expect(items.map((li) => li.textContent?.trim())).toEqual(['BMO (reported before the open)', 'AMC (reported after the close)', 'timing unknown'])
  })
  it('leaves "timing unknown" out of the legend when every event has a timing', () => {
    const points = structuredClone(IMPLIED_REALISED_DATA_FIXTURE.points)
    points[3].timing_used = 'BMO'
    render(<ImpliedRealisedDisplay data={checked({ points })} />)
    const items = within(screen.getByRole('list', { name: 'Legend' })).getAllByRole('listitem')
    expect(items.map((li) => li.textContent?.trim())).toEqual(['BMO (reported before the open)', 'AMC (reported after the close)'])
  })
  it('counts the events without an expected move under the chart', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    expect(screen.getByLabelText('Events not drawn')).toHaveTextContent('1 of 5 events have no expected move (the options give none) and are not drawn.')
  })
  it('says all events are drawn when every event has an expected move', () => {
    const points = IMPLIED_REALISED_DATA_FIXTURE.points.slice(0, 4)
    render(<ImpliedRealisedDisplay data={checked({ points })} />)
    expect(screen.getByLabelText('Events not drawn')).toHaveTextContent('All 4 events are drawn.')
    expect(dots(scatter(4))).toHaveLength(4)
  })
  it('draws no chart, and says so, when no event has an expected move; the summary is still there', () => {
    const points = IMPLIED_REALISED_DATA_FIXTURE.points.map((p) => ({ ...p, implied_abs_move_total: null }))
    render(<ImpliedRealisedDisplay data={checked({ points })} />)
    expect(screen.getByText('No event has an expected move to draw.')).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('list', { name: 'Legend' })).toBeNull()
    expect(screen.getByLabelText('Events not drawn')).toHaveTextContent('5 of 5 events have no expected move')
    expect(screen.getByRole('table', { name: 'Summary' })).toBeInTheDocument()
  })
  it('draws no chart for a file with no points at all', () => {
    render(<ImpliedRealisedDisplay data={checked({ points: [] })} />)
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByLabelText('Events not drawn')).toHaveTextContent('All 0 events are drawn.')
  })
})

describe('ImpliedRealisedDisplay: the numbers behind the scatter', () => {
  it('lists every event, also the one without an expected move, in a collapsed section', () => {
    render(<ImpliedRealisedDisplay data={checked()} />)
    const summary = screen.getByText(/Numbers behind the scatter/)
    expect(summary).toHaveTextContent('(5 events)')
    expect(summary.closest('details')).not.toHaveAttribute('open')
    const table = screen.getByRole('table', { name: 'Events', hidden: true })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Event', 'Day 0', 'Timing', 'Expected |move|', 'Realised |move|', 'Expected move status'])
    const rows = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))
    expect(rows).toEqual([
      ['FIXA:2031-01-01', '2031-01-02', 'BMO', '0.05', '0.025', 'ok'],
      ['FIXB:2031-02-01', '2031-02-02', 'AMC', '0.0625', '0.1', 'ok'],
      ['FIXC:2031-03-01', '2031-03-03', 'AMC', '0.03125', '0.0375', 'ok'],
      ['FIXD:2031-04-01', '2031-04-02', '—', '0.0375', '0.0125', '—'],
      ['FIXE:2031-05-01', '2031-05-02', 'BMO', '—', '0.05', 'nonpositive_event_variance'],
    ])
  })
})
