import { describe, it, expect, vi } from 'vitest'
import { IV_MEASURES_KIND, IV_MEASURES_URL, loadIvMeasures, parseIvMeasures, QUANTILE_NAMES } from './ivMeasures'
import { IV_MEASURES_DATA_FIXTURE, IV_MEASURES_FIXTURE } from '../test/ivMeasuresFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'

type Path = (string | number)[]
/** A deep copy of the hand-built good `data` with the value at `path` replaced (`undefined` deletes the key). */
const edited = (path: Path, value: unknown): unknown => {
  const root = structuredClone(IV_MEASURES_DATA_FIXTURE) as Record<string, unknown>
  let node: Record<string | number, unknown> = root
  for (const key of path.slice(0, -1)) node = node[key] as Record<string | number, unknown>
  const last = path[path.length - 1]
  if (value === undefined) delete node[last]
  else node[last] = value
  return root
}
const errorOf = (input: unknown): string => {
  const r = parseIvMeasures(input)
  if (r.ok) throw new Error('expected a failure, but the input was accepted')
  return r.error
}

const KEYS = ['sample', 'implied_move', 'crush', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const IMPLIED_MOVE_KEYS = 'units, n_identified, n_nonpositive, n, sqrt_mean_evar, quantiles, bin_edges, counts'
const CRUSH_KEYS = 'units, n, mean, quantiles, bin_edges, counts'
/** The empty histogram (no bins at all), which is only valid for n = 0. */
const EMPTY = { bin_edges: [], counts: [] }

describe('parseIvMeasures: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseIvMeasures(IV_MEASURES_DATA_FIXTURE)).toEqual({ ok: true, data: IV_MEASURES_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies of the arrays and objects', () => {
    const input = structuredClone(IV_MEASURES_DATA_FIXTURE)
    const r = parseIvMeasures(input)
    expect(input).toEqual(IV_MEASURES_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.caveats).not.toBe(input.caveats)
    expect(r.data.implied_move.bin_edges).not.toBe(input.implied_move.bin_edges)
    expect(r.data.implied_move.counts).not.toBe(input.implied_move.counts)
    expect(r.data.implied_move.quantiles).not.toBe(input.implied_move.quantiles)
    expect(r.data.crush.bin_edges).not.toBe(input.crush.bin_edges)
    expect(r.data.crush.counts).not.toBe(input.crush.counts)
    expect(r.data.crush.quantiles).not.toBe(input.crush.quantiles)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseIvMeasures(IV_MEASURES_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('accepts null quantiles, a null sqrt_mean_evar and a null mean', () => {
    const r = parseIvMeasures(
      edited(['implied_move'], { ...IV_MEASURES_DATA_FIXTURE.implied_move, quantiles: null, sqrt_mean_evar: null }),
    )
    if (!r.ok) throw new Error(r.error)
    expect(r.data.implied_move.quantiles).toBeNull()
    expect(r.data.implied_move.sqrt_mean_evar).toBeNull()
    const c = parseIvMeasures(edited(['crush'], { ...IV_MEASURES_DATA_FIXTURE.crush, quantiles: null, mean: null }))
    if (!c.ok) throw new Error(c.error)
    expect(c.data.crush.quantiles).toBeNull()
    expect(c.data.crush.mean).toBeNull()
  })
  it('accepts both histograms empty when n is 0, and no caveats', () => {
    const r = parseIvMeasures(
      edited(['implied_move'], { ...IV_MEASURES_DATA_FIXTURE.implied_move, n: 0, n_nonpositive: 0, n_identified: 0, sqrt_mean_evar: null, quantiles: null, ...EMPTY }),
    )
    expect(r.ok).toBe(true)
    expect(parseIvMeasures(edited(['crush'], { ...IV_MEASURES_DATA_FIXTURE.crush, n: 0, mean: null, quantiles: null, ...EMPTY })).ok).toBe(true)
    expect(parseIvMeasures(edited(['caveats'], [])).ok).toBe(true)
  })
  it('accepts a single edge with no counts (zero bins) when n is 0', () => {
    expect(parseIvMeasures(edited(['crush'], { ...IV_MEASURES_DATA_FIXTURE.crush, n: 0, bin_edges: [0.5], counts: [] })).ok).toBe(true)
  })
  it('accepts equal quantiles (non-decreasing is enough), zeros in the counts and negative edges', () => {
    const flat = { p10: 0.05, p25: 0.05, p50: 0.05, p75: 0.05, p90: 0.05 }
    expect(parseIvMeasures(edited(['implied_move', 'quantiles'], flat)).ok).toBe(true)
    expect(parseIvMeasures(edited(['crush', 'counts'], [0, 0, 9])).ok).toBe(true)
    expect(parseIvMeasures(edited(['crush', 'bin_edges'], [-3, -2, -1, 0])).ok).toBe(true)
  })
  it('accepts the edges of every count range: n = n_identified, n_nonpositive = n_identified, n_nonpositive = 0', () => {
    const base = IV_MEASURES_DATA_FIXTURE.implied_move
    expect(parseIvMeasures(edited(['implied_move'], { ...base, n_identified: 7, n_nonpositive: 0 })).ok).toBe(true) // n = n_identified = 7
    expect(parseIvMeasures(edited(['implied_move'], { ...base, n_identified: 7, n_nonpositive: 7 })).ok).toBe(true) // n_nonpositive = n_identified
  })
  it('allows an n_events of 0 and a decimal move that is negative (any finite sqrt_mean_evar)', () => {
    expect(parseIvMeasures(edited(['sample', 'n_events'], 0)).ok).toBe(true)
    expect(parseIvMeasures(edited(['implied_move', 'sqrt_mean_evar'], -0.5)).ok).toBe(true)
  })
})

describe('parseIvMeasures: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'iv', 5, true]) expect(errorOf(x), String(x)).toContain('iv measures data must be a JSON object')
    expect(errorOf(null)).toBe('iv measures data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`iv measures data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it', () => {
    expect(errorOf(edited(['histogram'], []))).toBe(`iv measures data has unexpected key(s): histogram (expected exactly: ${KEY_LIST})`)
  })
  it('reports missing and extra keys together', () => {
    const input = edited(['caveats'], undefined) as Record<string, unknown>
    input.note = 'x'
    expect(errorOf(input)).toContain('missing key(s): caveats; unexpected key(s): note')
  })
  it.each<[string, Path, unknown, string]>([
    ['sample lacks n_events', ['sample', 'n_events'], undefined, 'sample has missing key(s): n_events (expected exactly: label, n_events)'],
    ['sample has an extra key', ['sample', 'n_securities'], 3, 'sample has unexpected key(s): n_securities (expected exactly: label, n_events)'],
    ['implied_move lacks counts', ['implied_move', 'counts'], undefined, `implied_move has missing key(s): counts (expected exactly: ${IMPLIED_MOVE_KEYS})`],
    ['implied_move lacks sqrt_mean_evar (null is not the same as missing)', ['implied_move', 'sqrt_mean_evar'], undefined, `implied_move has missing key(s): sqrt_mean_evar (expected exactly: ${IMPLIED_MOVE_KEYS})`],
    ['implied_move has an extra key', ['implied_move', 'median'], 0.03, `implied_move has unexpected key(s): median (expected exactly: ${IMPLIED_MOVE_KEYS})`],
    ['crush lacks mean', ['crush', 'mean'], undefined, `crush has missing key(s): mean (expected exactly: ${CRUSH_KEYS})`],
    ['crush has an extra key', ['crush', 'n_identified'], 9, `crush has unexpected key(s): n_identified (expected exactly: ${CRUSH_KEYS})`],
    ['implied_move quantiles lack p50', ['implied_move', 'quantiles', 'p50'], undefined, 'implied_move.quantiles has missing key(s): p50 (expected exactly: p10, p25, p50, p75, p90)'],
    ['crush quantiles have a p95', ['crush', 'quantiles', 'p95'], 0, 'crush.quantiles has unexpected key(s): p95 (expected exactly: p10, p25, p50, p75, p90)'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
  it('lists the quantiles in the order p10 .. p90', () => {
    expect(QUANTILE_NAMES).toEqual(['p10', 'p25', 'p50', 'p75', 'p90'])
  })
})

describe('parseIvMeasures: sample and the counts of implied_move and crush', () => {
  it.each<[string, Path, unknown, string]>([
    ['sample is null', ['sample'], null, 'sample must be an object, got null'],
    ['sample is an array', ['sample'], [], 'sample must be an object, got an array'],
    ['sample label is empty', ['sample', 'label'], '', 'sample.label must be a non-empty string, got ""'],
    ['sample label is blank', ['sample', 'label'], '  ', 'sample.label must be a non-empty string, got "  "'],
    ['sample label is a number', ['sample', 'label'], 1, 'sample.label must be a non-empty string, got number 1'],
    ['sample n_events is negative', ['sample', 'n_events'], -1, 'sample.n_events must be a non-negative integer, got number -1'],
    ['sample n_events is a string', ['sample', 'n_events'], '12', 'sample.n_events must be a non-negative integer, got "12"'],
    ['sample n_events is fractional', ['sample', 'n_events'], 12.5, 'sample.n_events must be a non-negative integer, got number 12.5'],
    ['implied_move is a string', ['implied_move'], 'x', 'implied_move must be an object, got "x"'],
    ['implied_move units is empty', ['implied_move', 'units'], '', 'implied_move.units must be a non-empty string, got ""'],
    ['implied_move units is null', ['implied_move', 'units'], null, 'implied_move.units must be a non-empty string, got null'],
    ['n_identified is negative', ['implied_move', 'n_identified'], -1, 'implied_move.n_identified must be a non-negative integer, got number -1'],
    ['n_identified is a string', ['implied_move', 'n_identified'], '8', 'implied_move.n_identified must be a non-negative integer, got "8"'],
    ['n_nonpositive is fractional', ['implied_move', 'n_nonpositive'], 0.5, 'implied_move.n_nonpositive must be a non-negative integer, got number 0.5'],
    ['n is null', ['implied_move', 'n'], null, 'implied_move.n must be a non-negative integer, got null'],
    ['n_nonpositive is above n_identified', ['implied_move', 'n_nonpositive'], 9, 'implied_move.n_nonpositive must be at most n_identified (8), got number 9'],
    ['n is above n_identified', ['implied_move', 'n'], 9, 'implied_move.n must be at most n_identified (8), got number 9'],
    ['sqrt_mean_evar is NaN', ['implied_move', 'sqrt_mean_evar'], NaN, 'implied_move.sqrt_mean_evar must be a finite number or null, got number NaN'],
    ['sqrt_mean_evar is Infinity', ['implied_move', 'sqrt_mean_evar'], Infinity, 'implied_move.sqrt_mean_evar must be a finite number or null, got number Infinity'],
    ['sqrt_mean_evar is a string', ['implied_move', 'sqrt_mean_evar'], '0.04', 'implied_move.sqrt_mean_evar must be a finite number or null, got "0.04"'],
    ['crush is null', ['crush'], null, 'crush must be an object, got null'],
    ['crush units is blank', ['crush', 'units'], ' ', 'crush.units must be a non-empty string, got " "'],
    ['crush n is negative', ['crush', 'n'], -9, 'crush.n must be a non-negative integer, got number -9'],
    ['crush n is fractional', ['crush', 'n'], 9.5, 'crush.n must be a non-negative integer, got number 9.5'],
    ['crush mean is NaN', ['crush', 'mean'], NaN, 'crush.mean must be a finite number or null, got number NaN'],
    ['crush mean is -Infinity', ['crush', 'mean'], -Infinity, 'crush.mean must be a finite number or null, got number -Infinity'],
    ['crush mean is a string', ['crush', 'mean'], '-0.2', 'crush.mean must be a finite number or null, got "-0.2"'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toBe(message)
  })
})

describe.each(['implied_move', 'crush'] as const)('parseIvMeasures: quantiles of %s', (measure) => {
  const q = (name: string) => [measure, 'quantiles', name]
  const where = `${measure}.quantiles`
  it('rejects a value that is neither null nor an object', () => {
    expect(errorOf(edited([measure, 'quantiles'], 'x'))).toBe(`${where} must be null or an object, got "x"`)
    expect(errorOf(edited([measure, 'quantiles'], [1, 2, 3, 4, 5]))).toBe(`${where} must be null or an object, got an array`)
    expect(errorOf(edited([measure, 'quantiles'], 0))).toBe(`${where} must be null or an object, got number 0`)
  })
  it('does not treat a missing key as null', () => {
    expect(errorOf(edited([measure, 'quantiles'], undefined))).toContain(`${measure} has missing key(s): quantiles`)
  })
  it.each(QUANTILE_NAMES)('requires %s to be a finite number', (name) => {
    expect(errorOf(edited(q(name), NaN))).toBe(`${where}.${name} must be a finite number, got number NaN`)
    expect(errorOf(edited(q(name), Infinity))).toBe(`${where}.${name} must be a finite number, got number Infinity`)
    expect(errorOf(edited(q(name), '0.1'))).toBe(`${where}.${name} must be a finite number, got "0.1"`)
    expect(errorOf(edited(q(name), null))).toBe(`${where}.${name} must be a finite number, got null`)
  })
  // The fixture quantiles are strictly increasing, so setting one below its left neighbour breaks only that step.
  it.each<[string, string]>([
    ['p10', 'p25'],
    ['p25', 'p50'],
    ['p50', 'p75'],
    ['p75', 'p90'],
  ])('rejects %s > %s (the order must be p10 <= p25 <= p50 <= p75 <= p90)', (before, after) => {
    const input = edited(q(after), -100) as Record<string, Record<string, Record<string, number>>>
    const beforeValue = input[measure].quantiles[before]
    expect(errorOf(input)).toBe(`${where} must not decrease from ${before} to ${after}, but ${after} (-100) is below ${before} (${beforeValue})`)
  })
  it('names the first decreasing step when several decrease', () => {
    const bad = { p10: 5, p25: 4, p50: 3, p75: 2, p90: 1 }
    expect(errorOf(edited([measure, 'quantiles'], bad))).toBe(`${where} must not decrease from p10 to p25, but p25 (4) is below p10 (5)`)
  })
})

describe.each([
  ['implied_move', 7],
  ['crush', 9],
] as const)('parseIvMeasures: histogram of %s (n = %i)', (measure, n) => {
  const where = measure
  const e = (field: 'bin_edges' | 'counts', value: unknown) => edited([measure, field], value)
  it('rejects bin_edges that are not an array', () => {
    expect(errorOf(e('bin_edges', null))).toBe(`${where}.bin_edges must be an array, got null`)
    expect(errorOf(e('bin_edges', '0,1'))).toBe(`${where}.bin_edges must be an array, got "0,1"`)
    expect(errorOf(e('bin_edges', {}))).toBe(`${where}.bin_edges must be an array, got an object`)
  })
  it('rejects an edge that is not a finite number', () => {
    expect(errorOf(e('bin_edges', [0.01, NaN, 0.03, 0.04]))).toBe(`${where}.bin_edges[1] must be a finite number, got number NaN`)
    expect(errorOf(e('bin_edges', [0.01, 0.02, 0.03, Infinity]))).toBe(`${where}.bin_edges[3] must be a finite number, got number Infinity`)
    expect(errorOf(e('bin_edges', [0.01, 0.02, '0.03', 0.04]))).toBe(`${where}.bin_edges[2] must be a finite number, got "0.03"`)
    expect(errorOf(e('bin_edges', [null, 0.02, 0.03, 0.04]))).toBe(`${where}.bin_edges[0] must be a finite number, got null`)
  })
  it('rejects edges that do not strictly increase: equal neighbours, a step back, a reversed list', () => {
    expect(errorOf(e('bin_edges', [0.01, 0.02, 0.02, 0.04]))).toBe(`${where}.bin_edges must be strictly increasing, but bin_edges[2] (0.02) is not above bin_edges[1] (0.02)`)
    expect(errorOf(e('bin_edges', [0.01, 0.03, 0.02, 0.04]))).toBe(`${where}.bin_edges must be strictly increasing, but bin_edges[2] (0.02) is not above bin_edges[1] (0.03)`)
    expect(errorOf(e('bin_edges', [0.04, 0.03, 0.02, 0.01]))).toBe(`${where}.bin_edges must be strictly increasing, but bin_edges[1] (0.03) is not above bin_edges[0] (0.04)`)
  })
  it('rejects counts that are not an array', () => {
    expect(errorOf(e('counts', null))).toBe(`${where}.counts must be an array, got null`)
    expect(errorOf(e('counts', 7))).toBe(`${where}.counts must be an array, got number 7`)
  })
  it('rejects a count that is not a non-negative integer', () => {
    expect(errorOf(e('counts', [1, -1, 2]))).toBe(`${where}.counts[1] must be a non-negative integer, got number -1`)
    expect(errorOf(e('counts', [1, 4.5, 2]))).toBe(`${where}.counts[1] must be a non-negative integer, got number 4.5`)
    expect(errorOf(e('counts', [1, 4, '2']))).toBe(`${where}.counts[2] must be a non-negative integer, got "2"`)
    expect(errorOf(e('counts', [NaN, 4, 2]))).toBe(`${where}.counts[0] must be a non-negative integer, got number NaN`)
  })
  it('rejects a length mismatch: edges must be exactly one more than counts', () => {
    const edgesOf = (k: number) => Array.from({ length: k }, (_, i) => i / 10)
    // 3 counts: 3 edges, 5 edges, 0 edges are all wrong; 4 is right.
    expect(errorOf(e('bin_edges', edgesOf(3)))).toBe(`${where}.bin_edges must have one more entry than counts (or both be empty), got 3 edges and 3 counts`)
    expect(errorOf(e('bin_edges', edgesOf(5)))).toBe(`${where}.bin_edges must have one more entry than counts (or both be empty), got 5 edges and 3 counts`)
    expect(errorOf(e('bin_edges', []))).toBe(`${where}.bin_edges must have one more entry than counts (or both be empty), got 0 edges and 3 counts`)
  })
  it('rejects counts with no bins to put them in (empty edges are only valid with empty counts, and the other way round)', () => {
    expect(errorOf(e('counts', []))).toBe(`${where}.bin_edges must have one more entry than counts (or both be empty), got 4 edges and 0 counts`)
  })
  it('rejects counts whose sum is not n, saying both numbers', () => {
    const sum = measure === 'crush' ? [0, 3, 5] : [1, 4, 1] // one short
    expect(errorOf(e('counts', sum))).toBe(`${where}.counts add up to ${n - 1}, but n is ${n}`)
    const over = measure === 'crush' ? [0, 3, 7] : [1, 4, 3] // one over
    expect(errorOf(e('counts', over))).toBe(`${where}.counts add up to ${n + 1}, but n is ${n}`)
  })
  it('rejects both arrays empty while n is not 0', () => {
    expect(errorOf(edited([measure], { ...IV_MEASURES_DATA_FIXTURE[measure], ...EMPTY }))).toBe(`${where}.counts add up to 0, but n is ${n}`)
  })
  it('rejects a changed n whose counts still add up to the old n', () => {
    expect(errorOf(edited([measure, 'n'], n - 1))).toBe(`${where}.counts add up to ${n}, but n is ${n - 1}`)
  })
})

describe('parseIvMeasures: caveats and provenance', () => {
  it.each<[string, Path, unknown, string]>([
    ['caveats is a string', ['caveats'], 'one caveat', 'caveats must be an array, got "one caveat"'],
    ['caveats is null', ['caveats'], null, 'caveats must be an array, got null'],
    ['a caveat is empty', ['caveats', 1], '', 'caveats[1] must be a non-empty string, got ""'],
    ['a caveat is blank', ['caveats', 0], '   ', 'caveats[0] must be a non-empty string'],
    ['a caveat is a number', ['caveats', 0], 4, 'caveats[0] must be a non-empty string, got number 4'],
    ['provenance is null', ['provenance'], null, 'provenance must be an object, got null'],
    ['provenance lacks a key', ['provenance', 'params_hash'], undefined, 'provenance has missing key(s): params_hash'],
    ['provenance has an extra key', ['provenance', 'branch'], 'main', 'provenance has unexpected key(s): branch'],
    ['provenance dolt commit is empty', ['provenance', 'dolt_commits', 'options'], '', 'provenance.dolt_commits.options must be a non-empty string'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
})

describe('IV_MEASURES_URL and IV_MEASURES_KIND', () => {
  it('is a relative url (no leading slash, no scheme) so the app works under a sub-path', () => {
    expect(IV_MEASURES_URL).toBe('data/iv_measures.json')
  })
  it('names the kind the Python exporter writes', () => {
    expect(IV_MEASURES_KIND).toBe('iv_measures')
  })
})

describe('loadIvMeasures', () => {
  /** A fake fetch that answers with the given Response-like object. */
  const fakeFetch = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
  const serving = (body: unknown) => fakeFetch({ ok: true, status: 200, json: async () => body })

  it('returns the validated data for a good response, requesting the given URL without cache', async () => {
    const f = serving(IV_MEASURES_FIXTURE)
    const r = await loadIvMeasures('x/iv_measures.json', f)
    expect(r).toEqual({ ok: true, data: IV_MEASURES_DATA_FIXTURE })
    expect(f).toHaveBeenCalledWith('x/iv_measures.json', { cache: 'no-cache' })
  })
  it('defaults to the global fetch and the relative IV_MEASURES_URL', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200, json: async () => IV_MEASURES_FIXTURE } as Response)
    const r = await loadIvMeasures()
    expect(r.ok).toBe(true)
    expect(spy).toHaveBeenCalledWith('data/iv_measures.json', { cache: 'no-cache' })
    spy.mockRestore()
  })
  it('reports a network failure without throwing', async () => {
    const f = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }) as unknown as typeof fetch
    expect(await loadIvMeasures('data/iv_measures.json', f)).toEqual({ ok: false, error: 'could not fetch data/iv_measures.json: Failed to fetch' })
  })
  it('reports an HTTP error status', async () => {
    const r = await loadIvMeasures('data/iv_measures.json', fakeFetch({ ok: false, status: 404 }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('data/iv_measures.json returned HTTP 404')
  })
  it('reports a body that is not JSON', async () => {
    const f = fakeFetch({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })
    const r = await loadIvMeasures('data/iv_measures.json', f)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('is not valid JSON')
  })
  it('passes envelope violations through (here: the previous schema version)', async () => {
    const r = await loadIvMeasures('data/iv_measures.json', serving({ ...IV_MEASURES_FIXTURE, schema_version: '0.2.0' }))
    expect(r).toEqual({ ok: false, error: 'unsupported schema_version "0.2.0": this app only understands "0.3.0"' })
  })
  it('refuses a valid envelope of another kind, naming both kinds', async () => {
    const r = await loadIvMeasures('data/iv_measures.json', serving({ ...IV_MEASURES_FIXTURE, kind: 'sample_funnel' }))
    expect(r).toEqual({ ok: false, error: 'data/iv_measures.json has kind "sample_funnel", expected "iv_measures"' })
  })
  it('names the file and the rule when the data has the wrong shape', async () => {
    const broken = { ...IV_MEASURES_FIXTURE, data: edited(['crush', 'counts'], [0, 3, 5]) }
    const r = await loadIvMeasures('data/iv_measures.json', serving(broken))
    expect(r).toEqual({ ok: false, error: 'data/iv_measures.json: crush.counts add up to 8, but n is 9' })
  })
  it('checks the kind before looking at the data (a funnel file is not reported as a bad iv file)', async () => {
    const r = await loadIvMeasures('data/iv_measures.json', serving({ ...IV_MEASURES_FIXTURE, kind: 'meta', data: { milestone: 1 } }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('expected "iv_measures"')
  })
})
