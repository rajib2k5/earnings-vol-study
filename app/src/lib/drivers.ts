/**
 * Loads and checks `data/drivers.json` (kind "drivers", schema 0.5.0): the regressions of the study on what
 * drives the crush (CRUSH on the earnings surprise and the prior level of volatility, H5 and H6), the
 * realised-on-implied variance regression (H7) and their robustness variants, written by the Python exporter.
 * The app only draws these numbers; it never recomputes a coefficient, a standard error, a p-value or a Holm
 * adjustment. `fetch` is injected so tests never touch the network; nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   models      array of regression models in file order (the first is the primary crush model), each
 *               { model_id, adjustment, sample, label, dep_var, fixed_effects, n, n_clusters_date,
 *               n_clusters_firm, r2, terms }. `model_id` is NOT unique: the mean-adjusted twin and the coarse
 *               sample of a model carry the id of the model they repeat, so the position in the array identifies a model
 *   g1          the size-and-power gate for H5 to H7: { reps, band, calibrated, designs, power, calibration_h7 }
 *   holm        { family, left_family, post_gate }: `family` is the DECLARED family, which binds (fix R1 of the
 *               milestone-4 review: H5 to H7 stay in it with their real p-values even though their G1 size check failed),
 *               `left_family` the hypotheses that left it (none at 0.5.0), and `post_gate` a DESCRIPTIVE SENSITIVITY:
 *               { family, p_holm, season_cut }, the Holm p over the family without the hypotheses whose G1 primary check
 *               failed, and H2's season-cut counterfactual on that family. It is never the binding `p_holm`
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 *
 * A term is one coefficient (or one Wald test) of a model, with exactly the keys of `TERM_FIELDS`. Every estimate-like
 * cell is a finite number or null; p_value, p_holm and q_bh are probabilities (0 to 1), and ci_lo is at most ci_hi.
 * `t` holds the t statistic, or the F statistic of a Wald row. g1_size and g1_reps come together. On a robustness row
 * they mean a WITHHELD p-value: p-value and interval are both null (the estimate stands). On a primary row they are the
 * record of its FAILED size check: the row keeps its p-value, interval and Holm p, and has a note. No exploratory row
 * has them. A Wald row (statistic ending in "_wald") has no coef, se or interval and gives the numerator degrees of
 * freedom in `df_num`; no other row has a `df_num`.
 *
 * Cross-field rules (fix R4 of the milestone-4 review; each message names the inconsistency):
 *   D1  a primary row has p_value, p_holm and (unless it is a Wald row, which has no interval) ci_lo and ci_hi, and a
 *       hypothesis that is in holm.family
 *   D2  only a primary row has a p_holm
 *   D3  holm.family and holm.left_family are disjoint and neither lists a hypothesis twice
 *   D4  a g1.calibrated entry measured on g1.reps replications passes exactly when its rate is at most band[1]
 *       (an entry re-measured on another count is decided against that count's bar, which the file does not give)
 *   D5  a primary with g1_size matches the failed primary entry of its hypothesis in g1.calibrated (rate and
 *       replications) and has a note; a primary without g1_size has no failed primary entry
 *   D6  a robustness row whose statistic failed in g1.calibrated is withheld with that rate as its g1_size (the key
 *       of the twin model, adjustment "mean", two-way t, is "twoway_date_t:mean_adj")
 *   D7  post_gate.family is holm.family without the hypotheses whose primary entry failed, in the same order; the keys
 *       of post_gate.p_holm are post_gate.family and those of post_gate.season_cut a subset of it
 *   D8  no hypothesis of holm.left_family has a primary row
 */
