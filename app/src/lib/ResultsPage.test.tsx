import { describe, it, expect, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { ResultsDisplay, ResultsPage } from './ResultsPage'
import { parseTests, type TestsData } from './results'
import { TESTS_DATA_FIXTURE, TESTS_FIXTURE } from '../test/resultsFixture'
import { edited } from '../test/editHelpers'

/*
 * Mutations of fix R1 this file must catch (7 of 7 killed). Each was applied to src/lib/ResultsPage.tsx, one at a time, and
 * this file then failed; the file was restored and its sha256 checked each time (script outside the repo).
 *   RP1: the season-cut suffix of the Holm p dropped            RP2: its G taken from the primary row, not the cut row
 *   RP3: a cut row paired with a primary of any hypothesis      RP4: the failed-size-check note names hypotheses outside the family
 *   RP5: the Drivers-page pointer names every failed hypothesis RP6: the left-the-family item shown with none left
 *   RP7: the failed-size-check note dropped
 */

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The checked data for `ResultsDisplay`, built by the same validator the page uses, with some top-level fields replaced. */
function checked(patch: Record<string, unknown> = {}): TestsData {
  const r = parseTests({ ...TESTS_DATA_FIXTURE, ...patch })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

/** The cells of a table's body rows as text, one array per row. */
const bodyOf = (table: HTMLElement): string[][] =>
  within(table)
    .getAllByRole('row')
    .slice(1)
    .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent ?? ''))

/** The [name, value] pairs of a two-column table without a header row. */
const pairsOf = (table: HTMLElement): string[][] =>
  within(table)
    .getAllByRole('row')
    .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent ?? ''))

const robustnessHeadings = (): string[] => within(screen.getByRole('region', { name: 'Robustness checks' })).queryAllByRole('heading', { level: 3 }).map((h) => h.textContent ?? '')

const headersOf = (table: HTMLElement): string[] => within(table).getAllByRole('columnheader').map((h) => h.textContent ?? '')

