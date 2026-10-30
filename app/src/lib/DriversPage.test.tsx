import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { DriversDisplay, DriversPage } from './DriversPage'
import { parseDrivers, type DriverModel, type DriversData } from './drivers'
import { DRIVERS_DATA_FIXTURE, DRIVERS_FIXTURE } from '../test/driversFixture'
import { edited } from '../test/editHelpers'

/*
 * Mutations this file must catch. Each was applied to src/lib/DriversPage.tsx, one at a time, and this file then failed; the
 * file was restored and its sha256 checked each time (script outside the repo).
 * Milestone 4 (21 of 21 killed then). Fix R1 removed DP4, DP5 and DP15 (the left-the-family note, the all-declared heading
 * and its in-the-family column) and changed the tests behind DP1, DP3 and DP9, which were re-tried after it (killed); the
 * others were not re-tried:
 *   DP1: show the p-value (a dash) instead of "withheld"
 *   DP2: Wald df shows the denominator only
 *   DP3: failed-gate note flipped
 *   DP6: Holm p column shows q instead
 *   DP7: rejection rate shown as a fraction, not a percent
 *   DP8: band upper edge column shows the lower edge
 *   DP9: verdict recomputed from the rate instead of shown as written
 *   DP10: primary-model badge on the wrong model
 *   DP11: models shown in reverse order
 *   DP12: withheld point not drawn hollow
 *   DP13: an interval line is drawn for withheld rows too (zero length)
 *   DP14: plot takes every term with a coefficient, one-way rows too
 *   DP16: a detectable shift of 0 reads "not reached"
 *   DP17: provisional notice removed
 *   DP18: late answer for an old url no longer ignored
 *   DP19: an interval with one end shows as no interval (&& instead of ||)
 *   DP20: a null hypothesis shows as an empty cell
 *   DP21: a null note shows as an empty cell
 * Fix R1 and R7 of the milestone-4 review (10 of 10 killed):
 *   DP22: the stays-in-the-family sentence dropped              DP23: it also names a failed hypothesis outside the family
 *   DP24: the left-the-family sentence shown with none left     DP25: the left-the-family Holm item shown with none left
 *   DP26: the sensitivity caption names the kept hypotheses     DP27: the season-cut rows of the sensitivity dropped
 *   DP28: a failed primary's p loses its G1 size line           DP29: every caveat repeated next to the tables
 *   DP30: the caveat match is case-sensitive                    DP31: the sensitivity lists holm.family, not post_gate.family
 */

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The checked data for `DriversDisplay`, built by the same validator the page uses, with some top-level fields replaced. */
function checked(patch: Record<string, unknown> = {}): DriversData {
  const r = parseDrivers({ ...DRIVERS_DATA_FIXTURE, ...patch })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

/**
 * The checked fixture with some top-level fields replaced AFTER the validator: for display tests whose data the parser's
 * cross-field rules would refuse (a verdict that contradicts its rate, a primary without an interval end). The page must
 * still show such data as given.
 */
function unchecked(patch: Partial<DriversData>): DriversData {
  return { ...checked(), ...patch }
}

const SIZE_FAILED = (pct: string, reps: string) => `size check failed: G1 size ${pct} over ${reps} replications, liberal; a rejection would not be trusted`
const TABLE_CAVEAT = 'Fixture caveat X: every exploratory p and q here comes from an invented statistic.'

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

const headersOf = (table: HTMLElement): string[] => within(table).getAllByRole('columnheader').map((h) => h.textContent ?? '')

/** Column positions in a model's terms table. */
const COL = { term: 0, hypothesis: 1, role: 2, statistic: 3, coef: 4, se: 5, ci: 6, t: 7, df: 8, p: 9, q: 10, holm: 11, note: 12 }

/** The fixture's models with the fields of `patches[j]` replaced in term j of model 1 (the first). */
function modelsWith(...patches: (Record<string, unknown> | undefined)[]): unknown[] {
  const models = structuredClone(DRIVERS_DATA_FIXTURE.models) as unknown as { terms: Record<string, unknown>[] }[]
  patches.forEach((patch, j) => {
    models[0].terms[j] = { ...models[0].terms[j], ...patch }
  })
  return models
}

const region = (name: string): HTMLElement => screen.getByRole('region', { name })
const termsOf = (model: number): string[][] => bodyOf(screen.getByRole('table', { name: `Model ${model} terms` }))

describe('DriversPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<DriversPage fetchImpl={serving(DRIVERS_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading drivers')
    expect(screen.getByRole('heading', { level: 2, name: 'Drivers' })).toBeInTheDocument()
    await screen.findByRole('table', { name: 'G1 calibration' })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/drivers.json by default, and the given url when there is one', async () => {
    const f = serving(DRIVERS_FIXTURE)
    const { unmount } = render(<DriversPage fetchImpl={f} />)
    await screen.findByRole('table', { name: 'G1 calibration' })
    expect(f).toHaveBeenCalledWith('data/drivers.json', { cache: 'no-cache' })
    unmount()
    const g = serving(DRIVERS_FIXTURE)
    render(<DriversPage url="x/drivers.json" fetchImpl={g} />)
    await screen.findByRole('table', { name: 'G1 calibration' })
    expect(g).toHaveBeenCalledWith('x/drivers.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no table and no notice, when the file is missing (HTTP 404)', async () => {
    render(<DriversPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The drivers could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('complementary')).toBeNull()
  })
  it('shows an error for the previous schema version (0.4.0)', async () => {
    render(<DriversPage fetchImpl={serving({ ...DRIVERS_FIXTURE, schema_version: '0.4.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.4.0": this app only understands "0.5.0"')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('shows an error when the file is another kind (tests.json served at the drivers url)', async () => {
    render(<DriversPage fetchImpl={serving({ ...DRIVERS_FIXTURE, kind: 'tests' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "tests", expected "drivers"')
  })
  it('shows an error naming the rule when the data has the wrong shape (a withheld row that keeps its p-value)', async () => {
    const body = { ...DRIVERS_FIXTURE, data: edited(DRIVERS_DATA_FIXTURE, ['models', 0, 'terms', 2, 'p_value'], 0.1) }
    render(<DriversPage fetchImpl={serving(body)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/drivers.json: models[0].terms[2].g1_size is given only for a withheld p-value, but p_value is number 0.1')
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<DriversPage url="old/drivers.json" fetchImpl={oldFetch} />)
    rerender(<DriversPage url="new/drivers.json" fetchImpl={serving(DRIVERS_FIXTURE)} />)
    await screen.findByRole('table', { name: 'G1 calibration' })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table', { name: 'G1 calibration' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('DriversDisplay: the provisional-labels notice', () => {
  it('opens with the provisional notice built from the lookups, and every caveat once in it', () => {
    render(<DriversDisplay drivers={checked()} />)
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('Timing labels are provisional: 7 timing look-ups are done')
    for (const c of DRIVERS_DATA_FIXTURE.caveats) expect(within(notice).getAllByText(c)).toHaveLength(1)
    expect(within(notice).getAllByRole('listitem')).toHaveLength(DRIVERS_DATA_FIXTURE.caveats.length)
    // only the caveat on the exploratory p and q is shown a second time, next to the coefficient tables
    expect(DRIVERS_DATA_FIXTURE.caveats.map((c) => screen.getAllByText(c).length)).toEqual([1, 1, 2])
  })
  it('says the labels are complete when the file says so', () => {
    render(<DriversDisplay drivers={checked({ lookups: { n_done: 9, complete: true } })} />)
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing look-ups are complete: 9 done.')
  })
  it('puts the notice before the first table', () => {
    render(<DriversDisplay drivers={checked()} />)
    const notice = screen.getByRole('complementary')
    const table = screen.getByRole('table', { name: 'G1 calibration' })
    expect(notice.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
  it('shows the sample label of the provenance', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(screen.getByText(/Sample:/)).toHaveTextContent('Sample: fixture-sample.')
  })
})

describe('DriversDisplay: gate G1', () => {
  it('states the replications and the band as percents', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(screen.getByText(/Simulated size check/)).toHaveTextContent('500 replications. Band: 25.00% to 50.00%.')
  })
  it('lists every calibrated statistic with its rejection rate in percent, its replications, the band upper edge and the verdict', () => {
    render(<DriversDisplay drivers={checked()} />)
    const table = screen.getByRole('table', { name: 'G1 calibration' })
    expect(headersOf(table)).toEqual(['Hypothesis', 'Statistic', 'Primary', 'Rejection rate', 'Replications', 'Band upper edge', 'Verdict'])
    expect(bodyOf(table)).toEqual([
      ['H5', 'twoway_date_t', 'yes', '62.50%', '500', '50.00%', 'fail'],
      ['H5', 'cluster_date_t', 'no', '75.00%', '500', '50.00%', 'fail'],
      ['H5', 'twoway_date_t:mean_adj', 'no', '68.75%', '500', '50.00%', 'fail'],
      ['H6', 'twoway_date_t', 'yes', '37.50%', '500', '50.00%', 'pass'],
      ['H7', 'twoway_date_wald', 'yes', '56.25%', '500', '50.00%', 'fail'],
    ])
  })
  it('shows the replications of each row with a thousands separator', () => {
    const calibrated = [{ hypothesis: 'H5', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.0955, reps: 2000, pass: false }] as DriversData['g1']['calibrated']
    render(<DriversDisplay drivers={unchecked({ g1: { ...checked().g1, reps: 10000, calibrated } })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'G1 calibration' }))).toEqual([['H5', 'twoway_date_t', 'yes', '9.55%', '2,000', '50.00%', 'fail']])
    expect(screen.getByText(/Simulated size check/)).toHaveTextContent('10,000 replications')
  })
  it('shows the verdict as written, not recomputed: a rate above the band that the file marks as pass stays pass, and one below it marked fail stays fail', () => {
    const calibrated = [
      { hypothesis: 'H5', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.9, reps: 500, pass: true },
      { hypothesis: 'H6', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.01, reps: 500, pass: false },
    ] as DriversData['g1']['calibrated']
    // the parser refuses such verdicts (rule D4), so this is data it never passes on: the page still must not recompute
    render(<DriversDisplay drivers={unchecked({ g1: { ...checked().g1, calibrated } })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'G1 calibration' })).map((r) => r[6])).toEqual(['pass', 'fail'])
  })
  it('says which hypotheses failed gate G1 and that they stay in the declared family with their p-values, in a note (fix R1)', () => {
    render(<DriversDisplay drivers={checked()} />)
    const note = screen.getByRole('note', { name: 'Gate G1 verdict' })
    expect(note).toHaveTextContent(
      'Gate G1 failed for H5, H7: under the calibrated null the primary statistic rejects more often than the upper edge of the band (50.00%) allows. ' +
        'H5, H7 stay in the declared Holm family with their p-values and Holm p: the statistic is liberal on this design, so a rejection by it would not be trusted.',
    )
    expect(note).not.toHaveTextContent('left')
  })
  it('says a single failed hypothesis stays in the family in the singular, and names one that left the family only when there is one', () => {
    const calibrated = checked().g1.calibrated.filter((c) => c.hypothesis !== 'H7')
    render(<DriversDisplay drivers={unchecked({ g1: { ...checked().g1, calibrated }, holm: { ...checked().holm, left_family: ['H3'] } })} />)
    expect(screen.getByRole('note', { name: 'Gate G1 verdict' })).toHaveTextContent(
      'H5 stays in the declared Holm family with its p-value and Holm p: the statistic is liberal on this design, so a rejection by it would not be trusted. H3 left the family: not Holm-adjusted.',
    )
  })
  it('does not say a failed hypothesis stays in the family when it is not in it', () => {
    render(<DriversDisplay drivers={unchecked({ holm: { ...checked().holm, family: ['H1', 'H2', 'H6'] } })} />)
    const note = screen.getByRole('note', { name: 'Gate G1 verdict' })
    expect(note).toHaveTextContent(/^Gate G1 failed for H5, H7:/)
    expect(note).not.toHaveTextContent('stay')
  })
  it('does not name a hypothesis whose primary statistic passed, nor one that failed only with a robustness statistic', () => {
    const calibrated = [
      { hypothesis: 'H5', statistic: 'cluster_date_t', primary: false, rejection_rate: 0.9, reps: 500, pass: false },
      { hypothesis: 'H6', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.1, reps: 500, pass: true },
      { hypothesis: 'H7', statistic: 'twoway_date_wald', primary: true, rejection_rate: 0.9, reps: 500, pass: false },
    ] as DriversData['g1']['calibrated']
    render(<DriversDisplay drivers={unchecked({ g1: { ...checked().g1, calibrated } })} />)
    expect(screen.getByRole('note', { name: 'Gate G1 verdict' })).toHaveTextContent(/^Gate G1 failed for H7:/)
  })
  it('says every primary statistic passed, and mentions no family change, when none failed and none left', () => {
    const calibrated = checked().g1.calibrated.map((c) => ({ ...c, pass: true }))
    render(<DriversDisplay drivers={unchecked({ g1: { ...checked().g1, calibrated } })} />)
    const note = screen.getByRole('note', { name: 'Gate G1 verdict' })
    expect(note).toHaveTextContent('Every primary statistic passed gate G1.')
    expect(note).not.toHaveTextContent('left')
    expect(note).not.toHaveTextContent('stay')
    expect(note).not.toHaveTextContent('failed')
  })
  it('lists the rejection rates under the other designs in a collapsed section', () => {
    render(<DriversDisplay drivers={checked()} />)
    const summary = screen.getByText(/Rejection rates under the other simulation designs/)
    expect(summary).toHaveTextContent('(2)')
    expect(summary.closest('details')).not.toHaveAttribute('open')
    const table = screen.getByRole('table', { name: 'G1 designs', hidden: true })
    expect(headersOf(table)).toEqual(['Design', 'Hypothesis', 'Statistic', 'Primary', 'Rejection rate'])
    expect(bodyOf(table)).toEqual([
      ['FXD0', 'H5', 'twoway_date_t', 'yes', '12.50%'],
      ['FXD1', 'H6', 'cluster_date_t', 'no', '50.00%'],
    ])
  })
  it('lists the H7 calibration in a collapsed section, with a dash for a missing value', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(screen.getByText('H7 simulation calibration').closest('details')).not.toHaveAttribute('open')
    expect(pairsOf(screen.getByRole('table', { name: 'H7 calibration parameters', hidden: true }))).toEqual([
      ['fix_nu', '6.5'],
      ['fix_rho', '0.25'],
      ['fix_missing', '—'],
    ])
  })
})

describe('DriversDisplay: the Holm statement and the sensitivity', () => {
  const items = () => within(screen.getByRole('list', { name: 'Holm statement' })).getAllByRole('listitem').map((li) => li.textContent)
  const sensitivity = () => screen.getByRole('table', { name: 'Holm sensitivity' })

  it('says Holm runs over the declared family, and lists it (fix R1)', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(items()).toEqual(['Holm runs over the declared family: H1, H2, H5, H6, H7'])
    expect(screen.getByText(/^The binding Holm p-values are the ones of the declared family/)).toBeInTheDocument()
  })
  it('lists the hypotheses that left the family only when there are some', () => {
    render(<DriversDisplay drivers={checked({ holm: { ...DRIVERS_DATA_FIXTURE.holm, left_family: ['H3'] } })} />)
    expect(items()).toEqual(['Holm runs over the declared family: H1, H2, H5, H6, H7', 'Left the family: H3'])
  })
  it('captions the post-gate table as a descriptive sensitivity, naming the hypotheses it leaves out', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(within(sensitivity()).getByText(/^Descriptive sensitivity/)).toHaveTextContent(
      'Descriptive sensitivity, not binding: the Holm p over the family without the hypotheses whose G1 size check failed (H5, H7).',
    )
    expect(headersOf(sensitivity())).toEqual(['Row', 'Holm p without H5, H7'])
  })
  it('lists the post-gate Holm p of each hypothesis of its family as given, then the season cut', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(bodyOf(sensitivity())).toEqual([
      ['H1', '0.03125'],
      ['H2', '0.09375'],
      ['H6', '0.875'],
      ['H2 season cut', '0.15625'],
    ])
  })
  it('draws no season-cut row when the file has none, and says none was left out when nothing failed', () => {
    const family = DRIVERS_DATA_FIXTURE.holm.family
    const holm = { ...DRIVERS_DATA_FIXTURE.holm, post_gate: { family, p_holm: Object.fromEntries(family.map((h) => [h, 1])), season_cut: {} } }
    render(<DriversDisplay drivers={unchecked({ holm })} />)
    expect(bodyOf(sensitivity()).map((r) => r[0])).toEqual(['H1', 'H2', 'H5', 'H6', 'H7'])
    expect(within(sensitivity()).getByText(/^Descriptive sensitivity/)).toHaveTextContent('(none)')
  })
  it('shows a tiny sensitivity p-value in the file\'s own notation', () => {
    const postGate = DRIVERS_DATA_FIXTURE.holm.post_gate
    render(<DriversDisplay drivers={checked({ holm: { ...DRIVERS_DATA_FIXTURE.holm, post_gate: { ...postGate, p_holm: { ...postGate.p_holm, H1: 4.06e-22 } } } })} />)
    expect(bodyOf(sensitivity())[0]).toEqual(['H1', '4.06e-22'])
  })
  it('keeps the sensitivity apart from the binding Holm p of the model rows', () => {
    render(<DriversDisplay drivers={checked()} />)
    // the binding p_holm of the primaries (H5 0.0625, H6 1, H7 0.5), never a post-gate value; a dash for the robustness rows
    expect(termsOf(1).map((r) => r[COL.holm])).toEqual(['0.0625', '1', '—', '—', '0.5'])
  })
})

describe('DriversDisplay: power', () => {
  it('shows the detectable shift at 80% power, or "not reached on the grid" when it is null, with the power at each shift', () => {
    render(<DriversDisplay drivers={checked()} />)
    const table = screen.getByRole('table', { name: 'G1 power' })
    expect(headersOf(table)).toEqual(['Hypothesis', 'Shift of', 'Smallest shift with 80% power', 'Power at each shift'])
    expect(bodyOf(table)).toEqual([
      ['H5', 'beta', 'not reached on the grid', '0.01: 0.25 · 0.02: 0.75'],
      ['H6', 'beta', '0.04', '0.01: 0.25 · 0.02: 0.5 · 0.04: 1'],
      ['H7', 'b', '0.5', '0.5: 0.875 · 1: 0.125'],
    ])
  })
  it('shows a detectable shift of 0 as 0 (it is a number, not missing)', () => {
    const power = [{ hypothesis: 'H5', kind: 'beta', shifts: [0], power: [0.9], detectable_80: 0 }]
    render(<DriversDisplay drivers={checked({ g1: { ...DRIVERS_DATA_FIXTURE.g1, power } })} />)
    expect(bodyOf(screen.getByRole('table', { name: 'G1 power' }))[0][2]).toBe('0')
  })
})

describe('DriversDisplay: the models', () => {
  it('has a section and a terms table per model, in file order, and marks only the first as the primary model', () => {
    render(<DriversDisplay drivers={checked()} />)
    const headings = within(screen.getByRole('heading', { level: 2, name: 'Models' }).parentElement as HTMLElement)
      .getAllByRole('heading', { level: 3 })
      .filter((h) => /^Model \d/.test(h.textContent ?? ''))
      .map((h) => h.textContent)
    expect(headings).toEqual(['Model 1: Fixture model Aprimary model', 'Model 2: Fixture model B (twin)', 'Model 3: Fixture model C (Wald only)'])
    expect(within(region('Model 1: Fixture model A')).getByText('primary model')).toBeInTheDocument()
    expect(screen.getAllByText('primary model')).toHaveLength(1)
    for (const n of [1, 2, 3]) expect(screen.getByRole('table', { name: `Model ${n} terms` })).toBeInTheDocument()
  })
  it('tells models that share an id apart (the twin carries the id of model A)', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(DRIVERS_DATA_FIXTURE.models[0].model_id).toBe(DRIVERS_DATA_FIXTURE.models[1].model_id)
    expect(termsOf(1)).toHaveLength(5)
    expect(termsOf(2)).toHaveLength(2)
  })
  it('describes each model: dependent variable, adjustment, sample, fixed effects, n, clusters and R squared', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(within(region('Model 1: Fixture model A')).getByText(/FIX_DEP/)).toHaveTextContent(
      'FIX_DEP (log) · market-adjusted · daily sample · fixed effects: fix_fe1, fix_fe2 · n = 40 · date clusters 20 · firm clusters — · R² 0.5',
    )
    expect(within(region('Model 2: Fixture model B (twin)')).getByText(/FIX_DEP/)).toHaveTextContent(
      'FIX_DEP (log) · mean-adjusted · coarse sample · fixed effects: none · n = 12 · date clusters — · firm clusters 6 · R² —',
    )
  })
  it('says the file has no models when it has none', () => {
    render(<DriversDisplay drivers={checked({ models: [] })} />)
    expect(screen.getByText('The file has no models.')).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
  })
})

describe('DriversDisplay: the caveats next to the coefficient tables (fix R7)', () => {
  it('lists the file\'s caveats on the exploratory p and q under the Models heading, before the first model', () => {
    render(<DriversDisplay drivers={checked()} />)
    const list = screen.getByRole('list', { name: 'Caveats on the coefficient tables' })
    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([TABLE_CAVEAT])
    const heading = screen.getByRole('heading', { level: 2, name: 'Models' })
    expect(heading.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(list.compareDocumentPosition(screen.getByRole('table', { name: 'Model 1 terms' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
  it('matches "exploratory" in any case, and draws no list when no caveat is about the exploratory rows', () => {
    const { unmount } = render(<DriversDisplay drivers={checked({ caveats: ['Fixture caveat: EXPLORATORY p-values, invented.'] })} />)
    expect(screen.getByRole('list', { name: 'Caveats on the coefficient tables' })).toHaveTextContent('Fixture caveat: EXPLORATORY p-values, invented.')
    unmount()
    render(<DriversDisplay drivers={checked({ caveats: ['Fixture caveat D: invented.'] })} />)
    expect(screen.queryByRole('list', { name: 'Caveats on the coefficient tables' })).toBeNull()
  })
})

describe('DriversDisplay: the terms table', () => {
  it('has the columns asked for, in order', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(headersOf(screen.getByRole('table', { name: 'Model 1 terms' }))).toEqual([
      'Term', 'Hypothesis', 'Role', 'Statistic', 'Coef', 'SE', 'CI', 't (F for a Wald test)', 'df', 'p', 'q (BH)', 'Holm p', 'Note',
    ])
  })
  it('shows every number of a complete row exactly as the file has it, with the term id and the covariance under the label and the statistic', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(termsOf(1)[1]).toEqual([
      'Fixture term Bfix_term_b',
      'H6',
      'primary',
      'twoway_date_tfixture two-way, t',
      '-0.125',
      '0.125',
      '[-0.375, 0.125]',
      '-1',
      '7',
      '0.5',
      '—',
      '1',
      '—',
    ])
  })
  it('lists every row of the model, the one-way and Wald rows too, in file order', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(termsOf(1).map((r) => r[COL.statistic].split('fixture')[0])).toEqual(['twoway_date_t', 'twoway_date_t', 'cluster_date_t', 'twoway_date_t', 'twoway_date_wald'])
    expect(termsOf(1).map((r) => r[COL.role])).toEqual(['primary', 'primary', 'robustness', 'robustness', 'primary'])
  })
  it('shows a withheld p-value as "withheld" with the G1 size in percent and its replications, keeps the estimate, and shows no interval, q or Holm p', () => {
    render(<DriversDisplay drivers={checked()} />)
    const [, , oneWay, twoWay] = termsOf(1)
    // 0.75 = 75.00%, 500 replications; 0.09375 = 9.38%, 10000 printed as 10,000
    expect(oneWay.slice(COL.coef)).toEqual(['0.25', '0.03125', '—', '8', '19', 'withheld (G1 size 75.00% over 500 replications)', '—', '—', 'Fixture note: p-value and interval withheld.'])
    expect(twoWay.slice(COL.coef)).toEqual(['0.1875', '0.0625', '—', '3', '7', 'withheld (G1 size 9.38% over 10,000 replications)', '—', '—', 'Fixture note: withheld, coefficient kept.'])
  })
  it('never shows a p-value for a withheld row, and shows a row that is not withheld with its p-value', () => {
    render(<DriversDisplay drivers={checked()} />)
    const ps = termsOf(1).map((r) => r[COL.p])
    expect(ps.filter((p) => p.startsWith('withheld'))).toHaveLength(2)
    expect(ps).toEqual([`0.0125${SIZE_FAILED('62.50%', '500')}`, '0.5', expect.stringContaining('withheld'), expect.stringContaining('withheld'), `0.28125${SIZE_FAILED('56.25%', '500')}`])
  })
  it('shows a primary whose size check failed with its p-value, the G1 size and replications under it, its interval, Holm p and note (fix R1)', () => {
    render(<DriversDisplay drivers={checked()} />)
    const [h5, , , , h7] = termsOf(1)
    expect(h5.slice(COL.ci)).toEqual(['[0.125, 0.375]', '4', '7', `0.0125${SIZE_FAILED('62.50%', '500')}`, '—', '0.0625', 'Fixture note: size check failed; the p-value is kept.'])
    expect(h7.slice(COL.p)).toEqual([`0.28125${SIZE_FAILED('56.25%', '500')}`, '—', '0.5', 'Fixture note: the joint test failed its size check.'])
  })
  it('shows the failed size check of a primary measured on another count with that count', () => {
    const models = modelsWith({ g1_size: 0.0955, g1_reps: 2000 })
    render(<DriversDisplay drivers={unchecked({ models: models as DriverModel[] })} />)
    expect(termsOf(1)[0][COL.p]).toBe(`0.0125${SIZE_FAILED('9.55%', '2,000')}`)
  })
  it('shows a Wald row with a dash for coef, se and interval, its F statistic, and both degrees of freedom', () => {
    render(<DriversDisplay drivers={checked()} />)
    const wald = termsOf(1)[4]
    expect(wald[COL.coef]).toBe('—')
    expect(wald[COL.se]).toBe('—')
    expect(wald[COL.ci]).toBe('—')
    expect(wald[COL.t]).toBe('1.5')
    expect(wald[COL.df]).toBe('2, 7') // numerator, denominator
    expect(wald[COL.statistic]).toBe('twoway_date_waldfixture two-way, Wald F')
  })
  it('shows a row without a hypothesis with a dash, a null note as a dash, and the row of model 2', () => {
    render(<DriversDisplay drivers={checked()} />)
    expect(termsOf(2)[0]).toEqual(['Fixture term Cfix_term_c', '—', 'exploratory', 'twoway_date_tfixture two-way, t', '0.5', '0.25', '[-0.125, 1.125]', '2', '5', '0.125', '0.25', '—', '—'])
  })
  it('shows an interval with only one end as that end and a dash, not as no interval at all', () => {
    // a primary keeps both ends (rule D1); the page must still not hide an interval with one end
    const models = modelsWith({ ci_lo: null }, { ci_hi: null })
    render(<DriversDisplay drivers={unchecked({ models: models as DriverModel[] })} />)
    expect(termsOf(1).slice(0, 2).map((r) => r[COL.ci])).toEqual(['[—, 0.375]', '[-0.375, —]'])
  })
  it('shows tiny numbers in the file\'s own notation, not rounded', () => {
    const models = modelsWith(undefined, { p_value: 6.35e-23, q_bh: 4.445e-22, p_holm: 1.5e-9, coef: -0.1991 })
    render(<DriversDisplay drivers={checked({ models })} />)
    const first = termsOf(1)[1]
    expect([first[COL.coef], first[COL.p], first[COL.q], first[COL.holm]]).toEqual(['-0.1991', '6.35e-23', '4.445e-22', '1.5e-9'])
  })
  it('does no arithmetic: a t and p that do not match coef / se are shown as given', () => {
    // coef -0.125 / se 0.125 would be -1; the file says 7.5 and a p of 0.9, and the page must not "fix" them
    const models = modelsWith(undefined, { t: 7.5, p_value: 0.9 })
    render(<DriversDisplay drivers={checked({ models })} />)
    const first = termsOf(1)[1]
    expect([first[COL.t], first[COL.p]]).toEqual(['7.5', '0.9'])
  })
})

describe('DriversDisplay: the coefficient plot of each model', () => {
  const plot = (n: number, label: string): HTMLElement => screen.getByRole('img', { name: `Coefficients of model ${n}, ${label}, with intervals` })
  const circles = (svg: HTMLElement) => Array.from(svg.querySelectorAll('circle.forest-point'))

  it('draws one point per two-way row with a coefficient, in file order, and leaves out the one-way and the Wald rows', () => {
    render(<DriversDisplay drivers={checked()} />)
    const svg = plot(1, 'Fixture model A')
    expect(Array.from(svg.querySelectorAll('.row-label')).map((t) => t.textContent)).toEqual(['Fixture term A', 'Fixture term B', 'Fixture term B'])
    expect(circles(svg)).toHaveLength(3)
  })
  it('puts each point, interval and the zero line at its hand-worked pixel', () => {
    // Axis -0.4 .. 0.4 over x 230..616 and rows centred at y 37, 63, 89 (see chartLayout.test.ts, same three rows)
    render(<DriversDisplay drivers={checked()} />)
    const svg = plot(1, 'Fixture model A')
    const xs = circles(svg).map((c) => Number(c.getAttribute('cx')))
    const ys = circles(svg).map((c) => Number(c.getAttribute('cy')))
    expect(xs[0]).toBeCloseTo(543.625, 6)
    expect(xs[1]).toBeCloseTo(362.6875, 6)
    expect(xs[2]).toBeCloseTo(513.46875, 6)
    expect(ys).toEqual([37, 63, 89])
    const lines = Array.from(svg.querySelectorAll('line.forest-ci'))
    expect(lines.map((l) => [Number(l.getAttribute('x1')), Number(l.getAttribute('x2')), Number(l.getAttribute('y1'))])).toEqual([
      [expect.closeTo(483.3125, 6), expect.closeTo(603.9375, 6), 37],
      [expect.closeTo(242.0625, 6), expect.closeTo(483.3125, 6), 63],
    ])
    const zero = svg.querySelector('line.day0-line') as Element
    expect(Number(zero.getAttribute('x1'))).toBeCloseTo(423, 6)
    expect(zero.getAttribute('x1')).toBe(zero.getAttribute('x2'))
  })
  it('draws the interval of a row that has one, and for a withheld row only a hollow point with no interval', () => {
    render(<DriversDisplay drivers={checked()} />)
    const svg = plot(1, 'Fixture model A')
    expect(svg.querySelectorAll('line.forest-ci')).toHaveLength(2) // the third point is a withheld row: no interval
    expect(circles(svg).map((c) => c.classList.contains('withheld'))).toEqual([false, false, true])
  })
  it('titles each point with its coefficient and interval, or says the interval is withheld', () => {
    render(<DriversDisplay drivers={checked()} />)
    const titles = circles(plot(1, 'Fixture model A')).map((c) => c.querySelector('title')?.textContent)
    expect(titles).toEqual([
      'Fixture term A: coef 0.25, interval [0.125, 0.375]',
      'Fixture term B: coef -0.125, interval [-0.375, 0.125]',
      'Fixture term B: coef 0.1875, interval withheld',
    ])
  })
  it('labels the axis ticks with round numbers, one gridline each', () => {
    render(<DriversDisplay drivers={checked()} />)
    const svg = plot(1, 'Fixture model A')
    expect(Array.from(svg.querySelectorAll('text.tick')).map((t) => t.textContent).slice(0, 5)).toEqual(['-0.4', '-0.2', '0', '0.2', '0.4'])
    expect(svg.querySelectorAll('line.grid-line')).toHaveLength(5)
  })
  it('draws the second model on its own scale (its single row spans -0.125 to 1.125)', () => {
    render(<DriversDisplay drivers={checked()} />)
    const svg = plot(2, 'Fixture model B (twin)')
    expect(circles(svg)).toHaveLength(2) // fix_term_c, and the withheld twin row at 0.375 (inside that span)
    // span 1.25 over at most 6 steps: 1.25 / 6 = 0.208, so the step is 0.25 and the ticks run -0.25, 0, 0.25 .. 1.25
    expect(Array.from(svg.querySelectorAll('text.tick')).map((t) => t.textContent).slice(0, 7)).toEqual(['-0.25', '0', '0.25', '0.5', '0.75', '1', '1.25'])
  })
  it('says there is nothing to plot, and draws no plot, for a model with only a Wald row', () => {
    render(<DriversDisplay drivers={checked()} />)
    const section = region('Model 3: Fixture model C (Wald only)')
    expect(within(section).getByText('The model has no two-way coefficient to plot.')).toBeInTheDocument()
    expect(within(section).queryByRole('img')).toBeNull()
    expect(within(section).getByRole('table', { name: 'Model 3 terms' })).toBeInTheDocument() // the table still has the row
  })
  it('cuts a long term label in the plot, keeps it whole in the table, and gives the plot a name that says which model it is', () => {
    const label = 'A very long term label that cannot fit the margin of the plot'
    const models = modelsWith({ label })
    render(<DriversDisplay drivers={checked({ models })} />)
    const first = plot(1, 'Fixture model A').querySelector('.row-label') as Element
    expect(first.textContent).toHaveLength(34)
    expect(first.textContent?.endsWith('…')).toBe(true)
    expect(termsOf(1)[0][COL.term]).toContain(label)
  })
})
