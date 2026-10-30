import { describe, it, expect } from 'vitest'
import { IMPLIED_REALISED_KIND, IMPLIED_REALISED_URL, loadImpliedRealised, parseImpliedRealised } from './impliedRealised'
import { IMPLIED_REALISED_DATA_FIXTURE, IMPLIED_REALISED_FIXTURE } from '../test/impliedRealisedFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(IMPLIED_REALISED_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseImpliedRealised(input))
/** The path of field `key` of the regression of the fixture's summary. */
const reg = (key: string): Path => ['summary', 'regression', key]

const KEYS = ['points', 'summary', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const POINT_KEYS = [
  'event_id', 'ticker', 'sector', 'day0', 'timing_used', 'event_var', 'implied_var_total', 'implied_move', 'implied_abs_move_total',
  'realized_ret_0', 'abs_realized', 'implied_move_status', 'surprise_scaled',
]
const POINT_KEY_LIST = POINT_KEYS.join(', ')
const SUMMARY_KEYS = [
  'n', 'n_evar_nonpositive', 'n_with_implied_abs_move', 'share_exceed', 'share_exceed_se', 'share_exceed_p', 'share_exceed_benchmark',
  'mean_log_ratio', 'median_ratio', 'regression',
]
const SUMMARY_KEY_LIST = SUMMARY_KEYS.join(', ')
const REGRESSION_KEYS = [
  'n', 'a', 'a_se', 'b', 'b_se', 'b_ci', 'wald_f', 'wald_df_num', 'wald_df', 'wald_p', 'role', 'p_holm', 'n_clusters_date', 'n_clusters_firm',
  'wald_p_one_way', 'g1_rate', 'g1_pass', 'g1_bar', 'g1_rate_one_way', 'g1_pass_one_way',
]
const REGRESSION_KEY_LIST = REGRESSION_KEYS.join(', ')

/*
 * Mutations this file must catch: 15 of 15 tried were killed at milestone 4. Each was applied to src/lib/impliedRealised.ts, one at a time,
 * and this file then failed; the file was restored and its sha256 checked each time (script outside the repo).
 *   IR1: abs_realized may be negative
 *   IR2: day0 no longer checked as a calendar date
 *   IR3: AMC no longer a known timing
 *   IR4: b_ci order rule inverted
 *   IR5: wald_p not checked as a probability
 *   IR6: regression role not restricted to primary / exploratory
 *   IR7: p_holm may not be null
 *   IR8: g1_pass not checked as a boolean
 *   IR9: extra summary keys accepted
 *   IR10: extra regression keys accepted
 *   IR11: share_exceed (and p, benchmark) not checked as probabilities
 *   IR12: n_clusters_date no longer checked
 *   IR13: loader checks the wrong kind
 *   IR14: realized_ret_0 may be null
 *   IR15: only status "ok" is a known implied_move_status
 * Fix R1 and R4 of the milestone-4 review (15 of 15 killed; IR1 to IR15 were not re-tried after it):
 *   I1a: a primary may lack its Holm p                          I1b: an exploratory test may carry a Holm p
 *   I2a: g1_pass not checked against g1_bar                     I2b: a rate equal to g1_bar counts as a fail (< for <=)
 *   I2c: the one-way verdict not checked against g1_bar         I3a: no one-way check, yet a one-way p or rate given
 *   I3b: a one-way verdict without its rate                     I3c: a failed one-way check keeps its p-value
 *   I3d: a passed one-way check without its p-value             I4: a benchmark other than 0.425 accepted
 *   I5: a repeated event_id accepted                            Ix1: g1_bar not checked as a probability
 *   Ix2: g1_rate_one_way not checked as a probability or null   Ix3: g1_pass_one_way not checked as a boolean or null
 */

describe('parseImpliedRealised: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseImpliedRealised(IMPLIED_REALISED_DATA_FIXTURE)).toEqual({ ok: true, data: IMPLIED_REALISED_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies of the arrays and objects', () => {
    const input = structuredClone(IMPLIED_REALISED_DATA_FIXTURE)
    const r = parseImpliedRealised(input)
    expect(input).toEqual(IMPLIED_REALISED_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.points).not.toBe(input.points)
    expect(r.data.points[0]).not.toBe(input.points[0])
    expect(r.data.summary).not.toBe(input.summary)
    expect(r.data.summary.regression).not.toBe(input.summary.regression)
    expect(r.data.summary.regression.b_ci).not.toBe(input.summary.regression.b_ci)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('keeps the points in file order', () => {
    const r = parseImpliedRealised(IMPLIED_REALISED_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.points.map((p) => p.ticker)).toEqual(['FIXA', 'FIXB', 'FIXC', 'FIXD', 'FIXE'])
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseImpliedRealised(IMPLIED_REALISED_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('accepts a file with no points and no caveats', () => {
    expect(parseImpliedRealised(edited(['points'], [])).ok).toBe(true)
    expect(parseImpliedRealised(edited(['caveats'], [])).ok).toBe(true)
  })
  it('accepts every null a point may carry, an absolute move of 0, a negative return, and every timing and status', () => {
    const nulls = Object.fromEntries(['timing_used', 'event_var', 'implied_var_total', 'implied_move', 'implied_abs_move_total', 'implied_move_status', 'surprise_scaled'].map((k) => [k, null]))
    expect(parseImpliedRealised(edited(['points', 0], { ...IMPLIED_REALISED_DATA_FIXTURE.points[0], ...nulls })).ok).toBe(true)
    expect(parseImpliedRealised(edited(['points', 0], { ...IMPLIED_REALISED_DATA_FIXTURE.points[0], realized_ret_0: 0, abs_realized: 0 })).ok).toBe(true)
    for (const t of ['BMO', 'AMC']) expect(parseImpliedRealised(edited(['points', 0, 'timing_used'], t)).ok, t).toBe(true)
    for (const s of ['ok', 'nonpositive_event_variance', 'not_identified']) expect(parseImpliedRealised(edited(['points', 0, 'implied_move_status'], s)).ok, s).toBe(true)
    expect(IMPLIED_REALISED_DATA_FIXTURE.points[0].realized_ret_0).toBeLessThan(0)
  })
  it('accepts both roles, a Holm p of 0, a one-way p-value that passed its check, a one-way test never sized, and a passing gate', () => {
    const regression = IMPLIED_REALISED_DATA_FIXTURE.summary.regression
    expect([regression.role, regression.p_holm, regression.g1_pass, regression.wald_p_one_way]).toEqual(['primary', 0.5, false, null])
    expect(parseImpliedRealised(edited(['summary', 'regression'], { ...regression, role: 'exploratory', p_holm: null })).ok).toBe(true)
    expect(parseImpliedRealised(edited(reg('p_holm'), 0)).ok).toBe(true)
    expect(parseImpliedRealised(edited(['summary', 'regression'], { ...regression, wald_p_one_way: 0, g1_rate_one_way: 0.25, g1_pass_one_way: true })).ok).toBe(true)
    expect(parseImpliedRealised(edited(['summary', 'regression'], { ...regression, wald_p_one_way: null, g1_rate_one_way: null, g1_pass_one_way: null })).ok).toBe(true)
    expect(parseImpliedRealised(edited(['summary', 'regression'], { ...regression, g1_rate: 0.25, g1_pass: true })).ok).toBe(true)
    expect(parseImpliedRealised(edited(reg('b_ci'), [0.5, 0.5])).ok).toBe(true)
  })
})

describe('parseImpliedRealised: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'points', 5, true]) expect(errorOf(x), String(x)).toContain('implied_vs_realised data must be a JSON object')
    expect(errorOf(null)).toBe('implied_vs_realised data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`implied_vs_realised data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it, and reports missing and extra keys together', () => {
    expect(errorOf(edited(['rows'], []))).toBe(`implied_vs_realised data has unexpected key(s): rows (expected exactly: ${KEY_LIST})`)
    const input = edited(['caveats'], undefined) as Record<string, unknown>
    input.note = 'x'
    expect(errorOf(input)).toContain('missing key(s): caveats; unexpected key(s): note')
  })
  it.each(POINT_KEYS)('requires the point key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(['points', 1, key], undefined))).toBe(`points[1] has missing key(s): ${key} (expected exactly: ${POINT_KEY_LIST})`)
  })
  it('rejects an extra point key', () => {
    expect(errorOf(edited(['points', 3, 'spot'], 1))).toBe(`points[3] has unexpected key(s): spot (expected exactly: ${POINT_KEY_LIST})`)
  })
  it.each(SUMMARY_KEYS)('requires the summary key %s', (key) => {
    expect(errorOf(edited(['summary', key], undefined))).toBe(`summary has missing key(s): ${key} (expected exactly: ${SUMMARY_KEY_LIST})`)
  })
  it('rejects an extra summary key', () => {
    expect(errorOf(edited(['summary', 'share_below'], 0.1))).toBe(`summary has unexpected key(s): share_below (expected exactly: ${SUMMARY_KEY_LIST})`)
  })
  it.each(REGRESSION_KEYS)('requires the regression key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(reg(key), undefined))).toBe(`summary.regression has missing key(s): ${key} (expected exactly: ${REGRESSION_KEY_LIST})`)
  })
  it('rejects an extra regression key', () => {
    expect(errorOf(edited(reg('r2'), 0.1))).toBe(`summary.regression has unexpected key(s): r2 (expected exactly: ${REGRESSION_KEY_LIST})`)
  })
  it('names the kind and the url the Python exporter writes', () => {
    expect(IMPLIED_REALISED_KIND).toBe('implied_vs_realised')
    expect(IMPLIED_REALISED_URL).toBe('data/implied_vs_realised.json')
  })
})

describe('parseImpliedRealised: points', () => {
  it('rejects points that are not an array, and a point that is not an object', () => {
    expect(errorOf(edited(['points'], {}))).toBe('points must be an array, got an object')
    expect(errorOf(edited(['points', 0], 'event'))).toBe('points[0] must be an object, got "event"')
    expect(errorOf(edited(['points', 4], null))).toBe('points[4] must be an object, got null')
  })
  it.each<[string, unknown, string]>([
    ['event_id', '', 'points[2].event_id must be a non-empty string, got ""'],
    ['ticker', null, 'points[2].ticker must be a non-empty string, got null'],
    ['sector', ' ', 'points[2].sector must be a non-empty string, got " "'],
    ['day0', '2031-02-30', 'points[2].day0 must be a calendar date "YYYY-MM-DD", got "2031-02-30"'],
    ['day0', '2031-2-3', 'points[2].day0 must be a calendar date "YYYY-MM-DD", got "2031-2-3"'],
    ['day0', 20310203, 'points[2].day0 must be a calendar date "YYYY-MM-DD", got number 20310203'],
    ['day0', null, 'points[2].day0 must be a calendar date "YYYY-MM-DD", got null'],
    ['timing_used', 'PM', 'points[2].timing_used must be null, "BMO" or "AMC", got "PM"'],
    ['timing_used', 'bmo', 'points[2].timing_used must be null, "BMO" or "AMC", got "bmo"'],
    ['event_var', '0.1', 'points[2].event_var must be a finite number or null, got "0.1"'],
    ['event_var', NaN, 'points[2].event_var must be a finite number or null, got number NaN'],
    ['implied_var_total', Infinity, 'points[2].implied_var_total must be a finite number or null, got number Infinity'],
    ['implied_move', true, 'points[2].implied_move must be a finite number or null, got boolean true'],
    ['implied_abs_move_total', 'x', 'points[2].implied_abs_move_total must be a finite number or null, got "x"'],
    ['realized_ret_0', null, 'points[2].realized_ret_0 must be a finite number, got null'],
    ['realized_ret_0', '0.1', 'points[2].realized_ret_0 must be a finite number, got "0.1"'],
    ['realized_ret_0', NaN, 'points[2].realized_ret_0 must be a finite number, got number NaN'],
    ['abs_realized', -0.01, 'points[2].abs_realized must be a finite number of at least 0, got number -0.01'],
    ['abs_realized', null, 'points[2].abs_realized must be a finite number of at least 0, got null'],
    ['abs_realized', '0.1', 'points[2].abs_realized must be a finite number of at least 0, got "0.1"'],
    ['abs_realized', Infinity, 'points[2].abs_realized must be a finite number of at least 0, got number Infinity'],
    ['implied_move_status', 'bad', 'points[2].implied_move_status must be null, "ok", "nonpositive_event_variance" or "not_identified", got "bad"'],
    ['implied_move_status', 0, 'points[2].implied_move_status must be null, "ok", "nonpositive_event_variance" or "not_identified", got number 0'],
    ['surprise_scaled', 'x', 'points[2].surprise_scaled must be a finite number or null, got "x"'],
  ])('rejects %s = %j', (key, value, message) => {
    expect(errorOf(edited(['points', 2, key], value))).toBe(message)
  })
  it('accepts a real leap day and refuses a leap day in a year that has none', () => {
    expect(parseImpliedRealised(edited(['points', 2, 'day0'], '2032-02-29')).ok).toBe(true)
    expect(errorOf(edited(['points', 2, 'day0'], '2031-02-29'))).toContain('points[2].day0 must be a calendar date')
  })
})

describe('parseImpliedRealised: summary', () => {
  it.each<[string, Path, unknown, string]>([
    ['summary not an object', ['summary'], [], 'summary must be an object, got an array'],
    ['summary null', ['summary'], null, 'summary must be an object, got null'],
    ['n negative', ['summary', 'n'], -1, 'summary.n must be a non-negative integer, got number -1'],
    ['n fractional', ['summary', 'n'], 1.5, 'summary.n must be a non-negative integer, got number 1.5'],
    ['n_evar_nonpositive negative', ['summary', 'n_evar_nonpositive'], -1, 'summary.n_evar_nonpositive must be a non-negative integer, got number -1'],
    ['n_with_implied_abs_move a string', ['summary', 'n_with_implied_abs_move'], '4', 'summary.n_with_implied_abs_move must be a non-negative integer, got "4"'],
    ['share_exceed above 1', ['summary', 'share_exceed'], 1.5, 'summary.share_exceed must be a number from 0 to 1, got number 1.5'],
    ['share_exceed negative', ['summary', 'share_exceed'], -0.1, 'summary.share_exceed must be a number from 0 to 1, got number -0.1'],
    ['share_exceed null', ['summary', 'share_exceed'], null, 'summary.share_exceed must be a number from 0 to 1, got null'],
    ['share_exceed_se NaN', ['summary', 'share_exceed_se'], NaN, 'summary.share_exceed_se must be a finite number, got number NaN'],
    ['share_exceed_se a string', ['summary', 'share_exceed_se'], '0.1', 'summary.share_exceed_se must be a finite number, got "0.1"'],
    ['share_exceed_p above 1', ['summary', 'share_exceed_p'], 2, 'summary.share_exceed_p must be a number from 0 to 1, got number 2'],
    ['share_exceed_benchmark above 1', ['summary', 'share_exceed_benchmark'], 1.2, 'summary.share_exceed_benchmark must be a number from 0 to 1, got number 1.2'],
    ['mean_log_ratio a string', ['summary', 'mean_log_ratio'], '-0.2', 'summary.mean_log_ratio must be a finite number, got "-0.2"'],
    ['median_ratio null', ['summary', 'median_ratio'], null, 'summary.median_ratio must be a finite number, got null'],
    ['median_ratio Infinity', ['summary', 'median_ratio'], Infinity, 'summary.median_ratio must be a finite number, got number Infinity'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('accepts a negative mean log ratio, a share of 0 and a share of 1', () => {
    expect(IMPLIED_REALISED_DATA_FIXTURE.summary.mean_log_ratio).toBeLessThan(0)
    expect(parseImpliedRealised(edited(['summary', 'share_exceed'], 0)).ok).toBe(true)
    expect(parseImpliedRealised(edited(['summary', 'share_exceed'], 1)).ok).toBe(true)
  })
})

describe('parseImpliedRealised: the regression', () => {
  it.each<[string, Path, unknown, string]>([
    ['regression not an object', ['summary', 'regression'], null, 'summary.regression must be an object, got null'],
    ['n negative', reg('n'), -1, 'summary.regression.n must be a non-negative integer, got number -1'],
    ['n fractional', reg('n'), 2.5, 'summary.regression.n must be a non-negative integer, got number 2.5'],
    ['a null', reg('a'), null, 'summary.regression.a must be a finite number, got null'],
    ['a NaN', reg('a'), NaN, 'summary.regression.a must be a finite number, got number NaN'],
    ['a_se a string', reg('a_se'), '0.1', 'summary.regression.a_se must be a finite number, got "0.1"'],
    ['b null', reg('b'), null, 'summary.regression.b must be a finite number, got null'],
    ['b_se Infinity', reg('b_se'), Infinity, 'summary.regression.b_se must be a finite number, got number Infinity'],
    ['b_ci not an array', reg('b_ci'), 0.5, 'summary.regression.b_ci must be an array, got number 0.5'],
    ['b_ci of one end', reg('b_ci'), [0.5], 'summary.regression.b_ci must have 2 entries (one per end (low, high)), got 1'],
    ['b_ci of three ends', reg('b_ci'), [0.1, 0.5, 0.9], 'summary.regression.b_ci must have 2 entries (one per end (low, high)), got 3'],
    ['b_ci end a string', reg('b_ci'), [0.25, '1.25'], 'summary.regression.b_ci[1] must be a finite number, got "1.25"'],
    ['b_ci end null', reg('b_ci'), [null, 1.25], 'summary.regression.b_ci[0] must be a finite number, got null'],
    ['b_ci reversed', reg('b_ci'), [1.25, 0.25], 'summary.regression.b_ci must not decrease: the low end (1.25) is above the high end (0.25)'],
    ['wald_f null', reg('wald_f'), null, 'summary.regression.wald_f must be a finite number, got null'],
    ['wald_df_num NaN', reg('wald_df_num'), NaN, 'summary.regression.wald_df_num must be a finite number, got number NaN'],
    ['wald_df a string', reg('wald_df'), '9', 'summary.regression.wald_df must be a finite number, got "9"'],
    ['wald_p above 1', reg('wald_p'), 1.5, 'summary.regression.wald_p must be a number from 0 to 1, got number 1.5'],
    ['wald_p negative', reg('wald_p'), -0.1, 'summary.regression.wald_p must be a number from 0 to 1, got number -0.1'],
    ['wald_p null', reg('wald_p'), null, 'summary.regression.wald_p must be a number from 0 to 1, got null'],
    ['role unknown', reg('role'), 'robustness', 'summary.regression.role must be "primary" or "exploratory", got "robustness"'],
    ['role null', reg('role'), null, 'summary.regression.role must be "primary" or "exploratory", got null'],
    ['p_holm above 1', reg('p_holm'), 1.5, 'summary.regression.p_holm must be a number from 0 to 1 or null, got number 1.5'],
    ['p_holm a string', reg('p_holm'), '0.5', 'summary.regression.p_holm must be a number from 0 to 1 or null, got "0.5"'],
    ['n_clusters_date negative', reg('n_clusters_date'), -1, 'summary.regression.n_clusters_date must be a non-negative integer, got number -1'],
    ['n_clusters_date null', reg('n_clusters_date'), null, 'summary.regression.n_clusters_date must be a non-negative integer, got null'],
    ['n_clusters_firm fractional', reg('n_clusters_firm'), 1.5, 'summary.regression.n_clusters_firm must be a non-negative integer, got number 1.5'],
    ['wald_p_one_way negative', reg('wald_p_one_way'), -1, 'summary.regression.wald_p_one_way must be a number from 0 to 1 or null, got number -1'],
    ['wald_p_one_way a string', reg('wald_p_one_way'), '0.1', 'summary.regression.wald_p_one_way must be a number from 0 to 1 or null, got "0.1"'],
    ['g1_rate above 1', reg('g1_rate'), 1.5, 'summary.regression.g1_rate must be a number from 0 to 1, got number 1.5'],
    ['g1_rate null', reg('g1_rate'), null, 'summary.regression.g1_rate must be a number from 0 to 1, got null'],
    ['g1_pass a string', reg('g1_pass'), 'false', 'summary.regression.g1_pass must be true or false, got "false"'],
    ['g1_pass null', reg('g1_pass'), null, 'summary.regression.g1_pass must be true or false, got null'],
    ['g1_bar above 1', reg('g1_bar'), 1.5, 'summary.regression.g1_bar must be a number from 0 to 1, got number 1.5'],
    ['g1_bar null', reg('g1_bar'), null, 'summary.regression.g1_bar must be a number from 0 to 1, got null'],
    ['g1_rate_one_way a string', reg('g1_rate_one_way'), '0.17', 'summary.regression.g1_rate_one_way must be a number from 0 to 1 or null, got "0.17"'],
    ['g1_rate_one_way negative', reg('g1_rate_one_way'), -0.1, 'summary.regression.g1_rate_one_way must be a number from 0 to 1 or null, got number -0.1'],
    ['g1_pass_one_way a string', reg('g1_pass_one_way'), 'false', 'summary.regression.g1_pass_one_way must be true, false or null, got "false"'],
    ['g1_pass_one_way a number', reg('g1_pass_one_way'), 0, 'summary.regression.g1_pass_one_way must be true, false or null, got number 0'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
})

describe('parseImpliedRealised: cross-field rules (fix R4 of the milestone-4 review)', () => {
  const regression = IMPLIED_REALISED_DATA_FIXTURE.summary.regression
  const withRegression = (patch: Record<string, unknown>): unknown => edited(['summary', 'regression'], { ...regression, ...patch })

  describe('I1: a primary test has a Holm p, an exploratory one has none', () => {
    it('refuses a primary without a Holm p', () => {
      expect(errorOf(edited(reg('p_holm'), null))).toBe('summary.regression.p_holm must be a number when role is "primary" (the test is in the Holm family), got null')
    })
    it('refuses an exploratory test with a Holm p', () => {
      expect(errorOf(edited(reg('role'), 'exploratory'))).toBe('summary.regression.p_holm must be null when role is "exploratory" (not in the Holm family), got number 0.5')
    })
  })

  describe('I2: the G1 verdicts follow the bar', () => {
    it('refuses a pass above the bar and a fail within it', () => {
      expect(errorOf(edited(reg('g1_pass'), true))).toBe('summary.regression.g1_pass is true, but g1_rate (0.5625) is above g1_bar (0.5)')
      expect(errorOf(edited(reg('g1_rate'), 0.25))).toBe('summary.regression.g1_pass is false, but g1_rate (0.25) is within g1_bar (0.5)')
    })
    it('counts a rate equal to the bar as a pass', () => {
      expect(parseImpliedRealised(withRegression({ g1_rate: 0.5, g1_pass: true })).ok).toBe(true)
      expect(errorOf(withRegression({ g1_rate: 0.5 }))).toBe('summary.regression.g1_pass is false, but g1_rate (0.5) is within g1_bar (0.5)')
    })
    it('holds the one-way verdict to the same bar', () => {
      expect(errorOf(withRegression({ g1_pass_one_way: true, wald_p_one_way: 0.25 }))).toBe('summary.regression.g1_pass_one_way is true, but g1_rate_one_way (0.625) is above g1_bar (0.5)')
      expect(errorOf(withRegression({ g1_rate_one_way: 0.375 }))).toBe('summary.regression.g1_pass_one_way is false, but g1_rate_one_way (0.375) is within g1_bar (0.5)')
    })
  })

  describe('I3: the one-way p-value is withheld exactly when its size check failed', () => {
    it('refuses a one-way p-value next to a failed one-way check', () => {
      expect(errorOf(edited(reg('wald_p_one_way'), 0.375))).toBe('summary.regression.wald_p_one_way must be null (withheld) when g1_pass_one_way is false, got number 0.375')
    })
    it('refuses a passed one-way check without its p-value', () => {
      expect(errorOf(withRegression({ g1_rate_one_way: 0.25, g1_pass_one_way: true }))).toBe('summary.regression.wald_p_one_way must be a number when g1_pass_one_way is true, got null')
    })
    it('refuses a one-way p-value or rate when no one-way check ran', () => {
      expect(errorOf(withRegression({ g1_pass_one_way: null }))).toBe(
        'summary.regression.g1_pass_one_way is null (no one-way size check), so wald_p_one_way and g1_rate_one_way must be null, got null and number 0.625',
      )
      expect(errorOf(withRegression({ g1_pass_one_way: null, g1_rate_one_way: null, wald_p_one_way: 0.25 }))).toBe(
        'summary.regression.g1_pass_one_way is null (no one-way size check), so wald_p_one_way and g1_rate_one_way must be null, got number 0.25 and null',
      )
    })
    it('refuses a one-way verdict without its rate', () => {
      expect(errorOf(edited(reg('g1_rate_one_way'), null))).toBe('summary.regression.g1_rate_one_way must be a number when g1_pass_one_way is false, got null')
    })
  })

  describe('I4: the benchmark is the declared 0.425', () => {
    it('refuses another benchmark, even a near one', () => {
      expect(errorOf(edited(['summary', 'share_exceed_benchmark'], 0.5))).toBe(
        'summary.share_exceed_benchmark must be the declared 0.425 (a fairly priced normal move is exceeded 42.5% of the time), got number 0.5',
      )
      expect(errorOf(edited(['summary', 'share_exceed_benchmark'], 0.4251))).toContain('got number 0.4251')
    })
  })

  describe('I5: every event appears once', () => {
    it('refuses a repeated event_id and names both places', () => {
      expect(errorOf(edited(['points', 3, 'event_id'], 'FIXB:2031-02-01'))).toBe('points[3].event_id "FIXB:2031-02-01" repeats points[1]: every event appears once')
    })
    it('accepts the same ticker on two events', () => {
      expect(parseImpliedRealised(edited(['points', 3, 'ticker'], 'FIXB')).ok).toBe(true)
    })
  })
})

describe('parseImpliedRealised: lookups, caveats, provenance', () => {
  it.each<[string, Path, unknown, string]>([
    ['lookups not an object', ['lookups'], 20, 'lookups must be an object, got number 20'],
    ['lookups.complete a string', ['lookups', 'complete'], 'no', 'lookups.complete must be true or false, got "no"'],
    ['lookups.n_done negative', ['lookups', 'n_done'], -3, 'lookups.n_done must be a non-negative integer, got number -3'],
    ['caveats not an array', ['caveats'], 'provisional', 'caveats must be an array, got "provisional"'],
    ['a caveat empty', ['caveats', 1], '', 'caveats[1] must be a non-empty string, got ""'],
    ['provenance not an object', ['provenance'], 'x', 'provenance must be an object, got "x"'],
    ['provenance lacks params_hash', ['provenance', 'params_hash'], undefined, 'provenance has missing key(s): params_hash'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
})

describe('the order of the checks', () => {
  it('reports a bad point before a bad summary, and a bad summary before bad lookups', () => {
    const both = edited(['points', 0, 'ticker'], '') as Record<string, unknown>
    ;(both.summary as Record<string, unknown>).n = -1
    expect(errorOf(both)).toBe('points[0].ticker must be a non-empty string, got ""')
    const summaryAndLookups = edited(['summary', 'n'], -1) as Record<string, unknown>
    summaryAndLookups.lookups = null
    expect(errorOf(summaryAndLookups)).toBe('summary.n must be a non-negative integer, got number -1')
  })
  it('reports a bad point field in key order (the first one that fails)', () => {
    const input = edited(['points', 0, 'ticker'], '') as Record<string, unknown>
    ;((input.points as Record<string, unknown>[])[0] as Record<string, unknown>).abs_realized = -1
    expect(errorOf(input)).toBe('points[0].ticker must be a non-empty string, got ""')
  })
})

describeLoader({
  name: 'loadImpliedRealised',
  load: loadImpliedRealised,
  defaultUrl: 'data/implied_vs_realised.json',
  kind: 'implied_vs_realised',
  body: IMPLIED_REALISED_FIXTURE,
  data: IMPLIED_REALISED_DATA_FIXTURE,
  brokenBody: { ...IMPLIED_REALISED_FIXTURE, data: edited(reg('b_ci'), [1.25, 0.25]) },
  brokenError: 'summary.regression.b_ci must not decrease: the low end (1.25) is above the high end (0.25)',
})