describe('ResultsPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<ResultsPage fetchImpl={serving(TESTS_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading results')
    expect(screen.getByRole('heading', { level: 2, name: 'Results' })).toBeInTheDocument()
    await screen.findByRole('table', { name: 'Primary family' })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/tests.json by default, and the given url when there is one', async () => {
    const f = serving(TESTS_FIXTURE)
    const { unmount } = render(<ResultsPage fetchImpl={f} />)
    await screen.findByRole('table', { name: 'Primary family' })
    expect(f).toHaveBeenCalledWith('data/tests.json', { cache: 'no-cache' })
    unmount()
    const g = serving(TESTS_FIXTURE)
    render(<ResultsPage url="x/tests.json" fetchImpl={g} />)
    await screen.findByRole('table', { name: 'Primary family' })
    expect(g).toHaveBeenCalledWith('x/tests.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no table, when the file is missing (HTTP 404)', async () => {
    render(<ResultsPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The results could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('complementary')).toBeNull()
  })
  it('shows an error for the previous schema version (0.4.0)', async () => {
    render(<ResultsPage fetchImpl={serving({ ...TESTS_FIXTURE, schema_version: '0.4.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.4.0": this app only understands "0.5.0"')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error when the file is another kind (heatmap.json served at the tests url)', async () => {
    render(<ResultsPage fetchImpl={serving({ ...TESTS_FIXTURE, kind: 'heatmap' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "heatmap", expected "tests"')
  })
  it('shows an error naming the rule when the data has the wrong shape (a ragged power curve)', async () => {
    const body = { ...TESTS_FIXTURE, data: edited(TESTS_DATA_FIXTURE, ['g1', 'power', 0, 'power'], [0.25]) }
    render(<ResultsPage fetchImpl={serving(body)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/tests.json: g1.power[0].power must have 3 entries (one per shift), got 1')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<ResultsPage url="old/tests.json" fetchImpl={oldFetch} />)
    rerender(<ResultsPage url="new/tests.json" fetchImpl={serving(TESTS_FIXTURE)} />)
    await screen.findByRole('table', { name: 'Primary family' })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table', { name: 'Primary family' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('ResultsDisplay: the provisional-labels notice', () => {
  it('opens with the provisional notice built from the lookups, and every caveat once', () => {
    render(<ResultsDisplay tests={checked()} />)
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('Timing labels are provisional: 7 timing look-ups are done')
    for (const c of TESTS_DATA_FIXTURE.caveats) expect(screen.getAllByText(c)).toHaveLength(1)
    expect(within(notice).getAllByRole('listitem')).toHaveLength(TESTS_DATA_FIXTURE.caveats.length)
  })
  it('puts the notice before the first table', () => {
    render(<ResultsDisplay tests={checked()} />)
    const notice = screen.getByRole('complementary')
    const table = screen.getByRole('table', { name: 'Primary family' })
    expect(notice.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
  it('shows the sample label of the provenance', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(screen.getByText(/Sample:/)).toHaveTextContent('Sample: fixture-sample.')
  })
})

describe('ResultsDisplay: the primary family table', () => {
  it('has the columns asked for, in order', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(headersOf(screen.getByRole('table', { name: 'Primary family' }))).toEqual([
      'Hypothesis', 'Measure', 'Statistic', 'n', 'Estimate', 'SE', 'CI', 'Stat', 'df', 'p', 'Holm p',
    ])
  })
  it('has one row per primary row and no row of another role', () => {
    render(<ResultsDisplay tests={checked()} />)
    const rows = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    expect(rows).toHaveLength(2)
    expect(rows.map((r) => r[0])).toEqual(['H1', 'H2'])
    expect(rows.map((r) => r[2])).toEqual(['fix_stat_one', 'fix_stat_two'])
  })
  it('shows each number exactly as the file has it', () => {
    render(<ResultsDisplay tests={checked()} />)
    const [h1] = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    // n, estimate, se, CI, stat, df, p, Holm p
    expect(h1.slice(3)).toEqual(['11', '-0.5', '0.125', '[-0.75, -0.25]', '-4', '4', '0.0123', '0.0492'])
  })
  it('shows null as a dash (se, df and the interval of a randomisation test), never as 0', () => {
    render(<ResultsDisplay tests={checked()} />)
    const [, h2] = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    expect(h2.slice(3)).toEqual(['13', '0.75', '—', '—', '3.5', '—', '0.25', '1'])
  })
  it('names the measure with its units, adjustment and sample under it', () => {
    render(<ResultsDisplay tests={checked()} />)
    const [h1] = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    expect(h1[1]).toBe('fix_measure_afixture units A · market-adjusted · daily sample')
  })
  it('shows tiny and large numbers in the file\'s own notation, not rounded', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[0] = { ...rows[0], p_value: 6.35e-23, p_holm: 4.445e-22, estimate: -0.1991 }
    render(<ResultsDisplay tests={checked({ rows })} />)
    const [h1] = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    expect(h1[4]).toBe('-0.1991')
    expect(h1[9]).toBe('6.35e-23')
    expect(h1[10]).toBe('4.445e-22')
  })
  it('does no arithmetic: a stat and p that do not match estimate / se are shown as given', () => {
    // estimate -0.5 / se 0.125 would be -4; the file says 7.5, and the page must not "fix" it.
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[0] = { ...rows[0], stat: 7.5, p_value: 0.9, p_holm: 0.95 }
    render(<ResultsDisplay tests={checked({ rows })} />)
    const [h1] = bodyOf(screen.getByRole('table', { name: 'Primary family' }))
    expect(h1.slice(7)).toEqual(['7.5', '4', '0.9', '0.95'])
  })
  it('shows an interval with only one end as that end and a dash, not as no interval at all', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[0] = { ...rows[0], ci_lo: -0.75, ci_hi: null }
    rows[1] = { ...rows[1], ci_lo: null, ci_hi: 1.5 }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'Primary family' })).map((r) => r[6])).toEqual(['[-0.75, —]', '[—, 1.5]'])
  })
  it('shows a dash for a primary row that has no hypothesis', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[0] = { ...rows[0], hypothesis: null }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'Primary family' })).map((r) => r[0])).toEqual(['—', 'H2'])
  })
  it('shows the subgroup under the measure when it is not "all"', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[0] = { ...rows[0], subgroup_key: 'timing', subgroup_value: 'AMC' }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'Primary family' }))[0][1]).toContain('timing: AMC')
  })
})

