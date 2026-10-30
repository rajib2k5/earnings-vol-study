/**
 * Loads and checks `data/implied_vs_realised.json` (kind "implied_vs_realised", schema 0.5.0): for each
 * earnings event, the absolute move the options implied on day -1 next to the absolute move that was realised
 * on day 0, and the summary of the comparison (how often the realised move exceeds the implied one, and the
 * regression of realised on implied variance behind H7). Written by the Python exporter. The app only draws
 * these numbers; it never recomputes a share, a regression or a p-value. `fetch` is injected so tests never
 * touch the network; nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   points      array of events, each with exactly the keys of `ImpliedPoint`; `implied_abs_move_total` is the expected
 *               absolute move (null when the options give none, see `implied_move_status`), `abs_realized` the absolute
 *               realised move, `timing_used` the announcement timing the day-0 label rests on (provisional)
 *   summary     the comparison: counts, `share_exceed` against its benchmark (0.425: a fair-priced normal move is
 *               exceeded that often, not half the time), the log ratio and the median ratio, and the `regression`
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 *
 * `summary.regression` is the regression of realised on implied variance: intercept `a` and slope `b` with standard
 * errors, the 95% interval `b_ci`, the joint Wald test of a = 0 and b = 1 (`wald_f` with `wald_df_num` and `wald_df`
 * degrees of freedom, p-value `wald_p`), its `role` ("primary" or "exploratory"), `p_holm` (given exactly when it is in
 * the Holm family) and the gate-G1 size check of the test: `g1_rate`, the rejection rate under the calibrated null,
 * `g1_bar`, the band's upper edge it is compared with, and `g1_pass`; and the same check of the one-way test
 * (`g1_rate_one_way`, `g1_pass_one_way`, both null when it was not run), whose p-value `wald_p_one_way` is withheld
 * (null) when that check failed. Since fix R1 of the milestone-4 review H7 stays primary with its failed check.
 * Numbers are shown as written: this validator checks types, ranges and these cross-field rules (fix R4), not the
 * arithmetic:
 *   I1  a primary test has a Holm p (wald_p is always given); an exploratory one has none
 *   I2  g1_pass is true exactly when g1_rate is at most g1_bar; likewise g1_pass_one_way with g1_rate_one_way
 *   I3  g1_pass_one_way false: wald_p_one_way withheld (null); true: given; null (no one-way check): wald_p_one_way and
 *       g1_rate_one_way both null. g1_rate_one_way is given whenever g1_pass_one_way is
 *   I4  share_exceed_benchmark is the declared 0.425
 *   I5  no two points share an event_id
 */
import {
  isNumberOrNull,
  isProbability,
  isProbabilityOrNull,
  loadKind,
  oneOf,
  parseArrayOf,
  parseCaveats,
  parseLookups,
  parseRecords,
  type Lookups,
} from './dataParts'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isFiniteNumber, isIsoDate, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const IMPLIED_REALISED_URL = 'data/implied_vs_realised.json'
export const IMPLIED_REALISED_KIND = 'implied_vs_realised'

export const TIMINGS = ['BMO', 'AMC'] as const
/** When the company reported: before the market opened or after it closed. */
export type Timing = (typeof TIMINGS)[number]
export const IMPLIED_STATUSES = ['ok', 'nonpositive_event_variance', 'not_identified'] as const
export type ImpliedStatus = (typeof IMPLIED_STATUSES)[number]
export const REGRESSION_ROLES = ['primary', 'exploratory'] as const
export type RegressionRole = (typeof REGRESSION_ROLES)[number]

export interface ImpliedPoint {
  event_id: string
  ticker: string
  sector: string
  /** The first session that reacts to the announcement, "YYYY-MM-DD". */
  day0: string
  timing_used: Timing | null
  event_var: number | null
  implied_var_total: number | null
  implied_move: number | null
  /** The expected absolute move (a fraction: 0.05 is 5%); null when none is given. */
  implied_abs_move_total: number | null
  realized_ret_0: number
  /** The absolute realised move on day 0 (a fraction). */
  abs_realized: number
  implied_move_status: ImpliedStatus | null
  surprise_scaled: number | null
}

