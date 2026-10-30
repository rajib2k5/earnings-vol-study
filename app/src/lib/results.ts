/**
 * Loads and checks `data/tests.json` (kind "tests", schema 0.5.0): the test results of the study, written
 * by the Python exporter. The app only draws these numbers; it never recomputes a statistic, a
 * p-value or a Holm adjustment. `fetch` is injected so tests never touch the network; nothing here
 * throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   rows        array of test rows (see `TEST_ROW_FIELDS`): one per (hypothesis or measure, statistic, sample,
 *               subgroup, adjustment). `role` says where a row belongs: "primary" (the Holm family),
 *               "robustness" (another statistic for a primary hypothesis) or "exploratory" (q_bh applies)
 *   g1          the size-and-power gate: { reps, band, calibrated, designs, power, calibration }
 *   holm        { family, tested, untested, left_family }: lists of hypothesis names
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 *
 * Every estimate-like cell is a finite number or null. p_value, p_holm and q_bh are probabilities (0 to 1),
 * and ci_lo is at most ci_hi when both are there. Fields added after the milestone-3 review:
 * `g1_size` is the rejection rate under gate G1's calibrated null of a robustness statistic whose p-value
 * the exporter withheld as mis-sized, and `g1_reps` the replications that rate was measured on (2,000, or
 * 10,000 for a rate re-measured near the bar); `note` is the exporter's own sentence about the row (why its
 * p-value is withheld or kept, or a season-cut counterfactual), or null. A withheld row is a robustness row
 * with a null p-value and no interval, and g1_size and g1_reps come together (second fix round: a withheld
 * primary, or a withheld row that keeps its interval, is refused). `g1.calibrated[].pass` is the exporter's verdict and
 * is shown as written: it is not checked against `band` here, because the gate compares a rate with
 * the upper edge of the band, not with the whole band.
 *
 * Cross-field rules (fix R4 of the milestone-4 review; each message names the inconsistency):
 *   T1  a primary row has a p_value and a p_holm (a failed G1 check never withholds a primary)
 *   T2  only a primary row or a season-cut counterfactual (subgroup_key "season_cut") has a p_holm
 *   T3  holm.family and holm.left_family are disjoint; holm.tested and holm.untested are disjoint, and together they
 *       are holm.family (as sets: the order is the exporter's)
 * Since fix R1 the declared family H1 to H7 binds: H5 to H7 stay in `family` (and in `tested`) with a failed G1 check
 * in `g1.calibrated`; their rows are in drivers.json.
 */
import {
  isInteger,
  isNonNegIntOrNull,
  isNumberOrNull,
  isProbability,
  isProbabilityOrNull,
  loadKind,
  oneOf,
  ADJUSTMENTS,
  parseArrayOf,
  parseCaveats,
  parseLookups,
  parseRecords,
  type Adjustment,
  type Lookups,
} from './dataParts'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isFiniteNumber, isNonNegInt, isObject, isPositiveInt, isText, keyProblem, show, type Parsed } from './validate'

export const TESTS_URL = 'data/tests.json'
export const TESTS_KIND = 'tests'

export const HYPOTHESES = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7'] as const
export type Hypothesis = (typeof HYPOTHESES)[number]
export const ROLES = ['primary', 'robustness', 'exploratory'] as const
export type Role = (typeof ROLES)[number]
export const ESTIMANDS = ['equal_weighted', 'precision_weighted'] as const
export type Estimand = (typeof ESTIMANDS)[number]
export const SAMPLES = ['daily', 'mixed', 'coarse', 'cboe5'] as const
export type SampleName = (typeof SAMPLES)[number]

export interface TestRow {
  hypothesis: Hypothesis | null
  role: Role
  measure: string
  statistic: string
  estimand: Estimand | null
  sample: SampleName
  subgroup_key: string
  subgroup_value: string
  adjustment: Adjustment
  rel_day: number | null
  units: string
  n: number
  n_clusters: number | null
  n_clusters_firm: number | null
  estimate: number | null
  se: number | null
  stat: number | null
  df: number | null
  p_value: number | null
  p_holm: number | null
  q_bh: number | null
  ci_lo: number | null
  ci_hi: number | null
  rbar: number | null
  /** Rejection rate under G1's calibrated null, given only when the p-value is withheld as mis-sized. */
  g1_size: number | null
  /** The replications g1_size was measured on; given exactly when g1_size is. */
  g1_reps: number | null
  /** The exporter's note on this row, shown as written; null when there is none. */
  note: string | null
}

export interface Calibrated {
  hypothesis: Hypothesis
  statistic: string
  rejection_rate: number
  pass: boolean
}