describe('ResultsDisplay: robustness rows grouped under each hypothesis', () => {
  it('has a heading and a table per hypothesis, in H1, H2 order', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(robustnessHeadings()).toEqual(['H1', 'H2'])
    expect(screen.getByRole('table', { name: 'Robustness H1' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Robustness H2' })).toBeInTheDocument()
  })
  it('puts each robustness row under its own hypothesis, with its estimand', () => {
    render(<ResultsDisplay tests={checked()} />)
    const h1 = screen.getByRole('table', { name: 'Robustness H1' })
    expect(headersOf(h1)).toEqual(['Measure', 'Statistic', 'Estimand', 'n', 'Estimate', 'SE', 'CI', 'Stat', 'df', 'p'])
    const rows = bodyOf(h1)
    expect(rows.map((r) => r[1])).toEqual(['fix_stat_pw', 'fix_stat_rank'])
    expect(rows.map((r) => r[2])).toEqual(['precision_weighted', '—']) // a null estimand is a dash
    expect(rows[0].slice(3)).toEqual(['9', '-0.375', '0.25', '[-0.5, -0.125]', '-1.5', '8', '0.17'])
    expect(rows[1].slice(3)).toEqual(['10', '0.0625', '—', '—', '2.25', '—', '0.03'])
    expect(bodyOf(screen.getByRole('table', { name: 'Robustness H2' })).map((r) => r[1])).toEqual(['fix_stat_three'])
  })
  it('does not show the primary or exploratory rows in a robustness table', () => {
    render(<ResultsDisplay tests={checked()} />)
    const all = [...bodyOf(screen.getByRole('table', { name: 'Robustness H1' })), ...bodyOf(screen.getByRole('table', { name: 'Robustness H2' }))]
    expect(all).toHaveLength(3)
    expect(all.map((r) => r[1])).not.toContain('fix_stat_one')
    expect(all.map((r) => r[1])).not.toContain('fix_stat_four')
  })
  it('shows a withheld p-value as "withheld" with the G1 size in percent and its replications, keeps the estimate, and lists the note under the table', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[2] = { ...rows[2], p_value: null, ci_lo: null, ci_hi: null, g1_size: 0.241, g1_reps: 2000, note: 'Fixture note: withheld as mis-sized.' }
    render(<ResultsDisplay tests={checked({ rows })} />)
    const h1 = screen.getByRole('table', { name: 'Robustness H1' })
    // 0.241 of the replications = 24.10%; 2000 printed with its thousands separator.
    expect(bodyOf(h1)[0].slice(3)).toEqual(['9', '-0.375', '0.25', '—', '-1.5', '8', 'withheld (G1 size 24.10% over 2,000 replications)'])
    expect(bodyOf(h1)[1][9]).toBe('0.03') // a row without a G1 size keeps its p-value
    const notes = screen.getByRole('list', { name: 'Robustness H1 notes' })
    expect(within(notes).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['H1 fix_stat_pw: Fixture note: withheld as mis-sized.'])
    expect(screen.queryByRole('list', { name: 'Robustness H2 notes' })).toBeNull()
  })
  it('shows a rate re-measured on 10,000 replications with that count', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[2] = { ...rows[2], p_value: null, ci_lo: null, ci_hi: null, g1_size: 0.0606, g1_reps: 10000 }
    render(<ResultsDisplay tests={checked({ rows })} />)
    // 0.0606 = 6.06% (not 6.0600 or 0.0606); 10000 = 10,000.
    expect(bodyOf(screen.getByRole('table', { name: 'Robustness H1' }))[0][9]).toBe('withheld (G1 size 6.06% over 10,000 replications)')
  })
  it('shows a null p-value without a G1 size as a dash, not as withheld', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[2] = { ...rows[2], p_value: null }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'Robustness H1' }))[0][9]).toBe('—')
  })
  it('captions the primary family with its row notes, naming the subgroup of a note when it is not "all"', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[1] = { ...rows[1], note: 'Fixture note: the counterfactual season cut.' }
    rows[4] = { ...rows[4], subgroup_key: 'season_cut', subgroup_value: 'FX9_into_FX8', note: 'Fixture note: not a test of its own.' }
    render(<ResultsDisplay tests={checked({ rows })} />)
    const caption = screen.getByRole('list', { name: 'Primary family notes' })
    expect(within(caption).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['H2 fix_stat_two: Fixture note: the counterfactual season cut.'])
    const h2 = screen.getByRole('list', { name: 'Robustness H2 notes' })
    expect(h2.textContent).toBe('H2 fix_stat_three (season_cut: FX9_into_FX8): Fixture note: not a test of its own.')
    expect(screen.queryByRole('list', { name: 'Exploratory notes' })).toBeNull()
  })
  it('names a note of a row without a hypothesis with a dash', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[5] = { ...rows[5], note: 'Fixture note: exploratory.' }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(screen.getByRole('list', { name: 'Exploratory notes' }).textContent).toBe('— fix_stat_four (timing: AMC): Fixture note: exploratory.')
  })
  it('says so when the file has no robustness rows', () => {
    const rows = TESTS_DATA_FIXTURE.rows.filter((r) => r.role !== 'robustness')
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(screen.getByText('The file has no robustness rows.')).toBeInTheDocument()
    expect(robustnessHeadings()).toEqual([])
  })
  it('keeps a robustness row without a hypothesis, under its own heading, last', () => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[3] = { ...rows[3], hypothesis: null }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(robustnessHeadings()).toEqual(['H1', 'H2', 'No hypothesis'])
    expect(bodyOf(screen.getByRole('table', { name: 'Robustness No hypothesis' }))[0][1]).toBe('fix_stat_rank')
  })
})