export interface ImpliedRegression {
  n: number
  a: number
  a_se: number
  b: number
  b_se: number
  b_ci: [number, number]
  wald_f: number
  wald_df_num: number
  wald_df: number
  wald_p: number
  role: RegressionRole
  p_holm: number | null
  n_clusters_date: number
  n_clusters_firm: number
  wald_p_one_way: number | null
  g1_rate: number
  g1_pass: boolean
  /** The band's upper edge the G1 rates are compared with. */
  g1_bar: number
  /** The G1 rate of the one-way Wald test; null when it was not sized. */
  g1_rate_one_way: number | null
  g1_pass_one_way: boolean | null
}

export interface ImpliedSummary {
  n: number
  n_evar_nonpositive: number
  n_with_implied_abs_move: number
  share_exceed: number
  share_exceed_se: number
  share_exceed_p: number
  share_exceed_benchmark: number
  mean_log_ratio: number
  median_ratio: number
  regression: ImpliedRegression
}

export interface ImpliedRealisedData {
  points: ImpliedPoint[]
  summary: ImpliedSummary
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type ImpliedRealisedResult = Parsed<ImpliedRealisedData>

const isTiming = oneOf(...TIMINGS)
const isTimingOrNull = (x: unknown): x is Timing | null => x === null || isTiming(x)
const isStatus = oneOf(...IMPLIED_STATUSES)
const isStatusOrNull = (x: unknown): x is ImpliedStatus | null => x === null || isStatus(x)
const isNonNegNumber = (x: unknown): x is number => isFiniteNumber(x) && x >= 0

/** Every field of a point, in file order: [key, check, what the message says it must be]. */
const POINT_FIELDS: readonly (readonly [keyof ImpliedPoint, (x: unknown) => boolean, string])[] = [
  ['event_id', isText, 'a non-empty string'],
  ['ticker', isText, 'a non-empty string'],
  ['sector', isText, 'a non-empty string'],
  ['day0', isIsoDate, 'a calendar date "YYYY-MM-DD"'],
  ['timing_used', isTimingOrNull, 'null, "BMO" or "AMC"'],
  ['event_var', isNumberOrNull, 'a finite number or null'],
  ['implied_var_total', isNumberOrNull, 'a finite number or null'],
  ['implied_move', isNumberOrNull, 'a finite number or null'],
  ['implied_abs_move_total', isNumberOrNull, 'a finite number or null'],
  ['realized_ret_0', isFiniteNumber, 'a finite number'],
  ['abs_realized', isNonNegNumber, 'a finite number of at least 0'],
  ['implied_move_status', isStatusOrNull, 'null, "ok", "nonpositive_event_variance" or "not_identified"'],
  ['surprise_scaled', isNumberOrNull, 'a finite number or null'],
]
const POINT_KEYS = POINT_FIELDS.map(([k]) => k)

const IMPLIED_KEYS = ['points', 'summary', 'lookups', 'caveats', 'provenance'] as const
const SUMMARY_KEYS = [
  'n',
  'n_evar_nonpositive',
  'n_with_implied_abs_move',
  'share_exceed',
  'share_exceed_se',
  'share_exceed_p',
  'share_exceed_benchmark',
  'mean_log_ratio',
  'median_ratio',
  'regression',
] as const
const REGRESSION_KEYS = [
  'n',
  'a',
  'a_se',
  'b',
  'b_se',
  'b_ci',
  'wald_f',
  'wald_df_num',
  'wald_df',
  'wald_p',
  'role',
  'p_holm',
  'n_clusters_date',
  'n_clusters_firm',
  'wald_p_one_way',
  'g1_rate',
  'g1_pass',
  'g1_bar',
  'g1_rate_one_way',
  'g1_pass_one_way',
] as const

function parsePoint(o: Record<string, unknown>, at: string): Parsed<ImpliedPoint> {
  for (const [key, ok, expected] of POINT_FIELDS) {
    if (!ok(o[key])) return fail(`${at}.${key} must be ${expected}, got ${show(o[key])}`)
  }
  return { ok: true, data: Object.fromEntries(POINT_KEYS.map((k) => [k, o[k]])) as unknown as ImpliedPoint }
}

function parseRegression(input: unknown): Parsed<ImpliedRegression> {
  const where = 'summary.regression'
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, REGRESSION_KEYS)
  if (problem) return fail(problem)
  const numbers = ['a', 'a_se', 'b', 'b_se', 'wald_f', 'wald_df_num', 'wald_df'] as const
  for (const key of numbers) {
    if (!isFiniteNumber(input[key])) return fail(`${where}.${key} must be a finite number, got ${show(input[key])}`)
  }
  if (!isNonNegInt(input.n)) return fail(`${where}.n must be a non-negative integer, got ${show(input.n)}`)
  const ci = parseArrayOf(input.b_ci, `${where}.b_ci`, isFiniteNumber, 'a finite number', { n: 2, per: 'end (low, high)' })
  if (!ci.ok) return ci
  const [lo, hi] = ci.data
  if (lo > hi) return fail(`${where}.b_ci must not decrease: the low end (${lo}) is above the high end (${hi})`)
  if (!isProbability(input.wald_p)) return fail(`${where}.wald_p must be a number from 0 to 1, got ${show(input.wald_p)}`)
  if (!oneOf(...REGRESSION_ROLES)(input.role)) return fail(`${where}.role must be "primary" or "exploratory", got ${show(input.role)}`)
  if (!isProbabilityOrNull(input.p_holm)) return fail(`${where}.p_holm must be a number from 0 to 1 or null, got ${show(input.p_holm)}`)
  if (!isNonNegInt(input.n_clusters_date)) return fail(`${where}.n_clusters_date must be a non-negative integer, got ${show(input.n_clusters_date)}`)
  if (!isNonNegInt(input.n_clusters_firm)) return fail(`${where}.n_clusters_firm must be a non-negative integer, got ${show(input.n_clusters_firm)}`)
  if (!isProbabilityOrNull(input.wald_p_one_way)) return fail(`${where}.wald_p_one_way must be a number from 0 to 1 or null, got ${show(input.wald_p_one_way)}`)
  if (!isProbability(input.g1_rate)) return fail(`${where}.g1_rate must be a number from 0 to 1, got ${show(input.g1_rate)}`)
  if (typeof input.g1_pass !== 'boolean') return fail(`${where}.g1_pass must be true or false, got ${show(input.g1_pass)}`)
  if (!isProbability(input.g1_bar)) return fail(`${where}.g1_bar must be a number from 0 to 1, got ${show(input.g1_bar)}`)
  if (!isProbabilityOrNull(input.g1_rate_one_way)) return fail(`${where}.g1_rate_one_way must be a number from 0 to 1 or null, got ${show(input.g1_rate_one_way)}`)
  const passOneWay = input.g1_pass_one_way
  if (passOneWay !== null && typeof passOneWay !== 'boolean') return fail(`${where}.g1_pass_one_way must be true, false or null, got ${show(passOneWay)}`)
  // I1 (wald_p is a probability above, so never null)
  if (input.role === 'primary' && input.p_holm === null) return fail(`${where}.p_holm must be a number when role is "primary" (the test is in the Holm family), got null`)
  if (input.role === 'exploratory' && input.p_holm !== null) return fail(`${where}.p_holm must be null when role is "exploratory" (not in the Holm family), got ${show(input.p_holm)}`)
  // I2
  const bar = input.g1_bar
  if (input.g1_pass !== input.g1_rate <= bar) {
    return fail(`${where}.g1_pass is ${input.g1_pass}, but g1_rate (${input.g1_rate}) is ${input.g1_rate <= bar ? 'within' : 'above'} g1_bar (${bar})`)
  }
  const rateOneWay = input.g1_rate_one_way
  if (passOneWay !== null && rateOneWay !== null && passOneWay !== rateOneWay <= bar) {
    return fail(`${where}.g1_pass_one_way is ${passOneWay}, but g1_rate_one_way (${rateOneWay}) is ${rateOneWay <= bar ? 'within' : 'above'} g1_bar (${bar})`)
  }
  // I3
  if (passOneWay === null) {
    if (input.wald_p_one_way !== null || rateOneWay !== null) {
      return fail(
        `${where}.g1_pass_one_way is null (no one-way size check), so wald_p_one_way and g1_rate_one_way must be null, got ${show(input.wald_p_one_way)} and ${show(rateOneWay)}`,
      )
    }
  } else {
    if (rateOneWay === null) return fail(`${where}.g1_rate_one_way must be a number when g1_pass_one_way is ${passOneWay}, got null`)
    if (!passOneWay && input.wald_p_one_way !== null) {
      return fail(`${where}.wald_p_one_way must be null (withheld) when g1_pass_one_way is false, got ${show(input.wald_p_one_way)}`)
    }
    if (passOneWay && input.wald_p_one_way === null) return fail(`${where}.wald_p_one_way must be a number when g1_pass_one_way is true, got null`)
  }
  return {
    ok: true,
    data: {
      n: input.n,
      a: input.a as number,
      a_se: input.a_se as number,
      b: input.b as number,
      b_se: input.b_se as number,
      b_ci: [lo, hi],
      wald_f: input.wald_f as number,
      wald_df_num: input.wald_df_num as number,
      wald_df: input.wald_df as number,
      wald_p: input.wald_p,
      role: input.role,
      p_holm: input.p_holm,
      n_clusters_date: input.n_clusters_date,
      n_clusters_firm: input.n_clusters_firm,
      wald_p_one_way: input.wald_p_one_way,
      g1_rate: input.g1_rate,
      g1_pass: input.g1_pass,
      g1_bar: bar,
      g1_rate_one_way: rateOneWay,
      g1_pass_one_way: passOneWay,
    },
  }
}

