import { describe, it, expect } from 'vitest'
import { groupByHypothesis, loadTests, parseTests, rowsWithRole, TESTS_KIND, TESTS_URL, type TestRow } from './results'
import { TESTS_DATA_FIXTURE, TESTS_FIXTURE } from '../test/resultsFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(TESTS_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseTests(input))

const KEYS = ['rows', 'g1', 'holm', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const ROW_KEYS = [
  'hypothesis', 'role', 'measure', 'statistic', 'estimand', 'sample', 'subgroup_key', 'subgroup_value', 'adjustment', 'rel_day', 'units', 'n',
  'n_clusters', 'n_clusters_firm', 'estimate', 'se', 'stat', 'df', 'p_value', 'p_holm', 'q_bh', 'ci_lo', 'ci_hi', 'rbar',
  'g1_size', 'g1_reps', 'note',
]
const ROW_KEY_LIST = ROW_KEYS.join(', ')
const G1_KEY_LIST = 'reps, band, calibrated, designs, power, calibration'

describe('parseTests: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseTests(TESTS_DATA_FIXTURE)).toEqual({ ok: true, data: TESTS_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies of the arrays and objects', () => {
    const input = structuredClone(TESTS_DATA_FIXTURE)
    const r = parseTests(input)
    expect(input).toEqual(TESTS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.rows).not.toBe(input.rows)
    expect(r.data.rows[0]).not.toBe(input.rows[0])
    expect(r.data.g1.band).not.toBe(input.g1.band)
    expect(r.data.g1.power[0].shifts).not.toBe(input.g1.power[0].shifts)
    expect(r.data.g1.calibration).not.toBe(input.g1.calibration)
    expect(r.data.holm.family).not.toBe(input.holm.family)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseTests(TESTS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('accepts a file with no rows and no caveats, and empty g1 lists', () => {
    expect(parseTests(edited(['rows'], [])).ok).toBe(true)
    expect(parseTests(edited(['caveats'], [])).ok).toBe(true)
    const g1 = { ...TESTS_DATA_FIXTURE.g1, calibrated: [], designs: [], power: [], calibration: {} }
    expect(parseTests(edited(['g1'], g1)).ok).toBe(true)
  })
  it('accepts every null the row may carry, 0 and 1 as p-values, and a band of equal edges', () => {
    const nulls = Object.fromEntries(['hypothesis', 'estimand', 'rel_day', 'n_clusters', 'n_clusters_firm', 'estimate', 'se', 'stat', 'df', 'p_value', 'p_holm', 'q_bh', 'ci_lo', 'ci_hi', 'rbar', 'g1_size', 'g1_reps', 'note'].map((k) => [k, null]))
    expect(parseTests(edited(['rows', 0], { ...TESTS_DATA_FIXTURE.rows[0], ...nulls })).ok).toBe(true)
    expect(parseTests(edited(['rows', 0], { ...TESTS_DATA_FIXTURE.rows[0], p_value: 0, p_holm: 1, q_bh: 1 })).ok).toBe(true)
    expect(parseTests(edited(['g1', 'band'], [0.4, 0.4])).ok).toBe(true)
  })
  it('accepts an integer rel_day (also negative), every role, estimand, sample, adjustment and hypothesis', () => {
    expect(parseTests(edited(['rows', 0, 'rel_day'], -3)).ok).toBe(true)
    for (const role of ['primary', 'robustness', 'exploratory']) expect(parseTests(edited(['rows', 0, 'role'], role)).ok, role).toBe(true)
    for (const sample of ['daily', 'mixed', 'coarse', 'cboe5']) expect(parseTests(edited(['rows', 0, 'sample'], sample)).ok, sample).toBe(true)
    for (const h of ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7']) expect(parseTests(edited(['rows', 0, 'hypothesis'], h)).ok, h).toBe(true)
    for (const e of ['equal_weighted', 'precision_weighted']) expect(parseTests(edited(['rows', 0, 'estimand'], e)).ok, e).toBe(true)
    for (const a of ['market', 'mean']) expect(parseTests(edited(['rows', 0, 'adjustment'], a)).ok, a).toBe(true)
  })
  it('keeps a "__proto__" key of g1.calibration as plain data and does not touch the prototype', () => {
    const data = JSON.parse(JSON.stringify(TESTS_DATA_FIXTURE).replace('"fix_phi":0.5', '"__proto__":0.5'))
    const r = parseTests(data)
    if (!r.ok) throw new Error(r.error)
    expect(Object.hasOwn(r.data.g1.calibration, '__proto__')).toBe(true)
    expect(Object.getPrototypeOf(r.data.g1.calibration)).toBe(Object.prototype)
  })
})

describe('parseTests: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'tests', 5, true]) expect(errorOf(x), String(x)).toContain('tests data must be a JSON object')
    expect(errorOf(null)).toBe('tests data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`tests data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it, and reports missing and extra keys together', () => {
    expect(errorOf(edited(['summary'], []))).toBe(`tests data has unexpected key(s): summary (expected exactly: ${KEY_LIST})`)
    const input = edited(['caveats'], undefined) as Record<string, unknown>
    input.note = 'x'
    expect(errorOf(input)).toContain('missing key(s): caveats; unexpected key(s): note')
  })
  it.each(ROW_KEYS)('requires the row key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(['rows', 1, key], undefined))).toBe(`rows[1] has missing key(s): ${key} (expected exactly: ${ROW_KEY_LIST})`)
  })
  it('rejects an extra row key', () => {
    expect(errorOf(edited(['rows', 0, 'q_value'], 0.1))).toBe(`rows[0] has unexpected key(s): q_value (expected exactly: ${ROW_KEY_LIST})`)
  })
  it.each<[string, Path, unknown, string]>([
    ['g1 lacks power', ['g1', 'power'], undefined, `g1 has missing key(s): power (expected exactly: ${G1_KEY_LIST})`],
    ['g1 has an extra key', ['g1', 'seed'], 1, `g1 has unexpected key(s): seed (expected exactly: ${G1_KEY_LIST})`],
    ['a calibrated entry lacks pass', ['g1', 'calibrated', 0, 'pass'], undefined, 'g1.calibrated[0] has missing key(s): pass (expected exactly: hypothesis, statistic, rejection_rate, pass)'],
    ['a calibrated entry has an extra key', ['g1', 'calibrated', 1, 'band'], 1, 'g1.calibrated[1] has unexpected key(s): band (expected exactly: hypothesis, statistic, rejection_rate, pass)'],
    ['a design lacks primary', ['g1', 'designs', 1, 'primary'], undefined, 'g1.designs[1] has missing key(s): primary (expected exactly: design, hypothesis, statistic, primary, rejection_rate)'],
    ['a power curve lacks detectable_80', ['g1', 'power', 0, 'detectable_80'], undefined, 'g1.power[0] has missing key(s): detectable_80 (expected exactly: hypothesis, shifts, power, detectable_80)'],
    ['holm lacks left_family', ['holm', 'left_family'], undefined, 'holm has missing key(s): left_family (expected exactly: family, tested, untested, left_family)'],
    ['holm has an extra key', ['holm', 'p'], [], 'holm has unexpected key(s): p (expected exactly: family, tested, untested, left_family)'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('names the kind the Python exporter writes', () => {
    expect(TESTS_KIND).toBe('tests')
    expect(TESTS_URL).toBe('data/tests.json')
  })
})

describe('parseTests: rows', () => {
  it('rejects rows that are not an array, and a row that is not an object', () => {
    expect(errorOf(edited(['rows'], {}))).toBe('rows must be an array, got an object')
    expect(errorOf(edited(['rows', 0], 'row'))).toBe('rows[0] must be an object, got "row"')
    expect(errorOf(edited(['rows', 2], null))).toBe('rows[2] must be an object, got null')
  })
  it.each<[string, unknown, string]>([
    ['hypothesis', 'H8', 'rows[0].hypothesis must be null or one of H1 .. H7, got "H8"'],
    ['hypothesis', 'h1', 'rows[0].hypothesis must be null or one of H1 .. H7, got "h1"'],
    ['role', 'secondary', 'rows[0].role must be "primary", "robustness" or "exploratory", got "secondary"'],
    ['measure', '', 'rows[0].measure must be a non-empty string, got ""'],
    ['statistic', 5, 'rows[0].statistic must be a non-empty string, got number 5'],
    ['estimand', 'equal', 'rows[0].estimand must be null, "equal_weighted" or "precision_weighted", got "equal"'],
    ['sample', 'weekly', 'rows[0].sample must be "daily", "mixed", "coarse" or "cboe5", got "weekly"'],
    ['subgroup_key', null, 'rows[0].subgroup_key must be a non-empty string, got null'],
    ['subgroup_value', ' ', 'rows[0].subgroup_value must be a non-empty string, got " "'],
    ['adjustment', 'beta', 'rows[0].adjustment must be "market" or "mean", got "beta"'],
    ['rel_day', 1.5, 'rows[0].rel_day must be an integer or null, got number 1.5'],
    ['rel_day', '1', 'rows[0].rel_day must be an integer or null, got "1"'],
    ['units', undefined, 'rows[0] has missing key(s): units'],
    ['n', -1, 'rows[0].n must be a non-negative integer, got number -1'],
    ['n', null, 'rows[0].n must be a non-negative integer, got null'],
    ['n', '11', 'rows[0].n must be a non-negative integer, got "11"'],
    ['n_clusters', 2.5, 'rows[0].n_clusters must be a non-negative integer or null, got number 2.5'],
    ['n_clusters_firm', -2, 'rows[0].n_clusters_firm must be a non-negative integer or null, got number -2'],
    ['estimate', '0.1', 'rows[0].estimate must be a finite number or null, got "0.1"'],
    ['estimate', NaN, 'rows[0].estimate must be a finite number or null, got number NaN'],
    ['se', Infinity, 'rows[0].se must be a finite number or null, got number Infinity'],
    ['stat', true, 'rows[0].stat must be a finite number or null, got boolean true'],
    ['df', [], 'rows[0].df must be a finite number or null, got an array'],
    ['p_value', 1.5, 'rows[0].p_value must be a number from 0 to 1 or null, got number 1.5'],
    ['p_value', -0.1, 'rows[0].p_value must be a number from 0 to 1 or null, got number -0.1'],
    ['p_holm', 2, 'rows[0].p_holm must be a number from 0 to 1 or null, got number 2'],
    ['p_holm', '0.5', 'rows[0].p_holm must be a number from 0 to 1 or null, got "0.5"'],
    ['q_bh', 1.0001, 'rows[0].q_bh must be a number from 0 to 1 or null, got number 1.0001'],
    ['ci_lo', 'low', 'rows[0].ci_lo must be a finite number or null, got "low"'],
    ['ci_hi', {}, 'rows[0].ci_hi must be a finite number or null, got an object'],
    ['rbar', NaN, 'rows[0].rbar must be a finite number or null, got number NaN'],
    ['g1_size', 1.5, 'rows[0].g1_size must be a number from 0 to 1 or null, got number 1.5'],
    ['g1_size', '0.241', 'rows[0].g1_size must be a number from 0 to 1 or null, got "0.241"'],
    ['g1_reps', 0, 'rows[0].g1_reps must be a positive integer or null, got number 0'],
    ['g1_reps', 2000.5, 'rows[0].g1_reps must be a positive integer or null, got number 2000.5'],
    ['g1_reps', '2000', 'rows[0].g1_reps must be a positive integer or null, got "2000"'],
    ['note', '', 'rows[0].note must be a non-empty string or null, got ""'],
    ['note', 5, 'rows[0].note must be a non-empty string or null, got number 5'],
  ])('rejects row field %s = %j', (key, value, message) => {
    expect(errorOf(edited(['rows', 0, key], value))).toContain(message)
  })
  it('names the row index and the field of the first bad value', () => {
    expect(errorOf(edited(['rows', 4, 'p_value'], 7))).toBe('rows[4].p_value must be a number from 0 to 1 or null, got number 7')
  })
  it('accepts a withheld p-value (null) with its G1 size and a note, and refuses a G1 size next to a p-value', () => {
    const withheld = { ...TESTS_DATA_FIXTURE.rows[2], p_value: null, ci_lo: null, ci_hi: null, g1_size: 0.241, g1_reps: 2000, note: 'Fixture note: withheld.' }
    const r = parseTests(edited(['rows', 2], withheld))
    if (!r.ok) throw new Error(r.error)
    expect(r.data.rows[2].g1_size).toBe(0.241)
    expect(r.data.rows[2].g1_reps).toBe(2000)
    expect(r.data.rows[2].note).toBe('Fixture note: withheld.')
    expect(errorOf(edited(['rows', 2], { ...withheld, p_value: 0.17 }))).toBe('rows[2].g1_size is given only for a withheld p-value, but p_value is number 0.17')
    expect(errorOf(edited(['rows', 2], { ...withheld, p_value: 0 }))).toBe('rows[2].g1_size is given only for a withheld p-value, but p_value is number 0')
    expect(parseTests(edited(['rows', 1, 'note'], 'Fixture note on a primary row.')).ok).toBe(true)
  })
  it('refuses a G1 size without its replications, and replications without a G1 size', () => {
    const withheld = { ...TESTS_DATA_FIXTURE.rows[2], p_value: null, ci_lo: null, ci_hi: null, g1_size: 0.0606, g1_reps: 10000 }
    expect(parseTests(edited(['rows', 2], withheld)).ok).toBe(true)
    expect(errorOf(edited(['rows', 2], { ...withheld, g1_reps: null }))).toBe('rows[2].g1_reps is given exactly when g1_size is, but g1_size is number 0.0606 and g1_reps is null')
    expect(errorOf(edited(['rows', 2], { ...withheld, g1_size: null }))).toBe('rows[2].g1_reps is given exactly when g1_size is, but g1_size is null and g1_reps is number 10000')
  })
  it('refuses a withheld primary row: G1 gates a primary through g1.calibrated, it never withholds one', () => {
    // rows[0] is the H1 primary; with p, CI and Holm p null and a G1 size it would read as a withheld robustness row.
    const prim = { ...TESTS_DATA_FIXTURE.rows[0], p_value: null, p_holm: null, ci_lo: null, ci_hi: null, g1_size: 0.07, g1_reps: 2000 }
    expect(errorOf(edited(['rows', 0], prim))).toBe('rows[0].g1_size withholds only a robustness row, but role is "primary"')
    expect(errorOf(edited(['rows', 0], { ...prim, role: 'exploratory' }))).toBe('rows[0].g1_size withholds only a robustness row, but role is "exploratory"')
    expect(parseTests(edited(['rows', 0], { ...prim, role: 'robustness' })).ok).toBe(true)
  })
  it('refuses a withheld row that keeps either end of its interval', () => {
    const withheld = { ...TESTS_DATA_FIXTURE.rows[2], p_value: null, ci_lo: null, ci_hi: null, g1_size: 0.241, g1_reps: 2000 }
    expect(errorOf(edited(['rows', 2], { ...withheld, ci_lo: -0.5, ci_hi: -0.25 }))).toBe('rows[2] is withheld (g1_size number 0.241) but keeps its interval [number -0.5, number -0.25]')
    expect(errorOf(edited(['rows', 2], { ...withheld, ci_lo: -0.5 }))).toBe('rows[2] is withheld (g1_size number 0.241) but keeps its interval [number -0.5, null]')
    expect(errorOf(edited(['rows', 2], { ...withheld, ci_hi: 0 }))).toBe('rows[2] is withheld (g1_size number 0.241) but keeps its interval [null, number 0]')
  })
  it('rejects a confidence interval whose low end is above its high end, and accepts equal ends', () => {
    expect(errorOf(edited(['rows', 0], { ...TESTS_DATA_FIXTURE.rows[0], ci_lo: 1, ci_hi: 0.5 }))).toBe('rows[0].ci_lo (1) must be at most ci_hi (0.5)')
    expect(parseTests(edited(['rows', 0], { ...TESTS_DATA_FIXTURE.rows[0], ci_lo: 0.5, ci_hi: 0.5 })).ok).toBe(true)
    expect(parseTests(edited(['rows', 0], { ...TESTS_DATA_FIXTURE.rows[0], ci_lo: 1, ci_hi: null })).ok).toBe(true)
  })
})

describe('parseTests: g1', () => {
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
    ['calibrated rate above 1', ['g1', 'calibrated', 0, 'rejection_rate'], 1.2, 'g1.calibrated[0].rejection_rate must be a number from 0 to 1, got number 1.2'],
    ['calibrated rate null', ['g1', 'calibrated', 0, 'rejection_rate'], null, 'g1.calibrated[0].rejection_rate must be a number from 0 to 1, got null'],
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
    ['shifts not an array', ['g1', 'power', 0, 'shifts'], 1, 'g1.power[0].shifts must be an array, got number 1'],
    ['a shift not a number', ['g1', 'power', 0, 'shifts', 1], '1', 'g1.power[0].shifts[1] must be a finite number, got "1"'],
    ['power longer than shifts (ragged)', ['g1', 'power', 0, 'power'], [0.25, 0.5, 1, 1], 'g1.power[0].power must have 3 entries (one per shift), got 4'],
    ['power shorter than shifts (ragged)', ['g1', 'power', 1, 'power'], [0.125], 'g1.power[1].power must have 2 entries (one per shift), got 1'],
    ['a power above 1', ['g1', 'power', 0, 'power', 2], 1.5, 'g1.power[0].power[2] must be a number from 0 to 1, got number 1.5'],
    ['a power null', ['g1', 'power', 0, 'power', 0], null, 'g1.power[0].power[0] must be a number from 0 to 1, got null'],
    ['detectable_80 a string', ['g1', 'power', 0, 'detectable_80'], '2', 'g1.power[0].detectable_80 must be a finite number or null, got "2"'],
    ['detectable_80 NaN', ['g1', 'power', 0, 'detectable_80'], NaN, 'g1.power[0].detectable_80 must be a finite number or null, got number NaN'],
    ['calibration not an object', ['g1', 'calibration'], [], 'g1.calibration must be an object, got an array'],
    ['a calibration value a string', ['g1', 'calibration', 'fix_phi'], '0.5', 'g1.calibration.fix_phi must be a finite number, got "0.5"'],
    ['a calibration value null', ['g1', 'calibration', 'fix_noise'], null, 'g1.calibration.fix_noise must be a finite number, got null'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('accepts detectable_80 of null and a power curve that never reaches 1', () => {
    expect(TESTS_DATA_FIXTURE.g1.power[1].detectable_80).toBeNull()
    expect(parseTests(TESTS_DATA_FIXTURE).ok).toBe(true)
  })
})

describe('parseTests: holm, lookups, caveats, provenance', () => {
  it.each<[string, Path, unknown, string]>([
    ['holm not an object', ['holm'], null, 'holm must be an object, got null'],
    ['family not an array', ['holm', 'family'], 'H1', 'holm.family must be an array, got "H1"'],
    ['tested entry a number', ['holm', 'tested', 0], 1, 'holm.tested[0] must be a non-empty string, got number 1'],
    ['untested entry empty', ['holm', 'untested', 0], '', 'holm.untested[0] must be a non-empty string, got ""'],
    ['left_family null', ['holm', 'left_family'], null, 'holm.left_family must be an array, got null'],
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
  it('accepts a left_family with names and a tested list in any order', () => {
    expect(parseTests(edited(['holm', 'left_family'], ['H2'])).ok).toBe(true)
    expect(parseTests(edited(['holm', 'tested'], ['H2', 'H1'])).ok).toBe(true)
  })
})

describe('rowsWithRole and groupByHypothesis', () => {
  const row = (hypothesis: TestRow['hypothesis'], role: TestRow['role'], statistic: string): TestRow => ({ ...(TESTS_DATA_FIXTURE.rows[0] as unknown as TestRow), hypothesis, role, statistic })
  const rows = [
    row('H3', 'robustness', 'a'),
    row(null, 'robustness', 'b'),
    row('H1', 'robustness', 'c'),
    row('H3', 'robustness', 'd'),
    row('H1', 'primary', 'e'),
    row('H2', 'exploratory', 'f'),
  ]
  it('rowsWithRole keeps the rows of one role in file order', () => {
    expect(rowsWithRole(rows, 'robustness').map((r) => r.statistic)).toEqual(['a', 'b', 'c', 'd'])
    expect(rowsWithRole(rows, 'primary').map((r) => r.statistic)).toEqual(['e'])
    expect(rowsWithRole([], 'primary')).toEqual([])
  })
  it('groups by hypothesis in H1..H7 order, rows without a hypothesis last, file order inside a group', () => {
    const groups = groupByHypothesis(rowsWithRole(rows, 'robustness'))
    expect(groups.map((g) => [g.hypothesis, g.rows.map((r) => r.statistic)])).toEqual([
      ['H1', ['c']],
      ['H3', ['a', 'd']],
      [null, ['b']],
    ])
  })
  it('gives no group for a hypothesis with no rows, and none at all for no rows', () => {
    expect(groupByHypothesis(rows).map((g) => g.hypothesis)).toEqual(['H1', 'H2', 'H3', null])
    expect(groupByHypothesis([])).toEqual([])
  })
})

describeLoader({
  name: 'loadTests',
  load: loadTests,
  defaultUrl: 'data/tests.json',
  kind: 'tests',
  body: TESTS_FIXTURE,
  data: TESTS_DATA_FIXTURE,
  brokenBody: { ...TESTS_FIXTURE, data: edited(['g1', 'band'], [0.6, 0.3]) },
  brokenError: 'g1.band must not decrease: the lower edge (0.6) is above the upper edge (0.3)',
})