describe('ResultsDisplay: exploratory rows in a collapsible section', () => {
  it('is a details element, closed by default, whose summary counts the rows', () => {
    render(<ResultsDisplay tests={checked()} />)
    const summary = screen.getByText('Exploratory rows (2)')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details).not.toHaveAttribute('open')
  })
  it('lists the exploratory rows with q (BH), and only those rows', () => {
    render(<ResultsDisplay tests={checked()} />)
    const table = screen.getByRole('table', { name: 'Exploratory', hidden: true })
    expect(headersOf(table)).toEqual(['Measure', 'Statistic', 'n', 'Estimate', 'SE', 'CI', 'Stat', 'df', 'p', 'q (BH)'])
    const rows = bodyOf(table)
    expect(rows.map((r) => r[1])).toEqual(['fix_stat_four', 'fix_stat_mean'])
    expect(rows[0].slice(2)).toEqual(['6', '0.1875', '0.0625', '[0.0625, 0.3125]', '3', '5', '0.0105', '0.0321'])
  })
  it('shows a missing p-value, stat, interval and q as dashes, and the sample and subgroup under the measure', () => {
    render(<ResultsDisplay tests={checked()} />)
    const rows = bodyOf(screen.getByRole('table', { name: 'Exploratory', hidden: true }))
    expect(rows[1].slice(2)).toEqual(['4', '0.875', '—', '—', '—', '—', '—', '—'])
    expect(rows[0][0]).toBe('fix_measure_cfixture units C · market-adjusted · coarse sample · timing: AMC')
  })
})