/** The share of events a fairly priced normal move is exceeded by: the benchmark the study declared. */
export const SHARE_EXCEED_BENCHMARK = 0.425

function parseSummary(input: unknown): Parsed<ImpliedSummary> {
  if (!isObject(input)) return fail(`summary must be an object, got ${show(input)}`)
  const problem = keyProblem('summary', input, SUMMARY_KEYS)
  if (problem) return fail(problem)
  for (const key of ['n', 'n_evar_nonpositive', 'n_with_implied_abs_move'] as const) {
    if (!isNonNegInt(input[key])) return fail(`summary.${key} must be a non-negative integer, got ${show(input[key])}`)
  }
  for (const key of ['share_exceed', 'share_exceed_p', 'share_exceed_benchmark'] as const) {
    if (!isProbability(input[key])) return fail(`summary.${key} must be a number from 0 to 1, got ${show(input[key])}`)
  }
  for (const key of ['share_exceed_se', 'mean_log_ratio', 'median_ratio'] as const) {
    if (!isFiniteNumber(input[key])) return fail(`summary.${key} must be a finite number, got ${show(input[key])}`)
  }
  // I4
  if (input.share_exceed_benchmark !== SHARE_EXCEED_BENCHMARK) {
    return fail(`summary.share_exceed_benchmark must be the declared ${SHARE_EXCEED_BENCHMARK} (a fairly priced normal move is exceeded 42.5% of the time), got ${show(input.share_exceed_benchmark)}`)
  }
  const regression = parseRegression(input.regression)
  if (!regression.ok) return regression
  return {
    ok: true,
    data: {
      n: input.n as number,
      n_evar_nonpositive: input.n_evar_nonpositive as number,
      n_with_implied_abs_move: input.n_with_implied_abs_move as number,
      share_exceed: input.share_exceed as number,
      share_exceed_se: input.share_exceed_se as number,
      share_exceed_p: input.share_exceed_p as number,
      share_exceed_benchmark: input.share_exceed_benchmark as number,
      mean_log_ratio: input.mean_log_ratio as number,
      median_ratio: input.median_ratio as number,
      regression: regression.data,
    },
  }
}