export interface DesignRate {
  design: string
  hypothesis: Hypothesis
  statistic: string
  primary: boolean
  rejection_rate: number
}

export interface PowerCurve {
  hypothesis: Hypothesis
  shifts: number[]
  power: number[]
  /** Smallest shift on the grid with power of at least 80%; null when the grid never reaches it. */
  detectable_80: number | null
}

export interface G1 {
  reps: number
  band: [number, number]
  calibrated: Calibrated[]
  designs: DesignRate[]
  power: PowerCurve[]
  calibration: Record<string, number>
}

export interface Holm {
  family: string[]
  tested: string[]
  untested: string[]
  left_family: string[]
}

export interface TestsData {
  rows: TestRow[]
  g1: G1
  holm: Holm
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type TestsResult = Parsed<TestsData>

const isHypothesis = oneOf(...HYPOTHESES)
const isHypothesisOrNull = (x: unknown): x is Hypothesis | null => x === null || isHypothesis(x)
const isEstimandOrNull = (x: unknown): x is Estimand | null => x === null || oneOf(...ESTIMANDS)(x)
const isIntegerOrNull = (x: unknown): x is number | null => x === null || isInteger(x)
const isTextOrNull = (x: unknown): x is string | null => x === null || isText(x)
const isPositiveIntOrNull = (x: unknown): x is number | null => x === null || isPositiveInt(x)

/** Every field of a test row, in file order: [key, check, what the message says it must be]. */
const TEST_ROW_FIELDS: readonly (readonly [keyof TestRow, (x: unknown) => boolean, string])[] = [
  ['hypothesis', isHypothesisOrNull, 'null or one of H1 .. H7'],
  ['role', oneOf(...ROLES), '"primary", "robustness" or "exploratory"'],
  ['measure', isText, 'a non-empty string'],
  ['statistic', isText, 'a non-empty string'],
  ['estimand', isEstimandOrNull, 'null, "equal_weighted" or "precision_weighted"'],
  ['sample', oneOf(...SAMPLES), '"daily", "mixed", "coarse" or "cboe5"'],
  ['subgroup_key', isText, 'a non-empty string'],
  ['subgroup_value', isText, 'a non-empty string'],
  ['adjustment', oneOf(...ADJUSTMENTS), '"market" or "mean"'],
  ['rel_day', isIntegerOrNull, 'an integer or null'],
  ['units', isText, 'a non-empty string'],
  ['n', isNonNegInt, 'a non-negative integer'],
  ['n_clusters', isNonNegIntOrNull, 'a non-negative integer or null'],
  ['n_clusters_firm', isNonNegIntOrNull, 'a non-negative integer or null'],
  ['estimate', isNumberOrNull, 'a finite number or null'],
  ['se', isNumberOrNull, 'a finite number or null'],
  ['stat', isNumberOrNull, 'a finite number or null'],
  ['df', isNumberOrNull, 'a finite number or null'],
  ['p_value', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['p_holm', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['q_bh', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['ci_lo', isNumberOrNull, 'a finite number or null'],
  ['ci_hi', isNumberOrNull, 'a finite number or null'],
  ['rbar', isNumberOrNull, 'a finite number or null'],
  ['g1_size', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['g1_reps', isPositiveIntOrNull, 'a positive integer or null'],
  ['note', isTextOrNull, 'a non-empty string or null'],
]
const TEST_ROW_KEYS = TEST_ROW_FIELDS.map(([k]) => k)

const TESTS_KEYS = ['rows', 'g1', 'holm', 'lookups', 'caveats', 'provenance'] as const
const G1_KEYS = ['reps', 'band', 'calibrated', 'designs', 'power', 'calibration'] as const
const CALIBRATED_KEYS = ['hypothesis', 'statistic', 'rejection_rate', 'pass'] as const
const DESIGN_KEYS = ['design', 'hypothesis', 'statistic', 'primary', 'rejection_rate'] as const
const POWER_KEYS = ['hypothesis', 'shifts', 'power', 'detectable_80'] as const
const HOLM_KEYS = ['family', 'tested', 'untested', 'left_family'] as const

function parseRow(input: unknown, i: number): Parsed<TestRow> {
  const where = `rows[${i}]`
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, TEST_ROW_KEYS)
  if (problem) return fail(problem)
  for (const [key, ok, expected] of TEST_ROW_FIELDS) {
    if (!ok(input[key])) return fail(`${where}.${key} must be ${expected}, got ${show(input[key])}`)
  }
  const { ci_lo, ci_hi } = input
  if (typeof ci_lo === 'number' && typeof ci_hi === 'number' && ci_lo > ci_hi) {
    return fail(`${where}.ci_lo (${ci_lo}) must be at most ci_hi (${ci_hi})`)
  }
  if (input.g1_size !== null && input.p_value !== null) {
    return fail(`${where}.g1_size is given only for a withheld p-value, but p_value is ${show(input.p_value)}`)
  }
  if ((input.g1_size === null) !== (input.g1_reps === null)) {
    return fail(`${where}.g1_reps is given exactly when g1_size is, but g1_size is ${show(input.g1_size)} and g1_reps is ${show(input.g1_reps)}`)
  }
  if (input.g1_size !== null && input.role !== 'robustness') {
    return fail(`${where}.g1_size withholds only a robustness row, but role is ${show(input.role)}`)
  }
  if (input.g1_size !== null && (ci_lo !== null || ci_hi !== null)) {
    return fail(`${where} is withheld (g1_size ${show(input.g1_size)}) but keeps its interval [${show(ci_lo)}, ${show(ci_hi)}]`)
  }
  // T1
  if (input.role === 'primary') {
    for (const key of ['p_value', 'p_holm'] as const) {
      if (input[key] === null) return fail(`${where} has role "primary" but ${key} is null: a primary keeps its p-value and Holm p`)
    }
  }
  // T2
  if (input.p_holm !== null && input.role !== 'primary' && input.subgroup_key !== 'season_cut') {
    return fail(
      `${where}.p_holm is given only for a primary row or a season-cut counterfactual, but role is ${show(input.role)} and subgroup_key is ${show(input.subgroup_key)}`,
    )
  }
  return { ok: true, data: Object.fromEntries(TEST_ROW_KEYS.map((k) => [k, input[k]])) as unknown as TestRow }
}

/** A list of hypothesis names in a nested object: every entry a hypothesis-like string. */
const parseNames = (input: unknown, where: string) => parseArrayOf(input, where, isText, 'a non-empty string')

function parseG1(input: unknown): Parsed<G1> {
  if (!isObject(input)) return fail(`g1 must be an object, got ${show(input)}`)
  const problem = keyProblem('g1', input, G1_KEYS)
  if (problem) return fail(problem)
  const { reps, band, calibration } = input
  if (!isPositiveInt(reps)) return fail(`g1.reps must be a positive integer, got ${show(reps)}`)
  const bandNumbers = parseArrayOf(band, 'g1.band', isProbability, 'a number from 0 to 1', { n: 2, per: 'edge (lower, upper)' })
  if (!bandNumbers.ok) return bandNumbers
  const [lo, hi] = bandNumbers.data
  if (lo > hi) return fail(`g1.band must not decrease: the lower edge (${lo}) is above the upper edge (${hi})`)

  const calibrated = parseRecords<Calibrated>(input.calibrated, 'g1.calibrated', CALIBRATED_KEYS, (o, at) => {
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    if (!isText(o.statistic)) return fail(`${at}.statistic must be a non-empty string, got ${show(o.statistic)}`)
    if (!isProbability(o.rejection_rate)) return fail(`${at}.rejection_rate must be a number from 0 to 1, got ${show(o.rejection_rate)}`)
    if (typeof o.pass !== 'boolean') return fail(`${at}.pass must be true or false, got ${show(o.pass)}`)
    return { ok: true, data: { hypothesis: o.hypothesis, statistic: o.statistic, rejection_rate: o.rejection_rate, pass: o.pass } }
  })
  if (!calibrated.ok) return calibrated

  const designs = parseRecords<DesignRate>(input.designs, 'g1.designs', DESIGN_KEYS, (o, at) => {
    if (!isText(o.design)) return fail(`${at}.design must be a non-empty string, got ${show(o.design)}`)
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    if (!isText(o.statistic)) return fail(`${at}.statistic must be a non-empty string, got ${show(o.statistic)}`)
    if (typeof o.primary !== 'boolean') return fail(`${at}.primary must be true or false, got ${show(o.primary)}`)
    if (!isProbability(o.rejection_rate)) return fail(`${at}.rejection_rate must be a number from 0 to 1, got ${show(o.rejection_rate)}`)
    return { ok: true, data: { design: o.design, hypothesis: o.hypothesis, statistic: o.statistic, primary: o.primary, rejection_rate: o.rejection_rate } }
  })
  if (!designs.ok) return designs

  const power = parseRecords<PowerCurve>(input.power, 'g1.power', POWER_KEYS, (o, at) => {
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    const shifts = parseArrayOf(o.shifts, `${at}.shifts`, isFiniteNumber, 'a finite number')
    if (!shifts.ok) return shifts
    const curve = parseArrayOf(o.power, `${at}.power`, isProbability, 'a number from 0 to 1', { n: shifts.data.length, per: 'shift' })
    if (!curve.ok) return curve
    if (o.detectable_80 !== null && !isFiniteNumber(o.detectable_80)) {
      return fail(`${at}.detectable_80 must be a finite number or null, got ${show(o.detectable_80)}`)
    }
    return { ok: true, data: { hypothesis: o.hypothesis, shifts: shifts.data, power: curve.data, detectable_80: o.detectable_80 } }
  })
  if (!power.ok) return power

  if (!isObject(calibration)) return fail(`g1.calibration must be an object, got ${show(calibration)}`)
  for (const [k, v] of Object.entries(calibration)) {
    if (!isFiniteNumber(v)) return fail(`g1.calibration.${k} must be a finite number, got ${show(v)}`)
  }

  return {
    ok: true,
    data: {
      reps,
      band: [lo, hi],
      calibrated: calibrated.data,
      designs: designs.data,
      power: power.data,
      calibration: Object.fromEntries(Object.entries(calibration) as [string, number][]),
    },
  }
}

function parseHolm(input: unknown): Parsed<Holm> {
  if (!isObject(input)) return fail(`holm must be an object, got ${show(input)}`)
  const problem = keyProblem('holm', input, HOLM_KEYS)
  if (problem) return fail(problem)
  const lists = {} as Holm
  for (const key of HOLM_KEYS) {
    const names = parseNames(input[key], `holm.${key}`)
    if (!names.ok) return names
    lists[key] = names.data
  }
  // T3
  const { family, tested, untested, left_family } = lists
  const both = family.find((h) => left_family.includes(h))
  if (both !== undefined) return fail(`holm: ${both} is in both family and left_family`)
  const twice = tested.find((h) => untested.includes(h))
  if (twice !== undefined) return fail(`holm: ${twice} is in both tested and untested`)
  const union = [...tested, ...untested]
  const missing = family.filter((h) => !union.includes(h))
  const extra = union.filter((h) => !family.includes(h))
  if (missing.length > 0 || extra.length > 0) {
    return fail(`holm.tested and holm.untested together must be holm.family [${family.join(', ')}], but they lack [${missing.join(', ')}] and have the extra [${extra.join(', ')}]`)
  }
  return { ok: true, data: lists }
}

/**
 * Check the `data` object of a `kind: "tests"` envelope: exactly the keys above, each of the right
 * type. Nothing throws and nothing is coerced; a failure comes back as `{ ok: false, error }` naming
 * the first rule that failed.
 */
export function parseTests(input: unknown): TestsResult {
  if (!isObject(input)) return fail(`tests data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('tests data', input, TESTS_KEYS)
  if (top) return fail(top)

  const { rows } = input
  if (!Array.isArray(rows)) return fail(`rows must be an array, got ${show(rows)}`)
  const parsedRows: TestRow[] = []
  for (const [i, row] of rows.entries()) {
    const r = parseRow(row, i)
    if (!r.ok) return r
    parsedRows.push(r.data)
  }

  const g1 = parseG1(input.g1)
  if (!g1.ok) return g1
  const holm = parseHolm(input.holm)
  if (!holm.ok) return holm
  const lookups = parseLookups(input.lookups)
  if (!lookups.ok) return lookups
  const caveats = parseCaveats(input.caveats)
  if (!caveats.ok) return caveats
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: { rows: parsedRows, g1: g1.data, holm: holm.data, lookups: lookups.data, caveats: caveats.data, provenance: provenance.data },
  }
}

/** Fetch + validate `data/tests.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadTests = (url: string = TESTS_URL, fetchImpl?: typeof fetch): Promise<TestsResult> => loadKind(url, TESTS_KIND, parseTests, fetchImpl)

/** The rows of one role, in file order. */
export const rowsWithRole = (rows: readonly TestRow[], role: Role): TestRow[] => rows.filter((r) => r.role === role)

export interface HypothesisGroup {
  /** The hypothesis the rows belong to, or null for rows the file gives no hypothesis. */
  hypothesis: Hypothesis | null
  rows: TestRow[]
}

/**
 * The rows grouped by hypothesis, in H1 .. H7 order, the group without a hypothesis (if any) last.
 * Within a group the rows keep file order. Pure layout: no number is touched.
 */
export function groupByHypothesis(rows: readonly TestRow[]): HypothesisGroup[] {
  const groups: HypothesisGroup[] = []
  for (const h of [...HYPOTHESES, null]) {
    const inGroup = rows.filter((r) => r.hypothesis === h)
    if (inGroup.length > 0) groups.push({ hypothesis: h, rows: inGroup })
  }
  return groups
}