import {
  isNonNegIntOrNull,
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
import { HYPOTHESES, ROLES, SAMPLES, type Hypothesis, type Role, type SampleName } from './results'
import { fail, isFiniteNumber, isNonNegInt, isObject, isPositiveInt, isText, keyProblem, show, type Parsed } from './validate'

export const DRIVERS_URL = 'data/drivers.json'
export const DRIVERS_KIND = 'drivers'

export const MODEL_ADJUSTMENTS = ['market', 'mean', 'none'] as const
/** How the dependent variable of a model was adjusted; "none" for a model of raw realised variance. */
export type ModelAdjustment = (typeof MODEL_ADJUSTMENTS)[number]
export const TERM_STATISTICS = ['twoway_date_t', 'cluster_date_t', 'twoway_date_wald', 'cluster_date_wald'] as const
export type TermStatistic = (typeof TERM_STATISTICS)[number]
export const POWER_KINDS = ['beta', 'b'] as const
export type PowerKind = (typeof POWER_KINDS)[number]

export interface DriverTerm {
  term: string
  label: string
  hypothesis: Hypothesis | null
  role: Role
  statistic: TermStatistic
  cov_type: string
  n: number
  n_clusters_date: number | null
  n_clusters_firm: number | null
  coef: number | null
  se: number | null
  /** The t statistic, or the F statistic of a Wald row. */
  t: number | null
  df: number | null
  /** Numerator degrees of freedom; given exactly for a Wald row. */
  df_num: number | null
  p_value: number | null
  ci_lo: number | null
  ci_hi: number | null
  p_holm: number | null
  q_bh: number | null
  /**
   * Rejection rate under G1's calibrated null: on a robustness row, why its p-value is withheld as mis-sized; on a
   * primary row, the record of its failed size check (the p-value is kept).
   */
  g1_size: number | null
  /** The replications g1_size was measured on; given exactly when g1_size is. */
  g1_reps: number | null
  note: string | null
}

export interface DriverModel {
  model_id: string
  adjustment: ModelAdjustment
  sample: SampleName
  label: string
  dep_var: string
  fixed_effects: string[]
  n: number
  n_clusters_date: number | null
  n_clusters_firm: number | null
  r2: number | null
  terms: DriverTerm[]
}

export interface DriversCalibrated {
  hypothesis: Hypothesis
  statistic: string
  primary: boolean
  rejection_rate: number
  reps: number
  pass: boolean
}

export interface DriversDesign {
  design: string
  hypothesis: Hypothesis
  statistic: string
  primary: boolean
  rejection_rate: number
}

export interface DriversPower {
  hypothesis: Hypothesis
  /** What the shifts are: a slope shift ("beta", H5 and H6) or the slope b of the H7 regression ("b"). */
  kind: PowerKind
  shifts: number[]
  power: number[]
  /** Smallest shift on the grid with power of at least 80%; null when the grid never reaches it. */
  detectable_80: number | null
}

export interface DriversG1 {
  reps: number
  band: [number, number]
  calibrated: DriversCalibrated[]
  designs: DriversDesign[]
  power: DriversPower[]
  /** The calibration of the H7 simulation: parameter name to value (null when the exporter has none). */
  calibration_h7: Record<string, number | null>
}

/**
 * A descriptive sensitivity, never the binding `p_holm`: Holm over the declared family without the hypotheses whose G1
 * primary check failed.
 */
export interface DriversPostGate {
  family: string[]
  /** Holm p per hypothesis of `family`. */
  p_holm: Record<string, number>
  /** The Holm p of a season-cut counterfactual (fewer season clusters), per hypothesis that has one. */
  season_cut: Record<string, number>
}

export interface DriversHolm {
  /** The declared family: Holm runs over it, and its `p_holm` binds. */
  family: string[]
  left_family: string[]
  post_gate: DriversPostGate
}

export interface DriversData {
  models: DriverModel[]
  g1: DriversG1
  holm: DriversHolm
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type DriversResult = Parsed<DriversData>

const isHypothesis = oneOf(...HYPOTHESES)
const isHypothesisOrNull = (x: unknown): x is Hypothesis | null => x === null || isHypothesis(x)
const isTextOrNull = (x: unknown): x is string | null => x === null || isText(x)
const isPositiveIntOrNull = (x: unknown): x is number | null => x === null || isPositiveInt(x)

/** Every field of a term, in file order: [key, check, what the message says it must be]. */
const TERM_FIELDS: readonly (readonly [keyof DriverTerm, (x: unknown) => boolean, string])[] = [
  ['term', isText, 'a non-empty string'],
  ['label', isText, 'a non-empty string'],
  ['hypothesis', isHypothesisOrNull, 'null or one of H1 .. H7'],
  ['role', oneOf(...ROLES), '"primary", "robustness" or "exploratory"'],
  ['statistic', oneOf(...TERM_STATISTICS), '"twoway_date_t", "cluster_date_t", "twoway_date_wald" or "cluster_date_wald"'],
  ['cov_type', isText, 'a non-empty string'],
  ['n', isNonNegInt, 'a non-negative integer'],
  ['n_clusters_date', isNonNegIntOrNull, 'a non-negative integer or null'],
  ['n_clusters_firm', isNonNegIntOrNull, 'a non-negative integer or null'],
  ['coef', isNumberOrNull, 'a finite number or null'],
  ['se', isNumberOrNull, 'a finite number or null'],
  ['t', isNumberOrNull, 'a finite number or null'],
  ['df', isNumberOrNull, 'a finite number or null'],
  ['df_num', isNumberOrNull, 'a finite number or null'],
  ['p_value', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['ci_lo', isNumberOrNull, 'a finite number or null'],
  ['ci_hi', isNumberOrNull, 'a finite number or null'],
  ['p_holm', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['q_bh', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['g1_size', isProbabilityOrNull, 'a number from 0 to 1 or null'],
  ['g1_reps', isPositiveIntOrNull, 'a positive integer or null'],
  ['note', isTextOrNull, 'a non-empty string or null'],
]
const TERM_KEYS = TERM_FIELDS.map(([k]) => k)

const DRIVERS_KEYS = ['models', 'g1', 'holm', 'lookups', 'caveats', 'provenance'] as const
const MODEL_KEYS = ['model_id', 'adjustment', 'sample', 'label', 'dep_var', 'fixed_effects', 'n', 'n_clusters_date', 'n_clusters_firm', 'r2', 'terms'] as const
const G1_KEYS = ['reps', 'band', 'calibrated', 'designs', 'power', 'calibration_h7'] as const
const CALIBRATED_KEYS = ['hypothesis', 'statistic', 'primary', 'rejection_rate', 'reps', 'pass'] as const
const DESIGN_KEYS = ['design', 'hypothesis', 'statistic', 'primary', 'rejection_rate'] as const
const POWER_KEYS = ['hypothesis', 'kind', 'shifts', 'power', 'detectable_80'] as const
const HOLM_KEYS = ['family', 'left_family', 'post_gate'] as const
const POST_GATE_KEYS = ['family', 'p_holm', 'season_cut'] as const

function parseTerm(input: unknown, where: string): Parsed<DriverTerm> {
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, TERM_KEYS)
  if (problem) return fail(problem)
  for (const [key, ok, expected] of TERM_FIELDS) {
    if (!ok(input[key])) return fail(`${where}.${key} must be ${expected}, got ${show(input[key])}`)
  }
  const { ci_lo, ci_hi } = input
  if (typeof ci_lo === 'number' && typeof ci_hi === 'number' && ci_lo > ci_hi) {
    return fail(`${where}.ci_lo (${ci_lo}) must be at most ci_hi (${ci_hi})`)
  }
  if ((input.g1_size === null) !== (input.g1_reps === null)) {
    return fail(`${where}.g1_reps is given exactly when g1_size is, but g1_size is ${show(input.g1_size)} and g1_reps is ${show(input.g1_reps)}`)
  }
  if (input.g1_size !== null && input.role === 'exploratory') {
    return fail(`${where}.g1_size is given only on a withheld robustness row or as the failed size check of a primary, but role is "exploratory"`)
  }
  if (input.g1_size !== null && input.role === 'robustness') {
    if (input.p_value !== null) return fail(`${where}.g1_size is given only for a withheld p-value, but p_value is ${show(input.p_value)}`)
    if (ci_lo !== null || ci_hi !== null) {
      return fail(`${where} is withheld (g1_size ${show(input.g1_size)}) but keeps its interval [${show(ci_lo)}, ${show(ci_hi)}]`)
    }
  }
  const isWald = (input.statistic as string).endsWith('_wald')
  if (isWald) {
    for (const key of ['coef', 'se', 'ci_lo', 'ci_hi'] as const) {
      if (input[key] !== null) return fail(`${where}.${key} must be null for a Wald row (${show(input.statistic)}), got ${show(input[key])}`)
    }
    if (input.df_num === null) return fail(`${where}.df_num must be a number for a Wald row (${show(input.statistic)}), got null`)
  } else if (input.df_num !== null) {
    return fail(`${where}.df_num is given only for a Wald row, but statistic is ${show(input.statistic)} and df_num is ${show(input.df_num)}`)
  }
  // D1 (the part one row can check): a primary is never withheld; a failed size check is recorded in g1_size instead
  if (input.role === 'primary') {
    const kept = isWald ? (['p_value', 'p_holm'] as const) : (['p_value', 'ci_lo', 'ci_hi', 'p_holm'] as const)
    for (const key of kept) {
      if (input[key] === null) return fail(`${where} has role "primary" but ${key} is null: a primary keeps its p-value, interval and Holm p`)
    }
    if (input.hypothesis === null) return fail(`${where} has role "primary" but no hypothesis`)
  }
  // D2
  if (input.p_holm !== null && input.role !== 'primary') {
    return fail(`${where}.p_holm is given only for a primary row, but role is ${show(input.role)} and p_holm is ${show(input.p_holm)}`)
  }
  return { ok: true, data: Object.fromEntries(TERM_KEYS.map((k) => [k, input[k]])) as unknown as DriverTerm }
}

function parseModel(o: Record<string, unknown>, at: string): Parsed<DriverModel> {
  if (!isText(o.model_id)) return fail(`${at}.model_id must be a non-empty string, got ${show(o.model_id)}`)
  if (!oneOf(...MODEL_ADJUSTMENTS)(o.adjustment)) return fail(`${at}.adjustment must be "market", "mean" or "none", got ${show(o.adjustment)}`)
  if (!oneOf(...SAMPLES)(o.sample)) return fail(`${at}.sample must be "daily", "mixed", "coarse" or "cboe5", got ${show(o.sample)}`)
  if (!isText(o.label)) return fail(`${at}.label must be a non-empty string, got ${show(o.label)}`)
  if (!isText(o.dep_var)) return fail(`${at}.dep_var must be a non-empty string, got ${show(o.dep_var)}`)
  const fixedEffects = parseArrayOf(o.fixed_effects, `${at}.fixed_effects`, isText, 'a non-empty string')
  if (!fixedEffects.ok) return fixedEffects
  if (!isPositiveInt(o.n)) return fail(`${at}.n must be a positive integer, got ${show(o.n)}`)
  if (!isNonNegIntOrNull(o.n_clusters_date)) return fail(`${at}.n_clusters_date must be a non-negative integer or null, got ${show(o.n_clusters_date)}`)
  if (!isNonNegIntOrNull(o.n_clusters_firm)) return fail(`${at}.n_clusters_firm must be a non-negative integer or null, got ${show(o.n_clusters_firm)}`)
  if (!isNumberOrNull(o.r2)) return fail(`${at}.r2 must be a finite number or null, got ${show(o.r2)}`)
  if (!Array.isArray(o.terms)) return fail(`${at}.terms must be an array, got ${show(o.terms)}`)
  const terms: DriverTerm[] = []
  for (const [i, term] of o.terms.entries()) {
    const t = parseTerm(term, `${at}.terms[${i}]`)
    if (!t.ok) return t
    terms.push(t.data)
  }
  return {
    ok: true,
    data: {
      model_id: o.model_id,
      adjustment: o.adjustment,
      sample: o.sample,
      label: o.label,
      dep_var: o.dep_var,
      fixed_effects: fixedEffects.data,
      n: o.n,
      n_clusters_date: o.n_clusters_date,
      n_clusters_firm: o.n_clusters_firm,
      r2: o.r2,
      terms,
    },
  }
}

function parseG1(input: unknown): Parsed<DriversG1> {
  if (!isObject(input)) return fail(`g1 must be an object, got ${show(input)}`)
  const problem = keyProblem('g1', input, G1_KEYS)
  if (problem) return fail(problem)
  const { reps, band, calibration_h7 } = input
  if (!isPositiveInt(reps)) return fail(`g1.reps must be a positive integer, got ${show(reps)}`)
  const bandNumbers = parseArrayOf(band, 'g1.band', isProbability, 'a number from 0 to 1', { n: 2, per: 'edge (lower, upper)' })
  if (!bandNumbers.ok) return bandNumbers
  const [lo, hi] = bandNumbers.data
  if (lo > hi) return fail(`g1.band must not decrease: the lower edge (${lo}) is above the upper edge (${hi})`)

  const calibrated = parseRecords<DriversCalibrated>(input.calibrated, 'g1.calibrated', CALIBRATED_KEYS, (o, at) => {
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    if (!isText(o.statistic)) return fail(`${at}.statistic must be a non-empty string, got ${show(o.statistic)}`)
    if (typeof o.primary !== 'boolean') return fail(`${at}.primary must be true or false, got ${show(o.primary)}`)
    if (!isProbability(o.rejection_rate)) return fail(`${at}.rejection_rate must be a number from 0 to 1, got ${show(o.rejection_rate)}`)
    if (!isPositiveInt(o.reps)) return fail(`${at}.reps must be a positive integer, got ${show(o.reps)}`)
    if (typeof o.pass !== 'boolean') return fail(`${at}.pass must be true or false, got ${show(o.pass)}`)
    // D4: the verdict follows the bar of the count it was measured on; only g1.reps has its bar (band[1]) in the file
    if (o.reps === reps && o.pass !== o.rejection_rate <= hi) {
      return fail(
        `${at}.pass is ${o.pass}, but its rejection rate ${o.rejection_rate} on ${o.reps} replications is ${o.rejection_rate <= hi ? 'within' : 'above'} the band's upper edge ${hi}`,
      )
    }
    return { ok: true, data: { hypothesis: o.hypothesis, statistic: o.statistic, primary: o.primary, rejection_rate: o.rejection_rate, reps: o.reps, pass: o.pass } }
  })
  if (!calibrated.ok) return calibrated

  const designs = parseRecords<DriversDesign>(input.designs, 'g1.designs', DESIGN_KEYS, (o, at) => {
    if (!isText(o.design)) return fail(`${at}.design must be a non-empty string, got ${show(o.design)}`)
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    if (!isText(o.statistic)) return fail(`${at}.statistic must be a non-empty string, got ${show(o.statistic)}`)
    if (typeof o.primary !== 'boolean') return fail(`${at}.primary must be true or false, got ${show(o.primary)}`)
    if (!isProbability(o.rejection_rate)) return fail(`${at}.rejection_rate must be a number from 0 to 1, got ${show(o.rejection_rate)}`)
    return { ok: true, data: { design: o.design, hypothesis: o.hypothesis, statistic: o.statistic, primary: o.primary, rejection_rate: o.rejection_rate } }
  })
  if (!designs.ok) return designs

  const power = parseRecords<DriversPower>(input.power, 'g1.power', POWER_KEYS, (o, at) => {
    if (!isHypothesis(o.hypothesis)) return fail(`${at}.hypothesis must be one of H1 .. H7, got ${show(o.hypothesis)}`)
    if (!oneOf(...POWER_KINDS)(o.kind)) return fail(`${at}.kind must be "beta" or "b", got ${show(o.kind)}`)
    const shifts = parseArrayOf(o.shifts, `${at}.shifts`, isFiniteNumber, 'a finite number')
    if (!shifts.ok) return shifts
    const curve = parseArrayOf(o.power, `${at}.power`, isProbability, 'a number from 0 to 1', { n: shifts.data.length, per: 'shift' })
    if (!curve.ok) return curve
    if (o.detectable_80 !== null && !isFiniteNumber(o.detectable_80)) {
      return fail(`${at}.detectable_80 must be a finite number or null, got ${show(o.detectable_80)}`)
    }
    return { ok: true, data: { hypothesis: o.hypothesis, kind: o.kind, shifts: shifts.data, power: curve.data, detectable_80: o.detectable_80 } }
  })
  if (!power.ok) return power

  if (!isObject(calibration_h7)) return fail(`g1.calibration_h7 must be an object, got ${show(calibration_h7)}`)
  for (const [k, v] of Object.entries(calibration_h7)) {
    if (!isNumberOrNull(v)) return fail(`g1.calibration_h7.${k} must be a finite number or null, got ${show(v)}`)
  }

  return {
    ok: true,
    data: {
      reps,
      band: [lo, hi],
      calibrated: calibrated.data,
      designs: designs.data,
      power: power.data,
      calibration_h7: Object.fromEntries(Object.entries(calibration_h7) as [string, number | null][]),
    },
  }
}

/** The first entry that appears twice in `names`, or null. */
const repeated = (names: readonly string[]): string | null => names.find((n, i) => names.indexOf(n) !== i) ?? null

/** An object of hypothesis name to probability (a column of Holm p-values), copied. */
function parsePByHypothesis(input: unknown, where: string): Parsed<Record<string, number>> {
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  for (const [k, v] of Object.entries(input)) {
    if (!isProbability(v)) return fail(`${where}.${k} must be a number from 0 to 1, got ${show(v)}`)
  }
  return { ok: true, data: Object.fromEntries(Object.entries(input) as [string, number][]) }
}

function parsePostGate(input: unknown): Parsed<DriversPostGate> {
  const where = 'holm.post_gate'
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, POST_GATE_KEYS)
  if (problem) return fail(problem)
  const family = parseArrayOf(input.family, `${where}.family`, isText, 'a non-empty string')
  if (!family.ok) return family
  const pHolm = parsePByHypothesis(input.p_holm, `${where}.p_holm`)
  if (!pHolm.ok) return pHolm
  const seasonCut = parsePByHypothesis(input.season_cut, `${where}.season_cut`)
  if (!seasonCut.ok) return seasonCut
  // D7 (the part the sensitivity can check on its own): one Holm p per hypothesis of its family, and a season cut only for one of them
  const keys = Object.keys(pHolm.data)
  const missing = family.data.filter((h) => !keys.includes(h))
  const extra = keys.filter((h) => !family.data.includes(h))
  if (missing.length > 0 || extra.length > 0) {
    return fail(
      `${where}.p_holm must have one key per hypothesis of ${where}.family [${family.data.join(', ')}], but it lacks [${missing.join(', ')}] and has the extra [${extra.join(', ')}]`,
    )
  }
  const outside = Object.keys(seasonCut.data).filter((h) => !family.data.includes(h))
  if (outside.length > 0) return fail(`${where}.season_cut has [${outside.join(', ')}], which is not in ${where}.family [${family.data.join(', ')}]`)
  return { ok: true, data: { family: family.data, p_holm: pHolm.data, season_cut: seasonCut.data } }
}

function parseHolm(input: unknown): Parsed<DriversHolm> {
  if (!isObject(input)) return fail(`holm must be an object, got ${show(input)}`)
  const problem = keyProblem('holm', input, HOLM_KEYS)
  if (problem) return fail(problem)
  const family = parseArrayOf(input.family, 'holm.family', isText, 'a non-empty string')
  if (!family.ok) return family
  const left = parseArrayOf(input.left_family, 'holm.left_family', isText, 'a non-empty string')
  if (!left.ok) return left
  // D3
  for (const [key, names] of [['family', family.data], ['left_family', left.data]] as const) {
    const twice = repeated(names)
    if (twice !== null) return fail(`holm.${key} lists ${twice} twice`)
  }
  const both = family.data.find((h) => left.data.includes(h))
  if (both !== undefined) return fail(`holm: ${both} is in both family and left_family`)
  const postGate = parsePostGate(input.post_gate)
  if (!postGate.ok) return postGate
  return { ok: true, data: { family: family.data, left_family: left.data, post_gate: postGate.data } }
}

/** The key of a row in g1.calibrated: its statistic, marked ":mean_adj" for the two-way t of a mean-adjusted model. */
const calibratedKey = (model: DriverModel, term: DriverTerm): string =>
  model.adjustment === 'mean' && term.statistic === 'twoway_date_t' ? 'twoway_date_t:mean_adj' : term.statistic

/**
 * The rules that tie the terms, gate G1 and the Holm family together (D1's family part, D5, D6, D7's family part, D8).
 * Returns the first broken rule's message, or null.
 */
function crossCheck(models: readonly DriverModel[], g1: DriversG1, holm: DriversHolm): string | null {
  const primaryEntry = (h: string) => g1.calibrated.find((c) => c.primary && c.hypothesis === h)
  for (const [i, model] of models.entries()) {
    for (const [j, t] of model.terms.entries()) {
      const where = `models[${i}].terms[${j}]`
      const h = t.hypothesis as string // a primary has one (D1, checked per term); a row without one is skipped below
      if (t.role === 'primary') {
        // D8 (checked before D1's family part so the message names left_family)
        if (holm.left_family.includes(h)) return `${where} has role "primary", but ${h} is in holm.left_family`
        // D1
        if (!holm.family.includes(h)) return `${where} has role "primary", but its hypothesis ${h} is not in holm.family [${holm.family.join(', ')}]`
        // D5
        const entry = primaryEntry(h)
        if (t.g1_size !== null) {
          if (entry === undefined) return `${where} is a primary with g1_size ${t.g1_size}, but g1.calibrated has no primary entry for ${h}`
          if (entry.pass) return `${where} is a primary with g1_size ${t.g1_size} (a failed size check), but g1.calibrated says the primary statistic of ${h} passed`
          if (t.g1_size !== entry.rejection_rate) {
            return `${where}.g1_size (${t.g1_size}) must equal the rejection rate of the primary statistic of ${h} in g1.calibrated (${entry.rejection_rate})`
          }
          if (t.g1_reps !== entry.reps) {
            return `${where}.g1_reps (${t.g1_reps}) must equal the replications of the primary statistic of ${h} in g1.calibrated (${entry.reps})`
          }
          if (t.note === null) return `${where} is a primary whose size check failed (g1_size ${t.g1_size}) but has no note saying so`
        } else if (entry !== undefined && !entry.pass) {
          return `${where} is a primary with no g1_size, but g1.calibrated says the primary statistic of ${h} failed (rate ${entry.rejection_rate}): the failed size check must be recorded in g1_size and g1_reps`
        }
      } else if (t.role === 'robustness' && t.hypothesis !== null) {
        // D6
        const key = calibratedKey(model, t)
        const entry = g1.calibrated.find((c) => c.hypothesis === h && c.statistic === key)
        if (entry !== undefined && !entry.pass) {
          if (t.p_value !== null) {
            return `${where} is a robustness row whose statistic failed gate G1 (${h} ${key}, rate ${entry.rejection_rate}), so its p-value must be withheld, but p_value is ${t.p_value}`
          }
          if (t.g1_size !== entry.rejection_rate) {
            return `${where}.g1_size (${show(t.g1_size)}) must equal the G1 rejection rate of ${h} ${key} in g1.calibrated (${entry.rejection_rate})`
          }
        }
      }
    }
  }
  // D7
  const failed = failedHypotheses(g1.calibrated)
  const expected = holm.family.filter((h) => !failed.includes(h))
  const actual = holm.post_gate.family
  if (actual.length !== expected.length || actual.some((h, k) => h !== expected[k])) {
    return `holm.post_gate.family must be holm.family without the hypotheses whose G1 primary check failed (${failed.join(', ') || 'none'}): expected [${expected.join(', ')}], got [${actual.join(', ')}]`
  }
  return null
}

/**
 * Check the `data` object of a `kind: "drivers"` envelope: exactly the keys above, each of the right
 * type, then the cross-field rules D1 to D8. Nothing throws and nothing is coerced; a failure comes back as
 * `{ ok: false, error }` naming the first rule that failed.
 */
export function parseDrivers(input: unknown): DriversResult {
  if (!isObject(input)) return fail(`drivers data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('drivers data', input, DRIVERS_KEYS)
  if (top) return fail(top)

  const models = parseRecords<DriverModel>(input.models, 'models', MODEL_KEYS, parseModel)
  if (!models.ok) return models
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
  const broken = crossCheck(models.data, g1.data, holm.data)
  if (broken !== null) return fail(broken)

  return {
    ok: true,
    data: { models: models.data, g1: g1.data, holm: holm.data, lookups: lookups.data, caveats: caveats.data, provenance: provenance.data },
  }
}

/** Fetch + validate `data/drivers.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadDrivers = (url: string = DRIVERS_URL, fetchImpl?: typeof fetch): Promise<DriversResult> => loadKind(url, DRIVERS_KIND, parseDrivers, fetchImpl)

/** A term with a coefficient: what a forest plot can draw. */
export type PlottableTerm = DriverTerm & { coef: number }

/**
 * The terms of a model that a forest plot draws: the two-way rows (the statistic the study's inference rests on)
 * that have a coefficient, in file order. One-way rows and Wald rows are left out of the plot but stay in the table.
 * Pure selection: no number is touched.
 */
export function forestTerms(model: DriverModel): PlottableTerm[] {
  return model.terms.filter((t): t is PlottableTerm => t.statistic === 'twoway_date_t' && t.coef !== null)
}

/** The hypotheses whose primary statistic failed gate G1 (the verdict as the exporter wrote it), in file order, each once. */
export const failedHypotheses = (calibrated: readonly DriversCalibrated[]): string[] => [
  ...new Set(calibrated.filter((c) => c.primary && !c.pass).map((c) => c.hypothesis)),
]