describe('ResultsDisplay: the G1 gate', () => {
  it('states the replications and the band', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(screen.getByText(/Simulated size check/)).toHaveTextContent('500 replications. Band: 0.25 to 0.5.')
  })
  it('lists each calibrated rejection rate against the upper edge of the band, with the exporter\'s verdict', () => {
    render(<ResultsDisplay tests={checked()} />)
    const table = screen.getByRole('table', { name: 'G1 calibration' })
    expect(headersOf(table)).toEqual(['Hypothesis', 'Statistic', 'Rejection rate', 'Band upper edge', 'Verdict'])
    expect(bodyOf(table)).toEqual([
      ['H1', 'fix_stat_one', '0.375', '0.5', 'pass'],
      ['H2', 'fix_stat_two', '0.625', '0.5', 'fail'],
    ])
  })
  it('shows the verdict as written, not recomputed: a rate below the band that the file marks as pass stays pass', () => {
    const g1 = { ...TESTS_DATA_FIXTURE.g1, calibrated: [{ hypothesis: 'H1', statistic: 'fix_stat_one', rejection_rate: 0.0065, pass: true }] }
    render(<ResultsDisplay tests={checked({ g1 })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'G1 calibration' }))).toEqual([['H1', 'fix_stat_one', '0.0065', '0.5', 'pass']])
  })
  it('shows the detectable shift at 80% power, or "not reached on the grid" when it is null, with the power at each shift', () => {
    render(<ResultsDisplay tests={checked()} />)
    const table = screen.getByRole('table', { name: 'G1 power' })
    expect(headersOf(table)).toEqual(['Hypothesis', 'Smallest shift with 80% power', 'Power at each shift'])
    expect(bodyOf(table)).toEqual([
      ['H1', '2', '0.5: 0.25 · 1: 0.5 · 2: 1'],
      ['H2', 'not reached on the grid', '0.5: 0.125 · 1: 0.25'],
    ])
  })
  it('shows a detectable shift of 0 as 0 (it is a number, not missing)', () => {
    const g1 = { ...TESTS_DATA_FIXTURE.g1, power: [{ hypothesis: 'H1', shifts: [0], power: [0.9], detectable_80: 0 }] }
    render(<ResultsDisplay tests={checked({ g1 })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'G1 power' }))[0][1]).toBe('0')
  })
  it('lists the simulation calibration parameters in a collapsed section', () => {
    render(<ResultsDisplay tests={checked()} />)
    const summary = screen.getByText('Simulation calibration')
    expect(summary.closest('details')).not.toHaveAttribute('open')
    expect(pairsOf(screen.getByRole('table', { name: 'G1 calibration parameters', hidden: true }))).toEqual([
      ['fix_phi', '0.5'],
      ['fix_noise', '2'],
    ])
  })
})

