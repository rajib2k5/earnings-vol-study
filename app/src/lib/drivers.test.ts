import { describe, it, expect } from 'vitest'
import { DRIVERS_KIND, DRIVERS_URL, failedHypotheses, forestTerms, loadDrivers, parseDrivers, type DriverModel } from './drivers'
import { DRIVERS_DATA_FIXTURE, DRIVERS_FIXTURE } from '../test/driversFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(DRIVERS_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseDrivers(input))
/** The path of field `key` of term `j` of model `i` of the fixture. */
const term = (i: number, j: number, key: string): Path => ['models', i, 'terms', j, key]

const KEYS = ['models', 'g1', 'holm', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const MODEL_KEYS = ['model_id', 'adjustment', 'sample', 'label', 'dep_var', 'fixed_effects', 'n', 'n_clusters_date', 'n_clusters_firm', 'r2', 'terms']
const MODEL_KEY_LIST = MODEL_KEYS.join(', ')
const TERM_KEYS = [
  'term', 'label', 'hypothesis', 'role', 'statistic', 'cov_type', 'n', 'n_clusters_date', 'n_clusters_firm', 'coef', 'se', 't', 'df', 'df_num',
  'p_value', 'ci_lo', 'ci_hi', 'p_holm', 'q_bh', 'g1_size', 'g1_reps', 'note',
]
const TERM_KEY_LIST = TERM_KEYS.join(', ')
const G1_KEY_LIST = 'reps, band, calibrated, designs, power, calibration_h7'
const CALIBRATED_KEY_LIST = 'hypothesis, statistic, primary, rejection_rate, reps, pass'
const DESIGN_KEY_LIST = 'design, hypothesis, statistic, primary, rejection_rate'
const POWER_KEY_LIST = 'hypothesis, kind, shifts, power, detectable_80'
const HOLM_KEY_LIST = 'family, left_family, post_gate'
const POST_GATE_KEY_LIST = 'family, p_holm, season_cut'

/*
 * Mutations this file must catch. Each was applied to src/lib/drivers.ts, one at a time, and this file then failed; the file
 * was restored and its sha256 checked each time (script outside the repo).
 * Milestone 4 (22 of 22 killed then). Fix R1 changed DR2 and DR4 (re-tried as Dx2 and Dx1 below) and replaced the
 * all_declared rules DR14 and DR15 (re-tried as Dx3); the others were not re-tried after fix R1:
 *   DR1: swap the interval order rule (ci_lo > ci_hi becomes ci_lo < ci_hi)
 *   DR3: drop the rule that g1_size and g1_reps come together
 *   DR5: refuse a withheld row only when it keeps BOTH interval ends (|| becomes &&) (re-tried after fix R1: killed)
 *   DR6: a Wald row may keep its coef (coef dropped from the Wald null list)
 *   DR7: a Wald row needs no df_num
 *   DR8: a non-Wald row may carry df_num
 *   DR9: Wald detection by the wrong suffix
 *   DR10: power array no longer tied to the length of shifts
 *   DR11: g1.band order rule inverted
 *   DR12: p_value no longer checked as a probability
 *   DR13: extra term keys accepted
 *   DR16: forest plot also takes one-way rows
 *   DR17: failedHypotheses counts non-primary failures too
 *   DR18: statistic no longer restricted to the four known ones
 *   DR19: model n allowed to be 0
 *   DR20: calibration_h7 values may not be null
 *   DR21: loader checks the wrong kind
 *   DR22: model adjustment "none" not accepted
 * Fix R1 and R4 of the milestone-4 review (31 of 31 killed):
 *   D1a: a primary may lose its p-value, interval or Holm p      D1b: a Wald primary must have an interval too
 *   D1c: no primary needs an interval                           D1d: a primary may have no hypothesis
 *   D1e: a primary's hypothesis may be outside holm.family      D2: a non-primary row may carry a Holm p
 *   D3a: family / left_family may repeat a hypothesis           D3b: family and left_family may overlap
 *   D4a: pass not checked against band[1]                       D4b: D4 also applied to entries on another count
 *   D4c: a rate equal to band[1] counts as a fail (< for <=)    D5a: no check that the primary entry exists
 *   D5b: a primary's g1_size accepted when its entry passed     D5c: g1_size need not equal the entry's rate
 *   D5d: g1_reps need not equal the entry's reps                D5e: a failed primary needs no note
 *   D5f: a primary may hide a failed check (no g1_size)         D6a: a failed robustness statistic may keep its p
 *   D6b: a withheld g1_size need not equal its rate             D6c: no ":mean_adj" key for the twin model
 *   D6d: ":mean_adj" keyed on the market model instead          D7a: post_gate.family not checked
 *   D7b: post_gate.family order ignored                         D7c: post_gate.p_holm keys not checked
 *   D7d: extra post_gate.p_holm keys allowed                    D7e: season_cut may name a hypothesis outside post_gate
 *   D8: a hypothesis of left_family may have a primary row
 *   Dx1: g1_size accepted on an exploratory row (was DR4)       Dx2: a withheld robustness row may keep its p (was DR2)
 *   Dx3: post_gate Holm p values not checked as probabilities (was DR14)
 */

describe('parseDrivers: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseDrivers(DRIVERS_DATA_FIXTURE)).toEqual({ ok: true, data: DRIVERS_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies of the arrays and objects', () => {
    const input = structuredClone(DRIVERS_DATA_FIXTURE)
    const r = parseDrivers(input)
    expect(input).toEqual(DRIVERS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.models).not.toBe(input.models)
    expect(r.data.models[0]).not.toBe(input.models[0])
    expect(r.data.models[0].terms[0]).not.toBe(input.models[0].terms[0])
    expect(r.data.models[0].fixed_effects).not.toBe(input.models[0].fixed_effects)
    expect(r.data.g1.band).not.toBe(input.g1.band)
    expect(r.data.g1.power[0].shifts).not.toBe(input.g1.power[0].shifts)
    expect(r.data.g1.calibration_h7).not.toBe(input.g1.calibration_h7)
    expect(r.data.holm.post_gate).not.toBe(input.holm.post_gate)
    expect(r.data.holm.post_gate.family).not.toBe(input.holm.post_gate.family)
    expect(r.data.holm.post_gate.p_holm).not.toBe(input.holm.post_gate.p_holm)
    expect(r.data.holm.post_gate.season_cut).not.toBe(input.holm.post_gate.season_cut)
    expect(r.data.holm.family).not.toBe(input.holm.family)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('keeps the models in file order, and a model id that repeats (the twin and the coarse sample carry the id of the model they repeat)', () => {
    const r = parseDrivers(DRIVERS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.models.map((m) => m.label)).toEqual(['Fixture model A', 'Fixture model B (twin)', 'Fixture model C (Wald only)'])
    expect(r.data.models.map((m) => m.model_id)).toEqual(['fix_model_a', 'fix_model_a', 'fix_model_c'])
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseDrivers(DRIVERS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('accepts a file with no models, no caveats and empty g1 lists, and a model with no terms', () => {
    expect(parseDrivers(edited(['models'], [])).ok).toBe(true)
    expect(parseDrivers(edited(['caveats'], [])).ok).toBe(true)
    // with no calibrated entry nothing failed gate G1, so there are no primaries to record a failure and the sensitivity drops nothing
    const g1 = { ...DRIVERS_DATA_FIXTURE.g1, calibrated: [], designs: [], power: [], calibration_h7: {} }
    const family = DRIVERS_DATA_FIXTURE.holm.family
    const holm = { ...DRIVERS_DATA_FIXTURE.holm, post_gate: { family, p_holm: Object.fromEntries(family.map((h) => [h, 1])), season_cut: {} } }
    expect(parseDrivers({ ...DRIVERS_DATA_FIXTURE, models: [], g1, holm }).ok).toBe(true)
    expect(parseDrivers(edited(['models', 0, 'terms'], [])).ok).toBe(true)
    expect(parseDrivers(edited(['holm', 'post_gate', 'season_cut'], {})).ok).toBe(true)
  })
  it('accepts every null an exploratory term may carry, 0 and 1 as p-values, and a band of equal edges', () => {
    const nulls = Object.fromEntries(['hypothesis', 'n_clusters_date', 'n_clusters_firm', 'coef', 'se', 't', 'df', 'p_value', 'ci_lo', 'ci_hi', 'p_holm', 'q_bh', 'note'].map((k) => [k, null]))
    expect(parseDrivers(edited(['models', 1, 'terms', 0], { ...DRIVERS_DATA_FIXTURE.models[1].terms[0], ...nulls })).ok).toBe(true)
    expect(parseDrivers(edited(['models', 0, 'terms', 0], { ...DRIVERS_DATA_FIXTURE.models[0].terms[0], p_value: 0, p_holm: 1, q_bh: 1 })).ok).toBe(true)
    expect(parseDrivers(edited(['g1', 'band'], [0.4, 0.4])).ok).toBe(true)
    expect(parseDrivers(edited(['models', 0, 'terms', 0, 'ci_hi'], 0.125)).ok, 'ci_lo equal to ci_hi').toBe(true)
  })
  it('accepts every adjustment, sample, role, hypothesis and statistic', () => {
    for (const a of ['market', 'mean', 'none']) expect(parseDrivers(edited(['models', 0, 'adjustment'], a)).ok, a).toBe(true)
    for (const s of ['daily', 'mixed', 'coarse', 'cboe5']) expect(parseDrivers(edited(['models', 0, 'sample'], s)).ok, s).toBe(true)
    // the fixture has primary rows (terms[0], [1], [4] of model A); the exploratory row of model B may also be a robustness row
    expect(DRIVERS_DATA_FIXTURE.models[0].terms.map((t) => t.role)).toEqual(['primary', 'primary', 'robustness', 'robustness', 'primary'])
    for (const role of ['robustness', 'exploratory']) expect(parseDrivers(edited(term(1, 0, 'role'), role)).ok, role).toBe(true)
    for (const h of ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7']) expect(parseDrivers(edited(term(1, 0, 'hypothesis'), h)).ok, h).toBe(true)
    for (const s of ['twoway_date_t', 'cluster_date_t']) expect(parseDrivers(edited(term(1, 0, 'statistic'), s)).ok, s).toBe(true)
  })
  it('accepts both power kinds and a detectable shift of 0', () => {
    expect(parseDrivers(edited(['g1', 'power', 0, 'kind'], 'b')).ok).toBe(true)
    expect(parseDrivers(edited(['g1', 'power', 0, 'detectable_80'], 0)).ok).toBe(true)
  })
  it('keeps a "__proto__" key of g1.calibration_h7 as plain data and does not touch the prototype', () => {
    const data = JSON.parse(JSON.stringify(DRIVERS_DATA_FIXTURE).replace('"fix_nu":6.5', '"__proto__":6.5'))
    const r = parseDrivers(data)
    if (!r.ok) throw new Error(r.error)
    expect(Object.hasOwn(r.data.g1.calibration_h7, '__proto__')).toBe(true)
    expect(Object.getPrototypeOf(r.data.g1.calibration_h7)).toBe(Object.prototype)
  })
})

describe('parseDrivers: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'drivers', 5, true]) expect(errorOf(x), String(x)).toContain('drivers data must be a JSON object')
    expect(errorOf(null)).toBe('drivers data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`drivers data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it, and reports missing and extra keys together', () => {
    expect(errorOf(edited(['rows'], []))).toBe(`drivers data has unexpected key(s): rows (expected exactly: ${KEY_LIST})`)
    const input = edited(['caveats'], undefined) as Record<string, unknown>
    input.note = 'x'
    expect(errorOf(input)).toContain('missing key(s): caveats; unexpected key(s): note')
  })
  it.each(MODEL_KEYS)('requires the model key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(['models', 1, key], undefined))).toBe(`models[1] has missing key(s): ${key} (expected exactly: ${MODEL_KEY_LIST})`)
  })
  it('rejects an extra model key', () => {
    expect(errorOf(edited(['models', 0, 'weights'], 'x'))).toBe(`models[0] has unexpected key(s): weights (expected exactly: ${MODEL_KEY_LIST})`)
  })
  it.each(TERM_KEYS)('requires the term key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(term(0, 1, key), undefined))).toBe(`models[0].terms[1] has missing key(s): ${key} (expected exactly: ${TERM_KEY_LIST})`)
  })
  it('rejects an extra term key', () => {
    expect(errorOf(edited(term(1, 0, 'q_value'), 0.1))).toBe(`models[1].terms[0] has unexpected key(s): q_value (expected exactly: ${TERM_KEY_LIST})`)
  })
  it.each<[string, Path, unknown, string]>([
    ['g1 lacks power', ['g1', 'power'], undefined, `g1 has missing key(s): power (expected exactly: ${G1_KEY_LIST})`],
    ['g1 has the old calibration key', ['g1', 'calibration'], {}, `g1 has unexpected key(s): calibration (expected exactly: ${G1_KEY_LIST})`],
    ['g1 lacks calibration_h7', ['g1', 'calibration_h7'], undefined, `g1 has missing key(s): calibration_h7 (expected exactly: ${G1_KEY_LIST})`],
    ['a calibrated entry lacks reps', ['g1', 'calibrated', 0, 'reps'], undefined, `g1.calibrated[0] has missing key(s): reps (expected exactly: ${CALIBRATED_KEY_LIST})`],
    ['a calibrated entry has an extra key', ['g1', 'calibrated', 1, 'band'], 1, `g1.calibrated[1] has unexpected key(s): band (expected exactly: ${CALIBRATED_KEY_LIST})`],
    ['a design lacks primary', ['g1', 'designs', 1, 'primary'], undefined, `g1.designs[1] has missing key(s): primary (expected exactly: ${DESIGN_KEY_LIST})`],
    ['a power curve lacks kind', ['g1', 'power', 0, 'kind'], undefined, `g1.power[0] has missing key(s): kind (expected exactly: ${POWER_KEY_LIST})`],
    ['a power curve lacks detectable_80', ['g1', 'power', 0, 'detectable_80'], undefined, `g1.power[0] has missing key(s): detectable_80 (expected exactly: ${POWER_KEY_LIST})`],
    ['holm lacks post_gate', ['holm', 'post_gate'], undefined, `holm has missing key(s): post_gate (expected exactly: ${HOLM_KEY_LIST})`],
    ['holm has the old tested key', ['holm', 'tested'], [], `holm has unexpected key(s): tested (expected exactly: ${HOLM_KEY_LIST})`],
    ['holm has the removed all_declared key', ['holm', 'all_declared'], {}, `holm has unexpected key(s): all_declared (expected exactly: ${HOLM_KEY_LIST})`],
    ['post_gate lacks season_cut', ['holm', 'post_gate', 'season_cut'], undefined, `holm.post_gate has missing key(s): season_cut (expected exactly: ${POST_GATE_KEY_LIST})`],
    ['post_gate has an extra key', ['holm', 'post_gate', 'all_declared'], {}, `holm.post_gate has unexpected key(s): all_declared (expected exactly: ${POST_GATE_KEY_LIST})`],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('names the kind and the url the Python exporter writes', () => {
    expect(DRIVERS_KIND).toBe('drivers')
    expect(DRIVERS_URL).toBe('data/drivers.json')
  })
})

describe('parseDrivers: models', () => {
  it('rejects models that are not an array, and a model that is not an object', () => {
    expect(errorOf(edited(['models'], {}))).toBe('models must be an array, got an object')
    expect(errorOf(edited(['models', 0], 'model'))).toBe('models[0] must be an object, got "model"')
    expect(errorOf(edited(['models', 2], null))).toBe('models[2] must be an object, got null')
  })
  it.each<[string, unknown, string]>([
    ['model_id', '', 'models[1].model_id must be a non-empty string, got ""'],
    ['model_id', 7, 'models[1].model_id must be a non-empty string, got number 7'],
    ['adjustment', 'beta', 'models[1].adjustment must be "market", "mean" or "none", got "beta"'],
    ['adjustment', null, 'models[1].adjustment must be "market", "mean" or "none", got null'],
    ['sample', 'weekly', 'models[1].sample must be "daily", "mixed", "coarse" or "cboe5", got "weekly"'],
    ['label', ' ', 'models[1].label must be a non-empty string, got " "'],
    ['dep_var', null, 'models[1].dep_var must be a non-empty string, got null'],
    ['fixed_effects', 'sector', 'models[1].fixed_effects must be an array, got "sector"'],
    ['fixed_effects', [''], 'models[1].fixed_effects[0] must be a non-empty string, got ""'],
    ['n', 0, 'models[1].n must be a positive integer, got number 0'],
    ['n', 2.5, 'models[1].n must be a positive integer, got number 2.5'],
    ['n', '12', 'models[1].n must be a positive integer, got "12"'],
    ['n_clusters_date', -1, 'models[1].n_clusters_date must be a non-negative integer or null, got number -1'],
    ['n_clusters_date', '4', 'models[1].n_clusters_date must be a non-negative integer or null, got "4"'],
    ['n_clusters_firm', 1.5, 'models[1].n_clusters_firm must be a non-negative integer or null, got number 1.5'],
    ['r2', '0.5', 'models[1].r2 must be a finite number or null, got "0.5"'],
    ['r2', NaN, 'models[1].r2 must be a finite number or null, got number NaN'],
    ['terms', null, 'models[1].terms must be an array, got null'],
    ['terms', {}, 'models[1].terms must be an array, got an object'],
  ])('rejects %s = %j', (key, value, message) => {
    expect(errorOf(edited(['models', 1, key], value))).toBe(message)
  })
  it('names the model in the message, not just the field (models[2], not models[0])', () => {
    expect(errorOf(edited(['models', 2, 'n'], 0))).toBe('models[2].n must be a positive integer, got number 0')
  })
  it('accepts null for r2 and for both cluster counts (the twin model has them)', () => {
    const m = DRIVERS_DATA_FIXTURE.models[1]
    expect(m.r2).toBeNull()
    expect(m.n_clusters_date).toBeNull()
    expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
  })
})

describe('parseDrivers: terms', () => {
  it('rejects a term that is not an object', () => {
    expect(errorOf(edited(['models', 0, 'terms', 1], 'term'))).toBe('models[0].terms[1] must be an object, got "term"')
    expect(errorOf(edited(['models', 2, 'terms', 0], null))).toBe('models[2].terms[0] must be an object, got null')
  })
  it.each<[string, unknown, string]>([
    ['term', '', 'models[0].terms[1].term must be a non-empty string, got ""'],
    ['label', null, 'models[0].terms[1].label must be a non-empty string, got null'],
    ['hypothesis', 'H8', 'models[0].terms[1].hypothesis must be null or one of H1 .. H7, got "H8"'],
    ['hypothesis', 'h5', 'models[0].terms[1].hypothesis must be null or one of H1 .. H7, got "h5"'],
    ['role', 'secondary', 'models[0].terms[1].role must be "primary", "robustness" or "exploratory", got "secondary"'],
    ['statistic', 'bmp_t', 'models[0].terms[1].statistic must be "twoway_date_t", "cluster_date_t", "twoway_date_wald" or "cluster_date_wald", got "bmp_t"'],
    ['statistic', 5, 'models[0].terms[1].statistic must be "twoway_date_t", "cluster_date_t", "twoway_date_wald" or "cluster_date_wald", got number 5'],
    ['cov_type', ' ', 'models[0].terms[1].cov_type must be a non-empty string, got " "'],
    ['n', -1, 'models[0].terms[1].n must be a non-negative integer, got number -1'],
    ['n', null, 'models[0].terms[1].n must be a non-negative integer, got null'],
    ['n', '40', 'models[0].terms[1].n must be a non-negative integer, got "40"'],
    ['n_clusters_date', 2.5, 'models[0].terms[1].n_clusters_date must be a non-negative integer or null, got number 2.5'],
    ['n_clusters_firm', -2, 'models[0].terms[1].n_clusters_firm must be a non-negative integer or null, got number -2'],
    ['coef', '0.1', 'models[0].terms[1].coef must be a finite number or null, got "0.1"'],
    ['coef', NaN, 'models[0].terms[1].coef must be a finite number or null, got number NaN'],
    ['se', Infinity, 'models[0].terms[1].se must be a finite number or null, got number Infinity'],
    ['t', true, 'models[0].terms[1].t must be a finite number or null, got boolean true'],
    ['df', [], 'models[0].terms[1].df must be a finite number or null, got an array'],
    ['df_num', '2', 'models[0].terms[1].df_num must be a finite number or null, got "2"'],
    ['p_value', 1.5, 'models[0].terms[1].p_value must be a number from 0 to 1 or null, got number 1.5'],
    ['p_value', -0.1, 'models[0].terms[1].p_value must be a number from 0 to 1 or null, got number -0.1'],
    ['p_value', '0.5', 'models[0].terms[1].p_value must be a number from 0 to 1 or null, got "0.5"'],
    ['p_holm', 2, 'models[0].terms[1].p_holm must be a number from 0 to 1 or null, got number 2'],
    ['q_bh', -1, 'models[0].terms[1].q_bh must be a number from 0 to 1 or null, got number -1'],
    ['ci_lo', 'a', 'models[0].terms[1].ci_lo must be a finite number or null, got "a"'],
    ['ci_hi', NaN, 'models[0].terms[1].ci_hi must be a finite number or null, got number NaN'],
    ['g1_size', 1.5, 'models[0].terms[1].g1_size must be a number from 0 to 1 or null, got number 1.5'],
    ['g1_reps', 0, 'models[0].terms[1].g1_reps must be a positive integer or null, got number 0'],
    ['g1_reps', 2.5, 'models[0].terms[1].g1_reps must be a positive integer or null, got number 2.5'],
    ['note', '', 'models[0].terms[1].note must be a non-empty string or null, got ""'],
    ['note', 5, 'models[0].terms[1].note must be a non-empty string or null, got number 5'],
  ])('rejects %s = %j', (key, value, message) => {
    expect(errorOf(edited(term(0, 1, key), value))).toBe(message)
  })

  describe('the interval', () => {
    it('refuses ci_lo above ci_hi, and names both', () => {
      expect(errorOf(edited(term(0, 1, 'ci_lo'), 0.5))).toBe('models[0].terms[1].ci_lo (0.5) must be at most ci_hi (0.125)')
      expect(errorOf(edited(term(0, 0, 'ci_hi'), 0.0625))).toBe('models[0].terms[0].ci_lo (0.125) must be at most ci_hi (0.0625)')
    })
    it('checks the order only when both ends are there (on an exploratory row, which may lack either end)', () => {
      expect(parseDrivers(edited(term(1, 0, 'ci_hi'), null)).ok).toBe(true)
      expect(parseDrivers(edited(term(1, 0, 'ci_lo'), null)).ok).toBe(true)
    })
  })

  describe('g1_size and g1_reps: a withheld robustness p-value, or the failed size check of a primary', () => {
    it('is accepted: a robustness row with g1_size and g1_reps, a null p-value and no interval, whether the statistic is one-way or two-way', () => {
      expect(DRIVERS_DATA_FIXTURE.models[0].terms[2].g1_size).toBe(0.75)
      expect(DRIVERS_DATA_FIXTURE.models[0].terms[3].statistic).toBe('twoway_date_t')
      expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
    })
    it('is accepted on a primary that keeps its p-value, interval and Holm p (fix R1: a failed size check is recorded, not withheld)', () => {
      const t = DRIVERS_DATA_FIXTURE.models[0].terms[0]
      expect([t.role, t.p_value, t.ci_lo, t.ci_hi, t.p_holm, t.g1_size, t.g1_reps]).toEqual(['primary', 0.0125, 0.125, 0.375, 0.0625, 0.625, 500])
      expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
    })
    it('refuses g1_size on a robustness row that keeps its p-value', () => {
      expect(errorOf(edited(term(0, 2, 'p_value'), 0.1))).toBe('models[0].terms[2].g1_size is given only for a withheld p-value, but p_value is number 0.1')
    })
    it('refuses g1_size without g1_reps, and g1_reps without g1_size', () => {
      expect(errorOf(edited(term(0, 2, 'g1_reps'), null))).toBe('models[0].terms[2].g1_reps is given exactly when g1_size is, but g1_size is number 0.75 and g1_reps is null')
      expect(errorOf(edited(term(0, 1, 'g1_reps'), 2000))).toBe('models[0].terms[1].g1_reps is given exactly when g1_size is, but g1_size is null and g1_reps is number 2000')
    })
    it('refuses g1_size on an exploratory row', () => {
      expect(errorOf(edited(term(0, 2, 'role'), 'exploratory'))).toBe(
        'models[0].terms[2].g1_size is given only on a withheld robustness row or as the failed size check of a primary, but role is "exploratory"',
      )
    })
    it('refuses a withheld primary: a robustness row turned primary has no p-value (D1)', () => {
      expect(errorOf(edited(term(0, 2, 'role'), 'primary'))).toBe('models[0].terms[2] has role "primary" but p_value is null: a primary keeps its p-value, interval and Holm p')
    })
    it('refuses a withheld robustness row that keeps either end of its interval', () => {
      expect(errorOf(edited(term(0, 2, 'ci_lo'), 0.1))).toBe('models[0].terms[2] is withheld (g1_size number 0.75) but keeps its interval [number 0.1, null]')
      expect(errorOf(edited(term(0, 2, 'ci_hi'), 0.2))).toBe('models[0].terms[2] is withheld (g1_size number 0.75) but keeps its interval [null, number 0.2]')
      expect(errorOf(edited(term(0, 3, 'ci_hi'), 0.2))).toContain('models[0].terms[3] is withheld')
    })
    it('lets a robustness row that is not withheld keep its p-value and interval', () => {
      // terms[1] is the H6 primary, whose statistic passed gate G1; as a robustness row it carries no Holm p
      const row = { ...DRIVERS_DATA_FIXTURE.models[0].terms[1], role: 'robustness', p_holm: null }
      expect(parseDrivers(edited(['models', 0, 'terms', 1], row)).ok).toBe(true)
    })
  })

  describe('a Wald row (statistic ending in _wald)', () => {
    it('is accepted with no coef, se or interval and a numerator df, one-way or two-way', () => {
      expect(DRIVERS_DATA_FIXTURE.models[0].terms[4].statistic).toBe('twoway_date_wald')
      expect(DRIVERS_DATA_FIXTURE.models[2].terms[0].statistic).toBe('cluster_date_wald')
      expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
    })
    it.each([
      ['coef', 0.5],
      ['se', 0.5],
      ['ci_lo', 0.1],
      ['ci_hi', 0.2],
    ])('refuses a %s on a two-way Wald row', (key, value) => {
      expect(errorOf(edited(term(0, 4, key), value))).toBe(`models[0].terms[4].${key} must be null for a Wald row ("twoway_date_wald"), got number ${value}`)
    })
    it('refuses a coef on a one-way Wald row too', () => {
      expect(errorOf(edited(term(2, 0, 'coef'), 0.5))).toBe('models[2].terms[0].coef must be null for a Wald row ("cluster_date_wald"), got number 0.5')
    })
    it('refuses a Wald row without df_num', () => {
      expect(errorOf(edited(term(0, 4, 'df_num'), null))).toBe('models[0].terms[4].df_num must be a number for a Wald row ("twoway_date_wald"), got null')
    })
    it('refuses a df_num on a row that is not a Wald row', () => {
      expect(errorOf(edited(term(0, 0, 'df_num'), 2))).toBe('models[0].terms[0].df_num is given only for a Wald row, but statistic is "twoway_date_t" and df_num is number 2')
      expect(errorOf(edited(term(0, 2, 'df_num'), 2))).toContain('df_num is given only for a Wald row')
    })
  })
})

describe('parseDrivers: g1', () => {
  it.each<[string, Path, unknown, string]>([
    ['g1 not an object', ['g1'], [], 'g1 must be an object, got an array'],
    ['reps zero', ['g1', 'reps'], 0, 'g1.reps must be a positive integer, got number 0'],
    ['reps fractional', ['g1', 'reps'], 2.5, 'g1.reps must be a positive integer, got number 2.5'],
    ['reps a string', ['g1', 'reps'], '500', 'g1.reps must be a positive integer, got "500"'],
    ['band not an array', ['g1', 'band'], 0.3, 'g1.band must be an array, got number 0.3'],
    ['band of one edge', ['g1', 'band'], [0.3], 'g1.band must have 2 entries (one per edge (lower, upper)), got 1'],
    ['band of three edges', ['g1', 'band'], [0.1, 0.2, 0.3], 'g1.band must have 2 entries (one per edge (lower, upper)), got 3'],
    ['band edge above 1', ['g1', 'band'], [0.3, 1.5], 'g1.band[1] must be a number from 0 to 1, got number 1.5'],
    ['band edge null', ['g1', 'band'], [null, 0.5], 'g1.band[0] must be a number from 0 to 1, got null'],
    ['band reversed', ['g1', 'band'], [0.6, 0.3], 'g1.band must not decrease: the lower edge (0.6) is above the upper edge (0.3)'],
    ['calibrated not an array', ['g1', 'calibrated'], null, 'g1.calibrated must be an array, got null'],
    ['calibrated entry not an object', ['g1', 'calibrated', 0], 3, 'g1.calibrated[0] must be an object, got number 3'],
    ['calibrated hypothesis unknown', ['g1', 'calibrated', 0, 'hypothesis'], 'H9', 'g1.calibrated[0].hypothesis must be one of H1 .. H7, got "H9"'],
    ['calibrated hypothesis null', ['g1', 'calibrated', 0, 'hypothesis'], null, 'g1.calibrated[0].hypothesis must be one of H1 .. H7, got null'],
    ['calibrated statistic empty', ['g1', 'calibrated', 1, 'statistic'], '', 'g1.calibrated[1].statistic must be a non-empty string, got ""'],
    ['calibrated primary a string', ['g1', 'calibrated', 1, 'primary'], 'yes', 'g1.calibrated[1].primary must be true or false, got "yes"'],
    ['calibrated rate above 1', ['g1', 'calibrated', 0, 'rejection_rate'], 1.2, 'g1.calibrated[0].rejection_rate must be a number from 0 to 1, got number 1.2'],
    ['calibrated rate null', ['g1', 'calibrated', 0, 'rejection_rate'], null, 'g1.calibrated[0].rejection_rate must be a number from 0 to 1, got null'],
    ['calibrated reps zero', ['g1', 'calibrated', 0, 'reps'], 0, 'g1.calibrated[0].reps must be a positive integer, got number 0'],
    ['calibrated reps null', ['g1', 'calibrated', 3, 'reps'], null, 'g1.calibrated[3].reps must be a positive integer, got null'],
    ['calibrated pass a string', ['g1', 'calibrated', 0, 'pass'], 'true', 'g1.calibrated[0].pass must be true or false, got "true"'],
    ['calibrated pass a number', ['g1', 'calibrated', 0, 'pass'], 1, 'g1.calibrated[0].pass must be true or false, got number 1'],
    ['designs not an array', ['g1', 'designs'], {}, 'g1.designs must be an array, got an object'],
    ['design empty', ['g1', 'designs', 0, 'design'], '', 'g1.designs[0].design must be a non-empty string, got ""'],
    ['design hypothesis unknown', ['g1', 'designs', 1, 'hypothesis'], 'H0', 'g1.designs[1].hypothesis must be one of H1 .. H7, got "H0"'],
    ['design statistic number', ['g1', 'designs', 1, 'statistic'], 4, 'g1.designs[1].statistic must be a non-empty string, got number 4'],
    ['design primary a string', ['g1', 'designs', 0, 'primary'], 'yes', 'g1.designs[0].primary must be true or false, got "yes"'],
    ['design rate negative', ['g1', 'designs', 0, 'rejection_rate'], -0.5, 'g1.designs[0].rejection_rate must be a number from 0 to 1, got number -0.5'],
    ['power not an array', ['g1', 'power'], 'x', 'g1.power must be an array, got "x"'],
    ['power hypothesis unknown', ['g1', 'power', 0, 'hypothesis'], 'X', 'g1.power[0].hypothesis must be one of H1 .. H7, got "X"'],
    ['power kind unknown', ['g1', 'power', 0, 'kind'], 'gamma', 'g1.power[0].kind must be "beta" or "b", got "gamma"'],
    ['shifts not an array', ['g1', 'power', 0, 'shifts'], 1, 'g1.power[0].shifts must be an array, got number 1'],
    ['a shift not a number', ['g1', 'power', 0, 'shifts', 1], '1', 'g1.power[0].shifts[1] must be a finite number, got "1"'],
    ['power longer than shifts (ragged)', ['g1', 'power', 0, 'power'], [0.25, 0.5, 1], 'g1.power[0].power must have 2 entries (one per shift), got 3'],
    ['power shorter than shifts (ragged)', ['g1', 'power', 1, 'power'], [0.125], 'g1.power[1].power must have 3 entries (one per shift), got 1'],
    ['a power above 1', ['g1', 'power', 0, 'power', 1], 1.5, 'g1.power[0].power[1] must be a number from 0 to 1, got number 1.5'],
    ['a power null', ['g1', 'power', 0, 'power', 0], null, 'g1.power[0].power[0] must be a number from 0 to 1, got null'],
    ['detectable_80 a string', ['g1', 'power', 0, 'detectable_80'], '2', 'g1.power[0].detectable_80 must be a finite number or null, got "2"'],
    ['detectable_80 NaN', ['g1', 'power', 0, 'detectable_80'], NaN, 'g1.power[0].detectable_80 must be a finite number or null, got number NaN'],
    ['calibration_h7 not an object', ['g1', 'calibration_h7'], [], 'g1.calibration_h7 must be an object, got an array'],
    ['a calibration_h7 value a string', ['g1', 'calibration_h7', 'fix_nu'], '6.5', 'g1.calibration_h7.fix_nu must be a finite number or null, got "6.5"'],
    ['a calibration_h7 value NaN', ['g1', 'calibration_h7', 'fix_nu'], NaN, 'g1.calibration_h7.fix_nu must be a finite number or null, got number NaN'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('accepts a null calibration_h7 value and a detectable_80 of null', () => {
    expect(DRIVERS_DATA_FIXTURE.g1.calibration_h7.fix_missing).toBeNull()
    expect(DRIVERS_DATA_FIXTURE.g1.power[0].detectable_80).toBeNull()
    expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
  })
})

describe('parseDrivers: holm, lookups, caveats, provenance', () => {
  it.each<[string, Path, unknown, string]>([
    ['holm not an object', ['holm'], null, 'holm must be an object, got null'],
    ['family not an array', ['holm', 'family'], 'H1', 'holm.family must be an array, got "H1"'],
    ['family entry a number', ['holm', 'family', 0], 1, 'holm.family[0] must be a non-empty string, got number 1'],
    ['left_family entry empty', ['holm', 'left_family', 0], '', 'holm.left_family[0] must be a non-empty string, got ""'],
    ['left_family null', ['holm', 'left_family'], null, 'holm.left_family must be an array, got null'],
    ['post_gate not an object', ['holm', 'post_gate'], [0.5], 'holm.post_gate must be an object, got an array'],
    ['post_gate null', ['holm', 'post_gate'], null, 'holm.post_gate must be an object, got null'],
    ['post_gate.family not an array', ['holm', 'post_gate', 'family'], 'H1', 'holm.post_gate.family must be an array, got "H1"'],
    ['post_gate.family entry empty', ['holm', 'post_gate', 'family', 1], '', 'holm.post_gate.family[1] must be a non-empty string, got ""'],
    ['post_gate.p_holm not an object', ['holm', 'post_gate', 'p_holm'], [0.5], 'holm.post_gate.p_holm must be an object, got an array'],
    ['post_gate.p_holm value above 1', ['holm', 'post_gate', 'p_holm', 'H1'], 1.5, 'holm.post_gate.p_holm.H1 must be a number from 0 to 1, got number 1.5'],
    ['post_gate.p_holm value negative', ['holm', 'post_gate', 'p_holm', 'H2'], -0.1, 'holm.post_gate.p_holm.H2 must be a number from 0 to 1, got number -0.1'],
    ['post_gate.p_holm value null', ['holm', 'post_gate', 'p_holm', 'H6'], null, 'holm.post_gate.p_holm.H6 must be a number from 0 to 1, got null'],
    ['post_gate.p_holm value a string', ['holm', 'post_gate', 'p_holm', 'H1'], '0.5', 'holm.post_gate.p_holm.H1 must be a number from 0 to 1, got "0.5"'],
    ['post_gate.season_cut null', ['holm', 'post_gate', 'season_cut'], null, 'holm.post_gate.season_cut must be an object, got null'],
    ['post_gate.season_cut value above 1', ['holm', 'post_gate', 'season_cut', 'H2'], 2, 'holm.post_gate.season_cut.H2 must be a number from 0 to 1, got number 2'],
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
  it('accepts 0 and 1 as Holm sensitivity p-values, an empty season cut and an empty left_family', () => {
    expect(parseDrivers(edited(['holm', 'post_gate', 'p_holm', 'H1'], 0)).ok).toBe(true)
    expect(parseDrivers(edited(['holm', 'post_gate', 'season_cut', 'H2'], 1)).ok).toBe(true)
    expect(parseDrivers(edited(['holm', 'post_gate', 'season_cut'], {})).ok).toBe(true)
    expect(DRIVERS_DATA_FIXTURE.holm.left_family).toEqual([])
  })
  it('accepts a hypothesis that left the family when it has no primary row', () => {
    expect(parseDrivers(edited(['holm', 'left_family'], ['H3'])).ok).toBe(true)
  })
})

describe('parseDrivers: cross-field rules (fix R4 of the milestone-4 review)', () => {
  const holm = DRIVERS_DATA_FIXTURE.holm
  const calibrated = DRIVERS_DATA_FIXTURE.g1.calibrated

  describe('D1: a primary keeps its p-value, interval and Holm p, and its hypothesis is in the declared family', () => {
    it.each(['p_value', 'ci_lo', 'ci_hi', 'p_holm'])('refuses a two-way primary with %s null', (key) => {
      expect(errorOf(edited(term(0, 0, key), null))).toBe(`models[0].terms[0] has role "primary" but ${key} is null: a primary keeps its p-value, interval and Holm p`)
    })
    it('accepts a Wald primary without an interval (a joint test has none) and refuses one without a p-value or Holm p', () => {
      const wald = DRIVERS_DATA_FIXTURE.models[0].terms[4]
      expect([wald.role, wald.statistic, wald.ci_lo, wald.ci_hi]).toEqual(['primary', 'twoway_date_wald', null, null])
      expect(parseDrivers(DRIVERS_DATA_FIXTURE).ok).toBe(true)
      expect(errorOf(edited(term(0, 4, 'p_value'), null))).toBe('models[0].terms[4] has role "primary" but p_value is null: a primary keeps its p-value, interval and Holm p')
      expect(errorOf(edited(term(0, 4, 'p_holm'), null))).toBe('models[0].terms[4] has role "primary" but p_holm is null: a primary keeps its p-value, interval and Holm p')
    })
    it('refuses a primary without a hypothesis', () => {
      expect(errorOf(edited(term(0, 1, 'hypothesis'), null))).toBe('models[0].terms[1] has role "primary" but no hypothesis')
    })
    it('refuses a primary whose hypothesis is not in holm.family', () => {
      expect(errorOf(edited(['holm', 'family'], ['H1', 'H2', 'H5', 'H7']))).toBe('models[0].terms[1] has role "primary", but its hypothesis H6 is not in holm.family [H1, H2, H5, H7]')
    })
  })

  describe('D2: only a primary row has a Holm p', () => {
    it('refuses a Holm p on an exploratory row and on a robustness row', () => {
      expect(errorOf(edited(term(1, 0, 'p_holm'), 0.5))).toBe('models[1].terms[0].p_holm is given only for a primary row, but role is "exploratory" and p_holm is number 0.5')
      expect(errorOf(edited(term(0, 3, 'p_holm'), 0.5))).toBe('models[0].terms[3].p_holm is given only for a primary row, but role is "robustness" and p_holm is number 0.5')
    })
  })

  describe('D3: family and left_family are disjoint, and neither repeats a hypothesis', () => {
    it('refuses a hypothesis listed twice in family or in left_family', () => {
      expect(errorOf(edited(['holm', 'family'], [...holm.family, 'H2']))).toBe('holm.family lists H2 twice')
      expect(errorOf(edited(['holm', 'left_family'], ['H3', 'H3']))).toBe('holm.left_family lists H3 twice')
    })
    it('refuses a hypothesis in both family and left_family', () => {
      expect(errorOf(edited(['holm', 'left_family'], ['H4', 'H2']))).toBe('holm: H2 is in both family and left_family')
    })
  })

  describe('D4: a calibrated entry measured on g1.reps passes exactly when its rate is at most the band\'s upper edge', () => {
    it('refuses a pass above the edge and a fail within it', () => {
      expect(errorOf(edited(['g1', 'calibrated', 0, 'pass'], true))).toBe("g1.calibrated[0].pass is true, but its rejection rate 0.625 on 500 replications is above the band's upper edge 0.5")
      expect(errorOf(edited(['g1', 'calibrated', 3, 'pass'], false))).toBe("g1.calibrated[3].pass is false, but its rejection rate 0.375 on 500 replications is within the band's upper edge 0.5")
    })
    it('counts a rate equal to the edge as a pass', () => {
      expect(parseDrivers(edited(['g1', 'calibrated', 3, 'rejection_rate'], 0.5)).ok).toBe(true)
      expect(errorOf(edited(['g1', 'calibrated', 3], { ...calibrated[3], rejection_rate: 0.5, pass: false }))).toContain('g1.calibrated[3].pass is false')
    })
    it('does not check an entry re-measured on another count (the file does not give that count\'s bar)', () => {
      // the twin's entry, passing at 68.75% on 10,000 replications: its robustness row may then keep its withheld p-value
      expect(parseDrivers(edited(['g1', 'calibrated', 2], { ...calibrated[2], reps: 10000, pass: true })).ok).toBe(true)
      expect(errorOf(edited(['g1', 'calibrated', 2], { ...calibrated[2], pass: true }))).toContain('g1.calibrated[2].pass is true')
    })
  })

  describe('D5: a primary with g1_size is the failed primary entry of its hypothesis; a primary without one passed', () => {
    it('refuses g1_size on a primary whose hypothesis has no primary entry in g1.calibrated', () => {
      const g1 = { ...DRIVERS_DATA_FIXTURE.g1, calibrated: calibrated.filter((c) => !(c.hypothesis === 'H5' && c.primary)) }
      expect(errorOf({ ...DRIVERS_DATA_FIXTURE, g1 })).toBe('models[0].terms[0] is a primary with g1_size 0.625, but g1.calibrated has no primary entry for H5')
    })
    it('refuses g1_size on a primary whose primary entry passed', () => {
      expect(errorOf(edited(['g1', 'calibrated', 0], { ...calibrated[0], rejection_rate: 0.25, pass: true }))).toBe(
        'models[0].terms[0] is a primary with g1_size 0.625 (a failed size check), but g1.calibrated says the primary statistic of H5 passed',
      )
    })
    it('refuses a g1_size or g1_reps that is not the one of the primary entry', () => {
      expect(errorOf(edited(term(0, 0, 'g1_size'), 0.6))).toBe('models[0].terms[0].g1_size (0.6) must equal the rejection rate of the primary statistic of H5 in g1.calibrated (0.625)')
      expect(errorOf(edited(term(0, 0, 'g1_reps'), 2000))).toBe('models[0].terms[0].g1_reps (2000) must equal the replications of the primary statistic of H5 in g1.calibrated (500)')
    })
    it('refuses a failed primary without a note', () => {
      expect(errorOf(edited(term(0, 0, 'note'), null))).toBe('models[0].terms[0] is a primary whose size check failed (g1_size 0.625) but has no note saying so')
    })
    it('refuses a primary that hides its failed size check (no g1_size while its primary entry failed)', () => {
      const wald = { ...DRIVERS_DATA_FIXTURE.models[0].terms[4], g1_size: null, g1_reps: null }
      expect(errorOf(edited(['models', 0, 'terms', 4], wald))).toBe(
        'models[0].terms[4] is a primary with no g1_size, but g1.calibrated says the primary statistic of H7 failed (rate 0.5625): the failed size check must be recorded in g1_size and g1_reps',
      )
    })
    it('accepts a primary without g1_size whose hypothesis passed, or has no entry at all', () => {
      expect(DRIVERS_DATA_FIXTURE.models[0].terms[1].g1_size).toBeNull() // H6, which passed
      const g1 = { ...DRIVERS_DATA_FIXTURE.g1, calibrated: calibrated.filter((c) => c.hypothesis !== 'H6') }
      expect(parseDrivers({ ...DRIVERS_DATA_FIXTURE, g1 }).ok).toBe(true)
    })
  })

  describe('D6: a robustness row whose statistic failed gate G1 is withheld with that rate', () => {
    it('refuses a robustness row of a failed statistic that keeps its p-value', () => {
      const row = { ...DRIVERS_DATA_FIXTURE.models[0].terms[2], p_value: 0.01, g1_size: null, g1_reps: null }
      expect(errorOf(edited(['models', 0, 'terms', 2], row))).toBe(
        'models[0].terms[2] is a robustness row whose statistic failed gate G1 (H5 cluster_date_t, rate 0.75), so its p-value must be withheld, but p_value is 0.01',
      )
    })
    it('refuses a withheld row whose g1_size is not the rate of its statistic', () => {
      expect(errorOf(edited(term(0, 2, 'g1_size'), 0.7))).toBe('models[0].terms[2].g1_size (number 0.7) must equal the G1 rejection rate of H5 cluster_date_t in g1.calibrated (0.75)')
    })
    it('refuses a robustness row of a failed statistic with neither a p-value nor a g1_size', () => {
      const row = { ...DRIVERS_DATA_FIXTURE.models[0].terms[2], g1_size: null, g1_reps: null }
      expect(errorOf(edited(['models', 0, 'terms', 2], row))).toBe('models[0].terms[2].g1_size (null) must equal the G1 rejection rate of H5 cluster_date_t in g1.calibrated (0.75)')
    })
    it('keys the two-way row of a mean-adjusted model as "twoway_date_t:mean_adj", and that of another model by its statistic', () => {
      expect(errorOf(edited(term(1, 1, 'g1_size'), 0.625))).toBe(
        'models[1].terms[1].g1_size (number 0.625) must equal the G1 rejection rate of H5 twoway_date_t:mean_adj in g1.calibrated (0.6875)',
      )
      // the same row in a market-adjusted model is the two-way t of H5 itself, whose rate is 0.625
      expect(errorOf(edited(['models', 1, 'adjustment'], 'market'))).toBe('models[1].terms[1].g1_size (number 0.6875) must equal the G1 rejection rate of H5 twoway_date_t in g1.calibrated (0.625)')
    })
    it('puts no rule on a robustness row whose statistic passed or was not sized, or that has no hypothesis', () => {
      expect(DRIVERS_DATA_FIXTURE.models[0].terms[3].g1_size).toBe(0.09375) // H6 two-way: its entry passed; withheld on another count
      expect(parseDrivers(edited(term(0, 3, 'statistic'), 'cluster_date_t')).ok).toBe(true) // H6 cluster_date_t is not in g1.calibrated
      expect(parseDrivers(edited(['models', 0, 'terms', 2], { ...DRIVERS_DATA_FIXTURE.models[0].terms[2], hypothesis: null, g1_size: 0.1 })).ok).toBe(true)
    })
  })

  describe('D7: the post-gate sensitivity drops exactly the hypotheses whose primary check failed, and has one Holm p per hypothesis', () => {
    const postGate = (family: string[], seasonCut: Record<string, number> = {}) => ({
      ...holm,
      post_gate: { family, p_holm: Object.fromEntries(family.map((h) => [h, 0.5])), season_cut: seasonCut },
    })
    it('refuses a sensitivity family that drops too much, too little, or reorders', () => {
      const message = (got: string) => `holm.post_gate.family must be holm.family without the hypotheses whose G1 primary check failed (H5, H7): expected [H1, H2, H6], got [${got}]`
      expect(errorOf({ ...DRIVERS_DATA_FIXTURE, holm: postGate(['H1', 'H2']) })).toBe(message('H1, H2'))
      expect(errorOf({ ...DRIVERS_DATA_FIXTURE, holm: postGate(['H1', 'H2', 'H6', 'H7']) })).toBe(message('H1, H2, H6, H7'))
      expect(errorOf({ ...DRIVERS_DATA_FIXTURE, holm: postGate(['H2', 'H1', 'H6']) })).toBe(message('H2, H1, H6'))
    })
    it('wants the whole family when nothing failed gate G1', () => {
      // no models (so no primary records a failure) and no calibrated entry
      const quiet = { ...DRIVERS_DATA_FIXTURE, models: [], g1: { ...DRIVERS_DATA_FIXTURE.g1, calibrated: [] } }
      expect(errorOf({ ...quiet, holm: postGate(['H1', 'H2', 'H6']) })).toBe(
        'holm.post_gate.family must be holm.family without the hypotheses whose G1 primary check failed (none): expected [H1, H2, H5, H6, H7], got [H1, H2, H6]',
      )
      expect(parseDrivers({ ...quiet, holm: postGate(['H1', 'H2', 'H5', 'H6', 'H7']) }).ok).toBe(true)
    })
    it('refuses a Holm p missing for a hypothesis of the sensitivity family, or given for one outside it', () => {
      expect(errorOf(edited(['holm', 'post_gate', 'p_holm'], { H1: 0.5, H2: 0.5 }))).toBe(
        'holm.post_gate.p_holm must have one key per hypothesis of holm.post_gate.family [H1, H2, H6], but it lacks [H6] and has the extra []',
      )
      expect(errorOf(edited(['holm', 'post_gate', 'p_holm', 'H7'], 0.5))).toBe(
        'holm.post_gate.p_holm must have one key per hypothesis of holm.post_gate.family [H1, H2, H6], but it lacks [] and has the extra [H7]',
      )
    })
    it('refuses a season cut of a hypothesis outside the sensitivity family', () => {
      expect(errorOf(edited(['holm', 'post_gate', 'season_cut', 'H5'], 0.5))).toBe('holm.post_gate.season_cut has [H5], which is not in holm.post_gate.family [H1, H2, H6]')
    })
  })

  describe('D8: a hypothesis that left the family has no primary row', () => {
    it('refuses a primary of a hypothesis in left_family, naming left_family', () => {
      const moved = { ...holm, family: ['H1', 'H2', 'H6', 'H7'], left_family: ['H5'] }
      expect(errorOf({ ...DRIVERS_DATA_FIXTURE, holm: moved })).toBe('models[0].terms[0] has role "primary", but H5 is in holm.left_family')
    })
  })

  it('checks the cross-field rules only once every field has its type (a bad caveat is reported before a broken rule)', () => {
    const input = edited(term(0, 0, 'g1_size'), 0.6) as Record<string, unknown>
    input.caveats = ['']
    expect(errorOf(input)).toBe('caveats[0] must be a non-empty string, got ""')
  })
})

describe('the order of the checks', () => {
  it('reports a bad model before a bad g1, and a bad g1 before a bad holm', () => {
    const both = edited(['models', 0, 'n'], 0) as Record<string, unknown>
    ;(both.g1 as Record<string, unknown>).reps = 0
    expect(errorOf(both)).toBe('models[0].n must be a positive integer, got number 0')
    const g1AndHolm = edited(['g1', 'reps'], 0) as Record<string, unknown>
    g1AndHolm.holm = null
    expect(errorOf(g1AndHolm)).toBe('g1.reps must be a positive integer, got number 0')
  })
  it('reports a bad term of an earlier model before a bad field of a later one', () => {
    const input = edited(term(0, 1, 'p_value'), 2) as Record<string, unknown>
    ;((input.models as Record<string, unknown>[])[1] as Record<string, unknown>).n = 0
    expect(errorOf(input)).toBe('models[0].terms[1].p_value must be a number from 0 to 1 or null, got number 2')
  })
})

describe('forestTerms', () => {
  const model = (idx: number): DriverModel => {
    const r = parseDrivers(DRIVERS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    return r.data.models[idx]
  }
  it('keeps the two-way rows that have a coefficient, in file order, withheld ones too (their point is drawn without an interval)', () => {
    expect(forestTerms(model(0)).map((t) => `${t.term}:${t.statistic}:${t.coef}`)).toEqual([
      'fix_term_a:twoway_date_t:0.25',
      'fix_term_b:twoway_date_t:-0.125',
      'fix_term_b:twoway_date_t:0.1875',
    ])
  })
  it('leaves out one-way rows (the second row of model A) and Wald rows', () => {
    expect(forestTerms(model(0)).some((t) => t.statistic === 'cluster_date_t' || t.statistic.endsWith('_wald'))).toBe(false)
    expect(forestTerms(model(2))).toEqual([])
  })
  it('gives no term for a model with none, and every term of a model of two-way rows', () => {
    expect(forestTerms({ ...model(0), terms: [] })).toEqual([])
    expect(forestTerms(model(1)).map((t) => t.term)).toEqual(['fix_term_c', 'fix_term_a'])
  })
})

describe('failedHypotheses', () => {
  it('lists the hypotheses whose primary statistic failed, in file order, each once', () => {
    const r = parseDrivers(DRIVERS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    // H5 fails three times (primary, one-way, twin), H6 passes, H7 fails: the non-primary H5 rows alone must not matter, the primary one does
    expect(failedHypotheses(r.data.g1.calibrated)).toEqual(['H5', 'H7'])
  })
  it('ignores a failing statistic that is not primary, and a passing primary one', () => {
    const calibrated = [
      { hypothesis: 'H5', statistic: 'a', primary: false, rejection_rate: 0.9, reps: 10, pass: false },
      { hypothesis: 'H6', statistic: 'b', primary: true, rejection_rate: 0.1, reps: 10, pass: true },
    ] as const
    expect(failedHypotheses(calibrated)).toEqual([])
    expect(failedHypotheses([])).toEqual([])
  })
})

describeLoader({
  name: 'loadDrivers',
  load: loadDrivers,
  defaultUrl: 'data/drivers.json',
  kind: 'drivers',
  body: DRIVERS_FIXTURE,
  data: DRIVERS_DATA_FIXTURE,
  brokenBody: { ...DRIVERS_FIXTURE, data: edited(['g1', 'band'], [0.6, 0.3]) },
  brokenError: 'g1.band must not decrease: the lower edge (0.6) is above the upper edge (0.3)',
})