/**
 * Check the `data` object of a `kind: "implied_vs_realised"` envelope: exactly the keys above, each of the
 * right type. Nothing throws and nothing is coerced; a failure comes back as `{ ok: false, error }` naming
 * the first rule that failed.
 */
export function parseImpliedRealised(input: unknown): ImpliedRealisedResult {
  if (!isObject(input)) return fail(`implied_vs_realised data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('implied_vs_realised data', input, IMPLIED_KEYS)
  if (top) return fail(top)

  const points = parseRecords<ImpliedPoint>(input.points, 'points', POINT_KEYS, parsePoint)
  if (!points.ok) return points
  // I5
  const firstAt = new Map<string, number>()
  for (const [i, p] of points.data.entries()) {
    const first = firstAt.get(p.event_id)
    if (first !== undefined) return fail(`points[${i}].event_id ${show(p.event_id)} repeats points[${first}]: every event appears once`)
    firstAt.set(p.event_id, i)
  }
  const summary = parseSummary(input.summary)
  if (!summary.ok) return summary
  const lookups = parseLookups(input.lookups)
  if (!lookups.ok) return lookups
  const caveats = parseCaveats(input.caveats)
  if (!caveats.ok) return caveats
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: { points: points.data, summary: summary.data, lookups: lookups.data, caveats: caveats.data, provenance: provenance.data },
  }
}

/** Fetch + validate `data/implied_vs_realised.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadImpliedRealised = (url: string = IMPLIED_REALISED_URL, fetchImpl?: typeof fetch): Promise<ImpliedRealisedResult> =>
  loadKind(url, IMPLIED_REALISED_KIND, parseImpliedRealised, fetchImpl)