describe('ResultsDisplay: the Holm statement', () => {
  const items = () => within(screen.getByRole('list', { name: 'Holm statement' })).getAllByRole('listitem').map((li) => li.textContent)
  const failedNote = () => screen.queryByLabelText('Failed size checks')

  it('states the family, what was tested and the untested hypotheses entering as p = 1, and lists no left_family when it is empty', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(items()).toEqual(['Family: H1, H2, H3', 'Tested: H1, H2', 'Untested, entering the family as p = 1: H3'])
    expect(screen.queryByText(/left/i)).toBeNull()
  })
  it('says a hypothesis of the family whose size check failed stays in it with its p-value (fix R1), and does not point elsewhere when its rows are here', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(failedNote()).toHaveTextContent(
      "H2 failed gate G1's size check and stays in the family with its p-value: the statistic is liberal on this design, so a rejection by it would not be trusted.",
    )
    expect(screen.queryByText(/Drivers page/)).toBeNull()
  })
  it('names every failed hypothesis of the declared family once, and points to the Drivers page for those whose rows are not in this file', () => {
    const holm = { family: ['H1', 'H2', 'H5', 'H6', 'H7'], tested: ['H1', 'H2', 'H5', 'H6', 'H7'], untested: [], left_family: [] }
    const calibrated = [
      { hypothesis: 'H1', statistic: 'fix_stat_one', rejection_rate: 0.375, pass: true },
      { hypothesis: 'H5', statistic: 'fix_stat_five', rejection_rate: 0.625, pass: false },
      { hypothesis: 'H5', statistic: 'fix_stat_five_b', rejection_rate: 0.75, pass: false },
      { hypothesis: 'H6', statistic: 'fix_stat_six', rejection_rate: 0.5625, pass: false },
      { hypothesis: 'H7', statistic: 'fix_stat_seven', rejection_rate: 0.875, pass: false },
    ]
    render(<ResultsDisplay tests={checked({ holm, g1: { ...TESTS_DATA_FIXTURE.g1, calibrated } })} />)
    expect(items()).toEqual(['Family: H1, H2, H5, H6, H7', 'Tested: H1, H2, H5, H6, H7', 'Untested, entering the family as p = 1: none'])
    expect(failedNote()).toHaveTextContent(
      "H5, H6, H7 failed gate G1's size check and stay in the family with their p-values: the statistic is liberal on this design, so a rejection by it would not be trusted. " +
        'The rows of H5, H6, H7 are on the Drivers page.',
    )
    expect(failedNote()).not.toHaveTextContent('left')
  })
  it('lists the hypotheses that left the family when there are some, and says nothing of a failed hypothesis outside the family', () => {
    const holm = { ...TESTS_DATA_FIXTURE.holm, left_family: ['H4'] }
    const calibrated = [
      { hypothesis: 'H1', statistic: 'fix_stat_one', rejection_rate: 0.375, pass: true },
      { hypothesis: 'H4', statistic: 'fix_stat_four', rejection_rate: 0.625, pass: false },
    ]
    render(<ResultsDisplay tests={checked({ holm, g1: { ...TESTS_DATA_FIXTURE.g1, calibrated } })} />)
    expect(items()).toEqual(['Family: H1, H2, H3', 'Tested: H1, H2', 'Untested, entering the family as p = 1: H3', 'Left the family: H4'])
    expect(failedNote()).toBeNull()
  })
})

describe('ResultsDisplay: the season-cut counterfactual next to the Holm p', () => {
  const cutRows = (patch: Record<string, unknown> = {}) => {
    const rows: Record<string, unknown>[] = structuredClone(TESTS_DATA_FIXTURE.rows)
    rows[4] = { ...rows[4], subgroup_key: 'season_cut', subgroup_value: 'FX9_into_FX8', n_clusters: 3, p_holm: 0.75, ...patch }
    return rows
  }
  const holmColumn = () => bodyOf(screen.getByRole('table', { name: 'Primary family' })).map((r) => r[10])

  it('shows the Holm p of a primary with the cut row\'s cluster count G and Holm p, and leaves the other primaries alone', () => {
    render(<ResultsDisplay tests={checked({ rows: cutRows() })} />)
    expect(holmColumn()).toEqual(['0.0492', '1 (G = 3: 0.75)'])
  })
  it('takes G and the Holm p from the cut row as given, a dash when it has none', () => {
    render(<ResultsDisplay tests={checked({ rows: cutRows({ n_clusters: null, p_holm: null }) })} />)
    expect(holmColumn()).toEqual(['0.0492', '1 (G = —: —)'])
  })
  it('does not pair a cut row with a primary of another hypothesis, nor a primary without a hypothesis', () => {
    render(<ResultsDisplay tests={checked({ rows: cutRows({ hypothesis: 'H3' }) })} />)
    expect(holmColumn()).toEqual(['0.0492', '1'])
    cleanup()
    const rows = cutRows({ hypothesis: null })
    rows[1] = { ...rows[1], hypothesis: null }
    render(<ResultsDisplay tests={checked({ rows })} />)
    expect(holmColumn()).toEqual(['0.0492', '1'])
  })
  it('does not treat a robustness row of another subgroup as a cut', () => {
    render(<ResultsDisplay tests={checked()} />)
    expect(holmColumn()).toEqual(['0.0492', '1'])
  })
})
